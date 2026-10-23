import pytest

from week3_minutes.grounding import Grounding


@pytest.fixture
def ground(transcript):
    return Grounding(transcript)


@pytest.mark.parametrize(
    "quote",
    [
        "I'll merge the fix into the release branch by Thursday.",
        "i'll MERGE the fix   into the release branch",  # case, spacing
        "Karim: Not yet. I'll merge the fix into the release branch",  # with the speaker label
        "“we submit 2.4 on Monday”",  # curly quotes
    ],
)
def test_real_quotes_are_found(ground, quote):
    assert ground.quote_problem(quote) is None


@pytest.mark.parametrize(
    ("quote", "problem"),
    [
        ("Karim will merge the payment fix on Thursday", "not found"),  # paraphrase
        ("we ship dark mode in 2.5", "not found"),  # invented
        ("Monday", "too short"),
    ],
)
def test_paraphrased_or_invented_quotes_are_flagged(ground, quote, problem):
    assert problem in ground.quote_problem(quote)


def test_owners_must_be_named_in_the_transcript(ground):
    assert ground.owner_problem("Leila") is None
    assert ground.owner_problem("nadia") is None
    assert "not mentioned" in ground.owner_problem("Omar")
    assert "not mentioned" in ground.owner_problem("Karim Mansour")  # surname invented
    assert ground.owner_problem("team") == "no single owner"


def test_names_match_whole_words_only(ground):
    assert ground.name_appears("Sam")
    assert not ground.name_appears("Sa")  # part of "Sam" and "same"
