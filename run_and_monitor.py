# vim: ts=4 sw=4 et

# This code is part of A Example Pipeline for Unattended Pipelines,
# Data Transfer, and Computation Using Globus.
# https://github.com/stanford-rc/globus-example-flow/tree/flow
# This code provides a way to initiate and monitor the demo.
# It was written by A. Karl Kornel <akkornel@stanford.edu>

# © 2025 The Board of Trustees of the Leland Stanford Junior University
# SPDX-License-Identifier: BSD-3-Clause
# https://opensource.org/license/bsd-3-clause

# What follows is Inline Script metadata, which tools that support PEP 723 can
# use to automatically create an environment that can run the script.
# /// script
# requires-python = ">=3.8"
# dependencies = [
#   "click >=8.2.1",
#   "globus-sdk <4.0, >=3.56.0 ",
# ]
# ///

# This is the code that runs the demo!  It collects inputs, validates them (as
# much as it can), submits the Flow, and monitors the Run.  It outputs log
# entries similar to the Globus web site.

# This code is broken up into four major sections:

# PREPARE FOR USER INPUT
#   In this section, we connect to Globus, fetch the Flow, and prepare our
#   command-line parser based on the default values in the Flow's input schema.
# MAKE SOME VALIDATION FUNCTIONS
#   In this section, we define functions that check all of the parameters of the
#   Flow, before we submit.  We validate:
#   * Source Collection & Path exists
#   * Destination Collection & Path exists
#   * Compute Collection & Path exists
#   * All Collections are either HA or non-HA
#   * Compute Endpoint exists & is online
#   * Function is registered
# MAKE SOME HELPER FUNCTIONS
#   We define a helper function to monitor the progress of the Flow.  It prints
#   an output similar to the Globus web site's Flow Logs page.
# MAIN FUNCTION
#   Our main function is run by Click, after it has parsed all of the
#   command-line arguments.  It does the following:
#   * Perform Collection verifications (just the Collection part)
#   * Perform Function verification
#   * Perform Compute Endpoint verification, giving the user the option to
#     retry if the Compute Endpoint is offline.
#   * Refresh Globus login, if needed
#   * Perform Path verifications
#   If all of that verification works, the user is given an opportunity to
#   cancel.  If the user wishes to continue, they are prompted for a Flow
#   label, then the Flow is submitted.
#   Once a Run has started, the main function calls out to the monitoring
#   helper function.
#   Once the Run is no longer running, we exit!

# There are two required command-line arguments:
# * The Globus Compute Endpoint's UUID
# * The Function's UUID
# All other (non-constant) parts of the Flow's Input Schema can be changed via
# CLI options.

# This code has three constants that you can change:
# * CLIENT_ID: This is the UUID of a Globus Auth Native Client.  The value
#   provided is Stanford Research Computing's, which should work for you!
# * FLOW_UUID: This is the UUID of the Globus Flow that is being run.
#   WARNING: If you change the Flow's Input Schema, you will also need to
#   change this code!
# * TAGS is a set of strings that will be added as tags to the run.
#   NOTE: The tag "karl demo" will be added to the set.  Please do not change
#   this!  It may help track usage of this demo.
# * LOG_SLEEP: When the Flow is running, how long to sleep between checks for
#   new log entries.

# Start with stdlib imports
import dataclasses
import datetime
import enum
import os
import pathlib
import sys
import time
import typing
from typing import Any, Mapping, MutableSet, Self
import uuid

# Now do PyPi imports
import click
import globus_sdk
import globus_sdk.scopes

# Some constants

CLIENT_ID: uuid.UUID = uuid.UUID('e9e6822d-a941-4bd7-8a8c-602bee1da858')
'''The unique ID of our Globus Native Client
'''

FLOW_UUID: uuid.UUID = uuid.UUID('08cc20ad-a96e-445a-8418-c569bdc7117e')
'''The unique ID of the Flow that we are going to run

This may be overridden by setting the EXAMPLE_FLOW_UUID environment variable.
'''

TAGS: set[str] = {
    'flow demo v1',
}

LOG_SLEEP: float = 10.0
'''How long do we sleep between log updates?
'''

if 'EXAMPLE_FLOW_UUID' in os.environ:
    FLOW_UUID = uuid.UUID(os.environ['EXAMPLE_FLOW_UUID'])

