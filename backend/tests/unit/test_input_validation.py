"""
Unit tests for input validation logic:
  - _validate_target_value() and detect_target_type() from app.api.v1.targets
  - _build_nuclei_cmd() and _sanitise_extra_flags() from app.workers.scan_tasks
"""
import os
import uuid
import pytest
from unittest.mock import MagicMock
from fastapi import HTTPException

from app.api.v1.targets import _validate_target_value, detect_target_type
from app.models.target import TargetType
from app.workers.scan_tasks import _build_nuclei_cmd, _sanitise_extra_flags, ALLOWED_EXTRA_FLAGS


# ── _validate_target_value — valid inputs ─────────────────────────────────────

def test_valid_https_url():
    result = _validate_target_value("https://example.com")
    assert result == "https://example.com"


def test_valid_http_url_with_path_and_query():
    result = _validate_target_value("http://example.com/path?q=1&foo=bar")
    assert result == "http://example.com/path?q=1&foo=bar"


def test_valid_public_ip():
    result = _validate_target_value("8.8.8.8")
    assert result == "8.8.8.8"


def test_valid_cidr():
    result = _validate_target_value("1.2.3.0/24")
    assert result == "1.2.3.0/24"


def test_valid_domain():
    result = _validate_target_value("example.com")
    assert result == "example.com"


def test_valid_subdomain():
    result = _validate_target_value("sub.example.com")
    assert result == "sub.example.com"


def test_strips_leading_trailing_whitespace():
    result = _validate_target_value("  https://example.com  ")
    assert result == "https://example.com"


# ── _validate_target_value — control character injection ─────────────────────

def test_rejects_url_with_newline():
    with pytest.raises(HTTPException) as exc_info:
        _validate_target_value("http://evil.com\nnewline")
    assert exc_info.value.status_code == 400


def test_rejects_url_with_carriage_return():
    with pytest.raises(HTTPException) as exc_info:
        _validate_target_value("http://evil.com\rheader-injection")
    assert exc_info.value.status_code == 400


def test_rejects_null_byte():
    with pytest.raises(HTTPException) as exc_info:
        _validate_target_value("http://evil.com\x00null")
    assert exc_info.value.status_code == 400


def test_rejects_tab_in_value():
    with pytest.raises(HTTPException) as exc_info:
        _validate_target_value("http://evil.com\ttab")
    assert exc_info.value.status_code == 400


# ── _validate_target_value — dangerous protocols ──────────────────────────────

def test_rejects_javascript_protocol():
    with pytest.raises(HTTPException) as exc_info:
        _validate_target_value("javascript://alert(1)")
    assert exc_info.value.status_code == 400


def test_rejects_data_protocol():
    with pytest.raises(HTTPException) as exc_info:
        _validate_target_value("data:text/html,<h1>XSS</h1>")
    assert exc_info.value.status_code == 400


def test_rejects_file_protocol():
    with pytest.raises(HTTPException) as exc_info:
        _validate_target_value("file:///etc/passwd")
    assert exc_info.value.status_code == 400


def test_rejects_ftp_protocol():
    with pytest.raises(HTTPException) as exc_info:
        _validate_target_value("ftp://evil.com/")
    assert exc_info.value.status_code == 400


def test_rejects_ldap_protocol():
    with pytest.raises(HTTPException) as exc_info:
        _validate_target_value("ldap://internal.corp/")
    assert exc_info.value.status_code == 400


def test_rejects_gopher_protocol():
    with pytest.raises(HTTPException) as exc_info:
        _validate_target_value("gopher://evil.com/")
    assert exc_info.value.status_code == 400


# ── _validate_target_value — SSRF / localhost ─────────────────────────────────

def test_rejects_localhost_url():
    with pytest.raises(HTTPException) as exc_info:
        _validate_target_value("http://localhost/internal")
    assert exc_info.value.status_code == 400


def test_rejects_loopback_ip_url():
    with pytest.raises(HTTPException) as exc_info:
        _validate_target_value("http://127.0.0.1/admin")
    assert exc_info.value.status_code == 400


def test_rejects_aws_metadata_url():
    with pytest.raises(HTTPException) as exc_info:
        _validate_target_value("http://169.254.169.254/latest/meta-data/")
    assert exc_info.value.status_code == 400


def test_rejects_private_ip_10_network():
    with pytest.raises(HTTPException) as exc_info:
        _validate_target_value("http://10.0.0.1/")
    assert exc_info.value.status_code == 400


