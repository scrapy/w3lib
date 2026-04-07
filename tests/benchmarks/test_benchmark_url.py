from __future__ import annotations

from contextlib import suppress
from functools import partial
from typing import TYPE_CHECKING, Any

import pytest

from tests.test_url import KNOWN_SAFE_URL_STRING_URL_ISSUES, SAFE_URL_URL_CASES
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

if TYPE_CHECKING:
    from collections.abc import Callable

    from pytest_codspeed import BenchmarkFixture  # type: ignore[import-not-found]

pytest.importorskip("pytest_codspeed", reason="Benchmark tests require pytest-codspeed")

pytestmark = pytest.mark.benchmark


URLS = [
    url
    for url, output in SAFE_URL_URL_CASES
    if isinstance(output, (str, bytes)) and url not in KNOWN_SAFE_URL_STRING_URL_ISSUES
]


def _benchmark(func: Callable[..., Any]) -> None:
    for url in URLS:
        with suppress(Exception):
            func(url)  # ty:ignore[invalid-argument-type]


@pytest.mark.parametrize(
    "func",
    [
        partial(add_or_replace_parameter, name="arg", new_value="v"),
        partial(add_or_replace_parameters, new_parameters={"arg": "v"}),
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
        partial(url_query_parameter, parameter="param"),
    ],
)
def test_benchmark_safe_url(
    benchmark: BenchmarkFixture, func: Callable[..., Any]
) -> None:
    @benchmark
    def factory():
        _benchmark(func)
