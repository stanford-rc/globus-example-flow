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
#SBATCH --mail-type=END,FAIL

# Do any work needed to make the Globus CLI available.  For Sherlock, we
# load the Globus CLI module.  There are two verisons, one for Python 2.7 and
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

# Check that our transfer ID is valid, and (if it is) capture the task status.
output=$(globus task show --jmespath status ${transfer_id} 2>&1)
output_code=$?
if [ $output_code -ne 0 ]; then
    echo "ERROR!  The transfer ID ${transfer_id} is not valid."
    echo $output
    exit 1
else
    globus_task_status="${output}"
fi

# Set us up to requeue if we run out of time
do_requeue() {
    scontrol requeue $SLURM_JOBID
    return
}
trap 'do_requeue' SIGUSR1

# Wait for the transfer to complete or fail.

# NOTE: We cannot use `globus task wait` here.  The reason is annoying.
# Even though `globus task wait` will happily wait forever, we cannot wait
# indefinitely.  In order for bash to process signals, we need to have `globus
# task wait` time out.  Then, assuming there are no requeue signals to process,
# we can go right back to running the command.  But, the exit code for timeout
# (1) is the same exit code for HTTP/server failure.
# So, we have to implement this ourselves.

# We previously got the task status when we checked if we had a valid task ID.
while [ $globus_task_status = '"ACTIVE"' ]; do
    # Wait for 30 seconds.  This is good to do at the start of the loop,
    # because the transfer was probably just submitted, and it's unlikely that
    # it completed so quickly.
    sleep 30

    # Pull the status of the task.
    globus_task_status=$(globus task show --jmespath status ${transfer_id} 2>&1)
    output_code=$?
    
    # If the output code is non-zero, say something and exit.
    if [ $output_code -ne 0 ]; then
        echo 'ERROR!  The globus task show command failed.'
        echo "${globus_task_status}"
        exit 1
    fi

    # If the output code is zero, we'll let the loop decide what to do!
done

# Now check the status.  If it's "SUCCEEDED", then we're good!
if [ $globus_task_status = '"SUCCEEDED"' ]; then
    exit 0
fi

echo "Transfer failed.  ${globus_task_status}"
exit 1
