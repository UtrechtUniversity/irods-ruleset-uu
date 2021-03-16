# coding=utf-8
"""Datarequest API feature tests."""

__copyright__ = 'Copyright (c) 2020, Utrecht University'
__license__   = 'GPLv3, see LICENSE'

from pytest_bdd import (
    given,
    parsers,
    scenarios,
    then,
)

from conftest import api_request, post_form_data

scenarios('../../features/api/api_datarequest.feature')


@given('the Yoda datarequest browse API is queried', target_fixture="api_response")
def api_datarequest_browse(user):
    return api_request(
        user,
        "datarequest_browse",
        {}
    )


@given('the Yoda datarequest schema get API is queried with schema name "<schema_name>"', target_fixture="api_response")
def api_datarequest_schema_get(user, schema_name):
    return api_request(
        user,
        "datarequest_schema_get",
        {"schema_name": schema_name}
    )


@given('the Yoda datarequest submit API is queried with data', target_fixture="api_response")
def api_datarequest_submit(user):
    return api_request(
        user,
        "datarequest_submit",
        {"data": {
            "introduction": {},
            "researchers": {
                "contacts": [{
                    "name": "test",
                    "institution": "test",
                    "department": "test",
                    "academic_role": "test",
                    "work_address": "test",
                    "email": "test",
                    "phone": "test"
                }]
            },
            "datarequest": {
                "data": {
                    "selectedRows": [{
                        "expId": 1,
                        "expCohort": 1,
                        "expWave": 7,
                        "expType": 0,
                        "expSubject": 0,
                        "expName": "Blood",
                        "expInfo": ""
                    }]
                },
                "purpose": "Analyses for data assessment only (results will not be published)",
                "data_lock_notification": True,
                "publication_approval": True
            },
            "research_context": {
                "title": "test",
                "background": "test",
                "research_question": "test",
                "requested_data_summary": "test"
            },
            "hypotheses": {},
            "methods": {
                "design": "test",
                "preparation": "test",
                "processing": "test"
            },
            "contribution": {
                "contribution_time": "No",
                "contribution_financial": "Yes",
                "contribution_favor": "No",
                "contribution_financial_amount": 9000
            }
        }, "previous_request_id": None,
        })


@given('datarequest exists', target_fixture="datarequest_id")
def datarequest_exists(user):
    http_status, body = api_request(
        user,
        "datarequest_browse",
        {"sort_order": "desc"}
    )

    assert http_status == 200
    assert len(body["data"]["items"]) > 0

    return body["data"]["items"][0]["id"]


@given('the Yoda datarequest is owner API is queried with request id', target_fixture="api_response")
def api_datarequest_is_owner(user, datarequest_id):
    return api_request(
        user,
        "datarequest_is_owner",
        {"request_id": datarequest_id}
    )


@given('the Yoda datarequest is datamanager API is queried', target_fixture="api_response")
def api_datarequest_is_datamanager(user):
    return api_request(
        user,
        "datarequest_is_datamanager",
        {}
    )


@given('the Yoda datarequest is BoD member API is queried', target_fixture="api_response")
def api_datarequest_is_bod_member(user):
    return api_request(
        user,
        "datarequest_is_bod_member",
        {}
    )


@given('the Yoda datarequest is DMC member API is queried', target_fixture="api_response")
def api_datarequest_is_dmc_member(user):
    return api_request(
        user,
        "datarequest_is_dmc_member",
        {}
    )


@given('the Yoda datarequest is reviewer API is queried with request id', target_fixture="api_response")
def api_datarequest_is_reviewer(user, datarequest_id):
    return api_request(
        user,
        "datarequest_is_reviewer",
        {"request_id": datarequest_id}
    )


@given('the Yoda datarequest get API is queried with request id', target_fixture="api_response")
def api_datarequest_get(user, datarequest_id):
    return api_request(
        user,
        "datarequest_get",
        {"request_id": datarequest_id}
    )


@given('the Yoda datarequest preliminary review submit API is queried with request id', target_fixture="api_response")
def api_datarequest_preliminary_submit(user, datarequest_id):
    return api_request(
        user,
        "datarequest_preliminary_review_submit",
        {"data": {"preliminary_review": "Accepted for data manager review", "internal_remarks": "test"}, "request_id": datarequest_id}
    )


