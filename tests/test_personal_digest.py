import copy
import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import personal_digest as p

NOW = dt.datetime(2026, 9, 27, tzinfo=p.UTC)
PROFILE = {'selection_status': 'confirmed', 'mode': 'review_queue', 'timezone': 'Australia/Adelaide',
           'categories': ['E', 'F', 'D', 'A'], 'primary_categories': ['E', 'F', 'D'], 'max_items': 10,
           'sources': [{'id': c, 'categories': [c]} for c in ['E', 'F', 'D', 'A']]}


def fetched(category='E', title='News', link='https://example.com/one', date=None):
    return {'sources': [{'source_id': category, 'status': 'ok', 'articles': [
        {'title': title, 'link': link, 'summary': 'source summary', 'date': date or NOW.isoformat()}]}]}


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name)/'state.sqlite3'
        self.db = p.open_ledger(self.path)
        self.profile = copy.deepcopy(PROFILE)

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_unconfirmed_and_missing_source_config_stop(self):
        for change in [{'selection_status': 'pending'}, {'sources': []}]:
            with self.assertRaises(ValueError):
                p.collect(self.db, {**self.profile, **change}, fetched(), NOW)

    def test_repeated_input_and_restart_and_304(self):
        self.assertEqual(p.collect(self.db, self.profile, fetched(), NOW)['added'], 1)
        first = p.prepare_batch(self.db, self.profile, NOW)
        self.db.close()
        self.db = p.open_ledger(self.path)
        self.assertEqual(p.collect(self.db, self.profile, fetched(), NOW)['added'], 0)
        self.assertEqual(first, p.prepare_batch(self.db, self.profile, NOW))
        p.acknowledge(self.db, first['id'], {'verified': True, 'target_id': 'note-1'})
        self.assertIsNone(p.prepare_batch(self.db, self.profile, NOW))

    def test_changed_version_supersedes_unsent_version(self):
        p.collect(self.db, self.profile, fetched(title='v1'), NOW)
        p.collect(self.db, self.profile, fetched(title='v2'), NOW+dt.timedelta(minutes=1))
        b = p.prepare_batch(self.db, self.profile, NOW)
        self.assertEqual([x['title'] for x in b['items']], ['v2'])
        p.acknowledge(self.db, b['id'], {'verified': True, 'target_id': 'n'})
        self.assertIsNone(p.prepare_batch(self.db, self.profile, NOW))

    def test_changes_beyond_display_excerpt_are_detected(self):
        raw=fetched();raw['sources'][0]['articles'][0]['summary']='x'*1700+'old'
        self.assertEqual(p.collect(self.db,self.profile,raw,NOW)['added'],1)
        raw['sources'][0]['articles'][0]['summary']='x'*1700+'new'
        self.assertEqual(p.collect(self.db,self.profile,raw,NOW)['added'],1)

    def test_failure_is_not_empty_success(self):
        r = p.collect(self.db, self.profile, {'sources': []}, NOW)
        self.assertEqual(len(r['failures']), 4)
        self.assertEqual(r['model_calls'], 0)

    def test_disabled_source_does_not_leak_from_cache(self):
        p.collect(self.db, self.profile, fetched(), NOW)
        self.profile['sources'][0]['enabled'] = False
        self.assertIsNone(p.prepare_batch(self.db, self.profile, NOW))

    def test_pending_source_disable_requires_review(self):
        p.collect(self.db, self.profile, fetched(), NOW)
        p.prepare_batch(self.db, self.profile, NOW)
        self.profile['sources'][0]['enabled'] = False
        with self.assertRaises(ValueError):
            p.prepare_batch(self.db, self.profile, NOW)

    def test_priority_categories_share_space_before_fallback(self):
        for cat in ['E', 'F', 'D', 'A']:
            for i in range(5):
                p.collect(self.db, self.profile, fetched(cat, link=f'https://example.com/{cat}/{i}'), NOW)
        b = p.prepare_batch(self.db, self.profile, NOW)
        self.assertEqual([x['source_id'] for x in b['items'][:3]], ['E', 'F', 'D'])
        self.assertNotIn('A', [x['source_id'] for x in b['items']])

    def test_fallback_when_primary_has_no_items(self):
        p.collect(self.db, self.profile, fetched('A'), NOW)
        self.assertEqual(p.prepare_batch(self.db, self.profile, NOW)['items'][0]['source_id'], 'A')

    def test_tracking_links_deduplicate(self):
        p.collect(self.db, self.profile, fetched(link='https://example.com/one?utm_source=a'), NOW)
        self.assertEqual(p.collect(self.db, self.profile, fetched(), NOW)['added'], 0)

    def test_ack_requires_verified_receipt(self):
        p.collect(self.db, self.profile, fetched(), NOW)
        b = p.prepare_batch(self.db, self.profile, NOW)
        with self.assertRaises(ValueError):
            p.acknowledge(self.db, b['id'], {})
        self.assertEqual(p.prepare_batch(self.db, self.profile, NOW)['id'], b['id'])

    def test_old_cached_articles_are_filtered(self):
        r = p.collect(self.db, self.profile, fetched(date='2020-01-01T00:00:00Z'), NOW)
        self.assertEqual(r['added'], 0)

    def test_dst_day_uses_adelaide(self):
        later = dt.datetime(2026, 10, 4, 14, tzinfo=p.UTC)
        p.collect(self.db, self.profile, fetched(date=later.isoformat()), later)
        b = p.prepare_batch(self.db, self.profile, later)
        self.assertEqual(b['day'], '2026-10-05')


if __name__ == '__main__':
    unittest.main()
