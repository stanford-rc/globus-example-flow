#!/bin/bash

# Copyright © 2019 The Board of Trustees of the Leland Stanford Junior
# University.  Licensed under the MIT License; see the LICENSE file for details.

# This is a simple, single-threaded program.  We don't need many resources.
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G

# Only run for a little bit.  If we run out of time before the transfer is
# done, we will requeue ourselves.
#SBATCH --time=0:15:0
#SBATCH --signal=B:SIGUSR1

# We do support preemption.  If we are preempted, we should be requeued. 
#SBATCH --requeue

# Only email the user if we completely fail.
#SBATCH --mail-type=FAIL

# Load the Globus CLI module.  There are two verisons, one for Python 2.7 and
# one for Python 3.6.  Pick the one depending on which Python you want loaded.
# * py-globus-cli/1.9.0_py27
# * py-globus-cli/1.9.0_py36
module load system py-globus-cli/1.9.0_py36

# We should only have one argument
if [ $# -ne 1 ]; then
    echo 'ERROR!  The number of arguments should be only 1.'
    exit 1
fi

# Read in our transfer ID, using the file from the only argument
transfer_id_file=$1
if [ ! -f ${transfer_id_file} ]; then
    echo "ERROR! ${transfer_id_file} is not a file."
    exit 1
fi
transfer_id=$(cat ${transfer_id_file})

# Check that our transfer ID is valid
output=$(globus task show ${transfer_id} 2>&1)
output_code=$?
if [ $output_code -ne 0 ]; then
    echo "ERROR!  The transfer ID ${transfer_id} is not valid."
    echo $output
    exit 1
fi

# Set us up to requeue if we run out of time
do_requeue() {
    scontrol requeue $SLURM_JOBID
    return
}
trap 'do_requeue' SIGUSR1

# Wait for the transfer to complete or fail
output=$(globus task wait ${transfer_id} 2>&1)
output_code=$?

# Did we exit?  Was it OK?
if [ $output_code -eq 0 ]; then
    exit 0
# Any other result is a failure
else
    echo $output
    exit 1
fi
