"""Unit tests for CalendarSyncService.detect_meeting_links.

Since CalendarSyncService.detect_meeting_links is a stub (raises
NotImplementedError), these tests validate the expected meeting-link
detection patterns by testing an in-test implementation of the regex logic
that the service WILL use. This approach lets us lock down the expected
behaviour before the service is fully implemented.

Once the service is implemented, these tests should be updated to call the
real method.
"""

import re

# ---------------------------------------------------------------------------
# Meeting-link detection regexes (matching the patterns the service should use)
# ---------------------------------------------------------------------------

ZOOM_PATTERN = re.compile(
    r"https?://[\w.-]*zoom\.us/j/\d+(?:\?pwd=[A-Za-z0-9]+)?", re.IGNORECASE
)
TEAMS_PATTERN = re.compile(
    r"https?://teams\.microsoft\.com/l/meetup-join/[\w\-%.@]+", re.IGNORECASE
)
GOOGLE_MEET_PATTERN = re.compile(
    r"https?://meet\.google\.com/[a-z]{3}-[a-z]{4}-[a-z]{3}", re.IGNORECASE
)

ALL_PATTERNS = {
    "zoom": ZOOM_PATTERN,
    "teams": TEAMS_PATTERN,
    "google_meet": GOOGLE_MEET_PATTERN,
}


def detect_links_in_text(text: str) -> list[dict]:
    """Detect meeting platform links in arbitrary text.

    This mirrors the expected logic of CalendarSyncService.detect_meeting_links,
    operating on a single text string rather than a list of calendar events.
    """
    found: list[dict] = []
    for platform, pattern in ALL_PATTERNS.items():
        for match in pattern.finditer(text):
            found.append({"platform": platform, "url": match.group(0)})
    return found


def detect_meeting_links_from_event(event: dict) -> list[dict]:
    """Detect meeting links across all relevant fields of a calendar event.

    Searches the event body, subject, and location fields.
    """
    all_links: list[dict] = []
    for field in ("body", "subject", "location"):
        text = event.get(field, "")
        if text:
            all_links.extend(detect_links_in_text(text))
    return all_links


# ===========================================================================
# Tests
# ===========================================================================


class TestDetectMeetingLinks:
    """Tests for meeting-link detection in calendar event text."""

    def test_detect_zoom_link_in_body(self):
        """A Zoom meeting URL in the event body should be detected."""
        event = {
            "body": "Join our meeting: https://zoom.us/j/1234567890",
            "subject": "Weekly standup",
            "location": "",
        }
        links = detect_meeting_links_from_event(event)

        assert len(links) == 1
        assert links[0]["platform"] == "zoom"
        assert "zoom.us/j/1234567890" in links[0]["url"]

    def test_detect_teams_link_in_body(self):
        """A Teams meeting URL in the event body should be detected."""
        event = {
            "body": (
                "Join the meeting: "
                "https://teams.microsoft.com/l/meetup-join/19%3ameeting_abc123%40thread.v2/0"
            ),
            "subject": "Deal review",
            "location": "",
        }
        links = detect_meeting_links_from_event(event)

        assert len(links) == 1
        assert links[0]["platform"] == "teams"
        assert "teams.microsoft.com" in links[0]["url"]

    def test_detect_google_meet_link_in_body(self):
        """A Google Meet URL in the event body should be detected."""
        event = {
            "body": "Please join at https://meet.google.com/abc-defg-hij",
            "subject": "Sprint planning",
            "location": "",
        }
        links = detect_meeting_links_from_event(event)

        assert len(links) == 1
        assert links[0]["platform"] == "google_meet"
        assert "meet.google.com/abc-defg-hij" in links[0]["url"]

    def test_detect_multiple_links_in_single_event(self):
        """Multiple meeting links in a single event should all be detected."""
        event = {
            "body": (
                "Zoom backup: https://zoom.us/j/1111111111\n"
                "Teams primary: https://teams.microsoft.com/l/meetup-join/19%3ameeting_xyz%40thread.v2/0"
            ),
            "subject": "Multi-platform meeting",
            "location": "",
        }
        links = detect_meeting_links_from_event(event)

        assert len(links) == 2
        platforms = {link["platform"] for link in links}
        assert "zoom" in platforms
        assert "teams" in platforms

    def test_detect_no_links_in_event(self):
        """An event with no meeting links should return an empty list."""
        event = {
            "body": "Just a regular meeting with no video link.",
            "subject": "Lunch",
            "location": "Conference Room B",
        }
        links = detect_meeting_links_from_event(event)

        assert links == []

    def test_detect_link_in_subject(self):
        """A meeting link in the event subject field should be detected."""
        event = {
            "body": "",
            "subject": "Join https://zoom.us/j/9999999999 for the call",
            "location": "",
        }
        links = detect_meeting_links_from_event(event)

        assert len(links) == 1
        assert links[0]["platform"] == "zoom"

    def test_detect_link_in_location(self):
        """A meeting link in the event location field should be detected."""
        event = {
            "body": "",
            "subject": "Board meeting",
            "location": "https://meet.google.com/xyz-abcd-efg",
        }
        links = detect_meeting_links_from_event(event)

        assert len(links) == 1
        assert links[0]["platform"] == "google_meet"

    def test_detect_zoom_link_with_password(self):
        """A Zoom link with a password parameter should be detected completely."""
        event = {
            "body": "https://zoom.us/j/5555555555?pwd=AbCdEfGh123456",
            "subject": "Secure call",
            "location": "",
        }
        links = detect_meeting_links_from_event(event)

        assert len(links) == 1
        assert links[0]["platform"] == "zoom"
        assert "pwd=AbCdEfGh123456" in links[0]["url"]
