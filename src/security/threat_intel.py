"""Optional threat-intelligence lookup. OFF by default and opt-in per analysis.

Safety design (SSRF / privacy):
  * The endpoint is a constant; user-controlled text is only ever placed inside the JSON *body*, never in the host/path.
  * Suspicious URLs are NEVER fetched by us. The provider only receives the address as data.
  * Needs THREAT_INTEL_PROVIDER=safebrowsing and THREAT_INTEL_API_KEY in the environment. Without them nothing happens.
  * Any failure returns status "unknown" (never "safe"). "not_flagged" never means safe.
  * The URL addresses are sent to a third party, so the UI must ask the user first.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass

SAFE_BROWSING_ENDPOINT = "https://safebrowsing.googleapis.com/v4/threatMatches:find"
TIMEOUT_SECONDS = 4
MAX_URLS = 10


@dataclass(frozen=True)
class ThreatVerdict:
    url: str
    status: str            # flagged | not_flagged | unknown
    detail: str = ""


class ThreatIntelProvider:
    name = "none"

    def check(self, urls: list[str]) -> dict[str, ThreatVerdict]:  # pragma: no cover - interface
        raise NotImplementedError


class NullProvider(ThreatIntelProvider):
    name = "none"

    def check(self, urls):
        return {u: ThreatVerdict(u, "unknown", "no provider configured") for u in urls}


class SafeBrowsingProvider(ThreatIntelProvider):
    name = "google_safe_browsing"

    def __init__(self, api_key: str):
        self._key = api_key

    def check(self, urls):
        urls = [u for u in urls][:MAX_URLS]
        if not urls:
            return {}
        body = {"client": {"clientId": "gramsuraksha", "clientVersion": "2.0"},
                "threatInfo": {"threatTypes": ["MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE", "POTENTIALLY_HARMFUL_APPLICATION"],
                               "platformTypes": ["ANY_PLATFORM"], "threatEntryTypes": ["URL"],
                               "threatEntries": [{"url": u} for u in urls]}}
        req = urllib.request.Request(f"{SAFE_BROWSING_ENDPOINT}?key={self._key}", data=json.dumps(body).encode("utf-8"),
                                     headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:   # fixed https endpoint, bounded time
                payload = json.loads(resp.read(1_000_000).decode("utf-8") or "{}")
        except (urllib.error.URLError, TimeoutError, ValueError, OSError):
            return {u: ThreatVerdict(u, "unknown", "provider unavailable") for u in urls}
        flagged = {m.get("threat", {}).get("url"): m.get("threatType", "") for m in payload.get("matches", [])}
        return {u: (ThreatVerdict(u, "flagged", flagged[u]) if u in flagged else ThreatVerdict(u, "not_flagged", "not in provider lists")) for u in urls}


def get_provider(env=None) -> ThreatIntelProvider | None:
    """Configured provider or None. Never raises and never logs the key."""
    env = os.environ if env is None else env
    if env.get("THREAT_INTEL_PROVIDER", "").lower() == "safebrowsing" and env.get("THREAT_INTEL_API_KEY"):
        return SafeBrowsingProvider(env["THREAT_INTEL_API_KEY"])
    return None
