"""Application web : temps réel, enregistrement et simulation d'accès, avec une base locale de vecteurs."""

from __future__ import annotations

import time
import unicodedata
from collections import Counter, deque
from datetime import datetime

import cv2
import gradio as gr
import numpy as np

from app.styles import CSS
from app.ui import (
    TARGETS,
    access_screen,
    hero,
    journal_table,
    notice,
    people_table,
    pill,
    result_card,
    status_banner,
)
from src.config import EnrollmentConfig, QualityConfig, RecognitionConfig
from src.database import Database
from src.detect import Detection, align_face
from src.quality import STABLE_FRAMES, FrameReport, assess
from src.recognize import RecognitionError, Recognizer, ThresholdNotSetError

TITLE: str = "Reconnaissance faciale"
SUBTITLE: str = "Temps réel, enregistrement et simulation d'accès"
NOTICE: str = (
    "Les données biométriques ne sont jamais conservées sous forme de photo : seuls des vecteurs numériques "
    "sont stockés. Enregistrez une personne uniquement avec son consentement, et supprimez ses données sur demande."
)
PROCESS_INTERVAL: float = 0.6
JOURNAL_LIMIT: int = 20
UNKNOWN: str = "__inconnu__"
FONT: int = cv2.FONT_HERSHEY_SIMPLEX
COLORS: dict[str, tuple[int, int, int]] = {
    "green": (22, 163, 74),
    "red": (220, 38, 38),
    "yellow": (234, 179, 8),
    "orange": (245, 158, 11),
    "grey": (100, 116, 139),
}
LEVEL_KIND: dict[str, str] = {"ok": "ok", "warning": "warn", "error": "err"}
LEVEL_COLOR: dict[str, str] = {"ok": "green", "warning": "orange", "error": "red"}

_recognizer: Recognizer | None = None
_journal: list[dict] = []


def get_recognizer() -> Recognizer:
    """Crée le moteur une seule fois, puis le réutilise pour toutes les requêtes."""
    global _recognizer
    if _recognizer is None:
        _recognizer = Recognizer(Database(), RecognitionConfig())
    return _recognizer


def ascii_label(text: str) -> str:
    """Retire les accents, car la police OpenCV ne les affiche pas."""
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()


def draw_box(frame: np.ndarray, bbox: tuple, color: str, label: str) -> np.ndarray:
    """Dessine un cadre autour du visage, avec une étiquette collée au-dessus."""
    canvas = frame.copy()
    rgb = COLORS[color]
    x1, y1, x2, y2 = (int(v) for v in bbox)
    cv2.rectangle(canvas, (x1, y1), (x2, y2), rgb, 4)
    text = ascii_label(label)
    (width, height), _ = cv2.getTextSize(text, FONT, 0.8, 2)
    top = max(0, y1 - height - 14)
    cv2.rectangle(canvas, (x1, top), (x1 + width + 16, top + height + 14), rgb, -1)
    cv2.putText(canvas, text, (x1 + 8, top + height + 4), FONT, 0.8, (255, 255, 255), 2)
    return canvas


def draw_label(frame: np.ndarray, label: str, color: str) -> np.ndarray:
    """Écrit une étiquette dans le coin haut-gauche, quand aucun visage n'est délimité."""
    canvas = frame.copy()
    rgb = COLORS[color]
    text = ascii_label(label)
    (width, height), _ = cv2.getTextSize(text, FONT, 0.9, 2)
    cv2.rectangle(canvas, (10, 10), (10 + width + 20, 10 + height + 20), rgb, -1)
    cv2.putText(canvas, text, (20, 10 + height + 8), FONT, 0.9, (255, 255, 255), 2)
    return canvas


def throttled(state: dict, key: str) -> bool:
    """Vrai si le délai minimal est écoulé depuis le dernier traitement : limite la charge du CPU."""
    now = time.monotonic()
    if now - state[key] < PROCESS_INTERVAL:
        return False
    state[key] = now
    return True


def decide(history: deque, score: float, required: int) -> tuple[str | None, float]:
    """Lisse la décision sur la fenêtre : une personne doit être majoritaire pour être annoncée."""
    name, count = Counter(history).most_common(1)[0]
    if count >= required:
        return name, score
    return None, score


def new_realtime_state() -> dict:
    """État du temps réel : historique des décisions récentes et dernier affichage."""
    window = RecognitionConfig().window_size
    return {"last_t": 0.0, "last_frame": None, "last_status": "", "history": deque(maxlen=window)}


