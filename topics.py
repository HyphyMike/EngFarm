import numpy as np
import semantic

WINDOW = 5400
THRESH = 0.82

async def hot(store, text):
    v = await semantic.embed(text)
    return any(float(np.dot(v, c)) > THRESH for c in store.live_cooldowns(WINDOW))

async def claim(store, text):
    store.add_cooldown(store._h(text), await semantic.embed(text))