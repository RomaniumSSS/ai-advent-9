"""Немое видео из сохранённых реальных ответов; не запись экрана."""
import json
import subprocess
import tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
FONT = "/System/Library/Fonts/Supplemental/Arial.ttf"


def main():
    run = json.loads((ROOT / "results/run.json").read_text())
    assert len(run["requests"]) == 3
    pages = [("Локальная LLM: Qwen3 8B", [
        "День 26 • Реальный прогон HTTP API",
        f"Ollama {run['version']['version']} • Apple M2 • macOS arm64",
        "Адрес: http://127.0.0.1:11434 • облачный режим отключён",
        "Запуск: OLLAMA_NO_CLOUD=1 ollama serve",
        "Проверка: python3 day26/demo.py",
        "Видео собрано из сохранённых ответов, это не запись экрана."])]
    font = ImageFont.truetype(FONT, 27)
    def wrap(text):
        result = []
        for line in text.splitlines():
            words = line.split()
            current = ""
            for word in words:
                candidate = (current + " " + word).strip()
                if font.getlength(candidate) > 1140 and current:
                    result.append(current)
                    current = word
                else:
                    current = candidate
            result.append(current)
        return result
    for item in run["requests"]:
        response = item["response"]
        lines = wrap("Запрос: " + item["request"]["prompt"]) + [""] + wrap(response["response"])
        title = f"{item['level']} запрос • {item['elapsed_seconds']:.2f} с • {response['eval_count']} токенов"
        for offset in range(0, len(lines), 14):
            pages.append((title, lines[offset:offset+14]))
    pages.append(("Результат: 3 / 3 ответа", [
        "Модель загружена локально: /api/ps сохранён в run.json",
        "Простой: арифметика • Средний: объяснение Python",
        "Сложный: алгоритм объединения интервалов",
        "Код: day26/demo.py • Ответы: day26/results/run.json",
        "Повторный запуск: python3 day26/demo.py"]))
    with tempfile.TemporaryDirectory() as temp:
        temp = Path(temp)
        for index, (title, lines) in enumerate(pages):
            im = Image.new("RGB", (1280, 720), "#101827")
            draw = ImageDraw.Draw(im)
            draw.text((60, 30), "AI ADVENT / DAY 26 / LOCAL LLM", font=font, fill="#66dfd1")
            draw.text((60, 88), title, font=ImageFont.truetype(FONT, 33), fill="#ffffff")
            for i, line in enumerate(lines):
                draw.text((60, 158+i*35), line, font=font, fill="#e4ebf5")
            draw.text((60, 675), f"Реальные ответы HTTP API • {index+1}/{len(pages)}", font=ImageFont.truetype(FONT, 20), fill="#a7b8cd")
            im.save(temp / f"{index:03d}.png")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "1/12",
                        "-i", str(temp / "%03d.png"), "-c:v", "libx264", "-r", "25",
                        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                        str(ROOT / "video/Day26-demo.mp4")], check=True)


if __name__ == "__main__":
    main()
