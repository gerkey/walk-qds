import argparse
import collections
import re
import os
import sys

import lxml.etree


class QD:
    def __init__(self, package, depth):
        self.package = package
        self.depth = depth


class Package:
    def __init__(self, name, qd_path, lxml_tree):
        self.name = name
        self.qd_path = qd_path
        self.lxml_tree = lxml_tree

    def __eq__(self, other):
        return self.name == other

    def __repr__(self):
        return self.name


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--recurse', help='Whether to recursively find QDs for all dependencies', action='store_true', default=False)
    parser.add_argument('source_path', help='The top-level of the source tree in which to find package and dependencies', action='store')
    parser.add_argument('package', help='The top-level package for which to find Quality level of dependencies', action='store')
    args = parser.parse_args()

    source_path = args.source_path
    package_to_examine = args.package

    # First we walk the source repository, finding all of the packages and
    # storing their relative paths.  This saves us from having to do multiple
    # walks of the filesystem later.
    package_name_to_package = {}
    for (dirpath, dirnames, filenames) in os.walk(source_path):
        if 'package.xml' in filenames:
            tree = lxml.etree.parse(os.path.join(dirpath, 'package.xml'))
            for child in tree.getroot().getchildren():
                if child.tag == 'name':
                    package_name_to_package[child.text] = Package(child.text, os.path.join(dirpath, 'QUALITY_DECLARATION.md'), tree)
                    break

    if not package_to_examine in package_name_to_package:
        print("Could not find package to examine '%s'" % (package_to_examine))
        return 2

    packages_to_examine = collections.deque([package_to_examine])
    deps_found = collections.OrderedDict()
    deps_found[package_to_examine] = QD(package_name_to_package[package_to_examine], 0)
    deps_not_found = set()
    depth = 0
    while packages_to_examine:
        package = package_name_to_package[packages_to_examine.popleft()]
        deps = []
        for child in package.lxml_tree.getroot().getchildren():
            if child.tag in ['depend', 'build_depend']:
                deps.append(child.text)

        for dep in deps:
            if dep in deps_found:
                continue

            if dep in package_name_to_package:
                qd = QD(package_name_to_package[dep], deps_found[package.name].depth + 1)
                deps_found[dep] = qd
                if args.recurse:
                    packages_to_examine.append(dep)
            else:
                deps_not_found.add(dep)

    if deps_not_found:
        print("WARNING: Could not find packages '%s', not recursing" % (', '.join(deps_not_found)))

    quality_level_re = re.compile('.*claims to be in the \*\*Quality Level ([1-5])\*\*')
    dep_to_quality_level = collections.OrderedDict()
    for dep,qd in deps_found.items():
        if not os.path.exists(qd.package.qd_path):
            print("WARNING: Could not find quality declaration for package '%s', skipping" % (package.name))
            continue
        with open(qd.package.qd_path, 'r') as infp:
            for line in infp:
                match = re.match(quality_level_re, line)
                if match is None:
                    continue
                groups = match.groups()
                if len(groups) != 1:
                    continue
                dep_to_quality_level[qd.package.name] = (int(groups[0]), qd.depth)

    for dep,quality in dep_to_quality_level.items():
        print('%s%s: %d' % ('  ' * quality[1], dep, quality[0]))

    return 0

if __name__ == '__main__':
    sys.exit(main())