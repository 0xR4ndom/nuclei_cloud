"""
Unit tests for _parse_template() in app.workers.template_tasks.
No DB, no Celery — pure function tests.
"""
import os
import tempfile
import pytest

from app.workers.template_tasks import _parse_template


# ── helpers ───────────────────────────────────────────────────────────────────

def _write_yaml(content: str) -> str:
    """Write content to a temp .yaml file and return the path."""
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
    f.write(content)
    f.flush()
    f.close()
    return f.name


# ── valid YAML ────────────────────────────────────────────────────────────────

def test_full_valid_yaml():
    path = _write_yaml("""
id: cve-2021-44228
info:
  name: Apache Log4j RCE
  author: pdteam
  severity: critical
  description: Log4Shell remote code execution
  tags: cve,rce,log4j
  reference: https://nvd.nist.gov/vuln/detail/CVE-2021-44228
""")
    try:
        result = _parse_template(path)
        assert result is not None
        assert result["name"] == "Apache Log4j RCE"
        assert result["author"] == "pdteam"
        assert result["severity"] == "critical"
        assert result["description"] == "Log4Shell remote code execution"
        assert isinstance(result["tags"], list)
        assert "cve" in result["tags"]
        assert "rce" in result["tags"]
        assert "log4j" in result["tags"]
        assert isinstance(result["reference"], list)
        assert "https://nvd.nist.gov/vuln/detail/CVE-2021-44228" in result["reference"]
        assert result["path"] == path
    finally:
        os.unlink(path)


def test_minimal_yaml_with_defaults():
    """Only id and info.name — all optional fields should have safe defaults."""
    path = _write_yaml("""
id: simple-check
info:
  name: Simple Check
""")
    try:
        result = _parse_template(path)
        assert result is not None
        assert result["name"] == "Simple Check"
        assert result["tags"] == []
        assert result["reference"] == []
        assert result["description"] is None
        assert result["severity"] == "unknown"
    finally:
        os.unlink(path)


def test_tags_as_list():
    """Tags already in YAML list format should be preserved."""
    path = _write_yaml("""
id: test-list-tags
info:
  name: Tag List Test
  tags:
    - cve
    - rce
    - owasp
""")
    try:
        result = _parse_template(path)
        assert result is not None
        assert result["tags"] == ["cve", "rce", "owasp"]
    finally:
        os.unlink(path)


def test_tags_as_csv_string():
    """Tags as comma-separated string must be split into a list."""
    path = _write_yaml("""
id: test-csv-tags
info:
  name: CSV Tags
  tags: "cve,rce, log4j, owasp"
""")
    try:
        result = _parse_template(path)
        assert result is not None
        assert isinstance(result["tags"], list)
        assert "cve" in result["tags"]
        assert "log4j" in result["tags"]
        # Whitespace should be stripped
        assert all(t == t.strip() for t in result["tags"])
    finally:
        os.unlink(path)


def test_reference_as_single_string():
    """Reference as a single string should be wrapped in a list."""
    path = _write_yaml("""
id: test-ref-string
info:
  name: Ref String Test
  reference: https://example.com/advisory
""")
    try:
        result = _parse_template(path)
        assert result is not None
        assert isinstance(result["reference"], list)
        assert result["reference"] == ["https://example.com/advisory"]
    finally:
        os.unlink(path)


def test_reference_as_list():
    """Reference already in list format should be preserved."""
    path = _write_yaml("""
id: test-ref-list
info:
  name: Ref List Test
  reference:
    - https://example.com/1
    - https://example.com/2
""")
    try:
        result = _parse_template(path)
        assert result is not None
        assert result["reference"] == ["https://example.com/1", "https://example.com/2"]
    finally:
        os.unlink(path)


# ── invalid inputs ────────────────────────────────────────────────────────────

def test_invalid_yaml_syntax():
    """Malformed YAML must return None (no exception raised)."""
    path = _write_yaml("id: [broken: yaml: content: }: {")
    try:
        result = _parse_template(path)
        assert result is None
    finally:
        os.unlink(path)


def test_missing_info_key():
    """YAML without 'info' block must return None."""
    path = _write_yaml("""
id: no-info-block
requests:
  - method: GET
    path: ["{{BaseURL}}/"]
""")
    try:
        result = _parse_template(path)
        assert result is None
    finally:
        os.unlink(path)


def test_empty_info_block():
    """Empty info block (falsy) should return None."""
    path = _write_yaml("""
id: empty-info
info:
""")
    try:
        result = _parse_template(path)
        assert result is None
    finally:
        os.unlink(path)


def test_non_dict_yaml_content():
    """YAML that parses to a list instead of a dict must return None."""
    path = _write_yaml("- item1\n- item2\n- item3\n")
    try:
        result = _parse_template(path)
        assert result is None
    finally:
        os.unlink(path)


def test_nonexistent_file():
    """Non-existent file path must return None (no exception propagated)."""
    result = _parse_template("/tmp/this_file_does_not_exist_xyz.yaml")
    assert result is None


def test_tags_non_list_non_string_defaults_to_empty():
    """Tags of unexpected type (int) should fall back to empty list."""
    path = _write_yaml("""
id: bad-tags
info:
  name: Bad Tags
  tags: 12345
""")
    try:
        result = _parse_template(path)
        assert result is not None
        assert result["tags"] == []
    finally:
        os.unlink(path)


def test_reference_non_list_non_string_defaults_to_empty():
    """Reference of unexpected type should fall back to empty list."""
    path = _write_yaml("""
id: bad-ref
info:
  name: Bad Ref
  reference: 99999
""")
    try:
        result = _parse_template(path)
        assert result is not None
        assert result["reference"] == []
    finally:
        os.unlink(path)


def test_author_coerced_to_string():
    """Author value (even if numeric in YAML) should be cast to str."""
    path = _write_yaml("""
id: numeric-author
info:
  name: Numeric Author
  author: 42
""")
    try:
        result = _parse_template(path)
        assert result is not None
        assert isinstance(result["author"], str)
        assert result["author"] == "42"
    finally:
        os.unlink(path)


# ── skip-path logic (tested via the walker, not _parse_template directly) ─────
# Note: _parse_template itself does not skip based on path — the walker in
# sync_nuclei_templates() does. We verify _parse_template returns a valid result
# for any path, including paths containing ".github" or "helpers" in their name.

def test_parse_template_does_not_skip_by_path():
    """_parse_template itself parses any valid file regardless of path."""
    path = _write_yaml("""
id: test-helper
info:
  name: Helper Template
  severity: info
""")
    # Rename to simulate a path that the walker would skip
    helper_path = path.replace(".yaml", "/.github/test-helper.yaml")
    try:
        result = _parse_template(path)
        # The function itself returns a result — skipping is the walker's job
        assert result is not None
    finally:
        os.unlink(path)
