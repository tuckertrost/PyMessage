"""Analytics functions for iMessage data.

This module provides summary statistics and heatmap generation for message
DataFrames produced by get_messages().
"""

from __future__ import annotations

import pandas as pd

from pymessage.utils import generate_phone_variants


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _apply_time_filter(
    df: pd.DataFrame,
    start: str | pd.Timestamp | None,
    end: str | pd.Timestamp | None,
    last_n_days: int | None,
    reference_date: pd.Timestamp | None,
) -> pd.DataFrame:
    """Filter a messages DataFrame to a time window.

    Args:
        df: DataFrame from get_messages().
        start: Start date as ISO string or Timestamp. Ignored when last_n_days set.
        end: End date as ISO string or Timestamp. Ignored when last_n_days set.
        last_n_days: If provided, takes precedence over start/end and returns
            the last N days relative to reference_date.
        reference_date: Reference point for last_n_days. Defaults to now (UTC).

    Returns:
        Filtered DataFrame.
    """
    if reference_date is None:
        reference_date = pd.Timestamp.now(tz="UTC")

    if last_n_days is not None:
        cutoff = reference_date - pd.Timedelta(days=last_n_days)
        return df[df["timestamp"] >= cutoff]

    if start is not None:
        df = df[df["timestamp"] >= pd.to_datetime(start, utc=True)]
    if end is not None:
        df = df[df["timestamp"] <= pd.to_datetime(end, utc=True)]
    return df


