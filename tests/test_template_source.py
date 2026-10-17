import pytest
from hybrid_candidate.template_source import lexer_source


@pytest.mark.parametrize(('source','expected'),[
    ('',''),('a','a'),('a\n','a'),('a\n\n','a\n'),
    ('a\r\nb\r\n','a\nb'),('a\rb\r','a\nb\n'),('a\n ','a\n '),
])
def test_pinned_lexer_normalization_preserves_other_whitespace(source,expected):
    assert lexer_source(source)==expected