def realtime_stream(frame, state: dict | None):
    """Analyse le flux : détecte, identifie, lisse la décision, puis affiche le cadre et le statut."""
    state = state or new_realtime_state()
    if frame is None:
        return None, status_banner("idle", "CAMÉRA", "En attente du flux vidéo…"), state
    if not throttled(state, "last_t"):
        shown = state["last_frame"] if state["last_frame"] is not None else frame
        return shown, state["last_status"], state

    recognizer = get_recognizer()
    required = RecognitionConfig().required_matches
    faces = recognizer.detector.detect(frame)
    history: deque = state["history"]

    if not faces:
        history.clear()
        display = draw_label(frame, "AUCUN VISAGE", "grey")
        status = status_banner("idle", "AUCUN VISAGE", "Placez votre visage dans le champ de la caméra.")
    elif len(faces) > 1:
        history.clear()
        display = frame.copy()
        for face in faces:
            display = draw_box(display, face.bbox, "orange", "VISAGE")
        status = status_banner("warn", "PLUSIEURS VISAGES", "Une seule personne doit être visible.")
    else:
        face = faces[0]
        x1, y1, x2, y2 = face.bbox
        if min(x2 - x1, y2 - y1) < QualityConfig().min_face_px:
            history.clear()
            display = draw_box(frame, face.bbox, "grey", "TROP LOIN")
            status = status_banner("warn", "TROP LOIN", "Rapprochez-vous de la caméra.")
        else:
            vector = recognizer.embedder.embed(align_face(frame, face.landmarks))
            try:
                result = recognizer.identify_vector(vector)
            except ThresholdNotSetError as error:
                display = draw_box(frame, face.bbox, "grey", "SEUIL ?")
                status = status_banner("err", "CONFIGURATION", str(error))
            else:
                history.append(result.name or UNKNOWN)
                decided, score = decide(history, result.score or 0.0, required)
                if decided is None:
                    display = draw_box(frame, face.bbox, "yellow", "ANALYSE")
                    status = status_banner(
                        "analyse", "ANALYSE EN COURS",
                        f"Confirmation de l'identité : {len(history)}/{required} images.",
                    )
                elif decided == UNKNOWN:
                    display = draw_box(frame, face.bbox, "red", "INCONNU")
                    status = status_banner("err", "NON RECONNU", "Cette personne n'est pas dans la base.")
                else:
                    display = draw_box(frame, face.bbox, "green", f"{decided}  {score:.2f}")
                    status = status_banner("ok", "RECONNU", f"Bienvenue, {decided}.")

    state["last_frame"] = display
    state["last_status"] = status
    return display, status, state


def new_capture_state() -> dict:
    """État de la capture guidée pour l'enregistrement."""
    return {
        "last_t": 0.0, "last_frame": None, "last_status": "",
        "streak": 0, "best_score": 0.0, "best_frame": None, "locked": None,
    }


def capture_stream(frame, state: dict | None):
    """Guide la personne jusqu'à une photo stable, puis retient la meilleure image."""
    state = state or new_capture_state()
    if frame is None:
        return None, state["locked"], status_banner("idle", "CAMÉRA", "Autorisez la caméra et placez-vous face à l'objectif."), state
    if state["locked"] is not None:
        return state["last_frame"] if state["last_frame"] is not None else frame, state["locked"], \
            status_banner("ok", "PHOTO RETENUE", "Capture réussie. Vous pouvez enregistrer la personne."), state
    if not throttled(state, "last_t"):
        return state["last_frame"] if state["last_frame"] is not None else frame, None, state["last_status"], state

    recognizer = get_recognizer()
    faces = recognizer.detector.detect(frame)
    report: FrameReport = assess(frame, faces, QualityConfig())
    color = LEVEL_COLOR[report.level]
    if report.bbox is not None:
        display = draw_box(frame, report.bbox, color, report.short_label)
    else:
        display = draw_label(frame, report.short_label, color)

    if report.ok:
        state["streak"] += 1
        if report.quality_score > state["best_score"]:
            state["best_score"] = report.quality_score
            state["best_frame"] = frame.copy()
    else:
        state["streak"] = 0
        state["best_score"] = 0.0
        state["best_frame"] = None

    if state["streak"] >= STABLE_FRAMES and state["best_frame"] is not None:
        state["locked"] = state["best_frame"]
        status = status_banner("ok", "PHOTO RETENUE", "Capture réussie. Vous pouvez enregistrer la personne.")
    else:
        status = status_banner(
            LEVEL_KIND[report.level], report.short_label, report.message,
            progress=state["streak"] if report.ok else 0,
        )

    state["last_frame"] = display
    state["last_status"] = status
    return display, state["locked"], status, state


def reset_capture():
    """Recommence la capture guidée."""
    return new_capture_state(), None, status_banner("idle", "CAMÉRA", "Capture réinitialisée. Placez-vous face à l'objectif.")


