"""
scraper.py – China KI-Briefing Pipeline

Parst RSS Feed von 硅谷101 (Silicon Valley 101), lädt die neueste Episode herunter,
schickt Audio an Gemini zur Analyse und erstellt ein deutsches Briefing.

Kein Transkript-Zwischenschritt: Audio → deutsches Briefing direkt.
"""

import os
import sys
import json
import re
import tempfile
import urllib.request
import urllib.error
from xml.etree import ElementTree as ET
from datetime import datetime, timedelta

# ============================================================
# KONFIGURATION
# ============================================================

SOURCES = {
    "硅谷101": {
        "rss": "https://feeds.fireside.fm/sv101/rss",
        "apple_id": None,
        "language": "mandarin",
        "min_duration_minutes": 20,
        "exclude_title_patterns": [],
        "description": "Chinesischsprachiger Deep-Tech-Podcast von 泓君 (Jane Liu) aus dem Silicon Valley. Chinesische Insider-Perspektive.",
    },
    "ChinaTalk": {
        "rss": None,  # Wird über iTunes Lookup ermittelt
        "apple_id": "1289062927",
        "language": "english",
        "min_duration_minutes": 20,
        "exclude_title_patterns": [],
        "description": "Englischsprachiger China-Tech-Podcast von Jordan Schneider. Westliche Analyse mit Policymaker- und Analysten-Gästen.",
    },
}

PROCESSED_FILE = "processed.json"
OUTPUT_BRIEFING = "briefing.md"
OUTPUT_EMAIL = "briefing_email.html"

GEMINI_MODEL = "gemini-2.5-flash"
MAX_OUTPUT_TOKENS = 16384
TEMPERATURE = 0.2

# ============================================================
# BRIEFING SYSTEM PROMPT (Chinesisch → Deutsch)
# ============================================================

