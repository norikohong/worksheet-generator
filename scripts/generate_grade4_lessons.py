"""4학년 완전한 대화문에서 빈칸 4버전과 정답지 생성 (olefile, lxml 필요)."""
from pathlib import Path
from copy import deepcopy
import argparse, re, struct, zlib, zipfile
import olefile
from lxml import etree as E

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('lesson',choices=['G4L9','G4L10'])
parser.add_argument('--replace',action='store_true')
args=parser.parse_args()
OUT=ROOT/args.lesson
DATA={
 'G4L9':('What Day Is It Today?',[
  [(1,'day'),(2,'Monday'),(6,'Sports'),(8,'week'),(9,'soccer'),(10,'Wednesday'),(14,'Friday'),(14,'basketball')],
  [(0,'day'),(1,'Tuesday'),(2,'violin'),(4,'Thursday'),(5,'cooking'),(6,'cookies'),(9,'badminton'),(13,'Saturday')]]),
 'G4L10':('How Much Is It?',[
  [(0,'help'),(1,'much'),(2,'nine hundred'),(3,'take'),(4,'soccer ball'),(6,'four thousand'),(8,'for'),(10,'like')],
  [(0,'eight thousand'),(0,'jump rope'),(1,'hairpin'),(4,'help'),(6,'six thousand'),(11,'three thousand'),(13,'nine hundred'),(15,'take')]])}
TITLE,SPECS=DATA[args.lesson]
NS={'hp':'http://www.hancom.co.kr/hwpml/2011/paragraph'}
HP='{'+NS['hp']+'}'

def read_hwp(path):
 paragraphs=[]
 with olefile.OleFileIO(path) as o:
  flags=struct.unpack_from('<I',o.openstream('FileHeader').read(),36)[0]
  for stream in sorted(o.listdir()):
   if stream[0]!='BodyText':continue
   data=o.openstream(stream).read()
   if flags&1:data=zlib.decompress(data,-15)
   pos=0
   while pos<len(data):
    h=struct.unpack_from('<I',data,pos)[0];pos+=4;n=h>>20
    if n==4095:n=struct.unpack_from('<I',data,pos)[0];pos+=4
    value=data[pos:pos+n];pos+=n
    if h&1023==67:
     text=value.decode('utf-16le').strip()
     if text and all(ord(c)>=32 for c in text):paragraphs.append(text)
 return paragraphs

raw=read_hwp(next(OUT.glob('*.hwp')))
stories=[]
for name,end in [('Fun Talk','Chant and Do'),('Real Talk','Sing and Do')]:
 block=raw[raw.index(name)+1:raw.index(end)]
 starts=[i for i,t in enumerate(block) if t=='#1']
 assert len(starts)==2
 english,korean=block[:starts[1]],block[starts[1]:]
 assert len(english)==len(korean)
 story=[]
 for en,ko in zip(english,korean):
  if en.startswith('#'):
   assert en==ko
   story.append(('scene',en[1:],None));continue
  speaker,text=en.split(':',1);kspeaker,translation=ko.split(':',1)
  assert re.sub(r'\s','',speaker)==re.sub(r'\s','',kspeaker)
  story.append(('line',en,translation.strip()))
 stories.append(story)

counter=1000

def p(text,char='0',para='0'):
 global counter
 counter+=1
 node=E.Element(HP+'p',id=str(counter),paraPrIDRef=para,styleIDRef='0',pageBreak='0',columnBreak='0',merged='0')
 run=E.SubElement(node,HP+'run',charPrIDRef=char);E.SubElement(run,HP+'t').text=text
 return node

def replace_text(cell,text):
 sub=cell.find('hp:subList',NS)
 sample=deepcopy(sub.find('hp:p',NS))
 for child in list(sample):sample.remove(child)
 sample.set('pageBreak','0');sample.set('columnBreak','0')
 run=E.SubElement(sample,HP+'run',charPrIDRef='0');E.SubElement(run,HP+'t').text=text
 sub[:]=[sample]

