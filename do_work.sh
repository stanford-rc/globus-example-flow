#!/bin/bash

# Copyright © 2019 The Board of Trustees of the Leland Stanford Junior
# University.  Licensed under the MIT License; see the LICENSE file for details.

# Our work is single-threaded, and doesn't need many resources.
# Your work will, of course, need more!
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G

# The checksum generation really should not take more than an hour.
#SBATCH --time=1:00:0

# Only email the user if we completely fail.
#SBATCH --mail-type=FAIL

# We should only have two arguments
if [ $# -ne 2 ]; then
    echo 'ERROR!  The number of arguments should be only 2.'
    exit 1
fi

# Each argument should be a directory
for arg in $1 $2; do
    if [ ! -d ${arg} ]; then
        echo 'ERROR!  ${arg} is not a directory.'
        exit 1
    fi
done

# Move into the input directory
cd $1

# Now, do work!
# For demo purposes, our work will be simple.
# We'll make a checksum of each file in the input directory.
# We'll use `find` to do the directory traversal.
# Since we have nothing else to do, we'll let `find` take over!
exec find . -depth -not -type d -exec sha1sum --binary {} \; > $2/checksums
