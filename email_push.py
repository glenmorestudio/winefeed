#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
winefeed daily brief -> Klaviyo DRAFT campaign
==============================================
Renders nothing itself; reads the HTML email_brief.py already wrote to
~/primal_claude/klaviyo/winefeed-daily-brief.html (local-first source of truth),
updates the winefeed template, and creates a DRAFT campaign to the "Winefeed Daily
Brief" list. It NEVER creates a send job, so nothing goes out without a human in
Klaviyo pressing send (honors "Klaviyo owns email").

Idempotent per day: re-running updates that day's existing draft instead of piling
up duplicates. Skips cleanly (exit 0) if no Klaviyo private key is available.

Key: env KLAVIYO_PRIVATE_KEY, else ~/.primal_wine_club/config.json "klaviyo_key".
Run:  python3 email_brief.py && python3 email_push.py
"""
import json, os, sys, subprocess, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
REVISION = "2025-10-15"
TEMPLATE_ID = "WuKNJh"                 # "winefeed Daily Brief" template
FROM_EMAIL = "guido@primalwine.com"    # verified sender on the account
FROM_LABEL = "winefeed by Primal Wine"
REPLY_TO = "guido@primalwine.com"
# repo-local send file (written by email_brief.py; present on CI too),
# falling back to the local source-of-truth mirror if that's all there is.
HTML_PATH = os.path.join(HERE, "winefeed-email-klaviyo.html")
HTML_FALLBACK = os.path.expanduser("~/primal_claude/klaviyo/winefeed-daily-brief.html")

def get_key():
    k = os.environ.get("KLAVIYO_PRIVATE_KEY")
    if k:
        return k.strip()
    cfg = os.path.expanduser("~/.primal_wine_club/config.json")
    if os.path.exists(cfg):
        try:
            return json.load(open(cfg)).get("klaviyo_key")
        except Exception:
            return None
    return None

def get_list_id():
    try:
        return json.load(open(os.path.join(HERE, "klaviyo.json"))).get("list", "")
    except Exception:
        return ""

def kv(key, method, path, body=None):
    """Klaviyo API call -> (status_ok, parsed_json)."""
    args = ["curl", "-s", "-g", "-w", "\n%{http_code}", "-X", method,
            "https://a.klaviyo.com/api/" + path,
            "-H", "Authorization: Klaviyo-API-Key " + key,
            "-H", "revision: " + REVISION,
            "-H", "accept: application/json",
            "-H", "content-type: application/json"]
    if body is not None:
        args += ["-d", json.dumps(body)]
    r = subprocess.run(args, capture_output=True, timeout=60)
    out = r.stdout.decode("utf-8", "replace")
    nl = out.rfind("\n")
    code = out[nl + 1:].strip()
    payload = out[:nl] if nl >= 0 else out
    try:
        data = json.loads(payload) if payload.strip() else {}
    except Exception:
        data = {"_raw": payload}
    ok = code.startswith("2")
    return ok, data

def subject_and_preview():
    """A specific, enticing subject + preheader built from the day's lead briefs."""
    d = json.load(open(os.path.join(HERE, "feed_data.json")))
    items = d.get("items", {})
    heads = []
    for tab in ("MARKET", "CULTURE", "SCIENCE"):
        for row in items.get(tab, []):
            h = (row.get("head") or "").strip()
            if h:
                heads.append(h)
    lead = heads[0] if heads else "Today's wine brief"
    rest = heads[1:3]
    preview = "Plus: " + " · ".join(rest) if rest else "The wine world, summarized."
    return lead[:150], preview[:180]

def main():
    key = get_key()
    if not key:
        print("No Klaviyo key; skipping draft push (email HTML still written locally).")
        return 0
    list_id = get_list_id()
    if not list_id:
        print("No list id in klaviyo.json; aborting.", file=sys.stderr)
        return 1
    path = HTML_PATH if os.path.exists(HTML_PATH) else HTML_FALLBACK
    if not os.path.exists(path):
        print(f"Email HTML not found ({HTML_PATH}); run email_brief.py first.", file=sys.stderr)
        return 1
    html = open(path).read()

    today = datetime.date.today().isoformat()
    name = f"winefeed daily brief — {today}"
    subject, preview = subject_and_preview()

    # 1) refresh the shared template with today's HTML (assign clones it into the message)
    ok, data = kv(key, "PATCH", f"templates/{TEMPLATE_ID}/", {
        "data": {"type": "template", "id": TEMPLATE_ID,
                 "attributes": {"name": "winefeed Daily Brief", "html": html}}})
    if not ok:
        print("! template update failed:", json.dumps(data.get("errors", data))[:600], file=sys.stderr)
    else:
        print(f"template {TEMPLATE_ID} updated")

    # 2) find today's draft campaign (idempotent) or create a fresh draft
    campaign_id = None
    ok, data = kv(key, "GET", "campaigns/?filter=equals(messages.channel,'email')&sort=-created_at&page[size]=50")
    if ok:
        for c in data.get("data", []):
            if c.get("attributes", {}).get("name") == name:
                if c.get("attributes", {}).get("status", "").lower() in ("", "draft", "queued without recipients"):
                    campaign_id = c["id"]
                break

    if campaign_id:
        print(f"reusing today's draft campaign {campaign_id}")
    else:
        ok, data = kv(key, "POST", "campaigns/", {
            "data": {"type": "campaign", "attributes": {
                "name": name,
                "audiences": {"included": [list_id], "excluded": []},
                "campaign-messages": {"data": [{
                    "type": "campaign-message",
                    "attributes": {"definition": {
                        "channel": "email",
                        "label": "winefeed daily brief",
                        "content": {
                            "subject": subject, "preview_text": preview,
                            "from_email": FROM_EMAIL, "from_label": FROM_LABEL,
                            "reply_to_email": REPLY_TO}}}}]}}}})
        if not ok:
            print("! campaign create failed:", json.dumps(data.get("errors", data))[:600], file=sys.stderr)
            return 1
        campaign_id = data["data"]["id"]
        print(f"created draft campaign {campaign_id}")

    # 3) get the campaign's email message id
    ok, data = kv(key, "GET", f"campaigns/{campaign_id}/campaign-messages/")
    if not ok or not data.get("data"):
        print("! could not read campaign message", file=sys.stderr)
        return 1
    message_id = data["data"][0]["id"]

    # 4) update the message subject/preview (in case headlines changed on a re-run)
    kv(key, "PATCH", f"campaign-messages/{message_id}/", {
        "data": {"type": "campaign-message", "id": message_id,
                 "attributes": {"definition": {"channel": "email", "content": {
                     "subject": subject, "preview_text": preview,
                     "from_email": FROM_EMAIL, "from_label": FROM_LABEL,
                     "reply_to_email": REPLY_TO}}}}})

    # 5) clone today's template HTML into the message (this is the actual body)
    ok, data = kv(key, "POST", "campaign-message-assign-template/", {
        "data": {"type": "campaign-message", "id": message_id,
                 "relationships": {"template": {"data": {"type": "template", "id": TEMPLATE_ID}}}}})
    if not ok:
        print("! assign-template failed:", json.dumps(data.get("errors", data))[:600], file=sys.stderr)
        return 1

    print(f"DRAFT ready — subject: {subject!r}")
    print(f"Review + send in Klaviyo: https://www.klaviyo.com/campaign/{campaign_id}/")
    return 0

if __name__ == "__main__":
    sys.exit(main())
