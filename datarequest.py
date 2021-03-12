# -*- coding: utf-8 -*-
"""Functions to handle data requests."""

__copyright__ = 'Copyright (c) 2019-2020, Utrecht University'
__license__   = 'GPLv3, see LICENSE'
__author__    = ('Lazlo Westerhof, Jelmer Zondergeld')

import json
import re
from collections import OrderedDict
from datetime import datetime
from enum import Enum

import jsonschema
from genquery import AS_DICT, row_iterator

import avu_json
import mail
from util import *
from util.query import Query

__all__ = ['api_datarequest_browse',
           'api_datarequest_schema_get',
           'api_datarequest_submit',
           'api_datarequest_get',
           'api_datarequest_is_owner',
           'api_datarequest_is_bod_member',
           'api_datarequest_is_dmc_member',
           'api_datarequest_is_datamanager',
           'api_datarequest_is_reviewer',
           'api_datarequest_preliminary_review_submit',
           'api_datarequest_preliminary_review_get',
           'api_datarequest_datamanager_review_submit',
           'api_datarequest_datamanager_review_get',
           'api_datarequest_assignment_submit',
           'api_datarequest_assignment_get',
           'api_datarequest_review_submit',
           'api_datarequest_reviews_get',
           'api_datarequest_evaluation_submit',
           'api_datarequest_feedback_get',
           'api_datarequest_dta_post_upload_actions',
           'api_datarequest_signed_dta_post_upload_actions',
           'api_datarequest_data_ready']


###################################################
#                    Constants                    #
###################################################

DATAREQUESTSTATUSATTRNAME = "status"

YODA_PORTAL_FQDN  = config.yoda_portal_fqdn

JSON_EXT          = ".json"

SCHEMACOLLECTION  = constants.UUSYSTEMCOLLECTION + "/datarequest/schemas/youth-0"
SCHEMA            = "schema"
UISCHEMA          = "uischema"

GROUP_DM          = "datarequests-research-datamanagers"
GROUP_DMC         = "datarequests-research-data-management-committee"
GROUP_BOD         = "datarequests-research-board-of-directors"

DRCOLLECTION      = "home/datarequests-research"
DATAREQUEST       = "datarequest"
PR_REVIEW         = "preliminary_review"
DM_REVIEW         = "datamanager_review"
REVIEW            = "review"
ASSIGNMENT        = "assignment"
EVALUATION        = "evaluation"
FEEDBACK          = "feedback"
DTA_FILENAME      = "dta.pdf"
SIGDTA_FILENAME   = "dta_signed.pdf"


###################################################
#          Datarequest status functions           #
###################################################

# List of valid datarequest statuses
class status(Enum):
    IN_SUBMISSION                     = 'IN_SUBMISSION'
    SUBMITTED                         = 'SUBMITTED'
    PRELIMINARY_ACCEPT                = 'PRELIMINARY_ACCEPT'
    PRELIMINARY_REJECT                = 'PRELIMINARY_REJECT'
    PRELIMINARY_RESUBMIT              = 'PRELIMINARY_RESUBMIT'
    DATAMANAGER_ACCEPT                = 'DATAMANAGER_ACCEPT'
    DATAMANAGER_REJECT                = 'DATAMANAGER_REJECT'
    DATAMANAGER_RESUBMIT              = 'DATAMANAGER_RESUBMIT'
    UNDER_REVIEW                      = 'UNDER_REVIEW'
    REJECTED_AFTER_DATAMANAGER_REVIEW = 'REJECTED_AFTER_DATAMANAGER_REVIEW'
    RESUBMIT_AFTER_DATAMANAGER_REVIEW = 'RESUBMIT_AFTER_DATAMANAGER_REVIEW'
    REVIEWED                          = 'REVIEWED'
    APPROVED                          = 'APPROVED'
    REJECTED                          = 'REJECTED'
    RESUBMIT                          = 'RESUBMIT'
    DTA_READY                         = 'DTA_READY'
    DTA_SIGNED                        = 'DTA_SIGNED'
    DATA_READY                        = 'DATA_READY'


# List of valid datarequest status transitions (source, destination)
status_transitions = [(status(x),
                       status(y))
                      for x, y in [('IN_SUBMISSION',        'SUBMITTED'),
                                   ('SUBMITTED',            'PRELIMINARY_ACCEPT'),
                                   ('SUBMITTED',            'PRELIMINARY_REJECT'),
                                   ('SUBMITTED',            'PRELIMINARY_RESUBMIT'),
                                   ('PRELIMINARY_ACCEPT',   'DATAMANAGER_ACCEPT'),
                                   ('PRELIMINARY_ACCEPT',   'DATAMANAGER_REJECT'),
                                   ('PRELIMINARY_ACCEPT',   'DATAMANAGER_RESUBMIT'),
                                   ('DATAMANAGER_ACCEPT',   'UNDER_REVIEW'),
                                   ('DATAMANAGER_ACCEPT',   'REJECTED_AFTER_DATAMANAGER_REVIEW'),
                                   ('DATAMANAGER_ACCEPT',   'RESUBMIT_AFTER_DATAMANAGER_REVIEW'),
                                   ('DATAMANAGER_REJECT',   'UNDER_REVIEW'),
                                   ('DATAMANAGER_REJECT',   'REJECTED_AFTER_DATAMANAGER_REVIEW'),
                                   ('DATAMANAGER_REJECT',   'RESUBMIT_AFTER_DATAMANAGER_REVIEW'),
                                   ('DATAMANAGER_RESUBMIT', 'UNDER_REVIEW'),
                                   ('DATAMANAGER_RESUBMIT', 'REJECTED_AFTER_DATAMANAGER_REVIEW'),
                                   ('DATAMANAGER_RESUBMIT', 'RESUBMIT_AFTER_DATAMANAGER_REVIEW'),
                                   ('UNDER_REVIEW',         'REVIEWED'),
                                   ('REVIEWED',             'APPROVED'),
                                   ('REVIEWED',             'REJECTED'),
                                   ('REVIEWED',             'RESUBMIT'),
                                   ('APPROVED',             'DTA_READY'),
                                   ('DTA_READY',            'DTA_SIGNED'),
                                   ('DTA_SIGNED',           'DATA_READY')]]


def status_transition_allowed(ctx, current_status, new_status):
    transition = (current_status, new_status)

    return transition in status_transitions


def status_set(ctx, request_id, status):
    """Set the status of a data request

    :param ctx:        Combined type of a callback and rei struct
    :param request_id: Unique identifier of the data request
    :param status:     The status to which the data request should be set
    """
    metadata_set(ctx, request_id, "status", status.value)


def status_get_from_path(ctx, path):
    """Get the status of a datarequest from a path

    :param ctx:  Combined type of a callback and rei struct
    :param path: Path of the datarequest collection

    :returns: Status of given data request
    """
    temp, _ = pathutil.chop(path)
    _, request_id = pathutil.chop(temp)

    return status_get(ctx, request_id)


def status_get(ctx, request_id):
    """Get the status of a data request

    :param ctx:        Combined type of a callback and rei struct
    :param request_id: Unique identifier of the data request

    :raises UUError: Status could not be retrieved

    :returns: Status of given data request
    """
    # Construct filename and filepath
    coll_path = "/{}/{}/{}".format(user.zone(ctx), DRCOLLECTION, request_id)
    file_name = DATAREQUEST + JSON_EXT
    file_path = "{}/{}".format(coll_path, file_name)

    # Retrieve current status
    rows = row_iterator(["META_DATA_ATTR_VALUE"],
                        ("COLL_NAME = '{}' AND DATA_NAME = '{}' AND META_DATA_ATTR_NAME = 'status'").format(coll_path, file_name),
                        AS_DICT, ctx)
    if rows.total_rows() == 1:
        return status[list(rows)[0]['META_DATA_ATTR_VALUE']]
    # If no status is set, set status to IN_SUBMISSION (this is the case for newly submitted data
    # requests)
    elif rows.total_rows() == 0:
        return status.IN_SUBMISSION
    else:
        raise error.UUError("Could not unambiguously determine the current status for datarequest <{}>".format(request_id))


###################################################
#                 Helper functions                #
###################################################

def metadata_set(ctx, request_id, key, value):
    """Set an arbitrary metadata field on a data request

    :param ctx:        Combined type of a callback and rei struct
    :param request_id: Unique identifier of the data request
    :param key:        Key of the metadata field
    :param value:      Value of the metadata field
    """

    # Construct path to the collection of the data request
    coll_path = "/{}/{}/{}".format(user.zone(ctx), DRCOLLECTION, request_id)

    # Add delayed rule to update data request status
    response_status = ""
    response_status_info = ""
    ctx.requestDatarequestMetadataChange(coll_path, key,
                                         value, "0", response_status,
                                         response_status_info)

    # Trigger the processing of delayed rules
    ctx.adminDatarequestActions()


