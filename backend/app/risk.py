from app.models import RiskLevel


WATCH = {
    "temp_low": 36.0,
    "temp_high": 37.5,
    "sbp_low": 90,
    "sbp_high": 160,
    "spo2": 94,
    "pr_low": 50,
    "pr_high": 110,
    "rr_low": 10,
    "rr_high": 24,
}

CRITICAL = {
    "temp_low": 35.0,
    "temp_high": 39.0,
    "sbp_low": 80,
    "sbp_high": 180,
    "spo2": 90,
    "pr_low": 40,
    "pr_high": 130,
    "rr_low": 8,
    "rr_high": 30,
}


def suggest_risk(vitals: dict | None, critical_flag: bool = False) -> RiskLevel:
    if critical_flag:
        return RiskLevel.critical
    if not vitals:
        return RiskLevel.stable
    temp = vitals.get("temp")
    sbp = vitals.get("bp_systolic")
    spo2 = vitals.get("spo2")
    pr = vitals.get("pr")
    rr = vitals.get("rr")

    def out(val, low, high):
        return val is not None and (val < low or val > high)

    if (
        out(temp, CRITICAL["temp_low"], CRITICAL["temp_high"])
        or out(sbp, CRITICAL["sbp_low"], CRITICAL["sbp_high"])
        or (spo2 is not None and spo2 < CRITICAL["spo2"])
        or out(pr, CRITICAL["pr_low"], CRITICAL["pr_high"])
        or out(rr, CRITICAL["rr_low"], CRITICAL["rr_high"])
    ):
        return RiskLevel.critical

    if (
        out(temp, WATCH["temp_low"], WATCH["temp_high"])
        or out(sbp, WATCH["sbp_low"], WATCH["sbp_high"])
        or (spo2 is not None and spo2 < WATCH["spo2"])
        or out(pr, WATCH["pr_low"], WATCH["pr_high"])
        or out(rr, WATCH["rr_low"], WATCH["rr_high"])
    ):
        return RiskLevel.watch
    return RiskLevel.stable
