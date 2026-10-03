"""Records a natural-looking screen capture of SocietyMitra for the demo video.

  1. Start the app with your real keys:  NEBIUS_API_KEY=... TAVILY_API_KEY=... uvicorn app:app
  2. pip install playwright && playwright install chromium
  3. python scripts/record_demo.py      -> demo_video/screen.webm (+ screen.mp4 if ffmpeg exists)

Then record your own voice over it (see VIDEO_SCRIPT.md). The script moves a visible
cursor with eased curves, types at human speed with small pauses, and waits for real
Nemotron answers - nothing is faked.
"""
import random
import shutil
import subprocess
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = "http://localhost:8000"
OUT = Path("demo_video")
W, H = 1440, 900

CURSOR_JS = """
const c=document.createElement('div');
c.style.cssText='position:fixed;z-index:99999;width:18px;height:18px;border-radius:50%;'+
 'background:rgba(15,107,79,.35);border:2px solid #0f6b4f;pointer-events:none;transform:translate(-50%,-50%);transition:width .1s,height .1s';
document.addEventListener('DOMContentLoaded',()=>document.body.appendChild(c));
addEventListener('mousemove',e=>{c.style.left=e.clientX+'px';c.style.top=e.clientY+'px'});
addEventListener('mousedown',()=>{c.style.width='26px';c.style.height='26px'});
addEventListener('mouseup',()=>{c.style.width='18px';c.style.height='18px'});
"""

pos = [W / 2, H / 2]


def move(page, x, y):
    sx, sy = pos
    steps = random.randint(22, 34)
    for i in range(1, steps + 1):
        t = i / steps
        e = t * t * (3 - 2 * t)  # ease in-out
        jitter = (1 - t) * random.uniform(-3, 3)
        page.mouse.move(sx + (x - sx) * e + jitter, sy + (y - sy) * e + jitter)
        time.sleep(0.012)
    pos[:] = [x, y]


def click(page, selector, pause=0.5):
    box = page.locator(selector).first.bounding_box()
    move(page, box["x"] + box["width"] * random.uniform(.35, .65), box["y"] + box["height"] / 2)
    time.sleep(random.uniform(.15, .35))
    page.mouse.down(); time.sleep(.08); page.mouse.up()
    time.sleep(pause)


def human_type(page, text):
    for ch in text:
        page.keyboard.type(ch)
        time.sleep(random.uniform(.035, .11) + (.25 if ch in ",.?" else 0))


def ask(page, text, read_secs=7):
    click(page, "#q")
    human_type(page, text)
    time.sleep(.6)
    page.keyboard.press("Enter")
    page.wait_for_function("!document.querySelector('.typing')", timeout=180_000)
    time.sleep(1.2)
    # slow scroll so viewers can read, like a person would
    for _ in range(4):
        page.mouse.wheel(0, 160); time.sleep(.5)
    time.sleep(read_secs)


def main():
    OUT.mkdir(exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": W, "height": H}, record_video_dir=str(OUT),
                            record_video_size={"width": W, "height": H})
        ctx.add_init_script(CURSOR_JS)
        page = ctx.new_page()
        page.goto(URL); time.sleep(3)
        ask(page, "Water is leaking from B-301's bathroom into the ceiling of B-201. Who pays for the repair?", 9)
        click(page, "nav [data-tab=complaints]", 4)
        click(page, "nav [data-tab=dues]", 4)
        ask_btn = "tr:has-text('B-302') button"
        click(page, ask_btn, 1)
        page.wait_for_function("!document.querySelector('.typing')", timeout=180_000); time.sleep(8)
        page.select_option("#lang", "mr"); time.sleep(1)
        ask(page, "A member wants to rent out his flat. Does he need an NOC from the society, and what can we charge?", 9)
        page.select_option("#lang", "en")
        ask(page, "Can the committee ban dogs from using the lift?", 8)
        click(page, "nav [data-tab=rules]", 4)
        ctx.close(); b.close()
    vid = max(OUT.glob("*.webm"), key=lambda f: f.stat().st_mtime)
    final = OUT / "screen.webm"
    vid.replace(final)
    if shutil.which("ffmpeg"):
        subprocess.run(["ffmpeg", "-y", "-i", str(final), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        "-r", "30", str(OUT / "screen.mp4")], check=False)
    print("Saved", final)


if __name__ == "__main__":
    main()
