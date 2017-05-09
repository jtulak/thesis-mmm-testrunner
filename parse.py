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
import json

from lib import *

RES_PATH = os.path.join(
        os.path.realpath(os.path.dirname(__file__)),
        '../tex/results/output/')

CHECK_FOR_MKFS_ONLY = True


class Categories(Enum):
    UNKNOWN = 0
    STYLE = 1
    ERROR = 2
    SECURITY = 3

class Issue(object):
    def __init__(self, file, line, category, text, custom_hash=""):
        """
            custom_hash is for special cases like coverity, which has
            solved the cross-revision trackability for us, and we can
            uniquely identify the issue at any revision.
        """

        if not isinstance(category, Categories):
            raise Exception("Unknown category, not member of Categories enum: %s"
                    % str(category))

        self._file = file
        self._line = int(line)
        self._category = category
        self._text = text
        self.index = 0
        self._hash = custom_hash

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

    @property
    def custom_hash(self):
        return self._hash

    def extendText(self, text):
        self._text += "\n"+text

    def __eq__(self, issue):
        """ Return True if the given issue is the same,
            as this one. Line number can differ, because the offending
            piece of code could move between revisions.
        """
        if self.custom_hash and issue.custom_hash:
            return self.custom_hash == issue.custom_hash
        else:
            return self.file == issue.file \
                and self.category == issue.category \
                and self.text == self.text

    def __hash__(self):
        #return hash(self.__repr__())
        return hash((
                self.file,
                self.category.name,
                self.text,
                self.index,
                self._hash))


    def __str__(self):
        if len(self._hash):
            return '%s:%d (%s)\n %s\n Hash is: %s' % (
                    self.file,
                    self.line,
                    self.category.name,
                    self.text,
                    self._hash)
        else:
            return '%s:%d (%s)\n %s' % (
                    self.file,
                    self.line,
                    self.category.name,
                    self.text)

    def __repr__(self):
        if len(self._hash):
            return '<Issue %s:%d (%s) %s, hash %s>' % (
                    self.file,
                    self.line,
                    self.category,
                    self.text,
                    self._hash)
        else:
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
    _issues = None

    lastIssue = None

    def __init__(self, resultsdir):
        """ resultsdir is the directory with all commits-dirs """
        self.resultsdir = resultsdir
        self.compile()
        self._issues = dict()

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
            self._issues[revision] = set()

        # so we can have multiple issues with the same description
        # in the same file
        while issue in self._issues[revision]:
            issue.index +=1

        self._issues[revision].add(issue)
        self.lastIssue = issue

    def get_all_issues(self, revision):
        try:
            for issue in self._issues[revision]:
                yield issue
        except KeyError:
            return None

    def get_issues(self, revision, file):
        try:
            for issue in self._issues[revision]:
                if issue.file != file:
                    continue
                yield issue
        except KeyError:
            return None

    def get_diff(self, older, newer):
        """ Return a tuple (added, removed) with lists of issues
            changed between the two revisions.
        """
        issuesO = set(self._issues[older])
        issuesN = set(self._issues[newer])

        added = issuesN-issuesO
        removed = issuesO - issuesN
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

    DIR=1
    FILE=2
    LINE=3
    CATEGORY=4
    TEXT=5

    def compile(self):
        self.re = re.compile('^\[([^:]+)/([^:/]+):([0-9]+)\]: \(([^)]+)\) (.*)$')

    def get_category(self, string):
        if string == "style":
            return Categories.STYLE
        else:
            return Categories.ERROR

    def parse(self, line):
        """ CppCheck has a simple, single-line format of issues:
            [FILE:LINE]: (TYPE) text
        """
        try:
            if line[0] != '[':
                # certainly it is not an issue
                return None

            matches = self.re.match(line)

            if CHECK_FOR_MKFS_ONLY and matches.group(self.DIR)[-4:] != "mkfs":
                return None

            return Issue(
                    file=matches.group(self.DIR)+matches.group(self.FILE),
                    line=matches.group(self.LINE),
                    category = self.get_category(matches.group(self.CATEGORY)),
                    text = matches.group(self.TEXT))
        except:
            return None



