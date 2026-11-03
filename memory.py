import llm

async def reflect(store):
    rows = store.day_performance()
    if not rows:
        return
    top = rows[:5]
    bottom = rows[-5:]
    note = await llm.reflect(top, bottom, store.recent_lessons(20))
    store.add_lesson(note)
    print("[REFLECT] " + note)

def lessons_block(store, n=20):
    ls = store.recent_lessons(n)
    if not ls:
        return ""
    return "\n\nLessons from your own history:\n" + "\n".join("- " + l for l in ls)

def prune(store):
    store.prune(vectors=4000, metrics_days=90, events_days=60)