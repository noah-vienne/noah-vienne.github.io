#!/usr/bin/env python3
"""
update_rss.py — Récupère les flux RSS cybersécurité,
filtre les articles liés aux ransomwares et met à jour index.html.
Lancé automatiquement chaque jour par GitHub Actions.
"""

import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
import re
import sys
import os

# ── Configuration ─────────────────────────────────────────────────────────────

FEEDS = [
    {
        "name": "CERT-FR",
        "url": "https://www.cert.ssi.gouv.fr/feed/",
        "label": "CERT-FR — Alertes & Bulletins",
        "icon": "fas fa-shield-alt",
    },
    {
        "name": "LeMagIT",
        "url": "https://www.lemagit.fr/rss/Securite.xml",
        "label": "LeMagIT — Sécurité",
        "icon": "fas fa-newspaper",
    },
    {
        "name": "01net",
        "url": "https://www.01net.com/rss/actualites/securite/",
        "label": "01net — Cybersécurité",
        "icon": "fas fa-globe",
    },
]

# Mots-clés pour filtrer — si AUCUN résultat, on affiche tout sans filtre
KEYWORDS = [
    "ransomware", "rançongiciel", "rançon", "ransom",
    "chiffrement des données", "extorsion", "lockbit", "blackcat",
    "alphv", "ryuk", "conti", "clop", "akira", "play ransomware",
    "phishing", "hameçonnage", "cyberattaque", "cyber-attaque",
    "malware", "logiciel malveillant", "sauvegarde", "backup",
    "nis2", "nis 2", "double extorsion", "rançon",
    "données chiffrées", "système chiffré", "attaque informatique",
    "violation de données", "fuite de données",
]

MAX_PER_FEED = 8      # Articles max par flux
MAX_FALLBACK = 8      # Articles si aucun résultat filtré

MARKER_START = "<!-- FLUX RSS AUTOMATIQUE -->"
MARKER_END   = "<!-- FIN FLUX RSS -->"

# ── Helpers ────────────────────────────────────────────────────────────────────

def fetch_feed(url: str) -> list:
    """Télécharge et parse un flux RSS."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; RSS Reader)",
            "Accept": "application/rss+xml, application/xml, text/xml",
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
        root = ET.fromstring(raw)
        items = root.findall(".//item")
        result = []
        for item in items:
            title   = item.findtext("title", "").strip()
            link    = item.findtext("link", "").strip()
            pub     = item.findtext("pubDate", "").strip()
            summary = item.findtext("description", "").strip()
            # Nettoyer le HTML dans le résumé
            summary = re.sub(r"<[^>]+>", " ", summary)
            if title and link:
                result.append({
                    "title":   title,
                    "link":    link,
                    "date":    pub,
                    "summary": summary[:300],
                })
        return result
    except Exception as e:
        print(f"  [ERREUR] {url} → {e}", file=sys.stderr)
        return []


def matches_keywords(text: str) -> bool:
    """Retourne True si le texte contient au moins un mot-clé."""
    low = text.lower()
    return any(kw in low for kw in KEYWORDS)


def filter_articles(articles: list, max_count: int) -> list:
    """Filtre les articles par mots-clés, ou retourne les plus récents si aucun."""
    filtered = [
        a for a in articles
        if matches_keywords(a["title"] + " " + a["summary"])
    ]
    if filtered:
        print(f"     → {len(filtered)} articles filtrés (ransomware/cyber)")
        return filtered[:max_count]
    # Fallback : pas de filtre, on prend les plus récents
    print(f"     → Aucun article filtré, affichage des {min(len(articles), max_count)} plus récents")
    return articles[:max_count]


def format_date(date_str: str) -> str:
    """Convertit une date RFC 2822 en format lisible français."""
    if not date_str:
        return ""
    try:
        date_str = re.sub(r"\s+[A-Z]{2,4}$", "", date_str.strip())
        formats = [
            "%a, %d %b %Y %H:%M:%S %z",
            "%a, %d %b %Y %H:%M:%S",
            "%d %b %Y %H:%M:%S %z",
        ]
        dt = None
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                break
            except ValueError:
                continue
        if dt:
            mois = ["jan.", "fév.", "mars", "avr.", "mai", "juin",
                    "juil.", "août", "sep.", "oct.", "nov.", "déc."]
            return f"{dt.day:02d} {mois[dt.month - 1]} {dt.year}"
    except Exception:
        pass
    return date_str[:16] if len(date_str) > 16 else date_str


def build_rss_html(feeds_data: list) -> str:
    """Génère le bloc HTML complet."""
    now = datetime.now(timezone.utc)
    update_str = f"{now.day:02d}/{now.month:02d}/{now.year} à {now.hour:02d}h{now.minute:02d} UTC"

    cols_html = ""
    for feed in feeds_data:
        items_html = ""
        if feed["articles"]:
            for art in feed["articles"]:
                date_display = format_date(art["date"])
                date_html = f'<span class="rss-item-date">{date_display}</span>' if date_display else ""
                title = art["title"]
                if len(title) > 100:
                    title = title[:97] + "…"
                items_html += f"""            <div class="rss-item">
              <a href="{art['link']}" target="_blank" rel="noopener">{title}</a>
              {date_html}
            </div>\n"""
        else:
            items_html = '            <div class="rss-error">Flux temporairement indisponible.</div>\n'

        cols_html += f"""
        <!-- {feed['name']} -->
        <div class="rss-feed-col">
          <div class="rss-feed-label">
            <i class="{feed['icon']}"></i> {feed['label']}
          </div>
          <div class="rss-list">
{items_html}          </div>
        </div>
