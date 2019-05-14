#!/bin/bash

# Copyright © 2019 The Board of Trustees of the Leland Stanford Junior
# University.  Licensed under the MIT License; see the LICENSE file for details.

# This is a simple, single-threaded program.  We don't need many resources.
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G

# The transfer will either submit fairly quickly, or die fairly quickly.
#SBATCH --time=0:10:0

# Only email the user if we completely fail.
#SBATCH --mail-type=FAIL

# Load the Globus CLI module.  There are two verisons, one for Python 2.7 and
# one for Python 3.6.  Pick the one depending on which Python you want loaded.
# * py-globus-cli/1.9.0_py27
# * py-globus-cli/1.9.0_py36
module load system py-globus-cli/1.9.0_py36

# We should only have three arguments
if [ $# -ne 3 ]; then
    echo 'ERROR!  The number of arguments should be only 3.'
    exit 1
fi

# Each of the arguments being passed should have been validated in the script
# that scheduled this job.  Let's hope they're still OK!

# Read in the source Globus path
SOURCE_GLOBUS_PATH=$1

# Read in the destination Globus path
DEST_GLOBUS_PATH=$2

# Read in the path where we should put the output file
OUTPUT_JOB_FILE=$3

# Are we logged in to Globus?
output=$(globus whoami >/dev/null 2>&1)
output_code=$?
if [ $output_code -ne 0 ]; then
    echo 'ERROR!  Not logged in to Globus'
    exit 1
fi

# We already checked the destination path.
# We assume that it is still valid.

# Initiate the transfer
# NOTE: Some differences between this and the previous transfer:
# * We enable notifications.  This lets the user know sooner that their data
#   are ready!
# * We skip the activation checks.  The user is not present at this time;
#   if an endpoint is not activated, we will rely on Globus to notify them.
# * We do not do endpoint checks.  We want to allow for the possibility that
#   the data are being transferred to something like a laptop, which might not
#   be online at the precice time the transfer is started.
output=$(globus transfer ${SOURCE_GLOBUS_PATH} ${DEST_GLOBUS_PATH} \
    --recursive --notify on --skip-activation-check \
    --jmespath 'task_id' --format=UNIX \
    2>&1 1>${OUTPUT_JOB_FILE})
output_code=$?
if [ $output_code -ne 0 ]; then
    echo 'ERROR: The transfer of data in could not be started.'
    echo $output
    exit 1
fi

# That's it!
exit 0
