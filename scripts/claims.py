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
sources+=list((root/'portable-runtime').glob('safe-summary.json'))
sources+=list(root.glob('model-memory-safe-summary.json'))
sources+=list(root.glob('mirror-probe-safe-summary.json'))
sources+=list(root.glob('download-probe-safe-summary.json'))
sources+=list(root.glob('download-test-safe-summary.json'))
sources+=list((root/'centered-proposal').glob('safe-summary.json'))
def numeric(prefix,value,sample,source):
    if isinstance(value,(int,float)) and not isinstance(value,bool):add(prefix,value,'see metric name',sample,source,'Internal measurement; not official jury score')
    elif isinstance(value,dict):
        for key,v in value.items():numeric(prefix+'_'+key,v,sample,source)
    elif isinstance(value,list):
        for i,v in enumerate(value):numeric(prefix+'_'+str(i),v,sample,source)
for f in sources:
    record=json.loads(f.read_text());sample=record.get('split','train+tune' if f.parent.name in ['cpu-baseline','video-baseline','baseline-audit','centered-proposal'] else 'synthetic' if f.parent.name=='ui-qa' else 'technical' if f.parent==root or f.parent.name=='portable-runtime' else 'train')
    if f.name=='technical-benchmark.json':sample='train'
    for k,v in record.items():
        if k not in ['results','reports']:numeric(f.parent.name+'_'+k,v,sample,str(f))
    metrics=record.get('results',record.get('reports',{}))
    for strategy,result in metrics.items():
        metric_split='train' if strategy.startswith('train_') else 'tune'
        numeric(f.parent.name+'_'+strategy,result,metric_split,str(f))
        cm=result.get('confusion_matrix_tn_fp_fn_tp')
        if cm:
            for k,v in zip(['tn','fp','fn','tp'],[cm[0][0],cm[0][1],cm[1][0],cm[1][1]]):add(f.parent.name+'_'+strategy+'_'+k,v,'videos',metric_split,str(f),'Train is in-sample; tune is exploratory; preliminary scene groups')
out=Path('docs/claim-ledger.csv');out.parent.mkdir(exist_ok=True)
with out.open('w',newline='',encoding='utf-8') as fp:
    w=csv.DictWriter(fp,fieldnames=['claim','value','unit','sample','split','calculation','evidence_type','limitation']);w.writeheader();w.writerows(rows)
print(json.dumps({'claim_rows':len(rows),'hardware':env}))
