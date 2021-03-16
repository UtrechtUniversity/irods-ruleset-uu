@datarequest
Feature: Datarequest API

    Scenario: Datarequest browse
        Given user "researcher" is authenticated
        And the Yoda datarequest browse API is queried
        Then the response status code is "200"

    Scenario: Datarequest schema get
        Given user "researcher" is authenticated
        And the Yoda datarequest schema get API is queried with schema name "<schema_name>"
        Then the response status code is "200"

        Examples:
            | schema_name        |
            | datarequest        |
            | preliminary_review |
            | datamanager_review |
            | review             |
            | assignment         |
            | evaluation         |

    Scenario: Datarequest submit
        Given user "researcher" is authenticated
        And the Yoda datarequest submit API is queried with data
        Then the response status code is "200"

    Scenario: Datarequest is owner
        Given user "<user>" is authenticated
        And datarequest exists
        And the Yoda datarequest is owner API is queried with request id
        Then the response status code is "200"
        And the result is "<result>"

        Examples:
            | user        | result |
            | researcher  | True   |
            | datamanager | False  |
            | bodmember   | False  |
            | dmcmember   | False  |

    Scenario: Datarequest is datamanager
        Given user "<user>" is authenticated
        And the Yoda datarequest is datamanager API is queried
        Then the response status code is "200"
        And the result is "<result>"

        Examples:
            | user        | result |
            | researcher  | False  |
            | datamanager | True   |
            | bodmember   | False  |
            | dmcmember   | False  |

    Scenario: Datarequest is BoD member
        Given user "<user>" is authenticated
        And the Yoda datarequest is BoD member API is queried
        Then the response status code is "200"
        And the result is "<result>"

        Examples:
            | user        | result |
            | researcher  | False  |
            | datamanager | False  |
            | bodmember   | True   |
            | dmcmember   | False  |

    Scenario: Datarequest is DMC member
        Given user "<user>" is authenticated
        And the Yoda datarequest is DMC member API is queried
        Then the response status code is "200"
        And the result is "<result>"

        Examples:
            | user        | result |
            | researcher  | False  |
            | datamanager | False  |
            | bodmember   | False  |
            | dmcmember   | True   |

    Scenario: Datarequest get
        Given user "researcher" is authenticated
        And datarequest exists
        And the Yoda datarequest get API is queried with request id
        Then the response status code is "200"
        And request status is "SUBMITTED"

    Scenario: Datarequest preliminary review submit
        Given user "bodmember" is authenticated
        And datarequest exists
        And the Yoda datarequest preliminary review submit API is queried with request id
        Then the response status code is "200"
        And request status is "PRELIMINARY_ACCEPT"

    Scenario: Datarequest preliminary review get
        Given user "bodmember" is authenticated
        And datarequest exists
        And the Yoda datarequest preliminary review get API is queried with request id
        Then the response status code is "200"

    Scenario: Datarequest datamanager review submit
        Given user "datamanager" is authenticated
        And datarequest exists
        And the Yoda datarequest datamanager review submit API is queried with request id
        Then the response status code is "200"
        And request status is "DATAMANAGER_ACCEPT"

    Scenario: Datarequest datamanager review get
        Given user "bodmember" is authenticated
        And datarequest exists
        And the Yoda datarequest datamanager review get API is queried with request id
        Then the response status code is "200"

    Scenario: Datarequest assignment submit
        Given user "bodmember" is authenticated
        And datarequest exists
        And the datarequest assignment submit API is queried with request id
        Then the response status code is "200"
        And request status is "UNDER_REVIEW"

    Scenario: Datarequest assignment get
        Given user "bodmember" is authenticated
        And datarequest exists
        And the Yoda datarequest assignment get API is queried with request id
        Then the response status code is "200"

    Scenario: Datarequest is reviewer
        Given user "<user>" is authenticated
        And datarequest exists
        And the Yoda datarequest is reviewer API is queried with request id
        Then the response status code is "200"
        And the result is "<result>"

        Examples:
            | user        | result |
            | researcher  | False  |
            | datamanager | False  |
            | bodmember   | False  |
            | dmcmember   | True   |

    Scenario: Datarequest review submit
        Given user "dmcmember" is authenticated
        And datarequest exists
        And the datarequest review submit API is queried with request id
        Then the response status code is "200"
        And request status is "REVIEWED"

    Scenario: Datarequest reviews get
        Given user "bodmember" is authenticated
        And datarequest exists
        And the Yoda datarequest reviews get API is queried with request id
        Then the response status code is "200"

    Scenario: Datarequest evaluation submit
        Given user "bodmember" is authenticated
        And datarequest exists
        And the datarequest evaluation submit API is queried with request id
        Then the response status code is "200"
        And request status is "APPROVED"

    Scenario: Datarequest feedback get
        Given user "researcher" is authenticated
        And datarequest exists
        And the datarequest feedback get API is queried with request id
        Then the response status code is "400"

    Scenario: Datarequest datamanager upload DTA
        Given user "datamanager" is authenticated
        And datarequest exists
        And DTA is uploaded
        Then the response status code is "200"
        And request status is "DTA_READY"

    Scenario: Datarequest researcher upload signed DTA
        Given user "researcher" is authenticated
        And datarequest exists
        And signed DTA is uploaded
        Then the response status code is "200"
        And request status is "DTA_SIGNED"

    Scenario: Datarequest datamanager data ready
        Given user "datamanager" is authenticated
        And datarequest exists
        And the datarequest data ready API is queried with request id
        Then the response status code is "200"
        And request status is "DATA_READY"

#    Scenario: Datarequest resubmit
#        Given the Yoda datarequest submit API is queried with <data> and <previous_request_id>
#        Then the response status code is "200"
