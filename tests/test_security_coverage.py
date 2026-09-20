"""Security collection and optional alert policy regression checks."""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('fetch_web_security', ROOT / 'scripts/fetch-web.py')
assert spec is not None and spec.loader is not None
web = importlib.util.module_from_spec(spec)
spec.loader.exec_module(web)


class SecurityCoverageTests(unittest.TestCase):
    def test_primary_alert_sources(self):
        sources = json.loads((ROOT / 'config/defaults/sources.json').read_text())['sources']
        for handle in ('SlowMist_Team', 'PeckShieldAlert', 'BlockSecTeam'):
            matches = [s for s in sources if s.get('handle') == handle]
            self.assertEqual(len(matches), 1)
            self.assertTrue(matches[0]['enabled'])
            self.assertTrue(matches[0]['priority'])
            self.assertIn('crypto', matches[0]['topics'])

    def test_scam_warning_is_not_excluded(self):
        topics = json.loads((ROOT / 'config/defaults/topics.json').read_text())['topics']
        search = next(t for t in topics if t['id'] == 'crypto')['search']
        self.assertTrue(web.filter_content('Wallet malware scam warning: private key theft', search['must_include'], search['exclude']))
        self.assertTrue(any('SlowMist' in q for q in search['queries']))

    def test_optional_alert_policy(self):
        prompt = (ROOT / 'references/digest-prompt.md').read_text()
        self.assertIn('## Mandatory Security Coverage Check', prompt)
        self.assertIn('Omit this heading entirely if no incident qualifies', prompt)
        self.assertIn('security_check', prompt)
        self.assertIn('Alerts count toward existing global item/body limits', prompt)


if __name__ == '__main__':
    unittest.main()
