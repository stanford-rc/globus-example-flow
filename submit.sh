#!/bin/bash

# Copyright © 2019 The Board of Trustees of the Leland Stanford Junior
# University.  Licensed under the MIT License; see the LICENSE file for details.

# Load the Globus CLI module.  There are two verisons, one for Python 2.7 and
# one for Python 3.6.  Pick the one depending on which Python you want loaded.
# * py-globus-cli/1.9.0_py27
# * py-globus-cli/1.9.0_py36
module load system py-globus-cli/1.9.0_py36

# Where is our source data?
# (In the example, the source endpoint is d8eb36b6-6d04-11e5-ba46-22000b92c6ec)
# (That is the UUID of the ESnet Read-Only Test DTN at CERN)
SOURCE_ENDPOINT='d8eb36b6-6d04-11e5-ba46-22000b92c6ec'
SOURCE_DIR='/data1/50GB-in-medium-files/'

# Where is our destination?
# (In the example, the destination endpoint is dd2cd454-7369-11e9-8e59-029d279f7e24)
# (That is Karl's work laptop)
DEST_ENDPOINT='dd2cd454-7369-11e9-8e59-029d279f7e24'
DEST_DIR='~'

# Where is the compute?
# (In the example, the compute endpoint is 6881ae2e-db26-11e5-9772-22000b9da45e)
# (That is the UUID of Sherlock's endpoint)
COMPUTE_ENDPOINT='6881ae2e-db26-11e5-9772-22000b9da45e'

# Where is scratch space on the compute?
# (On Sherlock, this is in the personal scratch space)
SCRATCH_PATH=${SCRATCH}

# When doing preemptable tasks, what partition do we use?
# (On Sherlock, this would either be "owners" or "normal)
WAIT_PARTITION=owners

# When doing work, what partition do we use?
# (On Sherlock, this could be a PI partition, or "owners", or "normal")
WORK_PARTITION=owners

##
# BEGIN!
##

# Construct Globus paths, from the endpoint UUID and directory.
SOURCE_GLOBUS_PATH="${SOURCE_ENDPOINT}:${SOURCE_DIR}"
DEST_GLOBUS_PATH="${DEST_ENDPOINT}:${DEST_DIR}"

# Are we logged in to Globus?
output=$(globus whoami >/dev/null 2>&1)
output_code=$?
while [ $output_code -ne 0 ]; do
    echo 'You are not logged in to Globus.  Please use a web browser to log in.'
    globus login --no-local-server
    output=$(globus whoami 2>&1)
    output_code=$?
done
echo 'Logged in to Globus.'

# Are the endpoints activated?
for endpoint_id in $SOURCE_ENDPOINT $DEST_ENDPOINT $SHERLOCK_ENDPOINT; do
    output=$(globus endpoint is-activated ${endpoint_id} 2>&1)
    output_code=$?
    while [ $output_code -ne 0 ]; do
        if [ $output_code -eq 2 ]; then
            echo "ERROR!  The endpoint UUID ${endpoint_id} is not valid!"
            exit 1
        elif [ $output_code -eq 1 ]; then
            echo "WARNING: Endpoint ${endpoint_id} is not ready."
            echo 'Please go to this URL to activate your endpoint:'
            echo "https://app.globus.org/file-manager?origin_id=${endpoint_id}"
            echo "<< Press RETURN to check again, or Control-C to exit. >>"
            read x
        fi
        output=$(globus endpoint is-activated ${endpoint_id} 2>&1)
        output_code=$?
    done
    echo "Endpoint ${endpoint_id} is already activated."
done

# Are the source and destination paths valid?
for path in $SOURCE_GLOBUS_PATH $DEST_GLOBUS_PATH; do
    output=$(globus ls ${path} 2>&1 )
    output_code=$?
    if [ $output_code -ne 0 ]; then
        echo "WARNING: The path ${path} is not ready"
        echo "The path may be invalid, or the endpoint might not be connected."
        echo "Here is what the Globus CLI reported:"
        echo ${output}
        echo "<< Press RETURN to continue execution, or Control-C to exit. >>"
        read x
    else
        echo "Path ${path} is ready"
    fi
done

# Make a directory in scratch space to hold work.
RANDOM_NUMBER=$RANDOM
COMPUTE_INPUT_DIR=${SCRATCH_PATH}/${USER}_${RANDOM_NUMBER}_input
COMPUTE_OUTPUT_DIR=${SCRATCH_PATH}/${USER}_${RANDOM_NUMBER}_output
mkdir ${COMPUTE_INPUT_DIR}
mkdir ${COMPUTE_OUTPUT_DIR}
echo "Using directory ${COMPUTE_INPUT_DIR} to temporarily hold source data"
echo "Using directory ${COMPUTE_OUTPUT_DIR} to temporarily hold results"

# Get the Globus paths for the compute
COMPUTE_INPUT_GLOBUS_PATH="${COMPUTE_ENDPOINT}:${COMPUTE_INPUT_DIR}"
COMPUTE_OUTPUT_GLOBUS_PATH="${COMPUTE_ENDPOINT}:${COMPUTE_OUTPUT_DIR}"
INPUT_JOB_ID="${SCRATCH_PATH}/${USER}_${RANDOM_NUMBER}_inputjob"
OUTPUT_JOB_ID="${SCRATCH_PATH}/${USER}_${RANDOM_NUMBER}_outputjob"