@api.make()
def api_datarequest_is_owner(ctx, request_id):
    """Check if the invoking user is also the owner of a given data request

    This function is a wrapper for datarequest_is_owner.

    :param ctx:        Combined type of a callback and rei struct
    :param request_id: Unique identifier of the data request
    :type request_id: str

    :returns: `True` if ``user_name`` matches that of the owner of the data request with id ``request_id``, `False` otherwise
    :rtype: bool
    """

    is_owner = False

    try:
        is_owner = datarequest_is_owner(ctx, request_id, user.name(ctx))
    except error.UUError as e:
        return api.Error('logical_error', 'Could not determine datarequest owner: {}'.format(e))

    return is_owner


def datarequest_is_owner(ctx, request_id, user_name):
    """Check if the invoking user is also the owner of a given data request

    :param ctx:        Combined type of a callback and rei struct
    :param request_id: Unique identifier of the data request
    :type request_id: str
    :param user_name: Username of the user whose ownership is checked
    :type user_name: str

    :raises UUError: It was not possible to unambiguously determine the owner of the data request (either 0 or > 1 results for the data request)
    :return: `True` if ``user_name`` matches that of the owner of the data request with id ``request_id``, `False` otherwise
    :rtype: bool
    """
    # Construct path to the collection of the datarequest
    coll_path = "/{}/{}/{}".format(user.zone(ctx), DRCOLLECTION, request_id)

    # Query iCAT for the username of the owner of the data request
    rows = row_iterator(["DATA_OWNER_NAME"],
                        ("DATA_NAME = '{}' and COLL_NAME like '{}'".format(DATAREQUEST + JSON_EXT, coll_path)),
                        AS_DICT, ctx)

    # If there is not exactly 1 resulting row, something went terribly wrong
    if rows.total_rows() != 1:
        raise error.UUError("No or ambiguous data owner")

    # There is only a single row containing the owner of the data request
    return list(rows)[0]["DATA_OWNER_NAME"] == user_name


@api.make()
def api_datarequest_is_reviewer(ctx, request_id):
    return datarequest_is_reviewer(ctx, request_id)


def datarequest_is_reviewer(ctx, request_id):
    """Check if a user is assigned as reviewer to a data request

    :param ctx:        Combined type of a callback and rei struct
    :param request_id: Unique identifier of the data request

    :returns: Boolean indicating if the user is assigned as reviewer
    """
    # Force conversion of request_id to string
    request_id = str(request_id)

    # Get username
    username = user.name(ctx)

    # Reviewers are stored in one or more assignedForReview attributes on
    # the data request, so our first step is to query the metadata of our
    # data request file for these attributes

    # Declare variables needed for retrieving the list of reviewers
    coll_path = "/{}/{}/{}".format(user.zone(ctx), DRCOLLECTION, request_id)
    reviewers = []

    # Retrieve list of reviewers
    rows = row_iterator(["META_DATA_ATTR_VALUE"],
                        "COLL_NAME = '{}' AND DATA_NAME = '{}' AND META_DATA_ATTR_NAME = 'assignedForReview'".format(coll_path, DATAREQUEST + JSON_EXT),
                        AS_DICT, ctx)
    for row in rows:
        reviewers.append(row['META_DATA_ATTR_VALUE'])

    # Check if the reviewers list contains the current user
    is_reviewer = username in reviewers

    # Return the is_reviewer boolean
    return is_reviewer


@api.make()
def api_datarequest_is_bod_member(ctx):
    """Check if given user is BOD member

    :param ctx: Combined type of a callback and rei struct

    :returns: True if user is BOD member else False
    :rtype bool
    """
    return user.is_member_of(ctx, GROUP_BOD)


@api.make()
def api_datarequest_is_dmc_member(ctx):
    """Check if given user is BOD member

    :param ctx: Combined type of a callback and rei struct

    :returns: True if user is BOD member else False
    :rtype bool
    """
    return user.is_member_of(ctx, GROUP_DMC)


@api.make()
def api_datarequest_is_datamanager(ctx):
    """Check if given user is BOD member

    :param ctx: Combined type of a callback and rei struct

    :returns: True if user is BOD member else False
    :rtype bool
    """
    return user.is_member_of(ctx, GROUP_DM)


@api.make()
def api_datarequest_schema_get(ctx, schema_name):
    return datarequest_schema_get(ctx, schema_name)


def datarequest_schema_get(ctx, schema_name):
    """Get schema and UI schema of a datarequest form

    :param ctx:         Combined type of a callback and rei struct
    :param schema_name: Name of schema

    :returns: Dict with schema and UI schema
    """
    # Define paths to schema and uischema
    coll_path = "/{}{}".format(user.zone(ctx), SCHEMACOLLECTION)
    schema_path = "{}/{}/{}".format(coll_path, schema_name, SCHEMA + JSON_EXT)
    uischema_path = "{}/{}/{}".format(coll_path, schema_name, UISCHEMA + JSON_EXT)

    # Retrieve and read schema and uischema
    try:
        schema = jsonutil.read(ctx, schema_path)
        uischema = jsonutil.read(ctx, uischema_path)
    except error.UUFileNotExistError:
        return api.Error("file_read_error", "Could not read schema because it doesn't exist.")

    # Return JSON with schema and uischema
    return {"schema": schema, "uischema": uischema}


def datarequest_data_valid(ctx, data, schema_name):
    """Check if form data contains no errors

    :param ctx:         Combined type of a callback and rei struct
    :param data:        The form data to validate
    :param schema_name: Name of JSON schema against which to validate the form data

    :returns: Boolean indicating if datarequest is valid or API error
    """
    try:
        schema = datarequest_schema_get(ctx, schema_name)['schema']

        validator = jsonschema.Draft7Validator(schema)

        errors = list(validator.iter_errors(data))

        return len(errors) == 0
    except error.UUJsonValidationError as e:
        # File may be missing or not valid JSON
        return api.Error("validation_error",
                         "{} form data could not be validated against its schema.".format(schema_name))


###################################################
#          Datarequest workflow API calls         #
###################################################

@api.make()
def api_datarequest_browse(ctx, sort_on='name', sort_order='asc', offset=0, limit=10):
    """Get paginated datarequests, including size/modify date information.

    :param ctx:        Combined type of a callback and rei struct
    :param sort_on:    Column to sort on ('name', 'modified')
    :param sort_order: Column sort order ('asc' or 'desc')
    :param offset:     Offset to start browsing from
    :param limit:      Limit number of results

    :returns: Dict with paginated datarequests
    """
    coll = "/{}/{}".format(user.zone(ctx), DRCOLLECTION)

    def transform(row):
        # Remove ORDER_BY etc. wrappers from column names.
        x = {re.sub('.*\((.*)\)', '\\1', k): v for k, v in row.items()}

        return {'id':          x['COLL_NAME'].split('/')[-1],
                'name':        x['COLL_OWNER_NAME'],
                'create_time': int(x['COLL_CREATE_TIME']),
                'status':      x['META_DATA_ATTR_VALUE']}

    def transform_title(row):
        # Remove ORDER_BY etc. wrappers from column names.
        x = {re.sub('.*\((.*)\)', '\\1', k): v for k, v in row.items()}

        return {'id':          x['COLL_NAME'].split('/')[-1],
                'title':       x['META_DATA_ATTR_VALUE']}

    if sort_on == 'modified':
        # FIXME: Sorting on modify date is borked: There appears to be no
        # reliable way to filter out replicas this way - multiple entries for
        # the same file may be returned when replication takes place on a
        # minute boundary, for example.
        # We would want to take the max modify time *per* data name.
        # (or not? replication may take place a long time after a modification,
        #  resulting in a 'too new' date)
        ccols = ['COLL_NAME', 'ORDER(COLL_CREATE_TIME)', "COLL_OWNER_NAME", "META_DATA_ATTR_VALUE"]
    else:
        ccols = ['ORDER(COLL_NAME)', 'COLL_CREATE_TIME', "COLL_OWNER_NAME", "META_DATA_ATTR_VALUE"]

    if sort_order == 'desc':
        ccols = [x.replace('ORDER(', 'ORDER_DESC(') for x in ccols]

    qcoll = Query(ctx, ccols, "COLL_PARENT_NAME = '{}' AND DATA_NAME = '{}' AND META_DATA_ATTR_NAME = 'status'".format(coll, DATAREQUEST + JSON_EXT),
                  offset=offset, limit=limit, output=query.AS_DICT)

    ccols_title = ['COLL_NAME', "META_DATA_ATTR_VALUE"]
    qcoll_title = Query(ctx, ccols_title, "COLL_PARENT_NAME = '{}' AND DATA_NAME = '{}' AND META_DATA_ATTR_NAME = 'title'".format(coll, DATAREQUEST + JSON_EXT),
                        offset=offset, limit=limit, output=query.AS_DICT)

    colls = map(transform, list(qcoll))
    colls_title = map(transform_title, list(qcoll_title))

    # Merge datarequest title in results.
    for datarequest_title in colls_title:
        for datarequest in colls:
            if datarequest_title['id'] == datarequest['id']:
                datarequest['title'] = datarequest_title['title']
                break

    if len(colls) == 0:
        # No results at all?
        # Make sure the collection actually exists.
        if not collection.exists(ctx, coll):
            return api.Error('nonexistent', 'The given path does not exist')
        # (checking this beforehand would waste a query in the most common situation)

    return OrderedDict([('total', qcoll.total_rows()),
                        ('items', colls)])


