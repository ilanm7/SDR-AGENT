"""
Aircall call history importer → TargetCo SDR CRM format.
Usage: python data/aircall_importer.py data/aircall_calls.csv
"""
import pandas as pd
import json
from pathlib import Path
import sys


def _get(row, keys):
    for k in keys:
        if k in row and pd.notna(row[k]) and str(row[k]).strip():
            return str(row[k]).strip()
    return ""


def load_aircall_calls(csv_path: str) -> list[dict]:
    df = pd.read_csv(csv_path, dtype=str)
    df.columns = df.columns.str.strip()

    calls = []
    for _, row in df.iterrows():
        answered = _get(row, ["answered"]).lower()
        missed_reason = _get(row, ["missed_call_reason"])
        duration_str = _get(row, ["duration (in call)", "duration (total)"])
        duration_sec = 0
        try:
            duration_sec = int(float(duration_str))
        except (ValueError, TypeError):
            pass

        call = {
            "id":           _get(row, ["call id"]),
            "id_internal":  _get(row, ["call id (internal)"]),
            "direction":    _get(row, ["direction"]),
            "date":         _get(row, ["datetime (utc)", "datetime (tz offset incl.)"]),
            "agent":        _get(row, ["user"]),
            "from":         _get(row, ["from"]),
            "to":           _get(row, ["to"]),
            "contact":      _get(row, ["customer number"]),
            "line":         _get(row, ["aircall number", "line"]),
            "answered":     answered == "yes",
            "missed_reason": missed_reason,
            "duration_sec": duration_sec,
            "tags":         _get(row, ["tags"]),
            "notes":        _get(row, ["comments"]),
            "call_type":    _get(row, ["call type"]),
            "outcome":      _classify_outcome(answered, missed_reason, duration_sec),
        }
        calls.append(call)

    return calls


def _classify_outcome(answered: str, missed_reason: str, duration_sec: int) -> str:
    if answered != "yes":
        if missed_reason:
            return f"no_answer ({missed_reason})"
        return "no_answer"
    if duration_sec < 20:
        return "rejected"
    if duration_sec < 90:
        return "short_call"
    return "meaningful_call"


def format_call_for_coaching(call: dict) -> str:
    outcome_labels = {
        "rejected":       "Hung up immediately",
        "short_call":     "Short call — prospect not receptive",
        "meaningful_call": "Substantial call",
    }
    label = outcome_labels.get(call["outcome"], call["outcome"])
    lines = [
        "Post-call coaching — analyze this call:",
        f"- Agent: {call['agent']}",
        f"- Contact: {call['contact'] or call['to']}",
        f"- Date: {call['date']}",
        f"- Duration: {call['duration_sec']}s",
        f"- Outcome: {label}",
    ]
    if call["tags"]:
        lines.append(f"- Tags: {call['tags']}")
    if call["notes"]:
        lines.append(f"- Notes: {call['notes']}")
    return "\n".join(lines)


def save_to_crm(calls: list[dict], output_path: str = "data/crm_calls.json"):
    path = Path(output_path)
    existing = []
    if path.exists():
        with open(path) as f:
            existing = json.load(f)

    existing_ids = {c["id"] for c in existing if c.get("id")}
    new_calls = [c for c in calls if c.get("id") not in existing_ids]

    all_calls = existing + new_calls
    with open(path, "w") as f:
        json.dump(all_calls, f, ensure_ascii=False, indent=2)

    return len(new_calls), len(all_calls)


if __name__ == "__main__":
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "data/aircall_calls.csv"
    calls = load_aircall_calls(csv_path)
    added, total = save_to_crm(calls)

    print(f"\n✅ Import complete")
    print(f"   New calls added : {added}")
    print(f"   Total calls in CRM : {total}")
    print(f"   File : data/crm_calls.json\n")

    from collections import Counter
    outcomes = Counter(c["outcome"] for c in calls)
    print("📊 Call outcomes breakdown:")
    for outcome, count in outcomes.most_common():
        print(f"   {outcome}: {count}")

    agents = Counter(c["agent"] for c in calls if c["agent"])
    print("\n👤 Calls per agent:")
    for agent, count in agents.most_common():
        print(f"   {agent}: {count} calls")