"""

    return f"""    {MARKER_START}
    <div class="rss-block reveal">
      <div class="rss-header">
        <div class="rss-title-row">
          <div class="rss-dot"></div>
          <h3>Actualités ransomwares — Sources officielles</h3>
          <span class="rss-live">MÀJ AUTO</span>
        </div>
        <p class="rss-desc">Articles filtrés sur les ransomwares et la cybersécurité, mis à jour automatiquement chaque jour. Dernière mise à jour : {update_str}</p>
      </div>

      <div class="rss-feeds-grid">
{cols_html}
      </div>
      <div class="rss-footer">
        <i class="fas fa-sync-alt"></i> Mis à jour automatiquement chaque jour via GitHub Actions — Sources : cert.ssi.gouv.fr · lemagit.fr · 01net.com
      </div>
    </div>

    {MARKER_END}"""


def update_html(html_path: str, new_block: str) -> bool:
    """Remplace le bloc RSS dans index.html entre les deux marqueurs."""
    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()

    if MARKER_START not in content or MARKER_END not in content:
        print(f"  [ERREUR] Marqueurs introuvables dans {html_path}", file=sys.stderr)
        return False

    pattern = re.compile(
        re.escape(MARKER_START) + r".*?" + re.escape(MARKER_END),
        re.DOTALL
    )
    new_content = pattern.sub(new_block, content)

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(new_content)
    return True


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    html_path = os.path.join(os.path.dirname(__file__), "index.html")
    if not os.path.exists(html_path):
        print(f"[ERREUR] index.html introuvable : {html_path}", file=sys.stderr)
        sys.exit(1)

    print("Récupération des flux RSS...")
    feeds_data = []
    for feed in FEEDS:
        print(f"  → {feed['name']} ({feed['url']})")
        articles = fetch_feed(feed["url"])
        print(f"     {len(articles)} articles récupérés")
        filtered = filter_articles(articles, MAX_PER_FEED)
        feeds_data.append({
            "name":     feed["name"],
            "label":    feed["label"],
            "icon":     feed["icon"],
            "articles": filtered,
        })

    print("Génération du bloc HTML...")
    new_block = build_rss_html(feeds_data)

    print(f"Mise à jour de {html_path}...")
    ok = update_html(html_path, new_block)
    if ok:
        print("✅ index.html mis à jour avec succès !")
    else:
        print("❌ Échec de la mise à jour.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()