@api.make()
def api_datarequest_submit(ctx, data, previous_request_id):
    """Persist a data request to disk.

    :param ctx:                 Combined type of a callback and rei struct
    :param data:                Contents of the data request
    :param previous_request_id: Unique identifier of previous data request

    :returns: API status
    """
    timestamp = datetime.now()
    request_id = str(timestamp.strftime('%s'))
    coll_path = "/{}/{}/{}".format(user.zone(ctx), DRCOLLECTION, request_id)
    file_path = "{}/{}".format(coll_path, DATAREQUEST + JSON_EXT)

    # Validate data against schema
    if not datarequest_data_valid(ctx, data, DATAREQUEST):
        return api.Error("validation_fail",
                         "{} form data did not pass validation against its schema.".format(DATAREQUEST))

    # Create collection
    try:
        collection.create(ctx, coll_path)
    except error.UUError as e:
        return api.Error("create_collection_fail", "Could not create collection path: {}.".format(e))

    # Write data request data to disk
    try:
        jsonutil.write(ctx, file_path, data)
    except error.UUError:
        return api.Error('write_error', 'Could not write datarequest to disk')

    # Set the previous request ID as metadata if defined
    if previous_request_id:
        metadata_set(ctx, request_id, "previous_request_id", str(previous_request_id))

    # Set the proposal fields as AVUs on the proposal JSON file
    avu_json.set_json_to_obj(ctx, file_path, "-d", "root", json.dumps(data))

    # Set permissions for certain groups on the subcollection
    try:
        msi.set_acl(ctx, "recursive", "write", GROUP_DM, coll_path)
        msi.set_acl(ctx, "recursive", "write", GROUP_DMC, coll_path)
        msi.set_acl(ctx, "recursive", "write", GROUP_BOD, coll_path)
    except SetACLError:
        return api.Error("permission_error", "Could not set permissions on subcollection.")

    # Set the status metadata field to "submitted"
    status_set(ctx, request_id, status.SUBMITTED)


@api.make()
def api_datarequest_get(ctx, request_id):
    """Retrieve a data request.

    :param ctx:        Combined type of a callback and rei struct
    :param request_id: Unique identifier of the data request

    :returns: Dict with request JSON and status or API error on failure
    """
    # Convert request_id to string if it isn't already
    request_id = str(request_id)

    # Check if user is allowed to view to proposal. If not, return
    # PermissionError
    try:
        isboardmember = user.is_member_of(ctx, GROUP_BOD)
        isdatamanager = user.is_member_of(ctx, GROUP_DM)
        isdmcmember   = user.is_member_of(ctx, GROUP_DMC)
        isrequestowner = datarequest_is_owner(ctx, request_id, user.name(ctx))

        if not (isboardmember or isdatamanager or isdmcmember or isrequestowner):
            return api.Error("permission_error", "User is not authorized to view this data request.")
    except error.UUError as e:
        return api.Error("permission_error", "Something went wrong during permission checking: {}.".format(e))

    # Get request status
    datarequest_status = status_get(ctx, request_id).value

    # Get request
    datarequest = datarequest_get(ctx, request_id)

    # Return JSON encoded results
    return {'requestJSON': datarequest, 'requestStatus': datarequest_status}


def datarequest_get(ctx, request_id):
    # Construct filename and filepath
    coll_path = "/{}/{}/{}".format(user.zone(ctx), DRCOLLECTION, request_id)
    file_name = DATAREQUEST + JSON_EXT
    file_path = "{}/{}".format(coll_path, file_name)

    # Get the contents of the datarequest JSON file
    try:
        return data_object.read(ctx, file_path)
    except error.UUError as e:
        return api.Error("datarequest_read_fail", "Could not get contents of datarequest JSON file: {}.".format(e))


@api.make()
def api_datarequest_preliminary_review_submit(ctx, data, request_id):
    """Persist a preliminary review to disk.

    :param ctx:        Combined type of a callback and rei struct
    :param data:       Contents of the preliminary review
    :param request_id: Unique identifier of the data request

    :returns: API status
    """
    # Validate data against schema
    if not datarequest_data_valid(ctx, data, PR_REVIEW):
        return api.Error("validation_fail",
                         "{} form data did not pass validation against its schema.".format(PR_REVIEW))

    # Force conversion of request_id to string
    request_id = str(request_id)

    # Check if status transition allowed
    if not status_transition_allowed(ctx, status_get(ctx, request_id), status.PRELIMINARY_ACCEPT):
        return api.Error("transition", "Status transition not allowed.")

    # Read data into a dictionary
    preliminary_review = data

    # Check if user is a member of the Board of Directors. If not, do not
    # allow submission of the preliminary review
    try:
        isboardmember = user.is_member_of(ctx, GROUP_BOD)

        if not isboardmember:
            return api.Error("PermissionError", "User is not a member of the Board of Directors")
    except error.UUError:
        return api.Error("PermissionError", "Something went wrong during permissen checking")

    # Construct path to collection of the evaluation
    coll_path = "/{}/{}/{}".format(user.zone(ctx), DRCOLLECTION, request_id)

    # Write preliminary review data to disk
    try:
        preliminary_review_path = "{}/{}".format(coll_path, PR_REVIEW + JSON_EXT)
        jsonutil.write(ctx, preliminary_review_path, data)
    except error.UUError:
        return api.Error('write_error', 'Could not write preliminary review data to disk')

    # Give read permission on the preliminary review to data managers and Board of Directors members
    try:
        msi.set_acl(ctx, "default", "read", GROUP_BOD, preliminary_review_path)
        msi.set_acl(ctx, "default", "read", GROUP_DM, preliminary_review_path)
        msi.set_acl(ctx, "default", "read", GROUP_DMC, preliminary_review_path)
    except error.UUError:
        return api.Error("PermissionError", "Could not grant read permissions on the preliminary review file.")

    # Get the outcome of the preliminary review (accepted/rejected)
    decision = preliminary_review['preliminary_review']

    # Update the status of the data request
    if decision == "Accepted for data manager review":
        status_set(ctx, request_id, status.PRELIMINARY_ACCEPT)
    elif decision == "Rejected":
        datarequest_feedback_write(ctx, request_id, data['feedback_for_researcher'])
        status_set(ctx, request_id, status.PRELIMINARY_REJECT)
    elif decision == "Rejected (resubmit)":
        datarequest_feedback_write(ctx, request_id, data['feedback_for_researcher'])
        status_set(ctx, request_id, status.PRELIMINARY_RESUBMIT)
    else:
        return api.Error("InvalidData", "Invalid value for preliminary_review in preliminary review JSON data.")


@api.make()
def api_datarequest_preliminary_review_get(ctx, request_id):
    """Retrieve a preliminary review.

    :param ctx:        Combined type of a callback and rei struct
    :param request_id: Unique identifier of the data request

    :returns: Preliminary review JSON or API error on failure
    """
    # Force conversion of request_id to string
    request_id = str(request_id)

    # Check if user is authorized. If not, return PermissionError
    try:
        isboardmember = user.is_member_of(ctx, GROUP_BOD)
        isdatamanager = user.is_member_of(ctx, GROUP_DM)
        isreviewer = datarequest_is_reviewer(ctx, request_id)

        if not (isboardmember or isdatamanager or isreviewer):
            return api.Error("PermissionError", "User is not authorized to view this preliminary review.")
    except error.UUError as e:
        return api.Error("PermissionError", "Something went wrong during permission checking: {}.".format(e))

    return datarequest_preliminary_review_get(ctx, request_id)


def datarequest_preliminary_review_get(ctx, request_id):
    # Construct filename
    coll_path = "/{}/{}/{}".format(user.zone(ctx), DRCOLLECTION, request_id)
    file_name = PR_REVIEW + JSON_EXT
    file_path = "{}/{}".format(coll_path, file_name)

    # Get the contents of the review JSON file
    try:
        return data_object.read(ctx, file_path)
    except error.UUError as e:
        return api.Error("ReadError", "Could not get preliminary review data: {}.".format(e))