BRIEFING_SYSTEM_PROMPT = """Du bist ein Senior-Analyst, der chinesischsprachige Podcast-Episoden für europäische Entscheider aufbereitet.

## DEINE AUFGABE
Du hörst eine chinesischsprachige Podcast-Episode und erstellst daraus ein DEUTSCHES Executive Briefing.
Die Zielgruppe sind europäische Führungskräfte und Entscheider, die verstehen wollen, was in Chinas KI- und Tech-Ökosystem passiert – und was das für Europa bedeutet.

## QUELLE
Dieses Briefing basiert auf einer von zwei China-Tech-Quellen:

1. **硅谷101** (Silicon Valley 101) – chinesischsprachiger Deep-Tech-Podcast von Journalistin 泓君 (Jane Liu), basiert im Silicon Valley. Chinesische Tech-Insider sprechen offen über DeepSeek, Agents, KI-Infra, Chip-Restriktionen. Das ist die chinesische Innenperspektive, die westliche Medien nicht liefern.

2. **ChinaTalk** – englischsprachiger China-Tech-Podcast von Jordan Schneider. Gäste sind Policymaker, Analysten, Akademiker. Westliche Analyse der chinesischen KI-Landschaft mit Fokus auf Geopolitik, Exportkontrollen, und strategische Implikationen.

## KRITISCHE REGELN

1. **NUR Informationen aus dem Audio verwenden.** Kein Hintergrundwissen einbringen.
2. **Aussagen korrekt zuordnen.** Sprechernamen und Rollen wie im Podcast genannt verwenden. Bei Unklarheit: "laut der Diskussion".
3. **Nuancen bewahren.** Wenn jemand unsicher ist oder spekuliert, das widerspiegeln. Chinesische Tech-Insider sind oft freimütiger als westliche – diese Offenheit einfangen.
4. **KORREKT übersetzen.** Chinesische Firmennamen, Personennamen und Fachbegriffe korrekt ins Deutsche übertragen. Bei bekannten Firmen die internationale Bezeichnung verwenden (z.B. ByteDance, nicht 字节跳动). Bei weniger bekannten Firmen: deutscher Name + (chinesischer Name).
5. **Chinesische Originalbegriffe in Klammern** bei wichtigen Konzepten, z.B. "Involution (内卷)", "Preiskrieg (价格战)".

## RELEVANZ-FILTER

Wähle die 2-4 relevantesten Themen. Nicht jede Episode ist KI-relevant – wenn die Episode kein KI/Tech-Thema hat, schreibe ein kurzes Briefing und markiere es als "Geringe KI-Relevanz".

HOHE PRIORITÄT:
1. Chinesische KI-Modelle: DeepSeek, Zhipu/智谱, MiniMax, Moonshot/月之暗面, Kimi, Qwen, Doubao
2. KI-Investitionen, Bewertungen, Funding in China
3. US-China Tech-Wettbewerb, Chip-Restriktionen, Exportkontrollen, Huawei Ascend
4. KI-Infrastruktur: Rechenzentren, Energie, GPU-Knappheit in China
5. KI-Agents, Anwendungen, Kommerzialisierung in China
6. Vergleiche China vs. USA vs. Europa
7. Chinesische Industriepolitik, Regulierung, "人工智能+"

NIEDRIGE PRIORITÄT:
- Krypto/Web3 ohne KI-Bezug
- Rein persönliche Gründergeschichten ohne Marktrelevanz
- Lifestyle-Themen (Haarausfall, Fitness, Karten-Trading etc.)

## OUTPUT-FORMAT

# 📋 Executive Summary

| Thema | Zentrale These | Person(en) | Quelle |
|-------|---------------|------------|--------|
| [Thema] | [1 Satz auf Deutsch] | [Name, Rolle] | 硅谷101 |

# 🎙 Deep-Dive Analysen

## [Emoji] [Thema]: [Überschrift auf Deutsch]

[Zusammenfassung, 3-5 Sätze auf Deutsch. Kontext für europäische Leser liefern.]

**Konkrete Details:** (MAXIMAL 6 Punkte)
- [Fakt/Zahl/Beispiel aus dem Podcast]
- ...

**🌏 Einordnung für Europa:**
- [Was bedeutet das für europäische Unternehmen/Investoren/Policymaker?]
- [Konkreter Bezug: Wettbewerb, Lieferketten, Regulierung, Marktchancen]

# 💭 Zum Drüber Nachdenken

GENAU 2 Impulse. Nicht mehr, nicht weniger.

**[Provokante These mit China-Europa-Bezug]**
Kontext: [2-3 Sätze mit konkreten Namen, Zahlen, Firmen aus dem Podcast]
Die Frage dahinter: [1 zugespitzter Satz]

**[Zweite These]**
Kontext: [2-3 Sätze]
Die Frage dahinter: [1 Satz]

## QUALITÄTS-CHECKLISTE (intern, nicht ausgeben)
- [ ] Ist ALLES auf Deutsch geschrieben?
- [ ] Sind chinesische Namen korrekt transkribiert?
- [ ] Stehen wichtige chinesische Begriffe in Klammern?
- [ ] Würde ein europäischer Entscheider verstehen, WARUM ihn das betrifft?
- [ ] Sind die Impulse überspitzt und meinungsstark?
- [ ] GENAU 2 Impulse bei "Zum Drüber Nachdenken"?
- [ ] Habe ich NUR Informationen aus dem Audio verwendet?
"""

BRIEFING_USER_PROMPT = """Analysiere diese Podcast-Episode und erstelle ein deutsches Executive Briefing für europäische Entscheider.

Podcast: {source_name}
Beschreibung: {source_description}
Sprache: {source_language}
Episoden-Titel: {episode_title}

WICHTIG:
- Falls die Episode KEIN KI/Tech-Thema behandelt (z.B. Krypto, Lifestyle, Militärgeschichte), erstelle trotzdem ein kurzes Briefing, aber markiere am Anfang: "⚠️ Geringe KI-Relevanz – Episode behandelt primär [Thema]"
- Falls KI-relevant: Volle Analyse gemäß System-Prompt
- Die "Einordnung für Europa"-Abschnitte sind PFLICHT und müssen konkret sein (nicht "das betrifft auch Europa")
- Schreibe in der Executive Summary Tabelle als Quelle: {source_name}

Erstelle das Briefing jetzt."""


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def load_processed():
    if os.path.exists(PROCESSED_FILE):
        with open(PROCESSED_FILE, "r") as f:
            return json.load(f)
    return {}


