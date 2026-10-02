"""Немая презентация реального прогона; без текста приватных обсуждений."""
import json, subprocess, textwrap
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1]
OUT=Path(__file__).resolve().parent
FRAMES=OUT/'frames'; FRAMES.mkdir(exist_ok=True)
ledger=json.loads((ROOT/'private/run-v1/ledger.json').read_text())
entries=ledger['entries']; completed=[e for e in entries if e['status']=='completed']
known=sum(e['cost'] for e in completed); reserve=sum(e.get('cost',0) for e in entries if e['status']!='completed')
FONT='/System/Library/Fonts/Supplemental/Arial.ttf'
BOLD='/System/Library/Fonts/Supplemental/Arial Bold.ttf'
BG='#101827';FG='#edf2fa';ACC='#6be2ca';MUTED='#b8c6db'
def font(size,bold=False):return ImageFont.truetype(BOLD if bold else FONT,size)
def slide(number,title,subtitle,lines):
 im=Image.new('RGB',(1280,720),BG);d=ImageDraw.Draw(im)
 d.text((60,32),'AI ADVENT / DAY 22',font=font(20,True),fill=ACC)
 d.text((60,88),title,font=font(40,True),fill=FG)
 d.text((60,146),subtitle,font=font(23),fill=MUTED)
 y=228
 for line in lines:
  for part in textwrap.wrap(line,width=76):
   d.text((70,y),part,font=font(27),fill=FG);y+=38
  y+=19
 d.line((60,645,1220,645),fill='#344660',width=2)
 d.text((60,666),'Реальные результаты · видео без озвучки',font=font(18),fill=MUTED)
 d.text((1120,666),f'{number}/6',font=font(18),fill=ACC)
 p=FRAMES/f'{number:02}.png';im.save(p);return p
slides=[
slide(1,'Первый RAG-запрос','Готовый индекс Day21 → поиск → ответ',[
'Qwen3-Embedding 0.6B на VPS кодирует вопрос.',
'Код выбирает top-5 чанков по косинусному сходству.',
'DeepSeek V4.1 Flash отвечает через OpenRouter / DeepInfra.',
'Два режима: один вопрос с контекстом и без контекста.']),
slide(2,'Что проверяем','10 вопросов, ожидания и источники заданы заранее',[
'Поиск: попал ли ожидаемый документ в переданный контекст?',
'Ответ: есть ли нужные факты, ошибки и противоречия?',
'Эталонные ответы модели не передаются.',
'Все запросы независимые, настройки модели одинаковые.']),
slide(3,'Реальный запуск','Structure: 724 чанка, индекс не пересобирали',[
'Подготовка десяти вопросов на VPS: 18,34 секунды.',
'Все ожидаемые документы найдены в 5 из 10 вопросов.',
'Выбрано 50 чанков, из них 38 уникальных.',
f'Сохранено ответов: {len(completed)}/20. Известная цена: ${known:.6f}.',
f'Резерв неопределённой стоимости: ${reserve:.6f}.']),
slide(4,'Пример: проверка памяти Day7','Один вопрос — два режима',[
'Без RAG: модель сообщает, что не знает условие задания.',
'С RAG: начать диалог, перезапустить приложение, продолжить.',
'Ответ ссылается на найденное условие assignment:7.',
'Но сохранение истории и её загрузку ответ не объясняет.']),
slide(5,'Где решение ошибается','Поиск и генерацию нужно оценивать отдельно',[
'Q02: условие Day10 не найдено — нет списка стратегий.',
'Q04: требования найдены и перечислены, но ответ зря сомневается.',
'Q09: исправление из заметки передано верно.',
'Q10: первая фраза противоречит правильной цитате ниже.']),
slide(6,'Результат и ограничения','Код, контрольные вопросы, сравнение и локальный просмотр',[
'Два режима реализованы; офлайн-проверки прошли.',
'Реальный прогон выявил ограничения поиска и генерации.',
'Q03: после таймаута разрешённый повтор дал ответ.',
'Приватный HTML показывает ответы и выбранные чанки.',
'Реранкинг и фильтрация оставлены для Day23.'])]
manifest=FRAMES/'concat.txt'
manifest.write_text(''.join(f"file '{p.name}'\nduration 12\n" for p in slides)+f"file '{slides[-1].name}'\n")
subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(manifest),'-vf','fps=25','-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p','-an','-t','72','-movflags','+faststart',str(OUT/'Day22-demo.mp4')],check=True)
contact=Image.new('RGB',(1280,1080),BG)
for n,p in enumerate(slides):contact.paste(Image.open(p).resize((640,360)),((n%2)*640,(n//2)*360))
contact.save(FRAMES/'contact.png')
print('video: 72 seconds, 720p, no audio')
