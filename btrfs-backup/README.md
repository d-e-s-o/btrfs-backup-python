btrfs-backup
============

Purpose
-------

**btrfs-backup** is a program that can be used to backup data from one
or multiple btrfs file systems. It relies on the btrfs(8) utility
program to perform its job and provides a very simple interface for
quick btrfs snapshot creation and transferal.

As for the btrfs file system itself, the unit of backup is a subvolume.
Creation of snapshots for subvolumes is performed on an on demand basis,
that is, only if new data is detected to be available on the respective
subvolume a new snapshot is taken.

The program reasons in terms of repositories. A repository is a
directory on a btrfs system which is used to contain the newly created
as well as already available snapshots. In terms of backup there are two
repositories involved: a source repository and a destination repository.
These repositories are kept in sync by performing an incremental
transfer of the files of a snapshot from the source to the destination.
On the destination repository, the snapshot will subsequently be
remanifested.


Examples
--------

Assuming the following directory layout where each of the directories is
a btrfs subvolume:                                                <br />
.                                                                 <br />
├── backup                                                        <br />
├── snapshots                                                     <br />
└── subvolume                                                     <br />

The idea is that 'snapshots' will be the source repository, 'backup'
will be the destination repository, and 'subvolume' is the btrfs
subvolume to backup. In order to create a backup, use the following
command:

``$ btrfs-backup --subvolume=subvolume/ snapshots/ backup/``

The -s/--subvolume option can be supplied multiple times in order to
perform a backup of multiple subvolumes.