@api.make()
def api_datarequest_datamanager_review_submit(ctx, data, request_id):
    """Persist a datamanager review to disk.

    :param ctx:        Combined type of a callback and rei struct
    :param data:       Contents of the datamanager review
    :param request_id: Unique identifier of the data request

    :returns: API status
    """
    # Validate data against schema
    if not datarequest_data_valid(ctx, data, DM_REVIEW):
        return api.Error("validation_fail",
                         "{} form data did not pass validation against its schema.".format(DM_REVIEW))

    # Force conversion of request_id to string
    request_id = str(request_id)

    # Check if status transition allowed
    if not status_transition_allowed(ctx, status_get(ctx, request_id), status.DATAMANAGER_ACCEPT):
        api.Error("transition", "Status transition not allowed.")

    # Read datamanager review into a dictionary
    datamanager_review = data

    # Check if user is a data manager. If not, do not the user to assign the
    # request
    try:
        isdatamanager = user.is_member_of(ctx, GROUP_DM)

        if not isdatamanager:
            return api.Error("PermissionError", "User is not a data manager.")
    except error.UUerror as e:
        return api.Error("PermissionError", "Something went wrong during permission checking: {}.".format(e))

    # Construct path to collection of the evaluation
    coll_path = "/{}/{}/{}".format(user.zone(ctx), DRCOLLECTION, request_id)

    # Write data manager review data to disk
    try:
        datamanager_review_path = "{}/{}".format(coll_path, DM_REVIEW + JSON_EXT)
        jsonutil.write(ctx, datamanager_review_path, data)
    except error.UUError:
        return api.Error('write_error', 'Could not write data manager review data to disk')

    # Give read permission on the data manager review to data managers and Board of Directors members
    try:
        msi.set_acl(ctx, "default", "read", GROUP_BOD, datamanager_review_path)
        msi.set_acl(ctx, "default", "read", GROUP_DM, datamanager_review_path)
        msi.set_acl(ctx, "default", "read", GROUP_DMC, datamanager_review_path)
    except error.UUError:
        return api.Error("PermissionsError", "Could not grant read permissions on the preliminary review file.")

    # Get the outcome of the data manager review (accepted/rejected)
    decision = datamanager_review['datamanager_review']

    # Update the status of the data request
    if decision == "Accepted":
        status_set(ctx, request_id, status.DATAMANAGER_ACCEPT)
    elif decision == "Rejected":
        status_set(ctx, request_id, status.DATAMANAGER_REJECT)
    elif decision == "Rejected (resubmit)":
        status_set(ctx, request_id, status.DATAMANAGER_RESUBMIT)
    else:
        return api.Error("InvalidData", "Invalid value for decision in data manager review JSON data.")


@api.make()
def api_datarequest_datamanager_review_get(ctx, request_id):
    """Retrieve a data manager review.

    :param ctx:        Combined type of a callback and rei struct
    :param request_id: Unique identifier of the data request

    :returns: Datamanager review JSON or API error on failure
    """
    # Force conversion of request_id to string
    request_id = str(request_id)

    # Check if user is authorized. If not, return PermissionError
    try:
        isboardmember = user.is_member_of(ctx, GROUP_BOD)
        isdatamanager = user.is_member_of(ctx, GROUP_DM)
        isreviewer = datarequest_is_reviewer(ctx, request_id)

        if not (isboardmember or isdatamanager or isreviewer):
            return api.Error("PermissionError", "User is not authorized to view this data manager review.")
    except error.UUError:
        return api.Error("PermissionError", "Something went wrong during permission checking.")

    # Retrieve and return datamanager review
    return datarequest_datamanager_review_get(ctx, request_id)


def datarequest_datamanager_review_get(ctx, request_id):
    # Construct filename
    coll_path = "/{}/{}/{}".format(user.zone(ctx), DRCOLLECTION, request_id)
    file_name = DM_REVIEW + JSON_EXT
    file_path = "{}/{}".format(coll_path, file_name)

    # Get the contents of the data manager review JSON file
    try:
        return data_object.read(ctx, file_path)
    except error.UUError as e:
        return api.Error("ReadError", "Could not get data manager review data: {}.".format(e))


@api.make()
def api_datarequest_assignment_submit(ctx, data, request_id):
    """Persist an assignment to disk.

    :param ctx:        Combined type of a callback and rei struct
    :param data:       Contents of the assignment
    :param request_id: Unique identifier of the data request

    :returns: API status
    """
    # Validate data against schema
    if not datarequest_data_valid(ctx, data, ASSIGNMENT):
        return api.Error("validation_fail",
                         "{} form data did not pass validation against its schema.".format(ASSIGNMENT))

    # Force conversion of request_id to string
    request_id = str(request_id)

    # Check if status transition allowed
    if not status_transition_allowed(ctx, status_get(ctx, request_id), status.UNDER_REVIEW):
        api.Error("transition", "Status transition not allowed.")

    # Read assignment into dictionary
    assignment = data

    # Check if user is a member of the Board of Directors. If not, do not
    # allow assignment
    try:
        isboardmember = user.is_member_of(ctx, GROUP_BOD)

        if not isboardmember:
            return api.Error("PermissionError", "User is not a member of the Board of Directors")
    except error.UUError as e:
        return api.Error("PermissionError", "Something went wrong during permission checking: {}.".format(e))

    # Construct path to collection of the evaluation
    coll_path = "/{}/{}/{}".format(user.zone(ctx), DRCOLLECTION, request_id)

    # Write assignment data to disk
    try:
        assignment_path = "{}/{}".format(coll_path, ASSIGNMENT + JSON_EXT)
        jsonutil.write(ctx, assignment_path, data)
    except error.UUError:
        return api.Error('write_error', 'Could not write assignment data to disk')

    # Give read permission on the assignment to data managers and Board of Directors members
    try:
        msi.set_acl(ctx, "default", "read", GROUP_BOD, assignment_path)
        msi.set_acl(ctx, "default", "read", GROUP_DM, assignment_path)
        msi.set_acl(ctx, "default", "read", GROUP_DMC, assignment_path)
    except error.UUError as e:
        return api.Error("PermissionsError", "Could not grant read permissions on the assignment file: {}.".format(e))

    # Get the outcome of the assignment (accepted/rejected)
    decision = assignment['decision']

    # Update the status of the data request
    if decision == "Accepted for DMC review":
        assignees = json.dumps(assignment['assign_to'])
        assign_request(ctx, assignees, request_id)
        status_set(ctx, request_id, status.UNDER_REVIEW)
    elif decision == "Rejected":
        datarequest_feedback_write(ctx, request_id, data['feedback_for_researcher'])
        status_set(ctx, request_id, status.REJECTED_AFTER_DATAMANAGER_REVIEW)
    elif decision == "Rejected (resubmit)":
        datarequest_feedback_write(ctx, request_id, data['feedback_for_researcher'])
        status_set(ctx, request_id, status.RESUBMIT_AFTER_DATAMANAGER_REVIEW)
    else:
        return api.Error("InvalidData", "Invalid value for 'decision' key in datamanager review JSON data.")


def assign_request(ctx, assignees, request_id):
    """Assign a data request to one or more DMC members for review.

    :param ctx:        Combined type of a callback and rei struct
    :param assignees:  JSON-formatted array of DMC members
    :param request_id: Unique identifier of the data request

    :returns: A JSON dict with status info for the front office
    """
    # Check if user is a data manager. If not, do not the user to assign the
    # request
    try:
        isbodmember = user.is_member_of(ctx, GROUP_BOD)
    except error.UUError:
        isbodmember = false

    if not isbodmember:
        return api.Error("PermissionDenied", "User is not a data manager.")

    # Construct data request collection path
    coll_path = "/{}/{}/{}".format(user.zone(ctx), DRCOLLECTION, request_id)

    # Assign the data request by adding a delayed rule that sets one or more
    # "assignedForReview" attributes on the datarequest (the number of
    # attributes is determined by the number of assignees) ...
    status = ""
    status_info = ""
    ctx.requestDatarequestMetadataChange(coll_path,
                                         "assignedForReview",
                                         assignees,
                                         str(len(json.loads(assignees))),
                                         status, status_info)

    # ... and triggering the processing of delayed rules
    ctx.adminDatarequestActions()


@api.make()
def api_datarequest_assignment_get(ctx, request_id):
    """Retrieve assignment.

    :param ctx:        Combined type of a callback and rei struct
    :param request_id: Unique identifier of the data request

    :returns: Datarequest assignment JSON or API error on failure
    """
    # Force conversion of request_id to string
    request_id = str(request_id)

    return datarequest_assignment_get(ctx, request_id)


def datarequest_assignment_get(ctx, request_id):
    # Construct filename
    coll_path = "/{}/{}/{}".format(user.zone(ctx), DRCOLLECTION, request_id)
    file_name = ASSIGNMENT + JSON_EXT
    file_path = "{}/{}".format(coll_path, file_name)

    # Get the contents of the assignment JSON file
    try:
        return data_object.read(ctx, file_path)
    except error.UUError:
        return api.Error("ReadError", "Could not get assignment data.")


