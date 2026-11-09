from __future__ import annotations

import math


class S:
    """出走1回ごとの積み上げ。期待＝オッズから作った勝つ確率（その日のそのレースで合計1に直す）"""
    __slots__ = ("n", "win", "top3", "exp", "var", "ret")

    def __init__(self):
        self.n = self.win = self.top3 = 0
        self.exp = self.var = self.ret = 0.0

    def add(self, p: float, finish, odds):
        self.n += 1
        self.exp += p
        self.var += p * (1 - p)
        if finish == 1:
            self.win += 1
            self.ret += odds
        if finish is not None and finish <= 3:
            self.top3 += 1

    def out(self, nd: int = 3) -> dict:
        n = self.n
        ae = self.win / self.exp if self.exp > 0 else None
        z = (self.win - self.exp) / math.sqrt(self.var) if self.var > 0 else None
        return {"n": n, "win": round(self.win / n, nd) if n else None, "top3": round(self.top3 / n, nd) if n else None,
                "ae": round(ae, 3) if ae is not None else None, "z": round(z, 2) if z is not None else None,
                "roi": round(self.ret / n, 3) if n else None}


def band(dist: int) -> str:
    if dist <= 1300:
        return "〜1300m"
    if dist <= 1600:
        return "1400〜1600m"
    if dist <= 2000:
        return "1700〜2000m"
    return "2100m〜"


BANDS = ["〜1300m", "1400〜1600m", "1700〜2000m", "2100m〜"]


def race_probs(rows):
    """オッズのある馬だけで、勝つ確率（合計1）を作る。オッズが足りないレースは None"""
    inv = [1 / r["odds"] if r["odds"] else None for r in rows]
    ok = [x for x in inv if x]
    if len(ok) < max(3, int(0.8 * len(rows))):
        return None
    tot = sum(ok)
    return [x / tot if x else None for x in inv]


def style_of(r, n: int):
    """脚質（最初のコーナーの位置から）：逃げ=1番手、先行=頭数の35%まで、差し=70%まで、追込=それ以降"""
    if not r["pass"]:
        return None
    pos = r["pass"][0]
    if pos == 1:
        return "逃げ"
    rel = pos / n
    return "先行" if rel <= 0.35 else ("差し" if rel <= 0.7 else "追込")


def draw_of(frame):
    if frame is None:
        return None
    return "内枠(1〜2枠)" if frame <= 2 else ("中枠(3〜6枠)" if frame <= 6 else "外枠(7〜8枠)")


def corr(pairs):
    """重みつき相関（重み＝2期間の小さい方の頭数）"""
    pairs = [(a, b, w) for a, b, w in pairs if a is not None and b is not None and w > 0]
    if len(pairs) < 5:
        return None, len(pairs)
    sw = sum(w for *_, w in pairs)
    ma = sum(a * w for a, _, w in pairs) / sw
    mb = sum(b * w for _, b, w in pairs) / sw
    va = sum(w * (a - ma) ** 2 for a, _, w in pairs)
    vb = sum(w * (b - mb) ** 2 for _, b, w in pairs)
    cv = sum(w * (a - ma) * (b - mb) for a, b, w in pairs)
    return (round(cv / math.sqrt(va * vb), 3) if va > 0 and vb > 0 else None), len(pairs)
