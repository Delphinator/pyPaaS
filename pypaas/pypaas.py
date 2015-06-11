#!/usr/bin/env python
"""
pyPaaS command line interface
"""

import os.path
import subprocess
import sys

import flock

from .repo import Repo
from .runners import SimpleProcess
from .sshkey import SSHKey


def print_usage_and_exit():
    print("""
Usage:
    pypaas git-receive-pack <repo_name>
    pypaas git-pre-receive-hook <repo_name>
    pypaas rebuild_authorized_keys
    pypaas rebuild [<repo_name> <branch>]
    pypaas list
    pypaas cleanup
""")
    sys.exit(1)


def clean_repo_name(repo_name):
    if not isinstance(repo_name, str):
        if len(repo_name) != 1:
            raise RuntimeError('More than one <repo_name>')
        repo_name = repo_name[0]

    if repo_name.startswith("'") and repo_name.endswith("'"):
        repo_name = repo_name[1:-1]
    return repo_name


def git_receive_pack(repo_name):
    repo = Repo(repo_name)
    subprocess.check_call(
        [
            "git-shell", "-c",
            "git-receive-pack '{}'".format(repo.path)
        ],
        stdout=None, stderr=None,
        stdin=None
    )


def git_pre_receive_hook(repo_name):
    repo = Repo(repo_name)
    for oldref, newref, refname in [l.split() for l in sys.stdin]:
        if not refname.startswith('refs/heads/'):
            sys.stderr.write(
                'Your are pushing something other than a branch.\n' +
                'Only branches are currently supported targets!\n'
            )
            sys.exit(1)
        branch = refname[len('refs/heads/'):]

        branches = []
        for r_branch in repo.branches.values():
            if r_branch.name == branch:
                branches.append(r_branch)

        if len(branches) == 0:
            sys.stderr.write(
                'This branch is not configured!\n'
            )
            sys.exit(1)

        for r_branch in branches:
            r_branch.deploy(newref)


def rebuild(repo_name, branch):
    if repo_name is not None:
        repo = Repo(repo_name)
        branches = [repo.branches[clean_repo_name(sys.argv[3])]]
    else:
        branches = []
        for r in Repo.all():
            branches.extend(r.branches.values())
    for b in branches:
        if b.current_checkout is None:
            print('{b.repo.name}:{b.name} has no checkout. Skipping...'
                  .format(b=b))
            continue
        b.deploy(b.current_checkout.commit)


def cmd_list():
    print("\nRepos\n=====\n")
    for r in Repo.all():
        print('{}:'.format(r.name))
        for b in r.branches.values():
            print('\t{}:'.format(b.name))
            for runner in b.runners.values():
                print('\t\t{r.name} ({r.cls_name})'
                      .format(r=runner))


def cleanup():
    SimpleProcess.cleanup()


def main():
    with open(os.path.expanduser('~/.pypaas-lock'), 'w') as f:
        try:
            # This lock prevents two instances of pypaas from running
            # concurrently.
            # This is very important: pypaas is not designed to handle
            # a second process changing state as well. Replacing a files
            # (for example) is crash-safe, but not concurrency-safe,
            # as you can overwrite stuff without even realizing.
            # Finer grained locking is not inherently impossible, it's just
            # a source of significant complexity and potential for non-obvious
            # and subtile bugs.
            with flock.Flock(f, flock.LOCK_EX | flock.LOCK_NB):

                if len(sys.argv) < 2:
                    print_usage_and_exit()

                if sys.argv[1] == 'git-receive-pack':
                    if len(sys.argv) != 3:
                        print_usage_and_exit()
                    git_receive_pack(clean_repo_name(sys.argv[2]))

                elif sys.argv[1] == 'git-pre-receive-hook':
                    if len(sys.argv) != 3:
                        print_usage_and_exit()
                    git_pre_receive_hook(clean_repo_name(sys.argv[2]))

                elif sys.argv[1] == 'rebuild_authorized_keys':
                    if len(sys.argv) != 2:
                        print_usage_and_exit()
                    SSHKey.rebuild_authorized_keys()

                elif sys.argv[1] == 'rebuild':
                    if len(sys.argv) not in [2, 4]:
                        print_usage_and_exit()
                    if len(sys.argv) == 4:
                        rebuild(clean_repo_name(sys.argv[2]),
                                clean_repo_name(sys.argv[3]))
                    else:
                        rebuild(None, None)

                elif sys.argv[1] == 'list':
                    if len(sys.argv) != 2:
                        print_usage_and_exit()
                    cmd_list()

                elif sys.argv[1] == 'cleanup':
                    if len(sys.argv) != 2:
                        print_usage_and_exit()
                    cleanup()

                else:
                    print_usage_and_exit()
        except BlockingIOError:
            print('pypaas is already running. Please try again later.')
