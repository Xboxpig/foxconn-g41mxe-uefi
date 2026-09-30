#!/usr/bin/env python3
"""Local governance extension: exact fixtures cannot exempt new secrets."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / '.harness/runtime'))
from harnesslib import HarnessError, project_scan_files, secret_fixture_allowlist


class FixtureGate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='g41-harness-test-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root / 'vendor/test.txt'
        self.path.parent.mkdir()
        self.path.write_text('public synthetic vector\n', encoding='utf-8')
        self.manifest = self.root / 'fixtures.json'
        self.cfg = {'secret_scan': {'fixture_manifest': 'fixtures.json'}}
        self.row = {'path': 'vendor/test.txt', 'rule': 'credential-assignment',
                    'sha256': hashlib.sha256(self.path.read_bytes()).hexdigest(),
                    'lines': [1], 'reason': 'synthetic unit fixture, not real credential'}

    def save(self, rows=None):
        self.manifest.write_text(json.dumps({'schema': 'g41mxe-secret-fixtures/v1',
                                            'fixtures': [self.row] if rows is None else rows}))

    def test_exact_identity_and_location(self):
        self.save()
        allowed = secret_fixture_allowlist(self.root, self.cfg)
        self.assertEqual(allowed, {('vendor/test.txt', 1, 'credential-assignment')})
        self.assertNotIn(('vendor/test.txt', 2, 'credential-assignment'), allowed)
        self.assertNotIn(('other.txt', 1, 'credential-assignment'), allowed)
        self.assertNotIn(('vendor/test.txt', 1, 'github-token'), allowed)

    def test_no_config_no_exemptions(self):
        self.assertEqual(secret_fixture_allowlist(self.root, {}), set())

    def test_changed_content_rejected(self):
        self.save()
        self.path.write_text('modified vector\n')
        with self.assertRaises(HarnessError):
            secret_fixture_allowlist(self.root, self.cfg)

    def test_missing_file_rejected(self):
        self.row['path'] = 'absent.txt'
        self.save()
        with self.assertRaises(HarnessError):
            secret_fixture_allowlist(self.root, self.cfg)

    def test_escape_rejected(self):
        self.row['path'] = '../escape.txt'
        self.save()
        with self.assertRaises(HarnessError):
            secret_fixture_allowlist(self.root, self.cfg)

    def test_invalid_rule_reason_hash_and_lines(self):
        for key, value in [('rule', 'aws-access-key'), ('reason', ''),
                           ('sha256', 'bad'), ('lines', []), ('lines', [0]),
                           ('lines', [True]), ('lines', ['1'])]:
            with self.subTest(key=key, value=value):
                original = self.row[key]
                self.row[key] = value
                self.save()
                with self.assertRaises(HarnessError):
                    secret_fixture_allowlist(self.root, self.cfg)
                self.row[key] = original

    def test_duplicates_rejected(self):
        self.save([self.row, self.row])
        with self.assertRaises(HarnessError):
            secret_fixture_allowlist(self.root, self.cfg)

    def test_generated_copies_pruned_not_source(self):
        for name in ['build/copy', '.git/object', '.harness/venv/fixture',
                     'src/sub/build/maintained', 'src/board/code']:
            p = self.root / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text('synthetic\n')
        files = {p.relative_to(self.root).as_posix() for p in project_scan_files(self.root)}
        self.assertIn('vendor/test.txt', files)
        self.assertIn('src/board/code', files)
        self.assertIn('src/sub/build/maintained', files)
        self.assertNotIn('build/copy', files)
        self.assertNotIn('.git/object', files)
        self.assertNotIn('.harness/venv/fixture', files)


if __name__ == '__main__':
    unittest.main()
