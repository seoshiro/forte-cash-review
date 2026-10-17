"""Regenerate only aggregated, traceable numerical claims."""
from pathlib import Path
import csv,json,psutil,platform
root=Path('.private');safe=root/'environment.json'
env={'python':platform.python_version(),'ram_bytes':psutil.virtual_memory().total,'ram_gib':psutil.virtual_memory().total/2**30,'logical_cpus':psutil.cpu_count(),'free_disk_bytes':psutil.disk_usage('.').free}
safe.write_text(json.dumps(env,indent=2),encoding='utf-8')
rows=[]
def add(claim,value,unit,sample,source,limit=''):
    split=sample if sample in ['train','tune','holdout','train+tune'] else 'all' if 'dataset' in source else 'not applicable'
    rows.append({'claim':claim,'value':value,'unit':unit,'sample':sample,'split':split,'calculation':source,'evidence_type':'local calculation','limitation':limit})
data=json.loads((root/'dataset/safe-summary.json').read_text())
for k in ['label_rows','file_count','matched','unmatched','collisions','errors','decode_ok','duration_min_sec','duration_max_sec','groups']:
    add(k,data[k],'seconds' if k.startswith('duration') else 'count','dataset','scripts/manifest.py -> .private/dataset/safe-summary.json')
for k,v in data['targets'].items():add('positive_labels' if k=='1' else 'negative_labels',v,'count','dataset','scripts/manifest.py -> .private/dataset/safe-summary.json')
for k,v in data['split_counts'].items():add('split_'+k,v,'videos','dataset','scripts/manifest.py -> .private/dataset/safe-summary.json','Scene families require local human review; holdout closed')
add('gpu_vram',6141,'MiB','NVIDIA SMI','nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader','Total physical VRAM; not model memory')
for k in ['ram_bytes','ram_gib','logical_cpus','free_disk_bytes']:add(k,env[k],'GiB' if k.endswith('gib') else 'count/bytes','hardware','scripts/claims.py -> .private/environment.json')
sources=list((root/'benchmark').glob('safe-summary.json'))+list((root/'experiments').glob('*/safe-summary.json'))+list((root/'cpu-baseline').glob('safe-summary.json'))+list((root/'cpu-baseline').glob('technical-benchmark.json'))+list((root/'video-baseline').glob('safe-summary.json'))+list((root/'ui-qa').glob('safe-summary.json'))
sources+=list((root/'baseline-audit').glob('safe-summary.json'))
sources+=list((root/'baseline-audit').glob('invariance.json'))
sources+=list(root.glob('network-safe-summary.json'))
sources+=list(root.glob('security-safe-summary.json'))
sources+=list(root.glob('structured-security-safe-summary.json'))
sources+=list((root/'portable-runtime').glob('safe-summary.json'))
sources+=list(root.glob('model-memory-safe-summary.json'))
sources+=list(root.glob('mirror-probe-safe-summary.json'))
sources+=list(root.glob('download-probe-safe-summary.json'))
sources+=list(root.glob('download-test-safe-summary.json'))
sources+=list((root/'centered-proposal').glob('safe-summary.json'))
sources+=list(root.glob('reconnect-download-safe-summary.json'))
sources+=list(root.glob('acceleration-safe-summary.json'))
sources+=list(root.glob('startup-safe-summary.json'))
sources+=list(root.glob('source-integrity-safe-summary.json'))
sources+=list(root.glob('updated-cuda-candidates.json'))
sources+=list((root/'benchmark-bf16-initial').glob('safe-summary.json'))
sources+=list((root/'benchmark-compact-json-2').glob('safe-summary.json'))
sources+=list(root.glob('memory-observation-safe-summary.json'))
sources+=list(root.glob('memory-during-model-safe-summary.json'))
sources+=list(root.glob('benchmark-memory-safe-summary.json'))
sources+=list(root.glob('latency-budget-safe-summary.json'))
sources+=list(root.glob('advisory-identity-safe-summary.json'))
sources+=list(root.glob('synthetic-structure-diagnostic-safe-summary.json'))
sources+=list(root.glob('generation-contract-safe-summary.json'))
sources+=list(root.glob('runtime-guard-safe-summary.json'))
sources+=list(root.glob('budget-registration-safe-summary.json'))
sources+=list(root.glob('experiment-count-safe-summary.json'))
sources+=list(root.glob('status-eta-safe-summary.json'))
sources+=list(root.glob('budget-preflight-safe-summary.json'))
sources+=list((root/'model-api-qa').glob('*/safe-summary.json'))
sources+=list((root/'structured').glob('tune-uniform.safe-summary.json'))
sources+=list((root/'stage-profile').glob('*/safe-summary.json'))
sources+=list((root/'budget-benchmark').glob('*/safe-summary.json'))
sources+=list((root/'baseline-negative').glob('safe-summary.json'))
sources+=list((root/'ui-review-qa').glob('safe-summary.json'))
sources+=list(root.glob('review-tests-safe-summary.json'))
sources+=list(root.glob('always-controls-safe-summary.json'))
sources+=list(root.glob('local-mechanics-safe-summary.json'))
sources+=list(root.glob('empty-decoder-safe-summary.json'))
sources+=list((root/'synthetic-semantics').glob('*/safe-summary.json'))
sources+=list(root.glob('synthetic-format-safe-summary.json'))
sources+=list(root.glob('test-suite-safe-summary.json'))
sources+=list((root/'gate-control').glob('*-safe-summary.json'))
sources+=list((root/'runtime-upgrade/audit').glob('safe-summary.json'))
sources+=list((root/'runtime-upgrade/audit-after-decoder').glob('safe-summary.json'))
sources+=list((root/'runtime-upgrade').glob('component-safe-summary.json'))
sources+=list(root.glob('patched-tests-safe-summary.json'))
sources+=list(root.glob('native-safety-tests-safe-summary.json'))
sources+=list((root/'gguf-control').glob('*-safe-summary.json'))
sources+=list((root/'gguf-preflight').glob('safe-summary.json'))
sources+=list((root/'gguf-shape-diagnostic').glob('safe-summary.json'))
sources+=list((root/'clarifications').glob('*-safe-summary.json'))
sources+=list((root/'clarifications').glob('source-registration.json'))
sources+=list((root/'clarifications').glob('asr-audit*/safe-summary.json'))
sources+=list((root/'gguf-sequence-diagnostic').glob('safe-summary.json'))
sources+=list((root/'gguf-sequence-diagnostic-2048').glob('safe-summary.json'))
sources+=list((root/'panel-control').glob('*-safe-summary.json'))
sources+=list(root.glob('panel-tests-safe-summary.json'))
sources+=list(root.glob('panel-power-safe-summary.json'))
sources+=list((root/'oracle-diagnostic').glob('regular-coverage-safe-summary.json'))
sources+=list((root/'oracle-format-diagnostic').glob('safe-summary.json'))
sources+=list((root/'oracle-diagnostic-r1').glob('safe-summary.json'))
sources+=list((root/'oracle-diagnostic-r1').glob('synthetic-safe-summary.json'))
sources+=list(root.glob('oracle-tests-safe-summary.json'))
sources+=list(root.glob('decoder-longest-train-safe-summary.json'))
sources+=list(root.glob('oracle-schema-validity-safe-summary.json'))
sources+=list(root.glob('manual-review-tests-safe-summary.json'))
sources+=list((root/'train-review-synthetic-qa').glob('safe-summary.json'))
sources+=list((root/'manual-review').glob('launch-safe-summary.json'))
sources+=list((root/'api-final-review').glob('safe-summary.json'))
sources+=list(root.glob('annotation-provenance-safe-summary.json'))
sources+=list(root.glob('qvt-tests-safe-summary.json'))
sources+=list((root/'qvt-control').glob('safe-summary.json'))
sources+=list((root/'qvt-control').glob('technical-safe-summary.json'))
sources+=list((root/'qvt-control').glob('synthetic-safe-summary.json'))
sources+=list((root/'qvt-control').glob('protocol-deviation-safe-summary.json'))
sources+=list((root/'prototype-cache').glob('safe-summary.json'))
sources+=list((root/'prototype-cache').glob('review-safe-summary.json'))
sources+=list(root.glob('mechanics-review-safe-summary.json'))
sources+=list(root.glob('ecc-review-safe-summary.json'))
sources+=list(root.glob('ecc-installation-safe-summary.json'))
sources+=list((root/'xclip-prepare').glob('safe-summary.json'))
sources+=list((root/'xclip-synthetic-preflight').glob('safe-summary.json'))
sources+=list((root/'xclip-control').glob('safe-summary.json'))
sources+=list((root/'xclip-control').glob('synthetic-safe-summary.json'))
sources+=list((root/'xclip-control').glob('technical-safe-summary.json'))
sources+=list(root.glob('xclip-tests-safe-summary.json'))
sources+=list((root/'hybrid-r22').glob('synthetic-safe-summary.json'))
sources+=list((root/'hybrid-r22').glob('train-safe-summary.json'))
sources+=list((root/'hybrid-r22-recovery').glob('synthetic-safe-summary.json'))
sources+=list((root/'hybrid-r22-recovery').glob('train-safe-summary.json'))
sources+=list((root/'hybrid-r22').glob('escalated-loopback-safe-summary.json'))
sources+=list(root.glob('hybrid-tests-safe-summary.json'))
sources+=list((root/'hybrid-r22-recovery').glob('control-progress-safe-summary.json'))
sources+=list((root/'hybrid-r22-recovery').glob('watchdog-safe-summary.json'))
sources+=list((root/'share-ui').glob('safe-summary.json'))
sources+=list((root/'reliability').glob('historical-safe-summary.json'))
sources+=list((root/'reliability').glob('preprocessing-geometry-safe-summary.json'))
sources+=list((root/'reliability').glob('tests-safe-summary.json'))
sources+=list((root/'xclip-experimental-v2').glob('safe-summary.json'))
sources+=list((root/'xclip-hardneg-control').glob('safe-summary.json'))
sources+=list((root/'xclip-api-synthetic-smoke').glob('integration-safe-summary.json'))
sources+=list((root/'xclip-api-synthetic-smoke').glob('terminal-safe-summary.json'))
sources+=list((root/'access-preflight').glob('safe-summary.json'))
sources+=list((root/'xclip-positive-plumbing').glob('*safe-summary.json'))
sources+=list((root/'xclip-spatial-control').glob('safe-summary.json'))
sources+=list((root/'xclip-spatial-control/run').glob('terminal-safe-summary.json'))
sources+=list((root/'qwen-action-probe').glob('safe-summary.json'))
sources+=list((root/'qwen-action-probe/run').glob('terminal-safe-summary.json'))
sources+=list((root/'qwen-static-audit').glob('safe-summary.json'))
sources+=list((root/'runtime-template-audit').glob('*safe-summary.json'))
sources+=list((root/'runtime-template-audit/run').glob('terminal-safe-summary.json'))
sources+=list((root/'qwen-text-discrimination').glob('*safe-summary.json'))
sources+=list((root/'qwen-text-discrimination/run').glob('terminal-safe-summary.json'))
sources+=list((root/'qwen-decomposition').glob('*safe-summary.json'))
sources+=list((root/'qwen-decomposition/run').glob('terminal-safe-summary.json'))
sources+=list((root/'submission-matrix').glob('*safe-summary.json'))
def numeric(prefix,value,sample,source):
    if 'configured_limits' in prefix and isinstance(value,(int,float)) and not isinstance(value,bool):
        add(prefix,value,'configured value',sample,source,'Reviewed configuration, not measured throughput or performance');return
    if isinstance(value,(int,float)) and not isinstance(value,bool):
        limitation='Original registration omitted feature-cache digests; reused TRAIN exploratory diagnostic; not independent or release evidence' if 'prototype-cache' in source else 'Internal measurement; not official jury score'
        if 'xclip-hardneg-control' in source:limitation='One fixed reused-TRAIN group OOF diagnostic; useful gate failed; no independent quality or type/rule validation'
        if 'xclip-experimental-v2' in source:limitation='Full-TRAIN prototype preparation from verified cache; no in-sample quality metric or new inference'
        if 'xclip-api-synthetic-smoke' in source:limitation='Generated rectangles only; technical integration/lifetime checks, not cash-event quality or public access'
        if 'preprocessing-geometry' in source:limitation='Dimension-based retained-area estimate only; no visual inspection and no evidence of what was cropped'
        if 'xclip-positive-plumbing' in source:limitation='Generated VFR MOV plus controlled fixed features or synthetic worker; actual JPEG/PTS/auth plumbing only, no learned recognition or evidence relevance'
        if 'xclip-spatial-control' in source:limitation='One fixed reused-TRAIN group OOF spatial ablation; no expert ROI, independent quality or type/rule validation; monitor time is not API latency'
        if 'qwen-action-probe' in source:limitation='Three generated geometric cases per cell; diagnostic counts, not bank-action quality or model-capacity evidence; actual image token counts may differ'
        if 'runtime-template-audit' in source:limitation='Synthetic no-generation template rendering or public-header calculation only; original strict props identity check failed from terminal LF normalization; no action quality, schema grammar or vision embedding validation'
        if 'qwen-text-discrimination' in source:limitation='One fixed synthetic text discrimination control; conditional images only after strict text gate. Monitor counts one compound assertion, not calls; no bank, capacity or causal backend claim'
        if 'qwen-decomposition' in source:limitation='One fixed text-only synthetic decomposition; facts and binding are separate tasks, not a model-output pipeline. Ordering sensitivity observed, root cause unknown; monitor counts one assertion, not calls; no bank-quality claim'
        if 'submission-matrix' in source:limitation='Official criterion maxima/configured deadlines or synthetic launcher mechanics only; no awarded score, model quality, public availability or submission claim'
        if 'geometry_first_prompt_rule_or_allowed_token_selection' in prefix:limitation+='; legacy metric name counts first-definition semantics only, not allowed-list selection'
        add(prefix,value,'see metric name',sample,source,limitation)
    elif isinstance(value,dict):
        for key,v in value.items():numeric(prefix+'_'+key,v,sample,source)
    elif isinstance(value,list):
        for i,v in enumerate(value):numeric(prefix+'_'+str(i),v,sample,source)
