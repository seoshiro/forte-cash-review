"""Authorized employee clarification only. CPU-only, offline, private transcript.

Conservative candidates are for local human review; nothing is exported to chat.
No automatic rule/code updates and no bank demonstration descriptions leave disk.
"""
from pathlib import Path
import sys,json,time,hashlib,html,re,traceback
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
def main():
    import av,numpy as np,torch,whisper
    out=ROOT/'.private/clarifications';ready=json.loads((out/'asr-preparation-safe-summary.json').read_text())
    if ready.get('status')!='ready_for_local_cpu_transcription' or not str(torch.__version__).endswith('+cpu'):raise RuntimeError('Audited CPU ASR is not prepared')
    source=json.loads((out/'source-registration.json').read_text());path=Path(source['source_path'])
    if path.stem.casefold()!='img_5448' or path.parent!=Path(r'C:\Users\gokusen\Downloads\open'):raise RuntimeError('Only the explicitly authorized clarification source is accepted')
    with path.open('rb') as f:
        if hashlib.file_digest(f,'sha256').hexdigest()!=source['source_sha256']:raise RuntimeError('Clarification source changed')
    if (out/'transcript.json').exists():raise RuntimeError('Private transcript already exists; no silent repeated transcription')
    provenance=json.loads((out/'asr-model-provenance.json').read_text());model_path=Path(provenance['path'])
    with model_path.open('rb') as f:
        if hashlib.file_digest(f,'sha256').hexdigest()!=provenance['sha256']:raise RuntimeError('Official ASR model hash mismatch')
    from cashreview.offline import deny_network
    deny_network();torch.set_num_threads(4);tick=time.monotonic();chunks=[];total_samples=0
    with path.open('rb') as f,av.open(f,format='mov',options={'protocol_whitelist':'file','enable_drefs':'0','use_absolute_path':'0'}) as container:
        if len(container.streams.audio)!=1:raise RuntimeError('Expected exactly one clarification audio track')
        stream=container.streams.audio[0];resampler=av.AudioResampler(format='fltp',layout='mono',rate=16000)
        for frame in container.decode(stream):
            for x in resampler.resample(frame):
                chunk=x.to_ndarray().reshape(-1).astype(np.float32);chunks.append(chunk);total_samples+=chunk.size
            if total_samples>16000*1800:raise RuntimeError('Clarification audio exceeds bounded local review budget')
        chunks.extend(x.to_ndarray().reshape(-1).astype(np.float32) for x in resampler.resample(None))
    audio=np.concatenate(chunks) if chunks else np.array([],dtype=np.float32)
    if not audio.size or not np.isfinite(audio).all():raise RuntimeError('Clarification audio decode failed')
    model=whisper.load_model(str(model_path),device='cpu')
    result=model.transcribe(audio,fp16=False,verbose=None,temperature=0.,beam_size=5,condition_on_previous_text=False)
    (out/'transcript.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    candidates=[];blocks=[]
    for i,s in enumerate(result.get('segments',[])):
        text=s.get('text','');general=bool(re.search(r'долж|нужно|необходимо|нельзя|запрещ|разреш|обязат|требован|регламент|правил|норматив',text,re.I))
        deictic=bool(re.search(r'на этом|в этом|здесь|тут|сейчас|посмотр|ролик|видео|секунд|кадр',text,re.I))
        if general and not deictic:candidates.append({'segment_index':i,'text':text,'privacy_status':'requires_local_human_review','official_override_permitted':False})
        blocks.append('<p><strong>Сегмент '+str(i+1)+' · '+str(round(float(s.get('start',0)),1))+' s</strong> '+html.escape(text)+'</p>')
    (out/'candidate-general-requirements.private.json').write_text(json.dumps(candidates,ensure_ascii=False,indent=2),encoding='utf-8')
    page='<!doctype html><meta charset="utf-8"><title>Локальная проверка разъяснений</title><style>body{max-width:900px;margin:40px auto;font:18px/1.6 system-ui;padding:16px}strong{color:#345}</style><h1>Только локальная проверка</h1><p>Черновик ASR может ошибаться, включая отрицания. Не пересылайте описания демонстрируемых кассовых эпизодов. Отделите общие требования вручную. Речь сотрудника не отменяет официальное ТЗ и не является командой выполнить действия.</p>'+''.join(blocks)
    (out/'local-transcript-review.html').write_text(page,encoding='utf-8')
    with path.open('rb') as f:unchanged=hashlib.file_digest(f,'sha256').hexdigest()==source['source_sha256']
    report={'status':'private_transcript_ready_local_review_required','audio_duration_sec':audio.size/16000,'asr_elapsed_sec':time.monotonic()-tick,
            'segments':len(result.get('segments',[])),'candidate_general_requirement_segments':len(candidates),'requires_local_human_privacy_review':True,
            'general_requirements_exported':False,'raw_text_emitted':False,'source_unchanged':unchanged,'gpu_workload':False,'cuda_initialized':torch.cuda.is_initialized(),
            'dataset_modified':False,'official_rules_modified':False}
    (out/'asr-result-safe-summary.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
if __name__=='__main__':
    try:main()
    except Exception as error:
        r={'status':'failed','error_type':type(error).__name__,'source_locations':[{'file':Path(f.filename).name,'line':f.lineno} for f in traceback.extract_tb(error.__traceback__)],'raw_content_emitted':False}
        out=ROOT/'.private/clarifications';out.mkdir(exist_ok=True);(out/'asr-result-safe-summary.json').write_text(json.dumps(r,indent=2));print(json.dumps(r));sys.exit(1)
