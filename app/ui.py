"""Blocs HTML réutilisables : bandeau de statut, cartes de résultat, écran d'accès, journal, tableaux."""

from __future__ import annotations

from html import escape

from src.quality import STABLE_FRAMES

TARGETS: dict[str, str] = {"Téléphone": "📱", "Portail": "🚧", "Porte": "🚪"}


def hero(title: str, subtitle: str) -> str:
    """En-tête de l'application."""
    return f"<div class='hero'><h1>{escape(title)}</h1><p>{escape(subtitle)}</p></div>"


def notice(text: str) -> str:
    """Encadré d'information, utilisé pour la confidentialité."""
    return f"<div class='notice'>{escape(text)}</div>"


def status_banner(kind: str, title: str, message: str, progress: int | None = None) -> str:
    """Bandeau de statut coloré : kind parmi ok, warn, err, idle, analyse."""
    bar = ""
    if progress is not None:
        percent = max(0, min(progress, STABLE_FRAMES)) / STABLE_FRAMES * 100
        bar = (
            f"<div class='bar'><div style='width:{percent:.0f}%'></div></div>"
            f"<div class='bar-label'>Stabilité {min(progress, STABLE_FRAMES)}/{STABLE_FRAMES}</div>"
        )
    return (
        f"<div class='status {kind}'><div class='status-title'>{escape(title)}</div>"
        f"<div class='status-msg'>{escape(message)}</div>{bar}</div>"
    )


def result_card(ok: bool, title: str, body: str, pill: str = "") -> str:
    """Carte de résultat, verte si ok, rouge sinon."""
    css = "ok" if ok else "no"
    return (
        f"<div class='card result {css}'><div class='result-title'>{escape(title)} {pill}</div>"
        f"<div>{body}</div></div>"
    )


def pill(text: str, kind: str) -> str:
    """Étiquette colorée : kind parmi ok, no, wait."""
    return f"<span class='pill pill-{kind}'>{escape(text)}</span>"


def access_screen(target: str, granted: bool | None, message: str) -> str:
    """Écran simulé de l'appareil : vert si l'accès est accordé, rouge s'il est refusé, gris en attente."""
    icon = TARGETS.get(target, "📱")
    if granted is None:
        state, title, glyph = "idle", "EN ATTENTE", icon
    elif granted:
        state, title, glyph = "granted", "ACCÈS ACCORDÉ", "🔓"
    else:
        state, title, glyph = "denied", "ACCÈS REFUSÉ", "🔒"
    return (
        "<div class='device-scene'><div class='device'>"
        f"<div class='screen {state}'><div class='screen-icon'>{glyph}</div>"
        f"<div class='screen-title'>{title}</div>"
        f"<div class='screen-msg'>{escape(message)}</div></div></div></div>"
    )


def journal_table(entries: list[dict]) -> str:
    """Tableau des dernières tentatives d'accès, la plus récente en premier."""
    if not entries:
        return "<div class='muted'>Aucune tentative pour le moment.</div>"
    rows = "".join(
        f"<tr><td>{escape(e['heure'])}</td><td>{escape(e['cible'])}</td>"
        f"<td>{escape(e['personne'])}</td><td>{escape(e['score'])}</td>"
        f"<td>{pill('Accordé', 'ok') if e['accorde'] else pill('Refusé', 'no')}</td></tr>"
        for e in reversed(entries)
    )
    return (
        "<table class='table'><tr><th>Heure</th><th>Cible</th><th>Personne</th>"
        f"<th>Similarité</th><th>Résultat</th></tr>{rows}</table>"
    )


def people_table(rows: list[tuple[str, int]]) -> str:
    """Tableau des personnes enregistrées et de leur nombre de photos."""
    if not rows:
        return "<div class='muted'>La base est vide.</div>"
    body = "".join(
        f"<tr><td><b>{escape(name)}</b></td><td>{count} photo(s)</td></tr>" for name, count in rows
    )
    return f"<table class='table'><tr><th>Personne</th><th>Vecteurs</th></tr>{body}</table>"