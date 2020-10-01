import os
import pytest

from unittest.mock import patch
from karmabot.commands.joke import _get_closest_category
from karmabot.commands.topchannels import Channel, calc_channel_score
from karmabot.db import db_session
from karmabot.db.karma_user import KarmaUser
from karmabot.karma import Karma, _parse_karma_change
from karmabot.settings import KARMABOT_ID, SLACK_CLIENT


# Karma
@pytest.mark.parametrize(
    "test_change, expected",
    [(("<@ABC123>", "+++"), ("ABC123", 3)), (("<@XYZ123>", "----"), ("XYZ123", -4))],
)
def test_parse_karma_change(test_change, expected):
    assert _parse_karma_change(test_change) == expected


@pytest.mark.parametrize(
    "test_changes",
    [
        ("ABC123", "XYZ123", "CHANNEL42", 2),
        ("XYZ123", "ABC123", "CHANNEL42", 5),
        ("EFG123", "ABC123", "CHANNEL42", -3),
    ],
)
def test_change_karma(mock_filled_db_session, test_changes, mock_slack_api_call):
    session = db_session.create_session()
    pre_change_karma = session.query(KarmaUser).get(test_changes[1]).karma_points

    karma = Karma(test_changes[0], test_changes[1], test_changes[2])
    karma.change_karma(test_changes[3])

    post_change = session.query(KarmaUser).get(test_changes[1]).karma_points
    assert post_change == (pre_change_karma + test_changes[3])
    session.close()


def test_change_karma_msg(mock_filled_db_session):
    karma = Karma("ABC123", "XYZ123", "CHANNEL42")
    assert karma.change_karma(4) == "clamytoe's karma increased to 424"

    karma = Karma("EFG123", "ABC123", "CHANNEL42")
    assert karma.change_karma(-3) == "pybob's karma decreased to 389"


def test_change_karma_exceptions(mock_filled_db_session):
    with pytest.raises(RuntimeError):
        karma = Karma("ABC123", "XYZ123", "CHANNEL42")
        karma.change_karma("ABC")

    with pytest.raises(ValueError):
        karma = Karma("ABC123", "ABC123", "CHANNEL42")
        karma.change_karma(2)


def test_change_karma_bot_self(mock_filled_db_session):
    karma = Karma("ABC123", KARMABOT_ID, "CHANNEL42")
    assert (
        karma.change_karma(2) == "Thanks pybob for the extra karma, my karma is 12 now"
    )

    karma = Karma("EFG123", KARMABOT_ID, "CHANNEL42")
    assert (
        karma.change_karma(3)
        == "Thanks Julian Sequeira for the extra karma, my karma is 15 now"
    )

    karma = Karma("ABC123", KARMABOT_ID, "CHANNEL42")
    assert (
        karma.change_karma(-3)
        == "Not cool pybob lowering my karma to 12, but you are probably right, I will work harder next time"
    )


def test_process_karma_changes():
    pass


def _channel_score(channel):
    channel_info = channel["channel"]
    return calc_channel_score(
        Channel(
            channel_info["id"],
            channel_info["name"],
            channel_info["purpose"]["value"],
            len(channel_info["members"]),
            float(channel_info["latest"]["ts"]),
            channel_info["latest"].get("subtype"),
        )
    )


def test_channel_score(mock_slack_api_call, frozen_now):
    most_recent = SLACK_CLIENT.api_call("channels.info", channel="CHANNEL42")
    less_recent = SLACK_CLIENT.api_call("channels.info", channel="CHANNEL43")
    assert _channel_score(most_recent) > _channel_score(less_recent)


@patch.dict(os.environ, {"SLACK_KARMA_INVITE_USER_TOKEN": "xoxp-162..."})
@patch.dict(os.environ, {"SLACK_KARMA_BOTUSER": "U5Z6KGX4L"})
def test_ignore_message_subtypes(mock_slack_api_call, frozen_now):
    latest_ignored = SLACK_CLIENT.api_call("channels.info", channel="SOMEJOINS")
    all_ignored = SLACK_CLIENT.api_call("channels.info", channel="ONLYJOINS")
    assert _channel_score(latest_ignored) > 0
    assert _channel_score(all_ignored) == 0


@pytest.mark.parametrize(
    "user_category, expected",
    [
        ("all", "all"),
        ("neutral", "neutral"),
        ("chuck", "chuck"),
        ("", "all"),
        ("al", "all"),
        ("neutr", "neutral"),
        ("chuk", "chuck"),
        ("help", "all"),
    ],
)
def test_get_closest_category(user_category, expected):
    assert _get_closest_category(user_category) == expected
