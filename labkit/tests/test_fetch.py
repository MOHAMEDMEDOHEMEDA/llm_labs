import httpx
import pytest

from labkit.fetch import FetchError, RobotsPolicy, fetch_page, parse_html

HTML = """<html><head><title> Acme </title><style>.x { color: red }</style></head>
<body>
  <script>alert('tracking')</script>
  <h1>Welcome</h1><p>We build rockets.</p>
  <a href="/about">About</a>
  <a href="/about#team">Team</a>
  <a href="mailto:hi@acme.test">Mail</a>
  <a href="javascript:void(0)">Menu</a>
  <a href="https://other.test/x">Other</a>
  <a href="careers">Careers</a>
</body></html>"""


def html(body: str, status: int = 200) -> httpx.Response:
    return httpx.Response(status, text=body, headers={"content-type": "text/html; charset=utf-8"})


def client_for(routes: dict[str, httpx.Response | Exception]) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        result = routes.get(str(request.url), httpx.Response(404))
        if isinstance(result, Exception):
            raise result
        return result

    return httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True)


def test_parse_html_keeps_visible_text_and_resolves_links():
    page = parse_html(HTML, "https://acme.test/home/")

    assert page.title == "Acme"
    assert "We build rockets." in page.text
    assert "alert" not in page.text and "color" not in page.text
    # relative links resolved, fragments removed, duplicates and non-http schemes dropped
    assert page.links == (
        "https://acme.test/about",
        "https://other.test/x",
        "https://acme.test/home/careers",
    )


async def test_fetch_page_returns_parsed_page_with_final_url():
    routes = {
        "https://acme.test/": httpx.Response(301, headers={"location": "https://acme.test/home/"}),
        "https://acme.test/home/": html(HTML),
    }
    async with client_for(routes) as client:
        page = await fetch_page(client, "https://acme.test/")

    assert page.url == "https://acme.test/home/"
    assert "https://acme.test/home/careers" in page.links


@pytest.mark.parametrize(
    ("response", "reason"),
    [
        (httpx.Response(404), "HTTP 404"),
        (
            httpx.Response(200, content=b"%PDF", headers={"content-type": "application/pdf"}),
            "not an HTML page (application/pdf)",
        ),
    ],
)
async def test_fetch_page_rejects_unusable_responses(response, reason):
    async with client_for({"https://acme.test/x": response}) as client:
        with pytest.raises(FetchError) as caught:
            await fetch_page(client, "https://acme.test/x")
    assert caught.value.reason == reason


async def test_fetch_page_reports_timeouts_as_fetch_errors():
    request = httpx.Request("GET", "https://acme.test/slow")
    routes = {"https://acme.test/slow": httpx.ReadTimeout("slow", request=request)}
    async with client_for(routes) as client:
        with pytest.raises(FetchError, match="timed out"):
            await fetch_page(client, "https://acme.test/slow")


async def test_fetch_page_caps_response_size():
    big = "<html><body><p>" + "word " * 10_000 + "</p></body></html>"
    async with client_for({"https://acme.test/big": html(big)}) as client:
        page = await fetch_page(client, "https://acme.test/big", max_bytes=1_000)
    assert 0 < len(page.text) < 1_000


async def test_robots_disallow_is_respected():
    routes = {
        "https://acme.test/robots.txt": httpx.Response(
            200, text="User-agent: *\nDisallow: /private\n"
        ),
        "https://acme.test/public": html("<p>ok</p>"),
        "https://acme.test/private": html("<p>secret</p>"),
    }
    robots = RobotsPolicy()
    async with client_for(routes) as client:
        assert (await fetch_page(client, "https://acme.test/public", robots=robots)).text == "ok"
        with pytest.raises(FetchError) as caught:
            await fetch_page(client, "https://acme.test/private", robots=robots)
    assert caught.value.reason == "disallowed by robots.txt"


@pytest.mark.parametrize(
    ("robots_response", "reason"),
    [
        (httpx.Response(404), None),  # no robots.txt: no restrictions
        (httpx.Response(503), "robots.txt returned HTTP 503, so not fetching"),
        (httpx.ConnectError("refused"), "robots.txt unreachable (ConnectError), so not fetching"),
    ],
    ids=["4xx-allows", "5xx-blocks", "unreachable-blocks"],
)
async def test_robots_follows_rfc_9309_when_robots_txt_is_unavailable(robots_response, reason):
    routes = {"https://acme.test/robots.txt": robots_response}
    async with client_for(routes) as client:
        assert await RobotsPolicy().blocked_reason(client, "https://acme.test/about") == reason
