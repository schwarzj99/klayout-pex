#! /usr/bin/env python3
#
# --------------------------------------------------------------------------------
# SPDX-FileCopyrightText: 2024-2025 Martin Jan Köhler and Harald Pretl
# Johannes Kepler University, Institute for Integrated Circuits.
#
# This file is part of KPEX 
# (see https://github.com/iic-jku/klayout-pex).
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
# SPDX-License-Identifier: GPL-3.0-or-later
# --------------------------------------------------------------------------------
#
"""Replace symlinks below pdk/ with copies, so the built wheel carries them.

Run this once before `poetry build`. It is not a build hook on purpose:
declaring `[tool.poetry.build] script` makes poetry emit a platform wheel
(`cp3xx-...`) instead of `py3-none-any`.

Why it is needed: poetry-core resolves every included path and keys the set of
files to add on the result (`BuildIncludeFile.__init__` calls `path.resolve()`,
`__hash__` is the resolved path). A symlink therefore collapses onto its target,
which is already a member, and only one of the two names reaches the archive.
`pdk/ihp-sg13cmos5l/libs.tech/kpex/rule_decks/` consists of 47 such symlinks
into the ihp-sg13g2 deck directory, and none of them was shipped.

Git is the source of truth for what is a symlink, not the filesystem: with
`core.symlinks=false`, which is the default on Windows, a checkout writes them
as plain text files holding the target path. Those would otherwise be packaged
verbatim and the wheel would look complete while every deck was a one-line path.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

SYMLINK_MODE = '120000'
ROOT = 'pdk'


def tracked_symlinks(root: str) -> list[Path]:
    """Paths git records as symlinks, regardless of how they were checked out."""
    out = subprocess.run(['git', 'ls-files', '-s', '--', root],
                         capture_output=True, text=True, check=True).stdout
    paths = []
    for line in out.splitlines():
        meta, _, path = line.partition('\t')
        if meta.split()[0] == SYMLINK_MODE:
            paths.append(Path(path))
    return paths


def target_of(path: Path) -> Path:
    """The link target, read from the link itself or from its stand-in content."""
    link = os.readlink(path) if path.is_symlink() else path.read_text(encoding='utf-8').strip()
    return (path.parent / link).resolve()


def main() -> int:
    try:
        links = tracked_symlinks(ROOT)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f'{sys.argv[0]}: cannot ask git for tracked symlinks: {e}', file=sys.stderr)
        return 1

    if not links:
        print(f'{sys.argv[0]}: no symlinks tracked below {ROOT}/, nothing to do')
        return 0

    missing = []
    for path in links:
        target = target_of(path)
        if not target.is_file():
            missing.append((path, target))
            continue
        path.unlink()
        shutil.copy2(target, path)

    if missing:
        for path, target in missing:
            print(f'{sys.argv[0]}: {path} points at {target}, which does not exist',
                  file=sys.stderr)
        return 1

    print(f'{sys.argv[0]}: materialised {len(links)} symlinked files below {ROOT}/')
    return 0


if __name__ == '__main__':
    sys.exit(main())