def test_rejects_private_ip_192_168():
    with pytest.raises(HTTPException) as exc_info:
        _validate_target_value("http://192.168.1.1/")
    assert exc_info.value.status_code == 400


def test_rejects_localhost_domain_without_protocol():
    with pytest.raises(HTTPException) as exc_info:
        _validate_target_value("localhost")
    assert exc_info.value.status_code == 400


def test_rejects_private_cidr_10_network():
    with pytest.raises(HTTPException) as exc_info:
        _validate_target_value("10.0.0.0/8")
    assert exc_info.value.status_code == 400


def test_rejects_loopback_cidr():
    with pytest.raises(HTTPException) as exc_info:
        _validate_target_value("127.0.0.0/8")
    assert exc_info.value.status_code == 400


# ── _validate_target_value — CIDR validation ──────────────────────────────────

def test_rejects_invalid_cidr_bad_octet():
    with pytest.raises(HTTPException) as exc_info:
        _validate_target_value("300.0.0.0/8")
    assert exc_info.value.status_code == 400


def test_rejects_invalid_cidr_mask_too_large():
    with pytest.raises(HTTPException) as exc_info:
        _validate_target_value("192.168.1.0/33")
    assert exc_info.value.status_code == 400


# ── _validate_target_value — IP validation ────────────────────────────────────

def test_rejects_invalid_ip():
    with pytest.raises(HTTPException) as exc_info:
        _validate_target_value("999.999.999.999")
    assert exc_info.value.status_code == 400


# ── _validate_target_value — size limit ──────────────────────────────────────

def test_rejects_value_over_2048_chars():
    with pytest.raises(HTTPException) as exc_info:
        _validate_target_value("https://example.com/" + "a" * 2050)
    assert exc_info.value.status_code == 400


def test_rejects_empty_value():
    with pytest.raises(HTTPException) as exc_info:
        _validate_target_value("")
    assert exc_info.value.status_code == 400


# ── detect_target_type ────────────────────────────────────────────────────────

def test_detect_url_https():
    assert detect_target_type("https://example.com") == TargetType.URL


def test_detect_url_http():
    assert detect_target_type("http://example.com/path?q=1") == TargetType.URL


def test_detect_ip():
    assert detect_target_type("192.0.2.1") == TargetType.IP


def test_detect_cidr():
    assert detect_target_type("1.2.3.0/24") == TargetType.CIDR


def test_detect_domain():
    assert detect_target_type("example.com") == TargetType.DOMAIN


def test_detect_subdomain():
    assert detect_target_type("sub.example.com") == TargetType.DOMAIN


# ── _sanitise_extra_flags ─────────────────────────────────────────────────────

def test_allowed_flag_passes():
    result = _sanitise_extra_flags(["-headless"])
    assert result == ["-headless"]


def test_multiple_allowed_flags():
    result = _sanitise_extra_flags(["-headless", "-no-interactsh", "-silent"])
    assert result == ["-headless", "-no-interactsh", "-silent"]


def test_disallowed_flag_is_rejected():
    result = _sanitise_extra_flags(["--exec", "/bin/sh"])
    assert result == []


def test_mixed_allowed_and_disallowed():
    result = _sanitise_extra_flags(["-headless", "--rm-rf", "-silent"])
    assert "-headless" in result
    assert "-silent" in result
    assert "--rm-rf" not in result


def test_flag_with_equals_value_allowed():
    # Flags like -max-redirects=5 use the base flag name for whitelist check
    result = _sanitise_extra_flags(["-max-redirects=5"])
    assert result == ["-max-redirects=5"]


def test_empty_flags_list():
    result = _sanitise_extra_flags([])
    assert result == []


def test_blank_flag_strings_ignored():
    result = _sanitise_extra_flags(["", "   "])
    assert result == []


def test_shell_injection_attempt_rejected():
    malicious = ["; rm -rf /", "$(whoami)", "`id`", "-headless && curl evil.com"]
    result = _sanitise_extra_flags(malicious)
    assert result == []


# ── _build_nuclei_cmd — structural guarantees ─────────────────────────────────

def _make_scan(config: dict):
    """Create a minimal mock Scan object with the given config."""
    scan = MagicMock()
    scan.config = config
    scan.id = str(uuid.uuid4())
    return scan


def test_build_cmd_returns_list(tmp_path):
    scan = _make_scan({"rate_limit": 100})
    targets = str(tmp_path / "targets.txt")
    output = str(tmp_path / "output.json")
    cmd = _build_nuclei_cmd(scan, targets, output)
    assert isinstance(cmd, list), "Command must always be a list, never a string"


