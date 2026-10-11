#!/usr/bin/env python3
"""Generate Hebrew poll copy and Moodle Feedback XML; no external dependencies."""
from pathlib import Path
from html import escape
from xml.dom.minidom import Document

ROOT = Path(__file__).resolve().parent
TITLE = 'סייבר ובינה מלאכותית — מה מסקרן אותנו, ומה מטריד?'
OPENING = ('לפני שנצא לדרך, נבדוק אילו שאלות אנחנו מביאים לכיתה. '
           'הסקר אנונימי וללא ציון. אין תשובות נכונות: מעניין אותנו מה אתם חושבים עכשיו. '
           'התייחסו לחיים האישיים, לעבודה בשירות המדינה או לחברה בכללותה.')
COURSES = {'intro-cyber': 'מבוא לסייבר', 'fifth-dimension': 'סייבר — הממד החמישי'}
QUESTIONS = [
    ('cyber_interest', 'מה בסייבר הכי מעניין אותך להבין?', [
        'איך מתקפות מתרחשות, ואיך מתגוננים מפניהן.',
        'איך אנשים מקבלים החלטות ונופלים להטעיות.',
        'איך מגינים על מידע אישי ועל הפרטיות.',
        'איך מתקפות משפיעות על שירותים ציבוריים ועל תפקוד המדינה.',
        'איך מדינות משתמשות בסייבר לצורכי מודיעין, השפעה ועימות.',
        'משהו אחר.',
        'עדיין אין לי העדפה.',
    ]),
    ('cyber_concern', 'מה בסייבר הכי מטריד אותך?', [
        'גניבת כסף או השתלטות על חשבונות אישיים.',
        'חשיפה ושימוש לרעה במידע אישי.',
        'השבתת שירות ציבורי חיוני.',
        'טעות שלי שעלולה לפגוע באחרים או בארגון.',
        'שימוש בסייבר בעימותים בין מדינות.',
        'משהו אחר.',
        'כרגע אין נושא שמטריד אותי במיוחד.',
    ]),
    ('ai_interest', 'מה בבינה מלאכותית הכי מעניין אותך להבין?', [
        'איך היא פועלת, ומה היא באמת מסוגלת לעשות.',
        'איך להשתמש בה ללמידה, למחקר וליצירה.',
        'איך היא יכולה לשפר את העבודה ואת השירות לציבור.',
        'איך היא משנה מקצועות ומיומנויות.',
        'איך היא משנה את עולם הסייבר — בהתקפה ובהגנה.',
        'משהו אחר.',
        'עדיין אין לי העדפה.',
    ]),
    ('ai_concern', 'מה בבינה מלאכותית הכי מטריד אותך?', [
        'תשובות שגויות שנשמעות אמינות.',
        'פגיעה בפרטיות ושימוש במידע שמסרנו.',
        'התחזות וזיופים שקשה לזהות.',
        'החלטות לא הוגנות שקשה להבין או לערער עליהן.',
        'אובדן מיומנויות או פגיעה בתעסוקה.',
        'משהו אחר.',
        'כרגע אין נושא שמטריד אותי במיוחד.',
    ]),
]
OPEN_QUESTION = ('איזו שאלה אחת על סייבר או על בינה מלאכותית היית רוצה שנחקור בקורס? '
                 'אפשר גם לפרט תשובת ״משהו אחר״. משפט אחד מספיק. השאלה אינה חובה; אין צורך לציין שם או מקום עבודה.')
ONE_CHOICE = 'בכל אחת מארבע השאלות הראשונות בחרו תשובה אחת. השאלה האחרונה היא לבחירה.'
TWO_CHOICES = ('בכל אחת מארבע השאלות הראשונות אפשר לבחור עד שתי תשובות. '
               'אם בחרתם ״עדיין אין לי העדפה״ או ״כרגע אין נושא שמטריד אותי במיוחד״, '
               'בחרו באפשרות הזאת בלבד. השאלה האחרונה היא לבחירה.')


def item(doc, parent, index, kind, required, text, label, presentation, options=''):
    node = doc.createElement('ITEM')
    node.setAttribute('TYPE', kind)
    node.setAttribute('REQUIRED', str(int(required)))
    parent.appendChild(node)
    values = {'ITEMID': str(index), 'ITEMTEXT': text, 'ITEMLABEL': label,
              'PRESENTATION': presentation, 'OPTIONS': options,
              'DEPENDITEM': '0', 'DEPENDVALUE': ''}
    for key, value in values.items():
        element = doc.createElement(key)
        element.appendChild(doc.createCDATASection(value))
        node.appendChild(element)


