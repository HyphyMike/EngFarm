import numpy as np

ALPHA = 0.5
DIM = 6

def featurize(fmt, category, hour):
    x = np.zeros(DIM)
    x[{"bait_question": 0, "hot_take": 1, "quote_tweet": 2,
       "trend_reply": 1, "thread": 2}.get(fmt, 0)] = 1
    x[3 if category == "tech" else 4] = 1
    x[5] = np.sin(2 * np.pi * hour / 24)
    return x

def choose(store, arms, category, hour):
    best, best_v = None, -1e9
    for a in arms:
        A, b = store.bandit_state(a, DIM)
        Ainv = np.linalg.inv(A)
        theta = Ainv @ b
        x = featurize(a, category, hour)
        v = float(theta @ x + ALPHA * np.sqrt(x @ Ainv @ x))
        if v > best_v:
            best, best_v = a, v
    return best

def update(store, arm, category, hour, reward):
    x = featurize(arm, category, hour)
    A, b = store.bandit_state(arm, DIM)
    store.save_bandit(arm, A + np.outer(x, x), b + reward * x)