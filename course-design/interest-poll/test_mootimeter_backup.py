#!/usr/bin/env python3
"""Structural checks for generated MBZs; not a live Moodle restore test."""
from pathlib import Path
import tarfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent / 'mootimeter-backup'

class BackupTests(unittest.TestCase):
    def test_backups(self):
        paths = sorted(ROOT.glob('*.mbz'))
        self.assertEqual(len(paths), 2)
        for path in paths:
            with self.subTest(file=path.name), tarfile.open(path) as archive:
                members = {m.name: m for m in archive.getmembers()}
                self.assertEqual(archive.getmembers()[0].name, '.ARCHIVE_INDEX')
                lines = archive.extractfile('.ARCHIVE_INDEX').read().decode().splitlines()
                self.assertEqual(int(lines[0].rsplit(': ', 1)[1]), len(members) - 1)
                self.assertEqual(len(lines) - 1, len(members) - 1)
                for line in lines[1:]:
                    name, kind, size, mtime = line.split('\t')
                    member = members[name.rstrip('/')]
                    self.assertEqual(member.isdir(), kind == 'd')
                    self.assertEqual(member.size, int(size))
                    if kind == 'f':
                        self.assertEqual(member.mtime, int(mtime))
                documents = {name: ET.fromstring(archive.extractfile(name).read()) for name in members if name.endswith('.xml')}
                for root in documents.values():
                    self.assertFalse(any(e.tag.endswith('_answers') or e.tag == 'user' for e in root.iter()))
                manifest = documents['moodle_backup.xml']
                source_settings = {s.findtext('name'): s.findtext('value') for s in manifest.findall('information/settings/setting')}
                self.assertEqual(source_settings['users'], '0')
                self.assertEqual(source_settings['filename'], path.name)
                entry = manifest.find('information/contents/activities/activity')
                prefix = entry.findtext('directory')
                module = documents[prefix + '/module.xml']
                self.assertEqual(module.attrib['version'], '2025121100')
                self.assertEqual(module.findtext('visible'), '0')
                content = documents[prefix + '/mootimeter.xml']
                mt = content.find('mootimeter')
                self.assertEqual(entry.findtext('title'), mt.findtext('name'))
                pages = mt.findall('pages/page')
                self.assertEqual([p.findtext('tool') for p in pages], ['poll'] * 4 + ['wordcloud'])
                self.assertEqual([p.findtext('sortorder') for p in pages], ['0','1','2','3','4'])
                self.assertEqual(len({p.attrib['id'] for p in pages}), 5)
                optionids, settingids = [], []
                for page in pages:
                    self.assertEqual(page.findtext('instance'), mt.attrib['id'])
                    config = {}
                    for setting in page.findall('tool_settings/tool_setting'):
                        self.assertEqual(setting.findtext('pageid'), page.attrib['id'])
                        self.assertEqual(setting.findtext('tool'), page.findtext('tool'))
                        settingids.append(setting.attrib['id'])
                        config[setting.findtext('name')] = setting.findtext('value')
                    self.assertEqual(config['anonymousmode'], '1')
                    self.assertEqual(config['showonteacherpermission'], '0')
                    self.assertTrue(config['question'])
                    if page.findtext('tool') == 'poll':
                        self.assertEqual(config['maxanswersperuser'], '2')
                        options = page.findall('subplugin_mootimetertool_poll_page/mootimetertool_poll_options')
                        self.assertEqual(len(options), 7)
                        for option in options:
                            self.assertEqual(option.findtext('pageid'), page.attrib['id'])
                            self.assertTrue(option.findtext('optiontext'))
                            optionids.append(option.attrib['id'])
                    else:
                        self.assertEqual(config['maxinputsperuser'], '1')
                self.assertEqual(len(set(optionids)), 28)
                self.assertEqual(len(settingids), len(set(settingids)))
                other = 'הממד החמישי' if path.name.startswith('intro') else 'מבוא לסייבר'
                self.assertNotIn(other, mt.findtext('name'))
                self.assertNotIn(other, mt.findtext('intro'))

if __name__ == '__main__':
    unittest.main()
