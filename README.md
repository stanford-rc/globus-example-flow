# A Example Pipeline for Unattended Data Transfer and Computation Using Globus

[Globus](https://globus.org) is a platform for high-speed, unattended data
transfer between environments.  An "environment" can be anything, from a
high-performance compute cluster, to cloud services like Amazon S3 and Google
Drive, down to systems like the desktop in your office.

The ability for Globus transfers to be initiated and run in an unattended
way enables the possibility of their integration into pipelines where the
source data, the compute, and the results all live in separate locations.

The scripts in this repository are meant to show how such a pipeline might
look.  Manual intervention is required only to start the pipeline; after that
it runs unattended.  Other than the Globus CLI, the pipeline is written in BASH
script, and does not rely on any other programs, languages, or extensions.  It
is designed for users of [Sherlock](https://www.sherlock.stanford.edu), but the
code in these scripts could easily be adapted to work elsewhere.

# The Environment

The scripts assume that you have the following environment:

![A diagram which shows three major components: Two paths within the same amorphous pool of remote data (an "Inputs" path and an "Outputs" path), and a compute environment.  The compute environment has four pieces: A block of scratch space, a block of user space, a block of compute, and a block of login.  Bi-directional arrows connect the compute to the scratch space, and the compute to the user space.  One-way arrows run from the "Inputs" path to the scratch space, and from the scratch space to the "Outputs" path.  The login block is not connected to anything.](docs/environment.png?raw=true)

The diagram depicts a common compute environment: There are nodes meant for
users to log in, and there are nodes meant for running batch jobs.  SLURM is
used as the job manager.  There is a pool of fast, temporary storage (scratch
space); and a pool of slower, longer-term storage.

Outside of the compute environment, there are two paths on a remote data store,
one path used for source data and one path to store the results.

The scripts in this repository implement the following pipeline (the numbers
match the numbers in the diagram):

1. _Transfer raw data to scratch space._  This is done using Globus Transfer,
   from the raw data's Globus endpoint to the compute environment's endpoint.

2. _Do work._

3. _Copy results to the Globus endpoint._  This is also done using Globus
   Transfer, from the compute environment's endpoint to the endpoint used for
   results storage.

4. _Copy results to local storage._  This is done using a regular copy
   operation.  It is an optional step, and is done only as a backup.

5. _Delete data from scratch space._  This is done to clean up the scratch
   space.

# How To Use

To run this pipeline, you run the main script, `submit.sh`.  It begins the raw
data transfer (part 1 of the pipeline), and then submits SLURM jobs to perform
the other steps of the pipeline:

* `wait_for_transfer.sh` is a job that waits for a Globus transfer to complete.
  It is self-resubmitting, in case the transfer takes a long time to complete.
  Once the transfer completes, the job ends successfully, and the pipeline may
  continue.

  This script is submitted twice, first to monitor the completion of the raw
  data transfer (part 1 of the pipeline), and again to monitor the completion
  of the results transfer (part 3 of the pipeline).

* `do_work.sh` is a job that does the real work (part 2 of the pipeline).  Even
  though this job is submitted by `run.sh`, it will not start until the first
  `wait_for_transfer.sh` job completes successfully.

* `do_transfer.sh` is a job that initiates the Globus transfer of the results
  (part 3 of the pipeline).  It does not start until `do_work.sh` completes
  successfully.

The main script, `submit.sh`, also submits two jobs that do not have batch
scripts:

* The copy of results from scratch space to user space (part 4 of the
  pipeline), which uses a simple `cp` command.  It will not begin until the
  `do_work.sh` job completes successfully.

* The deletion of data in scratch space (cleaning up at the end of the
  pipeline), which uses a simple `rm` command.  It will not begin until the
  `cp` job _and_ the final `wait_for_transfer.sh` job have _both_ completed
  successfully.

The large number of SLURM jobs are used so that you may easily track the
progress of the pipeline.

To support multiple executions of the pipeline, `run.sh` will generate a random
number that will be used in all of the SLURM job names and in all directory
names.  After completing initial validation, `run.sh` will tell you the random
number, and the paths used for temporary data storage.  A directory will also
be created on the results-storage endpoint, to keep the results from this run
separate from other runs.

# Parameters and Customization

The descriptions above leave some open questions.  "What is the raw data?"
"What work is being done?"  "Where do the results go?"  At the top of the
`submit.sh` script, are variables where the answers to those questions may be
filled in.  This means the demo scripts may be used in your own environment, by
only changing a few variables.

In order for this to be a useful example to the Stanford community, here are
the defaults used in this repository:

* The source data are 50 GB of random data, organized in a three-level tree,
  transferred from the [ESnet](http://www.es.net/) [test
  DTN](https://fasterdata.es.net/performance-testing/DTNs/) at CERN.

* The compute environment used is
  [Sherlock](https://www.sherlock.stanford.edu).

* The work being done is a simple checksum:  The source data directory is
  walked, and the `sha1sum` command is run on each file, writing the checksum
  and path to an output file.  As outputs are being written to a single file,
  the checksums are generated serially.

The above defaults should work for any Sherlock user, except you will need to
change the destination to be your own desktop (or another endpoint where you
have write access).

# Copyright, Licensing, and Contributions

The contents of this repository are © 2021 The Board of Trustees of the Leland
Stanford Jr. University.  It is made available under the [MIT License](LICENSE).

Diagrams were created with [Monodraw](https://monodraw.helftone.com).

Contributions are welcome, if they will fix bugs or improve the clarity of the
scripts.  If you would like to customize these scripts for your own
environment, you should fork this repository, and then commit changes there.
You should also update this README, particularly the _Parameters and
Customization_ section, to reflect the changes you made.
