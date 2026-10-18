"""Generated-prefix-only object lifetime and exact-recipe determinism probe."""
from pathlib import Path
import gc,json,os,sys,time,weakref
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
os.environ.update(CUDA_VISIBLE_DEVICES='0',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',CUBLAS_WORKSPACE_CONFIG=':4096:8')
from cashreview.supervision import atomic_json
from cashreview.technical_diagnostics import safe_exception,save_private_trace


def main():
    import numpy as np,torch,psutil
    from threadpoolctl import threadpool_limits
    from xclip_candidate.last_layer import replay,fit
    output=ROOT/'.private/last-layer-lifetime-synthetic';output.mkdir(exist_ok=False)
    started=time.monotonic();torch.set_num_threads(2);torch.set_num_interop_threads(2);torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True
    cfg=json.loads((ROOT/'config/xclip-last-layer-protocol.json').read_text());rng=np.random.default_rng(4619);items=[]
    for index in range(6):
        prefix={key:rng.normal(size=(2,4,8,2048 if key=='h' else 512)).astype(np.float16) for key in ['h','fc2','residual','outer']}
        vector=replay({k:torch.from_numpy(v[0]) for k,v in prefix.items()}).numpy()
        items.append({'ordered':vector,'prefix':prefix,'times':np.arange(4,dtype=float),'target':index%2,'label_sec':1. if index%2 else None})
    def check():
        if time.monotonic()-started>120:raise TimeoutError('Synthetic lifetime probe wall limit')
    rows=[];first=None;equal=True
    try:
        with threadpool_limits(limits=2):
            for index in range(4):
                fitted,cost=fit(items,cfg,True,check)
                weights={key+'.'+name:value.detach().cpu().clone() for key,model in [('head',fitted[1]),('adapter',fitted[2])] for name,value in model.state_dict().items()}
                if first is None:first=weights
                else:equal=equal and all(torch.equal(first[key],value) for key,value in weights.items())
                refs=[weakref.ref(parameter) for model in fitted[1:] for parameter in model.parameters()]
                del fitted,weights
                torch.cuda.synchronize();torch.cuda.empty_cache()
                before=torch.cuda.memory_allocated()/2**20;alive_before=sum(ref() is not None for ref in refs)
                collected=gc.collect();torch.cuda.synchronize();torch.cuda.empty_cache()
                after=torch.cuda.memory_allocated()/2**20;alive_after=sum(ref() is not None for ref in refs)
                rows.append({'fit':index+1,'steps':cost['optimizer_steps'],'allocated_before_gc_mib':before,'allocated_after_gc_mib':after,
                             'parameter_objects_alive_before_gc':alive_before,'parameter_objects_alive_after_gc':alive_after,'objects_collected':collected})
        report={'status':'completed','scope':'Generated random prefixes only; no bank data, inference, semantic or quality claim',
                'fits':4,'steps_per_fit':500,'identical_repeated_fit_parameters':equal,'lifetime_observations':rows,'wall_sec':time.monotonic()-started,
                'peak_working_set_mib':psutil.Process().memory_info().peak_wset/2**20,'torch_peak_reserved_mib':torch.cuda.max_memory_reserved()/2**20,
                'gc_released_model_parameters':any(r['parameter_objects_alive_before_gc']>r['parameter_objects_alive_after_gc'] for r in rows),
                'historical_runtime_error_origin_proven':False}
        atomic_json(output/'safe-summary.json',report);print(json.dumps(report))
    except Exception as error:
        save_private_trace(error,output/'private-stack-trace.txt');report={'status':'failed','diagnostic':safe_exception(error,ROOT)}
        atomic_json(output/'safe-summary.json',report);print(json.dumps(report));raise SystemExit(1)


if __name__=='__main__':main()
