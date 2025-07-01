# vim: ts=4 sw=4 et

# This code is part of A Example Pipeline for Unattended Pipelines,
# Data Transfer, and Computation Using Globus.
# https://github.com/stanford-rc/globus-example-flow
# This code contains the Globus Compute function that does the "Computation"
# part of the demo.  It also contains code that is used to submit the Function
# to Globus HQ.
# It was written by A. Karl Kornel <akkornel@stanford.edu>

# © 2025 The Board of Trustees of the Leland Stanford Junior University
# SPDX-License-Identifier: BSD-3-Clause
# https://opensource.org/license/bsd-3-clause

# What follows is Inline Script metadata, which tools that support PEP 723 can
# use to automatically create an environment that can run the script.
# /// script
# requires-python = ">=3.8"
# dependencies = [
#   "globus-compute-sdk>=3.8.0",
# ]
# ///

# This script includes both the Function to register with Globus Compute, and
# also the code which does the registration.

# Start with the function we want to upload to Globus Compute
# NOTE: We do not do any top-level imports until *after* the function is
# defined.  This is important, because the function will only be able to
# reference the stuff that it imports in the function.
def do_checksum(
    in_dir: str,
    out_dir: str,
) -> None:
    """Checksum the contents of a directory.

    This iterates through a directory (and all sub-directories), doing a
    SHA-256 checksum of each file encountered.  The list of files and their
    checksums is written to the file `checksums.txt`.

    Directory contents are checksummed in sorted order.

    Items that are not files are skipped.  This includes symlinks.

    :param in_dir: The directory to be checksummed.

    :param out_dir:
        The directory to hold the `checksums.txt` list of file checksums.
    """

    # NOTE: Our parameter & return types should be base Python types.
    # Why?  Because if this is called from a Globus Flow, everything is being
    # converted to/from JSON.

    # Import all the modules that are required by the function.
    import hashlib
    import os
    import pathlib
    import typing

    # Constants
    BLOCK_SIZE = 4096 * 1024 * 1024  # 4 MiB, in bytes
    """How much do we read from disk at once?
    """

    # Convert our in and out paths to Path objects
    in_path = pathlib.Path(in_dir)
    out_path = pathlib.Path(out_dir)

    # Open a file to hold the list of checksums
    checksum_path = out_path / 'checksums.txt'
    checksum_fh = checksum_path.open(
        mode='w',
        encoding='utf-8',
        buffering=1,
        errors='backslashreplace',
    )

    # Make a list of directories to checksum.
    # We'll progress through directories in the order they're listed.
    dirs_to_check: list[pathlib.Path] = [
        in_path,
    ]

    # Iterate over all our directories
    while len(dirs_to_check) > 0:
        # Grab the directory at the head of the list
        dir_to_check = dirs_to_check.pop()

        # Sort the contents of the directory, and check each item.
        for dir_item in sorted(dir_to_check.iterdir()):
            if dir_item.is_dir():
                # Directories to the end of the list
                dirs_to_check.append(dir_item)
            elif dir_item.is_file():
                # Files are checksummed!

                # Open our file, and set up for single read
                target_fh = dir_item.open(
                    mode='rb',
                )
                # NOTE: This is an example of how Globus Compute can break.
                # macOS Python does not have the `os.posix_fadvise` function.
                # Even if you wrap the call like below, if you upload the
                # function from macOS and run on a Linux Compute Endpoint, the
                # Linux Compute Endpoint will throw an error.
                #if 'posix_fadvise' in dir(os):
                    #os.posix_fadvise(   # type: ignore[attr-defined]
                    #    target_fh.fileno(),  # fd
                    #    0,                   # offset
                    #    0,                   # len
                    #    os.POSIX_FADV_SEQUENTIAL | os.POSIX_FADV_NOREUSE,    # type: ignore[attr-defined]
                    #)

                # Set up our SHA-256 hasher
                hasher = hashlib.sha256(
                    usedforsecurity=False,
                )

                # Read & hash blocks of data
                data = target_fh.read(BLOCK_SIZE)
                while len(data) != 0:
                    hasher.update(data)
                    data = target_fh.read(BLOCK_SIZE)

                # Output our hash!
                print(
                    hasher.hexdigest(),
                    str(dir_item.relative_to(in_path)),
                    sep='\t',
                    end='\n',
                    file=checksum_fh,
                )
                target_fh.close()
            else:
                # Skip all other types of items (like symlinks)
                pass

    # All done!
    checksum_fh.close()

# Everything after this point is the "framework" that handles registration.
# We give the user the option to either run the function (to test it), or to
# "register" it (that is, serialize and uploda it) to Globus Compute.

# Since the function to register has been defined, we may now import stuff.
# Start with stdlib imports
import argparse
import pathlib
import sys

# Now do PyPi imports
import globus_compute_sdk

# Find our what we want to do:
argp = argparse.ArgumentParser(
    prog='do_checksum',
    description='Checksum contents of a directory, writing to a file in another directory',
)
argp_subparsers = argp.add_subparsers(
    dest='subparser_name',
)
argp_run = argp_subparsers.add_parser(
    'run',
    help='Run this program',
)
argp_upload = argp_subparsers.add_parser(
    'register',
    help='Register the Function with Globus Compute',
)
argp_run.add_argument(
    'in_dir',
    help='The directory to checksum',
    type=pathlib.Path,
)
argp_run.add_argument(
    'out_dir',
    help='The directory to store the checksum file',
    type=pathlib.Path,
)
args = argp.parse_args()

# Now we know what to do, do it!
if args.subparser_name == 'run':
    # The user has chosen to run the Function locally.

    # Make sure each path is a directory
    if not args.in_dir.is_dir():
        print(f"The input path ({args.in_dir}) must be a directory!")
        sys.exit(1)
    if not args.out_dir.is_dir():
        print(f"The ouptut path ({args.out_dir}) must be a directory!")
        sys.exit(1)

    # Do the work!
    print("Running…")
    do_checksum(
        in_dir=str(args.in_dir),
        out_dir=str(args.out_dir),
    )
    print(
        "Output written to",
        args.out_dir / 'checksums.txt',
    )
    sys.exit(0)
elif args.subparser_name == 'register':
    # The user has chosen to register the Function with Globus Compute.

    # Spawn our Globus Compute client
    # NOTE: Why do we use the Globus Compute SDK, instead of the Globus SDK?
    # Because the Globus Compute SDK has a Globus Auth Native App
    # pre-configured, so it saves us several steps.
    gcc = globus_compute_sdk.Client()

    # Register the function
    do_checksum_uuid = gcc.register_function(do_checksum)
    print(f"The function's UUID is {do_checksum_uuid}.")
    sys.exit(0)
else:
    # If we were not given an option, print a help message
    argp.print_help()