def feedback_xml(course):
    doc = Document()
    root = doc.createElement('FEEDBACK')
    root.setAttribute('VERSION', '200701')
    root.setAttribute('COMMENT', 'XML-Importfile for mod/feedback')
    doc.appendChild(root)
    items = doc.createElement('ITEMS')
    root.appendChild(items)
    intro = f'<div dir="rtl" lang="he"><h3>{TITLE}</h3><p>{course}</p><p>{OPENING}</p><p>{ONE_CHOICE}</p></div>'
    item(doc, items, 1, 'label', False, '', '', intro)
    for index, (key, question, options) in enumerate(QUESTIONS, start=2):
        # Native Feedback: r = radio, >>>>> type delimiter, | answer delimiter,
        # <<<<<0 = vertical layout; h hides the redundant "not selected" option.
        presentation = 'r>>>>>' + '|'.join(options) + '<<<<<0'
        item(doc, items, index, 'multichoice', True, question, key, presentation, 'h')
    item(doc, items, 6, 'textarea', False, OPEN_QUESTION, 'open_question', '50|3')
    return doc.toprettyxml(indent='  ', encoding='UTF-8')


def markdown(course):
    parts = ['<div dir="rtl" lang="he">', '', f'# {TITLE}', '', f'**קורס: {course}**', '',
             '## טקסט הפתיחה לסטודנטים', '', OPENING, '',
             '## הנחיית הבחירה — להציג רק את הנוסח שמתאים להגדרת הכלי', '',
             f'**ב־Mootimeter, לאחר הגבלת הבחירות ל־2:** {TWO_CHOICES}', '',
             f'**בבחירה יחידה, ובקובץ הייבוא למשוב Moodle:** {ONE_CHOICE}', '']
    for index, (_, question, options) in enumerate(QUESTIONS, start=1):
        parts += [f'## {index}. {question}', '', *[f'- {answer}' for answer in options], '']
    parts += ['## 5. שאלה פתוחה — לבחירה', '', OPEN_QUESTION, '',
              '## הודעת סיום', '', 'תודה. מיד נתבונן בתמונה הכיתתית ונבחר שאלות שנרצה לקחת איתנו לקורס.', '', '</div>', '']
    return '\n'.join(parts)


def copy_panel(index, label, text):
    return (f'<div class="copy-row"><label for="copy-{index}">{escape(label)}</label>'
            f'<textarea id="copy-{index}" dir="auto" readonly rows="2">{escape(text)}</textarea>'
            f'<button type="button" data-copy="copy-{index}" aria-label="העתקת {escape(label)}">העתקה</button></div>')


def copy_board(course):
    panels = ['<section><h2>שם הפעילות והתיאור</h2>',
              copy_panel('title', 'שם הפעילות', TITLE),
              copy_panel('intro', 'תיאור הפעילות', course + '\n' + OPENING + '\n' + TWO_CHOICES), '</section>']
    for index, (_, question, answers) in enumerate(QUESTIONS, start=1):
        panels += [f'<section><h2>דף {index} · סקר (Poll)</h2>',
                   '<p class="settings">מקסימום בחירות: <strong>2</strong> · מצב אנונימי: מופעל · תוצאות: מוסתרות עד סיום ההצבעה · תצוגה: תרשים פסים</p>',
                   copy_panel(f'q{index}', f'שאלה {index}', question)]
        for number, answer in enumerate(answers, start=1):
            panels.append(copy_panel(f'q{index}a{number}', f'אפשרות {number}', answer))
        panels.append('</section>')
    panels += ['<section><h2>דף 5 · שאלה פתוחה לבחירה (Wordcloud)</h2>',
               '<p class="settings">מקסימום תשובות למשתתף: <strong>1</strong> · מצב אנונימי: מופעל · תשובות: מוסתרות מהסטודנטים</p>',
               copy_panel('open', 'השאלה הפתוחה', OPEN_QUESTION + ' עד 150 תווים.'),
               '<p>משפט קצר אחד. את התשובות קוראים בתצוגת סקירת התשובות; אין צורך להקרין ענן מילים.</p></section>']
    template = (ROOT / 'copy-board.template.html').read_text(encoding='utf-8')
    return template.replace('{{COURSE}}', escape(course)).replace('{{PANELS}}', '\n'.join(panels))


if __name__ == '__main__':
    for slug, course in COURSES.items():
        (ROOT / f'{slug}-poll.md').write_text(markdown(course), encoding='utf-8')
        (ROOT / f'{slug}-feedback.xml').write_bytes(feedback_xml(course))
        (ROOT / f'{slug}-mootimeter.html').write_text(copy_board(course), encoding='utf-8')
        print(f'Built {slug}: Mootimeter copy board, Markdown, optional Feedback XML')
