# repository.py

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

"""Repository related functionality.

  This program uses the abstraction of a repository to reason about
  which files to transfer in order to create a backup of a btrfs
  subvolume. A repository is a directory that contains or is supposed to
  contain snapshots.
"""

from datetime import (
  datetime,
)
from deso.btrfs.alias import (
  alias,
)
from deso.btrfs.command import (
  delete,
  deserialize,
  diff,
  show,
  serialize,
  snapshot as mkSnapshot,
  snapshots as listSnapshots,
  sync as syncFs,
)
from deso.execute import (
  execute,
  pipeline,
)
from os import (
  sep,
  uname,
)
from os.path import (
  abspath,
  dirname,
  isdir,
  join,
  realpath,
)
from re import (
  compile as regex,
)


# The time format for the creation time of a snapshot. This format is
# used for deriving time stamps to be included in a snapshot's name.
# An important property this format has to provide is proper sorting:
# When sorting a list of snapshots (each containing a time stamp of this
# format), the most recent snapshot should always be at the end of the
# list after sorting is through. Since we are comparing strings, this
# property has to hold for all possible locales (even if Python does not
# include locales in their sorting, btrfs might, whose sorted output we
# parse).
_TIME_FORMAT = "%Y-%m-%d_%H:%M:%S"
_ANY_STRING = r"."
_NUM_STRING = r"[0-9]"
_NUMS_STRING = r"{nr}+".format(nr=_NUM_STRING)
_PATH_STRING = r"{any}+".format(any=_ANY_STRING)
_FLAG_STRING = r"[A-Z|]+"
# The format of a line as retrieved by executing the command returned by
# the snapshots() function. Each line is expected to be following the
# pattern:
# ID A gen B top level C path PATH
_LIST_STRING = r"^ID {nums} gen ({nums}) top level {nums} path ({path})$"
_LIST_REGEX = regex(_LIST_STRING.format(nums=_NUMS_STRING, path=_PATH_STRING))
# The first line in the output generated by executing the command
# returned by the show() should contain the subvolume path if the
# given directory is a subvolume. However, if it is the root of the
# btrfs file system then it will end in 'is btrfs root'. We need to
# detect this case to determine the btrfs root.
_SHOW_IS_ROOT = "is btrfs root"
# The format of a line as retrieved by executing the command returned by
# the diff() function. Each line is expected to be following the
# pattern:
# inode A file offset B len C disk start D offset E gen F flags FLAGS PATH
# We do not care about the FLAGS values. Apparently, they are always
# uppercase and can be combined via '|' but we do not interpret them.
_DIFF_STRING = (r"^inode {nums} file offset {nums} len {nums} disk start {nums}"
                r" offset {nums} gen {nums} flags {flags} ({path})$")
_DIFF_REGEX = regex(_DIFF_STRING.format(nums=_NUMS_STRING, flags=_FLAG_STRING,
                                        path=_PATH_STRING))
_DIFF_IGNORE = "transid marker"


def _parseListLine(line):
  """Parse a line of output of the command as returned by snapshots()."""
  m = _LIST_REGEX.match(line)
  if not m:
    raise ValueError("Invalid snapshot list: unable to match line \"%s\"" % line)

  gen, path = m.groups()

  result = {}
  result["gen"] = int(gen)
  result["path"] = path
  return result


def _parseDiffLine(line):
  """Parse a line of output for the command as returned by diff()."""
  m = _DIFF_REGEX.match(line)
  if not m:
    raise ValueError("Invalid diff list: unable to match line \"%s\"" % line)

  path, = m.groups()
  return path


def _snapshots(repository):
  """Retrieve a list of snapshots in a repository.

    Note:
      Because of a supposed bug in btrfs' handling of passed in
      directories, the output of this function is *not* necessarily
      limited to subvolumes *below* the given directory. See test case
      testRepositoryListNoSnapshotPresentInSubdir. For that matter,
      usage of this function is discouraged. Use the Repository's
      snapshots() method instead.
  """
  cmd = repository.command(listSnapshots, repository.path())
  output, _ = execute(*cmd, read_out=True, read_err=repository.readStderr)
  # We might retrieve an empty output if no snapshots were present. In
  # this case, just return early here.
  if not output:
    return []

  # Convert from byte array and split to retrieve a list of lines.
  output = output.decode("utf-8").splitlines()
  return [_parseListLine(line) for line in output]


