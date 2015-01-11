# testMain.py

#/***************************************************************************
# *   Copyright (C) 2015 Daniel Mueller (deso@posteo.net)                   *
# *                                                                         *
# *   This program is free software: you can redistribute it and/or modify  *
# *   it under the terms of the GNU General Public License as published by  *
# *   the Free Software Foundation, either version 3 of the License, or     *
# *   (at your option) any later version.                                   *
# *                                                                         *
# *   This program is distributed in the hope that it will be useful,       *
# *   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
# *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
# *   GNU General Public License for more details.                          *
# *                                                                         *
# *   You should have received a copy of the GNU General Public License     *
# *   along with this program.  If not, see <http://www.gnu.org/licenses/>. *
# ***************************************************************************/

"""Test the progam's main functionality."""

from deso.btrfs.alias import (
  alias,
)
from deso.btrfs.command import (
  create,
)
from deso.btrfs.main import (
  main as btrfsMain,
)
from deso.btrfs.test.btrfsTest import (
  BtrfsDevice,
  BtrfsTestCase,
  createDir,
  createFile,
  Mount,
)
from deso.execute import (
  execute,
)
from glob import (
  glob,
)
from os.path import (
  isfile,
)
from sys import (
  argv,
)
from unittest import (
  main,
)


class TestMain(BtrfsTestCase):
  """A test case for testing of the progam's main functionality."""
  def testRun(self):
    """Test a simple run of the program with two subvolumes."""
    with alias(self._mount) as m:
      # We backup our data to a different btrfs volume.
      with BtrfsDevice() as btrfs:
        with Mount(btrfs.device()) as b:
          subvolumes = [
            m.path("home", "user"),
            m.path("root"),
          ]
          createDir(m.path("snapshots"))
          createDir(m.path("home"))
          createDir(b.path("backup"))

          for subvolume in subvolumes:
            execute(*create(subvolume))

          createDir(m.path("home", "user", "data"))
          createFile(m.path("home", "user", "data", "movie.mp4"), b"abcdefgh")
          createDir(m.path("root", ".ssh"))
          createFile(m.path("root", ".ssh", "key.pub"), b"1234567890")

          args = "-s {user} --subvolume {root} {src} {dst}"
          args = args.format(user=m.path("home", "user"),
                             root=m.path("root"),
                             src=m.path("snapshots"),
                             dst=b.path("backup"))
          result = btrfsMain([argv[0]] + args.split())
          self.assertEqual(result, 0)

          user, root = glob(b.path("backup", "*"))

          self.assertTrue(isfile(m.path(user, "data", "movie.mp4")))
          self.assertTrue(isfile(m.path(root, ".ssh", "key.pub")))


if __name__ == "__main__":
  main()
