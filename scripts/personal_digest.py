#!/usr/bin/env python3
"""Strict opt-in selection and durable delivery ledger. Never calls a model.

Upstream fetch-rss/fetch-github output is input data, not executable instructions.
Private profile and SQLite state must live outside this repository.
"""
import argparse
import datetime as dt
import hashlib
import html
import json
import re
import sqlite3
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

CATEGORIES = {
    'A': 'AI / Codex / ChatGPT / 自动化', 'B': 'PTE / 英语学习',
    'C': '澳洲中教 / 教学资源 / 实习就业', 'D': '南澳移民政策',
    'E': '澳洲生活 / 本地活动 / 优惠', 'F': '全球重大新闻 / 经济科技',
    'G': 'Apple / iOS / 独立开发', 'H': '商业创业 / 效率工具',
    'I': '科学研究 / 其他爱好',
}
UTC = dt.timezone.utc


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def text(value, limit=2000):
    return re.sub(r'\s+', ' ', html.unescape(re.sub('<[^>]+>', '', str(value or '')))).strip()[:limit]


def canonical_url(value):
    u = urlsplit(value)
    if u.scheme not in ('https', 'http') or not u.hostname or u.username or u.password:
        raise ValueError('Only public HTTP(S) source links are supported')
    query = [(k, v) for k, v in parse_qsl(u.query, keep_blank_values=True)
             if not k.lower().startswith('utm_') and k.lower() not in ('fbclid', 'gclid')]
    return urlunsplit((u.scheme.lower(), u.netloc.lower(), u.path or '/', urlencode(sorted(query)), ''))


def validate_profile(p):
    if p.get('selection_status') != 'confirmed':
        raise ValueError('Interest and budget choices are not confirmed')
    categories = p.get('categories', [])
    if not categories or len(set(categories)) != len(categories) or any(x not in CATEGORIES for x in categories):
        raise ValueError('Choose unique category IDs from the catalog')
    if p.get('mode') not in ('original', 'review_queue'):
        raise ValueError('Choose original or review_queue; no automatic model provider is configured')
    ZoneInfo(p['timezone'])
    cap = p.get('max_items', 10)
    if type(cap) is not int or not 1 <= cap <= 20:
        raise ValueError('max_items must be 1–20')
    sources = p.get('sources', [])
    ids = set()
    for s in sources:
        if s['id'] in ids or not s.get('categories') or not set(s['categories']) <= set(CATEGORIES):
            raise ValueError('Each source requires unique ID and known categories')
        ids.add(s['id'])
    if not sources:
        raise ValueError('Explicit source allowlist is required; upstream defaults are never enabled')
    return p


