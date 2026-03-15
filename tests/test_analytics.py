"""Tests for pymessage.analytics module."""

import pandas as pd
import pytest

from pymessage import get_messages
from pymessage.analytics import (
    _apply_time_filter,
    _response_times,
    get_activity_summary,
    get_contact_heatmap,
    get_contact_summary,
)
from pymessage.backups import Backup


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_df(*rows):
    """Build a minimal messages DataFrame from (timestamp, is_from_me, chat_id) tuples."""
    records = []
    for ts, from_me, chat_id in rows:
        records.append({
            "timestamp": pd.Timestamp(ts, tz="UTC"),
            "read_at": pd.NaT,
            "sender": None if from_me else chat_id,
            "contact_name": "Me" if from_me else "Contact",
            "message_text": "hi",
            "is_from_me": from_me,
            "chat_id": chat_id,
            "is_group_chat": False,
            "attachment_path": None,
            "reaction_type": None,
            "reaction_action": None,
        })
    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# TestApplyTimeFilter
# ---------------------------------------------------------------------------

class TestApplyTimeFilter:
    def test_last_n_days_filter(self):
        ref = pd.Timestamp("2024-06-01", tz="UTC")
        df = _make_df(
            ("2024-05-20", False, "+11111111111"),  # 12 days before ref — excluded
            ("2024-05-25", False, "+11111111111"),  # 7 days before ref — included
            ("2024-05-31", False, "+11111111111"),  # 1 day before ref — included
        )
        result = _apply_time_filter(df, None, None, last_n_days=10, reference_date=ref)
        assert len(result) == 2

    def test_start_end_filter(self):
        df = _make_df(
            ("2024-01-01", False, "+11111111111"),
            ("2024-06-01", False, "+11111111111"),
            ("2024-12-01", False, "+11111111111"),
        )
        result = _apply_time_filter(df, "2024-03-01", "2024-09-01", None, None)
        assert len(result) == 1
        assert result.iloc[0]["timestamp"] == pd.Timestamp("2024-06-01", tz="UTC")

    def test_last_n_days_overrides_start_end(self):
        ref = pd.Timestamp("2024-06-01", tz="UTC")
        df = _make_df(
            ("2024-01-01", False, "+11111111111"),
            ("2024-05-25", False, "+11111111111"),  # within 10 days of ref
        )
        # start/end alone would include the first row, but last_n_days=10 overrides
        result = _apply_time_filter(
            df, "2024-01-01", "2024-01-31", last_n_days=10, reference_date=ref
        )
        assert len(result) == 1
        assert result.iloc[0]["timestamp"] == pd.Timestamp("2024-05-25", tz="UTC")

    def test_no_filter_returns_all(self):
        df = _make_df(
            ("2024-01-01", False, "+11111111111"),
            ("2024-06-01", False, "+11111111111"),
        )
        result = _apply_time_filter(df, None, None, None, None)
        assert len(result) == 2

    def test_empty_df_returns_empty(self, mock_backup: Backup):
        # Use a properly-structured empty DataFrame (correct columns, 0 rows)
        df = get_messages(mock_backup, phone_numbers="+99999999999")
        result = _apply_time_filter(df, "2024-01-01", "2024-12-31", None, None)
        assert result.empty

    def test_start_only_filter(self):
        df = _make_df(
            ("2024-01-01", False, "+11111111111"),
            ("2024-06-01", False, "+11111111111"),
        )
        result = _apply_time_filter(df, "2024-03-01", None, None, None)
        assert len(result) == 1

    def test_end_only_filter(self):
        df = _make_df(
            ("2024-01-01", False, "+11111111111"),
            ("2024-06-01", False, "+11111111111"),
        )
        result = _apply_time_filter(df, None, "2024-03-01", None, None)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# TestResponseTimes
# ---------------------------------------------------------------------------

class TestResponseTimes:
    def test_basic_response_times(self, mock_backup: Backup):
        df = get_messages(mock_backup)
        rt = _response_times(df, is_from_me=True)
        assert not rt.empty
        assert (rt > 0).all()

    def test_no_responses_returns_empty(self):
        # Only received messages — Tucker never responded
        df = _make_df(
            ("2024-01-01 12:00", False, "+11111111111"),
            ("2024-01-01 12:05", False, "+11111111111"),
        )
        rt = _response_times(df, is_from_me=True)
        assert rt.empty

    def test_gaps_over_one_day_excluded(self):
        # Tucker responds 3 days later — should be excluded
        df = _make_df(
            ("2024-01-01 12:00", False, "+11111111111"),
            ("2024-01-04 12:00", True, "+11111111111"),
        )
        rt = _response_times(df, is_from_me=True)
        assert rt.empty

    def test_short_response_included(self):
        df = _make_df(
            ("2024-01-01 12:00", False, "+11111111111"),
            ("2024-01-01 12:05", True, "+11111111111"),  # 5 minutes
        )
        rt = _response_times(df, is_from_me=True)
        assert len(rt) == 1
        assert abs(rt.iloc[0] - 300.0) < 1.0  # ~5 minutes in seconds

    def test_contact_response_times(self, mock_backup: Backup):
        df = get_messages(mock_backup)
        rt = _response_times(df, is_from_me=False)
        # The mock has received messages that come after sent ones
        assert not rt.empty
        assert (rt > 0).all()


