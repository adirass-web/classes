#!/usr/bin/env python3
"""Build deterministic, plugin-free Moodle Database preset archives (stdlib only)."""
from pathlib import Path
from html import escape
import re
import xml.etree.ElementTree as ET
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED, ZIP_STORED

ROOT = Path(__file__).resolve().parent
COURSES = {
    'intro-cyber': ('מבוא לסייבר', 'טכנולוגיה, ארגונים, התנהגות, כלכלה, משפט או מדיניות'),
    'fifth-dimension': ('סייבר — הממד החמישי', 'יחסים בינלאומיים, מדינה, ביטחון, אסטרטגיה או מחקר'),
}
CSS = '''.cyber-acq { font-family: Arial, "Noto Sans Hebrew", sans-serif; font-size: 1rem; line-height: 1.7; letter-spacing: normal; text-align: start; color: #172b3a; max-inline-size: 58rem; margin-inline: auto; }
.cyber-acq *, .cyber-acq *::before, .cyber-acq *::after { box-sizing: border-box; }
.cyber-acq .acq-card, .cyber-acq.acq-card { background: #fff; border: 1px solid #c9d5dd; border-radius: .75rem; padding: 1.25rem; margin-block: 1rem; }
.cyber-acq h2 { font-size: 1.5rem; line-height: 1.4; margin-block: 0 .75rem; }
.cyber-acq h3 { font-size: 1.12rem; line-height: 1.5; margin-block: 0 .4rem; }
.cyber-acq p { margin-block: .4rem .8rem; }
.cyber-acq .acq-note { background: #edf4f7; border-inline-start: .25rem solid #28627a; padding: .8rem 1rem; border-radius: .25rem; margin-block: 1rem; }
.cyber-acq .acq-field { margin-block: 1.25rem; min-inline-size: 0; }
.cyber-acq .acq-hint, .cyber-acq .acq-meta { color: #425b6b; }
.cyber-acq .acq-answer { overflow-wrap: anywhere; white-space: pre-wrap; }
.cyber-acq .acq-answer p { white-space: normal; }
.cyber-acq input[type="text"], .cyber-acq textarea { inline-size: 100%; max-inline-size: 100%; font: inherit; unicode-bidi: plaintext; }
.cyber-acq .acq-field > div, .cyber-acq .acq-field .d-inline-flex { max-inline-size: 100%; inline-size: 100%; }
.cyber-acq .acq-actions { display: flex; flex-wrap: wrap; gap: 1rem; align-items: center; margin-block-start: 1rem; }
.cyber-acq a { color: #185675; text-decoration: underline; text-underline-offset: .15em; }
.cyber-acq a:focus-visible { outline: 3px solid #28627a; outline-offset: 3px; }
@media (max-width: 480px) { .cyber-acq .acq-card, .cyber-acq.acq-card { padding: .85rem; } }
'''
# Inputs are produced by Moodle, so only enhance their direction; activity works without JS.
JS = '''(function () {
    function setDirection() {
        document.querySelectorAll('.cyber-acq input[type="text"], .cyber-acq textarea')
            .forEach(function (element) { element.setAttribute('dir', 'auto'); });
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', setDirection, { once: true });
    } else { setDirection(); }
})();
'''


def fields_for(domains):
    return [
        ('שם', 'text', 'איך קוראים לי?', 'השם שבו תרצו שנפנה אליכם.', True),
        ('מקום העבודה', 'text', 'איפה אני עובד/ת?', 'משרד, גוף או תחום שירות — ברמת הפירוט שמתאימה לכם. אפשר להישאר בתיאור כללי.', True),
        ('העיסוק שלי', 'textarea', 'במה אני עוסק/ת ביום־יום?', 'משפט בשפה שמי שעובד במקום אחר יוכל להבין, מעבר לשם התפקיד.', True),
        ('לימודים קודמים', 'textarea', 'מה כבר למדתי שיכול להתחבר לקורס?', f'ציינו קורס אחד או שניים, או תחומי לימוד, שעזרו לכם לחשוב על {domains}. אלה דוגמאות, לא דרישות קדם. אפשר לכתוב שלא למדתם קורס קשור.', True),
        ('רעיון שנשאר איתי', 'textarea', 'איזה רעיון נשאר איתי מהלימודים?', 'מושג, שאלה או הבחנה מהלימודים הקודמים, והסבר קצר במילים שלכם. אם אין לכם רעיון כזה, כתבו על נושא שהייתם רוצים להבין.', True),
        ('שאלה לקורס', 'textarea', 'מה מסקרן אותי כאן?', 'שאלה אחת שהייתם רוצים לבדוק בקורס, בעקבות הלימודים, החיים או העבודה.', True),
        ('מחוץ לעבודה', 'textarea', 'עוד משהו עליי — לבחירתכם', 'משהו שאתם אוהבים ללמוד או לעשות מחוץ לעבודה, ושנוח לכם לשתף. אפשר להשאיר ריק.', False),
    ]


def introduction(title):
    return f'''<div class="cyber-acq" dir="rtl" lang="he">
<h2>מי אנחנו, ומה אנחנו מביאים ללמידה?</h2>
<p class="acq-meta">{escape(title)} · פעילות היכרות · כ־13 דקות · ללא ציון</p>
<p>כולנו עובדים בשירות המדינה, בתפקידים שונים ועם רקע לימודי מגוון. לפני שנתחיל, נכיר את האנשים ואת נקודות המבט שנמצאות בכיתה.</p>
<ol><li><strong>כותבים — כ־6 דקות:</strong> הוסיפו כרטיס אישי קצר, כ־100–130 מילים בסך הכול.</li>
<li><strong>מכירים — כ־4 דקות:</strong> קראו כמה כרטיסים ובחרו עמית או עמיתה מתחום עבודה או מרקע לימודי שונה. פתחו את הכרטיס והוסיפו תגובה.</li>
<li><strong>משתפים — כ־3 דקות:</strong> נאסוף במליאה חיבורים ושאלות מעניינות שעלו.</li></ol>
<div class="acq-note"><p>הכרטיס והתגובות גלויים למשתתפי הקורס. שתפו פרטים שנוח לכם לפרסם בכיתה; אפשר לתאר את מקום העבודה באופן כללי.</p>
<p>אין צורך בידע קודם בסייבר. הרקע הלימודי שלכם הוא נקודת מוצא לשיחה וללמידה.</p></div>
</div>'''


