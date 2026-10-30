"""Service activation refuses absent, unreadable and default system identities."""

import pytest

from app.tools.service_preflight import configured_identity


@pytest.mark.parametrize(
    "report",
    [
        {},
        {"service_query": "NOT_INSTALLED"},
        {"service_query": "UNAVAILABLE", "service_identity": "PC\\operator"},
        {"service_query": "OK", "service_identity": None},
        {"service_query": "OK", "service_identity": " "},
        {"service_query": "OK", "service_identity": "LocalSystem"},
        {"service_query": "OK", "service_identity": " NT AUTHORITY\\SYSTEM "},
        {"service_query": "OK", "service_identity": ".\\LocalSystem"},
    ],
)
def test_unverified_or_system_identity_cannot_activate(report):
    assert not configured_identity(report)


def test_explicit_account_is_only_identity_check_not_runtime_acceptance():
    report = {
        "service_query": "OK",
        "service_identity": "PC\\operator",
        "identity_tls_dpapi_verified": False,
        "lifecycle_verified": False,
    }
    assert configured_identity(report)
    assert not report["identity_tls_dpapi_verified"]
    assert not report["lifecycle_verified"]