def _isRoot(directory, repository):
  """Check if a given directory represents the root of a btrfs file system."""
  cmd = repository.command(show, directory)
  output, _ = execute(*cmd, read_out=True, read_err=repository.readStderr)
  output = output.decode("utf-8")[:-1].split("\n")

  # The output of show() contains multiple lines in case the given
  # directory is a subvolume. In case it is an ordinary directory the
  # output is a single line and begins with "ERROR:" (but the command
  # actually succeeds), and in case of the root directory it will be
  # matched here.
  return len(output) == 1 and output[0].endswith(_SHOW_IS_ROOT)


def _findRoot(directory, repository):
  """Find the root of the btrfs file system containing the given directory."""
  assert directory
  assert directory == abspath(directory)

  # Note that we have no guard here against an empty directory as input
  # or later because of a dirname invocation. However, the show command
  # in _isRoot will fail for an empty directory (a case that will also
  # be hit if this function is run on a non-btrfs file system).
  while not _isRoot(directory, repository):
    new_directory = dirname(directory)

    # Executing a dirname on the root directory ('/') just returns the
    # root directory. Guard against endless loops.
    if new_directory == directory:
      raise FileNotFoundError("Root of btrfs file system not found for "
                              "directory: \"%s\"" % directory)

    directory = new_directory

  return directory


def _snapshotBaseName(subvolume):
  """Retrieve the base name of a snapshot for the given subvolume.

    The basename is the part of the first part of a snapshot's name that
    stays constant over time (but not system), i.e., that has no time
    information encoded in it and does not depend on data variable over
    time.
  """
  assert subvolume == realpath(subvolume)

  r = uname()
  name = "%s-%s-%s" % (r.nodename, r.sysname.lower(), r.machine)
  # Remove any leading or trailing directory separators and then replace
  # the ones in the middle with underscores to make names look less
  # confusing.
  path = subvolume.strip(sep).replace(sep, "_")
  return "%s-%s" % (name, path)


def _ensureUniqueName(snapshot, snapshots):
  """Make sure that a snapshot name is unique by potentially appending a number.

    Check if a snapshot with this name already exists in the given list.
    This can happen if we sync in very rapid succession (with data being
    added in between). In this case we need to add a number to
    snapshot's name to avoid name clashes.
  """
  i = 1
  name = snapshot

  # Note that there might be multiple snapshots created this way, so not
  # just pick the first number and be done but actually verify that the
  # newly generated name is unique and if not increment the number and
  # try again.
  # Note: Strictly speaking we would have to verify that appending a
  #       dash with a number preserves the sorting property that the
  #       most recent snapshot (in this case the one with the higher
  #       number if everything else in the name is equal) is listed
  #       last. We luck out because the time format already contains a
  #       dash as a separator so the existing test covers this case as
  #       well.
  while _findSnapshotByName(snapshots, name):
    name = "%s-%s" % (snapshot, i)
    i = i + 1

  # TODO: By just returning a name without actually creating the
  #       snapshot at the same moment we potentially race with
  #       concurrent snapshot operations. We should cope with failures
  #       due to name clashes instead.
  return name


def _snapshotName(subvolume, snapshots):
  """Retrieve a fully qualified, unique snapshot name."""
  name = _snapshotBaseName(subvolume)
  time = datetime.strftime(datetime.now(), _TIME_FORMAT)
  snapshot = "%s-%s" % (name, time)

  return _ensureUniqueName(snapshot, snapshots)


def _findSnapshotsForSubvolume(snapshots, subvolume):
  """Given a list of snapshots, find all belonging to the given subvolume."""
  base = _snapshotBaseName(subvolume)

  # It is worth pointing out that we assume here (and in a couple of
  # other locations) that all relevant snapshots are *not* located in a
  # sub-directory, otherwise we cannot simply compare the base against
  # the beginning of the string. This is a valid assumption for this
  # program, though.
  return list(filter(lambda x: x["path"].startswith(base), snapshots))


def _findMostRecent(snapshots, subvolume):
  """Given a list of snapshots, find the most recent one."""
  snapshots = _findSnapshotsForSubvolume(snapshots, subvolume)

  if not snapshots:
    return None

  # The most recent snapshot is the last since we list snapshots in
  # ascending order by date.
  return snapshots[-1]


def _findSnapshotByName(snapshots, name):
  """Check if a list of snapshots contains a given one."""
  snapshots = list(filter(lambda x: x["path"] == name, snapshots))

  if not snapshots:
    return None

  snapshot, = snapshots
  return snapshot