def record(target: str, person: str, score: str, granted: bool) -> None:
    """Ajoute une tentative au journal, en gardant les JOURNAL_LIMIT dernières."""
    _journal.append({
        "heure": datetime.now().strftime("%H:%M:%S"),
        "cible": target,
        "personne": person,
        "score": score,
        "accorde": granted,
    })
    del _journal[:-JOURNAL_LIMIT]


def enroll_action(name: str, consent: bool, uploaded, state: dict | None):
    """Enregistre la photo retenue, ou importée, pour la personne donnée, après consentement."""
    people, dropdown = list_people()
    if not consent:
        return result_card(False, "Consentement requis", "Cochez la case avant d'enregistrer."), people, dropdown
    if not name or not name.strip():
        return result_card(False, "Nom manquant", "Saisissez le nom de la personne."), people, dropdown
    photo = uploaded if uploaded is not None else (state or {}).get("locked")
    if photo is None:
        return result_card(False, "Aucune photo", "Capturez le visage ou importez une image."), people, dropdown
    try:
        count = get_recognizer().enroll(name, photo)
    except RecognitionError as error:
        return result_card(False, "Photo refusée", str(error)), people, dropdown
    except ValueError as error:
        return result_card(False, "Nom refusé", str(error)), people, dropdown

    minimum = EnrollmentConfig().min_photos
    status = pill("Suffisant", "ok") if count >= minimum else pill(f"Minimum conseillé : {minimum}", "wait")
    body = f"Photos dans la base : <b>{count}</b> {status}"
    people, dropdown = list_people()
    return result_card(True, f"{name.strip()} enregistré(e)", body), people, dropdown


def list_people():
    """Tableau des personnes enregistrées, et liste de suppression."""
    database = get_recognizer().database
    names = database.names()
    rows = [(name, database.count(name)) for name in names]
    return people_table(rows), gr.update(choices=names, value=None)


def delete_action(name: str | None):
    """Supprime une personne et toutes ses données, puis rafraîchit la liste."""
    if not name:
        message = result_card(False, "Aucune sélection", "Choisissez une personne à supprimer.")
    else:
        try:
            get_recognizer().database.remove(name)
            message = result_card(True, f"{name} supprimé(e)", "Toutes ses données ont été effacées.")
        except KeyError:
            message = result_card(False, "Introuvable", f"Personne inconnue : {name}.")
    people, dropdown = list_people()
    return message, people, dropdown


def verify_action(photo, target: str):
    """Simule l'ouverture de la cible à partir d'une photo, et journalise la tentative."""
    if photo is None:
        message = "Capturez le visage ou importez une image."
        return result_card(False, "Aucune photo", message), access_screen(target, None, message), journal_table(_journal)

    try:
        result = get_recognizer().identify(photo)
    except RecognitionError as error:
        record(target, "—", "—", False)
        return (
            result_card(False, "Photo refusée", str(error)),
            access_screen(target, False, str(error)),
            journal_table(_journal),
        )
    except ThresholdNotSetError as error:
        return result_card(False, "Configuration", str(error)), access_screen(target, False, str(error)), journal_table(_journal)

    if not result.candidates:
        message = "La base est vide. Enregistrez d'abord une personne."
        return result_card(False, "Base vide", message), access_screen(target, False, message), journal_table(_journal)

    score = f"{result.score:.3f}"
    if result.recognized:
        message = f"Bienvenue, {result.name}."
        title = f"Reconnu : {result.name}"
        pill_html = pill("Reconnu", "ok")
    else:
        message = "Personne non reconnue."
        title = "Inconnu"
        pill_html = pill("Inconnu", "no")
    record(target, result.name or "inconnu", score, result.recognized)

    rows = "".join(
        f"<tr><td>{rank}</td><td>{c.name}</td><td>{c.score:.3f}</td></tr>"
        for rank, c in enumerate(result.candidates, start=1)
    )
    body = (
        f"Similarité la plus haute : <b>{score}</b> · seuil : {result.threshold:.4f}"
        "<br><br><table class='table'><tr><th>Rang</th><th>Personne</th><th>Similarité</th></tr>"
        f"{rows}</table>"
    )
    return (
        result_card(result.recognized, title, body, pill_html),
        access_screen(target, result.recognized, message),
        journal_table(_journal),
    )


