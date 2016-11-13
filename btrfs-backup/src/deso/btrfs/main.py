# main.py

#/***************************************************************************
# *   Copyright (C) 2015-2016 Daniel Mueller (deso@posteo.net)              *
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

"""The main module interfaces with the user input and sets up bits required for execution."""

from deso.btrfs.alias import (
  alias,
)
from deso.btrfs.argv import (
  reorder as reorderArg,
)
from deso.btrfs.commands import (
  checkFileString,
)
from deso.execute import (
  ProcessError,
)
from sys import (
  argv as sysargv,
  stderr,
)
from os import (
  extsep,
)
from re import (
  compile as regex,
)
from datetime import (
  timedelta,
)
from argparse import (
  Action,
  ArgumentError,
  ArgumentParser,
  ArgumentTypeError,
  HelpFormatter,
)


def name():
  """Retrieve the name of the program."""
  return "btrfs-backup"


def description():
  """Retrieve a description of the program."""
  return "A simple and fast btrfs-based backup tool."


def version():
  """Retrieve the program's current version."""
  return "0.1"


def run(method, subvolumes, src_repo, dst_repo, debug=False, **kwargs):
  """Start actual execution."""
  try:
    # This import pulls in all required modules and we check for
    # availability of all required commands. If one is not available, we
    # bail out here.
    from deso.btrfs.program import Program
  except FileNotFoundError as e:
    if debug:
      raise
    print("A command was not found:\n\"%s\"" % e, file=stderr)
    return 1

  try:
    program = Program(subvolumes, src_repo, dst_repo)
    method(program)(**kwargs)
    return 0
  except ProcessError as e:
    if debug:
      raise
    print("Execution failure:\n\"%s\"" % e, file=stderr)
    return 2
  except Exception as e:
    if debug:
      raise
    print("A problem occurred:\n\"%s\"" % e, file=stderr)
    return 3


def duration(string):
  """Create a timedelta object from a duration string."""
  suffixes = {
    "S": timedelta(seconds=1),
    "M": timedelta(minutes=1),
    "H": timedelta(hours=1),
    "d": timedelta(days=1),
    "w": timedelta(weeks=1),
    "m": timedelta(weeks=4),
    "y": timedelta(weeks=52),
  }

  for suffix, duration_ in suffixes.items():
    expression = regex(r"^([1-9][0-9]*){s}$".format(s=suffix))
    m = expression.match(string)
    if m:
      amount, = m.groups()
      return int(amount) * duration_

  raise ArgumentTypeError("Invalid duration string: \"%s\"." % string)


def checkSnapshotExtension(string):
  """Validate the given snapshot extension parameter."""
  if string.startswith(extsep):
    error = "Extension must not start with \"%s\"." % extsep
    raise ArgumentTypeError(error)

  # The extension we store always includes the separator.
  return "%s%s" % (extsep, string)


class CheckSnapshotExtensionAction(Action):
  """Action to check correct usage of the --snapshot-ext parameter."""
  def __init__(self, option_strings, dest, nargs=None, const=None,
               default=None, type=None, choices=None, required=False,
               help=None, metavar=None, backup=None):
    """Create a new CheckSnapshotExtensionAction object."""
    super().__init__(option_strings=option_strings, dest=dest, nargs=nargs,
                     const=const, default=default, type=type,
                     choices=choices, required=required, help=help,
                     metavar=metavar)

    assert backup is not None
    self._backup = backup


  def __call__(self, parser, namespace, values, option_string=None):
    """Helper function to check constraints of arguments during parsing."""
    # We require that the namespace is already fully set up with the
    # appropriate filter argument. This constraint is enforced by
    # reordering the arguments before parsing them such that the snapshot
    # extension argument appears (and is evaluated) last.
    if self._backup:
      if not namespace.recv_filters:
        error = "This option must be used in conjunction with --recv-filter."
        raise ArgumentError(self, error)
    else:
      if not namespace.send_filters:
        error = "This option must be used in conjunction with --send-filter."
        raise ArgumentError(self, error)

    if self._backup:
      if not checkFileString(namespace.recv_filters[-1]):
        error = "The last receive filter must contain the \"{file}\" string."
        raise ArgumentError(self, error)
    else:
      if not checkFileString(namespace.send_filters[0]):
        error = "The first send filter must contain the \"{file}\" string."
        raise ArgumentError(self, error)

    # We are essentially a sophisticated "store" action. So set the
    # attribute here.
    setattr(namespace, self.dest, values)


def addStandardArgs(parser):
  """Add the standard arguments --version and --help to an argument parser."""
  parser.add_argument(
    "-h", "--help", action="help",
    help="Show this help message and exit.",
  )
  parser.add_argument(
    "--version", action="version", version="%s %s" % (name(), version()),
    help="Show the program\'s version and exit.",
  )


