"""Read-only Windows GPU memory counters for owned local model processes."""
from pathlib import Path
import ctypes as C,json,time,psutil,subprocess,re
from ctypes import wintypes as W
ROOT=Path(__file__).resolve().parents[1]
class Number(C.Union):_fields_=[('large',C.c_longlong),('double',C.c_double),('long',W.LONG)]
class Value(C.Structure):_fields_=[('status',W.DWORD),('number',Number)]
class Item(C.Structure):_fields_=[('name',W.LPWSTR),('value',Value)]
pdh=C.WinDLL('pdh.dll');pdh.PdhOpenQueryW.argtypes=[W.LPCWSTR,C.c_size_t,C.POINTER(C.c_void_p)]
pdh.PdhAddEnglishCounterW.argtypes=[C.c_void_p,W.LPCWSTR,C.c_size_t,C.POINTER(C.c_void_p)]
pdh.PdhCollectQueryData.argtypes=[C.c_void_p];pdh.PdhCloseQuery.argtypes=[C.c_void_p]
pdh.PdhGetFormattedCounterArrayW.argtypes=[C.c_void_p,W.DWORD,C.POINTER(W.DWORD),C.POINTER(W.DWORD),C.c_void_p]
query=C.c_void_p();report={'checked_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'scope':'process memory gauges and driver snapshot, not allocator peaks','bank_data_read':False}
def check(code):
    if code:raise OSError('PDH status '+hex(code & 0xffffffff))
try:
    check(pdh.PdhOpenQueryW(None,0,C.byref(query)));counters={}
    for name in ['Dedicated Usage','Shared Usage','Total Committed']:
        counter=C.c_void_p();check(pdh.PdhAddEnglishCounterW(query,'\\GPU Process Memory(*)\\'+name,0,C.byref(counter)));counters[name]=counter
    check(pdh.PdhCollectQueryData(query));time.sleep(1);check(pdh.PdhCollectQueryData(query))
    pids=set()
    for p in psutil.process_iter():
        try:
            if Path(p.cwd()).resolve()==ROOT and any(Path(x).name in {'benchmark.py','evaluate.py','diagnose_synthetic_structure.py'} for x in p.cmdline()[1:]):pids.add(p.pid)
        except (psutil.Error,OSError,ValueError):pass
    report['owned_model_processes']=len(pids);values={}
    for name,counter in counters.items():
        size=W.DWORD();count=W.DWORD();code=pdh.PdhGetFormattedCounterArrayW(counter,0x400,C.byref(size),C.byref(count),None)
        if code & 0xffffffff !=0x800007d2:check(code)
        buf=C.create_string_buffer(size.value);check(pdh.PdhGetFormattedCounterArrayW(counter,0x400,C.byref(size),C.byref(count),buf))
        items=C.cast(buf,C.POINTER(Item));total=0;matched=0
        for i in range(count.value):
            match=re.search(r'pid_(\d+)',items[i].name or '')
            if match and int(match[1]) in pids and items[i].value.status in [0,1]:total+=items[i].value.number.large;matched+=1
        values[name]={'bytes':total,'mib':total/2**20,'matching_counter_instances':matched}
    report.update(windows_pdh_available=True,process_gauges=values)
except OSError as error:report.update(windows_pdh_available=False,technical_error=str(error))
finally:
    if query:pdh.PdhCloseQuery(query)
try:
    text=subprocess.check_output(['nvidia-smi','--query-gpu=memory.total,memory.reserved,memory.used,memory.free','--format=csv,noheader,nounits'],text=True,timeout=10)
    rows=[[float(x.strip()) for x in line.split(',')] for line in text.strip().splitlines()]
    report['nvidia_smi_mib']=[dict(zip(['physical_total','driver_reserved','fb_used','fb_free'],row)) for row in rows]
except (subprocess.SubprocessError,ValueError):report['nvidia_smi_available']=False
(ROOT/'.private/memory-observation-safe-summary.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
