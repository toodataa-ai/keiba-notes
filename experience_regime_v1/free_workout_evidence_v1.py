#!/usr/bin/env python3
"""Single-page, low-volume free workout observations, separate from formal STEP1.

Source data are *factual times*, not copied reviews, articles or author grades.
Never extract or redistribute JRA video. No paid member pages, login or CAPTCHA.
No past-start predictions or modifications of immutable JRA forecasts.
Manual source URL assignment (not web crawling), robots.txt gate, one article GET.

To collect: python -m experience_regime_v1.free_workout_evidence_v1
  --week-id YYYY-MM-DD --race-id YYYY-MM-DD-{venue}-NN
  --source-url https://umasiru.com/archives/<article_id>
  --outdir /tmp/research-evidence
The runner validates the Git first-introduction commit of the frozen roster and
accepts only strictly prestart observations. Publishing the resulting evidence
requires a separate Git first-introduction proof before the scheduled start.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup, Tag

ROOT = Path(__file__).resolve().parents[1]
JST = ZoneInfo("Asia/Tokyo")
USER_AGENT = "keiba-notes-research/1.0 (single factual workout page; no article republishing)"
ARTICLE_HOSTS = {"umasiru.com", "www.umasiru.com"}
ARTICLE_RE = re.compile(r"^/archives/\d+/?$")
WORKOUT_LABELS = ("最終追切", "最終追い切り", "1週前", "一週前", "前走最終")
COLS = ("6F", "5F", "4F", "3F", "1F")
RANGES = {"6F": (60, 170), "5F": (50, 145), "4F": (37, 110),
          "3F": (26, 80), "1F": (9, 22)}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def parse_dt(s: str) -> datetime:
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("timezone_aware_datetime_required")
    return dt


def validate_source_url(source_url: str):
    p = urlparse(source_url)
    if (p.scheme != "https" or p.hostname not in ARTICLE_HOSTS or
        not ARTICLE_RE.fullmatch(p.path) or p.username or p.password or
        p.query or p.fragment or p.port):
        raise ValueError("unsupported_or_nonpublic_source_url")
    return p


def prestart_proof(path: Path, deadline: datetime):
    relative = path.relative_to(ROOT).as_posix()
    history = subprocess.check_output(
        ["git", "log", "--diff-filter=A", "--reverse", "--format=%H %cI", "--", relative],
        cwd=ROOT, text=True).strip().splitlines()
    if len(history) != 1:
        raise ValueError("frozen_roster_first_git_proof_missing_or_ambiguous")
    sha, stamp = history[0].split()
    if parse_dt(stamp) >= deadline:
        raise ValueError("frozen_roster_first_git_commit_after_start")
    first = subprocess.check_output(["git", "show", sha + ":" + relative], cwd=ROOT)
    if first != path.read_bytes():
        raise ValueError("frozen_roster_modified_since_first_git_commit")
    return {"commit_sha": sha, "first_committed_at": stamp,
            "sha256": hashlib.sha256(first).hexdigest(), "path": relative}


def exact_names(roster_path: Path, is_formal: bool):
    doc = read_json(roster_path)
    runners = doc["runners"]
    names = {r["horse_name"]: r["horse_number"] for r in runners}
    if len(names) != len(runners):
        raise ValueError("duplicate_roster_horse_names")
    if not all(isinstance(n, int) and n >= 1 for n in names.values()):
        raise ValueError("invalid_roster_horse_numbers")
    if is_formal:
        if not doc["source_proof_commit"]:
            raise ValueError("formal_prediction_has_no_proof")
    else:
        if doc.get("production_effect") or doc.get("no_odds_or_results_accessed") is not True:
            raise ValueError("research_source_must_be_price_blind")
    return doc, names


def find_roster(week_id: str, race_id: str, start_at: str):
    deadline = parse_dt(start_at)
    if not race_id.startswith(start_at[:10]):
        raise ValueError("race_date_does_not_match_start")
    if datetime.now(JST) >= deadline:
        raise ValueError("no_new_source_collection_after_start")
    paths = [
        ROOT / "experience_regime_v1/step1_frozen" / week_id / (race_id + ".json"),
        ROOT / "experience_regime_v1/research_step1_candidates" / week_id / (race_id + ".json"),
    ]
    existing = [p for p in paths if p.is_file()]
    if len(existing) != 1:
        raise ValueError("exactly_one_frozen_proven_roster_required")
    source = existing[0]
    doc, names = exact_names(source, source == paths[0])
    if doc["race_id"] != race_id:
        raise ValueError("race_id_frozen_roster_mismatch")
    proof = prestart_proof(source, deadline)
    return names, proof, source == paths[0]


def parse_time(cell: str, column: str):
    raw = cell.strip().replace("秒", "").replace("．", ".")
    # The ⑦ symbol denotes 7F stored under a publisher's 6F header.
    # Do not silently misinterpret 7F98.0 as 6F98.0.
    if not raw or raw in ("-", "－", "—", "―", "－", "–"):
        return None
    if re.search(r"[①②③④⑤⑥⑦⑧⑨➊➋➌➍➎➏➐]", raw):
        return None
    if not re.fullmatch(r"\d{1,3}\.\d", raw):
        return None
    t = float(raw)
    low, high = RANGES[column]
    return round(t, 1) if low <= t <= high else None


def parse_course(raw):
    m = re.fullmatch(
        r"(美浦|栗東)\s*(坂路|CW|W|ウッド|芝|ダート|P|ポリトラック)"
        r"(?:[（(](良|稍重|重|不良)[）)])?", raw.strip())
    if m is None:
        return {"label":raw.strip(), "center":None,"course":None,"going":None}
    canonical = {"CW":"ウッド","W":"ウッド","ウッド":"ウッド","P":"ポリトラック"}
    return {"label":raw.strip(),"center":m.group(1),
            "course":canonical.get(m.group(2), m.group(2)), "going":m.group(3)}


def workbook_from_html(html: bytes, roster: dict[str, int], race_date: date):
    """Extract only horse-identified per-session numeric observations, no article prose."""
    doc = BeautifulSoup(html, "html.parser")
    article = doc.find("article") or doc.find("main") or doc
    findings = {}
    for header in article.find_all(["h3","h4"]):
        horse = " ".join(header.get_text(" ", strip=True).split())
        if horse not in roster:
            continue
        if horse in findings:
            raise ValueError("duplicate_horse_heading:" + horse)
        table = None
        session_date = None
        # The table may be wrapped in a WordPress <figure>; follow at most
        # the current horse section and never cross into another horse.
        for el in header.next_elements:
            if not isinstance(el, Tag):
                continue
            if el is not header and el.name in ("h2","h3","h4"):
                break
            if el.name == "p" and session_date is None:
                txt = el.get_text(" ", strip=True)
                m = re.search(r"(\d{1,2})月(\d{1,2})日", txt)
                if m:
                    year = race_date.year
                    candidate = date(year, int(m.group(1)), int(m.group(2)))
                    if candidate > race_date:
                        candidate = date(year - 1, int(m.group(1)), int(m.group(2)))
                    session_date = candidate.isoformat()
            if el.name == "table":
                table = el
                break
        if table is None:
            continue
        lines = table.find_all("tr")
        if not lines:
            continue
        labels = [s.get_text(" ", strip=True) for s in lines[0].find_all(["th","td"])]
        norm = lambda t: re.sub(r"\s+","",t).replace("Ｆ","F")
        labels = [norm(t) for t in labels]
        # Strictly require explicit column labels to avoid shifted/misread clocks.
        if not ({"時期", "場所", "6F", "5F", "4F", "3F", "1F"} <= set(labels) and
                len(set(labels)) == len(labels)):
            continue
        entries = []
        for tr in lines[1:]:
            cells = [x.get_text(" ", strip=True) for x in tr.find_all(["td","th"])]
            if len(cells) != len(labels):
                continue
            row = dict(zip(labels, cells))
            session = norm(row["時期"])
            if session not in WORKOUT_LABELS:
                continue
            course = parse_course(row["場所"])
            times = {col:parse_time(row[col],col) for col in COLS}
            observed = [k for k,v in times.items() if v is not None]
            if not observed:
                continue
            # Paired accumulated splits must decrease from longer F to shorter F.
            if any(times[COLS[i]] <= times[COLS[j]] for i in range(len(COLS))
                   for j in range(i+1, len(COLS))
                   if times[COLS[i]] is not None and times[COLS[j]] is not None):
                raise ValueError("impossible_workout_split_order:" + horse)
            entries.append({
                "session": session, "workout_date": session_date if session in ("最終追切","最終追い切り") else None,
                "course": course, "split_seconds": times,
                "observed_split_count": len(observed)
            })
        if entries:
            findings[horse] = {"horse_number":roster[horse],"horse_name":horse,"workouts":entries}
    return findings


def extract_publication_time(html: bytes):
    doc=BeautifulSoup(html,"html.parser")
    meta=doc.find("meta",attrs={"property":"article:published_time"})
    if meta and meta.get("content"):
        return parse_dt(meta["content"]).isoformat()
    for item in doc.find_all("script",attrs={"type":"application/ld+json"}):
        try:
            data=json.loads(item.string or item.get_text())
        except (json.JSONDecodeError, ValueError):
            continue
        items=data.get("@graph",[]) if isinstance(data,dict) else data if isinstance(data,list) else []
        if isinstance(data,dict): items=[data]+items
        for d in items:
            if isinstance(d,dict) and d.get("datePublished"):
                try:return parse_dt(d["datePublished"]).isoformat()
                except ValueError:pass
    return None


def fetch_single_article(url: str):
    """Robots gate, one page, no crawler. Failure => no fallback to bypassing rules."""
    from requests import Session
    p=validate_source_url(url)
    robots=f"{p.scheme}://{p.netloc}/robots.txt"
    with Session() as session:
        session.headers.update({"User-Agent":USER_AGENT})
        r=session.get(robots,timeout=12)
        if r.status_code not in (200,404,410):
            raise ValueError("robots_unavailable_block_collection:" + str(r.status_code))
        if r.status_code==200:
            parser=RobotFileParser()
            parser.parse(r.text.splitlines())
            if not parser.can_fetch(USER_AGENT,url):
                raise ValueError("source_robots_disallows_collection")
            delay=parser.crawl_delay(USER_AGENT)
            if delay and delay>0:
                raise ValueError("source_requests_crawl_delay_requires_manual_review")
        response=session.get(url,timeout=25)
        response.raise_for_status()
        if not response.headers.get("Content-Type","").lower().startswith("text/html"):
            raise ValueError("source_not_public_html")
        if len(response.content)>2_000_000 or len(response.content)<1500:
            raise ValueError("source_page_size_out_of_bounds")
        return response.content


def capture(week_id: str, race_id: str, start_at: str, source_url: str, html: bytes,
            observed_at: str, *, frozen_roster: dict|None=None, roster_proof:dict|None=None,
            is_formal:bool|None=None):
    deadline=parse_dt(start_at)
    observed=parse_dt(observed_at)
    if observed>=deadline:
        raise ValueError("observation_was_not_prestart")
    validate_source_url(source_url)
    roster,proof,formal=(frozen_roster,roster_proof,is_formal) if frozen_roster is not None else find_roster(week_id,race_id,start_at)
    if not roster or not proof:
        raise ValueError("roster_and_first_commit_proof_required")
    publication=extract_publication_time(html)
    if publication is not None and parse_dt(publication)>=deadline:
        raise ValueError("article_was_published_after_race_start")
    per_horse=workbook_from_html(html,roster,deadline.date())
    verified=sorted(per_horse.values(), key=lambda x:x["horse_number"])
    return {
        "schema_version":1,"race_id":race_id,"week_id":week_id,
        "start_at":start_at,"source":{"url":source_url,
            "source_type":"public_third_party_article_minimal_numeric_facts_not_publisher_rating",
            "article_published_at":publication,
            "fetched_at":observed_at,
            "html_sha256":hashlib.sha256(html).hexdigest(),
            "publisher_copyright_respected_no_full_text_redistribution":True},
        "frozen_roster_proof":proof,"formal_roster":bool(formal),
        "before_post":True,"no_odds_or_results_used":True,"production_effect":False,
        "prediction_rank_grade_bets_unchanged":True,
        "workout_factor_grades":None,"workout_score_calibrated":False,
        "verified_horses":len(verified),"roster_horses":len(roster),
        "unavailable_horses":sorted(set(roster)-set(per_horse)),
        "observations":verified,
        "disclaimer":"Only publicly displayed numeric workout splits; not a verified ability model. G1 article may differ from official primary source. No after-start new predictions."
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--week-id",required=True)
    p.add_argument("--race-id",required=True)
    p.add_argument("--start-at",required=True)
    p.add_argument("--source-url",required=True)
    p.add_argument("--outdir",required=True)
    args=p.parse_args()
    deadline=parse_dt(args.start_at)
    if datetime.now(JST)>=deadline:
        raise SystemExit("BLOCKED_POSTSTART_NO_RETROACTIVE_WORKOUT_EVIDENCE")
    find_roster(args.week_id,args.race_id,args.start_at)  # fail before HTTP
    html=fetch_single_article(args.source_url)
    observed=datetime.now(JST).isoformat(timespec="milliseconds")
    doc=capture(args.week_id,args.race_id,args.start_at,args.source_url,html,observed)
    if datetime.now(JST)>=deadline:
        raise SystemExit("BLOCKED_TIMING_RACE_START_PASSED_BEFORE_EVIDENCE_SAVED")
    outdir=Path(args.outdir)
    outdir.mkdir(parents=True,exist_ok=True)
    dst=outdir/(args.race_id+".json")
    with dst.open("x",encoding="utf-8") as f:
        json.dump(doc,f,ensure_ascii=False,indent=2)
        f.write("\n")
    print("FREE_WORKOUT_SINGLE_SOURCE_RESEARCH",args.race_id,
          "horses_with_workout_clocks",doc["verified_horses"],
          "of",doc["roster_horses"],"source_sha256",doc["source"]["html_sha256"])


if __name__=="__main__":
    main()