@api.make()
def api_datarequest_review_submit(ctx, data, request_id):
    """Persist a data request review to disk.

    :param ctx:        Combined type of a callback and rei struct
    :param data:       Contents of the review
    :param request_id: Unique identifier of the data request

    :returns: A JSON dict with status info for the front office
    """
    # Validate data against schema
    if not datarequest_data_valid(ctx, data, REVIEW):
        return api.Error("validation_fail",
                         "{} form data did not pass validation against its schema.".format(REVIEW))

    # Force conversion of request_id to string
    request_id = str(request_id)

    # Check if status transition allowed
    if not status_transition_allowed(ctx, status_get(ctx, request_id), status.REVIEWED):
        return api.Error("transition", "Status transition not allowed.")

    # Check if the user has been assigned as a reviewer. If not, do not
    # allow submission of the review
    try:
        isreviewer = datarequest_is_reviewer(ctx, request_id)
    except error.UUError:
        isreviewer = false

    if not isreviewer:
        return api.Error("PermissionDenied", "User is not assigned as a reviewer to this request.")

    # Construct path to collection of review
    coll_path = "/{}/{}/{}".format(user.zone(ctx), DRCOLLECTION, request_id)

    # Write review data to disk
    try:
        review_path = "{}/review_{}.json".format(coll_path, user.name(ctx))
        jsonutil.write(ctx, review_path, data)
    except error.UUError as e:
        return api.Error('write_error', 'Could not write review data to disk: {}.'.format(e))

    # Give read permission on the review to Board of Director members
    try:
        msi.set_acl(ctx, "default", "read", GROUP_BOD, review_path)
    except error.UUError:
        return api.Error("PermissionsError", "Could not grant read permissions on the review file to the Board of Directors")

    # Remove the assignedForReview attribute of this user by first fetching
    # the list of reviewers ...
    reviewers = []

    iter = genquery.row_iterator(
        "META_DATA_ATTR_VALUE",
        "COLL_NAME = '{}' AND DATA_NAME = '{}' AND META_DATA_ATTR_NAME = 'assignedForReview'".format(coll_path, DATAREQUEST + JSON_EXT),
        genquery.AS_LIST, ctx)

    for row in iter:
        reviewer = row[0]
        reviewers.append(reviewer)

    # ... then removing the current reviewer from the list
    reviewers.remove(user.name(ctx))

    # ... and then updating the assignedForReview attributes
    status_code = ""
    status_info = ""
    ctx.requestDatarequestMetadataChange(coll_path,
                                         "assignedForReview",
                                         json.dumps(reviewers),
                                         str(len(reviewers)),
                                         status_code, status_info)
    ctx.adminDatarequestActions()

    # If there are no reviewers left, change the status of the proposal to
    # 'reviewed' and send an email to the Board of Directors members
    # informing them that the proposal is ready to be evaluated by them.
    if len(reviewers) < 1:
        status_set(ctx, request_id, status.REVIEWED)


@api.make()
def api_datarequest_reviews_get(ctx, request_id):
    """Retrieve a data request review.

    :param ctx:        Combined type of a callback and rei struct
    :param request_id: Unique identifier of the data request

    :returns: Datarequest review JSON or API error on failure
    """
    # Force conversion of request_id to string
    request_id = str(request_id)

    # Check if user is authorized. If not, return PermissionError
    try:
        isboardmember = user.is_member_of(ctx, GROUP_BOD)

        if not isboardmember:
            return api.Error("PermissionError", "User is not authorized to view this review.")
    except error.UUError as e:
        return api.Error("PermissionError", "Something went wrong during permission checking: {}.".format(e))

    # Construct filename
    coll_path = "/{}/{}/{}".format(user.zone(ctx), DRCOLLECTION, request_id)
    file_name = 'review_%.json'

    # Get the review JSON files
    reviews = []
    rows = row_iterator(["DATA_NAME"],
                        "COLL_NAME = '{}' AND DATA_NAME like '{}'".format(coll_path, file_name),
                        AS_DICT, ctx)
    for row in rows:
        file_path = "{}/{}".format(coll_path, row['DATA_NAME'])
        try:
            reviews.append(json.loads(data_object.read(ctx, file_path)))
        except error.UUError as e:
            return api.Error("ReadError", "Could not get review data: {}.".format(e))

    return json.dumps(reviews)


@api.make()
def api_datarequest_evaluation_submit(ctx, data, request_id):
    """Persist an evaluation to disk.

    :param ctx:        Combined type of a callback and rei struct
    :param data:       Contents of the evaluation
    :param request_id: Unique identifier of the data request

    :returns: API status
    """
    # Validate data against schema
    if not datarequest_data_valid(ctx, data, EVALUATION):
        return api.Error("validation_fail",
                         "{} form data did not pass validation against its schema.".format(EVALUATION))

    # Force conversion of request_id to string
    request_id = str(request_id)

    # Check if status transition allowed
    if not status_transition_allowed(ctx, status_get(ctx, request_id), status.APPROVED):
        api.Error("transition", "Status transition not allowed.")

    # Read evaluation into dictionary
    evaluation = data

    # Check if user is a member of the Board of Directors. If not, do not
    # allow submission of the evaluation
    try:
        isboardmember = user.is_member_of(ctx, GROUP_BOD)

        if not isboardmember:
            return api.Error("PermissionError", "User is not a member of the Board of Directors")
    except error.UUError as e:
        return api.Error("PermissionError", "Something went wrong during permission checking: {}.")

    # Construct path to collection of the evaluation
    coll_path = "/{}/{}/{}".format(user.zone(ctx), DRCOLLECTION, request_id)

    # Write evaluation data to disk
    try:
        evaluation_path = "{}/{}".format(coll_path, EVALUATION + JSON_EXT)
        jsonutil.write(ctx, evaluation_path, data)
    except error.UUError:
        return api.Error('write_error', 'Could not write evaluation data to disk')

    # Get outcome of evaluation
    decision = evaluation['evaluation']

    # Update the status of the data request
    if decision == "Approved":
        status_set(ctx, request_id, status.APPROVED)
    elif decision == "Rejected":
        datarequest_feedback_write(ctx, request_id, data['feedback_for_researcher'])
        status_set(ctx, request_id, status.REJECTED)
    elif decision == "Rejected (resubmit)":
        datarequest_feedback_write(ctx, request_id, data['feedback_for_researcher'])
        status_set(ctx, request_id, status.RESUBMIT)
    else:
        return api.Error("InvalidData", "Invalid value for 'evaluation' key in evaluation JSON data.")


def datarequest_evaluation_get(ctx, request_id):
    # Construct filename
    coll_path = "/{}/{}/{}".format(user.zone(ctx), DRCOLLECTION, request_id)
    file_name = EVALUATION + JSON_EXT
    file_path = "{}/{}".format(coll_path, file_name)

    # Get the contents of the assignment JSON file
    try:
        return data_object.read(ctx, file_path)
    except error.UUError:
        return api.Error("ReadError", "Could not get assignment data.")


def datarequest_feedback_write(ctx, request_id, feedback):
    """ Write feedback to researcher to a separate file and grant the researcher read access

    :param ctx:        Combined type of a callback and rei struct
    :param request_id: Unique identifier of the data request
    :param feedback:   String containing the feedback for the researcher
    """
    # Construct path to feedback file
    coll_path = "/{}/{}/{}".format(user.zone(ctx), DRCOLLECTION, request_id)
    feedback_path = "{}/{}".format(coll_path, FEEDBACK + JSON_EXT)

    # Write data to feedback file
    jsonutil.write(ctx, feedback_path, feedback)

    # Get the username of the owner of the data request from iCAT
    rows = row_iterator(["DATA_OWNER_NAME"],
                        "DATA_NAME = '{}' and COLL_NAME like '{}'".format(DATAREQUEST + JSON_EXT, coll_path),
                        AS_DICT, ctx)
    request_owner_username = []
    for row in rows:
        request_owner_username.append(row["DATA_OWNER_NAME"])
    # Check if exactly 1 owner was found. If not, return error
    if len(request_owner_username) != 1:
        return api.Error("MoreThanOneOwner", "Not exactly 1 owner found. Something is very wrong.")
    request_owner_username = request_owner_username[0]

    # Grant researcher read permissions
    try:
        msi.set_acl(ctx, "default", "read", request_owner_username,
                    "{}/{}".format(coll_path, FEEDBACK + JSON_EXT))
    except error.UUError:
        return api.Error("PermissionError", "Could not grant read permissions on the feedback file to the data request owner.")


@api.make()
def api_datarequest_feedback_get(ctx, request_id):
    """Get feedback for researcher

    :param ctx:        Combined type of a callback and rei struct
    :param request_id: Unique identifier of the data request

    :returns:          JSON-foramtted string containing feedback for researcher
    """
    # Check if data request status is appropriate
    status = status_get(ctx, request_id)
    if not status in [status.PRELIMINARY_REJECT, status.PRELIMINARY_RESUBMIT,
                      status.REJECTED_AFTER_DATAMANAGER_REVIEW,
                      status.RESUBMIT_AFTER_DATAMANAGER_REVIEW, status.REJECTED, status.RESUBMIT]:
        return api.Error("StatusError", "Inappropriate data request status.")

    # Construct filename
    coll_path = "/{}/{}/{}".format(user.zone(ctx), DRCOLLECTION, request_id)
    file_path = "{}/{}".format(coll_path, FEEDBACK + JSON_EXT)

    # Get the contents of the feedback JSON file
    try:
        return data_object.read(ctx, file_path)
    except error.UUError as e:
        return api.Error("ReadError", "Could not get feedback data: {}.".format(e))


