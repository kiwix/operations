import json
import subprocess
from typing import Any

import pytest


def get_kube_data(*args: str) -> tuple[int, list[dict[str, Any]]]:
    ps = subprocess.run(
        ["/usr/bin/env", "kubectl", "-o", "json", *args],
        text=True,
        capture_output=True,
        check=False,
    )
    payload = json.loads(ps.stdout)
    return ps.returncode, payload["items"]


def get_certificates() -> list[dict[str, Any]]:
    retcode, payload = get_kube_data("get", "certificate", "--all-namespaces")
    assert retcode == 0
    return [entry for entry in payload if entry.get("kind", "") == "Certificate"]


certificates = get_certificates()


@pytest.mark.parametrize(
    "certificate",
    certificates,
    ids=[cert["spec"]["commonName"] for cert in certificates],
)
def test_certificates_expiry(certificate):
    assert (
        certificate["status"]["conditions"][0]["message"]
        == "Certificate is up to date and has not expired"
    )
