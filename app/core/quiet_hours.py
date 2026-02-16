from __future__ import annotations


def _parse_hhmm(value: str) -> tuple[int, int]:
    hour, minute = value.split(':', 1)
    return int(hour), int(minute)


def is_quiet_now(rule_config, time_provider) -> bool:
    cfg = rule_config or {}
    start_h, start_m = _parse_hhmm(cfg.get('quiet_hours_start', '22:00'))
    end_h, end_m = _parse_hhmm(cfg.get('quiet_hours_end', '06:00'))
    if hasattr(time_provider, 'time') and callable(getattr(time_provider, 'time')):
        now = time_provider.time()
    elif callable(time_provider):
        now = time_provider()
    else:
        now = time_provider
    start_t = now.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
    end_t = now.replace(hour=end_h, minute=end_m, second=0, microsecond=0)
    if start_t <= end_t:
        return start_t <= now < end_t
    return now >= start_t or now < end_t
