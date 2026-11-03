import re, statistics
import llm

BOUNDS = {
    "mean_sentence": (6, 15),
    "lowercase_rate": (0.0, 0.35),
    "comma_per_100": (0.0, 4.0),
    "emoji_rate": (0.0, 0.15),
}

def measure(text):
    sents = [s for s in re.split(r"[.!?]+", text) if s.strip()]
    words = re.findall(r"\b\w+\b", text)
    return {
        "mean_sentence": statistics.mean([len(s.split()) for s in sents]) if sents else 0,
        "lowercase_rate": sum(w[0].islower() for w in words) / max(len(words), 1),
        "comma_per_100": text.count(",") / max(len(words), 1) * 100,
        "emoji_rate": sum(ord(c) > 0x2100 for c in text) / max(len(words), 1),
    }

def in_bounds(m):
    return all(BOUNDS[k][0] <= m[k] <= BOUNDS[k][1] for k in BOUNDS)

async def conform(store, text, prompt):
    if in_bounds(measure(text)):
        return text
    for _ in range(2):
        text = await llm.regen(prompt, measure(text))
        if in_bounds(measure(text)):
            break
    return text

def drift_report(store):
    recent = store.recent_texts(50)
    if len(recent) < 10:
        return {}
    return {k: round(statistics.mean([measure(t)[k] for t in recent]), 2) for k in BOUNDS}