*** Settings ***
Documentation     Patient lifecycle: create, read, search, update, delete.
Resource          common.resource
Suite Setup       Connect To Test Server

*** Test Cases ***
Create And Read A Patient
    [Tags]    REQ-PAT-01
    ${created}=    Create Test Patient
    Status Should Be    201
    ${read}=    Read Resource    Patient    ${created['id']}
    Resource Value Should Be    ${read}    name[0].given[0]    Claire
    Resource Value Should Be    ${read}    birthDate    1958-03-14

Search A Patient By Family Name
    [Tags]    REQ-PAT-02
    ${created}=    Create Test Patient
    ${family}=    Get Resource Value    ${created}    name[0].family
    ${found}=    Search Resources    Patient    family=${family}
    Length Should Be    ${found}    1
    Should Be Equal    ${found[0]['id']}    ${created['id']}

Update A Patient
    [Tags]    REQ-PAT-03
    ${created}=    Create Test Patient
    Set To Dictionary    ${created}    birthDate=1958-03-15
    ${updated}=    Update Resource    ${created}
    Resource Value Should Be    ${updated}    meta.versionId    2
    ${read}=    Read Resource    Patient    ${created['id']}
    Resource Value Should Be    ${read}    birthDate    1958-03-15

Delete A Patient
    [Tags]    REQ-PAT-04
    ${created}=    Create Test Patient
    Delete Resource    Patient    ${created['id']}
    Resource Should Not Exist    Patient    ${created['id']}
