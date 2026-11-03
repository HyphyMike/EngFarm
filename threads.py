import json
import llm, actions
from browser import pause

async def hook_score(text):
    return await llm.score_hook(text)

async def build_chain(topic, n=4):
    out = []
    for i in range(n):
        out.append(await llm.thread_beat(topic, out, i, n))
    return out

async def publish(s, store, chain):
    handle = __import__("config").load()["account_handle"]
    res = await actions.post(s, chain[0], handle)
    root = res and res.get("id")
    if not root:
        return None
    store.save_chain(root, chain)
    await pause(8000, 18000)
    for beat in chain[1:]:
        try:
            result = await actions.reply(s, root, beat, handle)
            if not result or not result.get("id"):
                return root
            store.advance_chain(root)
            await pause(8000, 18000)
        except Exception as e:
            print("  !! chain stalled: %s" % e)
            return root
    store.finish_chain(root)
    return root

async def repair(s, store):
    handle = __import__("config").load()["account_handle"]
    for root, beats, cursor in store.open_chains():
        beats = json.loads(beats)
        for beat in beats[cursor:]:
            try:
                result = await actions.reply(s, root, beat, handle)
                if not result or not result.get("id"):
                    return
                store.advance_chain(root)
                await pause(9000, 17000)
            except Exception:
                return
        store.finish_chain(root)
        print("  [CHAIN REPAIRED] " + root)