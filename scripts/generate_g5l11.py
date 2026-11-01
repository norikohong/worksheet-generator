"""G5L11 검토용 초안 생성. 실행: python (olefile, lxml 설치 필요)."""
from pathlib import Path
import argparse
import shutil
from datetime import datetime
import re, struct, zlib, zipfile
import olefile
from lxml import etree as E

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'G5L11'
parser = argparse.ArgumentParser()
parser.add_argument('--replace', action='store_true', help='기존 생성물을 백업하고 갱신')
args = parser.parse_args()
backup_dir = OUT / '.backups' / datetime.now().strftime('%Y%m%d-%H%M%S')
NS = {'hp': 'http://www.hancom.co.kr/hwpml/2011/paragraph'}
HP = '{' + NS['hp'] + '}'
ANSWERS = [['see', 'bedroom', 'window', 'living room'], ['bathroom', 'bedroom', 'kitchen', 'garden']]
TRANSLATIONS = [
['안녕, 수호. 안녕, 제이크.', '안녕, 민. 네가 안 보여.', '아, 미안해. 이제 내가 보이니?', '응, 괜찮아.',
 '얘들아, 나 지난주에 이사했어. 여기가 내 새집이야.', '와, 멋지다. 네 침실에는 무엇이 있니?',
 '내 침실에는 큰 침대가 있어. 그림들도 있어.', '좋다. 창문 아래에 있는 저것은 무엇이니?', '시계야.', '멋지다.',
 '여기는 거실이야.', '거실에는 무엇이 있니?', '우리 가족사진이 있어.', '멋지다! 아, 고양이를 키우니?', '응, 키워.'],
['해피 한옥에 오신 것을 환영합니다. 이곳은 한국의 전통 가옥입니다.',
 '제이크, 루카스! 내가 보이니? 여기는 한옥이야. 나는 오늘 여기에서 묵을 거야.', '와, 정말 아름답다!', '즐거운 시간 보내.',
 '여기는 거실입니다. 여기는 욕실이고, 여기는 침실입니다.', '여기가 침실인가요?', '네, 그렇습니다.', '침실에는 무엇이 있나요?',
 '작은 탁자가 있어. 아, 꽃병도 있네.', '이제 부엌으로 가 봅시다.', '부엌에는 무엇이 있나요?', '큰 솥인 가마솥이 두 개 있습니다.',
 '정말 크네요!', '이동합시다. 여기는 정원입니다. 한국의 전통 신발인 고무신이 있습니다.', '신어 봐도 될까요?', '물론이지요.', '보세요!', '아름다워요.']]

def extract(path):
    paragraphs = []
    with olefile.OleFileIO(path) as o:
        compressed = struct.unpack_from('<I', o.openstream('FileHeader').read(), 36)[0] & 1
        for stream in sorted(o.listdir()):
            if stream[0] != 'BodyText': continue
            data = o.openstream(stream).read()
            if compressed: data = zlib.decompress(data, -15)
            pos = 0
            while pos < len(data):
                h = struct.unpack_from('<I', data, pos)[0]; pos += 4
                size = h >> 20
                if size == 4095: size = struct.unpack_from('<I', data, pos)[0]; pos += 4
                payload = data[pos:pos+size]; pos += size
                if h & 1023 == 67: paragraphs.append(payload.decode('utf-16le').strip())
    selected = []; active = False
    for text in paragraphs:
        if text == '1': active = True
        if active and text.startswith('2. '): break
        if not active: continue
        if re.fullmatch(r'\d+', text): selected.append(('scene', text))
        elif re.match(r'^[가-힣, ]+\s*:', text): selected.append(('line', text))
        elif selected and selected[-1][0] == 'line' and text and ord(text[0]) >= 32:
            selected[-1] = ('line', selected[-1][1] + ' ' + text)
    return selected

sources = sorted(OUT.glob('*.hwp'))
stories = [extract(p) for p in sources]
for story, translations in zip(stories, TRANSLATIONS):
    assert sum(kind == 'line' for kind, _ in story) == len(translations)

counter = 100

def paragraph(text, char='19', para='0'):
    global counter
    counter += 1
    p = E.Element(HP+'p', id=str(counter), paraPrIDRef=para, styleIDRef='0', pageBreak='0', columnBreak='0', merged='0')
    run = E.SubElement(p, HP+'run', charPrIDRef=char)
    E.SubElement(run, HP+'t').text = text
    return p

