#!/usr/bin/env python3
"""Archive contract checks; these do not replace an import test in Moodle."""
from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET
from zipfile import ZipFile, ZIP_STORED
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parent
EXPECTED = {'preset.xml', 'singletemplate.html', 'listtemplate.html',
            'listtemplateheader.html', 'listtemplatefooter.html', 'addtemplate.html',
            'asearchtemplate.html', 'rsstemplate.html', 'rsstitletemplate.html',
            'csstemplate.css', 'jstemplate.js'}
SETTING_NAMES = {'intro', 'comments', 'requiredentries', 'requiredentriestoview',
                 'maxentries', 'rssarticles', 'approval', 'defaultsortdir', 'defaultsort'}


class PresetTests(unittest.TestCase):
    def test_site_export_variant(self):
        native_order = ['listtemplate.html', 'singletemplate.html', 'asearchtemplate.html',
                        'addtemplate.html', 'rsstemplate.html', 'csstemplate.css', 'jstemplate.js',
                        'listtemplateheader.html', 'listtemplatefooter.html', 'rsstitletemplate.html', 'preset.xml']
        for slug in ('intro-cyber', 'fifth-dimension'):
            with self.subTest(course=slug), ZipFile(ROOT / f'{slug}-acquaintance-site.zip') as z, TemporaryDirectory() as d:
                self.assertEqual(z.namelist(), native_order)
                self.assertIsNone(z.testzip())
                z.extractall(d)
                for name in native_order:
                    self.assertEqual((Path(d) / name).read_bytes(), z.read(name))
                self.assertEqual(z.read('jstemplate.js'), b'')
                self.assertEqual(z.read('listtemplatefooter.html'), b'</div>\n')
                root = ET.fromstring(z.read('preset.xml'))
                self.assertEqual(root.findtext('settings/manageapproved'), '1')
                self.assertEqual(root.findtext('settings/defaultsort'), '0')
                self.assertEqual(root.findtext('settings/comments'), '1')
                self.assertEqual(root.findtext('settings/maxentries'), '1')
                fields = root.findall('field')
                self.assertEqual(len(fields), 7)
                names = [f.findtext('name') for f in fields]
                for template in ('addtemplate.html', 'listtemplate.html', 'singletemplate.html'):
                    self.assertCountEqual(re.findall(r'\[\[(.*?)\]\]', z.read(template).decode()), names)
                self.assertEqual([f.findtext('name') for f in fields if f.findtext('required') == '0'], ['מחוץ לעבודה'])

    def test_compatible_zip_extraction(self):
        for slug in ('intro-cyber', 'fifth-dimension'):
            with self.subTest(course=slug), TemporaryDirectory() as directory:
                with ZipFile(ROOT / f'{slug}-acquaintance.zip') as original, ZipFile(ROOT / f'{slug}-acquaintance-v2.zip') as compatible:
                    self.assertIsNone(compatible.testzip())
                    self.assertEqual(set(compatible.namelist()), EXPECTED)
                    for entry in compatible.infolist():
                        self.assertEqual(entry.compress_type, ZIP_STORED)
                        self.assertEqual(entry.create_system, 0)
                        self.assertEqual(entry.external_attr, 0x20)
                        self.assertFalse(entry.flag_bits & 1)  # Not encrypted.
                        self.assertFalse(entry.is_dir())
                        self.assertEqual(entry.extra, b'')
                        self.assertEqual(compatible.read(entry), original.read(entry.filename))
                    compatible.extractall(directory)
                extracted = Path(directory)
                self.assertEqual({p.name for p in extracted.iterdir()}, EXPECTED)
                for p in extracted.iterdir():
                    self.assertEqual(p.read_bytes(), (ROOT / 'sources' / slug / p.name).read_bytes())
                self.assertEqual(len(ET.parse(extracted / 'preset.xml').findall('field')), 7)

    def test_import_contract(self):
        for slug in ('intro-cyber', 'fifth-dimension'):
            with self.subTest(course=slug), ZipFile(ROOT / f'{slug}-acquaintance.zip') as z:
                self.assertIsNone(z.testzip())
                self.assertEqual(set(z.namelist()), EXPECTED)
                contents = {n: z.read(n).decode('utf-8') for n in z.namelist()}
                for n, content in contents.items():
                    self.assertEqual(content, (ROOT / 'sources' / slug / n).read_text(encoding='utf-8'))
                root = ET.fromstring(contents['preset.xml'])
                self.assertEqual(root.tag, 'preset')
                settings = {el.tag: el.text for el in root.find('settings')}
                self.assertEqual(set(settings), SETTING_NAMES)
                for key, value in {'comments': '1', 'maxentries': '1', 'approval': '0',
                                   'requiredentriestoview': '0', 'rssarticles': '0'}.items():
                    self.assertEqual(settings[key], value)
                fields = root.findall('field')
                names = [f.findtext('name') for f in fields]
                self.assertEqual(len(names), 7)
                self.assertEqual(len(set(names)), 7)
                self.assertIn(settings['defaultsort'], names)
                self.assertEqual([f.findtext('name') for f in fields if f.findtext('required') == '0'], ['מחוץ לעבודה'])
                for f in fields:
                    self.assertIn(f.findtext('type'), ('text', 'textarea'))
                    self.assertTrue(f.findtext('description'))
                for filename, content in contents.items():
                    if not filename.endswith('.html'):
                        continue
                    self.assertLessEqual(set(re.findall(r'\[\[(.*?)\]\]', content)), set(names))
                    self.assertLessEqual(set(re.findall(r'##(.*?)##', content)), {'user', 'moreurl', 'edit', 'delete', 'comments'})
                    self.assertNotIn('<script', content)
                for template in ('addtemplate.html', 'singletemplate.html', 'listtemplate.html', 'asearchtemplate.html'):
                    self.assertCountEqual(re.findall(r'\[\[(.*?)\]\]', contents[template]), names)
                    self.assertIn('dir="rtl"', contents[template])
                    self.assertIn('lang="he"', contents[template])
                self.assertIn('##comments##', contents['singletemplate.html'])
                self.assertIn('href="##moreurl##"', contents['listtemplate.html'])
                self.assertNotRegex(contents['csstemplate.css'], r'(?:margin|padding|border)-(?:left|right)|text-align:\s*(?:left|right)')

    def test_course_separation(self):
        with ZipFile(ROOT / 'intro-cyber-acquaintance.zip') as a, ZipFile(ROOT / 'fifth-dimension-acquaintance.zip') as b:
            intro = a.read('addtemplate.html').decode()
            fifth = b.read('addtemplate.html').decode()
            self.assertIn('מבוא לסייבר', intro)
            self.assertNotIn('הממד החמישי', intro)
            self.assertIn('סייבר — הממד החמישי', fifth)
            self.assertNotIn('מבוא לסייבר', fifth)
            self.assertIn('יחסים בינלאומיים', fifth)
            self.assertNotEqual(intro, fifth)


if __name__ == '__main__':
    unittest.main()
