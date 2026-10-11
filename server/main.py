"""API FastAPI : pont entre l'interface React et le moteur de reconnaissance Python."""

from __future__ import annotations

import io
from collections import deque
from datetime import datetime
from typing import Any

import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, ImageOps
from starlette.concurrency import run_in_threadpool

from src.config import EnrollmentConfig, QualityConfig, RecognitionConfig
from src.database import Database
from src.detect import align_face
from src.quality import FrameReport, assess
from src.recognize import RecognitionError, Recognizer, ThresholdNotSetError

ALLOWED_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
JOURNAL_LIMIT: int = 50

app = FastAPI(title="Reconnaissance faciale", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

_recognizer: Recognizer | None = None
_journal: deque[dict[str, Any]] = deque(maxlen=JOURNAL_LIMIT)


def get_recognizer() -> Recognizer:
    global _recognizer
    if _recognizer is None:
        _recognizer = Recognizer(Database(), RecognitionConfig())
    return _recognizer


def decode_image(data: bytes) -> np.ndarray:
    try:
        with Image.open(io.BytesIO(data)) as img:
            img = ImageOps.exif_transpose(img)
            return np.asarray(img.convert("RGB"), dtype=np.uint8).copy()
    except Exception as error:
        raise HTTPException(status_code=400, detail="Image illisible.") from error


def serialize_report(report: FrameReport) -> dict[str, Any]:
    return {
        "level": report.level,
        "message": report.message,
        "label": report.short_label,
        "ok": report.ok,
        "score": round(report.quality_score, 4),
        "bbox": [int(v) for v in report.bbox] if report.bbox is not None else None,
        "min_face_px": QualityConfig().min_face_px,
    }


def serialize_identity(result) -> dict[str, Any]:
    return {
        "name": result.name,
        "recognized": result.recognized,
        "score": round(result.score, 4) if result.score is not None else None,
        "threshold": result.threshold,
        "candidates": [{"name": c.name, "score": round(c.score, 4)} for c in result.candidates],
    }


def analyze_image(image: np.ndarray) -> dict[str, Any]:
    recognizer = get_recognizer()
    faces = recognizer.detector.detect(image)
    report = assess(image, faces, QualityConfig())

    identity = None
    if len(faces) == 1:
        x1, y1, x2, y2 = faces[0].bbox
        if min(x2 - x1, y2 - y1) >= QualityConfig().min_face_px:
            vector = recognizer.embedder.embed(align_face(image, faces[0].landmarks))
            try:
                identity = serialize_identity(recognizer.identify_vector(vector))
            except ThresholdNotSetError as error:
                identity = {"error": str(error)}

    return {
        "width": int(image.shape[1]),
        "height": int(image.shape[0]),
        "faces": [
            {"bbox": [round(float(v), 1) for v in face.bbox], "score": round(face.score, 4)}
            for face in faces
        ],
        "quality": serialize_report(report),
        "identity": identity,
    }


def enroll_image(name: str, image: np.ndarray) -> int:
    return get_recognizer().enroll(name, image)


def verify_image(image: np.ndarray):
    return get_recognizer().identify(image)


def _entry(target: str, person: str, score: float | None, granted: bool) -> dict[str, Any]:
    return {
        "time": datetime.now().strftime("%H:%M:%S"),
        "target": target,
        "person": person,
        "score": round(score, 4) if score is not None else None,
        "granted": granted,
    }


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "threshold": RecognitionConfig().threshold}


@app.post("/api/analyze")
async def analyze(file: UploadFile = File(...)) -> dict[str, Any]:
    data = await file.read()
    return await run_in_threadpool(lambda: analyze_image(decode_image(data)))


@app.post("/api/enroll")
async def enroll(
    name: str = Form(...),
    consent: bool = Form(...),
    file: UploadFile = File(...),
) -> dict[str, Any]:
    if not consent:
        raise HTTPException(status_code=400, detail="Le consentement est obligatoire.")
    data = await file.read()
    image = await run_in_threadpool(decode_image, data)
    try:
        count = await run_in_threadpool(enroll_image, name, image)
    except (RecognitionError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    minimum = EnrollmentConfig().min_photos
    return {
        "name": name.strip(),
        "count": count,
        "minimum": minimum,
        "sufficient": count >= minimum,
    }


@app.get("/api/people")
def list_people() -> list[dict[str, Any]]:
    database = get_recognizer().database
    return [{"name": name, "count": database.count(name)} for name in database.names()]


@app.delete("/api/people/{name}")
def delete_person(name: str) -> dict[str, Any]:
    try:
        get_recognizer().database.remove(name)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=f"Personne inconnue : {name}") from error
    return {"deleted": name}


@app.post("/api/verify")
async def verify(file: UploadFile = File(...), target: str = Form("Téléphone")) -> dict[str, Any]:
    data = await file.read()
    image = await run_in_threadpool(decode_image, data)
    try:
        result = await run_in_threadpool(verify_image, image)
    except RecognitionError as error:
        _journal.appendleft(_entry(target, "—", None, False))
        raise HTTPException(status_code=422, detail=str(error)) from error
    except ThresholdNotSetError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error

    if not result.candidates:
        raise HTTPException(status_code=409, detail="La base est vide.")

    _journal.appendleft(_entry(target, result.name or "inconnu", result.score, result.recognized))
    return {"target": target, "granted": result.recognized, "identity": serialize_identity(result)}


@app.get("/api/journal")
def journal() -> list[dict[str, Any]]:
    return list(_journal)