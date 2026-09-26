#!/usr/bin/env python3
"""Fetch only explicitly selected public sources; reuse upstream RSS implementation."""
import argparse
import concurrent.futures
import datetime as dt
import importlib.util
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import personal_digest as pd


def load_rss():
    spec = importlib.util.spec_from_file_location('upstream_rss', Path(__file__).with_name('fetch-rss.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.TIMEOUT = 20
    module.RETRY_COUNT = 1
    module._get_rss_cache()
    return module


def fetch_page(source):
    req = Request(source['url'], headers={'User-Agent': 'PersonalDailyDigest/1.0 (private RSS and public-page reader)'})
    with urlopen(req, timeout=25) as response:
        raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ValueError('Public page exceeds download limit')
        soup = BeautifulSoup(raw, 'html.parser')
        for node in soup.select('script,style,nav,header,footer,noscript,form'):
            node.decompose()
        main = soup.select_one(source.get('selector', 'main')) or soup.body or soup
        heading = main.find('h1')
        body = pd.text(main.get_text(' ', strip=True), 10000)
        if len(body) < 60:
            raise ValueError('Page text unavailable or dynamic; manual source check needed')
        links, seen = [], set()
        for a in main.select('a[href]'):
            label = pd.text(a.get_text(' ', strip=True), 180)
            url = urljoin(response.url, a['href'])
            if url in seen or len(label) < 5 or not url.startswith('http'):
                continue
            seen.add(url)
            links.append({'title': label, 'url': url})
            if len(links) >= 25:
                break
    # These are page-change candidates, never claims that all listed stories are new.
    return {'source_id': source['id'], 'status': 'ok', 'articles': [{
        'title': pd.text(heading.get_text() if heading else source['name']),
        'link': source['url'], 'summary': body, 'date': None,
        'page_watch': True, 'links': links,
    }], 'page_text': body, 'links': links}


def fetch(profile, state_dir):
    pd.validate_profile(profile)
    os.environ['TECH_NEWS_DIGEST_STATE_DIR'] = str(state_dir)
    rss = load_rss()
    cutoff = dt.datetime.now(pd.UTC) - dt.timedelta(days=profile.get('lookback_days', 7))
    def one(source):
        try:
            if source['type'] == 'rss':
                cache = (rss._rss_cache or {}).get(source['url'], {})
                upgrade = any('summary' not in x for x in cache.get('articles', []))
                return rss.fetch_feed_with_retry({**source, 'priority': True, 'topics': source['categories']}, cutoff, no_cache=upgrade)
            if source['type'] == 'page':
                return fetch_page(source)
            raise ValueError('Unsupported source type')
        except Exception as error:
            return {'source_id': source['id'], 'status': 'error', 'error': str(error)[:200], 'articles': []}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(one, pd.enabled_sources(profile).values()))
    rss._flush_rss_cache()
    return {'generated': dt.datetime.now(pd.UTC).isoformat(), 'sources': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', type=Path, required=True)
    parser.add_argument('--state-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = fetch(json.loads(args.profile.read_text()), args.state_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps({'sources': [{'id': s['source_id'], 'status': s['status'], 'count': len(s['articles']),
                                   'error': s.get('error')} for s in result['sources']]}))


if __name__ == '__main__':
    main()