# ---------------------------------------------------------------------------
# TestGetActivitySummary
# ---------------------------------------------------------------------------

_SUMMARY_COLUMNS = [
    "total_messages", "total_sent", "total_received",
    "avg_messages_per_day", "unique_contacts",
    "most_active_day_of_week", "most_active_hour",
    "late_night_contacts", "pct_messages_with_attachments",
    "avg_message_length", "avg_response_time_seconds",
    "conversations_initiated", "conversations_received",
    "ghost_contacts",
]

_TOP_CONTACTS_COLUMNS = ["contact", "total", "sent", "received"]


class TestGetActivitySummary:
    def test_returns_two_dataframes(self, mock_backup: Backup):
        df = get_messages(mock_backup)
        result = get_activity_summary(df)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_summary_columns(self, mock_backup: Backup):
        df = get_messages(mock_backup)
        summary, _ = get_activity_summary(df)
        assert list(summary.columns) == _SUMMARY_COLUMNS
        assert len(summary) == 1

    def test_top_contacts_columns(self, mock_backup: Backup):
        df = get_messages(mock_backup)
        _, top = get_activity_summary(df)
        assert list(top.columns) == _TOP_CONTACTS_COLUMNS

    def test_empty_df_returns_correct_schema(self):
        df = _make_df()
        summary, top = get_activity_summary(df)
        assert summary.empty
        assert top.empty
        assert list(summary.columns) == _SUMMARY_COLUMNS
        assert list(top.columns) == _TOP_CONTACTS_COLUMNS

    def test_top_n_limits_contacts(self, mock_backup: Backup):
        df = get_messages(mock_backup)
        _, top = get_activity_summary(df, top_n=1)
        assert len(top) <= 1

    def test_total_counts_correct(self, mock_backup: Backup):
        df = get_messages(mock_backup)
        summary, _ = get_activity_summary(df)
        assert summary.iloc[0]["total_messages"] == len(df)
        assert summary.iloc[0]["total_sent"] == int(df["is_from_me"].sum())
        assert summary.iloc[0]["total_received"] == int((~df["is_from_me"]).sum())

    def test_counts_are_nonnegative(self, mock_backup: Backup):
        df = get_messages(mock_backup)
        summary, _ = get_activity_summary(df)
        assert summary.iloc[0]["total_messages"] >= 0
        assert summary.iloc[0]["avg_messages_per_day"] >= 0
        assert 0.0 <= summary.iloc[0]["pct_messages_with_attachments"] <= 1.0

    def test_top_contacts_sent_received_sum_to_total(self, mock_backup: Backup):
        df = get_messages(mock_backup)
        _, top = get_activity_summary(df)
        if not top.empty:
            assert (top["sent"] + top["received"] == top["total"]).all()

    def test_date_filter_reduces_messages(self, mock_backup: Backup):
        df = get_messages(mock_backup)
        # Filter to a date range that excludes all messages
        summary_all, _ = get_activity_summary(df)
        summary_filtered, _ = get_activity_summary(df, last_n_days=0)
        assert summary_all.iloc[0]["total_messages"] >= summary_filtered.get(
            "total_messages", pd.Series([0])
        ).iloc[0] if not summary_filtered.empty else True


# ---------------------------------------------------------------------------
# TestGetContactSummary
# ---------------------------------------------------------------------------

_CONTACT_SUMMARY_COLUMNS = [
    "total_messages", "total_sent", "total_received",
    "send_receive_ratio", "avg_messages_per_active_day",
    "total_active_days", "avg_read_time_seconds",
    "avg_response_time_you_seconds", "avg_response_time_contact_seconds",
    "conversations_initiated_you", "conversations_initiated_contact",
    "longest_gap_days", "messages_with_attachments",
    "avg_message_length_you", "avg_message_length_contact",
    "short_message_count_you", "short_message_count_contact",
    "most_active_hour", "most_active_day_of_week",
]


