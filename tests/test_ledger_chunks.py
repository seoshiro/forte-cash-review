import csv
from scripts.ledger_chunks import write_parts,FIELDS


def test_utf8_row_partition_is_lossless_bounded_and_removes_stale_parts(tmp_path):
    rows=[dict(zip(FIELDS,[f'claim_{i}','значение,\nсо строкой','unit','tune','tune','safe calculation','aggregate','limitation'])) for i in range(25)]
    parts=write_parts(tmp_path,rows,500)
    assert len(parts)>1
    reconstructed=[]
    for name,count,size in parts:
        assert (tmp_path/name).stat().st_size==size<=500
        with (tmp_path/name).open(encoding='utf-8',newline='') as stream:reconstructed.extend(csv.DictReader(stream))
    assert reconstructed==rows
    assert '25 rows' in (tmp_path/'claim-ledger-index.md').read_text()
    write_parts(tmp_path,rows[:1],500)
    assert not list(tmp_path.glob('claim-ledger-[0-9][0-9].csv'))
