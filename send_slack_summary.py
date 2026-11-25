"""Send a short summary of the latest scan report to Slack."""
import os
import re
import sys
from pathlib import Path

import requests

REPORT = Path("data/daily_scans/latest_optimized_scan.txt")
TOP_BUYS = 15
TOP_SELLS = 10


def parse_signals(text, kind):
    pattern = re.compile(rf"{kind} #(\d+): (\S+) \| Score: ([\d.]+)/(\d+)")
    blocks = []
    lines = text.splitlines()
    for i, line in enumerate(lines):
        m = pattern.search(line)
        if not m:
            continue
        sig = {"ticker": m.group(2), "score": m.group(3), "max": m.group(4)}
        for nxt in lines[i + 1:i + 25]:
            if re.search(r"(BUY|SELL) #\d+:", nxt):
                break
            if "Stop Loss:" in nxt and "stop" not in sig:
                sig["stop"] = nxt.split("Stop Loss:")[1].strip()
            elif "Risk/Reward:" in nxt and "rr" not in sig:
                sig["rr"] = nxt.split("Risk/Reward:")[1].split("(")[0].strip()
            elif "Entry Quality:" in nxt and "entry" not in sig:
                sig["entry"] = nxt.split("Entry Quality:")[1].strip()
        blocks.append(sig)
    return blocks


def count(text, label):
    m = re.search(rf"{label}: (\d+)", text)
    return m.group(1) if m else "?"


def main():
    webhook = os.getenv("SLACK_WEBHOOK_URL")
    if not webhook:
        print("SLACK_WEBHOOK_URL not set, skipping Slack message.")
        return 0
    if not REPORT.exists():
        requests.post(webhook, json={"text": "⚠️ Tarama raporu bulunamadı, tarama başarısız olmuş olabilir."}, timeout=30)
        return 0

    text = REPORT.read_text(encoding="utf-8")
    date = re.search(r"Scan Date: (\S+)", text)
    date = date.group(1) if date else ""

    buys = parse_signals(text, "BUY")
    sells = parse_signals(text, "SELL")

    msg = [f"*📊 Günlük Tarama — {date}*",
           f"Alım sinyali: *{count(text, 'Buy Signals')}*  |  Satış sinyali: *{count(text, 'Sell Signals')}*",
           ""]

    if buys:
        msg.append(f"*🟢 En iyi {min(TOP_BUYS, len(buys))} alım*")
        for s in buys[:TOP_BUYS]:
            extra = []
            if "entry" in s:
                extra.append(s["entry"])
            if "stop" in s:
                extra.append(f"stop {s['stop']}")
            if "rr" in s:
                extra.append(f"R/R {s['rr']}")
            msg.append(f"• *{s['ticker']}* {s['score']}/{s['max']}" + (f" — {', '.join(extra)}" if extra else ""))
    else:
        msg.append("🟢 Alım sinyali yok (piyasa filtresi alıma izin vermemiş olabilir).")

    msg.append("")
    if sells:
        msg.append(f"*🔴 En güçlü {min(TOP_SELLS, len(sells))} satış*")
        msg.append(", ".join(f"{s['ticker']} ({s['score']})" for s in sells[:TOP_SELLS]))

    r = requests.post(webhook, json={"text": "\n".join(msg)}, timeout=30)
    print("Slack:", r.status_code, r.text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
