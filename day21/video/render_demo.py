"""Локальное немое видео по проверенным агрегатам Day21; без текста переписки."""
from pathlib import Path
import json, subprocess
from PIL import Image, ImageDraw, ImageFont
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
BUILD=OUT/'frames'; BUILD.mkdir(exist_ok=True)
inspection=json.loads((ROOT/'day21/private/index-final-evidence/inspection.json').read_text())
assert inspection['status']=='ready'
assert inspection['strategies']['fixed']['chunks']==685
assert inspection['strategies']['structure']['chunks']==724
FONT='/System/Library/Fonts/Supplemental/Arial.ttf'
BOLD='/System/Library/Fonts/Supplemental/Arial Bold.ttf'
def font(n,bold=False): return ImageFont.truetype(BOLD if bold else FONT,n)
BG='#101827'; FG='#eef4fc'; MUTED='#a7b8cd'; CYAN='#66dfd1'
def base(i,title,sub):
 im=Image.new('RGB',(1280,720),BG); d=ImageDraw.Draw(im)
 d.text((64,35),'AI ADVENT   /   DAY 21',font=font(18,True),fill=CYAN)
 d.text((64,85),title,font=font(43,True),fill=FG)
 d.text((64,147),sub,font=font(23),fill=MUTED)
 d.line((64,640,1216,640),fill='#304259',width=2)
 d.text((64,666),'Индексация документов • реальные результаты на VPS',font=font(18),fill=MUTED)
 d.text((1120,666),f'{i:02d} / 07',font=font(18),fill=CYAN)
 return im,d
slides=[]
def add(im,seconds):
 p=BUILD/f'{len(slides)+1:02d}.png'; im.save(p); slides.append((p,seconds))
def line(d,y,text,bold=False,color=FG,size=29): d.text((80,y),text,font=font(size,bold),fill=color)
im,d=base(1,'Два индекса одного учебного корпуса','Документы → чанки → эмбеддинги → SQLite')
for y,n,label in [(235,'663','документа'),(345,'1 315','исходных записей'),(455,'239 405','символов')]:
 d.text((80,y),n,font=font(48,True),fill=CYAN); d.text((420,y+12),label,font=font(29),fill=FG)
line(d,565,'≈133 страницы по 1 800 символов. Требование: 20–30 страниц.',size=23,color=MUTED)
add(im,10)
im,d=base(2,'Что делает пайплайн','Один корпус и один эмбеддер для обеих стратегий')
for y,t in [(228,'1. Условия Days1–24, отобранные обсуждения и заметка'),(300,'2. Нарезка Fixed и Structure с лимитом 400 токенов'),(372,'3. Qwen3-Embedding 0.6B через локальный Ollama'),(444,'4. Текст, вектор из 1 024 чисел и метаданные → SQLite')]: line(d,y,t,size=28)
line(d,548,'Сборка завершена за 62 мин 21 с. Облачного инференса нет.',size=24,color=CYAN)
add(im,13)
im,d=base(3,'Две стратегии нарезки','Структурная нарезка учитывает разделы и связи вопрос–ответ')
line(d,227,'FIXED',True,CYAN,30); line(d,280,'Окна до 400 токенов; перекрытие до 60 токенов.',size=28)
line(d,366,'STRUCTURE',True,CYAN,30)
line(d,419,'Короткие обсуждения сохраняются целиком.',size=28)
line(d,466,'Длинные части делятся по абзацам и пунктам.',size=28)
line(d,531,'При необходимости — предложения и деление по размеру.',size=25,color=MUTED)
add(im,13)
im,d=base(4,'Что хранится в индексе','Фрагменты реального index_pipeline.py; текст переписки скрыт')
code=(ROOT.parent/'day21-sol-high/day21/index_pipeline.py').read_text()
assert 'chunk_id TEXT PRIMARY KEY,metadata_json TEXT NOT NULL,vector_json TEXT NOT NULL' in code
lines=['CREATE TABLE IF NOT EXISTS chunks (','    chunk_id TEXT PRIMARY KEY,','    metadata_json TEXT NOT NULL,','    vector_json TEXT NOT NULL',')']
d.rounded_rectangle((64,208,1216,415),radius=16,fill='#1b293d')
for n,t in enumerate(lines):d.text((88,225+n*34),t,font=font(26),fill=CYAN)
line(d,449,'Метаданные каждого чанка:',True,size=28)
line(d,495,'source • title • section • chunk_id • позиции в документе',size=26)
line(d,557,'После записи: integrity_check, сверка чанков и векторов.',size=25,color=MUTED)
add(im,13)
im,d=base(5,'Повторное открытие: READY','Результат реальной проверки сохранённой пары индексов')
line(d,220,'$ python inspect_index.py --root …/index-release-v1',size=25,color=CYAN)
# Только белый список агрегатов: ни текстов, ни авторов сообщений.
payload={'status':inspection['status'],'generation':inspection['generation'],'fixed':{'chunks':685,'documents':663,'vector_dimensions':1024},'structure':{'chunks':724,'documents':663,'vector_dimensions':1024},'network_calls':inspection['network_calls'],'corpus_text_printed':inspection['corpus_text_printed']}
for n,t in enumerate(json.dumps(payload,ensure_ascii=False,indent=2).splitlines()):
 d.text((85,268+n*20),t,font=font(18),fill=FG)
add(im,14)
im,d=base(6,'Сравнение на полном корпусе','638 связок вопрос–ответ помещаются в лимит одного чанка')
rows=[('Показатель','Fixed','Structure'),('Чанков / векторов','685','724'),('Токенов: медиана / максимум','88 / 400','86 / 398'),('Разделённых связок из 638','7','0'),('Время построения','29:18','33:01'),('Размер SQLite, MiB','11,26','11,86')]
for r,row in enumerate(rows):
 y=218+r*57
 if r%2==0:d.rounded_rectangle((64,y-8,1216,y+45),radius=8,fill='#1b293d')
 for x,t in zip([82,750,990],row): d.text((x,y),t,font=font(25,r==0),fill=CYAN if r==0 else FG)
line(d,584,'Ещё 11 слишком длинных пар не помещаются в обоих вариантах.',size=22,color=MUTED)
add(im,15)
im,d=base(7,'Day21: технический результат готов','Две стратегии → реальные векторы → сохранённые индексы')
for y,t in [(227,'Проверено покрытие всех 663 документов.'),(292,'Каждый чанк сверен с исходным текстом.'),(357,'Проверены размерность, конечность и норма векторов.'),(422,'14 тестов пайплайна + 3 теста инспектора прошли.')]:line(d,y,t,size=28)
line(d,516,'Structure лучше сохраняет помещающиеся reply-связки.',size=26,color=CYAN)
line(d,566,'Точность поиска и ответы с RAG — следующий этап, Day22.',size=25,color=MUTED)
add(im,12)
manifest=BUILD/'concat.txt'
manifest.write_text(''.join(f"file '{p.name}'\nduration {dur}\n" for p,dur in slides)+f"file '{slides[-1][0].name}'\n")
subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(manifest),'-vf','fps=25','-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p','-an','-t',str(sum(s for _,s in slides)),'-movflags','+faststart',str(OUT/'Day21-demo.mp4')],check=True)
print(json.dumps({'video':str(OUT/'Day21-demo.mp4'),'seconds':sum(s for _,s in slides),'audio':False,'bytes':(OUT/'Day21-demo.mp4').stat().st_size}))
