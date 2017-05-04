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
import argparse
from git import repo
import git
from enum import Enum

from lib import *

RES_PATH = os.path.join(
        os.path.realpath(os.path.dirname(__file__)),
        '../tex/results/output/')


class Categories(Enum):
    STYLE = 1
    ERROR = 2
    SECURITY = 3

class Issue(object):
    def __init__(self, file, line, category, text):

        if not isinstance(category, Categories):
            raise Exception("Unknown category, not member of Categories enum: %s"
                    % str(category))

        self._file = file
        self._line = int(line)
        self._category = category
        self._text = text

    @property
    def line(self):
        return self._line

    @property
    def category(self):
        return self._category

    @property
    def text(self):
        return self._text

    @property
    def file(self):
        return self._file

    def __eq__(self, issue):
        """ Return True if the given issue is the same,
            as this one. Line number can differ, because the offending
            piece of code could move between revisions.
        """
        return self.file == issue.file \
            and self.category == issue.category \
            and self.text == self.text


    def __str__(self):
        return '%s:%d (%s)\n %s' % (
                self.file,
                self.line,
                self.category.name,
                self.text)
    def __repr__(self):
        return '<Issue %s:%d (%s) %s>' % (
                self.file,
                self.line,
                self.category,
                self.text)

def print_issues(l):
    count = 0
    for i in l:
        count += 1
        print("%s\n" % str(i))
    print("Total: %d\n"%count)

class Parser(object):
    """ A generic parser for all tools """
    _filename = None
    _issues = {}

    def __init__(self, resultsdir):
        """ resultsdir is the directory with all commits-dirs """
        self.resultsdir = resultsdir
        self.compile()

    def _get_path(self, revision):
        if self._filename is None:
            raise NotImplementedError()
        return os.path.join(self.resultsdir, revision, self._filename)

    def _open_file(self, revision):
        return open(self._get_path(revision), 'r')

    def read_lines(self, revision):
        with self._open_file(revision) as f:
            for line in f.readlines():
                yield line.strip()

    def run(self, revision):
        for line in self.read_lines(revision):
            issue = self.parse(line)
            if issue is None:
                continue
            self.add_issue(revision, issue)

    def add_issue(self, revision, issue):
        if not revision in self._issues:
            self._issues[revision] = list()
        self._issues[revision].append(issue)

    def get_all_issues(self, revision):
        for issue in self._issues[revision]:
            yield issue

    def get_issues(self, revision, file):
        for issue in self._issues[revision]:
            if issue.file != file:
                continue
            yield issue

    def get_diff(self, older, newer):
        """ Return a tuple (added, removed) with lists of issues
            changed between the two revisions.
        """
        issuesO = self._issues[older]
        issuesN = self._issues[newer]

        added = issuesN[:]
        removed = issuesO[:]

        # TODO how to do the diff, while keeping an eye
        # on multiple occurences of the same issue?
        return (added,removed)

    def compile(self):
        """ Compile all regular expressions on __init__.
            Has to be implemented in every subclass.
        """
        raise NotImplementedError()

    def parse(self, line):
        """ Parse the line and create an issue out of it,
            or None if not an issue.
            Has to be implemented in every subclass.
        """
        raise NotImplementedError()



class CPAChecker(Parser):
    _filename = "cpacheck.log"

class CppCheck(Parser):
    _filename = "CppCheck.log"

    def compile(self):
        self.re = re.compile('^\[([^:]+):([0-9]+)\]: \(([^)]+)\) (.*)$')

    def get_category(self, string):
        if string == "style":
            return Categories.STYLE
        else:
            return Categories.ERROR

    def parse(self, line):
        """ CppCheck has a simple, single-line format of issues:
            [FILE:LINE]: (TYPE) text
        """
        if line[0] != '[':
            # certainly it is not an issue
            return None

        matches = self.re.match(line)
        return Issue(
                file=matches.group(1),
                line=matches.group(2),
                category = self.get_category(matches.group(3)),
                text = matches.group(4))



class GCC(Parser):
    _filename = "GCC.log"

class Coverity(Parser):
    _filename = "Coverity.log"
    _dirname = "cov.output"

# ------------------------------------------------
#   main
#
tools = [GCC, CppCheck, CPAChecker, Coverity]
tools_names = [t.__name__ for t in tools]
parser = argparse.ArgumentParser(description='Iterate over results and print results.')
parser.add_argument('revisions', metavar='REVISION', type=str, nargs='+',
                help='Git hash for revisions. Git range is accepted too.')
parser.add_argument('--tool', metavar='TOOL', type=str,
                help='One of the supported tools. If ommited, all are run. '
                     'Supported tools: %s' % ', '.join(tools_names))
parser.add_argument('--gitpath', metavar='PATH', type=str,
                help='Path to the repo.')
parser.add_argument('--respath', metavar='PATH', type=str,
                help='Path to the results directory.')
parser.add_argument('-d', '--diff', action='store_true',
                help='Print only the differences between two following revisions.')

args = parser.parse_args()
repo = None
revisions = None

# test args values and get data
if args.tool:
    if args.tool not in tools_names:
        print("Unknown tool %s" % args.tool)
        sys.exit(1)
    tools = [t for t in tools if t.__name__ == args.tool]

repo = get_repo_or_die(args.gitpath)
revisions = get_revisions_or_die(repo, args.revisions)

if args.respath:
    RES_PATH = args.respath

# run the parsers
for tool_cls in tools:
    print("### Tool %s" % tool_cls.__name__)
    tool = tool_cls(RES_PATH)

    for i,revision in enumerate(revisions):
        short = str(revision)[0:10]
        print("## Revision %s:\n" % short)
        tool.run(short)

        diff = args.diff
        if i == 0:
            diff = False

        if diff:
            added, removed = tool.get_diff(
                str(revisions[i-1])[0:10],
                short)
            print("# Added:")
            print_issues(added)
            print("# Removed:")
            print_issues(removed)
        else:
            # we don't want or can't print a diff
            print_issues(tool.get_all_issues(short))
