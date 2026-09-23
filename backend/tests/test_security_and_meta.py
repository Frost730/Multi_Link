import pytest
from app.core.security import sanitize_filename, validate_url

def test_sanitize_filename():
    assert sanitize_filename("simple.zip") == "simple.zip"
    assert sanitize_filename("../../etc/passwd") == "passwd"
    assert sanitize_filename("CON.txt") == "_CON.txt"
    assert sanitize_filename("file<invalid>:*?.iso") == "file_invalid____.iso"
    assert sanitize_filename("") == "download.bin"

def test_validate_url_schemes():
    valid, _ = validate_url("https://example.com/file.iso")
    assert valid is True
    valid, _ = validate_url("http://example.com/file.iso")
    assert valid is True
    valid, err = validate_url("ftp://example.com/file.iso")
    assert valid is False
    assert "Only http:// and https:// are allowed" in err
    valid, err = validate_url("file:///C:/test.txt")
    assert valid is False

def test_ssrf_protection():
    # Loopback IP blocked by default
    valid, err = validate_url("http://127.0.0.1:8000/test.iso", allow_private=False)
    assert valid is False
    assert "SSRF" in err or "blocked" in err

    # Private IP blocked
    valid, err = validate_url("http://192.168.1.1/secret", allow_private=False)
    assert valid is False

    # Cloud metadata blocked
    valid, err = validate_url("http://169.254.169.254/latest/meta-data", allow_private=False)
    assert valid is False

    # When allow_private is True, local testing is permitted
    valid, _ = validate_url("http://127.0.0.1:8000/test.iso", allow_private=True)
    assert valid is True
