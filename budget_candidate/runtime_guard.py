"""Fail closed on executable model-artifact loaders in the inference process."""
def disable_artifact_loaders(torch):
    def denied(*args,**kwargs):
        raise RuntimeError('Executable model artifact loading is disabled in this inference process')
    guarded=[]
    for owner,name,label in [(torch,'load','torch.load'),
                             (torch.serialization,'load','torch.serialization.load'),
                             (torch.jit,'load','torch.jit.load'),
                             (torch.export,'load','torch.export.load')]:
        if hasattr(owner,name):setattr(owner,name,denied);guarded.append(label)
    return {'blocked_loaders':guarded,'scope':'inference-process Python entry points; not a complete package security claim'}
