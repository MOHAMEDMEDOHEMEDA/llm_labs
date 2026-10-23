import asyncio
from dataclasses import replace

import pytest

from labkit.fetch import FetchError
from week1_brochure.config import PROVIDERS, Settings
from week1_brochure.models import LinkSelection, RelevantLink
from week1_brochure.pipeline import FetchFailure, generate_brochure

SETTINGS = Settings(link_model="small", writer_model="writer")
SITE = "https://acme.test/"


def chosen(*pairs: tuple[str, str]) -> LinkSelection:
    return LinkSelection(links=[RelevantLink(type=t, url=u) for t, u in pairs])


async def test_end_to_end_skips_broken_pages_and_reports_them(fake_llm, fetcher, page, tokenizer):
    about, careers, broken = (f"{SITE}{p}" for p in ("about", "careers", "team"))
    pages = {
        SITE: page(SITE, "Acme builds rockets.", links=(about, careers, broken)),
        about: page(about, "Founded in 2019."),
        careers: page(careers, "Hiring iOS engineers."),
        broken: FetchError(broken, "HTTP 500"),
    }
    llm = fake_llm([chosen(("about", about), ("careers", careers), ("team", broken))])
    streamed: list[str] = []

    result = await generate_brochure(
        "Acme",
        SITE,
        llm=llm,
        fetch=fetcher(pages),
        tokenizer=tokenizer,
        settings=SETTINGS,
        on_delta=streamed.append,
    )

    writer_prompt = llm.complete_calls[0]["user"]
    assert "Founded in 2019." in writer_prompt and "Hiring iOS engineers." in writer_prompt
    assert [s.label for s in result.sources] == ["Landing page", "About page", "Careers page"]
    assert result.failures == [FetchFailure(broken, "HTTP 500")]
    assert [u.model for u in result.usage] == ["small", "writer"]
    assert "".join(streamed) == result.markdown


async def test_landing_page_failure_stops_the_run(fake_llm, fetcher, tokenizer):
    with pytest.raises(FetchError):
        await generate_brochure(
            "Acme",
            SITE,
            llm=fake_llm([]),
            fetch=fetcher({}),
            tokenizer=tokenizer,
            settings=SETTINGS,
        )


async def test_unexpected_errors_are_not_swallowed(fake_llm, fetcher, page, tokenizer):
    about = f"{SITE}about"
    pages = {SITE: page(SITE, "x", links=(about,)), about: RuntimeError("bug in parser")}
    with pytest.raises(RuntimeError, match="bug in parser"):
        await generate_brochure(
            "Acme",
            SITE,
            llm=fake_llm([chosen(("about", about))]),
            fetch=fetcher(pages),
            tokenizer=tokenizer,
            settings=SETTINGS,
        )


async def test_fetches_concurrently_within_the_limit(fake_llm, page, tokenizer):
    urls = [f"{SITE}p{i}" for i in range(6)]
    in_flight = peak = 0

    async def slow_fetch(url):
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        await asyncio.sleep(0.01)
        in_flight -= 1
        return page(url, "text", links=tuple(urls) if url == SITE else ())

    await generate_brochure(
        "Acme",
        SITE,
        llm=fake_llm([chosen(*[("other", u) for u in urls])]),
        fetch=slow_fetch,
        tokenizer=tokenizer,
        settings=replace(SETTINGS, fetch_concurrency=2, max_links=6),
    )
    assert peak == 2


def test_settings_default_to_gemini_with_its_own_models():
    settings = Settings.from_env({})
    assert (settings.provider, settings.link_model, settings.writer_model) == (
        "gemini",
        PROVIDERS["gemini"].link_model,
        PROVIDERS["gemini"].writer_model,
    )


def test_settings_switch_provider_and_models_from_env_or_argument():
    assert Settings.from_env({"BROCHURE_PROVIDER": "openai"}).link_model == "gpt-5-nano"
    assert Settings.from_env({}, provider="openai").writer_model == "gpt-4.1-mini"
    env = {"BROCHURE_LINK_MODEL": "a", "BROCHURE_WRITER_MODEL": "b"}
    settings = Settings.from_env(env)
    assert (settings.link_model, settings.writer_model) == ("a", "b")
    with pytest.raises(ValueError, match="Unknown provider"):
        Settings.from_env({"BROCHURE_PROVIDER": "nope"})


def test_gemini_key_accepts_the_course_variable_name_as_a_fallback():
    gemini = PROVIDERS["gemini"]
    assert gemini.api_key({"GOOGLE_API_KEY": "g"}) == "g"
    assert gemini.api_key({"GEMINI_API_KEY": "a", "GOOGLE_API_KEY": "g"}) == "a"
    assert gemini.api_key({"OPENAI_API_KEY": "o"}) is None


async def test_pages_without_text_are_reported_not_sent_to_the_writer(
    fake_llm, fetcher, page, tokenizer
):
    """Seen live: a Workable careers page fetched fine but had 0 tokens of text."""
    jobs = "https://apply.workable.com/acme/"
    pages = {SITE: page(SITE, "Acme builds rockets.", links=(jobs,)), jobs: page(jobs, "  \n ")}
    llm = fake_llm([chosen(("careers", jobs))])

    result = await generate_brochure(
        "Acme",
        SITE,
        llm=llm,
        fetch=fetcher(pages),
        tokenizer=tokenizer,
        settings=SETTINGS,
    )

    assert [s.label for s in result.sources] == ["Landing page"]
    assert result.failures == [
        FetchFailure(jobs, "no readable text (likely rendered by JavaScript)")
    ]
    assert jobs not in llm.complete_calls[0]["user"]
