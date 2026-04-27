from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from w3lib.html import (
    get_base_url,
    get_meta_refresh,
    remove_comments,
    remove_tags,
    remove_tags_with_content,
    replace_entities,
    replace_escape_chars,
    replace_tags,
    unquote_markup,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from pytest_codspeed import BenchmarkFixture  # type: ignore[import-not-found]

    from tests.benchmarks import CasesMapType


BENCHMARK_CASES: CasesMapType = {
    replace_entities: [
        ((b"no entities",), {}),
        ((b"Price: &pound;100!",), {}),
        (("no entities",), {}),
        (("Price: &pound;100!",), {}),
        (("As low as &#163;100!",), {}),
        ((b"As low as &pound;100!",), {}),
        (
            (
                "redirectTo=search&searchtext=MR0221Y&aff=buyat&affsrc=d_data&cm_mmc=buyat-_-ELECTRICAL & SEASONAL-_-MR0221Y-_-9-carat gold &frac12;oz solid crucifix pendant",
            ),
            {},
        ),
        ((b"<b>Low &lt; High &amp; Medium &pound; six</b>",), {"keep": ["lt", "amp"]}),
        (("<b>Low &lt; High &amp; Medium &pound; six</b>",), {"keep": ["lt", "amp"]}),
        (("a &lt; b &illegal; c &#12345678; six",), {"remove_illegal": False}),
        (("a &lt; b &illegal; c &#12345678; six",), {"remove_illegal": True}),
        (("x&#x2264;y",), {}),
        (("x&#157;y",), {}),
        (("x&#157;y",), {"remove_illegal": False}),
        (("&#82179209091;",), {}),
        (("&#82179209091;",), {"remove_illegal": False}),
        (("x&#153;y",), {"encoding": "cp1252"}),
        (("x&#x99;y",), {"encoding": "cp1252"}),
        (("x\x99&#153;&#8482;y",), {"encoding": "cp1252"}),
        (("&lt&lt!",), {"encoding": "cp1252"}),
        (("&LT!",), {"encoding": "cp1252"}),
        (("&#X41 ",), {"encoding": "cp1252"}),
        (("&#x41!",), {"encoding": "cp1252"}),
        (("&#x41h",), {"encoding": "cp1252"}),
        (("&#65!",), {"encoding": "cp1252"}),
        (("&#65x",), {"encoding": "cp1252"}),
        (("&sup3!",), {"encoding": "cp1252"}),
        (("&Aacute!",), {"encoding": "cp1252"}),
        (("&#9731!",), {"encoding": "cp1252"}),
        (("&#153",), {"encoding": "cp1252"}),
        (("&#x99",), {"encoding": "cp1252"}),
    ],
    replace_tags: [
        ((b"no entities",), {}),
        (("no entities",), {}),
        (("This text contains <a>some tag</a>",), {}),
        ((b"This text is very im<b>port</b>ant", " "), {}),
        ((b'Click <a class="one"\r\n href="url">here</a>',), {}),
    ],
    remove_comments: [
        ((b"without comments",), {}),
        ((b"<!-- with comments -->",), {}),
        (("without comments",), {}),
        (("<!-- with comments -->",), {}),
        (("text without comments",), {}),
        (("<!--text with comments-->",), {}),
        (("Hello<!--World-->",), {}),
        (("Hello<!--My\nWorld-->",), {}),
        ((b"test <!--textcoment--> whatever",), {}),
        ((b"test <!--\ntextcoment\n--> whatever",), {}),
        ((b"test <!--",), {}),
    ],
    remove_tags: [
        ((b"no tags",), {}),
        ((b"no tags",), {"which_ones": ("p",)}),
        ((b"<p>one tag</p>",), {}),
        ((b"<p>one tag</p>",), {"which_ones": ("p",)}),
        ((b"<a>link</a>",), {"which_ones": ("b",)}),
        (("no tags",), {}),
        (("no tags",), {"which_ones": ("p",)}),
        (("<p>one tag</p>",), {}),
        (("<p>one tag</p>",), {"which_ones": ("p",)}),
        (("<a>link</a>",), {"which_ones": ("b",)}),
        (("no tags",), {"which_ones": ("p", "b")}),
        (("<p>one p tag</p>",), {}),
        (("<p>one p tag</p>",), {"which_ones": ("b",)}),
        (("<b>not will removed</b><i>i will removed</i>",), {"which_ones": ("i",)}),
        (('<p align="center" class="one">texty</p>',), {}),
        (('<p align="center" class="one">texty</p>',), {"which_ones": ("b",)}),
        (("a<br />b<br/>c",), {}),
        (("a<br />b<br/>c",), {"which_ones": ("br",)}),
        (("<p>a<br />b<br/>c</p>",), {"keep": ("br",)}),
        (("<p>a<br />b<br/>c</p>",), {"keep": ("p",)}),
        (("<p>a<br />b<br/>c</p>",), {"keep": ("p", "br", "div")}),
        (("<foo></foo><bar></bar><baz/>",), {"which_ones": ("Foo", "BAR", "baZ")}),
        (("<FOO></foO><BaR></bAr><BAZ/>",), {"which_ones": ("foo", "bar", "baz")}),
    ],
    remove_tags_with_content: [
        ((b"no tags",), {}),
        ((b"no tags",), {"which_ones": ("p",)}),
        ((b"<p>one tag</p>",), {"which_ones": ("p",)}),
        ((b"<a>link</a>",), {"which_ones": ("b",)}),
        (("no tags",), {}),
        (("no tags",), {"which_ones": ("p",)}),
        (("<p>one tag</p>",), {"which_ones": ("p",)}),
        (("<a>link</a>",), {"which_ones": ("b",)}),
        (("no tags",), {"which_ones": ("p", "b")}),
        (("<p>one p tag</p>",), {}),
        (("<p>one p tag</p>",), {"which_ones": ("p",)}),
        (("<b>not will removed</b><i>i will removed</i>",), {"which_ones": ("i",)}),
        (("<br/>a<br />",), {"which_ones": ("br",)}),
        (("<span></span><s></s>",), {"which_ones": ("s",)}),
    ],
    replace_escape_chars: [
        ((b"no ec",), {}),
        ((b"no ec",), {"replace_by": "str"}),
        ((b"no ec",), {"which_ones": ("\n", "\t")}),
        (("no ec",), {}),
        (("no ec",), {"replace_by": "str"}),
        (("no ec",), {"which_ones": ("\n", "\t")}),
        (("no ec",), {"which_ones": ("\n",)}),
        (("escape\n\n",), {}),
        (("escape\n",), {"which_ones": ("\t",)}),
        (("escape\tchars\n",), {"which_ones": ("\t",)}),
        (("escape\tchars\n",), {"replace_by": " "}),
        (("escape\tchars\n",), {"replace_by": "\xa3"}),
        (("escape\tchars\n",), {"replace_by": b"\xc2\xa3"}),
    ],
    unquote_markup: [
        (
            (
                """<node1>hi, this is sample text with entities: &amp; &copy;
<![CDATA[although this is inside a cdata! &amp; &quot;]]></node1>""",
            ),
            {},
        ),
        (
            (
                "<node2>blah&amp;blah<![CDATA[blahblahblah!&pound;]]>moreblah&lt;&gt;</node2>",
            ),
            {},
        ),
        (
            (
                "something&pound;&amp;more<node3><![CDATA[things, stuff, and such]]>what&quot;ever</node3><node4",
            ),
            {},
        ),
    ],
    get_base_url: [
        (
            (
                """<html><head><title>Dummy</title><base href='http://example.org/something' /></head><body>blahablsdfsal&amp;</body></html>""",
                "https://example.org",
            ),
            {},
        ),
        (("""<!-- <base href="http://example.com/"/> -->""",), {}),
        (
            (
                """<!-- <!--  <base href="http://example.com/"/> -- -->  <base href="http://example_2.com/"/> """,
            ),
            {},
        ),
        (
            (
                """<html><head><title>Dummy</title><base href='/absolutepath' /></head></html>""",
                "https://example.org",
            ),
            {},
        ),
        (
            (
                b"""<html><head><base href='//noscheme.com/path' /></head></html>""",
                "https://example.org",
            ),
            {},
        ),
    ],
    get_meta_refresh: [
        (
            (
                """<meta http-equiv="refresh" content="5;url=http://example.org/newpage" />""",
                "http://example.org",
            ),
            {},
        ),
        (("""<meta http-equiv="refresh" content="5" />""", "http://example.org"), {}),
        (
            (
                """<meta http-equiv="refresh" content="5; url=http://example.org/newpage" />""",
                "http://example.org",
            ),
            {},
        ),
        (
            (
                """<META HTTP-EQUIV="Refresh" CONTENT="1; URL=http://example.org/newpage">""",
                "http://example.org",
            ),
            {},
        ),
        (
            (
                """<meta http-equiv="refresh" content="3; url=&#39;http://www.example.com/other&#39;">""",
                "http://example.org",
            ),
            {},
        ),
        (
            (
                """<meta http-equiv="refresh" content="3; url=other.html">""",
                "http://example.com/page/this.html",
            ),
            {},
        ),
        (
            (
                b"""<meta http-equiv="refresh" content="3; url=http://example.com/to\xc2\xa3">""",
                "http://example.com",
            ),
            {},
        ),
        (
            (
                b"""<meta http-equiv="refresh" content="3; url=http://example.com/to\xa3">""",
                "http://example.com",
            ),
            {"encoding": "latin1"},
        ),
    ],
}


@pytest.mark.parametrize("func", BENCHMARK_CASES)
def test_benchmark_html(
    benchmark: BenchmarkFixture,
    func: Callable[..., Any],
) -> None:
    @benchmark
    def factory():
        for args, kwargs in BENCHMARK_CASES[func]:
            func(*args, **kwargs)
