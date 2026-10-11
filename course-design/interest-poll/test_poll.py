#!/usr/bin/env python3
"""Validate exported artifacts; does not run Moodle or Mootimeter."""
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

ROOT = Path(__file__).resolve().parent


class BoardParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.targets = []
        self.fields = {}
        self.current = None
        self.root = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'html':
            self.root = attrs
        if 'id' in attrs:
            self.ids.append(attrs['id'])
        if tag == 'button':
            self.targets.append(attrs['data-copy'])
        if tag == 'textarea':
            assert attrs['dir'] == 'auto'
            self.current = attrs['id']
            self.fields[self.current] = ''

    def handle_data(self, data):
        if self.current:
            self.fields[self.current] += data

    def handle_endtag(self, tag):
        if tag == 'textarea':
            self.current = None


class PollTests(unittest.TestCase):
    def test_feedback_import_structure(self):
        for slug in ('intro-cyber', 'fifth-dimension'):
            with self.subTest(course=slug):
                root = ET.parse(ROOT / f'{slug}-feedback.xml').getroot()
                self.assertEqual(root.tag, 'FEEDBACK')
                self.assertEqual(root.attrib['VERSION'], '200701')
                items = root.findall('./ITEMS/ITEM')
                self.assertEqual([i.attrib['TYPE'] for i in items], ['label'] + ['multichoice'] * 4 + ['textarea'])
                self.assertEqual([i.attrib['REQUIRED'] for i in items], ['0', '1', '1', '1', '1', '0'])
                self.assertEqual([i.findtext('ITEMID') for i in items], [str(i) for i in range(1, 7)])
                labels = [i.findtext('ITEMLABEL') for i in items[1:]]
                self.assertEqual(len(set(labels)), 5)
                for item in items:
                    self.assertEqual({c.tag for c in item}, {'ITEMID', 'ITEMTEXT', 'ITEMLABEL', 'PRESENTATION', 'OPTIONS', 'DEPENDITEM', 'DEPENDVALUE'})
                    self.assertEqual(item.findtext('DEPENDITEM'), '0')
                for item in items[1:5]:
                    kind, presentation = item.findtext('PRESENTATION').split('>>>>>')
                    answers, layout = presentation.split('<<<<<')
                    self.assertEqual(kind, 'r')
                    self.assertEqual(layout, '0')
                    self.assertEqual(len(answers.split('|')), 7)
                    self.assertEqual(len(set(answers.split('|'))), 7)
                    self.assertEqual(item.findtext('OPTIONS'), 'h')
                self.assertEqual(items[-1].findtext('PRESENTATION'), '50|3')

    def test_board_content_and_course_separation(self):
        for slug, title, other in [('intro-cyber', 'מבוא לסייבר', 'סייבר — הממד החמישי'),
                                   ('fifth-dimension', 'סייבר — הממד החמישי', 'מבוא לסייבר')]:
            with self.subTest(course=slug):
                content = (ROOT / f'{slug}-mootimeter.html').read_text(encoding='utf-8')
                md = (ROOT / f'{slug}-poll.md').read_text(encoding='utf-8')
                parser = BoardParser()
                parser.feed(content)
                self.assertEqual(parser.root, {'lang': 'he', 'dir': 'rtl'})
                self.assertEqual(len(parser.ids), len(set(parser.ids)))
                self.assertEqual(set(parser.targets), set(parser.fields))
                self.assertEqual(len(parser.fields), 35)  # Title, intro, 4 × (question + 7 options), open question.
                self.assertIn(title, parser.fields['copy-intro'])
                self.assertNotIn(other, content)
                self.assertNotIn(other, md)
                self.assertNotIn('{{', content)
                items = ET.parse(ROOT / f'{slug}-feedback.xml').getroot().findall('./ITEMS/ITEM')
                for index, item in enumerate(items[1:5], start=1):
                    question = item.findtext('ITEMTEXT')
                    self.assertEqual(parser.fields[f'copy-q{index}'], question)
                    self.assertIn(question, md)
                    answers = item.findtext('PRESENTATION').split('>>>>>')[1].split('<<<<<')[0].split('|')
                    for number, answer in enumerate(answers, start=1):
                        self.assertEqual(parser.fields[f'copy-q{index}a{number}'], answer)
                        self.assertIn(answer, md)
                self.assertIn('עד 150 תווים', parser.fields['copy-open'])


if __name__ == '__main__':
    unittest.main()