@api.make()
def api_datarequest_dta_post_upload_actions(ctx, request_id):
    """Grant read permissions on the DTA to the owner of the associated data request.

    :param ctx:        Combined type of a callback and rei struct
    :param request_id: Unique identifier of the data request

    :returns: API status
    """
    # Force conversion of request_id to string
    request_id = str(request_id)

    # Check if status transition allowed
    if not status_transition_allowed(ctx, status_get(ctx, request_id), status.DTA_READY):
        return api.Error("transition", "Status transition not allowed.")

    # Check if user is allowed to view to proposal. If not, return
    # PermissionError
    try:
        isdatamanager = user.is_member_of(ctx, GROUP_DM)

        if not isdatamanager:
            return api.Error("PermissionError", "User is not authorized to grant read permissions on the DTA.")
    except error.UUError as e:
        return api.Error("PermissionError", "Something went wrong during permission checking: {}.".format(e))

    # Construct path to the collection of the datarequest
    coll_path = "/{}/{}/{}".format(user.zone(ctx), DRCOLLECTION, request_id)

    # Query iCAT for the username of the owner of the data request
    rows = row_iterator(["DATA_OWNER_NAME"],
                        "DATA_NAME = '{}' and COLL_NAME like '{}'".format(DATAREQUEST + JSON_EXT, coll_path),
                        AS_DICT, ctx)

    # Extract username from query results
    request_owner_username = []
    for row in rows:
        request_owner_username.append(row["DATA_OWNER_NAME"])

    # Check if exactly 1 owner was found. If not, wipe
    # requestOwnerUserName list and set error status code
    if len(request_owner_username) != 1:
        return api.Error("MoreThanOneOwner", "Not exactly 1 owner found. Something is very wrong.")

    request_owner_username = request_owner_username[0]

    try:
        msi.set_acl(ctx, "default", "read", request_owner_username, "{}/{}".format(coll_path, DTA_FILENAME))
    except error.UUError:
        return api.Error("PermissionError", "Could not grant read permissions on the DTA to the data request owner.")

    # Set status to dta_ready
    status_set(ctx, request_id, status.DTA_READY)


@api.make()
def api_datarequest_signed_dta_post_upload_actions(ctx, request_id):
    """Grant read permissions on the signed DTA to the datamanagers group.

    :param ctx:        Combined type of a callback and rei struct
    :param request_id: Unique identifier of the data request

    :returns: API status
    """
    # Force conversion of request_id to string
    request_id = str(request_id)

    # Check if status transition allowed
    if not status_transition_allowed(ctx, status_get(ctx, request_id), status.DTA_SIGNED):
        return api.Error("transition", "Status transition not allowed.")

    # Check if user is allowed to view to proposal. If not, return
    # PermissionError
    try:
        isrequestowner = datarequest_is_owner(ctx, request_id, user.name(ctx))

        if not isrequestowner:
            return api.Error("PermissionError", "User is not authorized to grant read permissions on the signed DTA.")
    except error.UUError:
        return api.Error("PermissionError", "Something went wrong during permission checking.")

    # Construct path to the collection of the datarequest
    coll_path = "/{}/{}/{}".format(user.zone(ctx), DRCOLLECTION, request_id)

    try:
        msi.set_acl(ctx, "default", "read", GROUP_DM, "{}/{}".format(coll_path, SIGDTA_FILENAME))
    except error.UUError:
        return api.Error("PermissionsError", "Could not grant read permissions on the signed DTA to the data managers group.")

    # Set status to dta_signed
    status_set(ctx, request_id, status.DTA_SIGNED)


@api.make()
def api_datarequest_data_ready(ctx, request_id):
    """Set the status of a submitted datarequest to "Data ready".

    :param ctx:        Combined type of a callback and rei struct
    :param request_id: Unique identifier of the data request

    :returns: API status
    """
    # Force conversion of request_id to string
    request_id = str(request_id)

    # Check if status transition allowed
    if not status_transition_allowed(ctx, status_get(ctx, request_id), status.DATA_READY):
        return api.Error("transition", "Status transition not allowed.")

    # Check if user is allowed to view to proposal. If not, return
    # PermissionError
    try:
        isdatamanager = user.is_member_of(ctx, GROUP_DM)

        if not isdatamanager:
            return api.Error("PermissionError", "User is not authorized to mark the data as ready.")
    except error.UUError as e:
        return api.Error("PermissionError", "Something went wrong during permission checking: {}.".format(e))

    status_set(ctx, request_id, status.DATA_READY)


###################################################
#                   Email logic                   #
###################################################

def send_emails(ctx, obj_name, status_to):
    # Get request ID
    temp, _ = pathutil.chop(obj_name)
    _, request_id = pathutil.chop(temp)

    # Get datarequest status
    datarequest_status = status_get(ctx, request_id)

    # Determine and invoke the appropriate email routine
    if datarequest_status == status.SUBMITTED:
        datarequest_submit_emails(ctx, request_id)

    elif datarequest_status in (status.PRELIMINARY_ACCEPT, status.PRELIMINARY_REJECT,
                                status.PRELIMINARY_RESUBMIT):
        preliminary_review_emails(ctx, request_id, datarequest_status)

    elif datarequest_status in (status.DATAMANAGER_ACCEPT, status.DATAMANAGER_REJECT,
                                status.DATAMANAGER_RESUBMIT):
        datamanager_review_emails(ctx, request_id, datarequest_status)

    elif datarequest_status in (status.UNDER_REVIEW, status.REJECTED_AFTER_DATAMANAGER_REVIEW,
                                status.RESUBMIT_AFTER_DATAMANAGER_REVIEW):
        assignment_submit_emails(ctx, request_id, datarequest_status)

    elif datarequest_status == status.REVIEWED:
        review_submit_emails(ctx, request_id)

    elif datarequest_status in (status.APPROVED, status.REJECTED, status.RESUBMIT):
        evaluation_submit_emails(ctx, request_id, datarequest_status)

    elif datarequest_status == status.DTA_READY:
        dta_post_upload_actions_emails(ctx, request_id)

    elif datarequest_status == status.DTA_SIGNED:
        signed_dta_post_upload_actions_emails(ctx, request_id)

    elif datarequest_status == status.DATA_READY:
        data_ready_emails(ctx, request_id)


def datarequest_submit_emails(ctx, request_id):
    # Get (source data for) email input parameters
    datarequest       = json.loads(datarequest_get(ctx, request_id))
    researcher        = datarequest['researchers']['contacts'][0]
    research_context  = datarequest['research_context']
    bod_member_emails = json.loads(ctx.uuGroupGetMembersAsJson(GROUP_BOD, "")['arguments'][1])
    timestamp         = datetime.fromtimestamp(int(request_id)).strftime('%c')

    # Send email to researcher and Board of Directors member(s)
    mail_datarequest_researcher(ctx, researcher['email'], researcher['name'], request_id)
    for bodmember_email in bod_member_emails:
        if not bodmember_email == "rods":
            mail_datarequest_bodmember(ctx, bodmember_email, request_id, researcher['name'],
                                       researcher['email'], researcher['institution'],
                                       researcher['department'], timestamp,
                                       research_context['title'])


def preliminary_review_emails(ctx, request_id, datarequest_status):
    # Get (source data for) email input parameters
    datamanager_emails = json.loads(ctx.uuGroupGetMembersAsJson(GROUP_DM, "")['arguments'][1])

    # Email datamanager
    if datarequest_status == status.PRELIMINARY_ACCEPT:
        for datamanager_email in datamanager_emails:
            if not datamanager_email == "rods":
                mail_preliminary_review_accepted(ctx, datamanager_email, request_id)
        return

    # Email researcher with feedback and call to action
    elif datarequest_status in (status.PRELIMINARY_REJECT, status.PRELIMINARY_RESUBMIT):
        # Get additional (source data for) email input parameters
        datarequest             = json.loads(datarequest_get(ctx, request_id))
        researcher              = datarequest['researchers']['contacts'][0]
        preliminary_review      = json.loads(datarequest_preliminary_review_get(ctx, request_id))
        feedback_for_researcher = preliminary_review['feedback_for_researcher']

        # Send emails
        if datarequest_status   == status.PRELIMINARY_RESUBMIT:
            mail_preliminary_review_resubmit(ctx, researcher['email'], researcher['name'],
                                             feedback_for_researcher, datamanager_emails[0],
                                             request_id)
        elif datarequest_status == status.PRELIMINARY_REJECT:
            mail_preliminary_review_rejected(ctx, researcher['email'], researcher['name'],
                                             feedback_for_researcher, datamanager_emails[0],
                                             request_id)


def datamanager_review_emails(ctx, request_id, datarequest_status):
    # Get (source data for) email input parameters
    bod_member_emails   = json.loads(ctx.uuGroupGetMembersAsJson(GROUP_BOD, "")['arguments'][1])
    datamanager_review  = json.loads(datarequest_datamanager_review_get(ctx, request_id))
    datamanager_remarks = (datamanager_review['datamanager_remarks'] if 'datamanager_remarks' in
                           datamanager_review else "")

    # Send emails
    for bod_member_email in bod_member_emails:
        if not bod_member_email == "rods":
            if datarequest_status   == status.DATAMANAGER_ACCEPT:
                mail_datamanager_review_accepted(ctx, bod_member_email, request_id)
            elif datarequest_status == status.DATAMANAGER_RESUBMIT:
                mail_datamanager_review_resubmit(ctx, bod_member_email, datamanager_remarks,
                                                 request_id)
            elif datarequest_status == status.DATAMANAGER_REJECT:
                mail_datamanager_review_rejected(ctx, bod_member_email, datamanager_remarks,
                                                 request_id)


