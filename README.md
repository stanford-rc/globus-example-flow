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
