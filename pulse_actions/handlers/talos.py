"""
This module is for the following use case:

 - Talos jobs:

    * Trigger talos jobs twice if they are from PGO build.
"""
import logging

from mozci import query_jobs
from mozci.errors import MissingBuilderError
from mozci.mozci import trigger_talos_jobs_for_build
from mozci.platforms import get_buildername_metadata
from mozci.sources import buildjson

from pulse_actions.utils.misc import filter_invalid_builders

LOG = logging.getLogger(__name__.split('.')[-1])


def on_event(data, message, dry_run):
    """
    Whenever PGO builds are completed in mozilla-inbound or fx-team,
    we trigger the corresponding talos jobs twice.
    """
    # Cleaning mozci caches
    buildjson.BUILDS_CACHE = {}
    query_jobs.JOBS_CACHE = {}
    payload = data["payload"]
    status = payload["status"]
    buildername = payload["buildername"]
    try:
        info = get_buildername_metadata(buildername)
    except MissingBuilderError, e:
        LOG.warning(str(e))
        if not dry_run:
            # We need to ack the message to remove it from our queue
            message.ack()

        return
    revision = payload["revision"]

    if info['build_type'] == "pgo" and \
       info['repo_name'] in ['mozilla-inbound', 'fx-team'] and \
       info['platform_name'] != 'win64':
        # Treeherder can send us invalid builder names
        # https://bugzilla.mozilla.org/show_bug.cgi?id=1242038
        buildername = filter_invalid_builders(buildername)

        if buildername is None:
            if not dry_run:
                # We need to ack the message to remove it from our queue
                message.ack()
            return

        try:

            trigger_talos_jobs_for_build(
                buildername=buildername,
                revision=revision,
                times=2,
                priority=0,
                dry_run=dry_run
            )

            if not dry_run:
                # We need to ack the message to remove it from our queue
                message.ack()

        except Exception, e:
            # The message has not been acked so we will try again
            LOG.warning(str(e))
            raise
    else:
        if not dry_run:
            # We need to ack the message to remove it from our queue
            message.ack()

        LOG.debug("'%s' with status %i. Nothing to be done.",
                  buildername, status)