template=next((ROOT/'G4L8').glob('*LEVEL 1*.hwpx'))
versions=[]
for version in [1,2,3,4,'Answers']:
 key=version=='Answers';translated=key or version in (1,2);choices=not key and version in (1,3)
 with zipfile.ZipFile(template) as zin:
  original=E.fromstring(zin.read('Contents/section0.xml'))
  tables=original.findall('.//hp:tbl',NS)
  root=E.Element(original.tag,nsmap=original.nsmap)
  heading=p(f'Lesson {int(args.lesson.split("L")[1])}. {TITLE} — '+('교사용 정답지' if key else f'LEVEL {version}'))
  controls=original.findall('hp:p/hp:run',NS)
  for run in reversed(controls):
   kept=[deepcopy(x) for x in run if E.QName(x).localname in ('secPr','ctrl')]
   if kept:
    control=E.Element(HP+'run',charPrIDRef='0');control.extend(kept);heading.insert(0,control)
  root.append(heading)
  for idx,story in enumerate(stories):
   label=p('Fun Talk' if idx==0 else 'Real Talk')
   if idx==1:label.set('columnBreak','1')
   root.append(label)
   table=deepcopy(tables[2+idx]);rows=table.findall('hp:tr',NS)
   table.find('hp:pos',NS).set('treatAsChar','1')
   scenes=[t for kind,t,_ in story if kind=='scene']
   # Keep original two-row word bank and merged scene-number/dialogue cells.
   for row in rows[2:]:table.remove(row)
   table.set('rowCnt',str(2+len(scenes)))
   bank=sorted(answer for _,answer in SPECS[idx])
   word_index=0
   for row in rows[:2]:
    for cell in row.findall('hp:tc',NS):
     addr=cell.find('hp:cellAddr',NS)
     if addr.get('colAddr')=='0':replace_text(cell,'')
     else:
      replace_text(cell,bank[word_index] if choices else '')
      word_index+=1
   line_index=0;scene_row=None;number=0
   for kind,text,translation in story:
    if kind=='scene':
     scene_row=deepcopy(rows[2]);table.append(scene_row)
     for cell in scene_row.findall('hp:tc',NS):
      cell.find('hp:cellAddr',NS).set('rowAddr',str(int(text)+1))
      cell.find('hp:cellSz',NS).set('height','1000')
     left,right=scene_row.findall('hp:tc',NS)
     replace_text(left,text);right.find('hp:subList',NS)[:]=[]
     continue
    rendered=text
    for target,answer in SPECS[idx]:
     if target!=line_index:continue
     pattern=r'(?<![A-Za-z])'+re.escape(answer)+r'(?![A-Za-z])'
     assert len(re.findall(pattern,rendered))==1,(args.lesson,idx,line_index,answer,rendered)
     number+=1
     replacement=f'({number}) {answer}' if key else chr(0x2775+number)+' '+' '.join('_'*max(7,len(w)+1) for w in answer.split())
     rendered=re.sub(pattern,lambda m: replacement,rendered,count=1)
    if translated:rendered+=' ('+translation+')'
    right=scene_row.findall('hp:tc',NS)[1]
    right.find('hp:subList',NS).append(p(rendered))
    line_index+=1
   assert number==8
   table.find('hp:sz',NS).set('height','2000')
   holder=p('');holder[0].insert(0,table);root.append(holder)
   if key:root.append(p('정답: '+' / '.join(f'{i+1}. {answer}' for i,(_,answer) in enumerate(SPECS[idx]))))
  for cache in root.findall('.//hp:linesegarray',NS):cache.getparent().remove(cache)
  name='Teacher_Answers.hwpx' if key else f'Worksheet(LEVEL {version}).hwpx'
  target=OUT/name
  if target.exists() and not args.replace:raise FileExistsError(target)
  with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as zout:
   for info in zin.infolist():
    if info.filename=='Preview/PrvImage.png':continue
    data=zin.read(info.filename)
    if info.filename=='Contents/section0.xml':data=E.tostring(root,xml_declaration=True,encoding='UTF-8',standalone=True)
    elif info.filename=='Preview/PrvText.txt':data='\n'.join(t.text or '' for t in root.findall('.//hp:t',NS)).encode()
    elif info.filename.endswith(('.xml','.hpf','.rdf')):
     doc=E.fromstring(data)
     for el in list(doc.iter()):
      if any('PrvImage.png' in v for v in el.attrib.values()) and el.getparent() is not None:el.getparent().remove(el)
     data=E.tostring(doc,xml_declaration=True,encoding='UTF-8',standalone=True)
    zout.writestr(info,data)
  versions.append(target);print(target.relative_to(ROOT))
# All XML parts and English question text must remain consistent across four versions.
normalized=[]
for target in versions:
 with zipfile.ZipFile(target) as z:
  assert z.testzip() is None
  for name in z.namelist():
   if name.endswith(('.xml','.hpf','.rdf')):E.fromstring(z.read(name))
  r=E.fromstring(z.read('Contents/section0.xml'))
  text=''.join(r.itertext())
  for banned in ('Class:', 'Name:', '반:', '번호:', '이름:', '검토용 초안','보기:'):assert banned not in text
  if 'Answers' not in target.name:
   questions=[]
   for table in r.findall('.//hp:tbl',NS):
    lines=[]
    for row in table.findall('hp:tr',NS)[2:]:
     for line in row.findall('.//hp:tc',NS)[1].findall('hp:subList/hp:p',NS):
      en=''.join(line.itertext()).split(' (')[0];lines.append(en)
    assert re.findall('[❶-❽]',''.join(lines))==list('❶❷❸❹❺❻❼❽')
    questions.append(lines)
   normalized.append(questions)
assert all(x==normalized[0] for x in normalized)
print('검증 완료: 원문·해석 대응, 문항별 번호 1~8, 네 버전 일치, ZIP/XML')
