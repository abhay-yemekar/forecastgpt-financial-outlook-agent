import ipaddress
import socket

import pytest

from app.utils.fetcher import UnsafeUrlError, validate_url

PUBLIC_IP = "93.184.216.34"  # example.com — treated as a fixed public IP here


@pytest.fixture(autouse=True)
def fake_dns(monkeypatch):
    """Hermetic tests: never touch the real resolver (some ISPs wildcard-
    resolve even .invalid names, which would make refusals flaky)."""

    def getaddrinfo(host, port, *args, **kwargs):
        # Literal IPs resolve to themselves (matches real getaddrinfo);
        # names resolve to a fixed public IP.
        try:
            resolved = str(ipaddress.ip_address(host))
        except ValueError:
            resolved = PUBLIC_IP
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (resolved, 0))]

    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)


def test_allowlisted_https_url_passes():
    assert validate_url("https://www.screener.in/company/TCS/") == "https://www.screener.in/company/TCS/"


def test_subdomain_of_allowlisted_host_passes():
    assert validate_url("https://archives.bseindia.com/x.pdf")


def test_unknown_public_host_passes_by_default():
    # Companies host filings on their OWN domains (wipro.com, hdfcbank.com,
    # ...) — a static allowlist can never cover them. Any https URL that
    # resolves public is allowed unless ALLOWED_DOC_HOSTS restricts it.
    assert validate_url("https://www.wipro.com/investors/deck.pdf")


def test_optional_restriction_mode(monkeypatch):
    monkeypatch.setattr("app.utils.fetcher.ALLOWED_DOC_HOSTS", {"screener.in"})
    assert validate_url("https://www.screener.in/a.pdf")
    with pytest.raises(UnsafeUrlError, match="ALLOWED_DOC_HOSTS"):
        validate_url("https://www.wipro.com/deck.pdf")


def test_literal_loopback_ip_refused():
    with pytest.raises(UnsafeUrlError):
        validate_url("http://127.0.0.1:9/ssrf-probe")


def test_private_range_literal_refused():
    with pytest.raises(UnsafeUrlError):
        validate_url("http://192.168.1.10/doc.pdf")


def test_metadata_ip_refused():
    with pytest.raises(UnsafeUrlError):
        validate_url("http://169.254.169.254/latest/meta-data/")


def test_non_http_scheme_refused():
    with pytest.raises(UnsafeUrlError, match="http/https"):
        validate_url("file:///etc/passwd")


def test_no_scheme_refused():
    with pytest.raises(UnsafeUrlError, match="http/https"):
        validate_url("not-a-url")


def test_scheme_only_no_host_refused():
    with pytest.raises(UnsafeUrlError, match="no hostname"):
        validate_url("https:///doc.pdf")


def test_unresolvable_host_refused(monkeypatch):
    def boom(host, port, *args, **kwargs):
        raise socket.gaierror("name resolution failed")

    monkeypatch.setattr(socket, "getaddrinfo", boom)
    # Allowlisted host, so the failure happens at the DNS step, not the gate.
    with pytest.raises(UnsafeUrlError, match="could not resolve"):
        validate_url("https://www.screener.in/doc.pdf")


def test_dns_rebinding_style_refused(monkeypatch):
    # An allowlisted hostname resolving to a loopback address must be refused.
    def getaddrinfo(host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0))]

    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
    with pytest.raises(UnsafeUrlError, match="non-public address"):
        validate_url("https://www.screener.in/company/TCS/")


def test_custom_allowlist_via_env(monkeypatch):
    monkeypatch.setattr("app.utils.fetcher.ALLOWED_DOC_HOSTS", {"docs.example.com"})
    assert validate_url("https://docs.example.com/a.pdf")
    with pytest.raises(UnsafeUrlError):
        validate_url("https://www.screener.in/a.pdf")
