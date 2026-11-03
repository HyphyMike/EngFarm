import re
import llm

NUM = re.compile(r"\d")

async def gate(store, text, slot=0):
    if not NUM.search(text):
        return "pass", text
    v = await llm.verify_claim(text)
    if v.startswith("VERIFIED"):
        return "pass", text
    if v.startswith("UNVERIFIABLE"):
        return "strip", await llm.strip_numbers(text)
    store.add_claim(text, v[:120], ttl_h=6, slot=slot)
    print("  [QUEUED] " + text)
    return "queue", text

async def approve_queue(store):
    for cid, text in store.approved_claims():
        store.queue_send(text, "claim")
        store.retire_claim(cid, "queued")

async def expire_pass(store):
    for cid, text in store.expired_claims():
        store.queue_send(await llm.strip_numbers(text), "claim_stripped")
        store.retire_claim(cid, "expired_stripped")
        print("  [TTL->strip] claim %d" % cid)