def _findCommonSnapshots(src_snaps, dst_snaps):
  """Given two lists of snapshots, find the ones common on both lists."""
  # Note that although not strictly required we want to keep the
  # snapshot dicts with all their meta-data and not reduce them to
  # simple paths, i.e., strings. We achieve that by creating the set of
  # paths that is common to both repositories and then just filtering
  # out all other paths from one of the original lists.
  src_paths = set(map(lambda x: x["path"], src_snaps))
  dst_paths = set(map(lambda x: x["path"], dst_snaps))

  # Note that by using set intersection here we assume that there is a uniform
  # style of trailing directory separators used. This fact is ensured by the
  # Repository's snapshots() method.
  paths = src_paths & dst_paths

  # Work on the list with fewer items.
  snaps = src_snaps if len(src_snaps) <= len(dst_snaps) else dst_snaps
  return filter(lambda x: x["path"] in paths, snaps)


def _createSnapshot(subvolume, repository, snapshots):
  """Create a snapshot of the given subvolume in the given repository."""
  name = _snapshotName(subvolume, snapshots)
  cmd = repository.command(mkSnapshot, subvolume, repository.path(name))

  execute(*cmd, read_err=repository.readStderr)
  return name


def _findOrCreate(subvolume, repository, snapshots):
  """Ensure an up-to-date snapshot is available in the given repository."""
  snapshot = _findMostRecent(snapshots, subvolume)

  # If we found no snapshot or if files are changed between the current
  # state of the subvolume and the most recent snapshot we just found
  # then create a new snapshot.
  if not snapshot or _diff(snapshot, subvolume, repository):
    old = snapshot["path"] if snapshot else None
    new = _createSnapshot(subvolume, repository, snapshots)
    return new, old

  return snapshot["path"], snapshot["path"]


def _deploy(snapshot, parent, src, dst, src_snaps, subvolume):
  """Deploy a snapshot to a repository."""
  if parent:
    # Retrieve a list of snapshots in the destination repository.
    dst_snaps = dst.snapshots()

    # In case the snapshot did already exist, i.e., we did not create a
    # new one, the parent and the "current" snapshot are equal. And only
    # if it did already exist can it possibly be available in the destination
    # repository.
    if snapshot == parent:
      if _findSnapshotByName(dst_snaps, snapshot):
        # The snapshot is already present in the repository. There is
        # nothing to be done.
        return

    # We have to check which snapshots are available in the source
    # repository as well as the destination repository. These can be
    # used as parents for the incremental transfer. If none exists on
    # the destination side, we have to send the latest snapshot in its
    # entirety (i.e., the entire subvolume).
    parents = _findCommonSnapshots(src_snaps, dst_snaps)
    # We have the common set of snapshots, however, these are still
    # snapshots of arbitrary subvolumes. We are only interested in those
    # for the subvolume we are working on currently.
    parents = _findSnapshotsForSubvolume(parents, subvolume)
    # Convert the snapshot list to paths relative to the source repository.
    parents = map(lambda x: src.path(x["path"]), parents)
  else:
    parents = None

  # Be sure to have the snapshot persisted to disk before trying to
  # serialize it.
  execute(*src.command(syncFs, src.root), read_err=src.readStderr)
  # Only if both repositories agree that we should read data from
  # stderr we will do so.
  read_err = src.readStderr and dst.readStderr
  # Finally transfer the snapshot from the source repository to the
  # destination.
  src_cmds = src.pipeline(True, serialize, src.path(snapshot), parents)
  dst_cmds = dst.pipeline(False, deserialize, dst.path())

  pipeline(src_cmds + dst_cmds, read_err=read_err)


def _sync(subvolume, src, dst):
  """Sync a single subvolume between two repositories.

    The synchronization of two repositories is a two step process:
    1) Snapshot creation.
      o Find most recent snapshot in source repository for the subvolume
      | to backup.
      |-> Found one:
      |   o Check if the subvolume to backup has file changes with
      |   | respect to this snapshot.
      |   |-> Yes:
      |   |   o Create a new snapshot.
      |   |-> No:
      |       o Our snapshot is up-to-date, no need to create a new one.
      |-> Found none:
          o Create a new snapshot.
    2) Snapshot deployment.
      o Check whether the most recent snapshot (there now has to be one)
      | is available in the destination repository.
      |-> Yes:
      |   o The source and destination repositories are in sync already.
      |-> No:
          o Transfer the snapshot to the destination repository.
  """
  snapshots = src.snapshots()
  snapshot, parent = _findOrCreate(subvolume, src, snapshots)
  _deploy(snapshot, parent, src, dst, snapshots, subvolume)


