*** Settings ***
Documentation     Shared settings: library import, server URL and patient creation.
Library           FhirLibrary
Library           Collections

*** Variables ***
${FHIR_URL}       http://localhost:8080/fhir
${DATA}           ${CURDIR}/data

*** Keywords ***
Connect To Test Server
    ${version}=    Connect To FHIR Server    ${FHIR_URL}
    Should Start With    ${version}    4.

Create Test Patient
    [Documentation]    Creates the reference patient with a family name unique to this run.
    ${patient}=    Load Resource    ${DATA}/patient.json
    ${run}=    Evaluate    __import__('uuid').uuid4().hex[:8]
    Set To Dictionary    ${patient['name'][0]}    family=Martin-${run}
    ${created}=    Create Resource    ${patient}
    RETURN    ${created}

Create Observation For
    [Arguments]    ${patient}    ${file}
    ${obs}=    Load Resource    ${DATA}/${file}
    Set To Dictionary    ${obs}    subject=${{ {'reference': 'Patient/' + $patient['id']} }}
    ${created}=    Create Resource    ${obs}
    RETURN    ${created}
