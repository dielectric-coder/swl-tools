"""Shared schedule utilities used by swl.py and checksked.py."""


def compute_on_air(time_range, current_time):
    """Check if broadcast is active and compute duration/remaining time.
    Returns (duration_str, is_active, status_str, sort_minutes)."""
    if "-" not in time_range:
        return "—", False, "—", 9999
    try:
        start_s, end_s = time_range.split("-")
        start_time = int(start_s)
        end_time = int(end_s)
    except (ValueError, IndexError):
        return "—", False, "—", 9999

    duration = end_time - start_time
    is_active = False

    if duration < 0:
        duration += 2400
        is_active = (current_time >= start_time) or (current_time < end_time)
    else:
        is_active = start_time <= current_time < end_time

    dur_str = f"{duration:04d}"
    cur_h, cur_m = current_time // 100, current_time % 100
    cur_total = cur_h * 60 + cur_m

    if not is_active:
        sta_h, sta_m = start_time // 100, start_time % 100
        sta_total = sta_h * 60 + sta_m
        if sta_total <= cur_total:
            sta_total += 24 * 60
        until = sta_total - cur_total
        uh, um = until // 60, until % 60
        return dur_str, False, f"→ NEXT {uh:02d}h{um:02d}", until

    end_h, end_m = end_time // 100, end_time % 100
    end_total = end_h * 60 + end_m
    if end_total <= cur_total:
        end_total += 24 * 60
    remain = end_total - cur_total
    rh, rm = remain // 60, remain % 60
    return dur_str, True, f"◄ ON AIR {rh:02d}h{rm:02d}", remain
