import pytest

from w3lib.url import (
    add_or_replace_parameter,
    add_or_replace_parameters,
    any_to_uri,
    canonicalize_url,
    file_uri_to_path,
    is_url,
    parse_data_uri,
    parse_url,
    path_to_file_uri,
    safe_download_url,
    safe_url_string,
    url_query_cleaner,
    url_query_parameter,
)

pytest.importorskip("pytest_codspeed", reason="Benchmark tests require pytest-codspeed")

pytestmark = pytest.mark.benchmark

from .test_url import SAFE_URL_URL_CASES, KNOWN_SAFE_URL_STRING_URL_ISSUES

URLS = [url for url, output in SAFE_URL_URL_CASES if isinstance(output, (str, bytes)) and url not in KNOWN_SAFE_URL_STRING_URL_ISSUES]

def _benchmark():
    for url in URLS:
        safe_url_string(url)

def test_benchmark_safe_url(benchmark):
    benchmark(_benchmark)