def build_app() -> gr.Blocks:
    """Construit l'interface : temps réel, enregistrement avec gestion de la base, simulation d'accès."""
    rt_state = gr.State(new_realtime_state())
    enr_state = gr.State(new_capture_state())

    with gr.Blocks(title=TITLE) as demo:
        gr.HTML(f"<style>{CSS}</style>")
        gr.HTML(hero(TITLE, SUBTITLE))
        gr.HTML(notice(NOTICE))

        with gr.Tabs():
            with gr.Tab("Temps réel"):
                gr.HTML("<div class='card'><h3>Reconnaissance en direct</h3>"
                        "<div class='muted'>Le nom apparaît en vert quand la personne est reconnue, "
                        "INCONNU en rouge sinon. La décision est confirmée sur plusieurs images.</div></div>")
                with gr.Row(equal_height=False):
                    with gr.Column(scale=1):
                        rt_camera = gr.Image(sources=["webcam"], streaming=True, type="numpy",
                                             label="Caméra", height=280)
                    with gr.Column(scale=2):
                        rt_display = gr.Image(type="numpy", label="Analyse", height=400, interactive=False)
                        rt_status = gr.HTML(status_banner("idle", "CAMÉRA", "En attente du flux vidéo…"))
                rt_camera.stream(
                    fn=realtime_stream,
                    inputs=[rt_camera, rt_state],
                    outputs=[rt_display, rt_status, rt_state],
                    stream_every=0.5,
                )

            with gr.Tab("Enregistrement"):
                gr.HTML("<div class='card'><h3>Capturer le visage</h3>"
                        "<div class='muted'>Restez immobile : la meilleure image est retenue automatiquement.</div></div>")
                with gr.Row(equal_height=False):
                    with gr.Column(scale=1):
                        enr_camera = gr.Image(sources=["webcam"], streaming=True, type="numpy",
                                              label="Caméra", height=280)
                        enr_reset = gr.Button("Recommencer la capture", variant="secondary")
                    with gr.Column(scale=1):
                        enr_display = gr.Image(type="numpy", label="Guidage", height=280, interactive=False)
                        enr_preview = gr.Image(type="numpy", label="Photo retenue", height=200, interactive=False)
                        enr_status = gr.HTML(status_banner("idle", "CAMÉRA", "Autorisez la caméra pour commencer."))

                enr_camera.stream(
                    fn=capture_stream,
                    inputs=[enr_camera, enr_state],
                    outputs=[enr_display, enr_preview, enr_status, enr_state],
                    stream_every=0.5,
                )
                enr_reset.click(fn=reset_capture, outputs=[enr_state, enr_preview, enr_status])

                with gr.Row(equal_height=False):
                    with gr.Column(scale=1):
                        gr.HTML("<div class='card'><h3>Nouvelle personne</h3></div>")
                        name_input = gr.Textbox(label="Nom de la personne", max_lines=1)
                        consent_box = gr.Checkbox(label="La personne a consenti à cet enregistrement", value=False)
                        upload_enroll = gr.Image(type="numpy", sources=["upload"],
                                                 label="Ou importer une photo", height=160)
                        enroll_button = gr.Button("Enregistrer", variant="primary")
                    with gr.Column(scale=1):
                        enroll_output = gr.HTML()

                gr.HTML("<div class='card'><h3>Base de connaissance</h3></div>")
                people_output = gr.HTML()
                person_dropdown = gr.Dropdown(label="Personne à supprimer", choices=[], value=None)
                with gr.Row():
                    refresh_button = gr.Button("Actualiser", variant="secondary")
                    delete_button = gr.Button("Supprimer définitivement", variant="stop")
                delete_output = gr.HTML()

                enroll_button.click(
                    fn=enroll_action,
                    inputs=[name_input, consent_box, upload_enroll, enr_state],
                    outputs=[enroll_output, people_output, person_dropdown],
                )
                refresh_button.click(fn=list_people, outputs=[people_output, person_dropdown])
                delete_button.click(
                    fn=delete_action,
                    inputs=person_dropdown,
                    outputs=[delete_output, people_output, person_dropdown],
                )

            with gr.Tab("Simulation d'accès"):
                gr.HTML("<div class='card'><h3>Contrôle d'accès simulé</h3>"
                        "<div class='muted'>Aucun appareil réel n'est commandé. Le résultat illustre la décision.</div></div>")
                with gr.Row(equal_height=False):
                    with gr.Column(scale=1):
                        verify_photo = gr.Image(sources=["webcam", "upload"], type="numpy",
                                                label="Photo du visage", height=280)
                        target_input = gr.Radio(list(TARGETS), value="Téléphone", label="Appareil simulé")
                        verify_button = gr.Button("Vérifier et ouvrir", variant="primary")
                    with gr.Column(scale=1):
                        access_output = gr.HTML(access_screen("Téléphone", None, "Capturez un visage pour commencer."))
                        verify_output = gr.HTML()

                gr.HTML("<div class='card'><h3>Journal des tentatives</h3></div>")
                journal_output = gr.HTML(journal_table(_journal))
                verify_button.click(
                    fn=verify_action,
                    inputs=[verify_photo, target_input],
                    outputs=[verify_output, access_output, journal_output],
                )

        gr.HTML("<div class='footer'>Traitement local · Aucune photo conservée · Projet académique</div>")
    return demo


if __name__ == "__main__":
    build_app().launch(server_name="127.0.0.1", server_port=7860)