"""Pure public-template source normalization from pinned llama.cpp b11712."""


def lexer_source(source):
    # common/jinja/lexer.cpp:29-53 checks the original final character.
    normalized=source.replace('\r\n','\n').replace('\r','\n')
    if source.endswith('\n'):normalized=normalized[:-1]
    return normalized
