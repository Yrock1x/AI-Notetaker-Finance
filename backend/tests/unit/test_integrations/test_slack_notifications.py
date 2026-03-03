"""Unit tests for Slack notification Block Kit building.

Since SlackNotifier.send_meeting_complete raises NotImplementedError, these
tests validate the expected Block Kit structure by testing a reference
implementation of the block builder. This locks down the contract before the
service is fully implemented.

Once SlackNotifier is implemented, these tests should be updated to call the
real methods.
"""

import pytest


# ---------------------------------------------------------------------------
# Reference block builder (mirrors expected SlackNotifier behaviour)
# ---------------------------------------------------------------------------


def build_meeting_complete_blocks(meeting: dict) -> list[dict]:
    """Build Block Kit blocks for a meeting-complete notification.

    This is the expected structure that SlackNotifier.send_meeting_complete
    will produce.

    Parameters
    ----------
    meeting:
        A dict with at least ``title``, ``deal_name``, ``duration_minutes``,
        and ``meeting_url`` keys.

    Returns
    -------
    list[dict]
        A list of Slack Block Kit block dicts.
    """
    title = meeting.get("title", "Untitled Meeting")
    deal_name = meeting.get("deal_name", "")
    duration = meeting.get("duration_minutes", 0)
    meeting_url = meeting.get("meeting_url", "")

    blocks: list[dict] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"Meeting Complete: {title}",
            },
        },
        {"type": "divider"},
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Deal:* {deal_name}"},
                {"type": "mrkdwn", "text": f"*Duration:* {duration} min"},
            ],
        },
    ]

    if meeting_url:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"<{meeting_url}|View Meeting Details>",
                },
            }
        )

    return blocks


# ===========================================================================
# Tests
# ===========================================================================


class TestBuildMeetingCompleteBlocks:
    """Tests for Block Kit structure of meeting-complete notifications."""

    def test_build_meeting_complete_blocks_structure(self):
        """The block list should contain header, divider, and section blocks."""
        meeting = {
            "title": "Q4 Earnings Call",
            "deal_name": "Acme Corp Acquisition",
            "duration_minutes": 45,
            "meeting_url": "https://app.dealwise.ai/meetings/123",
        }
        blocks = build_meeting_complete_blocks(meeting)

        assert isinstance(blocks, list)
        assert len(blocks) >= 3

        # First block should be a header
        assert blocks[0]["type"] == "header"
        # Second should be divider
        assert blocks[1]["type"] == "divider"
        # Third should be a section with fields
        assert blocks[2]["type"] == "section"
        assert "fields" in blocks[2]

    def test_build_meeting_complete_blocks_contains_title(self):
        """The header block should contain the meeting title."""
        meeting = {
            "title": "Management Presentation",
            "deal_name": "Project Alpha",
            "duration_minutes": 60,
            "meeting_url": "",
        }
        blocks = build_meeting_complete_blocks(meeting)

        header_text = blocks[0]["text"]["text"]
        assert "Management Presentation" in header_text

    def test_build_meeting_complete_blocks_has_divider(self):
        """The block list should include at least one divider block."""
        meeting = {
            "title": "Due Diligence Review",
            "deal_name": "Project Beta",
            "duration_minutes": 30,
            "meeting_url": "",
        }
        blocks = build_meeting_complete_blocks(meeting)

        dividers = [b for b in blocks if b["type"] == "divider"]
        assert len(dividers) >= 1

    def test_build_meeting_complete_blocks_includes_deal_name(self):
        """The section fields should include the deal name."""
        meeting = {
            "title": "Kick-off",
            "deal_name": "Project Gamma",
            "duration_minutes": 15,
            "meeting_url": "",
        }
        blocks = build_meeting_complete_blocks(meeting)

        section = blocks[2]
        field_texts = [f["text"] for f in section["fields"]]
        assert any("Project Gamma" in t for t in field_texts)

    def test_build_meeting_complete_blocks_includes_duration(self):
        """The section fields should include the meeting duration."""
        meeting = {
            "title": "Review",
            "deal_name": "Deal X",
            "duration_minutes": 90,
            "meeting_url": "",
        }
        blocks = build_meeting_complete_blocks(meeting)

        section = blocks[2]
        field_texts = [f["text"] for f in section["fields"]]
        assert any("90" in t for t in field_texts)

    def test_build_meeting_complete_blocks_with_meeting_url(self):
        """When a meeting_url is provided, a link section should be appended."""
        meeting = {
            "title": "Final Review",
            "deal_name": "Deal Y",
            "duration_minutes": 30,
            "meeting_url": "https://app.dealwise.ai/meetings/456",
        }
        blocks = build_meeting_complete_blocks(meeting)

        # Should have 4 blocks: header, divider, section, link section
        assert len(blocks) == 4
        link_block = blocks[3]
        assert link_block["type"] == "section"
        assert "View Meeting Details" in link_block["text"]["text"]

    def test_build_meeting_complete_blocks_without_meeting_url(self):
        """When meeting_url is empty, the link section should be omitted."""
        meeting = {
            "title": "Review",
            "deal_name": "Deal Z",
            "duration_minutes": 20,
            "meeting_url": "",
        }
        blocks = build_meeting_complete_blocks(meeting)

        # Should only have 3 blocks (no link section)
        assert len(blocks) == 3