def save_processed(data):
    with open(PROCESSED_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_rss_url_from_apple_id(apple_id):
    """Resolve RSS feed URL from Apple Podcasts ID."""
    lookup_url = f"https://itunes.apple.com/lookup?id={apple_id}&entity=podcast"
    print(f"  Ermittle RSS Feed für Apple ID {apple_id}...")
    try:
        req = urllib.request.Request(lookup_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if data.get("resultCount", 0) > 0:
            feed_url = data["results"][0].get("feedUrl")
            if feed_url:
                print(f"  RSS Feed gefunden: {feed_url}")
                return feed_url
    except Exception as e:
        print(f"  WARNUNG: iTunes Lookup fehlgeschlagen: {e}")
    return None


def get_latest_rss_episode(rss_url, source_name, config):
    """Parse RSS feed and return latest episode info."""
    print(f"  Lade RSS Feed: {rss_url}")
    try:
        req = urllib.request.Request(rss_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            xml_data = resp.read()
    except Exception as e:
        print(f"  FEHLER: RSS Feed nicht erreichbar: {e}")
        return None

    root = ET.fromstring(xml_data)
    ns = {"itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd"}
    items = root.findall(".//item")

    min_dur = config.get("min_duration_minutes", 20)
    exclude = config.get("exclude_title_patterns", [])

    for item in items[:10]:
        title_el = item.find("title")
        title = title_el.text.strip() if title_el is not None and title_el.text else ""

        # Exclude patterns
        skip = False
        for pattern in exclude:
            if pattern.lower() in title.lower():
                skip = True
                break
        if skip:
            continue

        # Duration check
        dur_el = item.find("itunes:duration", ns)
        if dur_el is not None and dur_el.text:
            dur_text = dur_el.text.strip()
            try:
                if ":" in dur_text:
                    parts = dur_text.split(":")
                    if len(parts) == 3:
                        mins = int(parts[0]) * 60 + int(parts[1])
                    elif len(parts) == 2:
                        mins = int(parts[0])
                    else:
                        mins = 0
                else:
                    mins = int(dur_text) // 60
                if mins < min_dur:
                    print(f"  Überspringe (zu kurz: {mins} min): {title[:60]}")
                    continue
            except ValueError:
                pass

        # Audio URL
        enclosure = item.find("enclosure")
        if enclosure is None:
            continue
        audio_url = enclosure.get("url", "")
        if not audio_url:
            continue

        # Pub date
        pub_el = item.find("pubDate")
        pub_date = pub_el.text.strip() if pub_el is not None and pub_el.text else ""

        # GUID for dedup
        guid_el = item.find("guid")
        guid = guid_el.text.strip() if guid_el is not None and guid_el.text else audio_url

        print(f"  Neueste Episode: {title[:80]}")
        print(f"  Datum: {pub_date}")
        print(f"  Audio: {audio_url[:100]}...")
        return {
            "title": title,
            "audio_url": audio_url,
            "pub_date": pub_date,
            "guid": guid,
        }

    print(f"  Keine passende Episode gefunden für {source_name}")
    return None


def download_audio(url, max_size_mb=300):
    """Download audio file to temp location."""
    print(f"  Lade Audio herunter...")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=600) as resp:
            if ".m4a" in url.lower():
                suffix = ".m4a"
            elif ".ogg" in url.lower():
                suffix = ".ogg"
            else:
                suffix = ".mp3"

            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            total = 0
            while True:
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_size_mb * 1024 * 1024:
                    print(f"  WARNUNG: Datei zu groß (>{max_size_mb} MB), breche ab")
                    tmp.close()
                    os.unlink(tmp.name)
                    return None
                tmp.write(chunk)
            tmp.close()
            size_mb = total / (1024 * 1024)
            print(f"  Download komplett: {size_mb:.1f} MB → {tmp.name}")
            return tmp.name
    except Exception as e:
        print(f"  FEHLER beim Download: {e}")
        return None


def briefing_from_audio(audio_path, episode_title, source_name, source_config):
    """Send audio to Gemini and get German briefing directly."""
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        print("FEHLER: google-genai nicht installiert! Bitte: pip install google-genai")
        return None

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("FEHLER: GEMINI_API_KEY nicht gesetzt!")
        return None

    client = genai.Client(api_key=api_key)

    # Upload audio file
    print(f"  Lade Audio zu Gemini hoch...")
    try:
        uploaded = client.files.upload(file=audio_path)
        print(f"  Upload OK: {uploaded.name}")
    except Exception as e:
        print(f"  FEHLER beim Upload: {e}")
        return None

    # Wait for processing
    import time
    for attempt in range(30):
        status = client.files.get(name=uploaded.name)
        if status.state.name == "ACTIVE":
            print(f"  Datei aktiv, starte Analyse...")
            break
        print(f"  Warte auf Verarbeitung... (Versuch {attempt+1}/30)")
        time.sleep(10)
    else:
        print("  FEHLER: Datei wurde nicht rechtzeitig verarbeitet")
        return None

    # Generate briefing
    user_prompt = BRIEFING_USER_PROMPT.format(
        episode_title=episode_title,
        source_name=source_name,
        source_description=source_config.get("description", ""),
        source_language=source_config.get("language", "unknown"),
    )

    print(f"  Sende an Gemini ({GEMINI_MODEL}) zur Analyse...")
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[
                {
                    "parts": [
                        {"file_data": {"file_uri": uploaded.uri, "mime_type": uploaded.mime_type}},
                        {"text": user_prompt},
                    ]
                }
            ],
            config=types.GenerateContentConfig(
                system_instruction=BRIEFING_SYSTEM_PROMPT,
                temperature=TEMPERATURE,
                max_output_tokens=MAX_OUTPUT_TOKENS,
            ),
        )

        # Check finish reason
        finish_reason = None
        if response.candidates and len(response.candidates) > 0:
            finish_reason = response.candidates[0].finish_reason
            print(f"  Finish Reason: {finish_reason}")

        briefing_text = response.text
        print(f"  Briefing erhalten: {len(briefing_text)} Zeichen")

        # Check for truncation: if text is suspiciously short or ends mid-sentence
        if len(briefing_text) < 3000:
            print(f"  WARNUNG: Briefing sehr kurz ({len(briefing_text)} Zeichen) – möglicherweise abgeschnitten")
            print(f"  Letzte 100 Zeichen: ...{briefing_text[-100:]}")

            # Retry once with higher token limit
            print(f"  Versuche erneut mit erhöhtem Token-Limit...")
            response2 = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[
                    {
                        "parts": [
                            {"file_data": {"file_uri": uploaded.uri, "mime_type": uploaded.mime_type}},
                            {"text": user_prompt + "\n\nWICHTIG: Erstelle das VOLLSTÄNDIGE Briefing mit allen Abschnitten: Executive Summary, Deep-Dive Analysen (mit 'Einordnung für Europa'), und 'Zum Drüber Nachdenken' (GENAU 2 Impulse). Kürze NICHTS ab."},
                        ]
                    }
                ],
                config=types.GenerateContentConfig(
                    system_instruction=BRIEFING_SYSTEM_PROMPT,
                    temperature=TEMPERATURE,
                    max_output_tokens=MAX_OUTPUT_TOKENS * 2,
                ),
            )
            briefing_text2 = response2.text
            print(f"  Retry-Briefing erhalten: {len(briefing_text2)} Zeichen")

            # Use the longer version
            if len(briefing_text2) > len(briefing_text):
                briefing_text = briefing_text2
                print(f"  Verwende Retry-Version ({len(briefing_text)} Zeichen)")

        # Final validation: check all required sections are present
        required_sections = ["Executive Summary", "Deep-Dive", "Zum Drüber Nachdenken"]
        missing = [s for s in required_sections if s not in briefing_text and "Geringe KI-Relevanz" not in briefing_text]
        if missing:
            print(f"  WARNUNG: Fehlende Abschnitte: {missing}")

        return briefing_text
    except Exception as e:
        print(f"  FEHLER bei Gemini-Analyse: {e}")
        return None
    finally:
        try:
            client.files.delete(name=uploaded.name)
        except:
            pass


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 60)
    print("CHINA KI-BRIEFING PIPELINE")
    print("Quelle: 硅谷101 (Silicon Valley 101)")
    print("=" * 60)

    processed = load_processed()
    briefing_parts = []

    for source_name, config in SOURCES.items():
        print(f"\n--- {source_name} ---")

        rss_url = config.get("rss")
        if not rss_url:
            # Try iTunes lookup
            apple_id = config.get("apple_id")
            if apple_id:
                rss_url = get_rss_url_from_apple_id(apple_id)
            if not rss_url:
                print(f"  FEHLER: Kein RSS Feed für {source_name}")
                continue

        # Get latest episode
        episode = get_latest_rss_episode(rss_url, source_name, config)
        if not episode:
            continue

        # Dedup check
        dedup_key = f"{source_name}_{episode['guid']}"
        if dedup_key in processed:
            print(f"  Bereits verarbeitet, überspringe.")
            continue

        # Download audio
        audio_path = download_audio(episode["audio_url"])
        if not audio_path:
            continue

        try:
            briefing = briefing_from_audio(audio_path, episode["title"], source_name, config)
            if briefing:
                # Relevanz-Check: Überspringen wenn Gemini "Geringe KI-Relevanz" markiert
                if "Geringe KI-Relevanz" in briefing:
                    print(f"  ⏭️  Geringe KI-Relevanz – Episode wird übersprungen")
                    processed[dedup_key] = {
                        "title": episode["title"],
                        "date": episode["pub_date"],
                        "processed_at": datetime.now().isoformat(),
                        "method": "skipped_low_relevance",
                    }
                else:
                    briefing_parts.append(briefing)
                    processed[dedup_key] = {
                        "title": episode["title"],
                        "date": episode["pub_date"],
                        "processed_at": datetime.now().isoformat(),
                        "method": "gemini_audio_to_briefing",
                    }
                    print(f"  ✅ Briefing erstellt für: {episode['title'][:60]}")
            else:
                print(f"  ❌ Briefing-Erstellung fehlgeschlagen")
        finally:
            if os.path.exists(audio_path):
                os.unlink(audio_path)

    # Save results
    if briefing_parts:
        full_briefing = "\n\n---\n\n".join(briefing_parts)

        with open(OUTPUT_BRIEFING, "w", encoding="utf-8") as f:
            f.write(full_briefing)
        print(f"\n✅ Briefing gespeichert: {OUTPUT_BRIEFING} ({len(full_briefing)} Zeichen)")

        # Generate email HTML
        try:
            from email_template import convert_md_to_email
            email_html = convert_md_to_email(full_briefing)
            with open(OUTPUT_EMAIL, "w", encoding="utf-8") as f:
                f.write(email_html)
            print(f"✅ Email-HTML gespeichert: {OUTPUT_EMAIL} ({len(email_html)} Zeichen)")
        except ImportError:
            print("⚠️  email_template.py nicht gefunden – überspringe HTML")
        except Exception as e:
            print(f"⚠️  Email-HTML Fehler: {e}")

        save_processed(processed)
    else:
        print("\n⚠️  Keine neuen Episoden verarbeitet.")
        if not os.path.exists(OUTPUT_BRIEFING):
            with open(OUTPUT_BRIEFING, "w") as f:
                f.write("Keine neue Episode verfügbar.\n")


if __name__ == "__main__":
    main()