# Our Globus clients
globus_app = globus_sdk.UserApp(
    'karl-demo',
    client_id=CLIENT_ID,
)
globus_flows = globus_sdk.FlowsClient(app=globus_app)
globus_flow = globus_sdk.SpecificFlowClient(
    FLOW_UUID,
    app=globus_app,
)
globus_compute = globus_sdk.ComputeClient(app=globus_app)
globus_transfer = globus_sdk.TransferClient(app=globus_app)

# All of the above instances added their default scopes to the Globus App
# already.

# Prepare for user input

# Make a class to represent a Globus Collection
@dataclasses.dataclass(eq=True, frozen=True)
class GlobusCollection:
    uuid: uuid.UUID
    path: pathlib.PurePosixPath

# Make a class to track if we're running HA or not
class RunningHA(enum.Enum):
    UNKNOWN = enum.auto()
    YES = enum.auto()
    NO = enum.auto()

# First, get our Flow and extract the Input Schema
our_flow = globus_flows.get_flow(FLOW_UUID).data
our_schema = our_flow['input_schema']

# From our input schema, extract the defaults
default_source_data = GlobusCollection(
    uuid=uuid.UUID(our_schema['properties']['source_data']['properties']['id']['default']),
    path=pathlib.PurePosixPath(our_schema['properties']['source_data']['properties']['path']['default']),
)
default_cluster_temp = GlobusCollection(
    uuid=uuid.UUID(our_schema['properties']['cluster_temp']['properties']['id']['default']),
    path=pathlib.PurePosixPath(our_schema['properties']['cluster_temp']['properties']['path']['default']),
)
# cluster_compute_endpoint has no default
# function_id has no default
default_destination = GlobusCollection(
    uuid=uuid.UUID(our_schema['properties']['destination']['properties']['id']['default']),
    path=pathlib.PurePosixPath(our_schema['properties']['destination']['properties']['path']['default']),
)
path_prefix = our_schema['properties']['path_prefix']['const']

# With all the info extracted, we can now make our command!
help_text="""A Example Pipeline for Unattended Pipelines, Data Transfer, and Computation Using Globus.

This script is used to prepare a Run of the example Flow, to submit it, and to
monitor the Run's progress.  You need to provide the UUID (unique ID) of a
Globus Compute Endpoint that is running on a cluster, and the UUID of a
Function that has been registered with Globus Compute.

The Python version used to register the Function should match the Python
version used to run the Compute Endpoint.

The source Collection & Path, cluster's Collection & Path, and destination's
Collection & Path are using the defaults encoded in the Flow's Input Schema.
The default source points to 5 GB of publicly-available data, and should not
need to change.

The destination Collection & Path will need to be changed to something else,
such as your own Globus Connect Personal Mapped Collection.

The cluster's Collection points to Stanford SCG cluster Lab space.  You should
change the path to your own Lab directory.  If you do not have access to SCG,
then you'll need to specify a different cluster Collection UUID.

WARNING: There is a relationship between the cluster's Collection & Path, and
the Flow Definition.  This script cannot verify that relationship, so if you
change the cluster Collection, you'll probably need to change the Flow
Definition!
"""
click_cmd = click.Command(
    name=sys.argv[0],
    help=help_text,
    epilog="This script is from https://github.com/stanford-rc/globus-example-flow/tree/flow",
    context_settings={
        'show_default': True,
    },
)
click_cmd.params.append(click.Option(
    param_decls=['--label'],
    type=str,
    help='A label to attach to this run of the Flow',
))
click_cmd.params.append(click.Option(
    param_decls=['--yes'],
    is_flag=True,
    help='Skip the confirmation page; run the Flow immediately',
))
click_cmd.params.append(click.Option(
    param_decls=['--source-uuid'],
    type=click.UUID,
    help='The unique ID of the source data Globus Collection',
    default=default_source_data.uuid,
))
click_cmd.params.append(click.Option(
    param_decls=['--source-path'],
    type=pathlib.PurePosixPath,
    help='The path to the source data on the source data Globus Collection',
    default=default_source_data.path,
))
click_cmd.params.append(click.Option(
    param_decls=['--cluster-temp-uuid'],
    type=click.UUID,
    help='The unique ID of the cluster Collection',
    default=default_cluster_temp.uuid,
))
click_cmd.params.append(click.Option(
    param_decls=['--cluster-temp-path'],
    type=pathlib.PurePosixPath,
    help='The path to a temporary storage location on the cluster Collection',
    default=default_cluster_temp.path,
))
click_cmd.params.append(click.Option(
    param_decls=['--destination-uuid'],
    type=click.UUID,
    help='The unique ID of the destination Collection',
    default=default_destination.uuid,
))
click_cmd.params.append(click.Option(
    param_decls=['--destination-path'],
    type=pathlib.PurePosixPath,
    help='The path to store results on the destination Collection',
    default=default_destination.path,
))
click_cmd.params.append(click.Argument(
    param_decls=['CLUSTER_COMPUTE_ENDPOINT_UUID'],
    type=click.UUID,
))
click_cmd.params.append(click.Argument(
    param_decls=['FUNCTION_UUID'],
    type=click.UUID,
))

