# repository.py

#/***************************************************************************
# *   Copyright (C) 2015-2017,2019,2021 Daniel Mueller (deso@posteo.net)    *
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

from copy import (
  deepcopy,
)
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
  showFilesystem,
  serialize,
  snapshot as mkSnapshot,
  snapshots as listSnapshots,
  sync as syncFs,
  resolveId,
  rootId,
)
from deso.btrfs.commands import (
  replaceFileString,
  runCommands,
)
from deso.execute import (
  execute,
  ProcessError,
)
from os import (
  curdir,
  pardir,
  sep,
  uname,
)
from os.path import (
  abspath,
  dirname,
  expanduser,
  isabs,
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
_TIME_FORMAT_RAW = "{}-{}-{}_{}:{}:{}"
_TIME_FORMAT = _TIME_FORMAT_RAW.format("%Y", "%m", "%d", "%H", "%M", "%S")
_TIME_FORMAT_REGEX = _TIME_FORMAT_RAW.replace("{}", "....", 1).replace("{}", "..")
_ANY_STRING = r"."
_NUM_STRING = r"[0-9]"
_NUMS_STRING = r"{nr}+".format(nr=_NUM_STRING)
_PATH_STRING = r"{any}+".format(any=_ANY_STRING)
# The format of a line as retrieved by executing the command returned by
# the snapshots() function. Each line is expected to be following the
# pattern:
# ID A gen B top level C path PATH
_LIST_STRING = r"^ID {nums} gen ({nums}) top level {nums} path ({path})$"
_LIST_REGEX = regex(_LIST_STRING.format(nums=_NUMS_STRING, path=_PATH_STRING))
# The marker ending the file list reported by the diff() function. If
# this marker is the only thing reported then no files have changed.
_DIFF_END_MARKER = "transid marker"
# The separator of path elements in encoded form.
_PATH_ELEMENT_SEPARATOR = "@"


def _encodePath(path):
  """Given a path, retrieve an encoded version of it with replaced element separators.

    This function replaces all element separators with custom ones (see
    _PATH_ELEMENT_SEPARATOR) to make file names less confusing than with
    native separators.
  """
  path = _trail(path)
  # We allow only for absolute paths to be passed in (abspath always
  # returns an untrailed path).
  assert _untrail(path) == abspath(path), path
  path = path.replace(_PATH_ELEMENT_SEPARATOR, _PATH_ELEMENT_SEPARATOR * 2)
  path = path.replace(sep, _PATH_ELEMENT_SEPARATOR)
  return path


def _decodePath(string):
  """Given an encoded path, retrieve the normal form of it.

    Note that regardless of whether the encoded path contained a tailing
    separator or not the result of this function will always contain
    one.
  """
  # Careful not to replace escaped versions of the separator string.
  string = string.replace(_PATH_ELEMENT_SEPARATOR * 2, "{d}")
  string = string.replace(_PATH_ELEMENT_SEPARATOR, "{s}")
  string = string.format(d=_PATH_ELEMENT_SEPARATOR, s=sep)
  assert _untrail(string) == abspath(string), string
  return string


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
  output, _ = execute(*cmd, stdout=b"", stderr=repository.stderr)
  # We might retrieve an empty output if no snapshots were present. In
  # this case, just return early here.
  if not output:
    return []

  # Convert from byte array and split to retrieve a list of lines.
  output = output.decode("utf-8").splitlines()
  return [_parseListLine(line) for line in output]


def _snapshotFiles(directory, extension, repository):
  """Retrieve a list of snapshot files in a given directory."""
  base = _snapshotBaseName(None)
  time = _TIME_FORMAT_REGEX
  # Mind the asterisk between the time and the extension. It is required
  # because we can have snapshots with equal time stamps which are then
  # numbered in an increasing fashion.
  expression = regex(r"^%s.*-%s.*%s$" % (base, time, extension))

  # We have to rely on the '-v' parameter here to get a properly sorted
  # list and '-1' to display one file per line. We should not have to
  # use --color=never since coloring should not be applied here since
  # everything is non-interactive.
  cmd = repository.command(lambda: ["/bin/ls", "-v", "-1", directory])
  out, _ = execute(*cmd, stdout=b"", stderr=repository.stderr)
  out = out.decode("utf-8").splitlines()

  # In general we assume that the repository's directory does not
  # contain any user created files with which we could interfere.
  # However, we also try a little bit to filter out most files that
  # cannot possibly be snapshots because their naming scheme does not
  # match.
  files = []
  for f in out:
    m = expression.match(f)
    if m:
      files.append({"path": join(directory, f[:-len(extension)])})

  # We got a list of file names. However, our snapshot format is that of
  # a dict containing a 'path' key. Note that since we are unable to
  # interpret the format of arbitrary files (a filter is free to store
  # snapshots in any format), we have no chance of retrieving a
  # generation number here as is done for "native" snapshots.
  return files


def _findSubvolPath(directory, repository):
  """Find the path of a subvolume containing the given directory relative to the btrfs root."""
  try:
    # We start off by looking up the ID of the subvolume containing the
    # given directory.
    cmd = repository.command(rootId, directory)
    output, _ = execute(*cmd, stdout=b"", stderr=repository.stderr)
    id_ = int(output[:-1])

    # One we have that ID we can look up the subvolume's path relative
    # to the btrfs root.
    cmd = repository.command(resolveId, id_, directory)
    output, _ = execute(*cmd, stdout=b"", stderr=repository.stderr)
    return output[:-1].decode("utf-8")
  except ProcessError:
    return None


def _isDir(directory, repository):
  """Check if a directory exists."""
  try:
    # Append a trailing separator here to indicate that we are
    # checking for a directory. This way ls will fail if it is not. If
    # we left out the trailing separator and the directory actually
    # points to a file, ls would still succeed.
    func = lambda: ["/bin/ls", _trail(directory)]
    cmd = repository.command(func)

    execute(*cmd, stderr=repository.stderr)
    return True
  except ProcessError:
    return False


def _isRoot(directory, repository):
  """Check if a given directory represents the root of a btrfs file system."""
  try:
    cmd = repository.command(showFilesystem, directory)
    execute(*cmd, stdout=b"", stderr=repository.stderr)
    return True
  except ProcessError:
    return False


def _findDirectory(directory, repository, check):
  """Find a directory that matches a check."""
  assert directory

  if not _isDir(directory, repository):
    raise FileNotFoundError("Directory \"%s\" not found." % directory)

  cur_directory = directory
  while True:
    result, blob = check(cur_directory, repository)
    if result:
      return cur_directory, blob

    new_directory = dirname(cur_directory)
    # Executing a dirname on the root directory ('/') just returns the
    # root directory. Guard against endless loops.
    if new_directory == cur_directory:
      return None, None

    cur_directory = new_directory

  assert False


def _findRoot(directory, repository):
  """Find the root of the btrfs file system containing the given directory."""
  def isRoot(dir_, repo):
    """Small wrapper around _isRoot that returns a proper tuple."""
    return _isRoot(dir_, repo), None

  found, _ = _findDirectory(directory, repository, isRoot)
  return found


def _snapshotBaseName(subvolume):
  """Retrieve the base name of a snapshot for the given subvolume.

    The basename is the part of the first part of a snapshot's name that
    stays constant over time (but not system), i.e., that has no time
    information encoded in it and does not depend on data variable over
    time.
  """
  assert subvolume is None or subvolume == realpath(subvolume)

  r = uname()
  name = "%s-%s-%s" % (r.nodename, r.sysname.lower(), r.machine)
  if subvolume:
    # Remove any leading or trailing directory separators and then replace
    # the ones in the middle with underscores to make names look less
    # confusing.
    path = subvolume.strip(sep).replace(sep, "_")
    return "%s-%s-" % (name, path)
  else:
    return "%s-" % name


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
  snapshot = "%s%s" % (name, time)

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
  execute(*cmd, stderr=repository.stderr)

  # We create a snapshot and we (very likely) serialize it. So make sure
  # that it is persisted to disk. This step is performed here and not
  # before the actual deployment because here we are guaranteed to be
  # working on a "real" btrfs subvolume which we can sync.
  cmd = repository.command(syncFs, repository.root)
  execute(*cmd, stderr=repository.stderr)
  return name


def _findOrCreate(subvolume, repository, snapshots):
  """Ensure an up-to-date snapshot is available in the given repository."""
  snapshot = _findMostRecent(snapshots, subvolume)

  # If we found no snapshot or if files are changed between the current
  # state of the subvolume and the most recent snapshot we just found
  # then create a new snapshot.
  if not snapshot or _changed(snapshot, subvolume, repository):
    old = snapshot["path"] if snapshot else None
    new = _createSnapshot(subvolume, repository, snapshots)
    return new, old

  return snapshot["path"], snapshot["path"]


def _makeRelative(snapshots, directory):
  """Convert a list of absolute snapshots into a list with relative ones."""
  # We only want to loop once but we need to remove items during
  # iteration. So we iterate over a copy while deleting from the
  # original. In order to ensure all indices are valid even in the face
  # of deletion, we need to iterate from back to front. The enumerate
  # function counts in ascending order so for the deletion we need to
  # subtract the index from the length of the original array but because
  # of reverse iteration we need to subtract one more.
  rlen = len(snapshots) - 1
  copy = snapshots.copy()

  for i, snapshot in enumerate(reversed(copy)):
    path = snapshot["path"]
    # Check if the snapshot is not located in this repository's
    # directory.
    if path.startswith(directory):
      # Valid snapshot. Remove the now common prefix.
      snapshot["path"] = path[len(directory):]
    else:
      # Snapshot not in our directory. Remove it from the list.
      del snapshots[rlen - i]

  return snapshots


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

    # Now let the repository handle determination of the parents to use.
    # Depending on whether it is a "real" btrfs repository or a file
    # repository the parent list might be different.
    parents = src.parents(snapshot, subvolume, src_snaps, dst_snaps)
  else:
    parents = None

  # Only if both repositories agree that we should read data from
  # stderr we will do so.
  stderr = b"" if src.stderr == b"" and dst.stderr == b"" else None
  # Finally transfer the snapshot from the source repository to the
  # destination.
  src_cmds = src.sendPipeline(snapshot, parents)
  dst_cmds = dst.recvPipeline(snapshot)

  runCommands(src_cmds + dst_cmds, stderr=stderr)


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
    execute(*cmd, stderr=dst.stderr)


def restore(subvolumes, src, dst, snapshots_only=False):
  """Restore snapshots/subvolumes by transferal from another repository."""
  # Note that compared to _sync() we do not have to retrieve a new list
  # of snapshots on the source after every subvolume transfer because in
  # this step we are sure that we do not create any new snapshots (and
  # we assume nobody else does).
  snapshots = src.snapshots()

  for subvolume in subvolumes:
    _restore(realpath(subvolume), src, dst, snapshots, snapshots_only)


def _changed(snapshot, subvolume, repository):
  """Check if a given subvolume was changed with respect to a snapshot."""
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
  output, _ = execute(*cmd, stdout=b"", stderr=repository.stderr)
  # Do not decode the bytes object into a string. We cannot be sure of
  # the encoding. Although we could use sys.getfilesystemencoding() to
  # get the encoding used in the file system, cases were seen where file
  # names still contained undecodable characters (such as 0xbb).
  return not output.startswith(_DIFF_END_MARKER.encode("utf-8"))


def _purge(subvolume, repository, duration, snapshots):
  """Remove unused snapshots from a repository."""
  # Store the time we work with so that it does not change.
  now = datetime.now()
  snapshots = _findSnapshotsForSubvolume(snapshots, subvolume)

  # The list of snapshots is sorted in ascending order, that is, the
  # oldest snapshots will be at the beginning. Note that we exclude the
  # most recent snapshot, i.e., the last one in the list. It should
  # never be deleted.
  for snapshot in snapshots[:-1]:
    snapshot = snapshot["path"]
    time_str = _TIME_FORMAT_RAW
    time_str = time_str.replace("{}", "%s{4,}" % _NUM_STRING, 1)
    time_str = time_str.replace("{}", "%s{2}" % _NUM_STRING)
    time_re = regex(r".*(%s)(?:-[0-9]\+){0,1}" % time_str)

    m = time_re.match(snapshot)
    if not m:
      error = "Snapshot name does not contain a time stamp: \"{s}\""
      error = error.format(s=snapshot)
      raise ValueError(error)

    timestamp, = m.groups()
    # Parse the time stamp into a datetime value and check whether it is
    # old enough so that the snapshot should be deleted.
    time = datetime.strptime(timestamp, _TIME_FORMAT)
    if time + duration < now:
      cmd = repository.command(delete, repository.path(snapshot))
      execute(*cmd, stderr=repository.stderr)


def _trail(path):
  """Ensure the path has a trailing separator."""
  return join(path, "")


def _untrail(path):
  """Ensure the path has no trailing separator."""
  if path != sep:
    return _trail(path)[:-1]
  else:
    return path


def _relativize(path):
  """Adjust a relative path to make it point to the current directory."""
  if expanduser(path) == path and\
     not path.startswith(curdir) and\
     not path.startswith(pardir) and\
     not isabs(path):
    return join(curdir, path)

  return path


class RepositoryBase:
  """This class represents the base class for repositories for snapshots."""
  def __init__(self, directory, filters=None, read_err=True,
               remote_cmd=None):
    """Initialize the object and bind it to the given directory."""
    self._filters = filters
    self._read_err = b"" if read_err else None
    self._remote_cmd = remote_cmd
    # In order to properly handle relative paths correctly we need them
    # to start with the system's indicator for the current directory.
    # TODO: We could use a better story for path handling. The main
    #       concern are probably character based path comparisons (for
    #       prefixes, for instance).
    self._directory = _trail(_relativize(directory))

  def snapshots(self):
    """Retrieve a list of snapshots in this repository."""
    pass


  def parents(self, snapshot, subvolume, snapshots=None, dst_snapshots=None):
    """Retrieve a list of parent snapshots for the given snapshot of the supplied subvolume.

      Note that the interpretation of what a "parent" is exactly is up
      to the method (and the repository, for that matter). In
      particular, the main important fact is that the list of parents
      returned by this function has to be a valid input list for the
      'sendPipeline' method.
    """
    pass


  def path(self, *components):
    """Form an absolute path by combining the given path components."""
    return join(self._directory, *components)


  def command(self, function, *args, **kwargs):
    """Create a command."""
    command = function(*args, **kwargs)
    return (self._remote_cmd if self._remote_cmd else []) + command


  def sendPipeline(self, snapshot, parents):
    """Retrieve a pipeline of commands for sending the given snapshot."""
    pass


  def recvPipeline(self, snapshot):
    """Retrieve a pipeline of commands for receiving the given snapshot."""
    pass


  @property
  def stderr(self):
    """Retrieve the value to use as stderr keyword parameter when using an execution function."""
    # Note that for the simple reason that we run into issues where to
    # repositories are involved in a single command execution, having
    # this property per-repository is not the best idea. However, it was
    # deemed the most usable one because introducing another abstraction
    # just for command execution would bloat the code unnecessarily.
    return self._read_err


class Repository(RepositoryBase):
  """A repository for native snapshots.

    This class represents a native repository, i.e., one located on a
    btrfs volume. As such, objects of this class can be used as source
    and target repositories in backup and restore operations.
  """
  def __init__(self, directory, *args, **kwargs):
    """Initialize the repository, query its root in the btrfs file system."""
    super().__init__(directory, *args, **kwargs)
    self._root = _findRoot(_untrail(self._directory), self)

    if self._root is None:
      raise FileNotFoundError("Root of btrfs file system not found for "
                              "directory: \"%s\"" % self._directory)


  def snapshots(self):
    """Retrieve a list of snapshots in this repository."""
    def makeAbsolute(snapshot):
      """Convert a snapshot relative to the root directory to an absolute one."""
      snapshot["path"] = join(self._root, snapshot["path"])
      return snapshot

    # The list of snapshots we are going to retrieve can be "wrong" in a
    # variety of ways one would not expect given the intuitively simple
    # task of listing snapshots. If, for example, a subvolume of a btrfs
    # file system was mounted in a directory that is named differently
    # than the subvolume being mounted (by means of the 'subvol'
    # option), the snapshots path will still contain the name of the
    # subvolume, not that of the directory. The work around is rather
    # adventurous: We find the subvolume containing "our" directory and
    # retrieve its name. We then replace the last part of "our"
    # directory with this name and use the result as the "expected"
    # directory in the _makeRelative invocation.
    subvol_path = _trail(_findSubvolPath(self._root, self))

    snapshots = _snapshots(self)
    snapshots = _makeRelative(snapshots, subvol_path)
    # Make all paths absolute.
    snapshots = list(map(makeAbsolute, snapshots))
    # We need to work around the btrfs problem that not necessarily all
    # snapshots listed are located in our repository's directory. This
    # is done as one step along with converting the absolute snapshot
    # paths to relative ones where we just sort out everything not below
    # our directory.
    snapshots = _makeRelative(snapshots, self._directory)

    # TODO: We currently return a list of snapshots in the internally
    #       used format, i.e., dicts that contain a 'path' and a 'gen'
    #       key. Clients should not require the latter information
    #       and, thus, only the paths should be exposed to the
    #       outside. Such a change might require some adjustments,
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
      _purge(realpath(subvolume), self, duration, snapshots)


  def changed(self, snapshot, subvolume):
    """Check if a given subvolume was changed with respect to a snapshot."""
    # We are given a snapshot but we need a full snapshot entry
    # containing the name and the generation ID. So retrieve the list of
    # available snapshots and find the given one. A nice side effect is
    # that we check the validity of the snapshot being passed in.
    found = _findSnapshotByName(self.snapshots(), snapshot)
    if not found:
      raise FileNotFoundError("Snapshot not found: \"%s\"" % snapshot)

    return _changed(found, subvolume, self)


  def parents(self, _, subvolume, snapshots=None, dst_snapshots=None):
    """Retrieve a list of parent snapshots for the given snapshot of the supplied subvolume."""
    # We have no client not being able to supply the 'snapshots' list.
    assert snapshots is not None

    # The snapshots we have are still for arbitrary subvolumes. We are
    # only interested in those for the subvolume we are working on
    # currently.
    snapshots = _findSnapshotsForSubvolume(snapshots, subvolume)
    # We have to check which snapshots are available in the source
    # repository as well as the destination repository. These can be
    # used as parents for the incremental transfer. If none exists on
    # the destination side, we have to send the latest snapshot in its
    # entirety (i.e., the entire subvolume).
    parents = _findCommonSnapshots(snapshots, dst_snapshots)
    # Convert the snapshot list to paths relative to the source repository.
    parents = list(map(lambda x: self.path(x["path"]), parents))
    return parents


  def _pipeline(self, send, function, *args, **kwargs):
    """Create a command pipeline that includes all user supplied filters."""
    command = self.command(function, *args, **kwargs)
    # We assume the filters are already ordered according to the
    # intention to send or receive.
    if send:
      return [command] + (self._filters if self._filters else [])
    else:
      return (self._filters if self._filters else []) + [command]


  def sendPipeline(self, snapshot, parents):
    """Retrieve a pipeline of commands for sending the given snapshot."""
    return self._pipeline(True, serialize, self.path(snapshot), parents)


  def recvPipeline(self, _):
    """Retrieve a pipeline of commands for receiving the given snapshot."""
    return self._pipeline(False, deserialize, self.path())


  @property
  def root(self):
    """Retrieve the root directory of the btrfs file system the repository resides on."""
    return self._root


class FileRepository(RepositoryBase):
  """A repository comprising snapshot files with a given extension.

    Note that compared to "normal" repositories, i.e., objects of type
    Repository, file repositories are more restricted in their usage.
    Because they do not necessarily have to reside on an actual btrfs
    volume, creation of "real" snapshots and subvolumes is not possible.
    To that end, file repositories must not be used as source
    repositories in a sync operation and not as destination repositories
    in restores.
  """
  def __init__(self, directory, extension, *args, **kwargs):
    """Initialize the repository."""
    super().__init__(directory, *args, **kwargs)
    self._extension = extension


  def snapshots(self):
    """Retrieve a list of snapshot files in this repository.

      Note: Reasoning about snapshots always happens without the
            extension. That is, the paths of the snapshots returned from
            this function will not contain the extension.
    """
    snapshots = _snapshotFiles(self._directory, self._extension, self)
    snapshots = _makeRelative(snapshots, self._directory)
    return snapshots


  def parents(self, snapshot, subvolume, snapshots=None, dst_snapshots=None):
    """Retrieve a list of parent snapshots for the given snapshot of the supplied subvolume."""
    assert snapshots is not None

    snapshots = _findSnapshotsForSubvolume(snapshots, subvolume)
    # TODO: This method is not yet complete. We need to include only
    #       those snapshots that are true parents of the given one. That
    #       is, we have to stop at the last full snapshot.
    snapshots = filter(lambda x: x["path"] != snapshot, snapshots)
    return list(map(lambda x: self.path(x["path"]), snapshots))


  def _filterPipeline(self, index, snapshots):
    """Create a pipeline out of the filter commands."""
    # Convert all relative snapshot paths into absolute ones with the
    # appropriate extension.
    with alias(self._extension) as ext:
      snapshots = ["%s%s" % (self.path(s), ext) for s in snapshots]

    commands = deepcopy(self._filters)
    func = lambda: replaceFileString(commands[index], snapshots)
    # At least one command in the filters must contain a string {file}
    # which is now replaced by the actual snapshot name.
    commands[index] = self.command(func)
    return commands


  def sendPipeline(self, snapshot, parents):
    """Retrieve a pipeline of commands for sending the given snapshot."""
    # The given snapshot is the most recent one so it has to be listed
    # last.
    return self._filterPipeline(0, parents + [snapshot])


  def recvPipeline(self, snapshot):
    """Retrieve a pipeline of commands for receiving the given snapshot."""
    return self._filterPipeline(-1, [snapshot])
