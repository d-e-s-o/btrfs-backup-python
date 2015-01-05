# testRepository.py

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

"""Test the repository functionality."""

from deso.btrfs.alias import (
  alias,
)
from deso.btrfs.command import (
  create,
  snapshot,
)
from deso.btrfs.repository import (
  Repository,
  _findRoot,
  _snapshots,
)
from deso.btrfs.test.btrfsTest import (
  BtrfsRepositoryTestCase,
  BtrfsSnapshotTestCase,
  BtrfsTestCase,
  createDir,
  createFile,
)
from deso.execute import (
  execute,
)
from os import (
  remove,
)
from os.path import (
  isfile,
  join,
)
from unittest import (
  main,
)


class TestRepositoryBase(BtrfsTestCase):
  """Test basic repository functionality."""
  def testRepositoryListNoSnapshotPresent(self):
    """Verify that if no snapshot is present an empty list is returned."""
    repo = Repository(self._mount.path())
    self.assertEqual(repo.snapshots(), [])


  def testRepositorySubvolumeFindRootOnRoot(self):
    """Test retrieval of the absolute path of the btrfs root from the root."""
    with alias(self._mount) as m:
      self.assertEqual(_findRoot(m.path()), m.path())


  def testRepositorySubvolumeFindRootFromBelowRoot(self):
    """Test retrieval of the absolute path of the btrfs root from a sub-directory."""
    with alias(self._mount) as m:
      subdirectory = m.path("dir")
      createDir(subdirectory)
      self.assertEqual(_findRoot(subdirectory), m.path())


  def testRepositorySubvolumeFindRootFromSubvolume(self):
    """Test retrieval of the absolute path of the btrfs root from a true subvolume."""
    with alias(self._mount) as m:
      execute(*create(m.path("root")))
      self.assertEqual(_findRoot(m.path("root")), m.path())


class TestRepositorySnapshots(BtrfsSnapshotTestCase):
  """Test snapshot related repository functionality."""
  def testRepositoryListNoSnapshotPresentInSubdir(self):
    """Verify that if no snapshot is present in a directory an empty list is returned."""
    with alias(self._mount) as m:
      # Create a new sub-directory where no snapshots are present.
      createDir(m.path("dir"))
      # TODO: The assertion should really be assertEqual! I consider
      #       this behavior a bug because we pass in the -o option to
      #       the list command which is promoted as: "print only
      #       subvolumes below specified path".
      #       There is no subvolume below the given path, so reporting a
      #       snapshot here is wrong.
      self.assertNotEqual(_snapshots(m.path("dir")), [])


  def testRepositoryListOnlySnapshotsInRepository(self):
    """Verify that listing snapshots in a repository not in the btrfs root works."""
    with alias(self._mount) as m:
      createDir(m.path("repository"))

      execute(*snapshot(m.path("root"),
                        m.path("root_snapshot2")))
      execute(*snapshot(m.path("root"),
                        m.path("repository", "root_snapshot3")))
      execute(*snapshot(m.path("root"),
                        m.path("repository", "root_snapshot4")))

      repo = Repository(m.path("repository"))
      # Only snapshots in the repository must occur in the list.
      snap1, snap2 = repo.snapshots()

      self.assertEqual(snap1["path"], "root_snapshot3")
      self.assertEqual(snap2["path"], "root_snapshot4")


class TestRepository(BtrfsRepositoryTestCase):
  """Test repository functionality."""
  def testRepositoryListSnapshots(self):
    """Verify that we can list a single snapshot and parse it correctly."""
    snap, = self._repository.snapshots()

    # We cannot tell the generation number with 100% certainty because
    # slight differences in the implementation could change it. So just
    # compare the reported path for now.
    self.assertEqual(snap["path"], "root_snapshot")
    self.assertTrue("gen" in snap)


  def testRepositoryListMultipleSnapshots(self):
    """Verify that we can list multiple snapshots and parse them correctly."""
    with alias(self._repository) as r:
      execute(*snapshot(r.path("root"),
                        r.path("root_snapshot2")))

      snap1, snap2 = r.snapshots()

    self.assertEqual(snap1["path"], "root_snapshot")
    self.assertEqual(snap2["path"], "root_snapshot2")


  def testRepositoryEmptyDiff(self):
    """Verify that an empty diff is reported on a fresh snapshot."""
    with alias(self._repository) as r:
      self.assertEqual(r.diff("root_snapshot", r.path("root")), [])


  def testRepositoryEmptyFileNotInDiff(self):
    """Check whether a newly created empty file is reported by diff().

      The find-new functionality provided by btrfs apparently does not
      catch cases where an empty file is created in a subvolume after a
      snapshot was taken. This test checks for this property. Note that
      this property is *not* favorable for the usage of find-new in this
      program. This test case is meant to raise awareness for this
      issue.
    """
    with alias(self._repository) as r:
      createFile(r.path("root", "file2"))
      createFile(r.path("root", "file3"))
      createFile(r.path("root", "file4"))

      self.assertEqual(r.diff("root_snapshot", r.path("root")), [])
      self.assertTrue(isfile(r.path("root", "file2")))


  def testRepositoryDiff(self):
    """Verify that we can retrieve a list of changed files for a subvolume."""
    with alias(self._repository) as r:
      file1 = r.path("root", "file")
      dir1 = r.path("root", "dir")
      file2 = r.path("root", "dir", "file2")

      # Write something into the existing file to have it contain
      # changes over the snapshot.
      with open(file1, "w") as f:
        f.write("\0")

      # Also create a new file with some content.
      createDir(dir1)
      createFile(file2, b"test-data")

      files = r.diff("root_snapshot", r.path("root"))
      # We cannot tell for sure the order in which the files appear so use
      # a set here.
      expected = {"file", join("dir", "file2")}

      self.assertEqual(set(files), expected)


  def testRepositoryDiffDeletion(self):
    """Check whether deleted files in a subvolume are reported by diff().

      This test case checks that files that are present in a snapshot
      but got deleted in the associated subvolume are not reported by
      diff(). This test's purpose is more to show case and create
      awareness of this behavior than to actually verify that this
      property is really enforced.
    """
    with alias(self._repository) as r:
      remove(r.path("root", "file"))

      self.assertEqual(r.diff("root_snapshot", r.path("root")), [])


if __name__ == "__main__":
  main()
