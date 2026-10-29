"""Unit tests of the pure helpers, no server needed."""
import pytest

from FhirLibrary import check_reference_range, get_path, outcome_errors

PATIENT = {"name": [{"family": "Martin", "given": ["Claire"]}], "gender": "female"}


def obs(value, low=70, high=99):
    return {"valueQuantity": {"value": value, "unit": "mg/dL"},
            "referenceRange": [{"low": {"value": low}, "high": {"value": high}}]}


def test_get_path_follows_fields_and_indexes():
    assert get_path(PATIENT, "name[0].given[0]") == "Claire"
    assert get_path(PATIENT, "gender") == "female"


@pytest.mark.parametrize("path", ["name[1].family", "address", "name[0].prefix"])
def test_get_path_raises_on_missing(path):
    with pytest.raises(KeyError):
        get_path(PATIENT, path)


def test_reference_range_accepts_bounds_and_inside():
    for v in (70, 92, 99):
        assert check_reference_range(obs(v)) == v


@pytest.mark.parametrize("value,word", [(69, "below"), (182, "above")])
def test_reference_range_flags_outside(value, word):
    with pytest.raises(AssertionError, match=word):
        check_reference_range(obs(value))


def test_reference_range_requires_a_range():
    with pytest.raises(AssertionError, match="no referenceRange"):
        check_reference_range({"valueQuantity": {"value": 1}})


def test_outcome_errors_keeps_errors_and_fatals_only():
    outcome = {"issue": [{"severity": "information", "diagnostics": "ok"},
                         {"severity": "error", "diagnostics": "bad code"},
                         {"severity": "fatal", "code": "structure"}]}
    assert outcome_errors(outcome) == ["bad code", "structure"]