def open_ledger(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    db = sqlite3.connect(path, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.executescript('''
    CREATE TABLE IF NOT EXISTS versions (
      key TEXT PRIMARY KEY, url TEXT NOT NULL, version TEXT NOT NULL,
      source_id TEXT NOT NULL, payload TEXT NOT NULL, first_seen TEXT NOT NULL,
      delivered_batch TEXT);
    CREATE TABLE IF NOT EXISTS batches (
      id TEXT PRIMARY KEY, day TEXT NOT NULL, payload TEXT NOT NULL,
      created TEXT NOT NULL, delivered TEXT, receipt TEXT);
    CREATE TABLE IF NOT EXISTS source_checks (
      source_id TEXT PRIMARY KEY, checked TEXT NOT NULL, status TEXT NOT NULL);
    ''')
    path.chmod(0o600)
    return db


def enabled_sources(p):
    return {s['id']: s for s in p['sources'] if s.get('enabled', True)
            and set(s['categories']) & set(p['categories'])}


def collect(db, profile, fetched, now=None):
    validate_profile(profile)
    now = now or dt.datetime.now(UTC)
    allowed = enabled_sources(profile)
    results = {s['source_id']: s for s in fetched.get('sources', [])}
    failures, added = [], 0
    with db:
        for sid, source in allowed.items():
            result = results.get(sid)
            status = result.get('status', 'error') if result else 'missing'
            db.execute('INSERT OR REPLACE INTO source_checks VALUES(?,?,?)', (sid, now.isoformat(), status))
            if status != 'ok':
                failures.append({'source': sid, 'status': status})
                continue
            for a in result.get('articles', []):
                try:
                    url = canonical_url(a.get('link', a.get('url', '')))
                except ValueError:
                    failures.append({'source': sid, 'status': 'invalid_link'})
                    continue
                title = text(a.get('title'), 300)
                if not title:
                    continue
                full_summary = text(a.get('summary', a.get('description', '')), 2_000_000)
                summary = full_summary[:1600]
                excluded = profile.get('exclude_keywords', [])
                if any(x.casefold() in (title+' '+summary).casefold() for x in excluded if x):
                    continue
                date = a.get('date', a.get('published', ''))
                try:
                    parsed = dt.datetime.fromisoformat(date.replace('Z', '+00:00'))
                    if parsed.tzinfo is None:
                        raise ValueError('Missing timezone')
                    if parsed > now + dt.timedelta(hours=1):
                        raise ValueError('Future publication timestamp')
                    if parsed < now - dt.timedelta(days=profile.get('lookback_days', 7)):
                        continue
                    date = parsed.isoformat()
                except (ValueError, TypeError, AttributeError):
                    date = None
                version = digest([title, full_summary, a['content_hash']]) if a.get('content_hash') else digest([title, full_summary])
                key = digest([url, version])
                payload = {'key': key, 'url': url, 'title': title, 'summary': summary,
                           'published': date, 'source_id': sid, 'source_name': source.get('name', sid),
                           'categories': source['categories'], 'evidence': source.get('evidence', 'source'),
                           'collected': now.isoformat()}
                cur = db.execute('INSERT OR IGNORE INTO versions VALUES(?,?,?,?,?,?,NULL)',
                                 (key, url, version, sid, json.dumps(payload, ensure_ascii=False), now.isoformat()))
                added += cur.rowcount
    return {'added': added, 'failures': failures, 'checked': len(allowed), 'model_calls': 0}


def prepare_batch(db, profile, now=None):
    validate_profile(profile)
    now = now or dt.datetime.now(UTC)
    # Serialize batch preparation, including overlapping local scheduler runs.
    db.execute('BEGIN IMMEDIATE')
    try:
        old = db.execute('SELECT payload FROM batches WHERE delivered IS NULL ORDER BY created LIMIT 1').fetchone()
        allowed = enabled_sources(profile)
        if old:
            payload = json.loads(old['payload'])
            if any(x['source_id'] not in allowed or not (set(x['categories']) & set(profile['categories']))
                   for x in payload['items']):
                raise ValueError('Pending batch contains disabled interests/sources; review before delivery')
            db.commit()
            return payload
        pending = [json.loads(r['payload']) for r in db.execute('SELECT payload FROM versions WHERE delivered_batch IS NULL ORDER BY rowid DESC')]
        pending = [x for x in pending if x['source_id'] in allowed
                   and set(x['categories']) & set(profile['categories'])
                   and not any(k.casefold() in (x['title']+' '+x['summary']).casefold()
                               for k in profile.get('exclude_keywords', []) if k)]
        cutoff = now - dt.timedelta(days=profile.get('lookback_days', 7))
        pending = [x for x in pending if dt.datetime.fromisoformat(x['published'] or x['collected']) >= cutoff]
        for item in pending:
            item['categories'] = allowed[item['source_id']]['categories']
        latest = {}
        for item in pending:
            latest.setdefault(item['url'], item)
        pending = list(latest.values())
        priorities = {c: i for i, c in enumerate(profile['categories'])}
        pending.sort(key=lambda x: -(dt.datetime.fromisoformat(x['published']).timestamp() if x['published'] else 0))
        selected, used_urls, source_counts = [], set(), {}
        primary = profile.get('primary_categories', profile['categories'])
        groups = [primary, [c for c in profile['categories'] if c not in primary]]
        for group in groups:
            while len(selected) < profile.get('max_items', 10):
                found = False
                for category in group:
                    options = [x for x in pending if category in x['categories'] and x['url'] not in used_urls]
                    item = min(options, key=lambda x: source_counts.get(x['source_id'], 0)) if options else None
                    if item:
                        selected.append(item)
                        used_urls.add(item['url'])
                        source_counts[item['source_id']] = source_counts.get(item['source_id'], 0) + 1
                        found = True
                    if len(selected) >= profile.get('max_items', 10):
                        break
                if not found:
                    break
        if not selected:
            db.commit()
            return None
        day = now.astimezone(ZoneInfo(profile['timezone'])).date().isoformat()
        batch_id = digest([day, [x['key'] for x in selected]])[:24]
        payload = {'id': batch_id, 'day': day, 'mode': profile['mode'], 'items': selected,
                   'model_calls': 0, 'created': now.isoformat()}
        db.execute('INSERT INTO batches VALUES(?,?,?,?,NULL,NULL)',
                   (batch_id, day, json.dumps(payload, ensure_ascii=False), now.isoformat()))
        db.commit()
        return payload
    except Exception:
        db.rollback()
        raise


def acknowledge(db, batch_id, receipt):
    if not isinstance(receipt, dict) or not receipt.get('verified') or not receipt.get('target_id'):
        raise ValueError('A verified delivery receipt with target_id is required')
    with db:
        row = db.execute('SELECT * FROM batches WHERE id=?', (batch_id,)).fetchone()
        if not row:
            raise ValueError('Unknown batch')
        if row['delivered']:
            return
        batch = json.loads(row['payload'])
        for item in batch['items']:
            db.execute('UPDATE versions SET delivered_batch=? WHERE url=? AND first_seen<=?',
                       (batch_id, item['url'], item['collected']))
        db.execute('UPDATE batches SET delivered=?,receipt=? WHERE id=?',
                   (dt.datetime.now(UTC).isoformat(), json.dumps(receipt), batch_id))


def render(batch):
    lines = [f"每日信息 · {batch['day']}", '原标题与来源摘要；未调用模型。', '']
    for i, item in enumerate(batch['items'], 1):
        lines += [f"{i}. {item['title']}", f"来源：{item['source_name']}｜发布日期：{item['published'] or '未核实'}",
                  item['summary'], item['url'], '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', type=Path, required=True)
    parser.add_argument('--state', type=Path, required=True)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('validate')
    intake = sub.add_parser('collect')
    intake.add_argument('--input', type=Path, required=True)
    sub.add_parser('prepare')
    ack = sub.add_parser('ack')
    ack.add_argument('--batch', required=True)
    ack.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    profile = validate_profile(json.loads(args.profile.read_text()))
    if args.command == 'validate':
        print(json.dumps({'valid': True, 'enabled_sources': list(enabled_sources(profile))}))
        return
    db = open_ledger(args.state)
    if args.command == 'collect':
        result = collect(db, profile, json.loads(args.input.read_text()))
    elif args.command == 'prepare':
        result = prepare_batch(db, profile)
    else:
        acknowledge(db, args.batch, json.loads(args.receipt.read_text()))
        result = {'acknowledged': args.batch}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
