from itertools import pairwise

from week3_minutes.transcript import estimate_tokens, split


def test_short_transcript_stays_in_one_part(transcript):
    assert split(transcript, max_tokens=10_000) == [transcript]


def test_parts_respect_the_budget_and_never_cut_a_line(transcript):
    parts = split(transcript, max_tokens=120, overlap_lines=0)

    assert len(parts) > 2
    assert all(estimate_tokens(p) <= 120 for p in parts)
    original = set(transcript.splitlines())
    assert all(line in original for p in parts for line in p.splitlines())
    assert "\n".join(parts) == transcript  # nothing lost or duplicated without overlap


def test_overlap_repeats_the_end_of_the_previous_part(transcript):
    parts = split(transcript, max_tokens=150, overlap_lines=1)
    for previous, current in pairwise(parts):
        assert current.splitlines()[0] == previous.splitlines()[-1]


def test_a_single_huge_line_is_cut_rather_than_dropped():
    line = "x" * 2_000
    parts = split(line, max_tokens=100, overlap_lines=0)
    assert "".join(parts) == line
    assert all(estimate_tokens(p) <= 100 for p in parts)