class Clang(Parser):
    _filename = "Clang.log.cut"
    _buffer = []

    parsed = 0
    def compile(self):
        """ Example of the line we are parsing:
        copy/xfs_copy.c:144:40: warning: unused parameter 'log' [-Wunused-parameter]
        The groups are defined.
        """
        self.re1 = re.compile('^([^/]+)/([^:]+):([0-9]+):([0-9]+): ([^:]+): (.+) \[([^][]+)\]$')
        self.re2 = re.compile('^([^/]+)/([^:]+):([0-9]+):([0-9]+): ([^:]+): (.+)$')
        self.DIR = 1
        self.FILE = 2
        self.LINE = 3
        self.COLUMN = 4
        self.TYPE = 5
        self.TEXT = 6
        self.FLAG = 7

    def get_issue_type(self, line0, match):
        #txt = line0[7:-1]
        #if txt == "CLANG_WARNING" or txt == "COMPILER_WARNING":
        try:
            flag = match.group(self.FLAG)
            ret = {
                # style
                '-Wdiscarded-qualifiers': Categories.STYLE,
                '-Wshadow': Categories.STYLE,
                '-Wunused-parameter': Categories.STYLE,
                '-Wpointer-arith': Categories.STYLE,
                '-Wunused-but-set-variable': Categories.STYLE,
                '-Wstrict-prototypes': Categories.STYLE,
                '-Wempty-body': Categories.STYLE,
                '-Wmissing-field-initializers': Categories.STYLE,
                '-Wtype-limits': Categories.STYLE,
                '-Wshift-negative-value': Categories.STYLE,
                '-Wsign-compare': Categories.STYLE,
                '-Wincompatible-pointer-types-discards-qualifiers': Categories.STYLE,
                '-Wcast-align': Categories.STYLE,
                '-Wformat-nonliteral': Categories.STYLE,
                # errors
                '-Wfloat-equal': Categories.ERROR,
                }
            if flag in ret:
                return ret[flag]
            else:
                print("Unknown type of issue:\n%s" % match.group(0))
                return Categories.UNKNOWN
        except IndexError:
            # this is without flag
            #print("No flag: %s" % match.group(self.TEXT))
            pass
        return Categories.UNKNOWN

    def parse_buffer(self):
        # match can be on either line 1 or one of the following ones,
        # depending on if it is the first issue in a specific function or not
        # and depending on some includes.

        line = 0
        match = None
        try:
            while match is None:
                line += 1
                match = self.re1.match(self._buffer[line])
        except IndexError:
            # nothing was found until the end
            line = 0
            while match is None:
                line += 1
                match = self.re2.match(self._buffer[line])

        # do we want only mkfs files?
        if CHECK_FOR_MKFS_ONLY and match.group(self.DIR) != "mkfs":
            return None

        issue_type = self.get_issue_type(self._buffer[0], match)
        return Issue(file=match.group(self.DIR)+'/'+match.group(self.FILE),
                line=match.group(self.LINE),
                category=issue_type,
                text=match.group(self.TEXT))


    def parse(self, line):
        """ We have multiline outputs here, so we have to save the lines
            into a buffer one by one and when there is just a newline,
            then we can decide, because we filled one issue into the
            buffer.
        """
        self.parsed += 1
        if line == "CURRENT DEFECTS" or line == "===============":
            return None

        if len(line):
            # line is not empty, so it is still one issue,
            # just add it to buffer
            self._buffer.append(line)
            return None

        # the current line was empty, so we found the end of the issue
        try:
            issue = self.parse_buffer()
            self._buffer = []
            return issue
        except IndexError:
            # caused by multiple newlines in a row
            self._buffer = []
            return None

class GCC(Clang):
    _filename = "GCC.log.cut"

