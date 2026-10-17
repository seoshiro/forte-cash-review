from __future__ import annotations
from pathlib import Path
from io import BytesIO
import os, json, time, base64, re
import numpy as np
from .video import inspect, sample
from .schemas import Done

ROOT=Path(__file__).resolve().parents[1]


class LocalEngine:
    def __init__(self, config=None):
        import torch
        from transformers import Qwen3VLForConditionalGeneration, AutoProcessor
        self.torch=torch
        self.config=config or json.loads((ROOT/"config/experiment.json").read_text(encoding="utf-8"))
        self.registry=json.loads((ROOT/"config/rules.json").read_text(encoding="utf-8"))
        path=Path(os.environ.get("CASH_MODEL",ROOT/"models/qwen3-vl-2b")).resolve()
        if not path.is_dir(): raise RuntimeError("Local model not installed")
        torch.set_num_threads(4)
        if not torch.cuda.is_available(): raise RuntimeError("CUDA unavailable; benchmark CPU explicitly before deployment")
        self.model=Qwen3VLForConditionalGeneration.from_pretrained(str(path),local_files_only=True,torch_dtype=torch.bfloat16,attn_implementation="sdpa").to("cuda").eval()
        self.processor=AutoProcessor.from_pretrained(str(path),local_files_only=True,min_pixels=64*32*32,max_pixels=196*32*32)
        self.load_sec=None

    def observe(self, frames, research_candidates=False):
        rules=[r for r in self.registry["rules"] if r["enabled"] or research_candidates]
        if not rules: raise RuntimeError("No verified enabled rules")
        text=("You assist a human cash-procedure reviewer. These images are an ORDERED TEMPORAL SEQUENCE of the same camera, with exact seconds. Analyze actions across the sequence, not a single pose. "
              "No audio, face recognition, identity, emotion, intent, hidden bank records or numerical cash amounts. Do not read filenames or infer labels. Only describe visually supported actions. "
              "A possible violation needs ALL applicability conditions below. Missing view is NOT evidence of absence. Normal actions and ambiguous actions must not be called violations. "
              "Only use rule IDs in this verified registry: "+json.dumps(rules,ensure_ascii=False)+
              '\nReturn ONLY JSON: {"events":[{"rule_id":"R22","timestamp_sec":0.0,"confidence":0.0,"all_conditions_visible":true,"observation":"short factual visible action in Russian","limitation":"uncertainty in Russian"}],"limitation":"short review limitation"}. Empty events if none. At most 4 events. Confidence is a model estimate, not calibrated. Never invent paragraphs. Seconds must be within shown frames.')
        content=[]
        for f in frames:
            content.extend([{"type":"text","text":f"{f.sec:.3f} seconds:"},{"type":"image","image":f.image}])
        content.append({"type":"text","text":text})
        messages=[{"role":"user","content":content}]
        inputs=self.processor.apply_chat_template(messages,tokenize=True,add_generation_prompt=True,return_dict=True,return_tensors="pt").to("cuda")
        with self.torch.inference_mode():
            ids=self.model.generate(**inputs,max_new_tokens=self.config["max_new_tokens"],do_sample=False)
        output=self.processor.batch_decode(ids[:,inputs.input_ids.shape[1]:],skip_special_tokens=True)[0]
        # Content is private. Never print model output, including parse failures.
        match=re.search(r"\{.*\}",output,re.S)
        if not match: raise ValueError("Invalid model JSON")
        obj=json.loads(match[0])
        if not isinstance(obj.get("events"),list): raise ValueError("Invalid event list")
        return obj

    def analyze(self,path:Path,job_id:str,private:Path,strategy=None):
        started=time.monotonic(); cfg=self.config
        info=inspect(path); duration=info["duration_sec"]
        if not 0<duration<=180: raise ValueError("Duration outside supported budget")
        strategy=strategy or cfg["strategy"]
        observations=[]
        if strategy=="uniform":
            windows=[np.linspace(0,max(0,duration-.1),cfg["coarse_frames"]).tolist()]
        else:
            # Full timeline coverage, then refine only positive candidate windows.
            n=min(cfg["max_windows"],max(1,int(np.ceil(duration/cfg["window_sec"]))))
            edges=np.linspace(0,duration,n+1)
            windows=[np.linspace(edges[i],max(edges[i],edges[i+1]-.1),cfg["window_frames"]).tolist() for i in range(n)]
        accepted=[]; rules={r["id"]:r for r in self.registry["rules"] if r["enabled"]}
        for times in windows:
            if time.monotonic()-started>cfg["timeout_sec"]: raise TimeoutError("Analysis budget exhausted")
            frames=sample(path,times,cfg["max_side"])
            obs=self.observe(frames); observations.append({"start":frames[0].sec,"end":frames[-1].sec,"result":obs})
            for event in obs["events"]:
                if event.get("rule_id") not in rules or event.get("all_conditions_visible") is not True: continue
                conf=float(event.get("confidence",0)); t=float(event.get("timestamp_sec",-1))
                if conf<cfg["threshold"] or not frames[0].sec<=t<=frames[-1].sec: continue
                if strategy!="uniform":
                    radius=cfg["refine_radius_sec"]
                    finer=sample(path,np.linspace(max(0,t-radius),min(duration-.1,t+radius),cfg["refine_frames"]).tolist(),cfg["max_side"])
                    verify=self.observe(finer); observations.append({"start":finer[0].sec,"end":finer[-1].sec,"refinement":verify})
                    matches=[e for e in verify["events"] if e.get("rule_id")==event["rule_id"] and e.get("all_conditions_visible") is True and float(e.get("confidence",0))>=cfg["threshold"] and finer[0].sec<=float(e.get("timestamp_sec",-1))<=finer[-1].sec]
                    if not matches: continue
                    event=max(matches,key=lambda e:float(e["confidence"])); t=float(event["timestamp_sec"])
                if any(e["rule_id"]==event["rule_id"] and abs(float(e["timestamp_sec"])-t)<6 for e in accepted): continue
                accepted.append(event)
        result=[]; detail=[]
        for event in sorted(accepted,key=lambda e:float(e["timestamp_sec"])):
            t=float(event["timestamp_sec"]); rule=rules[event["rule_id"]]
            evidence=sample(path,[max(0,t-1),t,min(duration-.1,t+1)],max_side=960)
            center=min(evidence,key=lambda f:abs(f.sec-t)).sec
            encoded=[]
            for f in evidence:
                b=BytesIO(); f.image.save(b,"JPEG",quality=85)
                encoded.append({"timestamp_sec":round(f.sec,3),"image_base64":base64.b64encode(b.getvalue()).decode("ascii")})
            desc=f'{event["observation"]} Возможный признак для проверки человеком. {self.registry["document"]}, п. {rule["paragraph"]}. {self.registry["source"]}'
            result.append({"type":rule["type"],"timecode_sec":round(center,3),"description":desc,"evidence_frames":encoded})
            detail.append({"rule_id":rule["id"],"rule":rule,"observation":event["observation"],"limitation":event.get("limitation",""),"start_sec":max(0,t-3),"end_sec":min(duration,t+3),"source":self.registry["source"]})
        payload=Done(job_id=job_id,verdict="violation" if result else "no_violation",violations=result).model_dump()
        private.mkdir(parents=True,exist_ok=True)
        (private/"observations.json").write_text(json.dumps(observations,ensure_ascii=False),encoding="utf-8")
        (private/"detail.json").write_text(json.dumps({"events":detail,"duration_sec":duration,"limitations":["Автоматическая подсказка для проверки человеком; невидимые банковские данные не оцениваются.","Редкие или неразличимые действия могут быть пропущены; no_violation не доказывает соблюдение всех процедур."]},ensure_ascii=False),encoding="utf-8")
        metrics={"elapsed_sec":time.monotonic()-started,"vram_peak_mib":self.torch.cuda.max_memory_allocated()/2**20,"strategy":strategy}
        (private/"metrics.json").write_text(json.dumps(metrics),encoding="utf-8")
        return payload
