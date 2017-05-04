#!/usr/bin/env python3
# vim: set expandtab cindent sw=4 ts=4:
#
# (C)2017 Jan Tulak <jan@tulak.me>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#


import os
import sys
import re
from git import Repo
import git

PATH = os.path.dirname(__file__)
REPO_PATH = os.path.join(
        os.path.realpath(os.path.dirname(__file__)),
        '../xfsprogs-dev/')

class RevIsNotParent(Exception):
    pass

class ToolRuntimeError(RuntimeError):
    pass

def git_checkout(rev):
    curpath = os.getcwd()
    os.chdir(REPO_PATH)
    os.system('git checkout -q %s' % rev)
    os.chdir(curpath)

def git_range_to_revs(git_range):
    """ Get list of revisions for the specific range. """
    hashes=git_range.split('..')

    revisions = list()
    older = None
    newer = None

    # find which git is the older one and which the newer one
    a = repo.commit(hashes[0])
    b = repo.commit(hashes[1])
    if a.committed_date > b.committed_date:
        older = b
        newer = a
    else:
        older = a
        newer = b

    revisions.append(newer)

    parents = newer.iter_parents()
    for p in parents:
        revisions.append(p)

        if p == older:
            break

    try:
        next(parents)
    except StopIteration:
        raise RevIsNotParent(
                "Neither of the revisions %s and %s precedes the other one. "
                "Are they in different branches?" %
                (hashes[0], hashes[1]))

    revisions = reversed(revisions)
    return revisions

def get_revisions(repo, rev_list):
    """ For output of argparse, get a list of revisions.
        Break git range into specific revisions to allow a simple
        for-each over the output of this function.
    """
    revisions = list()
    for i in rev_list:
        if i.find('..') != -1:
            revisions += git_range_to_revs(i)
        else:
            revisions.append(repo.commit(i))
    return revisions

def get_revisions_or_die(repo,rev_list):
    """ return what get_revisions does, but kill the script
        if someting fails.
    """
    try:
        return get_revisions(repo, rev_list)
    except RevIsNotParent as ex:
        print("Error: %s" % str(ex))
        sys.exit(1)
    except git.exc.BadName as ex:
        print("Error: %s" % str(ex))
        sys.exit(1)

def get_repo_or_die(args_path):
    """ try to set git repo path and return the repo,
        die if it is not a repo.
    """
    global REPO_PATH
    if args_path:
        REPO_PATH = os.path.realpath(args_path)
    try:
        return Repo(REPO_PATH)
    except git.exc.NoSuchPathError:
        print("Error: Path not a git repository: %s" % REPO_PATH)
        sys.exit(1)
