"""Read-only technical TRAIN audit. Emit aggregates only; no media/results display."""
from pathlib import Path
import sys,json,hashlib,collections
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
OUT=ROOT/'.private/train-preparation-audit'


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def audit():
    import numpy as np,openpyxl
    from scripts.manifest import normalize,seconds
    from scripts.xclip_linear import inputs
    from xclip_candidate.features import window_targets
    from xclip_candidate.linear_head import supervised_windows,validate_items
    manifest=json.loads((ROOT/'.private/dataset/manifest.json').read_text(encoding='utf-8'))
    split=json.loads((ROOT/'.private/dataset/split.json').read_text())
    labels=Path(r'C:\Users\gokusen\Downloads\open\open_labels.xlsx')
    assert sha(labels)==split['labels_sha256']
    book=openpyxl.load_workbook(labels,read_only=True,data_only=True)
    source=list(book['labels'].values);book.close()
    headers=[str(x).strip().lower() for x in source[0]]
    indexes=[next(i for i,h in enumerate(headers) if term in h) for term in ['наименование','тайм','нарушение']]
    label_rows=[r for r in source[1:] if r[indexes[0]] is not None]
    assert len(label_rows)==len(manifest)==42
    lookup={row['original_id']:row for row in manifest};assert len(lookup)==len(manifest)
    assert len({normalize(r[indexes[0]]) for r in label_rows})==len(label_rows)
    for record in label_rows:
        row=lookup[str(record[indexes[0]])]
        target=str(record[indexes[2]]).strip().lower()
        assert target in ['нарушение','без нарушения']
        assert row['target']==int(target=='нарушение') and row['label_sec']==seconds(record[indexes[1]])
        assert normalize(record[indexes[0]])==row['normalized_id']==normalize(Path(row['path']).name)
        assert row['error'] is None and row['decode_ok'] and row['pts_monotonic']
        assert row['label_sec'] is None if not row['target'] else 0<=row['label_sec']<row['duration_sec']
        assert row['split']==split['assignments'][row['sha256']] and row['group']==split['groups'][row['sha256']]
    assert seconds('1минута 8 секунда')==68 and seconds(None) is None
    assert normalize('X-unit-1')==normalize('Х-unit-1.mov')
    groups=collections.defaultdict(set);content=collections.defaultdict(set)
    for row in manifest:groups[row['group']].add(row['split']);content[row['sha256']].add(row['split'])
    assert all(len(s)==1 for s in groups.values()) and all(len(s)==1 for s in content.values())
    # Recompute the original numeric near-duplicate predicate without opening frames.
    near_pairs=0
    for index,a in enumerate(manifest):
        for b in manifest[:index]:
            f,g=a.get('fingerprint',[]),b.get('fingerprint',[])
            near=(a['sha256']==b['sha256'] or len(f)==len(g)==5 and abs(a['duration_sec']-b['duration_sec'])<1 and max((x^y).bit_count() for x,y in zip(f,g))<=6)
            if near:near_pairs+=1;assert a['group']==b['group'] and a['split']==b['split']
    selected,inventory=inputs();cfg=json.loads((ROOT/'config/xclip-protocol.json').read_text())
    items=[];max_grid_error=0.;max_point_gap=0.;windows=0;nonzero_first=0
    for row in selected:
        assert sha(row['path'])==row['sha256']
        with np.load(ROOT/'.private/xclip-control/features'/f"{row['sha256']}.npz",allow_pickle=False) as data:
            item={key:np.array(data[key]) for key in ['times','ordered']}
        item.update({key:row[key] for key in ['sha256','group','target','label_sec']})
        expected=window_targets(row['duration_sec'],cfg).mean(1)
        assert item['ordered'].shape==(len(expected),512) and item['times'].shape==expected.shape
        grid_error=float(np.max(abs(item['times']-expected)));assert grid_error<=.1
        assert np.all(item['times']>=0) and np.all(item['times']<row['duration_sec'])
        assert np.allclose(np.linalg.norm(item['ordered'],axis=1),1,atol=1e-4)
        max_grid_error=max(max_grid_error,grid_error);windows+=len(expected)
        nonzero_first+=abs(row['first_pts_sec'])>1e-6
        if row['target']:max_point_gap=max(max_point_gap,float(np.min(abs(item['times']-row['label_sec']))))
        items.append(item)
    validate_items(items)
    X,y,weights=supervised_windows(items)
    positive=sum(i['target'] for i in items)
    assert int(y.sum())==positive
    assert int((y==0).sum())==sum(len(i['times']) for i in items if not i['target'])
    assert abs(weights[y==0].sum()-weights[y==1].sum())<1e-8
    for held in {i['group'] for i in items}:
        train=[i for i in items if i['group']!=held];test=[i for i in items if i['group']==held]
        assert {i['sha256'] for i in train}.isdisjoint(i['sha256'] for i in test)
        assert {i['target'] for i in train}=={0,1}
    # Generated uniform RGB only: official resize/crop/rescale/normalization exactly once.
    from transformers import AutoImageProcessor
    from PIL import Image
    processor=AutoImageProcessor.from_pretrained(str(ROOT/'models/xclip-base-patch32'),local_files_only=True,use_fast=False)
    pixels=processor(images=[[Image.new('RGB',(320,180),(255,0,0)) for _ in range(8)]],return_tensors='np')['pixel_values']
    expected=(np.array([1.,0.,0.])-np.asarray(processor.image_mean))/np.asarray(processor.image_std)
    assert pixels.shape==(1,8,3,224,224)
    color_error=float(np.max(abs(pixels[0,0,:,112,112]-expected)))
    assert color_error<1e-5 and processor.do_rescale and processor.do_normalize
    return {'status':'PASS','scope':'All42 official workbook labels/manifest metadata integrity; then TRAIN-only source/cache audit and generated RGB processor check',
        'label_rows':len(manifest),'manifest_label_mismatches':0,'normalization_collisions':0,'cross_split_groups':0,
        'exact_contents_crossing_split':0,'numeric_duplicate_pairs_same_group':near_pairs,
        'train_original_rows':sum(i['manifest_multiplicity'] for i in selected),'train_unique_contents':len(items),
        'train_groups':len({i['group'] for i in items}),'positive_unique_train_videos':positive,'negative_unique_train_videos':len(items)-positive,
        'ordered_cached_windows':windows,'cache_digests_verified':len(inventory),'train_source_digests_verified':len(selected),
        'maximum_cached_center_vs_requested_pts_sec':max_grid_error,'maximum_nearest_center_to_positive_point_sec':max_point_gap,
        'train_nonzero_first_pts_count':nonzero_first,'positive_supervised_windows_existing_baseline':int(y.sum()),
        'other_positive_windows_marked_negative':0,'synthetic_rgb_normalization_max_abs_error':color_error,
        'observed_preparation_bug':False,'scene_family_grouping_expert_verified':False,'crop_periphery_risk_remains':True,
        'code_validation_gaps_fixed':4,'manifest_split_or_cache_regenerated':False,
        'holdout_media_opened':False,'new_bank_frames_decoded':False,'new_model_inference':False,
        'tune_used_for_selection':False,'per_video_outputs_emitted':False,'annotations_or_private_predictions_read':False,
        'limitations':['Automatic dHash grouping can miss scene families; no local expert review',
            'Single point is incomplete event supervision; center crop can remove relevant periphery',
            'Center-to-point gap is not a sampled annotation-frame distance; parser reuse is not an independent parser proof',
            'Audit does not validate event types, action semantics, localization relevance or new viewpoint robustness']}


if __name__=='__main__':
    OUT.mkdir(exist_ok=True)
    try:
        result=audit();(OUT/'safe-summary.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
    except Exception as error:
        result={'status':'failed','technical_error_type':type(error).__name__,'raw_private_content_emitted':False}
        (OUT/'safe-summary.json').write_text(json.dumps(result));print(json.dumps(result));raise SystemExit(1)
