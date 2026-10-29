"""Robot Framework keywords for testing a FHIR R4 server."""
import json
import re
from pathlib import Path

import requests
from robot.api import logger
from robot.api.deco import keyword, library

__version__ = "0.1.0"

FHIR_JSON = "application/fhir+json"
_STEP = re.compile(r"([A-Za-z_][\w]*)(?:\[(\d+)\])?")


def get_path(resource, path):
    """Value at a dotted path such as ``name[0].family``. Raises ``KeyError`` when absent."""
    value = resource
    for part in path.split("."):
        m = _STEP.fullmatch(part)
        if not m:
            raise ValueError(f"Invalid path step '{part}' in '{path}'")
        field, index = m.group(1), m.group(2)
        if not isinstance(value, dict) or field not in value:
            raise KeyError(f"'{path}': no field '{field}'")
        value = value[field]
        if index is not None:
            if not isinstance(value, list) or int(index) >= len(value):
                raise KeyError(f"'{path}': no element [{index}] in '{field}'")
            value = value[int(index)]
    return value


def outcome_errors(outcome):
    """Diagnostics of the error and fatal issues of an OperationOutcome."""
    return [i.get("diagnostics", i.get("code", "?")) for i in outcome.get("issue", [])
            if i.get("severity") in ("error", "fatal")]


def check_reference_range(observation):
    """Raise ``AssertionError`` when ``valueQuantity`` falls outside ``referenceRange[0]``."""
    value = get_path(observation, "valueQuantity.value")
    unit = observation["valueQuantity"].get("unit", "")
    ranges = observation.get("referenceRange") or []
    if not ranges:
        raise AssertionError("Observation has no referenceRange")
    low = ranges[0].get("low", {}).get("value")
    high = ranges[0].get("high", {}).get("value")
    if low is not None and value < low:
        raise AssertionError(f"{value} {unit} is below the reference range ({low} - {high})")
    if high is not None and value > high:
        raise AssertionError(f"{value} {unit} is above the reference range ({low} - {high})")
    return value


