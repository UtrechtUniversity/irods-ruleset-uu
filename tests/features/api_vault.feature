Feature: Vault API

    Examples:
        | vault                         |
        | /tempZone/home/vault-initial1 |

    Scenario: Vault submit
        Given data package exists in "<vault>"
        And the Yoda vault submit API is queried on datapackage in "<vault>"
        Then the response status code is "200"
        And data package status is "SUBMITTED_FOR_PUBLICATION"

    Scenario: Vault cancel
        Given data package exists in "<vault>"
        And the Yoda vault cancel API is queried on datapackage in "<vault>"
        Then the response status code is "200"
        And data package status is "UNPUBLISHED"

    Scenario: Vault submit after cancel
        Given data package exists in "<vault>"
        And the Yoda vault submit API is queried on datapackage in "<vault>"
        Then the response status code is "200"
        And data package status is "SUBMITTED_FOR_PUBLICATION"

    Scenario: Vault approve
        Given data package exists in "<vault>"
        And the Yoda vault approve API is queried on datapackage in "<vault>"
        Then the response status code is "200"
        And data package status is "APPROVED_FOR_PUBLICATION"
