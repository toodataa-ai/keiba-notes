"""レーダーチャートの『条件』切り替え（芝/ダート・競馬場・牡牝・季節）。"""
VENUES = [("sapporo", "札幌"), ("hakodate", "函館"), ("fukushima", "福島"), ("niigata", "新潟"), ("tokyo", "東京"),
          ("nakayama", "中山"), ("chukyo", "中京"), ("kyoto", "京都"), ("hanshin", "阪神"), ("kokura", "小倉")]
VK = {j: k for k, j in VENUES}
CONDS = ([("turf", "芝", "馬場"), ("dirt", "ダート", "馬場")]
         + [("v_" + k, j, "競馬場") for k, j in VENUES]
         + [("sex_m", "牡馬（せん馬を含む）", "性別"), ("sex_f", "牝馬", "性別")]
         + [("sea_spring", "春（3〜5月）", "季節"), ("sea_summer", "夏（6〜8月）", "季節"),
            ("sea_autumn", "秋（9〜11月）", "季節"), ("sea_winter", "冬（12〜2月）", "季節")])
MIN_COND = 100


def keys(surface, venue, sex, date):
    out = ["turf" if surface == "芝" else "dirt", "v_" + VK[venue]]
    if sex:
        out.append("sex_f" if sex == "牝" else "sex_m")
    m = int(date[5:7])
    out.append("sea_spring" if 3 <= m <= 5 else "sea_summer" if 6 <= m <= 8 else "sea_autumn" if 9 <= m <= 11 else "sea_winter")
    return out


SEASON_IDX = lambda m: 0 if 3 <= m <= 5 else 1 if 6 <= m <= 8 else 2 if 9 <= m <= 11 else 3
VENUE_IDX = {j: i for i, (_, j) in enumerate(VENUES)}


def cell(surface, venue, sex, date):
    """（芝ダ, 競馬場, 性別, 季節）を 0〜159 の番号に。ページ側で同じ式をほどく"""
    return ((((1 if surface != "芝" else 0) * 10 + VENUE_IDX[venue]) * 2 + (1 if sex == "牝" else 0)) * 4
            + SEASON_IDX(int(date[5:7])))
