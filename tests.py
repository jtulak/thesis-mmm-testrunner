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

from git import Repo
import git
import os, sys, argparse
import re
import subprocess
import shutil

PATH = os.path.dirname(__file__)
REPO_PATH = os.path.join(
        os.path.realpath(os.path.dirname(__file__)),
        '../xfsprogs-dev/')
LIVE = False
OUTPUT = os.path.realpath(os.path.join(PATH, 'output'))

class RevIsNotParent(Exception):
    pass

class ToolRuntimeError(RuntimeError):
    pass

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

def save_lines(subdir, tag, lines):
    """ Save lines to a file in OUTPUT/subdir and tags it with tag."""
    path = os.path.join(OUTPUT, subdir)
    target = os.path.join(path, "%s.log"%tag)

    if os.path.isdir(path):
        shutil.rmtree(path)

    os.mkdir(path)
    with open(target, 'w') as f:
        for line in lines:
            f.write("%s\n" % line)





def get_revisions(rev_list):
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


class Tool(object):
    _name = None
    _containerPath = None

    def __init__(self):
        if self._containerPath is None:
            raise Exception("Class %s does not have set containerPath "
                        "in its definition." % type(self).__name__)
        self._containerPath = os.path.join(
                os.path.realpath(os.path.dirname(__file__)),
                self._containerPath)
        self._cmd = os.path.join(self._containerPath, 'run.sh')

    def run(self, rev):
        os.chdir(self._containerPath)
        output = []
        try:
            p = subprocess.Popen(
                    [self._cmd, REPO_PATH],
                    stdout = subprocess.PIPE,
                    stderr=subprocess.PIPE)

            for line in iter(p.stdout.readline, b''):
                line = line.decode('utf-8').replace('\n','')
                if LIVE:
                    print(line)
                output.append(line)

            save_lines(rev, self.name, output)

            p.stdout.close()
            p.wait()
        except subprocess.CalledProcessError as e:
            raise ToolRuntimeError("command '{}' return with error (code {}): {}"
                    .format(e.cmd, e.returncode, e.output))


    @property
    def name(self):
        if self._name is None:
            raise NotImplemented()
        return self._name

    def __str__(self):
        return self.name



class CppCheck(Tool):
    _name = "CppCheck"
    _containerPath = "cppcheck/"

class CPAChecker(Tool):
    _name = "CPAChecker"
    _containerPath = "cpacheck/"

    def run(self, rev):
        print("CPAchecker is not yet implemented")

class Coverity(Tool):
    _name = "Coverity"
    _containerPath = "coverity/"

    def run(self, rev):
        super().run(rev)

        path = os.path.join(OUTPUT, rev)
        target = os.path.join(path, "cov.output")

        shutil.move('cov', target)

class GCC(Tool):
    _name = "GCC"
    _containerPath = "gcc/"





# ############### MAIN ##################

tools = [GCC(), CppCheck(), CPAChecker(), Coverity()]
tools_names = [t.name for t in tools]

# parse args
parser = argparse.ArgumentParser(description='Iterate over revisions and run tests on them.')
parser.add_argument('revisions', metavar='REVISION', type=str, nargs='+',
                help='Git hash for revisions. Git range is accepted too.')
parser.add_argument('-l', '--live', action='store_true',
                help='Print live output from tools.')
parser.add_argument('-o', '--output', metavar='PATH', type=str,
                help='Output directory to save the generated data.')
parser.add_argument('--path', metavar='PATH', type=str,
                help='Path to the repo to test.')
parser.add_argument('--tool', metavar='TOOL', type=str,
                help='One of the supported tools. If ommited, all are run. '
                     'Supported tools: %s' % ', '.join(tools_names))

args = parser.parse_args()
repo = None
revisions = None

# test args values and get data
if args.tool:
    if args.tool not in tools_names:
        print("Unknown tool %s" % args.tool)
        sys.exit(1)
    tools = [t for t in tools if t.name == args.tool]

if args.path:
    REPO_PATH = os.path.realpath(args.path)
try:
    repo = Repo(REPO_PATH)
except git.exc.NoSuchPathError:
    print("Error: Path not a git repository: %s" % REPO_PATH)
    sys.exit(1)

LIVE = args.live

if args.output:
    OUTPUT = args.output

# get revisions to test
try:
    revisions = get_revisions(args.revisions)
except RevIsNotParent as ex:
    print("Error: %s" % str(ex))
    sys.exit(1)
except git.exc.BadName as ex:
    print("Error: %s" % str(ex))
    sys.exit(1)

try:
    if os.path.isdir(OUTPUT):
        shutil.rmtree(OUTPUT+'.bak', ignore_errors=True)
        shutil.move(OUTPUT, OUTPUT+'.bak')
    os.mkdir(OUTPUT)
except Exception as e:
    print("Can't create the output directory: %s" % str(e))
    sys.exit(1)

# run the tests
for revision in revisions:
    print("git checkout %s" % str(revision)[0:10])
    repo.head.reference = revision
    for tool in tools:
        print("Running %s..." % tool.name)
        try:
            tool.run(str(revision)[0:10])
        except ToolRuntimeError as e:
            print('Tool %s eded with an error: %s' %(tool.name, e))

print("All done, the output is saved in directory %s" % OUTPUT)
