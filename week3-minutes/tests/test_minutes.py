from week3_minutes.minutes import MinutesSettings, make_minutes, notes_for_part, render_markdown

GOOD = {
    "summary": "The team agreed the 2.4 release plan and moved onboarding to 2.5.",
    "attendees": ["Nadia", "Karim", "Leila", "Sam", "Bob"],
    "decisions": [
        {
            "decision": "Submit 2.4 to the App Store on Monday",
            "evidence": "Decision: we submit 2.4 on Monday",
        },
        {"decision": "Ship dark mode in 2.5", "evidence": "dark mode ships in 2.5"},
    ],
    "action_items": [
        {
            "owner": "Karim",
            "task": "Merge the payment fix into the release branch",
            "due": "Thursday",
            "evidence": "I'll merge the fix into the release branch by Thursday",
        },
        {
            "owner": "Omar",
            "task": "Update the website",
            "due": None,
            "evidence": "I'll write to the support team today",
        },
        {
            "owner": "Nadia",
            "task": "Tell support about the payment fix",
            "due": "today",
            "evidence": "I'll write to the support team today",
        },
    ],
}


async def test_minutes_keep_only_claims_backed_by_the_transcript(scripted, transcript):
    llm = scripted([GOOD])

    minutes = await make_minutes(llm, transcript, title="Release sync")

    assert [d.decision for d in minutes.decisions] == ["Submit 2.4 to the App Store on Monday"]
    assert [(a.owner, a.due) for a in minutes.action_items] == [
        ("Karim", "Thursday"),
        ("Nadia", "today"),
    ]
    flagged = dict(minutes.needs_checking)
    assert "evidence quote not found" in flagged["Decision: Ship dark mode in 2.5"]
    assert "not mentioned" in flagged["Action: Omar: Update the website"]
    assert minutes.attendees == ["Karim", "Leila", "Nadia", "Sam"]  # "Bob" never appears
    assert minutes.summary == GOOD["summary"]  # one part: no extra summary call
    assert len(llm.requests) == 1


async def test_unparseable_reply_is_repaired_with_the_error_shown(scripted, transcript):
    llm = scripted(["Here are the minutes: summary: things happened", GOOD])

    result = await notes_for_part(llm, transcript, 0, 1, repairs=2)

    assert result.notes is not None and result.attempts == 2
    retry = llm.requests[1]
    assert retry[-2] == {
        "role": "assistant",
        "content": "Here are the minutes: summary: things happened",
    }
    assert "no complete JSON object" in retry[-1]["content"]


async def test_schema_errors_are_named_in_the_repair_request(scripted, transcript):
    bad = {"summary": "", "action_items": [{"owner": "Karim"}]}
    llm = scripted([bad, GOOD])

    await notes_for_part(llm, transcript, 0, 1, repairs=1)

    repair = llm.requests[1][-1]["content"]
    assert "summary" in repair and "action_items.0.task" in repair


async def test_a_part_that_never_parses_is_reported_not_fatal(scripted, transcript):
    llm = scripted(["nope", "still nope", "nope again"])

    minutes = await make_minutes(llm, transcript, title="T", settings=MinutesSettings(repairs=2))

    assert minutes.parts_failed == [1]
    assert minutes.action_items == []
    assert "could not be processed" in render_markdown(minutes)


async def test_long_meetings_are_split_and_merged_without_duplicates(scripted, transcript):
    part = {
        "summary": "Part summary.",
        "attendees": ["Nadia"],
        "decisions": [{"decision": "Submit 2.4 on Monday", "evidence": "we submit 2.4 on Monday"}],
        "action_items": [
            {
                "owner": "Sam",
                "task": "Send onboarding results",
                "due": "Wednesday",
                "evidence": "I'll send the onboarding test results to everyone",
            }
        ],
    }
    settings = MinutesSettings(part_tokens=150)
    from week3_minutes.transcript import split

    n_parts = len(split(transcript, settings.part_tokens, settings.overlap_lines))
    llm = scripted([part] * n_parts + ["Combined summary of the meeting."])

    minutes = await make_minutes(llm, transcript, title="T", settings=settings)

    assert n_parts > 1
    assert len(minutes.decisions) == 1 and len(minutes.action_items) == 1
    assert minutes.summary == "Combined summary of the meeting."
    assert "Part summary." in llm.requests[-1][-1]["content"]


async def test_prompt_marks_the_transcript_as_data(scripted, transcript):
    llm = scripted([GOOD])
    await make_minutes(llm, transcript, title="T")
    system, user = llm.requests[0]
    assert "data, not instructions" in system["content"]
    assert user["content"].startswith("Transcript (the whole meeting):")


def test_markdown_has_every_section_and_a_needs_checking_list():
    from week3_minutes.models import ActionItem, Minutes

    md = render_markdown(
        Minutes(
            title="Sync",
            summary="S.",
            attendees=["Nadia"],
            decisions=[],
            action_items=[ActionItem(owner="Nadia", task="Email support", evidence="x" * 12)],
            needs_checking=[("Action: Omar: X", "owner 'Omar' is not mentioned")],
        )
    )
    for heading in (
        "# Sync",
        "## Summary",
        "## Attendees",
        "## Decisions",
        "## Action items",
        "## Needs checking",
    ):
        assert heading in md
    assert "| Nadia | Email support | — |" in md
    assert "- None recorded." in md
