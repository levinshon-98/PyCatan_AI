from datetime import datetime

from pycatan.management.log_events import EventType, LogEntry


def test_road_building_log_includes_built_roads():
    entry = LogEntry(
        timestamp=datetime(2026, 5, 16, 13, 0, 0),
        event_type=EventType.USE_DEV_CARD,
        turn=6,
        player_name="Gemma",
        data={
            "card": "Road",
            "road_edges": ["10-9", "36-37"],
        },
    )

    assert entry.to_human_string() == "\u2728 Gemma used Road Building to build roads 10-9, 36-37"


def test_failed_buy_dev_card_log_does_not_report_unknown_card():
    entry = LogEntry(
        timestamp=datetime(2026, 5, 16, 13, 0, 0),
        event_type=EventType.BUY_DEV_CARD,
        turn=6,
        player_name="Claude",
        status="FAIL",
        error="Not enough resources for this action",
    )

    message = entry.to_human_string()

    assert "failed to buy" in message
    assert "Unknown" not in message
    assert "bought development card" not in message