@given('the Yoda datarequest preliminary review get API is queried with request id', target_fixture="api_response")
def api_datarequest_preliminary_get(user, datarequest_id):
    return api_request(
        user,
        "datarequest_preliminary_review_get",
        {"request_id": datarequest_id}
    )


@given('the Yoda datarequest datamanager review submit API is queried with request id', target_fixture="api_response")
def api_datarequest_datamanager_review_submit(user, datarequest_id):
    return api_request(
        user,
        "datarequest_datamanager_review_submit",
        {"data": {"datamanager_review": "Accepted", "datamanager_remarks": "test"}, "request_id": datarequest_id}
    )


@given('the Yoda datarequest datamanager review get API is queried with request id', target_fixture="api_response")
def api_datarequest_review_get(user, datarequest_id):
    return api_request(
        user,
        "datarequest_datamanager_review_get",
        {"request_id": datarequest_id}
    )


@given('the datarequest assignment submit API is queried with request id', target_fixture="api_response")
def api_datarequest_assignment_submit(user, datarequest_id):
    return api_request(
        user,
        "datarequest_assignment_submit",
        {"data": {"decision": "Accepted for DMC review", "response_to_dm_remarks": "test", "assign_to": ["dmcmember"]}, "request_id": datarequest_id}
    )


@given('the Yoda datarequest assignment get API is queried with request id', target_fixture="api_response")
def api_datarequest_assignment_get(user, datarequest_id):
    return api_request(
        user,
        "datarequest_assignment_get",
        {"request_id": datarequest_id}
    )


@given('the datarequest review submit API is queried with request id', target_fixture="api_response")
def api_datarequest_review_submit(user, datarequest_id):
    return api_request(
        user,
        "datarequest_review_submit",
        {"data": {"biological_samples": "No", "evaluation": "Approve", "contribution": "test", "informed_consent_fit": "test", "research_question_answerability": "test", "study_quality": "test", "logistical_feasibility": "test", "study_value": "test", "researcher_expertise": "test", "username": "functionaladminpriv"}, "request_id": datarequest_id}
    )


@given('the Yoda datarequest reviews get API is queried with request id', target_fixture="api_response")
def api_datarequest_reviews_get(user, datarequest_id):
    return api_request(
        user,
        "datarequest_reviews_get",
        {"request_id": datarequest_id}
    )


@given('the datarequest evaluation submit API is queried with request id', target_fixture="api_response")
def api_datarequest_evaluation_submit(user, datarequest_id):
    return api_request(
        user,
        "datarequest_evaluation_submit",
        {"data": {"evaluation": "Approved"}, "request_id": datarequest_id}
    )


@given('the datarequest feedback get API is queried with request id', target_fixture="api_response")
def api_datarequest_feedback_get(user, datarequest_id):
    return api_request(
        user,
        "datarequest_feedback_get",
        {"request_id": datarequest_id}
    )


@given('DTA is uploaded', target_fixture="api_response")
def api_datarequest_dta_upload(user, datarequest_id):
    return post_form_data(
        user,
        "/datarequest/datarequest/upload_dta/{}".format(datarequest_id),
        {"data": ("dta.pdf", "test")}
    )


@given('signed DTA is uploaded', target_fixture="api_response")
def api_datarequest_signed_dta_upload(user, datarequest_id):
    return post_form_data(
        user,
        "/datarequest/datarequest/upload_signed_dta/{}".format(datarequest_id),
        {"data": ("signed_dta.pdf", "test")}

    )


@given('the datarequest data ready API is queried with request id', target_fixture="api_response")
def api_datarequest_data_ready(user, datarequest_id):
    return api_request(
        user,
        "datarequest_data_ready",
        {"request_id": datarequest_id}
    )


@then(parsers.parse('the response status code is "{code:d}"'))
def api_response_code(api_response, code):
    http_status, _ = api_response
    assert http_status == code


@then(parsers.parse('request status is "{status}"'))
def request_status(user, datarequest_id, status):
    _, body = api_request(
        user,
        "datarequest_get",
        {"request_id": datarequest_id}
    )

    assert len(body['data']) > 0
    assert body['data']['requestStatus'] == status


@then('the result is "<result>"')
def result_is(api_response, result):
    _, body = api_response

    assert str(body['data']) == result