def assignment_submit_emails(ctx, request_id, datarequest_status):
    # Get (source data for) email input parameters
    datarequest             = json.loads(datarequest_get(ctx, request_id))
    researcher              = datarequest['researchers']['contacts'][0]
    research_context        = datarequest['research_context']
    assignment              = json.loads(datarequest_assignment_get(ctx, request_id))
    assignees               = assignment['assign_to']

    # Send emails
    if datarequest_status == status.UNDER_REVIEW:
        mail_assignment_accepted_researcher(ctx, researcher['email'], researcher['name'],
                                            request_id)
        for assignee_email in assignees:
            mail_assignment_accepted_assignee(ctx, assignee_email, research_context['title'],
                                              request_id)

    elif datarequest_status in (status.RESUBMIT_AFTER_DATAMANAGER_REVIEW,
                                status.REJECTED_AFTER_DATAMANAGER_REVIEW):
        # Get additional email input parameter
        feedback_for_researcher = assignment['feedback_for_researcher']

        # Send emails
        if datarequest_status == status.RESUBMIT_AFTER_DATAMANAGER_REVIEW:
            mail_assignment_resubmit(ctx, researcher['email'], researcher['name'], request_id,
                                     feedback_for_researcher)
        elif datarequest_status == status.REJECTED_AFTER_DATAMANAGER_REVIEW:
            mail_assignment_rejected(ctx, researcher['email'], researcher['name'], request_id,
                                     feedback_for_researcher)


def review_submit_emails(ctx, request_id):
    # Get (source data for) email input parameters
    datarequest       = json.loads(datarequest_get(ctx, request_id))
    researcher        = datarequest['researchers']['contacts'][0]
    bod_member_emails = json.loads(ctx.uuGroupGetMembersAsJson(GROUP_BOD, "")['arguments'][1])

    # Send emails
    mail_review_researcher(ctx, researcher['email'], researcher['name'], request_id)
    for bodmember_email in bod_member_emails:
        if not bodmember_email == "rods":
            mail_review_bodmember(ctx, bodmember_email, request_id)


def evaluation_submit_emails(ctx, request_id, datarequest_status):
    # Get (source data for) email input parameters
    datarequest             = json.loads(datarequest_get(ctx, request_id))
    researcher              = datarequest['researchers']['contacts'][0]
    evaluation              = json.loads(datarequest_evaluation_get(ctx, request_id))
    feedback_for_researcher = (evaluation['feedback_for_researcher'] if 'feedback_for_researcher' in
                               evaluation else "")
    datamanager_emails      = json.loads(ctx.uuGroupGetMembersAsJson(GROUP_DM, "")['arguments'][1])

    # Send emails
    if datarequest_status == status.APPROVED:
        mail_evaluation_approved_researcher(ctx, researcher['email'], researcher['name'],
                                            request_id)
        for datamanager_email in datamanager_emails:
            if not datamanager_email == "rods":
                mail_evaluation_approved_datamanager(ctx, datamanager_email, request_id)
    elif datarequest_status == status.RESUBMIT:
        mail_evaluation_resubmit(ctx, researcher['email'], researcher['name'],
                                 feedback_for_researcher, datamanager_emails[0], request_id)
    elif datarequest_status == status.REJECTED:
        mail_evaluation_rejected(ctx, researcher['email'], researcher['name'],
                                 feedback_for_researcher, datamanager_emails[0], request_id)


def dta_post_upload_actions_emails(ctx, request_id):
    # Get (source data for) email input parameters
    datarequest = json.loads(datarequest_get(ctx, request_id))
    researcher  = datarequest['researchers']['contacts'][0]

    # Send email
    mail_dta(ctx, researcher['email'], researcher['name'], request_id)


def signed_dta_post_upload_actions_emails(ctx, request_id):
    # Get (source data for) email input parameters
    datamanager_emails = json.loads(ctx.uuGroupGetMembersAsJson(GROUP_DM, "")['arguments'][1])

    # Send email
    for datamanager_email in datamanager_emails:
        if not datamanager_email == "rods":
            mail_signed_dta(ctx, datamanager_email, request_id)


def data_ready_emails(ctx, request_id):
    # Get (source data for) email input parameters
    datarequest       = json.loads(datarequest_get(ctx, request_id))
    researcher        = datarequest['researchers']['contacts'][0]
    datamanager_email = json.loads(ctx.uuGroupGetMembersAsJson(GROUP_DM, "")['arguments'][1])[0]

    # Send email
    mail_data_ready(ctx, researcher['email'], researcher['name'], datamanager_email, request_id)


###################################################
#                 Email templates                 #
###################################################

def mail_datarequest_researcher(ctx, researcher_email, researcher_name, request_id):
    return mail.send(ctx,
                     to=researcher_email,
                     actor=user.full_name(ctx),
                     subject="YOUth data request {}: submitted".format(request_id),
                     body="""Dear {},

Your data request has been submitted.

You will be notified by email of the status of your request. You may also log into Yoda to view the status and other information about your data request.

The following link will take you directly to your data request: https://{}/datarequest/view/{}.

With kind regards,
YOUth
""".format(researcher_name, YODA_PORTAL_FQDN, request_id))


def mail_datarequest_bodmember(ctx, bodmember_email, request_id, researcher_name, researcher_email,
                               researcher_institution, researcher_department, submission_date,
                               proposal_title):
    return mail.send(ctx,
                     to=bodmember_email,
                     actor=user.full_name(ctx),
                     subject="YOUth data request {}: submitted".format(request_id),
                     body="""Dear Board of Directors member,

A new data request has been submitted.

Submitted by: {} ({})
Affiliation: {}, {}
Date: {}
Request ID: {}
Proposal title: {}

The following link will take you to the preliminary review form: https://{}/datarequest/preliminaryreview/{}.

With kind regards,
YOUth
""".format(researcher_name, researcher_email, researcher_institution, researcher_department, submission_date, request_id, proposal_title, YODA_PORTAL_FQDN, request_id))


def mail_preliminary_review_accepted(ctx, datamanager_email, request_id):
    return mail.send(ctx,
                     to=datamanager_email,
                     actor=user.full_name(ctx),
                     subject="YOUth data request {}: accepted for data manager review".format(request_id),
                     body="""Dear data manager,

Data request {} has been approved for review by the Board of Directors.

You are now asked to review the data request for any potential problems concerning the requested data and to submit your recommendation (accept, resubmit, or reject) to the YOUth board of directors.

The following link will take you directly to the review form: https://{}/datarequest/datamanagerreview/{}.

With kind regards,
YOUth
""".format(request_id, YODA_PORTAL_FQDN, request_id))


def mail_preliminary_review_resubmit(ctx, researcher_email, researcher_name,
                                     feedback_for_researcher, datamanager_email, request_id):
    return mail.send(ctx,
                     to=researcher_email,
                     actor=user.full_name(ctx),
                     subject="YOUth data request {}: rejected (resubmit)".format(request_id),
                     body="""Dear {},

Your data request has been rejected for the following reason(s):

{}

You are however allowed to resubmit your data request. You may do so using this link: https://{}/datarequest/add/{}.

If you wish to object against this rejection, please contact the YOUth data manager ({}).

With kind regards,
YOUth
""".format(researcher_name, feedback_for_researcher, YODA_PORTAL_FQDN, request_id, datamanager_email))


def mail_preliminary_review_rejected(ctx, researcher_email, researcher_name,
                                     feedback_for_researcher, datamanager_email, request_id):
    return mail.send(ctx,
                     to=researcher_email,
                     actor=user.full_name(ctx),
                     subject="YOUth data request {}: rejected".format(request_id),
                     body="""Dear {},

Your data request has been rejected for the following reason(s):

{}

If you wish to object against this rejection, please contact the YOUth data manager ({}).

With kind regards,
YOUth
""".format(researcher_name, feedback_for_researcher, datamanager_email))


def mail_datamanager_review_accepted(ctx, bodmember_email, request_id):
    return mail.send(ctx,
                     to=bodmember_email,
                     actor=user.full_name(ctx),
                     subject="YOUth data request {}: accepted by data manager".format(request_id),
                     body="""Dear Board of Directors member,

Data request {} has been accepted by the data manager.

You are now asked to assign the data request for review to one or more DMC members. To do so, please navigate to the assignment form using this link: https://{}/datarequest/assign/{}.

With kind regards,
YOUth
""".format(request_id, YODA_PORTAL_FQDN, request_id))


def mail_datamanager_review_resubmit(ctx, bodmember_email, datamanager_remarks, request_id):
    return mail.send(ctx,
                     to=bodmember_email,
                     actor=user.full_name(ctx),
                     subject="YOUth data request {}: rejected (resubmit) by data manager".format(request_id),
                     body="""Dear Board of Directors member,

Data request {} has been rejected (resubmission allowed) by the data manager for the following reason(s):

{}

The data manager's review is advisory. Please consider the objections raised and then either reject the data request or assign it for review to one or more DMC members. To do so, please navigate to the assignment form using this link https://{}/datarequest/assign/{}.

With kind regards,
YOUth
""".format(request_id, datamanager_remarks, YODA_PORTAL_FQDN, request_id))