all_outputs = []
for version in [1, 2, 3, 4, 'Answers']:
    key = version == 'Answers'
    translation = key or version in (1, 2)
    choices = not key and version in (1, 3)
    template_version = 1 if choices else 2
    template = ROOT / f'G5L9/Dictation({template_version}).hwpx'
    with zipfile.ZipFile(template) as zin:
        root = E.fromstring(zin.read('Contents/section0.xml'))
        header = E.fromstring(zin.read('Contents/header.xml'))
        table = root.find('.//hp:tbl', NS)
        title = '교사용 정답지' if key else f'Dictation({version})'
        # One shared heading avoids repeating the same two-line title in both columns.
        heading = root.find('hp:p/hp:run/hp:t', NS)
        heading.text = f'Lesson 11. What’s in the Kitchen? — {title} [검토용 초안]'
        rows = table.findall('hp:tr', NS)
        for idx, cell in enumerate(rows[0].findall('hp:tc', NS)):
            sub = cell.find('hp:subList', NS)
            sub[:] = []
            sub.append(paragraph('Fun Talk' if idx == 0 else 'Real Talk', '14', '21'))
            sub.append(paragraph('5학년   반: ______  번호: ______  이름: ______________'))
            t_idx = 0
            for kind, text in stories[idx]:
                if kind == 'scene': sub.append(paragraph(f'[장면 {text}]', '16', '23')); continue
                def replace(m):
                    n = int(m.group(1)); answer = ANSWERS[idx][n-1]
                    return f'({n}) {answer}' if key else f'{chr(0x2473+n)} ' + ' '.join('_'*max(8,len(w)+2) for w in answer.split())
                rendered = re.sub(r'\((\d+)\)\s*_+', replace, text)
                p = paragraph(rendered)
                if translation:
                    run = E.SubElement(p, HP+'run', charPrIDRef='0')
                    E.SubElement(run, HP+'t').text = ' (' + TRANSLATIONS[idx][t_idx] + ')'
                sub.append(p)
                t_idx += 1
            if key: sub.append(paragraph('정답: ' + ' / '.join(f'{i+1}. {a}' for i,a in enumerate(ANSWERS[idx]))))
        if choices:
            for idx, cell in enumerate(rows[1].findall('hp:tc', NS)):
                sub = cell.find('hp:subList', NS); sub[:] = []
                sub.append(paragraph('보기: ' + '    /    '.join(sorted(ANSWERS[idx]))))
        # Old line-layout caches describe the previous lesson and must be recalculated.
        for cache in root.findall('.//hp:linesegarray', NS): cache.getparent().remove(cache)
        preview = '\n'.join(t.text or '' for t in root.findall('.//hp:t', NS))
        name = 'Teacher_Answers.hwpx' if key else f'Dictation({version}).hwpx'
        target = OUT / name
        if target.exists():
            if not args.replace: raise FileExistsError(target)
            backup_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, backup_dir / name)
        with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as zout:
            for info in zin.infolist():
                if info.filename == 'Preview/PrvImage.png': continue
                data = zin.read(info.filename)
                if info.filename == 'Contents/section0.xml': data = E.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)
                if info.filename == 'Preview/PrvText.txt': data = preview.encode('utf-8')
                # Remove references to the old lesson's preview image.
                if info.filename.endswith(('.xml', '.hpf', '.rdf')) and info.filename != 'Contents/section0.xml':
                    doc = header if info.filename == 'Contents/header.xml' else E.fromstring(data)
                    for element in list(doc.iter()):
                        if any('PrvImage.png' in v for v in element.attrib.values()) and element.getparent() is not None:
                            element.getparent().remove(element)
                    data = E.tostring(doc, xml_declaration=True, encoding='UTF-8', standalone=True)
                zout.writestr(info, data)
        all_outputs.append(target)
        print(target.relative_to(ROOT))

# Verify package integrity, every XML part, numbering, and cross-version English text.
normalized = []
for path in all_outputs:
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None
        for name in z.namelist():
            if name.endswith(('.xml','.hpf','.rdf')): E.fromstring(z.read(name))
        root = E.fromstring(z.read('Contents/section0.xml'))
        cells = root.find('.//hp:tbl/hp:tr', NS).findall('hp:tc', NS)
        lines = []
        for cell in cells:
            texts = [t.text or '' for t in cell.findall('.//hp:t', NS)]
            dialogue = [t for t in texts if re.match(r'^[가-힣, ]+\s*:', t)]
            if 'Answers' not in path.name:
                assert re.findall('[⑴-⑷]', '\n'.join(dialogue)) == list('⑴⑵⑶⑷')
            lines.append(dialogue)
        if 'Answers' not in path.name: normalized.append(lines)
assert all(n == normalized[0] for n in normalized)
print('검증 완료: ZIP/XML, 영역별 번호 1~4, 네 버전의 영어 대화·빈칸 일치')