class Coverity(Parser):
    _filename = "cov.output/%s/json"

    class Levels(Enum):
        LOW = 1
        MEDIUM = 2
        HIGH = 3
        CUSTOM = 4
    _level = Levels.HIGH

    @classmethod
    def level(cls, lvl = None):
        if lvl is None:
            return cls._level
        else:
            if cls.level_valid(lvl):
                cls._level = list(cls.Levels)[cls.levels_list().index(lvl)]
            else:
                raise ValueError("Unknown Coverity level %s" % lvl)

    @classmethod
    def level_valid(self, lvl):
        if lvl in self.levels_list():
            return True
        else:
            return False

    @staticmethod
    def enum_to_str(enum):
        return str(enum).split('.')[1].lower()

    @classmethod
    def levels_list(cls):
        return list(map(cls.enum_to_str,cls.Levels))

    def _get_path(self, revision):
        return os.path.join(self.resultsdir,
                revision,
                self._filename % self.enum_to_str(self.level()))

    def compile(self):
        pass

    def get_type(self, issue):
        # select the last item from the list
        kind = issue['checkerProperties']['issueKinds'][-1]
        if kind == 'QUALITY':
            return Categories.STYLE
        elif kind == 'SECURITY':
            return Categories.SECURITY
        return Categories.UNKNOWN


    def run(self, revision):
        """ Coverity produces JSON and because we don't need the regular line-by-line
            parsing as for the other tools, implement custom run().
        """
        issues = None
        with open(self._get_path(revision)) as data_file:
            data = json.load(data_file)
            issues = data['issues']

        i = 0
        for issue in issues:
            #self.parse_events_tree(revision, issue, issue['events'])
            main = None
            for event in issue['events']:
                if event['main']:
                    main = event
                    # get the directory and file
            d,f = main['filePathname'].split('/')[-2:]
            if CHECK_FOR_MKFS_ONLY and d[-4:] != "mkfs":
                continue

            self.add_issue(revision, Issue(
                file = os.path.join(d,f),
                line = main['lineNumber'],
                category = self.get_type(issue),
                text = main['eventDescription'],
                custom_hash = issue['mergeKey'],
            ))


# ------------------------------------------------
#   main
#
tools = [GCC, Clang, CppCheck, CPAChecker, Coverity]
tools_names = [t.__name__ for t in tools]

parser = argparse.ArgumentParser(description='Iterate over results and print results.')
parser.add_argument('revisions', metavar='REVISION', type=str, nargs='+',
                help='Git hash for revisions. Git range is accepted too.')
parser.add_argument('-c', '--clevel', metavar='LEVEL', type=str,
        help='Level of Coverity analysis. Default is %s. '
                     'Supported levels: %s' %(
                        Coverity.enum_to_str(Coverity.level()),
                        ', '.join(Coverity.levels_list())))
parser.add_argument('--tool', metavar='TOOL', type=str,
                help='One of the supported tools. If ommited, all are run. '
                     'Supported tools: %s' % ', '.join(tools_names))
parser.add_argument('--gitpath', metavar='PATH', type=str,
                help='Path to the repo.')
parser.add_argument('--respath', metavar='PATH', type=str,
                help='Path to the results directory.')
parser.add_argument('-d', '--diff', action='store_true',
                help='Print only the differences between two following revisions.')
parser.add_argument('-a', '--all', action='store_true',
                help='Do not check only for mkfs, but for whole xfsprogs.')

args = parser.parse_args()
repo = None
revisions = None

if args.all:
    CHECK_FOR_MKFS_ONLY = False

if args.clevel:
    try:
        Coverity.level(args.clevel)
    except ValueError:
        print("Invalid Coverity level %s. Accepted levels are: %s" %
                (args.clevel,', '.join(Coverity.levels_list())))
        sys.exit(1)


# test args values and get data
if args.tool:
    if args.tool not in tools_names:
        print("Unknown tool %s" % args.tool)
        sys.exit(1)
    tools = [t for t in tools if t.__name__ == args.tool]
    if args.tool != "Coverity" and args.clevel:
        print("Option --clevel is ignored, because Coverity is not parsed.")

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
