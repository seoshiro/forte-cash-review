"""Reproduce trial counts from retained aggregate reports and public configs."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1];private=ROOT/'.private'
cpu=json.loads((private/'cpu-baseline/safe-summary.json').read_text())
video=json.loads((private/'video-baseline/safe-summary.json').read_text())
centered=json.loads((private/'centered-proposal/safe-summary.json').read_text())
config=json.loads((ROOT/'config/centered-proposal.json').read_text())
counts={'window_cpu_tune_configurations':len(cpu['results']),
        'video_cpu_tune_configurations':len(video['results']),
        'centered_cpu_tune_configurations':sum(k.startswith('tune_') and 'constant_' not in k for k in centered['results']),
        'centered_train_oof_metric_configurations':len(config['variants'])*len(config['C_candidates'])*len(config['threshold_candidates'])*2,
        'centered_train_folds':config['train_group_folds'],
        'centered_train_cv_model_fits':len(config['variants'])*len(config['C_candidates'])*config['train_group_folds'],
        'completed_cpu_hypothesis_families':3,
        'qwen_format_configurations':sum((private/folder/'safe-summary.json').is_file() for folder in ['benchmark-bf16-initial','benchmark-compact-json-2','benchmark']),
        'registered_new_architecture_candidates':1,'registered_train_only_syntax_repairs_max':1,
        'candidate_tune_evaluations_per_configuration_max':1,
        'holdout_opened':False}
counts['completed_cpu_tune_configurations']=sum(counts[k] for k in ['window_cpu_tune_configurations','video_cpu_tune_configurations','centered_cpu_tune_configurations'])
counts['qwen_uniform_tune_runs_started']=sum('uniform-tune' in path.name for path in (private/'experiments').glob('*') if (path/'frozen-config.json').is_file())
(private/'experiment-count-safe-summary.json').write_text(json.dumps(counts,indent=2),encoding='utf-8')
print(json.dumps(counts))
