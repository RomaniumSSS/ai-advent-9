"""Записать короткое видео проверенного trace в MP4."""
from __future__ import annotations
import json
import subprocess
import tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
from .build import HERE,main as build

CHROME=Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
VIDEO=HERE/'day19-three-mcp-tools.mp4'

def main():
    build()
    with tempfile.TemporaryDirectory(prefix='day19-video-') as directory:
        with sync_playwright() as playwright:
            browser=playwright.chromium.launch(headless=True,executable_path=str(CHROME) if CHROME.is_file() else None)
            context=browser.new_context(viewport={'width':1440,'height':900},record_video_dir=directory,
                                        record_video_size={'width':1440,'height':900},device_scale_factor=1)
            page=context.new_page();errors=[]
            page.on('pageerror',lambda err:errors.append(str(err)))
            page.goto((HERE/'evidence.html').as_uri())
            for number,seconds in ((1,4),(2,3),(3,4),(4,4),(5,4),(6,4),(7,5)):
                page.evaluate('(n)=>show(n)',number)
                page.wait_for_timeout(seconds*1000)
            raw=page.video
            context.close();browser.close()
            if errors:raise RuntimeError('page_errors: '+json.dumps(errors))
            subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',raw.path(),
                            '-c:v','libx264','-preset','medium','-crf','20','-pix_fmt','yuv420p',
                            '-movflags','+faststart','-an',str(VIDEO)],check=True)
    print(json.dumps({'video':str(VIDEO),'page_errors':errors},ensure_ascii=False))

if __name__=='__main__':main()