@library(scope="SUITE", version=__version__, doc_format="ROBOT")
class FhirLibrary:
    """Keywords to test a FHIR R4 REST server: CRUD on resources, search, profile
    validation and checks on clinical values.

    = Connection =

    Call `Connect To FHIR Server` first. Every request is sent with
    ``Content-Type: application/fhir+json``.

    = Resources =

    Resources are Robot Framework dictionaries. `Load Resource` reads one from a
    JSON file. Keywords that create or read a resource return the server's version.

    = Paths =

    `Resource Value Should Be` and `Get Resource Value` take a dotted path into the
    resource, with list indexes: ``name[0].family``, ``code.coding[0].code``.

    = Example =

    | `Connect To FHIR Server` | http://localhost:8080/fhir |
    | ${patient}= | `Load Resource` | ${CURDIR}/data/patient.json |
    | ${created}= | `Create Resource` | ${patient} |
    | `Resource Value Should Be` | ${created} | name[0].family | Martin |
    """

    def __init__(self, timeout=30):
        self._timeout = float(timeout)
        self._base = None
        self._session = requests.Session()
        self._session.headers.update({"Accept": FHIR_JSON, "Content-Type": FHIR_JSON})
        self.last_response = None

    # ------------------------------------------------------------- connection

    @keyword("Connect To FHIR Server")
    def connect_to_fhir_server(self, base_url):
        """Sets the server base URL, then checks it answers ``/metadata`` with a
        CapabilityStatement. Returns the FHIR version the server declares."""
        self._base = base_url.rstrip("/")
        statement = self._send("GET", "metadata", expected=200)
        if statement.get("resourceType") != "CapabilityStatement":
            raise AssertionError(f"/metadata returned {statement.get('resourceType')}, not a CapabilityStatement")
        logger.info(f"Connected to {self._base}, FHIR {statement.get('fhirVersion')}")
        return statement.get("fhirVersion")

    # ------------------------------------------------------------------- CRUD

    @keyword
    def load_resource(self, path):
        """Reads a FHIR resource from a JSON file and returns it as a dictionary."""
        resource = json.loads(Path(path).read_text(encoding="utf-8"))
        if "resourceType" not in resource:
            raise ValueError(f"{path} has no resourceType")
        return resource

    @keyword
    def create_resource(self, resource):
        """Creates the resource with POST and returns the created resource, ``id`` included.
        Fails unless the server answers 201."""
        return self._send("POST", resource["resourceType"], json_body=resource, expected=201)

    @keyword
    def read_resource(self, resource_type, resource_id):
        """Reads a resource with GET ``[type]/[id]``. Fails unless the server answers 200."""
        return self._send("GET", f"{resource_type}/{resource_id}", expected=200)

    @keyword
    def update_resource(self, resource):
        """Replaces the resource with PUT ``[type]/[id]`` and returns the server's version.
        The resource must carry its ``id``."""
        path = f"{resource['resourceType']}/{resource['id']}"
        return self._send("PUT", path, json_body=resource, expected=200)

    @keyword
    def delete_resource(self, resource_type, resource_id):
        """Deletes a resource. Accepts 200 and 204, the two answers FHIR allows."""
        self._send("DELETE", f"{resource_type}/{resource_id}", expected=(200, 204))

    @keyword
    def resource_should_not_exist(self, resource_type, resource_id):
        """Passes when reading the resource answers 404 or 410 (deleted)."""
        self._send("GET", f"{resource_type}/{resource_id}", expected=(404, 410))

    # ----------------------------------------------------------------- search

    @keyword
    def search_resources(self, resource_type, **params):
        """Searches with GET ``[type]?params`` and returns the matching resources as a list.

        | ${found}= | `Search Resources` | Patient | family=Martin | birthdate=1958-03-14 |
        """
        bundle = self._send("GET", resource_type, params=params, expected=200)
        if bundle.get("resourceType") != "Bundle":
            raise AssertionError(f"Search returned {bundle.get('resourceType')}, not a Bundle")
        return [e["resource"] for e in bundle.get("entry", []) if "resource" in e]

    # ------------------------------------------------------------- validation

    @keyword
    def resource_should_be_valid(self, resource):
        """Sends the resource to the server's ``$validate`` operation and fails when the
        OperationOutcome holds an ``error`` or ``fatal`` issue."""
        outcome = self._validate(resource)
        errors = outcome_errors(outcome)
        if errors:
            raise AssertionError("Resource is not valid:\n- " + "\n- ".join(errors))

    @keyword
    def resource_should_be_invalid(self, resource, expected_message=None):
        """Fails when ``$validate`` finds no error. With ``expected_message``, one error
        must contain that text."""
        errors = outcome_errors(self._validate(resource))
        if not errors:
            raise AssertionError("Resource was expected to be invalid, the server found no error")
        if expected_message and not any(expected_message in e for e in errors):
            raise AssertionError(f"No error contains '{expected_message}':\n- " + "\n- ".join(errors))

    # ----------------------------------------------------------------- checks

    @keyword
    def get_resource_value(self, resource, path):
        """Returns the value at a dotted path, see `Paths`."""
        return get_path(resource, path)

    @keyword
    def resource_value_should_be(self, resource, path, expected):
        """Fails when the value at ``path`` differs from ``expected``, compared as strings."""
        actual = get_path(resource, path)
        if str(actual) != str(expected):
            raise AssertionError(f"{path}: expected '{expected}', got '{actual}'")

    @keyword
    def observation_should_be_within_reference_range(self, observation):
        """Fails when the Observation's ``valueQuantity`` is outside its first
        ``referenceRange``. Returns the value."""
        return check_reference_range(observation)

    @keyword
    def observation_should_be_outside_reference_range(self, observation):
        """Passes when ``valueQuantity`` is below or above the first ``referenceRange``:
        the abnormal-result case."""
        try:
            check_reference_range(observation)
        except AssertionError as e:
            if "no referenceRange" in str(e):
                raise
            logger.info(str(e))
            return
        raise AssertionError("Observation value is within its reference range")

    @keyword
    def status_should_be(self, expected):
        """Checks the HTTP status of the last request."""
        if self.last_response is None:
            raise AssertionError("No request sent yet")
        if self.last_response.status_code != int(expected):
            raise AssertionError(f"Expected HTTP {expected}, got {self.last_response.status_code}")

    # --------------------------------------------------------------- internal

    def _validate(self, resource):
        return self._send("POST", f"{resource['resourceType']}/$validate",
                          json_body=resource, expected=(200, 400, 422))

    def _send(self, method, path, json_body=None, params=None, expected=200):
        if self._base is None:
            raise RuntimeError("Call 'Connect To FHIR Server' first")
        url = f"{self._base}/{path}"
        resp = self._session.request(method, url, json=json_body, params=params, timeout=self._timeout)
        self.last_response = resp
        logger.debug(f"{method} {resp.url} -> {resp.status_code}")
        allowed = expected if isinstance(expected, tuple) else (expected,)
        if resp.status_code not in allowed:
            detail = resp.text[:500]
            try:
                detail = "; ".join(outcome_errors(resp.json())) or detail
            except ValueError:
                pass
            raise AssertionError(f"{method} {path}: expected HTTP {' or '.join(map(str, allowed))}, "
                                 f"got {resp.status_code}: {detail}")
        return resp.json() if resp.content else {}
