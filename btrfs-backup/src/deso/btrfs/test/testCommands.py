# testCommands.py

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

"""Test the commands functionality."""

from deso.btrfs.commands import (
  checkFileString,
  isSpring,
  replaceFileString,
)
from unittest import (
  main,
  TestCase,
)


class TestRepositoryBase(TestCase):
  """Test basic repository functionality."""
  def testSpringDetection(self):
    """Verify we can properly detect springs."""
    self.assertTrue(isSpring([["cat", "test"]]))
    self.assertTrue(isSpring([["cat", "test"], ["tr", "a", "b"]]))

    self.assertFalse(isSpring(["cat", "test"]))
    self.assertFalse(isSpring(["cat", "test1", "test2", "test3"]))


  def testCheckFileString(self):
    """Verify that the checkFileString function works as expected."""
    # Simple pipeline with {file} string.
    command = ["cat", "{file}"]
    self.assertTrue(checkFileString(command))

    # Simple pipeline, no {file} string.
    command = ["cat", "test"]
    self.assertFalse(checkFileString(command))

    # A spring with the {file} string in one command. Note that we
    # explicitly allow for this string to be not only in the first
    # command of the spring but any.
    command = [["cat", "test"], ["cat", "{file}"]]
    self.assertTrue(checkFileString(command))

    # A spring with no {file} string.
    command = [["cat", "test1"], ["cat", "test2"]]
    self.assertFalse(checkFileString(command))


  def testReplaceFileString(self):
    """Verify that the replaceFileString function works as expected."""
    self.assertFalse(replaceFileString(["cat"], ["test"]), None)
    self.assertFalse(replaceFileString(["cat", "-o"], ["test"]), None)

    command = ["cat", "{file}"]
    expected = ["cat", "test"]
    self.assertTrue(replaceFileString(command, ["test"]))
    self.assertEqual(command, expected)

    command = ["cat", "-o", "{file}", "-a", "test2"]
    expected = ["cat", "-o", "test", "-a", "test2"]
    self.assertTrue(replaceFileString(command, ["test"]))
    self.assertEqual(command, expected)

    command = ["cat", "--a-long-option={file}", "-a", "test2"]
    expected = ["cat", "--a-long-option=test", "-a", "test2"]
    self.assertTrue(replaceFileString(command, ["test"]))
    self.assertEqual(command, expected)

    command = ["cat", "--input={file}", "-a", "test3"]
    expected = ["cat", "--input=test1", "--input=test2", "-a", "test3"]
    self.assertTrue(replaceFileString(command, ["test1", "test2"]))
    self.assertEqual(command, expected)


if __name__ == "__main__":
  main()