def addOptionalArgs(parser, backup):
  """Add the optional arguments to a parser."""
  parser.add_argument(
    # In order to implement the --join option we use a trick: We append
    # the value 'None' to the 'send_filters' array that stores all send
    # filters.
    # TODO: Right now this option can be specified multiple times. That
    #       is wrong and should not be allowed. However, it is tricky to
    #       enforce that. Find a way.
    "--join", action="append_const", const=[None], dest="send_filters",
    help="Only allowed in conjunction with send filters. When specified, "\
         "it does two things. First, it changes the default execution "\
         "mode for the commands from a pipeline with a single source "\
         "(origin of data) to one with multiple sources. Which means "\
         "that the previous commands (filters) will be run in sequence "\
         "and their output be accumulated into a single destination "\
         "(rather than it being piped from one filter to the next). "\
         "Secondly, all subsequent filters will have the data from this "\
         "one source as their input.",
  )
  parser.add_argument(
    "--no-read-stderr", action="store_false", dest="read_err", default=True,
    help="Turn off reading of data from stderr. No information about "
         "the reason for a command failure except for the return code "
         "will be available. This option is helpful in certain cases "
         "where a command (likely a remote command) forks a child which "
         "stays alive longer than the actually run command. In such a "
         "case if we read the data from stderr we will effectively wait "
         "for the forked off command to terminate before continuing "
         "execution.",
  )
  parser.add_argument(
    "--remote-cmd", action="store", dest="remote_cmd", metavar="command",
    help="The command to use for running btrfs on a remote site. Needs "
         "to include the full path to the binary or script, e.g., "
         "\"/usr/bin/ssh server\".",
  )
  parser.add_argument(
    "--send-filter", action="append", default=None, dest="send_filters",
    metavar="command", nargs=1,
    help="A filter command applied in the snapshot send process. "
         "Multiple send filters can be supplied.",
  )
  parser.add_argument(
    "--recv-filter", action="append", default=None, dest="recv_filters",
    metavar="command", nargs=1,
    help="A filter command applied in the snapshot receive process. "
         "Multiple receive filters can be supplied.",
  )

  if backup:
    text = "Extension to use for storing a snapshot file. Only allowed "\
           "in conjunction with a custom receive filter that stores data "\
           "in a file (with the given extension) rather than to "\
           "deserialize the stream into a btrfs subvolume. In this case, "\
           "the very last receive filter must contain the string "\
           "\"{file}\" (without quotes) which will be replaced by the "\
           "file name of the snapshot to create. The filter must ensure "\
           "to save the data it received on stdin (and potentially "\
           "processed) into the given file."
  else:
    text = "Extension to use for identifying a snapshot file. Only "\
           "allowed in conjunction with a custom send filter that reads "\
           "data from multiple files (with the given extension) rather "\
           "than to serialize btrfs snapshots or subvolumes. In this "\
           "case, the first send filter must contain the string "\
           "\"{file}\" (without quotes). The argument containing this "\
           "string will be replicated for each file to send. The filter "\
           "must ensure to output the (potentially processed) data to "\
           "stdout."

  def createCheckAction(*args, **kwargs):
    """Create a CheckSnapshotExtensionAction object."""
    return CheckSnapshotExtensionAction(*args, backup=backup, **kwargs)

  # We use a custom action here to check all the constraints which the
  # filters have to satisfy in case --snapshot-ext is provided. The
  # action has access to the internally used namespace. This namespace
  # needs to contain all required attributes, which means all relevant
  # arguments need to have been parsed. Since the ArgumentParser parses
  # arguments in the order they are supplied on the command line (as
  # opposed to the order they were added in), we rely on the fact that
  # the --snapshot-ext option is at the end of the argument vector here.
  # The reorderArg invocation used earlier enforces this property.
  parser.add_argument(
    "--snapshot-ext", action=createCheckAction, dest="extension",
    metavar="extension", type=checkSnapshotExtension, help=text,
  )
  parser.add_argument(
    "--debug", action="store_true", dest="debug", default=False,
    help="Allow for exceptions to escape the program thereby producing "
         "full backtraces.",
  )


def addRequiredArgs(parser):
  """Add the various required arguments to a parser."""
  parser.add_argument(
    "src", action="store", metavar="source-repo",
    help="The path to the source repository.",
  )
  parser.add_argument(
    "dst", action="store", metavar="destination-repo",
    help="The path to the destination repository.",
  )
  parser.add_argument(
    "-s", "--subvolume", action="append", metavar="subvolume", nargs=1,
    dest="subvolumes", required=True,
    help="Path to a subvolume to include in the backup. Can be supplied "
         "multiple times to include more than one subvolume.",
  )


def addBackupParser(parser):
  """Add a parser for the backup command to another parser."""
  backup = parser.add_parser(
    "backup", add_help=False, formatter_class=SubLevelHelpFormatter,
    help="Backup one or more subvolumes.",
  )
  backup.set_defaults(method=lambda x: x.backup)

  required = backup.add_argument_group("Required arguments")
  addRequiredArgs(required)

  optional = backup.add_argument_group("Optional arguments")
  optional.add_argument(
    "--keep-for", action="store", type=duration, metavar="duration",
    dest="keep_for",
    help="Duration how long to keep snapshots. Snapshots that are older "
         "than \'duration\' will be deleted from the source repository "
         "when the next backup is performed. A duration is specified by "
         "an amount (i.e., a number) along with a suffix. Valid "
         "suffixes are: S (seconds), M (minutes), H (hours), d (days), "
         "w (weeks), m (months), and y (years).",
  )
  addOptionalArgs(optional, backup=True)
  addStandardArgs(optional)


