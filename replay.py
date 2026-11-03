import asyncio, glob, json, sys
import llm

async def main(day=None):
    files = sorted(glob.glob("candidates/*.json"))
    if not files:
        return print("no candidate captures yet")
    path = ("candidates/%s.json" % day) if day else files[-1]
    cands = json.load(open(path))[:25]
    print("replaying %d from %s\n" % (len(cands), path))
    drift = 0
    for c in cands:
        a = await llm.reply_to(c["text"], c["handle"])
        b = await llm.reply_to(c["text"], c["handle"])
        same = len(set(a.lower().split()) & set(b.lower().split())) / max(len(a.split()), 1)
        if same < 0.35:
            drift += 1
        print("@%s\n  A: %s\n  B: %s\n  overlap: %.2f\n" % (c["handle"], a, b, same))
    print("unstable prompts: %d/%d" % (drift, len(cands)))

if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else None))