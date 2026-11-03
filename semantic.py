import os
import httpx
import numpy as np

SELF_THRESH = 0.86
PEER_THRESH = 0.90
PEER_MIN_LEN = 60
PEER_BAND = 0.40

async def embed(text):
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post("https://api.venice.ai/api/v1/embeddings",
            headers={"Authorization": "Bearer " + os.environ["VENICE_API_KEY"]},
            json={"model": "text-embedding-bge-m3", "input": text[:2000]})
        r.raise_for_status()
        return np.array(r.json()["data"][0]["embedding"], dtype=np.float32)

async def too_similar(store, text, thresh=SELF_THRESH):
    v = await embed(text)
    return any(float(np.dot(v, r)) > thresh for r in store.recent_vectors(200))

async def echoes_peers(store, text):
    if len(text) < PEER_MIN_LEN:
        return False
    v = await embed(text)
    for ln, pv in store.recent_peer_vectors(400):
        if abs(ln - len(text)) / max(len(text), 1) > PEER_BAND:
            continue
        if float(np.dot(v, pv)) > PEER_THRESH:
            return True
    return False

async def remember(store, key, text):
    store.save_vector(key, (await embed(text)).tobytes())