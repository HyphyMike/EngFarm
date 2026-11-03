import llm

async def incoming(m):
    try:
        return int(await llm.raw(
            "Score 0-100 how worth answering this reply is. Additions and questions score high, "
            "'nice post' scores low.\n\n" + m["text"], 8))
    except Exception:
        return 50

def target_score(t, relationship):
    s = min(t["likes"] / 20, 30)
    s += max(0, 25 - t["replies"])
    s += 20 if relationship else 0
    return s