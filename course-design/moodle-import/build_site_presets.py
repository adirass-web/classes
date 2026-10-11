#!/usr/bin/env python3
"""Adapt a site's exported preset with libzip, preserving its archive metadata.
Usage: python3 build_site_presets.py /path/to/site-export.zip
Requires the system libzip shared library; does not connect to Moodle.
"""
import argparse
import ctypes as C
import ctypes.util
import hashlib
from pathlib import Path
import time
import struct
import xml.etree.ElementTree as ET
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parent
EXPECTED = {'listtemplate.html', 'singletemplate.html', 'asearchtemplate.html',
            'addtemplate.html', 'rsstemplate.html', 'csstemplate.css', 'jstemplate.js',
            'listtemplateheader.html', 'listtemplatefooter.html', 'rsstitletemplate.html', 'preset.xml'}


def adapt(reference):
    with ZipFile(reference) as z:
        if set(z.namelist()) != EXPECTED or z.testzip() is not None:
            raise ValueError('Reference must contain the eleven core Database preset files at its root')
        names = z.namelist()
        metadata = {i.filename: i for i in z.infolist()}
        compression = {i.filename: (i.compress_type, 9 if i.flag_bits & 2 else 6) for i in z.infolist()}
        reference_xml = z.read('preset.xml')
        # The site sample contains an empty JavaScript template. Retain it.
        if z.read('jstemplate.js') != b'':
            raise ValueError('Use the exported built-in Journal preset with an empty JavaScript template')
    lib = C.CDLL(ctypes.util.find_library('zip') or 'libzip.so')
    for name, result, args in [
        ('zip_open', C.c_void_p, [C.c_char_p, C.c_int, C.POINTER(C.c_int)]),
        ('zip_source_buffer', C.c_void_p, [C.c_void_p, C.c_void_p, C.c_uint64, C.c_int]),
        ('zip_file_add', C.c_int64, [C.c_void_p, C.c_char_p, C.c_void_p, C.c_uint32]),
        ('zip_file_set_external_attributes', C.c_int, [C.c_void_p, C.c_uint64, C.c_uint32, C.c_uint8, C.c_uint32]),
        ('zip_file_set_mtime', C.c_int, [C.c_void_p, C.c_uint64, C.c_int64, C.c_uint32]),
        ('zip_set_file_compression', C.c_int, [C.c_void_p, C.c_uint64, C.c_int32, C.c_uint32]),
        ('zip_close', C.c_int, [C.c_void_p]),
        ('zip_discard', None, [C.c_void_p]),
        ('zip_strerror', C.c_char_p, [C.c_void_p]),
    ]:
        fn = getattr(lib, name)
        fn.restype, fn.argtypes = result, args
    for slug in ('intro-cyber', 'fifth-dimension'):
        source = ROOT / 'sources' / slug
        original = ET.parse(source / 'preset.xml').getroot()
        root = ET.fromstring(reference_xml)
        settings = root.find('settings')
        for key, value in {'comments': '1', 'maxentries': '1', 'approval': '0',
                           'requiredentries': '0', 'requiredentriestoview': '0'}.items():
            settings.find(key).text = value
        # Leave the site's empty intro, numeric defaultsort and manageapproved unchanged.
        for field in list(root.findall('field')):
            root.remove(field)
        for field in original.findall('field'):
            new = ET.SubElement(root, 'field')
            for key in ('type', 'name', 'required'):
                ET.SubElement(new, key).text = field.findtext(key)
            if field.findtext('type') == 'textarea':
                for key in ('param2', 'param3', 'param4', 'param5'):
                    ET.SubElement(new, key).text = field.findtext(key)
        ET.indent(root)
        files = {n: (source / n).read_bytes() for n in names}
        files['preset.xml'] = ('<?xml version="1.0"?>\n' + ET.tostring(root, encoding='unicode') + '\n').encode()
        files['listtemplateheader.html'] += b'<div class="acq-list" dir="rtl" lang="he">\n'
        files['listtemplatefooter.html'] = b'</div>\n'
        files['jstemplate.js'] = b''
        destination = ROOT / f'{slug}-acquaintance-site.zip'
        error = C.c_int()
        archive = lib.zip_open(str(destination).encode(), 9, C.byref(error))  # ZIP_CREATE | ZIP_TRUNCATE.
        if not archive:
            raise RuntimeError(f'libzip open failed: {error.value}')
        buffers = []  # zip_source_buffer borrows these until zip_close completes.
        try:
            for index, name in enumerate(names):
                buf = C.create_string_buffer(files[name])
                buffers.append(buf)
                payload = lib.zip_source_buffer(archive, buf, len(files[name]), 0)
                if not payload or lib.zip_file_add(archive, name.encode(), payload, 0) != index:
                    raise RuntimeError(lib.zip_strerror(archive).decode())
                method, level = compression[name]
                if lib.zip_set_file_compression(archive, index, method, level) < 0:
                    raise RuntimeError(lib.zip_strerror(archive).decode())
                info = metadata[name]
                if lib.zip_file_set_external_attributes(archive, index, 0, info.create_system, info.external_attr) < 0:
                    raise RuntimeError(lib.zip_strerror(archive).decode())
                if lib.zip_file_set_mtime(archive, index, int(time.mktime(info.date_time + (0, 0, -1))), 0) < 0:
                    raise RuntimeError(lib.zip_strerror(archive).decode())
            if lib.zip_close(archive) < 0:
                raise RuntimeError(lib.zip_strerror(archive).decode())
            archive = None
        finally:
            if archive:
                lib.zip_discard(archive)
        # PHP's export declares ZIP 2.0 even for stored entries. libzip's C API
        # declares 1.0 for these entries. Match the reference in both headers;
        # entry payloads, sizes and checksums are untouched.
        data = bytearray(destination.read_bytes())
        end = len(data) - 22
        if data[end:end + 4] != b'PK\x05\x06':
            raise ValueError('Expected a single-disk ZIP without an archive comment')
        central = struct.unpack_from('<I', data, end + 16)[0]
        with ZipFile(destination) as generated:
            for info in generated.infolist():
                expected_version = metadata[info.filename].extract_version
                if data[central:central + 4] != b'PK\x01\x02':
                    raise ValueError('Invalid central directory')
                struct.pack_into('<H', data, info.header_offset + 4, expected_version)
                struct.pack_into('<H', data, central + 6, expected_version)
                name_length, extra_length, comment_length = struct.unpack_from('<HHH', data, central + 28)
                central += 46 + name_length + extra_length + comment_length
        destination.write_bytes(data)
        with ZipFile(destination) as z:
            assert z.namelist() == names and z.testzip() is None
            assert all(z.read(n) == files[n] for n in names)
        print(destination.name, destination.stat().st_size, hashlib.sha256(destination.read_bytes()).hexdigest())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reference', type=Path)
    adapt(parser.parse_args().reference)
