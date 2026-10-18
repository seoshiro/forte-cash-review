"""Allowlisted exception diagnostics. Raw messages/locals never leave private files."""
from pathlib import Path
import math, re, traceback

RESOURCE_KEYS = {'elapsed_sec', 'rss_mib', 'peak_working_set_mib', 'available_ram_mib',
                 'minimum_available_ram_mib', 'torch_allocated_mib', 'torch_reserved_mib',
                 'torch_peak_allocated_mib', 'torch_peak_reserved_mib', 'gpu_free_mib',
                 'minimum_free_gpu_mib', 'optimizer_step', 'check_calls'}
CODES = {'host_memory_guard', 'gpu_memory_guard', 'deadline_guard'}


class TechnicalGuardError(RuntimeError):
    def __init__(self, code):
        if code not in CODES: raise ValueError('Unknown technical guard code')
        self.safe_code = code
        super().__init__(code)


def classify(error):
    code = getattr(error, 'safe_code', None)
    if code in CODES: return code
    message = str(error).lower()  # Used locally for a closed category; never returned.
    if type(error).__name__ == 'OutOfMemoryError' or any(s in message for s in ['cuda out of memory', 'cuda error: out of memory', 'cublas_status_alloc_failed']): return 'cuda_oom'
    if isinstance(error, MemoryError): return 'host_oom'
    if isinstance(error, TimeoutError): return 'deadline'
    if 'registered host memory budget exceeded' in message: return 'host_memory_guard'
    if 'registered gpu memory budget exceeded' in message: return 'gpu_memory_guard'
    if 'deterministic' in message: return 'determinism'
    if any(s in message for s in ['nonfinite', 'non-finite']) or re.search(r'\b(?:nan|inf|infinity)\b', message): return 'numerical_instability'
    if any(s in message for s in ['shapes cannot be multiplied', 'size mismatch', 'shape mismatch', 'must match the size', 'invalid shape']): return 'shape'
    if any(s in message for s in ['cuda', 'cublas', 'cudnn']): return 'cuda_runtime'
    if isinstance(error, OSError): return 'io_or_os'
    return 'unclassified_technical'


def safe_exception(error, root, resources=None):
    root = Path(root).resolve(); locations = []; tb = error.__traceback__
    while tb is not None and len(locations) < 64:
        filename = Path(tb.tb_frame.f_code.co_filename)
        try:
            relative = filename.resolve().relative_to(root)
            valid = filename.suffix == '.py' and not any(p.lower() in {'.private', 'models'} for p in relative.parts)
            code_file = relative.as_posix() if valid else '<external-python-code>'
        except (ValueError, OSError): code_file = '<external-python-code>'
        function = tb.tb_frame.f_code.co_name
        if not re.fullmatch(r'[A-Za-z_<>][A-Za-z0-9_<>]{0,99}', function): function = '<code>'
        locations.append({'code_file': code_file, 'line': int(tb.tb_lineno), 'function': function})
        tb = tb.tb_next
    names = {'RuntimeError', 'ValueError', 'TimeoutError', 'OutOfMemoryError', 'MemoryError',
             'OSError', 'FileNotFoundError', 'PermissionError', 'AssertionError', 'TechnicalGuardError'}
    numbers = {key: value for key, value in (resources or {}).items()
               if key in RESOURCE_KEYS and type(value) in (int, float) and math.isfinite(value)}
    return {'exception_name': type(error).__name__ if type(error).__name__ in names else 'Exception',
            'technical_category': classify(error), 'code_stack_locations': locations,
            'resources': numbers, 'raw_message_emitted': False, 'locals_or_tensor_contents_emitted': False}


def save_private_trace(error, path):
    # Local only: capture_locals=False. Never read this file through cloud tools.
    path = Path(path)
    with path.open('x', encoding='utf-8') as stream:
        stream.writelines(traceback.TracebackException.from_exception(error, capture_locals=False).format())
