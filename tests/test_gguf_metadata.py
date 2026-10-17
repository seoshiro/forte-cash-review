import struct,pytest
from scripts.audit_qwen_metadata import header


def text(value):
    raw=value.encode();return struct.pack('<Q',len(raw))+raw


def test_public_header_parser_skips_arrays_and_preserves_template(tmp_path):
    raw=b'GGUF'+struct.pack('<IQQ',3,1,3)
    raw+=text('tokenizer.tokens')+struct.pack('<IIQ',9,8,2)+text('a')+text('b')
    raw+=text('general.architecture')+struct.pack('<I',8)+text('synthetic-test')
    raw+=text('tokenizer.chat_template')+struct.pack('<I',8)+text('public synthetic template')
    path=tmp_path/'fake.gguf';path.write_bytes(raw);result=header(path)
    assert result['metadata']=={'general.architecture':'synthetic-test','tokenizer.chat_template':'public synthetic template'}
    assert result['header_bytes_read']==len(raw)


def test_header_parser_rejects_wrong_magic(tmp_path):
    path=tmp_path/'fake.gguf';path.write_bytes(b'nope')
    with pytest.raises(ValueError):header(path)


def test_truncated_last_unselected_array_is_not_accepted(tmp_path):
    raw=b'GGUF'+struct.pack('<IQQ',3,0,1)
    raw+=text('unselected.array')+struct.pack('<IIQ',9,6,10)+struct.pack('<f',1.)
    path=tmp_path/'fake.gguf';path.write_bytes(raw)
    with pytest.raises(ValueError,match='Truncated public GGUF payload'):header(path)
