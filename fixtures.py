import asyncio, pathlib, sys
from browser import Session
import scrape

PAGES = {"trends": "https://x.com/explore/tabs/trending",
         "search": "https://x.com/search?q=ai&f=live",
         "profile": "https://x.com/levelsio"}

async def record():
    d = pathlib.Path("fixtures")
    d.mkdir(exist_ok=True)
    async with Session() as s:
        for name, url in PAGES.items():
            await s.goto(url)
            (d / (name + ".html")).write_text(await s.page.content())
            print("saved", name)

def check():
    bad = []
    for f in pathlib.Path("fixtures").glob("*.html"):
        n = scrape.count_selectors(f.read_text())
        print("%s: %d selector hits" % (f.stem, n))
        if n == 0:
            bad.append(f.stem)
    if bad:
        raise SystemExit("BROKEN: %s" % bad)

if __name__ == "__main__":
    if sys.argv[1] == "record":
        asyncio.run(record())
    else:
        check()