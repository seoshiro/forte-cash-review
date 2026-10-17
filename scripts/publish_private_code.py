"""Publish audited committed code using existing gh authorization; no raw Git logs."""
from pathlib import Path
import subprocess,os,json,sys,argparse,re
ROOT=Path(__file__).resolve().parents[1]
TARGET='seoshiro/forte-cash-review';URL='https://github.com/'+TARGET


def clean_environment(source):
    env=dict(source)
    for key in list(env):
        if key.startswith(('GIT_TRACE','CASH_','TUNNEL_','CF_','CLOUDFLARE_')) or key in ['GIT_CURL_VERBOSE','GH_DEBUG']:
            env.pop(key,None)
    env['GIT_TERMINAL_PROMPT']='0'
    return env


def command(args,allow_absent=False):
    response=subprocess.run(args,cwd=ROOT,env=clean_environment(os.environ),stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120,creationflags=subprocess.CREATE_NO_WINDOW)
    if allow_absent and response.returncode==1:return ''
    if response.returncode:raise RuntimeError('Bounded GitHub action failed')
    return response.stdout.decode('utf-8').strip()


def checked_push_destination(run=command):
    rewrites=run(['git','config','--get-regexp',r'^url\..*\.(insteadof|pushinsteadof)$'],allow_absent=True)
    if rewrites:raise RuntimeError('URL rewrites require separate inspection')
    expected=URL+'.git'
    fetch=run(['git','remote','get-url','--all','origin']).splitlines()
    push=run(['git','remote','get-url','--push','--all','origin']).splitlines()
    if fetch!=[expected] or push!=[expected]:raise RuntimeError('Unexpected or multiple push destinations')
    return expected


def require_private_target(repo):
    if repo.get('private') is not True or repo.get('full_name')!=TARGET:raise RuntimeError('Exact private repository required')


def require_unchanged_clean_head(expected,run=command):
    if run(['git','rev-parse','HEAD'])!=expected or run(['git','status','--porcelain']):raise RuntimeError('Audited snapshot changed')


def main(action):
    phase='private_target_check'
    try:
        repo=json.loads(command(['gh','api','repos/'+TARGET]));require_private_target(repo)
        head=command(['git','rev-parse','HEAD'])
        if not re.fullmatch('[0-9a-f]{40}',head):raise RuntimeError('Invalid commit identity')
        if action=='push':
            phase='clean_tree_and_publication_audits'
            if command(['git','status','--porcelain']):raise RuntimeError('Commit reviewed source before publication')
            for script in ['audit_repo.py','audit_git_history.py']:
                result=json.loads(command([sys.executable,'scripts/'+script]))
                if result.get('result',result.get('status'))!='PASS':raise RuntimeError('Publication audit failed')
            destination=checked_push_destination()
            require_private_target(json.loads(command(['gh','api','repos/'+TARGET])))
            require_unchanged_clean_head(head)
            phase='audited_code_push'
            command(['git','-c','credential.helper=','-c','credential.helper=!gh auth git-credential','push',destination,head+':refs/heads/main'])
        phase='remote_commit_verification'
        remote=json.loads(command(['gh','api','repos/'+TARGET+'/commits/main']))['sha']
        if remote!=head or command(['git','rev-parse','HEAD'])!=head:raise RuntimeError('Remote/local audited commit differs')
        report={'status':'PASS','repository_url':URL,'visibility':'PRIVATE','published_commit':remote,
            'remote_matches_local_head':True,'working_tree_clean':not bool(command(['git','status','--porcelain'])),
            'action':action,'existing_authorization_used':True,'new_credentials_or_grants_created':False,
            'raw_transport_logs_emitted':False,'bank_artifacts_or_keys_uploaded':False}
        path=ROOT/'.private/release/github-safe-summary.json';path.write_text(json.dumps(report,indent=2));print(json.dumps(report))
    except Exception as error:
        report={'status':'failed','phase':phase,'technical_error_type':type(error).__name__,'raw_transport_logs_emitted':False,'outcome_may_require_remote_check':phase=='audited_code_push'}
        print(json.dumps(report));raise SystemExit(1)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['verify','push']);args=parser.parse_args();main(args.action)