def sync(subvolumes, src, dst):
  """Sync the given subvolumes between two repositories, i.e., this one and a "remote" one."""
  # Note that when we synchronize multiple subvolumes and one of the
  # last subvolume synchronizations fails (for whatever reason), the
  # previously created and sync'ed snapshots will stay. This behavior is
  # by design. Whenever a unit is successfully backed up we leave it
  # this way.
  for subvolume in subvolumes:
    # Note that we use realpath here rather than abspath because we care
    # about the uniqueness of snapshot names and so the given subvolume
    # path has to be in canonical form.
    _sync(realpath(subvolume), src, dst)


def _restore(subvolume, src, dst, snapshots, snapshots_only):
  """Restore a snapshot/subvolume by transferal from another repository."""
  snapshot = _findMostRecent(snapshots, subvolume)
  subvolume = realpath(subvolume)

  # In case the given source repository does not contain any snapshots
  # for the given subvolume we cannot do anything but signal that to
  # the user.
  if not snapshot:
    error = "No snapshot to restore found for subvolume \"{s}\" in \"{r}\""
    error = error.format(s=subvolume, r=src.path())
    raise FileNotFoundError(error)

  # We want to signal an error to the user in case the subvolume already
  # exists but he/she has asked us to restore it. We cannot solely rely
  # on btrfs snapshot for this detection because in case there is a
  # directory where 'subvolume' points to, the command will just
  # manifest the new subvolume in this directory. So explicitly guard
  # against this case here.
  if not snapshots_only and isdir(subvolume):
    error = "Cannot restore subvolume \"{s}\": a directory with this name exists."
    error = error.format(s=subvolume)
    raise FileExistsError(error)

  snapshot = snapshot["path"]

  # Restoration of a subvolume involves a subset of the steps we do
  # when we perform a full sync: the deployment.
  _deploy(snapshot, snapshot, src, dst, snapshots, subvolume)

  # Now that we got the snapshot back on the destination repository,
  # we can restore the actual subvolume from it (if desired).
  if not snapshots_only:
    cmd = dst.command(mkSnapshot, dst.path(snapshot), subvolume, writable=True)
    execute(*cmd, read_err=dst.readStderr)


def restore(subvolumes, src, dst, snapshots_only=False):
  """Restore snapshots/subvolumes by transferal from another repository."""
  # Note that compared to _sync() we do not have to retrieve a new list
  # of snapshots on the source after every subvolume transfer because in
  # this step we are sure that we do not create any new snapshots (and
  # we assume nobody else does).
  snapshots = src.snapshots()

  for subvolume in subvolumes:
    _restore(subvolume, src, dst, snapshots, snapshots_only)


def _diff(snapshot, subvolume, repository):
  """Find the files that changed in a given subvolume with respect to a snapshot."""
  # Because of an apparent bug in btrfs(8) (or a misunderstanding on my
  # side), we cannot use the generation reported for a snapshot to
  # create a diff of the files that changed *since* then. Rather, we
  # have to increment the generation by one, otherwise the files changed
  # *in* the snapshot are included in the diff as well.
  generation = str(snapshot["gen"] + 1)

  # TODO: Strictly speaking the command created by diff() works on a
  #       generation basis and has no knowledge of snapshots. We need
  #       to clarify whether a new snapshot *always* also means a new
  #       generation (I assume so, but it would be best to get
  #       confirmation).
  cmd = repository.command(diff, subvolume, generation)
  output, _ = execute(*cmd, read_out=True, read_err=repository.readStderr)
  output = output.decode("utf-8")[:-1].split("\n")
  # The diff output usually is ended by a line such as:
  # "transid marker was" followed by a generation ID. We should ignore
  # those lines since we do not require this information. So filter
  # them out here.
  output = filter(lambda x: not x.startswith(_DIFF_IGNORE), output)
  return [_parseDiffLine(line) for line in output]


def _purge(subvolume, repository, duration, snapshots):
  """Remove unused snapshots from a repository."""
  # Store the time we work with so that it does not change.
  now = datetime.now()
  base = _snapshotBaseName(subvolume)
  snapshots = _findSnapshotsForSubvolume(snapshots, subvolume)

  # The list of snapshots is sorted in ascending order, that is, the
  # oldest snapshots will be at the beginning. Note that we exclude the
  # most recent snapshot, i.e., the last one in the list. It should
  # never be deleted.
  for snapshot in snapshots[:-1]:
    snapshot = snapshot["path"]
    # The string is comprised of the base name, the separator '-', as
    # well as the time stamp. Remove all but the time stamp.
    string = snapshot[len(base)+1:]

    # Parse the time stamp into a datetime value and check whether it is
    # old enough so that the snapshot should be deleted.
    time = datetime.strptime(string, _TIME_FORMAT)
    if time + duration < now:
      cmd = repository.command(delete, repository.path(snapshot))
      execute(*cmd, read_err=repository.readStderr)