for f in sources:
    record=json.loads(f.read_text());sample=record.get('split','train+tune' if f.parent.name in ['cpu-baseline','video-baseline','baseline-audit','centered-proposal'] else 'synthetic' if f.parent.name=='ui-qa' else 'technical' if f.parent==root or f.parent.name=='portable-runtime' else 'train')
    if f.name=='technical-benchmark.json':sample='train'
    if f.parent.parent.name=='synthetic-semantics' or f.name=='synthetic-format-safe-summary.json':sample='synthetic'
    if f.parent.name=='gguf-control' and f.name=='synthetic-safe-summary.json':sample='synthetic'
    if f.parent.name=='gguf-shape-diagnostic':sample='synthetic'
    if f.parent.name in ['gguf-sequence-diagnostic','gguf-sequence-diagnostic-2048']:sample='synthetic'
    if f.parent.name=='panel-control' and f.name.startswith('synthetic'):sample='synthetic'
    if f.parent.name=='oracle-format-diagnostic':sample='synthetic'
    if f.parent.name=='train-review-synthetic-qa':sample='synthetic'
    if f.parent.name=='manual-review':sample='technical'
    if f.parent.name=='api-final-review':sample='technical'
    if f.parent.name=='qvt-control':sample='synthetic' if f.name.startswith('synthetic') else 'train'
    if f.parent.name=='prototype-cache':sample='train' if f.name=='safe-summary.json' else 'technical'
    if f.parent.name=='xclip-prepare':sample='technical'
    if f.parent.name=='xclip-synthetic-preflight':sample='synthetic'
    if f.parent.name=='xclip-control':sample='synthetic' if f.name.startswith('synthetic') else 'technical' if f.name.startswith('failure') else 'train'
    if f.parent.name.startswith('hybrid-r22'):sample='synthetic' if f.name.startswith(('synthetic','control-progress')) else 'technical' if any(k in f.name for k in ['loopback','watchdog']) else 'train'
    if f.parent.name=='share-ui':sample='synthetic UI'
    if f.parent.name in ['reliability','xclip-experimental-v2','access-preflight']:sample='synthetic' if f.name=='tests-safe-summary.json' else 'technical'
    if f.parent.name=='xclip-api-synthetic-smoke':sample='synthetic'
    if f.parent.name=='xclip-hardneg-control':sample='train'
    if f.parent.name=='xclip-positive-plumbing':sample='synthetic'
    if f.parent.name=='xclip-spatial-control':sample='train'
    if f.parent.name=='qwen-action-probe':sample='synthetic'
    if f.parent.name=='qwen-static-audit':sample='technical'
    if f.parent.name=='runtime-template-audit':sample='synthetic' if f.name in ['safe-summary.json','tests-safe-summary.json'] else 'technical'
    if f.parent.name=='qwen-text-discrimination':sample='synthetic'
    if f.parent.name=='qwen-decomposition':sample='synthetic'
    if f.parent.name=='submission-matrix':sample='technical'
    if f.parent.name=='run' and f.parent.parent.name in ['xclip-spatial-control','qwen-action-probe']:sample='technical' if f.parent.parent.name=='xclip-spatial-control' else 'synthetic'
    if f.parent.name.startswith('oracle-diagnostic'):sample='synthetic' if f.name.startswith('synthetic') else 'train'
    if f.parent.name=='clarifications':sample='technical'
    prefix=f.stem if f.parent==root else f.parent.name
    if f.parent.name=='panel-control':prefix+='_'+f.stem
    if f.parent.name.startswith('oracle-diagnostic'):prefix+='_'+f.stem
    if f.parent.name=='qvt-control':prefix+='_'+f.stem
    if f.parent.name=='prototype-cache':prefix+='_'+f.stem
    if f.parent.name=='xclip-control':prefix+='_'+f.stem
    if f.parent.name.startswith('hybrid-r22'):prefix+='_'+f.stem
    if f.parent.name in ['reliability','xclip-api-synthetic-smoke']:prefix+='_'+f.stem
    if f.parent.name=='xclip-positive-plumbing':prefix+='_'+f.stem
    if f.parent.name=='runtime-template-audit':prefix+='_'+f.stem
    if f.parent.name=='qwen-text-discrimination':prefix+='_'+f.stem
    if f.parent.name in ['qwen-decomposition','submission-matrix']:prefix+='_'+f.stem
    if f.parent.name=='run' and f.parent.parent.name=='runtime-template-audit':sample='synthetic';prefix='runtime-template-audit_monitor'
    if f.parent.name=='run' and f.parent.parent.name=='qwen-text-discrimination':sample='synthetic';prefix='qwen-text-discrimination_monitor'
    if f.parent.name=='run' and f.parent.parent.name=='qwen-decomposition':sample='synthetic';prefix='qwen-decomposition_monitor'
    if f.parent.name=='run' and f.parent.parent.name in ['xclip-spatial-control','qwen-action-probe']:prefix=f.parent.parent.name+'_monitor'
    for k,v in record.items():
        if k not in ['results','reports']:numeric(prefix+'_'+k,v,sample,str(f))
    metrics=record.get('results',record.get('reports',{}))
    for strategy,result in metrics.items():
        metric_split='train' if strategy.startswith('train_') else 'tune'
        if f.parent.name.startswith('oracle-diagnostic'):metric_split='train'
        if f.parent.name=='qvt-control':metric_split='train'
        if f.parent.name=='prototype-cache':metric_split='train'
        if f.parent.name=='xclip-control':metric_split='train'
        if f.parent.name=='xclip-hardneg-control':metric_split='train'
        if f.parent.name=='xclip-spatial-control':metric_split='train'
        if f.parent.name.startswith('hybrid-r22'):metric_split='train'
        numeric(f.parent.name+'_'+strategy,result,metric_split,str(f))
        cm=result.get('confusion_matrix_tn_fp_fn_tp')
        if cm:
            for k,v in zip(['tn','fp','fn','tp'],[cm[0][0],cm[0][1],cm[1][0],cm[1][1]]):
                limitation='Exploratory group OOF; automatic groups unreviewed; duplicate-row protocol deviation; not release evidence' if f.parent.name=='qvt-control' else 'Train is in-sample; tune is exploratory; preliminary scene groups'
                if f.parent.name=='prototype-cache':limitation='Reused TRAIN group OOF; original feature-cache digest inventory missing; not release evidence'
                if f.parent.name=='xclip-control':limitation='Exploratory reused-TRAIN group OOF; automatic scene-family groups unreviewed; no type/rule validation'
                if f.parent.name=='xclip-hardneg-control':limitation='One fixed reused-TRAIN group OOF diagnostic; useful gate failed; original baseline preserved; no type/rule validation'
                if f.parent.name=='xclip-spatial-control':limitation='One fixed reused-TRAIN group OOF spatial ablation; useful gate failed; no type/rule/evidence validation'
                if f.parent.name.startswith('hybrid-r22'):limitation='Limited R22 reused-TRAIN group OOF; binary labels cannot validate types or observations; cached-XCLIP Qwen-stage latency excludes feature extraction/API upload'
                add(f.parent.name+'_'+strategy+'_'+k,v,'videos',metric_split,str(f),limitation)
