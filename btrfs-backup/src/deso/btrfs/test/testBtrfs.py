# testBtrfs.py

#/***************************************************************************
# *   Copyright (C) 2014-2015 Daniel Mueller (deso@posteo.net)              *
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

"""Test btrfs wrapping functionality."""

from deso.btrfs.alias import (
  alias,
)
from deso.btrfs.command import (
  create,
  delete,
  deserialize,
  diff,
  serialize,
  snapshot,
  sync,
)
from deso.btrfs.test.btrfsTest import (
  BtrfsDevice,
  BtrfsSnapshotTestCase,
  BtrfsTestCase,
  make,
  Mount,
)
from deso.execute import (
  execute,
  pipeline,
)
from os.path import (
  isdir,
  isfile,
)
from unittest import (
  TestCase,
  main,
)


class TestBtrfsDevice(TestCase):
  """A test case for btrfs loop device related functionality."""
  def testBtrfsDeviceCreation(self):
    """Verify that we can create a btrfs formatted loop back device."""
    def testReadWrite(name, string):
      """Open a file, write something into it and read it back."""
      with open(mount.path(name), "w+") as handle:
        handle.write(string)
        handle.seek(0)
        self.assertEqual(handle.read(), string)

    with BtrfsDevice() as btrfs:
      with Mount(btrfs.device()) as mount:
        # We got the btrfs loop back device created and mounted
        # somewhere. Try creating a file, writing something to it, and
        # reading the data back to verify that everything actually
        # works.
        testReadWrite(mount.path("test.txt"), "testString98765")


class TestBtrfsSubvolume(BtrfsTestCase):
  """Test btrfs subvolume functionality."""
  def testBtrfsSubvolumeCreate(self):
    """Verify that we can create a btrfs subvolume."""
    # Create a subvolume and some files in it.
    with alias(self._mount) as m:
      execute(*create(m.path("root")))
      make(m, "root", "dir", "file", data=b"test")

      self.assertTrue(isdir(m.path("root")))
      self.assertTrue(isdir(m.path("root", "dir")))
      self.assertTrue(isfile(m.path("root", "dir", "file")))


  def testBtrfsSubvolumeDelete(self):
    """Verify that we can delete a btrfs subvolume."""
    with alias(self._mount) as m:
      execute(*create(m.path("root")))
      make(m, "root", "file", data=b"")
      self.assertTrue(isfile(m.path("root", "file")))
      execute(*delete(m.path("root")))

      self.assertFalse(isdir(m.path("root")))
      self.assertFalse(isfile(m.path("root", "file")))


  def testBtrfsSnapshot(self):
    """Verify that we can create a snapshot of a btrfs subvolume.

      Notes: We do not want to test all properties a snapshot provides
             here (for instance, that once snapshotted further changes
             in the original repository are not reflected in the
             snapshot), we trust that if we properly create a snapshot
             it will just have these properties.
    """
    with alias(self._mount) as m:
      data = b"test-string-to-read-from-snapshot"
      file_ = m.path("root_snapshot", "file")

      execute(*create(m.path("root")))
      make(m, "root", "file", data=data)

      execute(*snapshot(m.path("root"),
                        m.path("root_snapshot")))

      # Verify that the snapshot file and the original have the same
      # content.
      self.assertContains(file_, data.decode("utf-8"))


class TestBtrfsSnapshot(BtrfsSnapshotTestCase):
  """Test btrfs snapshot functionality."""
  def testBtrfsSnapshotReadOnly(self):
    """Verify that a created snapshot is read-only."""
    with alias(self._mount) as m:
      # Creating a new file in the read-only snapshot should raise
      # 'OSError: [Errno 30] Read-only file system'.
      regex = "Read-only file"
      with self.assertRaisesRegex(OSError, regex):
        make(m, "root_snapshot", "file2", data=b"")


  def testBtrfsSnapshotCreateWritable(self):
    """Verify that we can create a writable snapshot."""
    with alias(self._mount) as m:
      # Delete the original subvolume.
      execute(*delete(m.path("root")))
      # And recreate it from the snapshot.
      execute(*snapshot(m.path("root_snapshot"), m.path("root"), writable=True))
      # We must be able to write to the subvolume.
      make(m, "root", "file2", data=b"test-data")
      self.assertContains(m.path("root", "file2"), "test-data")


  def testBtrfsDiffCanUseArbitraryGeneration(self):
    """Verify that we are allowed to pass in an arbitrary generation to diff()."""
    # Because of a supposed bug in btrfs' find-new generation handling
    # we pass in a generation that is incremented once over the actual
    # generation of the snapshot. Since this generation might not
    # necessarily exist, this test case verifies that the program does
    # not report an error in such a case.
    with alias(self._mount) as m:
      execute(*diff(m.path("root"), "1337"))


  def testBtrfsSerializeAndDeserialize(self):
    """Test the serialization and deserialization functionality."""
    with alias(self._mount) as m:
      # The snapshot will manifest itself under the same name it was
      # created. So we need a sub-directory to contain it.
      make(m, "sent")
      # Make sure the snapshot is persisted to disk before serializing
      # it.
      execute(*sync(m.path()))
      pipeline([
        serialize(m.path("root_snapshot")),
        deserialize(m.path("sent"))
      ])

      self.assertTrue(isdir(m.path("sent", "root_snapshot")))
      self.assertTrue(isfile(m.path("sent", "root_snapshot", "file")))


  def testBtrfsSendToDifferentFileSystem(self):
    """Test sending a subvolume from one btrfs file system to another."""
    with BtrfsDevice() as btrfs:
      with Mount(btrfs.device()) as dst,\
           alias(self._mount) as src:
        self.assertFalse(isdir(dst.path("root_snapshot")))

        execute(*sync(src.path()))
        # Send the snapshot to the newly created btrfs file system and
        # deserialize it in its / directory.
        pipeline([
          serialize(src.path("root_snapshot")),
          deserialize(dst.path())
        ])

        self.assertTrue(isdir(dst.path("root_snapshot")))
        self.assertTrue(isfile(dst.path("root_snapshot", "file")))


if __name__ == "__main__":
  main()
