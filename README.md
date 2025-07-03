# A Example Pipeline for Unattended Pipelines, Data Transfer, and Computation Using Globus

[Globus](https://globus.org) is a platform for *high-speed, unattended data
transfer* between environments.  An "environment" can be anything, from a
high-performance compute cluster, to cloud services like Amazon S3 and Google
Drive, to systems like the desktop in your office or the workstation connected
to your lab instrument.  **Globus Transfer** is what enables data transfer
and sharing between environments.

The ability for Globus transfers to be initiated and run in an unattended way
enables the possibility of their integration into pipelines where the source
data, the compute, and the results all live in separate locations.  Indeed,
**Globus Flows** lets us create such a pipeline, and have Globus manage its
execution, without needing to run a workflow engine locally.

But what about compute?  **Globus Compute** is a *Function-as-a-Service*
product, where you can upload Python code (or containers) for execution on a
*Compute Endpoint* running on your HPC.

The files in this repository demonstrate a Globus Flow that uses Globus
Transfer to move data, and Globus Compute to process it, ultimately delivering
results to your desktop.  It is designed to be adaptable to your own compute
environment, even if "compute environment" means a high-powered workstation.

The "compute" performed in the demonstration is to checksum the contents of a
directory tree, and output a text file containing file names and their
checksums.

Manual intervention is required only to start the Flow (the pipeline); after
that it runs unattended.  The Flow defininition is written in [Amazon States
Language](https://states-language.net), which Amazon created for their [AWS
Step
Functions](https://docs.aws.amazon.com/step-functions/latest/dg/welcome.html)
service.  The Compute Function is written in Python.  Python code is also
provided to "register" the Function with Globus Compute, and to manage Run
validation and submission.

The [demonstration
Flow](https://app.globus.org/flows/08cc20ad-a96e-445a-8418-c569bdc7117e) is
available to be run by anyone who can log in to Globus.  However, the
demonstration Flow is coded to work on the [Stanford SCG Bioinformatics
Cluster](https://login.scg.stanford.edu).  If you want the Flow to work with
your cluster, you will need to adjust it.  The Function code should be portable
across clusters.

# How to Use (on SCG)

For reasons that will be explained later, the Globus Flow used in this demo
must be customized for the environment that will be running Globus Compute.

We begin with an example that will work for folks who are using the [Stanford
SCG Bioinformatics Cluster](https://login.scg.stanford.edu).  The
publicly-available Flow Definition is designed for use with SCG, and so users
only need to register the demo Compute Function and start a Compute Endpoint.
You can then proceed with running the Flow.

All of this will be done within a Python virtualenv.  The steps are:

1. Create a Python Virtualenv

2. Register the Function with Globus Compute

3. Configure a Globus Compute Endpoint

4. Run the Flow

NOTE: On SCG, Python versions are provided through Lmod modules.  Every example
assumes that you have already loaded the `python/3.11.1` module.

## Create a Python Virtualenv

To begin, we need a Python virtualenv on the cluster.  The virtualenv needs the
`globus-compute-sdk` package (to support Function registration), and the
`globus-compute-endpoint` package (for the Globus Compute Endpoint software).

This asciicast demonstrates the creation of the venv and the installation of the
packages:

[![asciicast](https://asciinema.org/a/725655.svg)](https://asciinema.org/a/725655)

Here are the commands to run, to reproduce the demo in your own session:

```
# Create a venv for our Compute Endpoint and Compute Function
mkdir globus_compute_endpoint
/scg/apps/software/python/3.11.1/bin/python -m venv --upgrade-deps globus_compute_endpoint

# Activate the venv, and confirm `python` is pointing to the venv's Python.
cd globus_compute_endpoint
. bin/activate
which python
python -V

# Install the Globus Compute SDK and the Globus Compute Endpoint packages
pip install globus-compute-sdk globus-compute-endpoint
```

The venv is now ready to use.

## Register the Function with Globus Compute

With our venv ready, the first thing to do is to register the Function.  This
asciicast demonstrates the registration of the Function:

[![asciicast](https://asciinema.org/a/725656.svg)](https://asciinema.org/a/725656)

The demonstration assumes that you just logged in to SCG, and that you need to
re-activate the venv.  Here are the commands to run, to reproduce the demo in
your own session:

```
# If needed, activate the venv
cd globus_compute_endpoint
. bin/activate
which python
python -V

# Download the `function.py` script from the GitHub repo.
curl -L -o function.py https://github.com/stanford-rc/globus-example-flow/raw/refs/heads/flow/function.py

# Run the script, with instructions to register the Compute Function.
# This might prompt you to authenticate.
python function.py register
```

Once the `function.py` script completes, you may delete the script.  Functions
are not tied to individual users (though they are tied to a particular Python
version), and they may be used multiple times.

In the above example, the Compute Function has been registered and assigned
UUID `e381b154-abe5-48d2-956f-4c61ee02adf0`.  We will need this UUID when it is
time to run the Flow.

## Configure a Globus Compute Endpoint

Next, we configure the Globus Compute Endpoint.  This involves telling the
Compute Endpoint about our job scheduler, and how jobs should be submitted.

This asciicast demonstrates the creation and configuration of the Compute
Endpoint:

[![asciicast](https://asciinema.org/a/725819.svg)](https://asciinema.org/a/725819)

The demonstration assumes that you just logged in to SCG, and that you are a
member of the Full-Tier `ruthm` Lab.  You should change the SLURM account to
your own PI's SUNetID; and if your Lab is a Free-Tier Lab, you should change
the SLURM partition from `batch` to `nih_s10`.

The demo stores the Compute Endpoint configuration in the
`globus_compute_demo` directory.  Normally configuration is stored in the
hidden `.globus_compute` directory in your home directory; the explicit
configuration path makes cleanup easier.

Here are the commands to run, to reproduce the demo in your own session:

```
# If needed, activate the venv
cd globus_compute_endpoint
. bin/activate
which python
python -V

# Create a new Compute Endpoint
globus-compute-endpoint \
--config-dir=/home/akkornel/globus_compute_demo/config \
configure --display-name "Globus Flow Demo on SCG" globus_flow_demo

# Edit the file at path `config/globus_flow_demo/config.yaml`,
# configuring the provider as follows:

provider:
  type: SlurmProvider
  partition: batch
  account: ruthm
  launcher:
    type: SrunLauncher

# After saving the `config.yaml` file, start the Endpoint
globus-compute-endpoint --config-dir=/home/akkornel/globus_compute_demo/config start globus_flow_demo

# List all endpoints, confirming that the Endpoint is started
globus-compute-endpoint --config-dir=/home/akkornel/globus_compute_demo/config list
```

In the above example, the Compute Endpoint has been registered and assigned
UUID `b72ee151-a5d9-4cfc-97b3-86e0664730b2`.

## Run the Flow

With the Function registered and Compute Engine running, we may now run the
Flow!

This asciicast demonstrates running the Flow:

[![asciicast](https://asciinema.org/a/725821.svg)](https://asciinema.org/a/725821)

In the above example, we see…

* The Compute Endpoint is still running, and we have its UUID
  (`b72ee151-a5d9-4cfc-97b3-86e0664730b2`).

* We remembered the UUID of the Compute Function that we registered (it is
  `e381b154-abe5-48d2-956f-4c61ee02adf0`).

* On the cluster, we are storing files temporarily at path `/ruthm/akkornel` on
  the [SRCC SCG Lab
  Storage](https://app.globus.org/file-manager/collections/3257fc54-9071-42fa-88ca-6097b2679b9a/overview)
  Collection.  The Collection's UUID is part of the Flow Definition, and so is
  not specified on the command line.

* We are sending the results to a path in Karl's home directory in the [SRCC SCG
  Home](https://app.globus.org/file-manager/collections/2e23906b-0608-45bb-b344-393b8706e862/overview)
  Collection.  The Collection's UUID is `2e23906b-0608-45bb-b344-393b8706e862`.

All that's left is to run the script!  The script logs us in to Globus,
validates the information we provided, asks for final confirmation (and a label
for the Run), and then runs the Flow.

Once the Flow run is submitted, the script shows us the progress of the Run's
progression through each state of the Flow.  (Read the section on *The Flow
Definition* for more information about the Flow's states.)

Once the Run is complete, the script exits, and we can see the checksums file
has been uploaded.

Meanwhile, monitoring the SLURM queue shows the Globus Compute job in queue and
running, as we can see in this asciicast:

[![asciicast](https://asciinema.org/a/725822.svg)](https://asciinema.org/a/725822)

Here are the commands to run, to reproduce the demo in your own session:

```
# If needed, activate the venv
cd globus_compute_endpoint
. bin/activate
which python
python -V

# Download the script that will submit the Flow run
# Also, install the Python packages needed by the script
pip install globus-sdk click
curl -L -o run_and_monitor.py https://github.com/stanford-rc/globus-example-flow/raw/refs/heads/flow/run_and_monitor.py

# Make a directory to hold the results of the Compute Function
mkdir results

# Confirm the Compute Endpoint is still running
globus-compute-endpoint --config-dir /home/akkornel/globus_compute_demo/config list 

# Run the Flow, and monitor the Run.  Note that you need to provide:
# * A path on SCG Lab storage, to hold the data temporarily
# * A Collecton UUID and path to receive the results
# * The UUID of your Compute Endpoint
# * The UUID of your Compute Function
python run_and_monitor.py
--cluster-temp-path /ruthm/akkornel/ \
--destination-uuid 2e23906b-0608-45bb-b344-393b8706e862 \
--destination-path /akkornel/globus_compute_endpoint/results/ \
b72ee151-a5d9-4cfc-97b3-86e0664730b2 \
e381b154-abe5-48d2-956f-4c61ee02adf0

# Go into the results directory, and confirm the Run created a directory
cd results
ls

# Go into the directory created by the Run
cd karl-demo*

# Confirm we have a checksums file, and examine it
ls
head checksums.txt
```

With the above steps, an SCG user should be able to run this demo themselves!

If someone not on SCG wanted to run the demo, they would be required to update
at least the Flow Definition.  So, before giving an example of that, it is
necessary to explain the environment which the demo uses, and how to modify it.

# The Environment

The scripts assume that you have the following environment:

![A diagram which shows three major components: A desktop system, an amorphous pool of remote data, and a cluster that contains a login node, storage, and compute node.](docs/environment1.png?raw=true)

The diagram depicts a common HPC cluster: There are nodes meant for
users to log in (login nodes), and there are nodes meant for running batch jobs
(compute nodes).  Users connect to login nodes and submit batch jobs to a job
scheduler.  The scheduler receives batch jobs and runs them on compute nodes.
There is also a space for data storage.

Outside of the cluster, there is a desktop (which you are using,
and which will be the destination for your results), and a pool of remote data
(the source data).

The Flow in this repository implements the following pipeline (the numbers
match the numbers in the diagram):

1. _Transfer source data to compute._  This is done using Globus Transfer,
   from the source data's Collection to the cluster's Collection.

2. _Submit compute job._  Once transfer is complete, the Flow asks the Globus
   Compute Endpoint to do some work on the source data.  The Compute Endpoint
   submits a batch job to a compute node.

3. _Do work._  On the compute node, work is performed.  In this demo, all of the
   downloaded files are checksummed, and the checksums written to a text file.

4. _Copy results to the desktop._  This is also done using Globus Transfer,
   from the cluster's Collection to a Globus Connect Personal
   endpoint running on your desktop.

Not shown in the diagram are several directory-creation and -deletion steps:

* Before Step 1 (transfer source data), empty directories are created on the
  cluster's storage, and a directory is created on the desktop to hold the
  results.

* After Step 4 (copy results), all directories on the cluster's
  storage—including the copy of the source data—are deleted.

Also, if the Flow encounters any errors, it cleans up everything that had been
created up to the point of the failure.  The intent is to not leave anything
behind, other than the results on the Desktop.  The exception is if the Flow is
cancelled: Cancelling the Flow also cancels all cleanup steps.

In the example environment, the Globus Compute (Single-User) Endpoint is
running on a Login Node.  For this to work, the user must have taken the action
to start the Compute Endpoint.  The user could have also started the Globus
Compute Endpoint inside its own batch job.

With the **Globus Compute Multi-User Endpoint**, the Login Node is no longer
required, as can be seen in this example environment:

![A diagram which shows three major components: A desktop system, an amorphous pool of remote data, and a cluster that contains a login node, compute endpoint, storage, and compute node.](docs/environment2.png?raw=true)

In this environment, the cluster administrator has provisioned a Globus Compute
Multi-User Endpoint.  The Compute Endpoint has been configured to use the job
scheduler, allowing the user to do work without needing to connect to the login
node.  User authentication is handled at all stages by Globus Auth, in
connection with your local Identity Provider.

# Parameters and Customization

## The Input Schema

The descriptions above leave some open questions.  "What is the raw data?"
"What work is being done?"  "Where do the results go?"  These questions are
answered by the Input Schema.

The [input schema](schema.json) lists all of the variables that must be
provided when a Run is started.  You need to provide three Globus Collections
(each having a UUID and a path), a Globus Compute Endpoint UUID, and a Globus
Compute Function UUID.  This section talks about all these inputs.

The first Collection is `source_data`.  This points to the path
`/5GB-in-small-files/` in the [ESnet CERN DTN (Anonymous read-only
testing)](https://app.globus.org/file-manager/collections/722751ce-1264-43b8-9160-a9272f746d78/overview)
Collection.  This path contains 1,875 files and 651 directories, and takes
approximately 4.66 GiB of space on disk.  This dataset was chosen as one that
does not take up much space, and balances Globus' parallelization ability with
the latency that comes from small files (average file size is 2.55 MiB).

The `source_data` is available for anyone to access, and should not need to be
changed.

The second Collection is `cluster_temp`.  This points to the path
`/ruthm/akkornel` on [SRCC SCG Lab Storage](https://app.globus.org/file-manager/collections/3257fc54-9071-42fa-88ca-6097b2679b9a/overview), which points to `/labs` in the [Stanford SCG Bioinformatics
Cluster](https://login.scg.stanford.edu).  If you have an account on SCG, then
you should only need to change `cluster_temp.path` to point to your own path;
it should be OK to change this during Flow submission, so you should not need
to change the Input Schema.

*If you want to point `cluster_temp` to a different cluster, you will need to
also change the Flow Definition.*  That will be described in the next section.

The final Collection is `destination`, which points to Karl's work laptop.
This should definitely be changed.  You can either change the Input Schema, or
you can change the values during Flow submission.

Next is `cluster_compute_endpoint`.  This is the UUID of the Globus Compute
Endpoint that will be running the checksum job.  See the *Compute Endpoint*
section for more information.

Next is `function_id`, which is the UUID of the Globus Compute Function that
will be doing the checksum work.  The [function.py](function.py) script
can be used to register this.  *Make sure you use the same Python version to
register the script, as you use to run the Compute Endpoint.*

Finally, the Input Schema contains the parameter `path_prefix`.  This string is
added to the directories that the Flow creates, along with the Run's unique ID,
and helps to ensure uniqueness.  The parameter is set to a fixed value in the
Input Schema, so it should be left alone.

To summarize:

* Everyone should change the `destination`, either in the Input Schema or
  during Flow submission, to point to their own destination.

* SCG users could customize `cluster_temp.path` to their own lab space.
  Non-SCG users will need to change `cluster_temp` completely, and will also
  need to change the Flow Definition.

* Everyone should change `cluster_compute_endpoint` and `function_id` during
  Flow submission, pointing to their own Compute Endpoint and Compute Function.

* The other parameters can be left alone.

## The Flow Definition

A Globus Flow is a state machine.  Other than the start and end states, each
state does some sort of work: It might set some variables, take an action (like
"create directory"), or make a decision about what to do next.  Each state has
access to the information from the Input Schema, information produced by
already-executed states, and information about the Run itself (like the Run's
unique ID).  [Read more about authoring
Flows](https://docs.globus.org/api/flows/authoring-flows/).

The following diagram shows the Flow in graphic form.  You may wish to open the
image separately to view it at full size.

![A diagram showing the states of the Flow, and transitions from state to state.](docs/flow.png?raw=true)

(The diagram was produced using the [Flows
IDE](https://globus.github.io/flows-ide/), version 1.4.7-beta.  To reproduce
the diagram, open the Flows IDE and paste in the contents of
[definition.json](definition.json?raw=true).)

The Flow has 15 states, two of which (`EndFailure` and `EndSuccess`) are
terminal.  `Compute_Paths` is the starting state.  The states are split into
several categories:

1. **Compute Paths**: This is the `Compute_Paths` and
   `Compute_Function_Arguments` states.  This takes our inputs and computes all
   of the different paths for where files will be stored.

2. **Make Directories**: This is `MakeDir_Compute`,
   `MakeDir_Compute_Input`, `MakeDir_Compute_Output`, and
   `MakeDir_Results`, to create directories for temporary storage and
   results storage.

3. **Copy Inputs**: This is `Copy_Inputs_To_Compute`, a simple Transfer.

4. **Compute**: This is `Do_Compute`, which calls Globus Compute to do
   the checksumming.

5. **Copy Results**: This is `Copy_Results_To_Dest`, another simple Transfer.

6. **Clean Up**: This is `Cleanup_Compute`, which is always run; and
   `Cleanup_Results`, which is only run if some part of the Flow fails.

Normal operation proceeds from state to state in the order listed above.  Every
state (except for the `End` states) catches exceptions, transitioning to an
approriate `Cleanup` state depending on the nature of the exception:
`Cleanup_Results` on an exception in any state from Categories 1 through 4;
`Cleanup_Compute` is run regardless.

The Flow ends in the `End` state, which goes to either `EndFailure` or
`EndSuccess`, depending on if there was a problem with the Run.

Special notice must be given to the `Compute_Function_Arguments` state.  The
Compute Function needs to know the absolute path to the `cluster_temp` storage.
Globus Collections can have base paths, so to convert a Collection path into an
absolute path, you typically need to add a prefix.  The
`Compute_Function_Arguments` state is responsible for adding this prefix.

**If you change `cluster_temp` in the Input Schema, you must also change the
definition of `in_dir` and `out_dir` in the `Compute_Function_Arguments` state.**

Take the current Flow Definition as an example.  In the current Flow
Definition, `cluster_temp` points to [SRCC SCG Lab
Storage](https://app.globus.org/file-manager/collections/3257fc54-9071-42fa-88ca-6097b2679b9a/overview).
The base path of this Mapped Collection is `/labs`, so to get an absolute path
that works on ths cluster, you must start with `/labs` and then add the
`cluster_temp.path`.  So, that is what happens in the
`Compute_Function_Arguments` state.

To Summarize:

* Most of the Flow states will work in your situation, with one exception.

* The `Compute_Function_Arguments` state will need to be customized to your
  cluster.

* If you are using this Flow with [SRCC SCG Lab
  Storage](https://app.globus.org/file-manager/collections/3257fc54-9071-42fa-88ca-6097b2679b9a/overview),
  then you do not need to change anything in the Flow Definition.  Though you
  will need to specify a different `cluster_temp.path`.

# Copyright, Licensing, and Contributions

The contents of this repository are © 2025 The Board of Trustees of the Leland
Stanford Jr. University.  It is made available under the [BSD 3-Clause
License](LICENSE).

Diagrams were created with [Monodraw](https://monodraw.helftone.com).

Contributions are welcome, if they will fix bugs or improve the clarity of the
scripts.  If you would like to customize these scripts for your own
environment, you should fork this repository and commit changes there.
You should also update this README, particularly the _Parameters and
Customization_ section, to reflect the changes you made.
