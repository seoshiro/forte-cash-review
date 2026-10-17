"""Read-only dataset audit. Per-video information is written ONLY to .private."""
from pathlib import Path
import argparse, csv, hashlib, json, re, sys, random, math
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
        if not re.fullmatch(r'\d+:\d+(?::\d+)?(?:[.,]\d+)?',t):raise ValueError('Invalid timestamp syntax')
        parts = [float(x.replace(',','.')) for x in t.split(":")]
        if any(x>=60 for x in parts[1:]):raise ValueError('Invalid timestamp component')
        return sum(v * 60**i for i, v in enumerate(reversed(parts)))
    if re.fullmatch(r'\d+(?:[.,]\d+)?',t):
        result=float(t.replace(',','.'))
        if not math.isfinite(result):raise ValueError('Nonfinite timestamp')
        return result
    match=re.fullmatch(r'(?:(\d+)\s*(?:минута|минуты|минут|мин|м)\.?\s*)?(?:(\d+(?:[.,]\d+)?)\s*(?:секунда|секунды|секунд|сек|с)\.?)?',t)
    if not match or not any(match.groups()):raise ValueError('Invalid timestamp syntax')
    minutes=int(match[1]) if match[1] else 0;secs=float(match[2].replace(',','.')) if match[2] else 0.
    if not math.isfinite(secs) or match[1] and secs>=60:raise ValueError('Invalid timestamp component')
    return minutes*60+secs


def label_error(target,point,duration):
    if target and point is None:return 'positive_missing_timestamp'
    if not target and point is not None:return 'negative_has_timestamp'
    if point is not None and (not math.isfinite(point) or not 0<=point<duration):return 'label_outside_video'
    return None


def validate_saved_split(split,records,labels_sha256):
    if split.get('labels_sha256')!=labels_sha256:raise ValueError('Saved split label source changed')
    expected={row['sha256'] for row in records}
    if set(split['assignments'])!=expected or set(split['groups'])!=expected:raise ValueError('Saved split source inventory changed')
    grouped=defaultdict(set)
    for row in records:
        key=row['sha256'];part=split['assignments'][key]
        if part not in ['train','tune','holdout'] or split['groups'][key]!=row['group']:raise ValueError('Saved split grouping changed')
        grouped[row['group']].add(part)
    if any(len(parts)!=1 for parts in grouped.values()):raise ValueError('Saved group crosses splits')


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
                r['error']=label_error(r['target'],r['label_sec'],r['duration_sec']) or (None if r['decode_ok'] and r['pts_monotonic'] else 'invalid_decoded_pts')
                r["fingerprint"]=[dhash(s.image) for s in sample(f,[r["duration_sec"]*q for q in [.1,.3,.5,.7,.9]],max_side=96)]
            except Exception as exc: r["error"]=type(exc).__name__
        records.append(r)
    if collisions or any(row['error'] for row in records):raise ValueError('Dataset has unresolved validation errors')
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
    validate_saved_split(split,records,hashlib.file_digest(a.labels.open('rb'),'sha256').hexdigest())
    for r in records: r["split"]=split["assignments"][r['sha256']]
    (a.out/"manifest.json").write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding="utf-8")
    (a.out/"unmatched.json").write_text(json.dumps([str(f) for fs in files.values() for f in fs if f not in used],ensure_ascii=False),encoding="utf-8")
    ok=[r for r in records if r.get("decode_ok")]
    summary={"label_rows":len(records),"file_count":sum(map(len,files.values())),"matched":len(used),"unmatched":sum(map(len,files.values()))-len(used),"collisions":collisions,"errors":sum(bool(r["error"]) for r in records),"targets":dict(Counter(r["target"] for r in records)),"decode_ok":len(ok),"duration_min_sec":min((r["duration_sec"] for r in ok),default=None),"duration_max_sec":max((r["duration_sec"] for r in ok),default=None),"codecs":dict(Counter(r["codec"] for r in ok)),"rotations":dict(Counter(str(r["frame_rotations"]) for r in ok)),"groups":len(groups),"split_counts":dict(Counter(r["split"] for r in records)),"split_sha256":hashlib.file_digest(split_path.open("rb"),"sha256").hexdigest()}
    (a.out/"safe-summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps(summary))
    if collisions or summary["errors"]: sys.exit(2)

if __name__=="__main__":
    try:main()
    except Exception as error:print(json.dumps({'status':'failed','technical_error_type':type(error).__name__,'raw_private_content_emitted':False}));sys.exit(1)
