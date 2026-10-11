#!/usr/bin/env python3
"""Build activity MBZs for Mootimeter >= v0.3.3 from a native no-user-data backup.
The site's exported v0.3.2 cannot restore Poll options. These files require its
upstream restore fix; they are not advertised as compatible with that version.
"""
import argparse
import copy
import gzip
import hashlib
import io
from pathlib import Path, PurePosixPath
import sys
import tarfile
import xml.etree.ElementTree as ET
sys.dont_write_bytecode = True
from build_poll import COURSES, TITLE, OPENING, TWO_CHOICES, QUESTIONS, OPEN_QUESTION

ROOT = Path(__file__).resolve().parent / 'mootimeter-backup'
TARGET_VERSION = '2025121100'  # Public v0.3.3, contains upstream 35c0379 restore fix.


def xml_bytes(root):
    ET.indent(root)
    # Moodle detect_moodle2_format matches the declaration literally.
    return b'<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding='utf-8') + b'\n'


def add(parent, name, value):
    child = ET.SubElement(parent, name)
    child.text = str(value)
    return child


def build(reference):
    files, directories = {}, []
    with tarfile.open(reference, 'r:*') as source:
        for member in source:
            name = member.name
            path = PurePosixPath(name)
            if path.is_absolute() or '..' in path.parts or member.issym() or member.islnk():
                raise ValueError('Unsafe archive path or link')
            if name == '.ARCHIVE_INDEX':
                continue
            if member.isdir():
                directories.append(name.rstrip('/') + '/')
            elif member.isfile():
                files[name] = source.extractfile(member).read()
            else:
                raise ValueError('Unsupported archive member')
    meta = ET.fromstring(files['moodle_backup.xml'])
    info = meta.find('information')
    activity = info.find('contents/activities/activity')
    if len(info.findall('contents/activities/activity')) != 1 or activity.findtext('modulename') != 'mootimeter':
        raise ValueError('Provide a backup of exactly one Mootimeter activity')
    settings = info.findall('settings/setting')
    if not any(s.findtext('name') == 'users' and s.findtext('value') == '0' for s in settings):
        raise ValueError('User data must be excluded from the reference backup')
    for name, data in files.items():
        if name.endswith('.xml'):
            root = ET.fromstring(data)
            if any(e.tag.endswith('_answers') or e.tag == 'user' for e in root.iter()):
                raise ValueError('Reference contains user/answer records')
    prefix = activity.findtext('directory')
    content_name = prefix + '/mootimeter.xml'
    module_name = prefix + '/module.xml'
    timestamp = int(info.findtext('backup_date'))
    source_activity = ET.fromstring(files[content_name])
    source_module = ET.fromstring(files[module_name])
    ROOT.mkdir(exist_ok=True)
    for slug, course in COURSES.items():
        output = dict(files)
        content = copy.deepcopy(source_activity)
        mt = content.find('mootimeter')
        mt.find('name').text = f'{TITLE} — {course}'
        mt.find('intro').text = f'<div dir="rtl" lang="he"><p>{course}</p><p>{OPENING}</p><p>{TWO_CHOICES}</p></div>'
        mt.find('introformat').text = '1'
        mt.find('timemodified').text = str(timestamp)
        pages = mt.find('pages')
        pages.clear()
        setting_id, option_id = 1, 1
        questions = [(q, 'poll', a) for _, q, a in QUESTIONS] + [(OPEN_QUESTION + ' עד 150 תווים.', 'wordcloud', [])]
        for order, (question, tool, answers) in enumerate(questions):
            pageid = 1170 + order
            page = ET.SubElement(pages, 'page', id=str(pageid))
            for key, value in {'instance': mt.attrib['id'], 'tool': tool,
                               'title': question if tool == 'poll' else 'שאלה לקורס — לבחירה',
                               'visible': 1, 'sortorder': order,
                               'timecreated': timestamp, 'timemodified': timestamp}.items():
                add(page, key, value)
            config = {'question': question, 'anonymousmode': '1', 'showonteacherpermission': '0'}
            config.update({'maxanswersperuser': '2', 'visualizationtype': '2'} if tool == 'poll'
                          else {'maxinputsperuser': '1', 'allowduplicateanswers': '0'})
            tool_settings = ET.SubElement(page, 'tool_settings')
            for key, value in config.items():
                setting = ET.SubElement(tool_settings, 'tool_setting', id=str(setting_id))
                setting_id += 1
                for tag, text in {'tool': tool, 'pageid': pageid, 'name': key, 'value': value,
                                  'timemodified': timestamp}.items():
                    add(setting, tag, text)
            if tool == 'poll':
                wrapper = ET.SubElement(page, 'subplugin_mootimetertool_poll_page')
                for answer in answers:
                    option = ET.SubElement(wrapper, 'mootimetertool_poll_options', id=str(option_id))
                    option_id += 1
                    for key, value in {'pageid': pageid, 'optiontext': answer,
                                       'timecreated': timestamp, 'timemodified': timestamp}.items():
                        add(option, key, value)
        output[content_name] = xml_bytes(content)
        module = copy.deepcopy(source_module)
        module.set('version', TARGET_VERSION)
        module.find('visible').text = '0'  # Restore hidden for instructor review.
        module.find('visibleold').text = '0'
        module.find('completion').text = '0'
        for extension in list(module):
            if extension.tag.startswith('plugin_plagiarism_'):
                module.remove(extension)  # No unrelated activity-specific plagiarism record.
        output[module_name] = xml_bytes(module)
        filename = f'{slug}-poll-requires-mootimeter-0.3.3-v2.mbz'
        manifest = copy.deepcopy(meta)
        manifest.find('information/name').text = filename
        manifest.find('information/contents/activities/activity/title').text = mt.findtext('name')
        manifest.find('information/details/detail').set('backup_id', hashlib.md5(filename.encode()).hexdigest())
        for setting in manifest.findall('information/settings/setting'):
            if setting.findtext('name') == 'filename':
                setting.find('value').text = filename
        output['moodle_backup.xml'] = xml_bytes(manifest)
        entries = [(n, None) for n in directories] + list(output.items())
        index = f'Moodle archive file index. Count: {len(entries)}\n'
        for name, data in entries:
            index += f'{name}\t{"d" if data is None else "f"}\t{0 if data is None else len(data)}\t{"?" if data is None else timestamp}\n'
        with (ROOT / filename).open('wb') as raw:
            with gzip.GzipFile(filename='', fileobj=raw, mode='wb', mtime=timestamp) as compressed:
                with tarfile.open(fileobj=compressed, mode='w', format=tarfile.USTAR_FORMAT) as archive:
                    for name, data in [('.ARCHIVE_INDEX', index.encode())] + entries:
                        record = tarfile.TarInfo(name)
                        record.mode = 0o755 if data is None else 0o644
                        record.mtime = timestamp
                        record.type = tarfile.DIRTYPE if data is None else tarfile.REGTYPE
                        record.size = 0 if data is None else len(data)
                        archive.addfile(record, None if data is None else io.BytesIO(data))
        print(filename, (ROOT / filename).stat().st_size, 'bytes; requires fixed Mootimeter restore')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reference', type=Path)
    build(parser.parse_args().reference)
