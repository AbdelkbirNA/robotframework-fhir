*** Settings ***
Documentation     Profile validation through the server's $validate operation.
Resource          common.resource
Suite Setup       Connect To Test Server

*** Test Cases ***
A Conformant Patient Passes Validation
    [Tags]    REQ-VAL-01
    ${patient}=    Load Resource    ${DATA}/patient.json
    Resource Should Be Valid    ${patient}

A Patient With An Unknown Gender Code Is Rejected
    [Tags]    REQ-VAL-02
    ${patient}=    Load Resource    ${DATA}/patient_invalid_gender.json
    Resource Should Be Invalid    ${patient}    femme

A Glucose Result Passes Validation
    [Tags]    REQ-VAL-03
    ${obs}=    Load Resource    ${DATA}/glucose_normal.json
    Resource Should Be Valid    ${obs}
