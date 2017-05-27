# command.py

#/***************************************************************************
# *   Copyright (C) 2015,2017 Daniel Mueller (deso@posteo.net)              *
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

"""Functions for creating btrfs commands ready for execution.

  In order to perform btrfs related actions we interface with the
  btrfs(8) command. This command provides the necessary functionality we
  require throughout the program, e.g., for creating and deleting
  subvolumes (only used for testing), listing, creating and deleting
  snapshots, sending and receiving them, and more.
"""

from deso.execute import (
  findCommand,
)
from itertools import (
  chain,
)


_BTRFS = findCommand("btrfs")


def create(subvolume):
  """Retrieve the command to create a new btrfs subvolume."""
  return [_BTRFS, "subvolume", "create", subvolume]


def delete(subvolume):
  """Retrieve the command to delete a btrfs subvolume."""
  return [_BTRFS, "subvolume", "delete", subvolume]


def show(subvolume):
  """Retrieve the command to show information about a btrfs subvolume."""
  return [_BTRFS, "subvolume", "show", subvolume]


def snapshot(source, destination, writable=False):
  """Retrieve the command to create a snapshot of a subvolume."""
  options = []
  if not writable:
    options = ["-r"]

  return [_BTRFS, "subvolume", "snapshot"] + options + [source, destination]


def sync(filesystem):
  """Retrieve the command to sync the given btrfs file system to disk.

    Notes:
      A sync operation should be performed before attempting to send
      (i.e., serialize) a btrfs snapshot.
  """
  return [_BTRFS, "filesystem", "sync", filesystem]


def serialize(subvolume, parents=None):
  """Retrieve the command to serialize a btrfs subvolume into a byte stream."""
  options = []
  if parents:
    # We only use the clone-source (-c) option here and not the parent (-p) one
    # because we can specify multiple clone sources (the parameter is allowed
    # multiple times) whereas we must only specify one parent. In any case,
    # if the -c option is given the btrfs command will figure out the parent to
    # use by itself.
    # In general, the clone-source option specifies that data from a given
    # snapshot (that has to be available on both the source and the
    # destination) is used when constructing back the subvolume from the byte
    # stream. This additional information can be used to achieve better sharing
    # of internally used data in the resulting subvolume. Since the
    # clone-source option implies the parent option, it also instructs the
    # command to send only the incremental data (to the latest snapshot).
    options = list(chain.from_iterable(["-c", parent] for parent in parents))

  return [_BTRFS, "send"] + options + [subvolume]


def deserialize(data):
  """Retrieve the command to deserialize a btrfs subvolume from a byte stream."""
  return [_BTRFS, "receive", data]


def snapshots(directory):
  """Retrieve a command to list all snapshots in a given directory.

    Notes:
      Please be aware of the wrong handling of the -o parameter in
      btrfs, leading to *not* necessarily only snapshots below the given
      directory being returned.
  """
  # Note: We include a time stamp into a snapshot's name which is
  #       formatted in a way so as to ensure sorting a list of snapshots
  #       is in ascending order with respect to the time each was
  #       created at.
  # Note: We do not pass in the -s option here. The reason is that once
  #       we send and received a snapshot, the property of it being a
  #       snapshot is lost. The only property that is preserved is it
  #       being read-only.
  return [_BTRFS, "subvolume", "list", "--sort=path", "-r", "-o", directory]


def diff(subvolume, generation):
  """Retrieve a command to query a list of changed files for the given subvolume.

    This function creates a command that, given a btrfs subvolume and a
    previous generation ID, determines the files that have been changed.
  """
  return [_BTRFS, "subvolume", "find-new", subvolume, generation]


def showFilesystem(filesystem):
  """Retrieve the command to show information about a btrfs file system."""
  return [_BTRFS, "filesystem", "show", filesystem]
