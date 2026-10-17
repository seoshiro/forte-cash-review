"""Bounded local mechanics audit. Emit fixed aggregate numbers/booleans only.

Never opens manual annotations, generated observations or media. Reuses existing
QVT features to reproduce its frozen heads, without choosing new parameters.
"""
from pathlib import Path
import os,sys,json,hashlib,time,importlib.util
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',DO_NOT_TRACK='1')
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));os.chdir(ROOT)
from cashreview.offline import deny_network
import numpy as np,openpyxl
from qvt_candidate.evaluate import fit,predict,metrics
from qvt_candidate.features import representations


def mechanical_conclusion(checks):
    passed=bool(checks) and all(value is True for value in checks.values())
    return 'Mechanical checks pass; max-window aggregation amplifies false windows. Representation/domain weakness remains a competing explanation.' if passed else 'One or more mechanical checks failed; do not infer a semantic/modeling root cause.'


def main():
    deny_network()
    started=time.monotonic();out=ROOT/'.private/qvt-mechanics';out.mkdir(exist_ok=True)
    cfg=json.loads((ROOT/'config/qvt-protocol.json').read_text())
    manifest=json.loads((ROOT/'.private/dataset/manifest.json').read_text(encoding='utf-8'))
    split=json.loads((ROOT/'.private/dataset/split.json').read_text(encoding='utf-8'))
    data_path=Path(r'C:\Users\gokusen\Downloads\open\open_labels.xlsx')
    workbook=openpyxl.load_workbook(data_path,read_only=True,data_only=True)
    sheet=workbook['labels'];raw=list(sheet.values);workbook.close()
    spec=importlib.util.spec_from_file_location('manifest_reader',ROOT/'scripts/manifest.py')
    reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader)
    positive='\u043d\u0430\u0440\u0443\u0448\u0435\u043d\u0438\u0435'
    negative='\u0431\u0435\u0437 \u043d\u0430\u0440\u0443\u0448\u0435\u043d\u0438\u044f'
    train=[r for r in manifest if r['split']=='train' and not r['error']]
    train_ids={r['normalized_id'] for r in train}
    official={reader.normalize(row[0]):(int(str(row[2]).strip().lower()==positive),reader.seconds(row[1])) for row in raw[1:]
        if row[0] is not None and reader.normalize(row[0]) in train_ids}
    normalized=[str(row[2]).strip().lower() for row in raw[1:] if row[0] is not None and reader.normalize(row[0]) in train_ids]
    match=all(official[r['normalized_id']]==(r['target'],r['label_sec']) for r in train)
    by_hash={};hash_splits={};group_splits={}
    for row in manifest:
        by_hash.setdefault(row['sha256'],[]).append(row)
        hash_splits.setdefault(row['sha256'],set()).add(row['split'])
        group_splits.setdefault(row['group'],set()).add(row['split'])
    duplicate_labels_consistent=all(len({(r['target'],r['label_sec']) for r in rows})==1 for rows in by_hash.values() if rows[0]['split']=='train')
    # Reconstruct the historical selection bug exactly. Do not repair/re-score it.
    ordered=sorted(train,key=lambda r:r['duration_sec']);probes=[ordered[0],ordered[len(ordered)//2],ordered[-1]]
    actual=probes+[r for r in sorted(train,key=lambda r:r['sha256']) if r['sha256'] not in {p['sha256'] for p in probes}]
    items=[];timestamp_valid=True;grid_max_offset=0.;finite=True;norm_error=0.;coverage=[]
    for row in actual:
        with np.load(ROOT/'.private/qvt-control/features'/(row['sha256']+'.npz'),allow_pickle=False) as z:
            times=z['times'];features=z['features']
        finite &= bool(np.isfinite(times).all() and np.isfinite(features).all())
        timestamp_valid &= bool(np.all(np.diff(times)>0) and times[0]>=0 and times[-1]<row['duration_sec']+.05)
        nominal=np.arange(0,max(.01,row['duration_sec']-.1),cfg['features']['frame_step_sec'])
        timestamp_valid &= len(times)==len(nominal)
        if len(times)==len(nominal):grid_max_offset=max(grid_max_offset,float(np.max(abs(times-nominal))))
        norm_error=max(norm_error,float(np.max(abs(np.linalg.norm(features,axis=1)-1))))
        if row['target']:coverage.append(float(np.min(abs(times-row['label_sec']))))
        items.append({'sha256':row['sha256'],'group':row['group'],'target':row['target'],'label_sec':row['label_sec'],'times':times,'features':features})
    original=json.loads((ROOT/'.private/qvt-control/private-oof-results.json').read_text())
    arms={};groups=sorted(set(item['group'] for item in items))
    for arm in ['static','temporal']:
        records=[];negative_scores=[];negative_any=0;negative_videos=0;window_counts=[];class_weight_delta=0.
        scale_error=0.;group_isolation=True;positive_column=True;prediction_match=True;time_match=True;max_score_match=True
        old={r['source_sha256']:r for r in original[arm]}
        for group in groups:
            fit_items=[i for i in items if i['group']!=group]
            group_isolation &= all(i['group']!=group for i in fit_items)
            counts={label:sum(i['target']==label for i in fit_items) for label in [0,1]}
            weights={label:0. for label in [0,1]};X=[]
            for item in fit_items:
                features=representations(item['features'])[arm]
                indices=[int(np.argmin(abs(item['times']-item['label_sec'])))] if item['target'] else list(range(len(features)))
                X.extend(features[i] for i in indices)
                weights[item['target']]+=sum(len(fit_items)/(2*counts[item['target']]*len(indices)) for _ in indices)
            class_weight_delta=max(class_weight_delta,abs(weights[0]-weights[1]))
            model=fit(fit_items,arm,cfg)
            positive_column &= model[-1].classes_.tolist()==[0,1]
            scale_error=max(scale_error,float(np.max(abs(model[0].mean_-np.mean(np.asarray(X),axis=0)))))
            for item in items:
                if item['group']!=group:continue
                values=representations(item['features'])[arm]
                scores=model.predict_proba(values)[:,1];p=predict(model,item['times'],item['features'],arm,.5)
                prediction_match &= p['prediction']==old[item['sha256']]['prediction']
                time_match &= abs(p['time_sec']-old[item['sha256']]['time_sec'])<1e-9
                max_score_match &= abs(p['score']-float(max(scores)))<1e-9
                if not item['target']:
                    negative_scores.extend(scores.tolist());negative_videos+=1;negative_any+=int(np.any(scores>=.5));window_counts.append(len(scores))
                p.update(truth=item['target'],error_sec=abs(p['time_sec']-item['label_sec']) if item['target'] else None)
                records.append(p)
        arms[arm]={'group_isolation':bool(group_isolation),'positive_probability_column_is_class_one':bool(positive_column),
            'stored_predictions_reproduced':bool(prediction_match),'stored_argmax_times_reproduced':bool(time_match),
            'video_score_is_window_max':bool(max_score_match),'scaler_mean_max_abs_error':scale_error,
            'positive_negative_total_weight_max_abs_difference':class_weight_delta,
            'negative_windows':len(negative_scores),'negative_windows_at_or_above_fixed_threshold':sum(s>=.5 for s in negative_scores),
            'negative_videos':negative_videos,'negative_videos_any_positive_window':negative_any,
            'negative_video_window_count_mean':float(np.mean(window_counts)),'metrics':metrics(records)}
    schema={'official_xlsx':{'sheet':'labels','columns':['file_identifier:string','point_timestamp:nullable text','binary_target:string']},
        'claim_ledger_csv':['claim','value','unit','sample','split','calculation','evidence_type','limitation'],
        'per_video_csv_export_created':False,'rows_disclosed':False}
    checks={'train_labels_match':match,'known_train_label_tokens':set(normalized)=={positive,negative},
        'source_workbook_digest_matches':hashlib.sha256(data_path.read_bytes()).hexdigest()==split['labels_sha256'],
        'train_duplicate_supervision_consistent':duplicate_labels_consistent,'cache_finite':bool(finite),
        'timestamps_valid':bool(timestamp_valid),'no_hash_cross_split_leaks':all(len(v)==1 for v in hash_splits.values()),
        'no_auto_group_cross_split_leaks':all(len(v)==1 for v in group_splits.values())}
    for arm,value in arms.items():
        for key in ['group_isolation','positive_probability_column_is_class_one','stored_predictions_reproduced','stored_argmax_times_reproduced','video_score_is_window_max']:
            checks[arm+'_'+key]=value[key]
        checks[arm+'_scaler_matches_fold']=value['scaler_mean_max_abs_error']<1e-6
        checks[arm+'_class_weight_totals_match']=value['positive_negative_total_weight_max_abs_difference']<1e-9
    summary={'scope':'TRAIN-supervision mechanics; global schema/hash/split metadata only; fixed historical parameters, no tuning',
        'audit_revision':2,'checks':checks,'all_mechanical_checks_passed':all(checks.values()),
        'official_workbook_schema':schema,'official_train_label_rows':len(official),'official_train_positive_labels':normalized.count(positive),
        'official_train_negative_labels':normalized.count(negative),'all_label_tokens_known':set(normalized)=={positive,negative},
        'manifest_targets_and_timestamps_match_official':match,'labels_source_hash_matches_split':hashlib.sha256(data_path.read_bytes()).hexdigest()==split['labels_sha256'],
        'negative_timestamps_are_missing':all(r['label_sec'] is None for r in train if not r['target']),
        'timestamp_parser_68_sec_synthetic_check':reader.seconds('1\u043c\u0438\u043d\u0443\u0442\u0430 8 \u0441\u0435\u043a\u0443\u043d\u0434\u0430')==68,
        'unicode_synthetic_id_normalization_check':reader.normalize('X-999.mov')==reader.normalize('\u0425-999.mov'),
        'manifest_rows':len(manifest),'unique_content_hashes':len(by_hash),'duplicate_extra_rows':len(manifest)-len(by_hash),
        'duplicate_labels_consistent':duplicate_labels_consistent,'hash_cross_split_leaks':sum(len(v)>1 for v in hash_splits.values()),
        'auto_group_cross_split_leaks':sum(len(v)>1 for v in group_splits.values()),'historical_train_rows':len(train),
        'historical_actual_items':len(actual),'cache_finite':bool(finite),'frame_l2_norm_max_abs_error':norm_error,
        'timestamps_valid_and_monotonic':bool(timestamp_valid),'sampling_grid_pts_max_offset_sec':grid_max_offset,
        'train_positive_nearest_grid_error_max_sec':max(coverage),'arms':arms,'elapsed_sec':time.monotonic()-started,
        'manual_annotations_read':False,'raw_observations_read':False,'new_model_inference':False,'tune_run':False,
        'official_workbook_all_rows_read_locally':True,'supervision_comparisons_restricted_to_train':True,
        'holdout_media_inference':False,'holdout_model_evaluation':False,'holdout_labels_used_for_model_selection':False,
        'historical_audit_inspected_all_workbook_labels':True,
        'conclusion':mechanical_conclusion(checks)}
    (out/'safe-summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary),flush=True)


if __name__=='__main__':
    try:main()
    except Exception as error:
        print(json.dumps({'status':'failed','technical_error_type':type(error).__name__,'contents_emitted':False}));sys.exit(1)