def test_build_cmd_no_shell_string(tmp_path):
    """Ensure command is never a single shell string that could be injected."""
    scan = _make_scan({"rate_limit": 100})
    cmd = _build_nuclei_cmd(scan, str(tmp_path / "t.txt"), str(tmp_path / "o.json"))
    assert not isinstance(cmd, str)
    # Each element must be a plain string
    for arg in cmd:
        assert isinstance(arg, str)


def test_build_cmd_rate_limit_is_numeric_string(tmp_path):
    scan = _make_scan({"rate_limit": 75})
    cmd = _build_nuclei_cmd(scan, str(tmp_path / "t.txt"), str(tmp_path / "o.json"))
    rl_idx = cmd.index("-rate-limit")
    rate_val = cmd[rl_idx + 1]
    assert rate_val.isdigit(), f"rate-limit value must be numeric string, got {rate_val!r}"


def test_build_cmd_rate_limit_clamped_high(tmp_path):
    """Rate limit above 1000 must be clamped to 1000."""
    scan = _make_scan({"rate_limit": 99999})
    cmd = _build_nuclei_cmd(scan, str(tmp_path / "t.txt"), str(tmp_path / "o.json"))
    rl_idx = cmd.index("-rate-limit")
    assert int(cmd[rl_idx + 1]) <= 1000


def test_build_cmd_rate_limit_clamped_low(tmp_path):
    """Rate limit of 0 must be clamped to at least 1."""
    scan = _make_scan({"rate_limit": 0})
    cmd = _build_nuclei_cmd(scan, str(tmp_path / "t.txt"), str(tmp_path / "o.json"))
    rl_idx = cmd.index("-rate-limit")
    assert int(cmd[rl_idx + 1]) >= 1


def test_build_cmd_severity_filter_included(tmp_path):
    scan = _make_scan({"severity": ["critical", "high"]})
    cmd = _build_nuclei_cmd(scan, str(tmp_path / "t.txt"), str(tmp_path / "o.json"))
    assert "-severity" in cmd
    sev_idx = cmd.index("-severity")
    assert "critical" in cmd[sev_idx + 1]
    assert "high" in cmd[sev_idx + 1]


def test_build_cmd_invalid_severity_stripped(tmp_path):
    """Severity values not in the allowed set must be dropped."""
    scan = _make_scan({"severity": ["critical", "CRITICAL; rm -rf /"]})
    cmd = _build_nuclei_cmd(scan, str(tmp_path / "t.txt"), str(tmp_path / "o.json"))
    if "-severity" in cmd:
        sev_idx = cmd.index("-severity")
        sev_val = cmd[sev_idx + 1]
        assert "rm" not in sev_val
        assert ";" not in sev_val


def test_build_cmd_tags_with_injection_stripped(tmp_path):
    """Tag values containing non-alphanumeric/hyphen chars must be dropped."""
    scan = _make_scan({"tags": ["cve", "valid-tag", "injected; id"]})
    cmd = _build_nuclei_cmd(scan, str(tmp_path / "t.txt"), str(tmp_path / "o.json"))
    if "-tags" in cmd:
        t_idx = cmd.index("-tags")
        tags_val = cmd[t_idx + 1]
        assert "injected" not in tags_val
        assert "cve" in tags_val


def test_build_cmd_extra_flags_whitelisted(tmp_path):
    """Extra flags not on the whitelist must be excluded from command."""
    scan = _make_scan({"extra_flags": ["-headless", "--evil-flag"]})
    cmd = _build_nuclei_cmd(scan, str(tmp_path / "t.txt"), str(tmp_path / "o.json"))
    assert "-headless" in cmd
    assert "--evil-flag" not in cmd


def test_build_cmd_always_json_flag(tmp_path):
    """Command must always include -json for structured output."""
    scan = _make_scan({})
    cmd = _build_nuclei_cmd(scan, str(tmp_path / "t.txt"), str(tmp_path / "o.json"))
    assert "-json" in cmd


def test_build_cmd_targets_file_included(tmp_path):
    """The targets file path must appear in the command under -list."""
    targets_file = str(tmp_path / "targets.txt")
    scan = _make_scan({})
    cmd = _build_nuclei_cmd(scan, targets_file, str(tmp_path / "o.json"))
    assert "-list" in cmd
    list_idx = cmd.index("-list")
    assert cmd[list_idx + 1] == targets_file