# Let's begin by transferring data
echo 'Starting data transfer to compute…'
output=$(globus transfer ${SOURCE_GLOBUS_PATH} ${COMPUTE_INPUT_GLOBUS_PATH} \
    --recursive --notify off --label "Transfer for ${RANDOM_NUMBER}" \
    --jmespath 'task_id' --format=UNIX \
    2>&1 1>${INPUT_JOB_ID})
output_code=$?
if [ $output_code -ne 0 ]; then
    echo 'ERROR: The transfer of data in could not be started.'
    echo $output
    echo "Cleaning up scratch space…"
    rm -r ${INPUT_JOB_ID} ${COMPUTE_INPUT_DIR} ${COMPUTE_OUTPUT_DIR}
    exit 1
fi

# Time to submit our jobs!

# If a job fails to submit, cancel all the ones we already scheduled.
# Jobs with ID number 0 are not scheduled.
# We walk the array in reverse, killing the last job first, and so on.
declare -a jobid
do_cleanup() {
    for (( i=${#jobid[@]} ; i>=0 ; i-- )); do
        job=${jobid[i]}
        echo "Cancelling SLURM job ${job}…"
        scancel ${job}
    done
    echo "Cancelling Globus transfer…"
    globus task cancel $(cat ${INPUT_JOB_ID})
    globus task wait $(cat ${INPUT_JOB_ID})
    echo "Cleaning up scratch space…"
    rm -r ${INPUT_JOB_ID} ${COMPUTE_INPUT_DIR} ${COMPUTE_OUTPUT_DIR}
    return
}

echo 'Submitting SLURM jobs…'
echo 'JOB ID NUMBERS:'

# Each job has the same set of shell script:
# * Run the command, sending all output to $output, and capture $output_code
#   Each job has a semi-descriptive name.
#   The first job has no dependency; all other jobs depend on the last job in
#   the job ID array.
#   When successful, only output the job ID number; nothing else.
#   Different jobs can be placed in different partitions; all other sbatch
#   parameters are stored in the sbatch script itself.
# * If the `sbatch` failed, clean up the already-scheduled jobs.
#   $output will contain error text, so output it.
# * If the `sbatch` is successful, then $output will contain a job ID.
#   Push that to the end of the job ID list.

# JOB: Monitor transfer of data in
output=$(sbatch --partition ${WAIT_PARTITION} --job-name "${RANDOM_NUMBER} monitor transfer in" \
    --parsable \
    wait_for_transfer.sh ${INPUT_JOB_ID} 2>&1)
output_code=$?
if [ $output_code -ne 0 ]; then
    echo 'ERROR scheduling monitor of transfer in'
    echo $output
    do_cleanup
    exit 1
fi
jobid+=($output)
echo " Monitor transfer in: ${output}"

# JOB: Work on data
output=$(sbatch --partition ${WORK_PARTITION} --job-name "${RANDOM_NUMBER} work" \
    --parsable --dependency afterok:${jobid[-1]} \
    do_work.sh ${COMPUTE_INPUT_DIR} ${COMPUTE_OUTPUT_DIR} 2>&1)
output_code=$?
if [ $output_code -ne 0 ]; then
    echo 'ERROR scheduling work'
    echo $output
    do_cleanup
    exit 1
fi
jobid+=($output)
echo "        Work on data: ${output}"

# JOB: Initiate transfer out
output=$(sbatch --partition ${WORK_PARTITION} --job-name "${RANDOM_NUMBER} initiate transfer out" \
    --parsable --dependency afterok:${work_jobid} \
    do_transfer.sh ${COMPUTE_OUTPUT_GLOBUS_PATH} ${DEST_GLOBUS_PATH} ${OUTPUT_JOB_ID} 2>&1)
output_code=$?
if [ $output_code -ne 0 ]; then
    echo 'ERROR scheduling transfer out'
    echo $output
    do_cleanup
    exit 1
fi
jobid+=($output)
echo "Transfer results out: ${output}"

# JOB: Monitor transfer of data out
output=$(sbatch --partition ${WAIT_PARTITION} --job-name "${RANDOM_NUMBER} monitor transfer out" \
    --parsable --dependency afterok:${jobid[-1]} \
    wait_for_transfer.sh ${OUTPUT_JOB_ID} 2>&1)
output_code=$?
if [ $output_code -ne 0 ]; then
    echo 'ERROR scheduling monitor of transfer out'
    echo $output
    do_cleanup
    exit 1
fi
jobid+=($output)
echo "Monitor transfer out: ${output}"

# JOB: Clean up $SCRATCH
output=$(sbatch --partition ${WORK_PARTITION} --job-name "${RANDOM_NUMBER} cleanup" \
    --parsable --dependency afterok:${jobid[-1]},afterok:${copy_jobid} \
    --wrap "/bin/rm -r ${INPUT_JOB_ID} ${OUTPUT_JOB_ID} ${COMPUTE_INPUT_DIR} ${COMPUTE_OUTPUT_DIR}" \
    2>&1)
output_code=$?
if [ $output_code -ne 0 ]; then
    echo 'ERROR scheduling cleanup'
    echo $output
    do_cleanup
    exit 1
fi
jobid+=($output)
echo "    Clean up scratch: ${output}"

# That's it!
# There is nothing to clean up.  Although we did make some stuff in the
# $SCRATCH_PATH, our last job should clean all those up!
echo 'Work submitted!'
echo 'NOTE: If something goes weird after this point, you will need to clean up the scratch directories yourself.'
exit 0