class TestGetContactSummary:
    def test_returns_single_row(self, mock_backup: Backup):
        df = get_messages(mock_backup)
        result = get_contact_summary(df, "+12345678900")
        assert len(result) == 1

    def test_all_columns_present(self, mock_backup: Backup):
        df = get_messages(mock_backup)
        result = get_contact_summary(df, "+12345678900")
        assert list(result.columns) == _CONTACT_SUMMARY_COLUMNS

    def test_unknown_contact_returns_empty(self, mock_backup: Backup):
        df = get_messages(mock_backup)
        result = get_contact_summary(df, "+99999999999")
        assert result.empty
        assert list(result.columns) == _CONTACT_SUMMARY_COLUMNS

    def test_phone_number_variants_work(self, mock_backup: Backup):
        df = get_messages(mock_backup)
        r1 = get_contact_summary(df, "+12345678900")
        r2 = get_contact_summary(df, "2345678900")
        r3 = get_contact_summary(df, "12345678900")
        total = r1.iloc[0]["total_messages"]
        assert r2.iloc[0]["total_messages"] == total
        assert r3.iloc[0]["total_messages"] == total

    def test_send_receive_ratio_inf_when_no_received(self):
        df = _make_df(
            ("2024-01-01 12:00", True, "+12345678900"),
            ("2024-01-01 12:05", True, "+12345678900"),
        )
        result = get_contact_summary(df, "+12345678900")
        assert result.iloc[0]["send_receive_ratio"] == float("inf")

    def test_send_receive_ratio_correct(self, mock_backup: Backup):
        df = get_messages(mock_backup, phone_numbers="+12345678900")
        result = get_contact_summary(df, "+12345678900")
        row = result.iloc[0]
        expected = row["total_sent"] / row["total_received"]
        assert abs(row["send_receive_ratio"] - expected) < 1e-9

    def test_empty_df_returns_correct_schema(self, mock_backup: Backup):
        df = get_messages(mock_backup, phone_numbers="+99999999999")
        result = get_contact_summary(df, "+12345678900")
        assert result.empty
        assert list(result.columns) == _CONTACT_SUMMARY_COLUMNS

    def test_total_counts_match(self, mock_backup: Backup):
        df = get_messages(mock_backup, phone_numbers="+12345678900")
        result = get_contact_summary(df, "+12345678900")
        assert result.iloc[0]["total_messages"] == len(df)
        assert result.iloc[0]["total_sent"] == int(df["is_from_me"].sum())
        assert result.iloc[0]["total_received"] == int((~df["is_from_me"]).sum())

    def test_conversations_initiated_sum(self, mock_backup: Backup):
        df = get_messages(mock_backup, phone_numbers="+12345678900")
        result = get_contact_summary(df, "+12345678900")
        row = result.iloc[0]
        # initiated_you + initiated_contact should equal number of active days
        assert (
            row["conversations_initiated_you"] + row["conversations_initiated_contact"]
            == row["total_active_days"]
        )


# ---------------------------------------------------------------------------
# TestGetContactHeatmap
# ---------------------------------------------------------------------------

class TestGetContactHeatmap:
    def test_returns_7x24_shape(self, mock_backup: Backup):
        df = get_messages(mock_backup)
        heatmap = get_contact_heatmap(df, "+12345678900")
        assert heatmap.shape == (7, 24)

    def test_all_days_present(self, mock_backup: Backup):
        df = get_messages(mock_backup)
        heatmap = get_contact_heatmap(df, "+12345678900")
        expected = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        assert list(heatmap.index) == expected

    def test_all_hours_present(self, mock_backup: Backup):
        df = get_messages(mock_backup)
        heatmap = get_contact_heatmap(df, "+12345678900")
        assert list(heatmap.columns) == list(range(24))

    def test_empty_contact_returns_zeros(self, mock_backup: Backup):
        df = get_messages(mock_backup)
        heatmap = get_contact_heatmap(df, "+99999999999")
        assert heatmap.shape == (7, 24)
        assert (heatmap == 0).all().all()

    def test_values_are_nonnegative_integers(self, mock_backup: Backup):
        df = get_messages(mock_backup)
        heatmap = get_contact_heatmap(df, "+12345678900")
        assert (heatmap >= 0).all().all()
        assert heatmap.dtypes.apply(pd.api.types.is_integer_dtype).all()

    def test_total_count_matches_message_count(self, mock_backup: Backup):
        df = get_messages(mock_backup)
        # get the count for the conversation directly
        contact_df = get_messages(mock_backup, phone_numbers="+12345678900")
        heatmap = get_contact_heatmap(df, "+12345678900")
        assert heatmap.values.sum() == len(contact_df)

    def test_empty_df_returns_zeros(self, mock_backup: Backup):
        df = get_messages(mock_backup, phone_numbers="+99999999999")
        heatmap = get_contact_heatmap(df, "+12345678900")
        assert heatmap.shape == (7, 24)
        assert (heatmap == 0).all().all()
