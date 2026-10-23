from week1_brochure.llm import LLMOutputError
from week1_brochure.models import LinkSelection, RelevantLink
from week1_brochure.selection import select_links

CANDIDATES = ["https://acme.test/about", "https://acme.test/careers", "https://acme.test/blog"]


def selection(*pairs: tuple[str, str]) -> LinkSelection:
    return LinkSelection(links=[RelevantLink(type=t, url=u) for t, u in pairs])


async def run(llm, max_links=6, candidates=CANDIDATES):
    return await select_links(
        llm,
        model="small",
        site_url="https://acme.test/",
        candidates=candidates,
        max_links=max_links,
    )


async def test_keeps_only_offered_urls_in_their_original_spelling(fake_llm):
    llm = fake_llm(
        [
            selection(
                ("about", "https://acme.test/about/"),  # trailing slash added by the model
                ("careers", "https://acme.test/jobs"),  # invented: not a candidate
                ("about", "https://acme.test/about"),  # duplicate
                ("careers", "https://acme.test/careers"),
            )
        ]
    )

    links, usage = await run(llm)

    assert [(link.type, link.url) for link in links] == [
        ("about", "https://acme.test/about"),
        ("careers", "https://acme.test/careers"),
    ]
    assert len(usage) == 1


async def test_caps_the_number_of_links(fake_llm):
    llm = fake_llm([selection(*[("other", url) for url in CANDIDATES])])
    links, _ = await run(llm, max_links=2)
    assert len(links) == 2


async def test_retries_once_after_an_unusable_answer(fake_llm):
    llm = fake_llm([LLMOutputError("cut off"), selection(("about", "https://acme.test/about"))])
    links, _ = await run(llm)
    assert llm.parse_calls == 2
    assert [link.url for link in links] == ["https://acme.test/about"]


async def test_falls_back_to_no_links_after_two_unusable_answers(fake_llm):
    llm = fake_llm([LLMOutputError("refused"), LLMOutputError("refused")])
    links, usage = await run(llm)
    assert (links, usage) == ([], [])


async def test_skips_the_model_when_there_is_nothing_to_choose(fake_llm):
    llm = fake_llm([])
    assert await run(llm, candidates=[]) == ([], [])
    assert llm.parse_calls == 0
