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
  _replaceFileStringInCommand,
  _replaceFileStringInSpring,
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


  def testReplaceFileStringInCommand(self):
    """Verify that the _replaceFileStringInCommand function works as expected."""
    self.assertFalse(_replaceFileStringInCommand(["cat"], ["test"]), None)
    self.assertFalse(_replaceFileStringInCommand(["cat", "-o"], ["test"]), None)

    command = ["cat", "{file}"]
    expected = ["cat", "test"]
    self.assertTrue(_replaceFileStringInCommand(command, ["test"]))
    self.assertEqual(command, expected)

    command = ["cat", "-o", "{file}", "-a", "test2"]
    expected = ["cat", "-o", "test", "-a", "test2"]
    self.assertTrue(_replaceFileStringInCommand(command, ["test"]))
    self.assertEqual(command, expected)

    command = ["cat", "--a-long-option={file}", "-a", "test2"]
    expected = ["cat", "--a-long-option=test", "-a", "test2"]
    self.assertTrue(_replaceFileStringInCommand(command, ["test"]))
    self.assertEqual(command, expected)

    command = ["cat", "--input={file}", "-a", "test3"]
    expected = ["cat", "--input=test1", "--input=test2", "-a", "test3"]
    self.assertTrue(_replaceFileStringInCommand(command, ["test1", "test2"]))
    self.assertEqual(command, expected)


  def testReplaceFileStringInSpring(self):
    """Verify that the _replaceFileStringInSpring function works as expected."""
    commands = [["cat", "test"]]
    self.assertFalse(_replaceFileStringInSpring(commands, ["test"]))

    commands = [["cat", "-o", "test"]]
    self.assertFalse(_replaceFileStringInSpring(commands, ["test"]))

    commands = [["cat", "{file}"]]
    expected = [["cat", "test"]]
    self.assertTrue(_replaceFileStringInSpring(commands, ["test"]))
    self.assertEqual(commands, expected)

    commands = [["cat", "-o", "{file}", "-a", "test2"]]
    expected = [
      ["cat", "-o", "test1", "-a", "test2"],
      ["cat", "-o", "test2", "-a", "test2"],
      ["cat", "-o", "test3", "-a", "test2"],
    ]
    files = ["test1", "test2", "test3"]
    self.assertTrue(_replaceFileStringInSpring(commands, files))
    self.assertEqual(commands, expected)

    commands = [["cat", "--a-long-option={file}"]]
    expected = [
      ["cat", "--a-long-option=1"],
      ["cat", "--a-long-option=2"],
      ["cat", "--a-long-option=42"],
    ]
    self.assertTrue(_replaceFileStringInSpring(commands, ["1", "2", "42"]))
    self.assertEqual(commands, expected)

    # We also allow command other than the first to contain the {file}
    # string.
    commands = [["cat", "test"], ["cat", "--a-long-option={file}"]]
    expected = [
      ["cat", "test"],
      ["cat", "--a-long-option=1"],
      ["cat", "--a-long-option=2"],
      ["cat", "--a-long-option=42"],
    ]
    self.assertTrue(_replaceFileStringInSpring(commands, ["1", "2", "42"]))
    self.assertEqual(commands, expected)


  def testReplaceFileStringSuccess(self):
    """Verify that the replaceFileString function works as expected."""
    # Test the function with a "normal" command.
    command = ["cat", "{file}"]
    expected = ["cat", "test"]
    self.assertEqual(replaceFileString(command, ["test"]), expected)

    # Test the function with a spring.
    command = [["cat", "{file}"], ["echo", "success"]]
    expected = [["cat", "test"], ["echo", "success"]]
    self.assertEqual(replaceFileString(command, ["test"]), expected)


  def testReplaceFileStringFailure(self):
    """Verify that the replaceFileString function throws correct errors."""
    regex = r"Replacement string.*in: \"%s\"$"
    command = [
      ["cat", "test1"],
      ["cat", "test2"],
    ]
    with self.assertRaisesRegex(NameError, regex % "cat test1 | cat test2"):
      replaceFileString(command, ["test"])

    command = ["echo", "data"]
    with self.assertRaisesRegex(NameError, regex % "echo data"):
      replaceFileString(command, ["test"])


if __name__ == "__main__":
  main()
