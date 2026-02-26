# China KI-Briefing 🇨🇳

Automatisiertes deutsches Executive Briefing aus **硅谷101** (Silicon Valley 101) – Chinas führender Deep-Tech-Podcast.

## Warum 硅谷101?

| Eigenschaft | Detail |
|------------|--------|
| **Host** | 泓君 (Jane Liu), Journalistin, basiert im Silicon Valley |
| **Sprache** | Mandarin – chinesische Innenperspektive |
| **Fokus** | KI, Chips, Agents, DeepSeek, US-China Tech-Wettbewerb |
| **Gäste** | Ex-DeepMind, Ex-Google, chinesische KI-Gründer, VCs |
| **Frequenz** | ~Biweekly + Weekly-Kurzformat |
| **RSS** | `https://feeds.fireside.fm/sv101/rss` (Fireside-hosted) |

### Dreiklang-Differenzierung

🇺🇸 **TBPN / All-In** → Was denkt das Silicon Valley?
🇨🇳 **硅谷101** → Was denken chinesische KI-Insider?
🇪🇺 **EU-Kontext** → Was bedeutet das für Europa?

## Wie es funktioniert

1. **RSS Feed** von 硅谷101 wird geprüft (2x/Woche: Mo + Do)
2. **MP3 Download** der neuesten Episode
3. **Gemini 2.5 Flash** analysiert das Mandarin-Audio → deutsches Briefing
4. **Email-HTML** wird generiert (Gold/Navy Design)
5. **Commit & Push** → Make.com kann die Datei abholen

## Setup

### 1. GitHub Secret
- `GEMINI_API_KEY` – Dein Google AI Studio API Key (gleicher wie beim Haupt-Briefing)

### 2. Workflow Permissions
- Settings → Actions → General → **Read and write permissions** ✅

### 3. Manueller Test
- Actions Tab → China KI-Briefing → Run workflow

## Dateien

| Datei | Zweck |
|-------|-------|
| `scraper.py` | RSS → Download → Gemini Audio → Briefing |
| `email_template.py` | Markdown → gestyltes HTML-Email |
| `processed.json` | Duplikat-Erkennung |
| `.github/workflows/china-briefing.yml` | GitHub Actions (Mo+Do 7:00 UTC) |

## Kosten

- Gemini 2.5 Flash: ~€0.01-0.03 pro Episode (~60 Min Audio)
- ~€0.05-0.15/Monat bei 2-4 Episoden

## Hinweis

Nicht jede 硅谷101-Episode ist KI-relevant (manche behandeln Krypto, Lifestyle etc.).
Der Prompt markiert solche Episoden automatisch als "⚠️ Geringe KI-Relevanz".
