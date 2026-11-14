"""Owner-controlled bootstrap. Tokens are displayed only at creation.

python -m veap.enterprise.cli bootstrap --org "VEAB Pilot" --email admin@example.org
python -m veap.enterprise.cli add-user --tenant TENANT_ID --email reviewer@example.org --role reviewer
"""
from __future__ import annotations
import argparse
import os
from .db import StudioDB


def main(argv=None):
    parser=argparse.ArgumentParser(description='VEAB Assurance Studio operator bootstrap (local CLI)')
    cmd=parser.add_subparsers(dest='action',required=True)
    boot=cmd.add_parser('bootstrap')
    boot.add_argument('--org',required=True)
    boot.add_argument('--email',required=True)
    boot.add_argument('--name',default='Platform owner')
    add=cmd.add_parser('add-user')
    add.add_argument('--tenant',required=True)
    add.add_argument('--email',required=True)
    add.add_argument('--name',default='Reviewer')
    add.add_argument('--role',required=True,choices=['owner','researcher','reviewer','auditor','viewer'])
    for p in (boot,add):
        p.add_argument('--oidc-subject',default=None)
        p.add_argument('--oidc-issuer',default=None)
    args=parser.parse_args(argv)
    root=os.getenv('VEAB_STUDIO_DATA_DIR','./studio-data')
    repo=StudioDB(root)
    if args.action=='bootstrap':
        tenant,actor=repo.bootstrap(args.org,args.email,args.name,oidc_issuer=args.oidc_issuer,
                                    oidc_subject=args.oidc_subject)
    else:
        tenant,actor=repo.bootstrap('',args.email,args.name,role=args.role,tenant_id=args.tenant,
                                    oidc_issuer=args.oidc_issuer,oidc_subject=args.oidc_subject)
    print('Tenant ID:',tenant)
    print('Principal ID:',actor)
    if args.oidc_subject:
        print('OIDC account bound; no developer token issued.')
    else:
        print('Developer bearer token (displayed once):',repo.issue_dev_token(actor))
        print('Do not commit this token. Developer mode is loopback-only.')

if __name__=='__main__':
    main()
