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


def replaceFileString(command, files):
  """Replace the {file} string in a command with the actual file name.

    Note: Any replacement is performed on the actual data, i.e., without
          making a copy beforehand.
  """
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
