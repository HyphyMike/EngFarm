import os, httpx
import config

BANS = ("Great", "This", "Hot take", "Unpopular opinion", "Let's", "Here's", "Just")
_STORE = [None]

def bind(store):
    _STORE[0] = store

def _system():
    c = config.load()
    return ("You write tweets for @" + c["account_handle"] + ".\nVoice: " + c["voice"] +
            "\nRules: output the tweet only, under 240 chars, no hashtags, no emoji, "
            "no em dashes, one specific claim. Never open with: " + ", ".join(BANS))

async def _call(prompt, temp=0.95, max_tokens=200, system=None):
    c = config.load()
    async with httpx.AsyncClient(timeout=60) as cl:
        r = await cl.post("https://api.venice.ai/api/v1/chat/completions",
            headers={"Authorization": "Bearer " + os.environ["VENICE_API_KEY"]},
            json={"model": c["model"], "temperature": temp, "max_tokens": max_tokens,
                  "messages": [{"role": "system", "content": system or _system()},
                               {"role": "user", "content": prompt}]})
        r.raise_for_status()
        j = r.json()
    if _STORE[0]:
        _STORE[0].add_cost("gen", j.get("usage", {}).get("total_tokens", 0))
    return j["choices"][0]["message"]["content"].strip().strip('"')

async def _gen(prompt, temp=0.95):
    out = await _call(prompt, temp)
    for b in BANS:
        if out.startswith(b) and temp < 1.3:
            out = await _call(prompt, temp + 0.15)
            break
    return out[:279]

async def regen(prompt, stats):
    return await _call(prompt + "\n\nCurrent shape: " + str(stats) +
                       ". Rewrite closer to 9 words per sentence, few commas, some lowercase.", 0.9)

async def raw(prompt, max_tokens=8):
    return await _call(prompt, 0.2, max_tokens)

async def hot_take(seed):
    return await _gen("Confident, mildly contrarian take about: " + seed)

async def bait_question(seed):
    return await _gen("Engagement-bait question about " + seed +
                      ", answerable in under 10 words.")

async def quote_take(t):
    return await _gen("One sharp quote-tweet observation.\n\n" + t)

async def trend_take(trend, recent):
    return await _gen("Trending now: " + trend +
                      ". Standalone take, not a news summary. Recent posts of mine: " + str(recent))

async def reply_to(text, handle, trend=None):
    ctx = (" Part of the " + trend + " trend.") if trend else ""
    return await _gen("Reply to @" + handle +
                      ". Concrete angle, agree-and-extend or push back. Don't compliment." +
                      ctx + "\n\n" + text)

async def thread_followup(text, context, directive):
    return await _gen("Them: " + text + "\nYour original: " + context +
                      "\nDirective: " + directive + "\nWrite the next line.")

async def is_answerable(t):
    return (await raw("Answerable with a real reply? yes/no.\n\n" + t, 4)).lower().startswith("y")

async def is_dead_end(t):
    return (await raw("Is this a dead-end line ('thanks!', 'agreed')? yes/no.\n\n" + t, 4)).lower().startswith("y")

async def score_hook(t):
    try:
        return int((await raw("Score 0-100 how much this hook stops scrolling.\n\n" + t, 6)).strip(" ."))
    except Exception:
        return 50

async def verify_claim(t):
    return await _call("VERIFIED / UNVERIFIABLE / CHECK. Is the number in this tweet supportable?\n\n" + t, 0.2, 12)

async def strip_numbers(t):
    return await _gen("Rewrite without any digits, keep the claim.\n\n" + t)

async def thread_beat(topic, prior, i, n):
    return await _gen("Thread on " + topic + ". Beat " + str(i + 1) + "/" + str(n) +
                      ". Prior beats: " + str(prior) + ". One short beat.")

async def plan_post(fmt, digest, lessons, segment):
    return await _gen("Format " + fmt + ". Metrics: " + str(digest) + ". Lessons: " +
                      str(lessons) + ". Audience segment: " + segment +
                      ". Give one angle in a sentence.", 0.8)

async def plan_replies(digest, targets):
    return await _call("Pick 5 reply targets from " + str(targets) + " for today's metrics " +
                       str(digest) + ". Return JSON list of handles.", 0.6)

async def propose_experiment(lessons, prior):
    return await _call("Propose one testable change. Lessons: " + str(lessons) +
                       ". Prior: " + str(prior) + ". One sentence.", 0.9)

async def reflect(top, bottom, lessons):
    return await _call("Top: " + str(top) + "\nBottom: " + str(bottom) + "\nPrior lessons: " +
                       str(lessons) + "\nIn 3 sentences, why did the top work and the bottom fail?", 0.7)

async def assess_day(trends, digest):
    return await _call("Trends: " + str(trends) + "\nMetrics: " + str(digest) +
                       "\nPOST or SKIP today, then a reason in 8 words.", 0.4, 30)

async def from_angle(fmt, angle, lessons, segment=""):
    return await _gen("Write the " + fmt + " for this angle: " + angle +
                      ". Audience: " + segment + ". " + lessons)