def _trail(path):
  """Ensure the path has a trailing separator."""
  return join(path, "")


class Repository:
  """This class represents a repository for snapshots."""
  def __init__(self, directory, filters=None, read_err=True,
               remote_cmd=None):
    """Initialize the object and bind it to the given directory."""
    # We always work with absolute paths here.
    directory = abspath(directory)

    self._filters = filters
    self._read_err = read_err
    self._remote_cmd = remote_cmd
    self._root = _findRoot(directory, self)
    self._directory = _trail(directory)


  def snapshots(self):
    """Retrieve a list of snapshots in this repository."""
    snapshots = _snapshots(self)

    # We need to work around the btrfs problem that not necessarily all
    # snapshots listed are located in our repository's directory.
    with alias(self._directory) as prefix:
      # We only want to loop once but we need to remove items during
      # iteration. So we iterate over a *copy* while deleting from the
      # original. In order to ensure all indices are valid even in the
      # face of deletion, we need to iterate from back to front. The
      # enumerate function counts in ascending order so for the deletion
      # we need to subtract the index from the length of the original
      # array but because of reverse iteration we need to subtract one
      # more.
      rlen = len(snapshots) - 1
      copy = snapshots.copy()

      for i, snapshot in enumerate(reversed(copy)):
        # Make all paths absolute.
        path = join(self._root, snapshot["path"])
        # Check if the snapshot is not located in this repository's
        # directory.
        if path.startswith(prefix):
          # Valid snapshot. Remove the now common prefix.
          snapshot["path"] = path[len(prefix):]
        else:
          # Snapshot not in our directory. Remove it from the list.
          del snapshots[rlen - i]

      # TODO: We currently return a list of snapshots in the internally
      #       used format, i.e., a dict that contains a 'path' and a
      #       'gen' key. Clients should not require the latter
      #       information and, thus, only the paths should be exposed to
      #       the outside. Such a change might require some adjustments,
      #       however, and it is unclear whether it is worth the effort.
      return snapshots


  def purge(self, subvolumes, duration):
    """Remove unused snapshots from the repository."""
    # Note that we cache the snapshots here. This will cause problems if
    # the same subvolume is passed in multiple times in which case we
    # might try to remove an associated snapshot multiple times as well,
    # which is destined to fail. However, this is clearly wrong usage.
    # TODO: Strictly speaking the best place for purging existing
    #       snapshots is from the sync() function. When in this function
    #       we have already queried all snapshots and can work with them
    #       instead of gathering a new list here.
    snapshots = self.snapshots()

    for subvolume in subvolumes:
      _purge(subvolume, self, duration, snapshots)


  def diff(self, snapshot, subvolume):
    """Find the files that changed in a given subvolume with respect to a snapshot."""
    # We are given a snapshot but we need a full snapshot entry
    # containing the name and the generation ID. So retrieve the list of
    # available snapshots and find the given one. A nice side effect is
    # that we check the validity of the snapshot being passed in.
    found = _findSnapshotByName(self.snapshots(), snapshot)
    if not found:
      raise FileNotFoundError("Snapshot not found: \"%s\"" % snapshot)

    return _diff(found, subvolume, self)


  def path(self, *components):
    """Form an absolute path by combining the given path components."""
    return join(self._directory, *components)


  def command(self, function, *args, **kwargs):
    """Create a command."""
    command = function(*args, **kwargs)
    return (self._remote_cmd if self._remote_cmd else []) + command


  def pipeline(self, send, function, *args, **kwargs):
    """Create a command pipeline that includes all user supplied filters."""
    command = self.command(function, *args, **kwargs)
    # We assume the filters are already ordered according to the
    # intention to send or receive.
    if send:
      return [command] + (self._filters if self._filters else [])
    else:
      return (self._filters if self._filters else []) + [command]


  @property
  def root(self):
    """Retrieve the root directory of the btrfs file system the repository resides on."""
    return self._root


  @property
  def readStderr(self):
    """Check whether or not to read data from stderr when executing a command."""
    # Note that for the simple reason that we run into issues where to
    # repositories are involved in a single command execution, having
    # this property per-repository is not the best idea. However, it was
    # deemed the most usable one because introducing another abstraction
    # just for command execution would bloat the code unnecessarily.
    return self._read_err
