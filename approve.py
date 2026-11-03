from store import Store

s = Store()
for cid, text in s.q("SELECT id,text FROM claims WHERE status='pending'"):
    print("[%d] %s" % (cid, text))
    if input("send? y/n ").lower() == "y":
        s.approve_claim(cid)
        print("queued for next post slot")