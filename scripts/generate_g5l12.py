"""G5L12 워크시트 생성 (olefile, lxml 설치 필요).

출력 기준:
- 반·번호·이름 작성란과 ‘검토용 초안’ 문구를 넣지 않는다.
- 하단 보기에는 ‘보기:’ 접두어 없이 단어·표현 목록만 표시한다.
- 정답 후보 등 확인이 필요한 사항은 생성_검수.md에 별도로 기록한다.
"""
from pathlib import Path
import argparse
import shutil
from datetime import datetime
import re, struct, zlib, zipfile
import olefile
from lxml import etree as E

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'G5L12'
parser = argparse.ArgumentParser()
parser.add_argument('--replace', action='store_true', help='기존 생성물을 백업하고 갱신')
args = parser.parse_args()
backup_dir = OUT / '.backups' / datetime.now().strftime('%Y%m%d-%H%M%S')
NS = {'hp': 'http://www.hancom.co.kr/hwpml/2011/paragraph'}
HP = '{' + NS['hp'] + '}'
ANSWERS = [['learn', 'website', 'go ice-skating', 'go hiking', 'make', 'film'], ['town', 'trip', 'take a walk', 'go fishing', 'take a picture', 'vacation']]
TRANSLATIONS = [['겨울 방학이 다가오고 있어요!',
  '야호!',
  '여러분 신나 보이네요! 방학 동안 무엇을 하고 싶나요?',
  '저는 기타를 배우고 싶어요.',
  '아, 학교에 음악 동아리가 있어요. 거기서 기타를 배울 수 있어요. 가입하고 싶나요?',
  '네, 하고 싶어요.',
  '학교 웹사이트에서 다양한 프로그램을 살펴볼 수 있어요.',
  '너는 무엇을 하고 싶니?',
  '나는 겨울 스포츠를 해 보고 싶어.',
  '좋다. 나는 스케이트를 타고 싶어. 같이 스포츠 캠프에 가자.',
  '좋은 생각이야.',
  '나는 하이킹 프로그램에 참여해 보고 싶어.',
  '재미있겠다. 하이킹과 캠핑을 할 수 있어.',
  '유나야, 너는 무엇을 하고 싶니?',
  '나는 댄스 영상을 만들고 싶어. 나를 위해 영상을 촬영해 줄 수 있니?',
  '물론이지. 같이 하자.',
  '좋아. 고마워.'],
 ['안녕, 에릭. 포항 날씨는 어떠니?',
  '좋아.',
  '나는 이번 주말에 포항에 갈 거야.',
  '포항에서 무엇을 하고 싶니?',
  '나는 해변에 가고 싶어. 네가 사는 동네에도 가 보고 싶어.',
  '좋아. 나중에 보자.',
  '만나서 반가워, 앰버.',
  '만나서 반가워, 에릭.',
  '여행은 어땠니?',
  '좋았어요. 하이킹을 했어요.',
  '여기서 무엇을 하고 싶니?',
  '저는 해변에 가서 산책하고 싶어요.',
  '저도요. 낚시도 하고 싶어요.',
  '좋아. 호미곶으로 가자!',
  '아, 좋은 생각이에요!',
  '사진을 찍고 싶니?',
  '응, 찍고 싶어.',
  '좋아. 셋, 둘, 하나! 김치!',
  '재미있게 지내고 있니?',
  '응. 나는 내 겨울 방학이 좋아.']]

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
        heading.text = f'Lesson 12. What Do You Want to Do? — {title}'
        rows = table.findall('hp:tr', NS)
        for idx, cell in enumerate(rows[0].findall('hp:tc', NS)):
            sub = cell.find('hp:subList', NS)
            sub[:] = []
            sub.append(paragraph('Fun Talk' if idx == 0 else 'Real Talk', '14', '21'))
            t_idx = 0
            for kind, text in stories[idx]:
                if kind == 'scene': sub.append(paragraph(f'[장면 {text}]', '16', '23')); continue
                def replace(m):
                    n = int(m.group(1)) if m.group(1) else ord(m.group(2)) - 0x2473; answer = ANSWERS[idx][n-1]
                    return f'({n}) {answer}' if key else f'{chr(0x2473+n)} ' + ' '.join('_'*max(8,len(w)+2) for w in answer.split())
                rendered = re.sub(r'(?:\((\d+)\)|([⑴-⒇]))\s*_+(?:[ \t]+_+)*', replace, text)
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
                sub.append(paragraph('    /    '.join(sorted(ANSWERS[idx]))))
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
                assert re.findall('[⑴-⒇]', '\n'.join(dialogue)) == [chr(0x2474+i) for i in range(6)]
            lines.append(dialogue)
        if 'Answers' not in path.name: normalized.append(lines)
assert all(n == normalized[0] for n in normalized)
print('검증 완료: ZIP/XML, 영역별 번호 1~6, 네 버전의 영어 대화·빈칸 일치')