out=Path('docs/claim-ledger.csv');out.parent.mkdir(exist_ok=True)
def configured(prefix,value,source):
    if isinstance(value,(int,float)) and not isinstance(value,bool):
        if prefix.startswith(('motion_draft','xclip_draft')):
            add(prefix,value,'draft configured value','draft experiment',source,'Unregistered/unrun draft, not a measured result or acceptance evidence');return
        if prefix.startswith('prototype_cache_protocol'):
            add(prefix,value,'configured value','PROTO-CACHE-01',source,'Original fixed diagnostic configuration, not measured quality; original cache digests omitted');return
        if prefix.startswith('xclip_protocol'):
            add(prefix,value,'configured value','XCLIP-PROTO-01',source,'Pre-registered configuration/target, not measured quality');return
        if prefix.startswith('xclip_artifacts'):
            add(prefix,value,'artifact/configured value','technical',source,'Official artifact identity/size or download limit; not model speed/VRAM');return
        if prefix.startswith('xclip_hardneg_protocol'):
            add(prefix,value,'configured value','XCLIP-HARDNEG-01',source,'Pre-registered one-run diagnostic configuration/target; not measured quality');return
        if prefix.startswith('xclip_spatial_protocol'):
            add(prefix,value,'configured value','XCLIP-SPATIAL-01',source,'Pre-registered one-run spatial geometry/budget/target; not a measured result');return
        if prefix.startswith('qwen_action_probe'):
            add(prefix,value,'configured value','QWEN-ACTION-CONTROL-01',source,'Pre-registered fully synthetic diagnostic; no bank-action or capacity claim');return
        if prefix.startswith('qwen_text_discrimination'):
            add(prefix,value,'configured value','QWEN-TEXT-DISCRIMINATION-01',source,'One frozen synthetic input/decoding discrimination protocol; configured counts/budgets are not measured quality');return
        if prefix.startswith('qwen_decomposition_draft'):
            add(prefix,value,'draft configured/planning value','unregistered next choice',source,'Unrun draft; time estimate is unmeasured source-reviewer planning, not a promise or achieved runtime');return
        if prefix.startswith('qwen_decomposition_protocol'):
            add(prefix,value,'configured value','QWEN-DECOMPOSITION-01',source,'Frozen one-run text-only synthetic configuration; not measured quality or a bank semantic gate');return
        if prefix.startswith('submission_criteria'):
            add(prefix,value,'official maximum/configured planning value','submission preparation',source,'Criterion maximum is not an awarded score; deadlines are supplied organizer/user targets, not confirmed acceptance');return
        if prefix.startswith('hybrid_protocol'):
            add(prefix,value,'configured value','HYBRID-R22-01',source,'Pre-registered synthetic-gated limited-rule hypothesis, not measured quality');return
        add(prefix,value,'configured value','QVT-01' if prefix.startswith('qvt_protocol') else 'ORACLE-01R1' if prefix.startswith('oracle_protocol') else 'PANEL-01' if prefix.startswith('panel_protocol') else 'GGUF-01' if prefix.startswith('gguf_protocol') else 'GATE-01' if prefix.startswith('gate_protocol') else 'BUDGET-01R1',source,'Pre-registered configuration/target, not a measured result')
    elif isinstance(value,dict):
        for k,v in value.items():configured(prefix+'_'+k,v,source)
    elif isinstance(value,list):
        for i,v in enumerate(value):configured(prefix+'_'+str(i),v,source)
