"""Drafting in your voice via an OpenAI-compatible endpoint (Venice by default)."""
import os, re, httpx

BANNED_OPENERS = ("great point", "this.", "this is", "hot take", "unpopular opinion")

def _system(cfg):
    return (f"You draft tweets for @{cfg['account_handle']}. A human reviews and edits every "
            f"draft before anything is posted.\n\nVoice:\n{cfg['voice']}\n\nRules:\n"
            "- Output only the tweet text. No quotes, no preamble, no numbering.\n"
            "- Under 260 characters. No hashtags.\n"
            "- Make one specific point. Don't invent facts, numbers, or personal experiences.\n"
            "- If you'd need a fact you don't have, write it as a question instead.")

def _clean(t):
    t = t.strip().strip('"').strip()
    t = re.sub(r"^\s*(\d+[.)]|-)\s*", "", t)
    return t[:280]

def _gen(cfg, prompt, temperature=0.9):
    llm = cfg["llm"]
    r = httpx.post(f"{llm['base_url'].rstrip('/')}/chat/completions",
                   headers={"Authorization": f"Bearer {os.environ.get(llm['api_key_env'], '')}"},
                   json={"model": llm["model"], "temperature": temperature,
                         "messages": [{"role": "system", "content": _system(cfg)},
                                      {"role": "user", "content": prompt}]},
                   timeout=60)
    r.raise_for_status()
    return _clean(r.json()["choices"][0]["message"]["content"])

def variants(cfg, prompt):
    out, n = [], int(cfg["llm"].get("variants", 3))
    for i in range(n * 2):                      # a few extra tries to skip duds/dupes
        if len(out) >= n:
            break
        t = _gen(cfg, prompt, temperature=0.8 + 0.1 * (i % 3))
        if t and t not in out and not t.lower().startswith(BANNED_OPENERS):
            out.append(t)
    return out

def reply(cfg, author, text, angle=""):
    return variants(cfg, f"Draft a reply to this tweet by @{author}. Add something concrete: "
                         f"an example, a counterpoint, or a sharp question. Don't flatter."
                         f"{' Angle: ' + angle if angle else ''}\n\nTweet:\n{text}")

def quote(cfg, author, text, angle=""):
    return variants(cfg, f"Draft a quote-tweet comment on this tweet by @{author}. One sharp "
                         f"observation that stands on its own."
                         f"{' Angle: ' + angle if angle else ''}\n\nTweet:\n{text}")

def post(cfg, topic, style="take"):
    asks = {"take": f"Draft an original, opinionated post about {topic}.",
            "question": f"Draft a question about {topic} that people in the field would "
                        f"genuinely want to answer.",
            "lesson": f"Draft a short, practical tip about {topic}."}
    return variants(cfg, asks.get(style, asks["take"]))
