"""Offline, owned-process native Transformers runtime. No response logging."""
from pathlib import Path
import json
import os
import subprocess
import sys
import threading
import time
import psutil
from cashreview.supervision import atomic_json


class ResourceLimitError(RuntimeError):
    pass


class ResourceWatch:
    def __init__(self, directory, cfg):
        self.path = Path(directory) / 'resource-safe-summary.json'
        self.cfg = cfg['resources']
        self.stop_event = threading.Event()
        self.deadline = None
        self.rss = []
        self.available = []
        self.reserved = []
        self.device = []
        self.free_vram = []
        self.low = 0
        self.thread = None

    def snapshot(self):
        return {'worker_rss_peak_bytes': max(self.rss) if self.rss else None,
                'system_available_ram_min_bytes': min(self.available) if self.available else None,
                'torch_reserved_peak_observed_bytes': max(self.reserved) if self.reserved else None,
                'device_used_peak_observed_mib': max(self.device) if self.device else None,
                'device_free_min_observed_mib': min(self.free_vram) if self.free_vram else None,
                'ram_samples': len(self.rss), 'gpu_samples': len(self.device),
                'scope': 'Owned worker sampled RSS; whole-system available RAM/device VRAM include other processes; not guaranteed instantaneous high-water'}

    def abort(self, reason, code=75):
        try:
            atomic_json(self.path, dict(self.snapshot(), resource_guard_stopped=True, technical_reason=reason))
        finally:
            os._exit(code)  # Supervisor's owned Windows job releases only this worker.

    def check_torch_reserved(self):
        torch = sys.modules.get('torch')
        cuda = getattr(torch, 'cuda', None)
        if cuda is None or not getattr(cuda, 'is_initialized', lambda: False)():
            return True
        value = int(cuda.max_memory_reserved())
        self.reserved.append(value)
        return value <= self.cfg['torch_reserved_cap_bytes']

    def start(self):
        def loop():
            while not self.stop_event.is_set():
                rss = psutil.Process().memory_info().rss
                available = psutil.virtual_memory().available
                self.rss.append(rss)
                self.available.append(available)
                self.low = self.low + 1 if available < self.cfg['available_ram_floor_bytes'] else 0
                if self.low >= self.cfg['low_ram_consecutive_samples']:
                    self.abort('available_system_ram_floor')
                if rss > self.cfg['worker_rss_cap_bytes']:
                    self.abort('worker_rss_cap')
                if not self.check_torch_reserved():
                    self.abort('torch_reserved_cap')
                try:
                    result = subprocess.run(['nvidia-smi', '--id=0', '--query-gpu=memory.used,memory.free', '--format=csv,noheader,nounits'],
                                            capture_output=True, text=True, timeout=1.5, creationflags=subprocess.CREATE_NO_WINDOW)
                    if result.returncode == 0:
                        used, free = map(float, result.stdout.strip().split(','))
                        self.device.append(used)
                        self.free_vram.append(free)
                        if used > self.cfg['device_used_cap_mib']:
                            self.abort('device_used_cap')
                except (OSError, ValueError, subprocess.TimeoutExpired):
                    pass
                if self.deadline is not None and time.monotonic() > self.deadline:
                    self.abort('active_stage_deadline', 76)
                self.stop_event.wait(self.cfg['poll_sec'])
        def guarded_loop():
            try:
                loop()
            except BaseException:
                self.abort('resource_watcher_failure')
        self.thread = threading.Thread(target=guarded_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(3)
        if self.thread and self.thread.is_alive():
            raise RuntimeError('Resource watcher did not stop')
        within = self.check_torch_reserved()
        value = dict(self.snapshot(), resource_guard_stopped=False, torch_resource_limit_passed=within)
        atomic_json(self.path, value)
        return value


class LocalRuntime:
    def __init__(self, model_path, cfg, watch, global_deadline):
        if psutil.virtual_memory().available < cfg['resources']['ram_before_load_bytes']:
            raise MemoryError('Insufficient current RAM reserve before model load')
        watch.deadline = min(global_deadline, time.monotonic() + cfg['budget']['startup_sec'])
        import torch
        from transformers import AutoProcessor, InternVLForConditionalGeneration
        if not torch.cuda.is_available():
            raise RuntimeError('CUDA unavailable; no CPU fallback')
        if torch.cuda.mem_get_info()[0] / 2**20 < cfg['resources']['minimum_free_vram_before_load_mib']:
            raise MemoryError('Insufficient current GPU reserve')
        torch.set_num_threads(4)
        torch.manual_seed(cfg['inference']['seed'])
        torch.cuda.reset_peak_memory_stats()
        started = time.monotonic()
        self.torch = torch
        self.cfg = cfg
        self.watch = watch
        self.processor = AutoProcessor.from_pretrained(model_path, local_files_only=True, trust_remote_code=False)
        self.model = InternVLForConditionalGeneration.from_pretrained(model_path, local_files_only=True, trust_remote_code=False,
                                                                     dtype=torch.bfloat16, attn_implementation='sdpa').eval().to('cuda:0')
        torch.cuda.synchronize()
        if not watch.check_torch_reserved():
            raise ResourceLimitError('Torch reserved cap after load')
        self.load_sec = time.monotonic() - started
        if time.monotonic() > watch.deadline:
            raise TimeoutError('Late model load')
        watch.deadline = None

    def observe(self, images, prompt, deadline):
        outer = self.watch.deadline
        active = min(deadline, outer) if outer is not None else deadline
        self.watch.deadline = active
        try:
            return self._observe(images, prompt, active)
        finally:
            self.watch.deadline = outer

    def _observe(self, images, prompt, deadline):
        torch = self.torch
        tick = time.monotonic()
        content = []
        for index, image in enumerate(images):
            content.extend([{'type': 'text', 'text': 'F' + str(index) + ':'}, {'type': 'image', 'image': image}])
        content.append({'type': 'text', 'text': prompt})
        messages = [{'role': 'user', 'content': content}]
        batch = self.processor.apply_chat_template(messages, add_generation_prompt=True, tokenize=True, return_dict=True,
                                                    return_tensors='pt', processor_kwargs={'crop_to_patches': False, 'min_patches': 1, 'max_patches': 1})
        tokens = batch['input_ids'].shape[-1]
        image_tokens = int((batch['input_ids'] == self.model.config.image_token_id).sum().item())
        if image_tokens != len(images) * self.model.config.image_seq_length:
            raise ValueError('Unexpected frame/token correspondence')
        if tokens > self.cfg['inference']['max_input_tokens']:
            raise ValueError('Bounded input context exceeded')
        if images and batch['pixel_values'].shape[0] != len(images):
            raise ValueError('Unexpected image splitting')
        batch = batch.to('cuda:0')
        for key in batch:
            if hasattr(batch[key], 'is_floating_point') and batch[key].is_floating_point():
                batch[key] = batch[key].to(dtype=torch.bfloat16)
        with torch.inference_mode():
            generated = self.model.generate(**batch, do_sample=False, max_new_tokens=self.cfg['inference']['max_new_tokens'],
                                            use_cache=True, max_time=max(.001, deadline-time.monotonic()))
        torch.cuda.synchronize()
        if not self.watch.check_torch_reserved():
            raise ResourceLimitError('Torch reserved cap after generation')
        new = generated[0, tokens:]
        eos = self.model.generation_config.eos_token_id
        eos = [eos] if type(eos) is int else list(eos or [])
        normal = bool(len(new) and int(new[-1]) in eos)
        text = self.processor.decode(new, skip_special_tokens=True)
        metrics = {'input_tokens': tokens, 'image_tokens': image_tokens, 'output_tokens': len(new),
                   'elapsed_sec': time.monotonic()-tick, 'normal_eos': normal, 'images': len(images)}
        del batch, generated, new
        if time.monotonic() > deadline:
            raise TimeoutError('Late VLM response')
        return text, metrics

    def close(self):
        del self.model
        del self.processor
        import gc
        gc.collect()
        self.torch.cuda.empty_cache()
        self.torch.cuda.synchronize()