configured('budget_protocol',json.loads(Path('config/budget-protocol.json').read_text()),'config/budget-protocol.json')
configured('gate_protocol',json.loads(Path('config/gate-protocol.json').read_text()),'config/gate-protocol.json')
configured('gguf_protocol',json.loads(Path('config/gguf-protocol.json').read_text()),'config/gguf-protocol.json')
configured('panel_protocol',json.loads(Path('config/panel-protocol.json').read_text()),'config/panel-protocol.json')
configured('oracle_protocol',json.loads(Path('config/oracle-diagnostic.json').read_text()),'config/oracle-diagnostic.json')
configured('qvt_protocol',json.loads(Path('config/qvt-protocol.json').read_text()),'config/qvt-protocol.json')
configured('motion_draft',json.loads(Path('config/motion-protocol.json').read_text()),'config/motion-protocol.json')
configured('xclip_draft',json.loads(Path('config/xclip-draft.json').read_text()),'config/xclip-draft.json')
configured('prototype_cache_protocol',json.loads(Path('config/prototype-cache-protocol.json').read_text()),'config/prototype-cache-protocol.json')
configured('xclip_protocol',json.loads(Path('config/xclip-protocol.json').read_text()),'config/xclip-protocol.json')
configured('xclip_artifacts',json.loads(Path('config/xclip-artifacts.json').read_text()),'config/xclip-artifacts.json')
configured('xclip_hardneg_protocol',json.loads(Path('config/xclip-hardneg-protocol.json').read_text()),'config/xclip-hardneg-protocol.json')
configured('xclip_spatial_protocol',json.loads(Path('config/xclip-spatial-protocol.json').read_text()),'config/xclip-spatial-protocol.json')
configured('qwen_action_probe',json.loads(Path('config/qwen-action-probe.json').read_text()),'config/qwen-action-probe.json')
configured('qwen_text_discrimination',json.loads(Path('config/qwen-text-discrimination.json').read_text()),'config/qwen-text-discrimination.json')
configured('qwen_decomposition_draft',json.loads(Path('config/qwen-decomposition-draft.json').read_text()),'config/qwen-decomposition-draft.json')
configured('qwen_decomposition_protocol',json.loads(Path('config/qwen-decomposition-protocol.json').read_text()),'config/qwen-decomposition-protocol.json')
configured('submission_criteria',json.loads(Path('config/submission-criteria.json').read_text()),'config/submission-criteria.json')
configured('hybrid_protocol',json.loads(Path('config/hybrid-protocol.json').read_text()),'config/hybrid-protocol.json')
with out.open('w',newline='',encoding='utf-8') as fp:
    w=csv.DictWriter(fp,fieldnames=['claim','value','unit','sample','split','calculation','evidence_type','limitation'],lineterminator='\n');w.writeheader();w.writerows(rows)
print(json.dumps({'claim_rows':len(rows),'hardware':env}))