# Make some validation functions!

class CollectionInfo(typing.NamedTuple):
    display_name: str
    collection_type: str | None
    is_ha: bool
def lookup_collection(
    target: GlobusCollection,
) -> CollectionInfo | None:
    # Try looking up the Collection.  404s etc. will happen here.
    try:
        collection_lookup = globus_transfer.get_endpoint(target.uuid)
    except Exception as e:
        click.secho('FAILED!', fg="red", bold=True)
        click.echo(str(e))
        collection_lookup = None
    if collection_lookup is None:
        return None

    # Do we have a supported collection type?
    if collection_lookup['entity_type'] not in {
        'GCP_mapped_collection',
        'GCP_guest_collection',
        'GCSv5_mapped_collection',
        'GCSv5_guest_collection',
    }:
        # Raise an error and assume it's HA
        click.secho('FAILED!', fg="red", bold=True)
        click.echo(f"Entity is of unknown type {collection_lookup['entity_type']}")
        collection_type = None
        is_ha = True
    else:
        # If we recognize the entity type, then we'll be able to check if its HA
        collection_type = collection_lookup['entity_type']
        is_ha = collection_lookup['high_assurance']

    # For GCSv5 non-HA Mapped Collections, we have a scope to add.
    if (
        collection_lookup['entity_type'] == 'GCSv5_mapped_collection' and
        collection_lookup['high_assurance'] is False
    ):
        globus_transfer.add_app_data_access_scope(target.uuid)

    # Return our info
    return CollectionInfo(
        display_name=collection_lookup['display_name'],
        collection_type=collection_type,
        is_ha=is_ha,
    )

def lookup_path(
    target: GlobusCollection,
) -> bool | None:
    try:
        stat_results = globus_transfer.operation_stat(
            target.uuid,
            path=str(target.path),
        )
    except Exception as e:
        click.secho('FAILED!', fg="red", bold=True)
        click.echo(str(e))
        stat_results = None
    if stat_results is None:
        return None
    elif stat_results['type'] == 'dir':
        return True
    else:
        click.secho('FAILED!', fg="red", bold=True, nl=False)
        click.echo(f"is a {stat_results['type']}, not a dir")
        return False

class FunctionInfo(typing.NamedTuple):
    name: str
    python_version: str
def lookup_function(
    target: uuid.UUID,
) -> FunctionInfo | None:
    try:
        function_info = globus_compute.get_function(target)
    except Exception as e:
        click.secho('FAILED!', fg="red", bold=True)
        click.echo(str(e))
        function_info = None

    if function_info is None:
        return None
    else:
        return FunctionInfo(
            name=function_info['function_name'],
            python_version=function_info['metadata']['python_version'],
        )

def lookup_compute(
    target: uuid.UUID,
) -> str | None:
    try:
        compute_status = globus_compute.get_endpoint_status(target)
    except Exception as e:
        click.secho('FAILED!', fg="red", bold=True)
        click.echo(str(e))
        compute_status = None

    # If we failed, return None
    # If we are offline, return an empty string
    # Otherwise, return True for online or False for offline
    if compute_status is None:
        return None
    elif compute_status['status'] == 'offline':
        return ''
    else:
        # If we are online, return the display name
        compute_info = globus_compute.get_endpoint(target)
        return compute_info['display_name']

# Make some helper functions

@dataclasses.dataclass(frozen=True)
class LogEntry():
    when: datetime.datetime
    code: str
    state_name: str | None
    @classmethod
    def from_log_entry(
        cls,
        log_entry: Mapping[Any, Any],
    ) -> Self:
        return cls(
            when=datetime.datetime.fromisoformat(log_entry['time']),
            code=log_entry['code'],
            state_name=(None if 'state_name' not in log_entry['details'] else log_entry['details']['state_name']),
        )
    def __str__(self) -> str:
        log_line = f"{self.when}: "
        if self.state_name is not None:
            log_line += f"{self.state_name} - "
        log_line += self.code
        return log_line
