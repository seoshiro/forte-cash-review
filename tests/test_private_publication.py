import pytest
from scripts.publish_private_code import clean_environment,checked_push_destination,require_private_target,require_unchanged_clean_head,URL,TARGET


def test_transport_debug_flags_are_removed_even_if_zero_and_existing_auth_is_not_replaced():
    source={'GIT_CURL_VERBOSE':'0','GIT_TRACE':'0','GIT_TRACE_CURL':'1','GH_DEBUG':'api','CASH_API_KEY':'unit-only',
        'PATH':'unit-path','GH_TOKEN':'existing-unit-only','GIT_TERMINAL_PROMPT':'1'}
    result=clean_environment(source)
    assert set(result)=={'PATH','GH_TOKEN','GIT_TERMINAL_PROMPT'}
    assert result['GIT_TERMINAL_PROMPT']=='0' and result['GH_TOKEN']==source['GH_TOKEN']
    assert source['GIT_CURL_VERBOSE']=='0'


@pytest.mark.parametrize('push,rewrites',[
    ('https://other.invalid/private.git',''),
    (URL+'.git\nhttps://other.invalid/private.git',''),
    (URL+'.git','url.https://other.invalid/.pushinsteadof https://github.com/')
])
def test_foreign_pushurl_multiple_destinations_or_rewrites_block_before_push(push,rewrites):
    calls=[]
    def run(args,allow_absent=False):
        calls.append(args)
        if args[1]=='config':return rewrites
        return push if '--push' in args else URL+'.git'
    with pytest.raises(RuntimeError):checked_push_destination(run)
    assert not any('push' in args for args in calls)


def test_single_verified_push_destination_is_used_directly():
    def run(args,allow_absent=False):return '' if args[1]=='config' else URL+'.git'
    assert checked_push_destination(run)==URL+'.git'


@pytest.mark.parametrize('repo',[{'private':False,'full_name':TARGET},{'private':True,'full_name':'other/target'}])
def test_exact_private_target_guard_is_explicit_and_cannot_be_optimized_out(repo):
    with pytest.raises(RuntimeError):require_private_target(repo)


@pytest.mark.parametrize('head,status',[('b'*40,''),('a'*40,' M public-source.py')])
def test_changed_head_or_dirty_tree_after_audit_blocks_the_snapshot(head,status):
    def run(args):return head if args[1]=='rev-parse' else status
    with pytest.raises(RuntimeError):require_unchanged_clean_head('a'*40,run)
