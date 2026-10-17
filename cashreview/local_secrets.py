"""User-scoped Windows DPAPI storage for this app's newly generated secrets."""
import ctypes,os,json
from ctypes import wintypes as w
from pathlib import Path


class Blob(ctypes.Structure):
    _fields_=[('size',w.DWORD),('data',ctypes.POINTER(ctypes.c_ubyte))]


def crypt(data,protect):
    if os.name!='nt':raise RuntimeError('Windows user-scoped DPAPI required')
    buffer=ctypes.create_string_buffer(data);source=Blob(len(data),ctypes.cast(buffer,ctypes.POINTER(ctypes.c_ubyte)));target=Blob()
    library=ctypes.WinDLL('crypt32',use_last_error=True);kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    fn=library.CryptProtectData if protect else library.CryptUnprotectData
    fn.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,w.DWORD,ctypes.POINTER(Blob)]
    fn.restype=w.BOOL;kernel.LocalFree.argtypes=[ctypes.c_void_p];kernel.LocalFree.restype=ctypes.c_void_p
    if not fn(ctypes.byref(source),None,None,None,None,1,ctypes.byref(target)):raise OSError('DPAPI operation failed')
    try:return ctypes.string_at(target.data,target.size)
    finally:kernel.LocalFree(ctypes.cast(target.data,ctypes.c_void_p))


def save(path,value):
    payload=json.dumps(value,ensure_ascii=True).encode('utf-8');encrypted=crypt(payload,True)
    with Path(path).open('xb') as stream:stream.write(encrypted);stream.flush();os.fsync(stream.fileno())


def load(path):
    return json.loads(crypt(Path(path).read_bytes(),False).decode('utf-8'))