def _response_times(df: pd.DataFrame, is_from_me: bool) -> pd.Series:
    """Compute response times for messages sent by one party within each chat.

    Finds pairs where one side sends a message and the other side replies,
    and returns the elapsed seconds for each such pair.

    Args:
        df: Messages DataFrame sorted by timestamp.
        is_from_me: If True, compute Tucker's response times (received → sent).
            If False, compute the contact's response times (sent → received).

    Returns:
        Series of response time values in seconds.
    """
    times = []
    for _, chat_df in df.groupby("chat_id"):
        chat_df = chat_df.sort_values("timestamp")
        prev_ts = None
        prev_from_me = None
        for _, row in chat_df.iterrows():
            cur_from_me = row["is_from_me"]
            cur_ts = row["timestamp"]
            if (
                prev_ts is not None
                and prev_from_me is not None
                and prev_from_me != cur_from_me
                and cur_from_me == is_from_me
            ):
                delta = (cur_ts - prev_ts).total_seconds()
                if 0 < delta < 86400:  # ignore gaps > 1 day
                    times.append(delta)
            prev_ts = cur_ts
            prev_from_me = cur_from_me
    return pd.Series(times, dtype=float)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_activity_summary(
    df: pd.DataFrame,
    start: str | pd.Timestamp | None = None,
    end: str | pd.Timestamp | None = None,
    last_n_days: int | None = None,
    reference_date: pd.Timestamp | None = None,
    top_n: int = 10,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compute overall messaging activity statistics.

    Args:
        df: DataFrame produced by get_messages().
        start: Optional start date for filtering (ISO string or Timestamp).
        end: Optional end date for filtering (ISO string or Timestamp).
        last_n_days: If provided, overrides start/end and filters to the last
            N days relative to reference_date.
        reference_date: Reference point for last_n_days. Defaults to now (UTC).
        top_n: Number of top contacts to include in top_contacts_df.

    Returns:
        Tuple of (summary_df, top_contacts_df).

        summary_df is a single-row DataFrame with columns:
        - total_messages (int)
        - total_sent (int)
        - total_received (int)
        - avg_messages_per_day (float)
        - unique_contacts (int)
        - most_active_day_of_week (str, e.g. "Saturday")
        - most_active_hour (int, 0–23)
        - late_night_contacts (list[str])
        - pct_messages_with_attachments (float, 0–1)
        - avg_message_length (float)
        - avg_response_time_seconds (float)
        - conversations_initiated (int)
        - conversations_received (int)
        - ghost_contacts (list[str])

        top_contacts_df has columns: contact, total, sent, received.
        Sorted descending by total, limited to top_n rows.

    Examples:
        >>> from pymessage import EXAMPLE_BACKUP, get_messages, get_activity_summary
        >>> df = get_messages(EXAMPLE_BACKUP)
        >>> summary, top = get_activity_summary(df)
        >>> print(summary["total_messages"].iloc[0])
    """
    df = _apply_time_filter(df, start, end, last_n_days, reference_date)

    if df.empty:
        empty_summary = pd.DataFrame(
            columns=[
                "total_messages", "total_sent", "total_received",
                "avg_messages_per_day", "unique_contacts",
                "most_active_day_of_week", "most_active_hour",
                "late_night_contacts", "pct_messages_with_attachments",
                "avg_message_length", "avg_response_time_seconds",
                "conversations_initiated", "conversations_received",
                "ghost_contacts",
            ]
        )
        empty_top = pd.DataFrame(columns=["contact", "total", "sent", "received"])
        return empty_summary, empty_top

    sent = df[df["is_from_me"]]
    received = df[~df["is_from_me"]]

    # Basic counts
    total = len(df)
    total_sent = len(sent)
    total_received = len(received)

    # Days span
    day_span = max(
        1,
        (df["timestamp"].max() - df["timestamp"].min()).days + 1,
    )
    avg_per_day = total / day_span

    # Unique contacts (exclude "Me")
    unique_contacts = df.loc[~df["is_from_me"], "contact_name"].nunique()

    # Most active day / hour
    most_active_dow = df["timestamp"].dt.day_name().mode()[0]
    most_active_hour = int(df["timestamp"].dt.hour.mode()[0])

    # Late-night contacts: >20% of their msgs between 10pm–4am UTC
    df_recv = df[~df["is_from_me"]].copy()
    df_recv["hour"] = df_recv["timestamp"].dt.hour
    df_recv["is_late"] = df_recv["hour"].apply(lambda h: h >= 22 or h < 4)
    if not df_recv.empty:
        contact_late = df_recv.groupby("contact_name")["is_late"].mean()
        late_night_contacts = contact_late[contact_late > 0.2].index.tolist()
    else:
        late_night_contacts = []

    # Attachment %
    pct_with_attach = (
        df["attachment_path"].notna().sum() / total if total > 0 else 0.0
    )

    # Avg message length (non-null, non-empty)
    texts = df["message_text"].dropna()
    texts = texts[texts.str.strip() != ""]
    avg_len = float(texts.str.len().mean()) if not texts.empty else 0.0

    # Avg response time (Tucker's responses to received messages)
    rt = _response_times(df, is_from_me=True)
    avg_rt = float(rt.mean()) if not rt.empty else 0.0

    # Conversations initiated vs received: per (chat_id, date), who sent first
    df2 = df.copy()
    df2["date"] = df2["timestamp"].dt.date
    conv_init = 0
    conv_recv = 0
    for (_, _), grp in df2.groupby(["chat_id", "date"]):
        first = grp.sort_values("timestamp").iloc[0]
        if first["is_from_me"]:
            conv_init += 1
        else:
            conv_recv += 1

    # Ghost contacts: Tucker's reply rate < 20%
    ghost_contacts = []
    for contact, grp in df.groupby("contact_name"):
        if contact == "Me":
            continue
        s = grp["is_from_me"].sum()
        r = (~grp["is_from_me"]).sum()
        if r > 0 and s / (s + r) < 0.2:
            ghost_contacts.append(contact)

    summary = pd.DataFrame([{
        "total_messages": total,
        "total_sent": total_sent,
        "total_received": total_received,
        "avg_messages_per_day": avg_per_day,
        "unique_contacts": unique_contacts,
        "most_active_day_of_week": most_active_dow,
        "most_active_hour": most_active_hour,
        "late_night_contacts": late_night_contacts,
        "pct_messages_with_attachments": pct_with_attach,
        "avg_message_length": avg_len,
        "avg_response_time_seconds": avg_rt,
        "conversations_initiated": conv_init,
        "conversations_received": conv_recv,
        "ghost_contacts": ghost_contacts,
    }])

    # Top contacts — group by chat_id so both sent and received are counted
    # per conversation partner (not just messages the contact sent).
    non_group = df[~df["is_group_chat"]]
    # Map chat_id → contact display name via received messages
    chat_to_contact = (
        non_group[~non_group["is_from_me"]]
        .groupby("chat_id")["contact_name"]
        .first()
        .to_dict()
    )
    rows = []
    for chat_id, grp in non_group.groupby("chat_id"):
        contact_label = chat_to_contact.get(chat_id, chat_id)
        rows.append({
            "contact": contact_label,
            "total": len(grp),
            "sent": int(grp["is_from_me"].sum()),
            "received": int((~grp["is_from_me"]).sum()),
        })
    contact_stats = (
        pd.DataFrame(rows)
        .sort_values("total", ascending=False)
        .head(top_n)
        .reset_index(drop=True)
    ) if rows else pd.DataFrame(columns=["contact", "total", "sent", "received"])

    return summary, contact_stats


def get_contact_summary(
    df: pd.DataFrame,
    contact: str,
    start: str | pd.Timestamp | None = None,
    end: str | pd.Timestamp | None = None,
    last_n_days: int | None = None,
    reference_date: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Compute per-contact messaging statistics.

    Args:
        df: DataFrame produced by get_messages().
        contact: Phone number or email to summarize. All format variants
            are checked (e.g. "+12345678900", "2345678900").
        start: Optional start date for filtering.
        end: Optional end date for filtering.
        last_n_days: If provided, overrides start/end.
        reference_date: Reference point for last_n_days. Defaults to now (UTC).

    Returns:
        Single-row DataFrame with columns:
        - total_messages (int)
        - total_sent (int)
        - total_received (int)
        - send_receive_ratio (float)
        - avg_messages_per_active_day (float)
        - total_active_days (int)
        - avg_read_time_seconds (float)
        - avg_response_time_you_seconds (float)
        - avg_response_time_contact_seconds (float)
        - conversations_initiated_you (int)
        - conversations_initiated_contact (int)
        - longest_gap_days (float)
        - messages_with_attachments (int)
        - avg_message_length_you (float)
        - avg_message_length_contact (float)
        - short_message_count_you (int)
        - short_message_count_contact (int)
        - most_active_hour (int, 0–23)
        - most_active_day_of_week (str)

    Examples:
        >>> from pymessage import EXAMPLE_BACKUP, get_messages, get_contact_summary
        >>> df = get_messages(EXAMPLE_BACKUP)
        >>> s = get_contact_summary(df, "+18015550002")
        >>> print(s["total_messages"].iloc[0])
    """
    df = _apply_time_filter(df, start, end, last_n_days, reference_date)

    variants = set(generate_phone_variants(contact))
    filtered = df[df["chat_id"].isin(variants)]

    empty = pd.DataFrame(
        columns=[
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
    )

    if filtered.empty:
        return empty

    sent = filtered[filtered["is_from_me"]]
    received = filtered[~filtered["is_from_me"]]

    total = len(filtered)
    total_sent = len(sent)
    total_received = len(received)
    ratio = total_sent / total_received if total_received > 0 else float("inf")

    active_days = filtered["timestamp"].dt.date.nunique()
    avg_per_day = total / active_days if active_days > 0 else 0.0

    # Avg read time (time between receiving a message and it being read)
    recv_with_read = received[received["read_at"].notna()]
    if not recv_with_read.empty:
        read_times = (
            recv_with_read["read_at"] - recv_with_read["timestamp"]
        ).dt.total_seconds()
        avg_read_time = float(read_times.mean())
    else:
        avg_read_time = float("nan")

    # Response times
    rt_you = _response_times(filtered, is_from_me=True)
    rt_contact = _response_times(filtered, is_from_me=False)
    avg_rt_you = float(rt_you.mean()) if not rt_you.empty else float("nan")
    avg_rt_contact = float(rt_contact.mean()) if not rt_contact.empty else float("nan")

    # Conversations initiated
    filtered2 = filtered.copy()
    filtered2["date"] = filtered2["timestamp"].dt.date
    init_you = 0
    init_contact = 0
    for _, grp in filtered2.groupby("date"):
        first = grp.sort_values("timestamp").iloc[0]
        if first["is_from_me"]:
            init_you += 1
        else:
            init_contact += 1

    # Longest gap
    sorted_ts = filtered["timestamp"].sort_values()
    if len(sorted_ts) > 1:
        gaps = sorted_ts.diff().dt.total_seconds().dropna() / 86400
        longest_gap = float(gaps.max())
    else:
        longest_gap = float("nan")

    # Attachments
    msgs_with_attach = int(filtered["attachment_path"].notna().sum())

    # Message lengths
    def _avg_len(sub: pd.DataFrame) -> float:
        texts = sub["message_text"].dropna()
        texts = texts[texts.str.strip() != ""]
        return float(texts.str.len().mean()) if not texts.empty else float("nan")

    def _short_count(sub: pd.DataFrame) -> int:
        texts = sub["message_text"].dropna()
        return int((texts.str.len() < 20).sum())

    avg_len_you = _avg_len(sent)
    avg_len_contact = _avg_len(received)
    short_you = _short_count(sent)
    short_contact = _short_count(received)

    most_active_hour = int(filtered["timestamp"].dt.hour.mode()[0])
    most_active_dow = filtered["timestamp"].dt.day_name().mode()[0]

    return pd.DataFrame([{
        "total_messages": total,
        "total_sent": total_sent,
        "total_received": total_received,
        "send_receive_ratio": ratio,
        "avg_messages_per_active_day": avg_per_day,
        "total_active_days": active_days,
        "avg_read_time_seconds": avg_read_time,
        "avg_response_time_you_seconds": avg_rt_you,
        "avg_response_time_contact_seconds": avg_rt_contact,
        "conversations_initiated_you": init_you,
        "conversations_initiated_contact": init_contact,
        "longest_gap_days": longest_gap,
        "messages_with_attachments": msgs_with_attach,
        "avg_message_length_you": avg_len_you,
        "avg_message_length_contact": avg_len_contact,
        "short_message_count_you": short_you,
        "short_message_count_contact": short_contact,
        "most_active_hour": most_active_hour,
        "most_active_day_of_week": most_active_dow,
    }])


def get_contact_heatmap(
    df: pd.DataFrame,
    contact: str,
    start: str | pd.Timestamp | None = None,
    end: str | pd.Timestamp | None = None,
    last_n_days: int | None = None,
    reference_date: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Build a 7×24 message-count heatmap for a contact.

    Args:
        df: DataFrame produced by get_messages().
        contact: Phone number or email to filter on.
        start: Optional start date for filtering.
        end: Optional end date for filtering.
        last_n_days: If provided, overrides start/end.
        reference_date: Reference point for last_n_days. Defaults to now (UTC).

    Returns:
        7×24 DataFrame where:
        - Index: day-of-week strings Monday through Sunday
        - Columns: integers 0–23 (hours)
        - Values: message counts (int)

    Examples:
        >>> from pymessage import EXAMPLE_BACKUP, get_messages, get_contact_heatmap
        >>> df = get_messages(EXAMPLE_BACKUP)
        >>> heatmap = get_contact_heatmap(df, "+18015550003")
        >>> print(heatmap.shape)  # (7, 24)
    """
    df = _apply_time_filter(df, start, end, last_n_days, reference_date)

    variants = set(generate_phone_variants(contact))
    filtered = df[df["chat_id"].isin(variants)].copy()

    day_order = [
        "Monday", "Tuesday", "Wednesday", "Thursday",
        "Friday", "Saturday", "Sunday",
    ]
    all_hours = list(range(24))

    if filtered.empty:
        return pd.DataFrame(0, index=day_order, columns=all_hours)

    filtered["hour"] = filtered["timestamp"].dt.hour
    filtered["dow"] = filtered["timestamp"].dt.day_name()

    pivot = (
        filtered.groupby(["dow", "hour"])
        .size()
        .unstack(fill_value=0)
    )

    # Ensure all days and hours are present
    pivot = pivot.reindex(index=day_order, columns=all_hours, fill_value=0)

    return pivot