def peer_prompt():
    return '<p>בחרו עמית או עמיתה מרקע שונה וכתבו: <strong>״עניין אותי מה שכתבת על ___. הייתי רוצה לשמוע ממך עוד על ___.״</strong></p>'


def build(slug, title, domains):
    fields = fields_for(domains)
    intro = introduction(title)
    add = intro + '\n<div class="cyber-acq acq-card" dir="rtl" lang="he">\n<p>ענו בקצרה. כל השדות נדרשים למעט ״מחוץ לעבודה״; אפשר לציין שאין לימודים קודמים קשורים.</p>\n'
    for name, kind, question, hint, required in fields:
        add += f'<section class="acq-field"><h3>{escape(question)}</h3><p class="acq-hint">{escape(hint)}</p>[[{name}]]</section>\n'
    add += '<p>בסיום שמרו את הכרטיס באמצעות כפתור השמירה של הפעילות.</p></div>\n'
    body = '<article class="cyber-acq acq-card" dir="rtl" lang="he">\n<h2><bdi>[[שם]]</bdi></h2>\n<p class="acq-meta">פורסם על ידי: ##user##</p>\n'
    for name, kind, question, hint, required in fields[1:]:
        body += f'<section class="acq-field"><h3>{escape(question)}</h3><div class="acq-answer" dir="auto">[[{name}]]</div></section>\n'
    single = body + '<div class="acq-actions">##edit## ##delete##</div>\n<section class="acq-note"><h3>ממשיכים להכיר</h3>' + peer_prompt() + '##comments##</section>\n</article>\n'
    listing = body + '<div class="acq-actions"><a href="##moreurl##">פותחים את הכרטיס ומגיבים</a> ##edit## ##delete##</div>\n</article>\n'
    search = '<div class="cyber-acq acq-card" dir="rtl" lang="he"><h2>מחפשים עמיתים</h2>\n'
    for name, *_ in fields:
        search += f'<section class="acq-field"><h3>{escape(name)}</h3>[[{name}]]</section>\n'
    search += '</div>\n'
    xml = ET.Element('preset')
    ET.SubElement(xml, 'description').text = f'היכרות אקדמית לעובדי שירות המדינה — {title}. כרטיס אישי ותגובה לעמית, ללא ציון.'
    settings = ET.SubElement(xml, 'settings')
    for k, v in {'intro': intro, 'comments': '1', 'requiredentries': '0', 'requiredentriestoview': '0', 'maxentries': '1', 'rssarticles': '0', 'approval': '0', 'defaultsortdir': '0', 'defaultsort': 'שם'}.items():
        ET.SubElement(settings, k).text = v
    for name, kind, question, hint, required in fields:
        node = ET.SubElement(xml, 'field')
        props = {'type': kind, 'name': name, 'description': hint, 'required': str(int(required)), 'param1': '0'}
        if kind == 'textarea':
            props.update(param2='45', param3='3', param4='1', param5='0')
        for k, v in props.items():
            ET.SubElement(node, k).text = v
    ET.indent(xml)
    files = {
        'preset.xml': ET.tostring(xml, encoding='unicode', xml_declaration=True),
        'singletemplate.html': single,
        'listtemplate.html': listing,
        'listtemplateheader.html': intro + '\n',
        'listtemplatefooter.html': '',
        'addtemplate.html': add,
        'asearchtemplate.html': search,
        'rsstemplate.html': '<div dir="rtl" lang="he"><p>[[מקום העבודה]]</p><p>[[שאלה לקורס]]</p></div>\n',
        'rsstitletemplate.html': '[[שם]]',
        'csstemplate.css': CSS,
        'jstemplate.js': JS,
    }
    source = ROOT / 'sources' / slug
    source.mkdir(parents=True, exist_ok=True)
    with ZipFile(ROOT / f'{slug}-acquaintance.zip', 'w', compression=ZIP_DEFLATED) as archive:
        for filename, contents in files.items():
            (source / filename).write_text(contents, encoding='utf-8')
            info = ZipInfo(filename, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, contents.encode('utf-8'))
    # Alternate download for extraction problems: classic ZIP, stored entries,
    # DOS regular-file attributes, ASCII filenames, no encryption or ZIP64.
    # Keep the same eleven root entries required by the Moodle preset importer.
    with ZipFile(ROOT / f'{slug}-acquaintance-v2.zip', 'w', compression=ZIP_STORED, allowZip64=False) as archive:
        for filename, contents in files.items():
            info = ZipInfo(filename, date_time=(2026, 1, 1, 0, 0, 0))
            info.create_system = 0
            info.create_version = 20
            info.extract_version = 10
            info.compress_type = ZIP_STORED
            info.external_attr = 0x20  # DOS archive attribute; neither hidden nor a directory.
            archive.writestr(info, contents.encode('utf-8'))
    print(f'Built {slug}-acquaintance.zip ({len(fields)} fields, {len(files)} files)')
    print(f'Built {slug}-acquaintance-v2.zip (classic ZIP, uncompressed)')


if __name__ == '__main__':
    for slug, (title, domains) in COURSES.items():
        build(slug, title, domains)
