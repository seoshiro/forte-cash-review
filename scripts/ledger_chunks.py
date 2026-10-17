"""Bounded UTF-8 CSV parts with a lossless row partition and a public index."""
from pathlib import Path
import csv,io
FIELDS=['claim','value','unit','sample','split','calculation','evidence_type','limitation']
MAX_BYTES=900*1024


def encode(rows):
    stream=io.StringIO(newline='');writer=csv.DictWriter(stream,fieldnames=FIELDS,lineterminator='\n')
    writer.writeheader();writer.writerows(rows)
    return stream.getvalue().encode('utf-8')


def write_parts(directory,rows,max_bytes=MAX_BYTES):
    directory=Path(directory);directory.mkdir(exist_ok=True)
    header=encode([]);parts=[];current=[];size=len(header)
    for row in rows:
        row_bytes=len(encode([row]))-len(header)
        if row_bytes+len(header)>max_bytes:raise ValueError('Single ledger row exceeds bound')
        if current and size+row_bytes>max_bytes:parts.append(current);current=[];size=len(header)
        current.append(row);size+=row_bytes
    if current or not parts:parts.append(current)
    if len(parts)>99:raise ValueError('Too many ledger parts')
    names=[]
    for index,part in enumerate(parts,1):
        name='claim-ledger.csv' if index==1 else f'claim-ledger-{index:02d}.csv'
        payload=encode(part);assert len(payload)<=max_bytes
        (directory/name).write_bytes(payload);names.append((name,len(part),len(payload)))
    # Delete only obsolete, narrowly named generated continuation files in this directory.
    wanted={name for name,_,_ in names}
    for path in directory.glob('claim-ledger-[0-9][0-9].csv'):
        if path.name not in wanted:path.unlink()
    lines=['# Claim ledger','',f'Aggregate numerical claims: {len(rows)} rows. Each CSV part repeats the same header. No video-level results are included.','',
        '| Part | Rows | UTF-8 bytes |','|---|---:|---:|']
    lines += [f'| [{name}]({name}) | {count} | {size} |' for name,count,size in names]
    (directory/'claim-ledger-index.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return names
