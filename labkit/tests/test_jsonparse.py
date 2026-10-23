import pytest

from labkit.jsonparse import NoJSONObject, extract_json_object


@pytest.mark.parametrize(
    "reply",
    [
        '{"a": 1}',
        'Sure! Here are the minutes:\n```json\n{"a": 1}\n```\nLet me know if you need more.',
        'Note: {not json} but this is: {"a": 1}',
        '[1, 2] then {"a": 1}',
    ],
    ids=["bare", "fenced-with-prose", "broken-object-first", "array-first"],
)
def test_finds_the_first_complete_object(reply):
    assert extract_json_object(reply) == {"a": 1}


def test_braces_inside_strings_do_not_confuse_it():
    assert extract_json_object('{"quote": "use {x} here", "n": {"m": 2}}') == {
        "quote": "use {x} here",
        "n": {"m": 2},
    }


@pytest.mark.parametrize("reply", ["no json here", '{"a": 1', "[1, 2, 3]"])
def test_reports_when_there_is_no_object(reply):
    with pytest.raises(NoJSONObject):
        extract_json_object(reply)