def monitor_flow(
    run_id: uuid.UUID,
    start_time: str
) -> bool | None:
    # The Globus SDK does not provide a way to stream log entries.
    # So, we track the timestamp of the most recently-received entry.
    last_log_ts = datetime.datetime.fromisoformat(start_time)

    # BUT, some log entries have duplicate timestamps.  So, make a set for them.
    log_entries: MutableSet[LogEntry] = set()

    # Track the Flow's completion & success
    flow_running = True
    flow_successful: bool | None = False

    # Clear the screen
    click.clear()
    click.echo(f"Follow the Flow run at https://app.globus.org/runs/{run_id}")

    # Start pulling log entries
    while flow_running is True:
        # Fetch the 20 most-recent log updates.
        # If the check fails, then bail out.
        try:
            flow_logs = globus_flows.get_run_logs(
                run_id=run_id,
                limit=20,
                reverse_order=True,
            )
        except Exception as e:
            click.echo(str(e))
            flow_logs = None
        # If we got an error, then kick us out of the loop. 
        if flow_logs is None:
            flow_running = False
            flow_successful = None
            break

        # Iterate over the logs, oldest first
        flow_logs_oldest_first = reversed(list(flow_logs))
        for log_entry in flow_logs_oldest_first:
            # Process the entry into an instance
            entry_obj = LogEntry.from_log_entry(log_entry)

            if last_log_ts > entry_obj.when:
                # If the log is older then the last-received timestamp, skip.
                #click.echo(f"SKIP {entry_obj}")
                continue
            elif last_log_ts == entry_obj.when:
                # It's possible to have multiple logs that have an identical
                # timestamp.  For example, when one step ends & another step
                # begins.  For those cases, check if we've seen an entry.
                if entry_obj not in log_entries:
                    click.echo(entry_obj)
                    log_entries.add(entry_obj)
            else:
                # New items always print
                click.echo(entry_obj)
                last_log_ts = entry_obj.when
                log_entries.add(entry_obj)

            # Have we succeeded or failed?  If yes, we'done!
            if log_entry['code'] in (
                'FlowSucceeded',
                'FlowFailed',
                'FlowCanceled',
            ):
                if log_entry['code'] == 'FlowSucceeded':
                    flow_successful = True
                flow_running = False
                break

        # Sleep a bit before checking again
        if not flow_running:
            time.sleep(LOG_SLEEP)

    # We're done!
    return flow_successful

# Finally, our main function!

