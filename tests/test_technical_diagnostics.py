import json
from pathlib import Path
import pytest
from cashreview.technical_diagnostics import classify, safe_exception, TechnicalGuardError


@pytest.mark.parametrize('error,category', [
    (RuntimeError('CUDA out of memory; PRIVATE_CLIP.mov tensor([321])'), 'cuda_oom'),
    (RuntimeError('total norm is non-finite PRIVATE_CLIP.mov'), 'numerical_instability'),
    (RuntimeError('mat1 and mat2 shapes cannot be multiplied PRIVATE_CLIP.mov'), 'shape'),
    (RuntimeError('CUBLAS_STATUS_EXECUTION_FAILED PRIVATE_CLIP.mov'), 'cuda_runtime'),
    (RuntimeError('deterministic implementation unavailable PRIVATE_CLIP.mov'), 'determinism'),
    (TechnicalGuardError('host_memory_guard'), 'host_memory_guard'),
    (TechnicalGuardError('gpu_memory_guard'), 'gpu_memory_guard'),
    (TimeoutError('PRIVATE_CLIP.mov'), 'deadline'),
    (MemoryError('PRIVATE_CLIP.mov'), 'host_oom'),
    (RuntimeError('PRIVATE_CLIP.mov arbitrary unseen payload'), 'unclassified_technical')])
def test_classification_and_report_never_emit_message_data(error, category):
    assert classify(error) == category
    try: raise error
    except Exception as caught:
        report = safe_exception(caught, Path(__file__).resolve().parents[1],
                                {'rss_mib': 123., 'filename': 'PRIVATE_CLIP.mov', 'gpu_free_mib': float('nan')})
    encoded = json.dumps(report)
    assert 'PRIVATE_CLIP' not in encoded and 'tensor(' not in encoded and 'filename' not in encoded
    assert report['resources'] == {'rss_mib': 123.}
    assert report['technical_category'] == category and report['code_stack_locations']
    assert all(set(v) == {'code_file', 'line', 'function'} for v in report['code_stack_locations'])


def test_unknown_guard_code_refused():
    with pytest.raises(ValueError): TechnicalGuardError('PRIVATE_CLIP.mov')