def addRestoreParser(parser):
  """Add a parser for the restore command to another parser."""
  restore = parser.add_parser(
    "restore", add_help=False, formatter_class=SubLevelHelpFormatter,
    help="Restore subvolumes or snapshots from a repository.",
  )
  restore.set_defaults(method=lambda x: x.restore)

  required = restore.add_argument_group("Required arguments")
  addRequiredArgs(required)

  optional = restore.add_argument_group("Optional arguments")
  optional.add_argument(
    "--snapshots-only", action="store_true", dest="snapshots_only",
    default=False,
    help="Restore only snapshots, not the entire source subvolume."
  )
  addOptionalArgs(optional, backup=False)
  addStandardArgs(optional)


class TopLevelHelpFormatter(HelpFormatter):
  """A help formatter class for a top level parser."""
  def add_usage(self, usage, actions, groups, prefix=None):
    """Add usage information, overwrite the default prefix."""
    # Control flow is tricky here. Our invocation *might* come from the
    # sub-level parser or we might have been invoked directly. In the
    # latter case use our own prefix, otherwise just pass through the
    # given one.
    if prefix is None:
      prefix = "Usage: "

    super().add_usage(usage, actions, groups, prefix)


class SubLevelHelpFormatter(HelpFormatter):
  """A help formatter class for a sub level parser."""
  def add_usage(self, usage, actions, groups, prefix=None):
    """Add usage information, overwrite the default prefix."""
    super().add_usage(usage, actions, groups, "Usage: ")


def prepareNamespace(ns):
  """Prepare the given namespace object for conversion into dict."""
  def split(filters):
    """Split a number of filters into an array of commands."""
    return [f.split() for f in filters]

  def prepare(filters):
    """Prepare filters ready for use by the remaining parts of the program."""
    # The filters array might contain a None element (if the --join
    # option is used). In that case we set up the final array in a
    # different way: the first element will be an array of filters (as
    # opposed to a single filter).
    if None in filters:
      index = filters.index(None)
      part1 = split(filters[:index])
      part2 = split(filters[index+1:])

      # Create a new array with the first element being an array itself.
      return [part1] + part2 if part1 else part2
    else:
      return split(filters)

  method = ns.method
  src_repo = ns.src
  dst_repo = ns.dst
  remote_cmd = ns.remote_cmd

  # The namespace's appended list arguments are stored as a list of
  # list of strings. Convert each to a list of strings.
  subvolumes = [x for x, in ns.subvolumes]
  send_filters = [x for x, in ns.send_filters] if ns.send_filters else None
  recv_filters = [x for x, in ns.recv_filters] if ns.recv_filters else None

  if remote_cmd:
    # TODO: Right now we do not support remote commands that contain
    #       spaces in their path. E.g., "/bin/connect to server" would
    #       not be a valid command.
    remote_cmd = remote_cmd.split()

  # The send filters might contain a None element in case the --join
  # option is supplied. Handle this case correctly.
  if send_filters:
    send_filters = prepare(send_filters)
  if recv_filters:
    recv_filters = split(recv_filters)

  ns.recv_filters = recv_filters
  ns.send_filters = send_filters
  ns.remote_cmd = remote_cmd

  # Remove all positional and already processed or otherwise handled
  # attributes from the namespace object. This way we can directly
  # convert it into a dict and pass in all remaining properties as
  # keyword arguments subsequently.
  del ns.subvolumes
  del ns.src
  del ns.dst
  del ns.command
  del ns.method

  return method, subvolumes, src_repo, dst_repo


def main(argv):
  """The main function parses the program arguments and reacts on them."""
  parser = ArgumentParser(prog=name(), add_help=False,
                          description="%s -- %s" % (name(), description()),
                          formatter_class=TopLevelHelpFormatter)
  subparsers = parser.add_subparsers(
    title="Subcommands", metavar="command", dest="command",
    help="A command to perform.",
  )
  subparsers.required = True
  optional = parser.add_argument_group("Optional arguments")
  addStandardArgs(optional)

  addBackupParser(subparsers)
  addRestoreParser(subparsers)

  # Note that argv contains the path to the program as the first element
  # which we kindly ignore. Furthermore, we do some trickery to have
  # proper argument checking: For the --snapshot-ext option we perform
  # various checks (see checkSnapshotExtension). For this checking to
  # work the option has to be evaluated after all filter options. To
  # that end, we move it to the end of the options because the
  # ArgumentParser evaluates arguments in the order in which they are
  # provided in the argument vector.
  args = argv[1:].copy()
  args = reorderArg(args, "--snapshot-ext", has_arg=True)
  namespace = parser.parse_args(args)

  with alias(namespace) as ns:
    method, subvolumes, src_repo, dst_repo = prepareNamespace(ns)
    return run(method, subvolumes, src_repo, dst_repo, **vars(ns))


if __name__ == "__main__":
  exit(main(sysargv))