def main(**kwargs) -> None:
    # Will we be asking for confirmation before starting the Run?
    get_confirmation = not kwargs['yes']

    # If we are not getting confirmation, make sure we have a label
    flow_label = ''
    if not get_confirmation:
        flow_label = ('' if kwargs['label'] is None else kwargs['label'])
        if len(flow_label) < 1:
            click.echo('--label is required and may not be empty')
            sys.exit(1)
        if len(flow_label) > 64:
            click.echo('Maximum label length is 64 characters')
            sys.exit(1)

    # Make our run parameters based on our inputs
    # This also ensures types are set for everything
    source_data = GlobusCollection(
        uuid=kwargs['source_uuid'],
        path=kwargs['source_path'],
    )
    cluster_temp = GlobusCollection(
        uuid=kwargs['cluster_temp_uuid'],
        path=kwargs['cluster_temp_path'],
    )
    destination = GlobusCollection(
        uuid=kwargs['destination_uuid'],
        path=kwargs['destination_path'],
    )
    cluster_compute_endpoint: uuid.UUID = kwargs['cluster_compute_endpoint_uuid']
    function_id: uuid.UUID = kwargs['function_uuid']

    # Prepare to store a dict of display names
    # And track if we're running HA or not
    display_names: dict[GlobusCollection, str] = dict()
    running_ha = RunningHA.UNKNOWN
    valid_paths: int = 0

    # Add lots of scopes to our Globus App, then (if needed) send the user
    # through a login.
    # For each Collection, check if we need to add a Scope.
    for collection in (source_data, cluster_temp, destination):
        click.secho(f"Looking up Collection {collection.uuid}… ", nl=False)
        collection_lookup_results = lookup_collection(collection)

        # Did we get results, and a collection type?
        if collection_lookup_results is None:
            continue
        if collection_lookup_results.collection_type is None:
            continue

        # We got a collection type, so record the display name.
        click.secho('OK! ', fg='green', nl=False)
        click.echo(f"Found {collection_lookup_results.display_name}")
        display_names[collection] = collection_lookup_results.display_name

    # Validate our Function
    click.echo(f"Looking up Function {function_id}… ", nl=False)
    function_info = lookup_function(function_id)
    if function_info is not None:
        click.secho('OK! ', fg='green', nl=False)
        click.echo(f"Found {function_info.name}")

    # Validate our Compute endpoint
    click.echo(f"Looking up Compute Endpoint {cluster_compute_endpoint}… ", nl=False)
    compute_name = lookup_compute(cluster_compute_endpoint)
    if compute_name is not None:
        while compute_name == '':
            click.secho('OFFLINE', fg='yellow')
            click.pause('Start the Compute Endpoint, then press any key to check again.')
            click.echo('Checking Compute Endpoint… ', nl=False)
            compute_name = lookup_compute(cluster_compute_endpoint)
        click.secho('OK! ', fg='green', nl=False)
        click.echo(f"Found {compute_name}")

    # If needed, obtain additional Globus Consents
    click.echo('Checking Globus Auth…')
    click.echo('(If login is not needed, this will be skipped.)')
    globus_app.login()

    # Check paths
    for collection in (source_data, cluster_temp, destination):
        click.secho(f"Checking Path {collection.path}… ", nl=False)
        path_lookup_results = lookup_path(collection)
        if path_lookup_results is not None:
            if path_lookup_results is True:
                click.secho('OK! ', fg='green')
                valid_paths += 1

    # Final check before user confirmation
    if len(display_names) < 3:
        sys.exit(1)
    if function_info is None:
        sys.exit(1)
    if compute_name is None:
        sys.exit(1)
    if valid_paths < 3:
        sys.exit(1)

    # Display the information about our pending Run
    info_string = f"""Your Flow will be configured as follows…
SOURCE:
    Transfer: {source_data.uuid} ({display_names[source_data]})
        Path: {source_data.path}
COMPUTE:
    Transfer: {cluster_temp.uuid} ({display_names[cluster_temp]})
        Path: {cluster_temp.path}
    Globus Compute:
        Endpoint: {cluster_compute_endpoint} ({compute_name})
        Function: {function_id} ({function_info.name}), Python {function_info.python_version}
DESTINATION:
    Transfer: {destination.uuid} ({display_names[destination]})
        Path: {destination.path}"""
    click.echo(info_string)

    # If needed, get confirmation and a label
    if get_confirmation:
        try:
            click.echo()
            click.confirm('Run the Flow?', abort=True)
        except Exception:
            sys.exit(0)

        while flow_label == '':
            flow_label = click.prompt('Each Flow must have a label.  Enter one now')
            # The prompt automatically re-prompts on no input.
            # But, we must check for a too-long input.
            if len(flow_label) > 64:
                click.secho('Maximum Flow label length is 64 characters', fg='yellow')
                flow_label = ''
    else:
        # If we're skipping confirmation, output the already-provided label
        click.echo(f"Flow Label: {flow_label}")

    # Run the flow!
    click.echo('Submitting Flow run… ', nl=False)
    try:
        submit_result = globus_flow.run_flow(
            label=flow_label,
            tags=list(TAGS | {'karl demo'}),
            body={
                'source_data': {
                    'id': source_data.uuid,
                    'path': str(source_data.path),
                },
                'cluster_temp': {
                    'id': cluster_temp.uuid,
                    'path': str(cluster_temp.path),
                },
                'destination': {
                    'id': destination.uuid,
                    'path': str(destination.path),
                },
                'cluster_compute_endpoint': cluster_compute_endpoint,
                'function_id': function_id,
                'path_prefix': path_prefix,
            },
        )
    except Exception as e:
        click.secho('FAILED!', fg="red", bold=True)
        click.echo(str(e))
        submit_result = None
    if submit_result is None:
        sys.exit(1)
    run_id = uuid.UUID(submit_result['run_id'])
    click.secho('OK! ', fg='green', nl=False)
    click.echo(f"Run ID is {run_id}")
    time.sleep(5)

    # Monitor the flow and report results
    flow_successful = monitor_flow(
        run_id,
        submit_result['start_time'],
    )
    if flow_successful is None:
        click.secho('Flow status unknown!', fg="yellow", bold=True)
        click.echo(f"Continue to follow the Flow run at https://app.globus.org/runs/{run_id}")
    elif flow_successful is True:
        click.secho('Flow complete!', fg="green", bold=True)
    elif flow_successful is False:
        click.secho('Flow failed (or cancelled).', fg="red", bold=True)

    # And that's it!
    return None

# Run our command!
click_cmd.callback = main
click_cmd.main(standalone_mode=True)