def mail_datamanager_review_rejected(ctx, bodmember_email, datamanager_remarks, request_id):
    return mail.send(ctx,
                     to=bodmember_email,
                     actor=user.full_name(ctx),
                     subject="YOUth data request {}: rejected by data manager".format(request_id),
                     body="""Dear Board of Directors member,

Data request {} has been rejected by the data manager for the following reason(s):

{}

The data manager's review is advisory. Please consider the objections raised and then either reject the data request or assign it for review to one or more DMC members. To do so, please navigate to the assignment form using this link https://{}/datarequest/assign/{}.

With kind regards,
YOUth
""".format(request_id, datamanager_remarks, YODA_PORTAL_FQDN, request_id))


def mail_assignment_accepted_researcher(ctx, researcher_email, researcher_name, request_id):
    return mail.send(ctx,
                     to=researcher_email,
                     actor=user.full_name(ctx),
                     subject="YOUth data request {}: assigned".format(request_id),
                     body="""Dear {},

Your data request has been assigned for review.

The following link will take you directly to your data request: https://{}/datarequest/view/{}.

With kind regards,
YOUth
""".format(researcher_name, YODA_PORTAL_FQDN, request_id))


def mail_assignment_accepted_assignee(ctx, assignee_email, proposal_title, request_id):
    return mail.send(ctx,
                     to=assignee_email,
                     actor=user.full_name(ctx),
                     subject="YOUth data request {}: assigned".format(request_id),
                     body="""Dear DMC member,

Data request {} (proposal title: \"{}\") has been assigned to you for review. Please sign in to Yoda to view the data request and submit your review.

The following link will take you directly to the review form: https://{}/datarequest/review/{}.

With kind regards,
YOUth
""".format(request_id, proposal_title, YODA_PORTAL_FQDN, request_id))


def mail_assignment_resubmit(ctx, researcher_email, researcher_name, feedback_for_researcher,
                             request_id):
    return mail.send(ctx,
                     to=researcher_email,
                     actor=user.full_name(ctx),
                     subject="YOUth data request {}: rejected (resubmit)".format(request_id),
                     body="""Dear {},

Your data request has been rejected for the following reason(s):

{}

You are however allowed to resubmit your data request. You may do so using this link: https://{}/datarequest/add/{}.

If you wish to object against this rejection, please contact the YOUth data manager.

With kind regards,
YOUth
""".format(researcher_name, feedback_for_researcher, YODA_PORTAL_FQDN, request_id))


def mail_assignment_rejected(ctx, researcher_email, researcher_name, feedback_for_researcher,
                             request_id):
    return mail.send(ctx,
                     to=researcher_email,
                     actor=user.full_name(ctx),
                     subject="YOUth data request {}: rejected".format(request_id),
                     body="""Dear {},

Your data request has been rejected for the following reason(s):

{}

If you wish to object against this rejection, please contact the YOUth data manager.

With kind regards,
YOUth
""".format(researcher_name, feedback_for_researcher))


def mail_review_researcher(ctx, researcher_email, researcher_name, request_id):
    return mail.send(ctx,
                     to=researcher_email,
                     actor=user.full_name(ctx),
                     subject="YOUth data request {}: reviewed".format(request_id),
                     body="""Dear {},

Your data request been reviewed by the YOUth Data Management Committee and is awaiting final evaluation by the YOUth Board of Directors.

The following link will take you directly to your data request: https://{}/datarequest/view/{}.

With kind regards,
YOUth
""".format(researcher_name, YODA_PORTAL_FQDN, request_id))


def mail_review_bodmember(ctx, bodmember_email, request_id):
    return mail.send(ctx,
                     to=bodmember_email,
                     actor=user.full_name(ctx),
                     subject="YOUth data request {}: reviewed".format(request_id),
                     body="""Dear Board of Directors member,

Data request {} has been reviewed by the YOUth Data Management Committee and is awaiting your final evaluation.

Please log into Yoda to evaluate the data request. The following link will take you directly to the evaluation form: https://{}/datarequest/evaluate/{}.

With kind regards,
YOUth
""".format(request_id, YODA_PORTAL_FQDN, request_id))


def mail_evaluation_approved_researcher(ctx, researcher_email, researcher_name,
                                        request_id):
    return mail.send(ctx,
                     to=researcher_email,
                     actor=user.full_name(ctx),
                     subject="YOUth data request {}: approved".format(request_id),
                     body="""Dear {},

Congratulations! Your data request has been approved. The YOUth data manager will now create a Data Transfer Agreement for you to sign. You will be notified when it is ready.

The following link will take you directly to your data request: https://{}/datarequest/view/{}.

With kind regards,
YOUth
""".format(researcher_name, YODA_PORTAL_FQDN, request_id))


def mail_evaluation_approved_datamanager(ctx, datamanager_email, request_id):
    return mail.send(ctx,
                     to=datamanager_email,
                     actor=user.full_name(ctx),
                     subject="YOUth data request {}: approved".format(request_id),
                     body="""Dear data manager,

Data request {} has been approved by the Board of Directors. Please sign in to Yoda to upload a Data Transfer Agreement for the researcher.

The following link will take you directly to the data request: https://{}/datarequest/view/{}.

With kind regards,
YOUth
""".format(request_id, YODA_PORTAL_FQDN, request_id))


def mail_evaluation_resubmit(ctx, researcher_email, researcher_name, feedback_for_researcher,
                             datamanager_email, request_id):
    return mail.send(ctx,
                     to=researcher_email,
                     actor=user.full_name(ctx),
                     subject="YOUth data request {}: rejected (resubmit)".format(request_id),
                     body="""Dear {},

Your data request has been rejected for the following reason(s):

{}

You are however allowed to resubmit your data request. You may do so using this link: https://{}/datarequest/add/{}.

If you wish to object against this rejection, please contact the YOUth data manager ({}).

The following link will take you directly to your data request: https://{}/datarequest/view/{}.

With kind regards,
YOUth
""".format(researcher_name, feedback_for_researcher, YODA_PORTAL_FQDN, request_id, datamanager_email, YODA_PORTAL_FQDN, request_id))


def mail_evaluation_rejected(ctx, researcher_email, researcher_name, feedback_for_researcher,
                             datamanager_email, request_id):
    return mail.send(ctx,
                     to=researcher_email,
                     actor=user.full_name(ctx),
                     subject="YOUth data request {}: rejected".format(request_id),
                     body="""Dear {},

Your data request has been rejected for the following reason(s):

{}

If you wish to object against this rejection, please contact the YOUth data manager ({}).

The following link will take you directly to your data request: https://{}/datarequest/view/{}.

With kind regards,
YOUth
""".format(researcher_name, feedback_for_researcher, datamanager_email, YODA_PORTAL_FQDN, request_id))


def mail_dta(ctx, researcher_email, researcher_name, request_id):
    return mail.send(ctx,
                     to=researcher_email,
                     actor=user.full_name(ctx),
                     subject="YOUth data request {}: DTA ready".format(request_id),
                     body="""Dear {},

The YOUth data manager has created a Data Transfer Agreement to formalize the transfer of the data you have requested. Please sign in to Yoda to download and read the Data Transfer Agreement.

The following link will take you directly to your data request: https://{}/datarequest/view/{}.

If you do not object to the agreement, please upload a signed copy of the agreement. After this, the YOUth data manager will prepare the requested data and will provide you with instructions on how to download them.

With kind regards,
YOUth
""".format(researcher_name, YODA_PORTAL_FQDN, request_id))


def mail_signed_dta(ctx, datamanager_email, request_id):
    return mail.send(ctx,
                     to=datamanager_email,
                     actor=user.full_name(ctx),
                     subject="YOUth data request {}: DTA signed".format(request_id),
                     body="""Dear data manager,

The researcher has uploaded a signed copy of the Data Transfer Agreement for data request {}.

Please log in to Yoda to review this copy. The following link will take you directly to the data request: https://{}/datarequest/view/{}.

After verifying that the document has been signed correctly, you may prepare the data for download. When the data is ready for the researcher to download, please click the \"Data ready\" button. This will notify the researcher by email that the requested data is ready. The email will include instructions on downloading the data.

With kind regards,
YOUth
""".format(request_id, YODA_PORTAL_FQDN, request_id))


def mail_data_ready(ctx, researcher_email, researcher_name, datamanager_email, request_id):
    return mail.send(ctx,
                     to=researcher_email,
                     actor=user.full_name(ctx),
                     subject="YOUth data request {}: data ready".format(request_id),
                     body="""Dear {},

The data you have requested is ready for you to download! For information on how to access the data through Yoda, see https://www.uu.nl/en/research/yoda/guide-to-yoda/i-want-to-start-using-yoda or contact the YOUth data manager ({}).

With kind regards,
YOUth
""".format(researcher_name, datamanager_email))
