"""Read-only dataset audit. Per-video information is written ONLY to .private."""
from pathlib import Path
import argparse, csv, hashlib, json, re, sys, random
from collections import Counter, defaultdict
import openpyxl
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cashreview.video import inspect, sample, dhash


def normalize(value):
    return re.sub(r"\s+", "", Path(str(value)).stem).replace("Х", "X").replace("х", "x").upper()


def seconds(value):
    if value is None or not str(value).strip(): return None
    t = str(value).lower().strip()
    if ":" in t:
        parts = [float(x) for x in t.split(":")]
        return sum(v * 60**i for i, v in enumerate(reversed(parts)))
    m = re.search(r"(\d+)\s*м", t)
    s = re.search(r"(\d+(?:[.,]\d+)?)\s*с", t)
    if m or s: return (int(m[1])*60 if m else 0) + (float(s[1].replace(",", ".")) if s else 0)
    return float(t.replace(",", "."))


def main():
    p=argparse.ArgumentParser(); p.add_argument("--videos", type=Path, required=True); p.add_argument("--labels",type=Path,required=True); p.add_argument("--out",type=Path,default=Path(".private/dataset")); a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=True)
    book=openpyxl.load_workbook(a.labels,read_only=True,data_only=True)
    raw=list(book["labels"].values); book.close()
    headers=[str(x).strip().lower() for x in raw[0]]
    if not all(any(t in h for h in headers) for t in ["наименование", "тайм", "нарушение"]): raise ValueError("Unexpected headers")
    indexes=[next(i for i,h in enumerate(headers) if t in h) for t in ["наименование", "тайм", "нарушение"]]
    files=defaultdict(list)
    for f in a.videos.iterdir():
        if f.is_file(): files[normalize(f.name)].append(f)
    records=[]; collisions=sum(len(v)>1 for v in files.values()); used=set()
    seen=Counter(normalize(row[indexes[0]]) for row in raw[1:] if row[indexes[0]] is not None)
    collisions += sum(n>1 for n in seen.values())
    for row in raw[1:]:
        if row[indexes[0]] is None: continue
        original=str(row[indexes[0]]); key=normalize(original)
        text=str(row[indexes[2]]).strip().lower()
        if text not in ("нарушение", "без нарушения"): raise ValueError("Unknown target")
        r={"original_id":original,"normalized_id":key,"target":int(text=="нарушение"),"label_sec":seconds(row[indexes[1]]),"error":None}
        matches=files.get(key,[])
        if len(matches)!=1: r["error"]="missing_or_ambiguous"
        else:
            f=matches[0]; used.add(f); r["path"]=str(f.resolve()); r["sha256"]=hashlib.file_digest(f.open("rb"),"sha256").hexdigest()
            try:
                r.update(inspect(f,decode=True))
                if r["label_sec"] is not None and not 0<=r["label_sec"]<r["duration_sec"]: r["error"]="label_outside_video"
                if not r["target"] and r["label_sec"] is not None: r["error"]="negative_has_timestamp"
                r["fingerprint"]=[dhash(s.image) for s in sample(f,[r["duration_sec"]*q for q in [.1,.3,.5,.7,.9]],max_side=96)]
            except Exception as exc: r["error"]=type(exc).__name__
        records.append(r)
    # Exact/near duplicates always remain together. This is not a face/identity grouping.
    parent=list(range(len(records)))
    def root(i):
        while parent[i]!=i: i=parent[i]
        return i
    for i,r in enumerate(records):
        for j,s in enumerate(records[:i]):
            f,g=r.get("fingerprint",[]),s.get("fingerprint",[])
            if r.get("sha256") and (r["sha256"]==s.get("sha256") or (len(f)==len(g)==5 and abs(r["duration_sec"]-s["duration_sec"])<1 and max((x^y).bit_count() for x,y in zip(f,g))<=6)):
                parent[root(i)]=root(j)
    groups=defaultdict(list)
    for i,r in enumerate(records): r["group"]=f"g{root(i):03d}"; groups[r["group"]].append(r)
    split_path=a.out/"split.json"
    if not split_path.exists():
        rng=random.Random(261017); buckets=defaultdict(list)
        for g,rs in groups.items(): buckets[int(any(x["target"] for x in rs))].append(g)
        splits={}
        for gs in buckets.values():
            rng.shuffle(gs); n=len(gs); nt=max(1,round(n*.2)); nh=max(1,round(n*.15))
            for k,g in enumerate(gs): splits[g]="holdout" if k<nh else "tune" if k<nh+nt else "train"
        split={"seed":261017,"group_method":"exact sha256 + 5-frame dhash distance<=6, duration<1s; scene-family grouping requires human review", "holdout_opened":False,"labels_sha256":hashlib.file_digest(a.labels.open("rb"),"sha256").hexdigest(),"assignments":{r["sha256"]:splits[r["group"]] for r in records if r.get("sha256")},"groups":{r["sha256"]:r["group"] for r in records if r.get("sha256")}}
        split_path.write_text(json.dumps(split,ensure_ascii=False,indent=2),encoding="utf-8")
    split=json.loads(split_path.read_text(encoding="utf-8"))
    for r in records: r["split"]=split["assignments"].get(r.get("sha256"))
    (a.out/"manifest.json").write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding="utf-8")
    (a.out/"unmatched.json").write_text(json.dumps([str(f) for fs in files.values() for f in fs if f not in used],ensure_ascii=False),encoding="utf-8")
    ok=[r for r in records if r.get("decode_ok")]
    summary={"label_rows":len(records),"file_count":sum(map(len,files.values())),"matched":len(used),"unmatched":sum(map(len,files.values()))-len(used),"collisions":collisions,"errors":sum(bool(r["error"]) for r in records),"targets":dict(Counter(r["target"] for r in records)),"decode_ok":len(ok),"duration_min_sec":min((r["duration_sec"] for r in ok),default=None),"duration_max_sec":max((r["duration_sec"] for r in ok),default=None),"codecs":dict(Counter(r["codec"] for r in ok)),"rotations":dict(Counter(str(r["frame_rotations"]) for r in ok)),"groups":len(groups),"split_counts":dict(Counter(r["split"] for r in records)),"split_sha256":hashlib.file_digest(split_path.open("rb"),"sha256").hexdigest()}
    (a.out/"safe-summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps(summary))
    if collisions or summary["errors"]: sys.exit(2)

if __name__=="__main__": main()
