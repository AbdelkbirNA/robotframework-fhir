*** Settings ***
Documentation     Laboratory results: glucose Observations against their reference range.
Resource          common.resource
Suite Setup       Prepare Patient

*** Test Cases ***
Normal Glucose Is Within Its Reference Range
    [Tags]    REQ-LAB-01
    ${obs}=    Create Observation For    ${PATIENT}    glucose_normal.json
    ${value}=    Observation Should Be Within Reference Range    ${obs}
    Should Be Equal As Numbers    ${value}    92

High Glucose Is Flagged Outside Its Reference Range
    [Tags]    REQ-LAB-02
    ${obs}=    Create Observation For    ${PATIENT}    glucose_high.json
    Observation Should Be Outside Reference Range    ${obs}
    Run Keyword And Expect Error    *above the reference range*
    ...    Observation Should Be Within Reference Range    ${obs}

Results Are Searchable By Patient And LOINC Code
    [Tags]    REQ-LAB-03
    ${found}=    Search Resources    Observation    subject=Patient/${PATIENT['id']}    code=http://loinc.org|2345-7
    Length Should Be    ${found}    2
    FOR    ${obs}    IN    @{found}
        Resource Value Should Be    ${obs}    code.coding[0].code    2345-7
        Resource Value Should Be    ${obs}    subject.reference    Patient/${PATIENT['id']}
    END

*** Keywords ***
Prepare Patient
    Connect To Test Server
    ${patient}=    Create Test Patient
    Set Suite Variable    ${PATIENT}    ${patient}
