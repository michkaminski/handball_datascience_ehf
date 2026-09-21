KICKOFF_DISPLAY_FMT = "Dy Mon DD, YYYY HH24:MI"
KICKOFF_AT_SQL = (
    f"COALESCE(m.kickoff_at, to_timestamp(m.kickoff_display, '{KICKOFF_DISPLAY_FMT}'))"
)
