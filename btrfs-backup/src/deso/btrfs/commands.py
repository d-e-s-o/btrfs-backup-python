# commands.py

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

"""Functionality related to handling commands in various forms."""

from copy import (
  deepcopy,
)
from deso.execute import (
  formatCommands,
)


def isSpring(command):
  """Check if a command array actually describes a spring."""
  return isinstance(command[0], list)


def _checkFileStringInSpring(commands):
  """Check if the given spring contains the "{file}" string."""
  # We explicitly check all commands in the spring because we allow
  # commands other than the first to contain the {file} string.
  for command in commands:
    if _checkFileStringInCommand(command):
      return True

  return False


def _checkFileStringInCommand(command):
  """Check if the given command contains the "{file}" string."""
  # There are different ways the {file} string can be provided which
  # depend on the command used. It might be part of a short option, a
  # long option, or it can be a stand alone argument. We do not care
  # as long as it does exist and so just create a string out of the
  # respective filter command and scan it instead of inspecting every
  # single argument of the command.
  return "{file}" in " ".join(command)


def checkFileString(command):
  """Check if the given command contains the "{file}" string."""
  if isSpring(command):
    return _checkFileStringInSpring(command)
  else:
    return _checkFileStringInCommand(command)


def _replaceFileStringInSpring(commands, files):
  """Replace the {file} string in a spring with the actual file name(s)."""
  def replicate(command, file_):
    """Replicate and command containing a {file} string and replace it with the actual file."""
    replica = deepcopy(command)
    result = _replaceFileStringInCommand(replica, [file_])
    assert result, replica
    return replica

  assert isSpring(commands), commands

  # Note that we do not insist here on the {file} string being located
  # in the first command of the spring. Not sure about use cases where
  # it would not be there but we leave that open to users.
  for i, command in enumerate(commands):
    if "{file}" in " ".join(command):
      # For a spring we replicate the entire command containing the
      # '{file}' string (as opposed to the option associated with it, if
      # any) and insert a duplicate into the list of commands.
      commands[i:i+1] = [replicate(command, f) for f in files]
      return True

  return False


def _replaceFileStringInCommand(command, files):
  """Replace the {file} string in a command with the actual file name(s)."""
  # TODO: This function replicates the argument that contains the {file}
  #       string to allow not only for lists of snapshot files in a
  #       consecutive fashion (i.e., "/bin/cat {file}" is expanded to
  #       "/bin/cat file1 file2 ...") but also for multiple options
  #       ("/bin/dd if={file}" is expanded to "/bin/dd if=file1 if=file2
  #       ...". However, because of the one argument assumption, this
  #       function cannot handle short options where there is a space
  #       between the argument and its parameter since they would appear
  #       as different arguments altogether (that is, "/bin/tar -f
  #       {file}" would be supplied as ['/bin/tar', '-f', '{file}'] and
  #       the fact that the {file} string belongs to the -f option is
  #       lost to the function. As of now this limitation is not a
  #       problem because of a lack of programs using this style of
  #       argument passing. It might become one, though.
  for i, arg in enumerate(command):
    # Check if the argument contains the replacement string {file}. If
    # it does, then replicate it for each snapshot while replacing the
    # string with its actual name.
    if "{file}" in arg:
      # Replace the current argument with the list of arguments with
      # all the file names.
      command[i:i+1] = [arg.format(file=f) for f in files]
      return True

  return False


def replaceFileString(command, files):
  """Replace the {file} string in a command with the actual snapshot name.

    Note: Any replacement is performed on the actual data, i.e., without
          making a copy beforehand.
  """
  def raiseError(commands):
    """Raise an error telling the user that no {file} string was found."""
    error = "Replacement string {{file}} not found in: \"{cmd}\""
    error = error.format(cmd=formatCommands(commands))
    raise NameError(error)

  assert isinstance(files, list), files

  # The command might actually be a list of commands in case of a
  # spring. In that case our replacement looks slightly different.
  if isSpring(command):
    if not _replaceFileStringInSpring(command, files):
      raiseError(command)
  else:
    if not _replaceFileStringInCommand(command, files):
      raiseError([command])

  return command
