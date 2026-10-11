"""Contrôle qualité d'une image de capture : nombre de visages, taille, centrage, lumière, netteté."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from src.config import QualityConfig
from src.detect import Detection

ENROLL_MIN_PX: int = 120
CENTER_TOLERANCE: float = 0.2
BRIGHTNESS_LOW: float = 60.0
BRIGHTNESS_HIGH: float = 200.0
MIN_DETECTION_SCORE: float = 0.8
SHARPNESS_REFERENCE: float = 300.0
STABLE_FRAMES: int = 5


@dataclass(frozen=True)
class FrameReport:
    """Verdict sur une image : niveau, message à l'utilisateur, zone du visage et score de qualité."""

    level: str
    message: str
    short_label: str
    bbox: tuple[int, int, int, int] | None
    quality_score: float

    @property
    def ok(self) -> bool:
        """Vrai si l'image peut servir à une capture."""
        return self.level == "ok"


def sharpness(image_rgb: np.ndarray) -> float:
    """Netteté mesurée par la variance du filtre Laplacien : plus elle est haute, plus l'image est nette."""
    gray = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def brightness(image_rgb: np.ndarray) -> float:
    """Luminosité moyenne, de 0 (noir) à 255 (blanc)."""
    gray = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2GRAY)
    return float(gray.mean())


def assess(image_rgb: np.ndarray, faces: list[Detection], quality: QualityConfig) -> FrameReport:
    """Juge une image et retourne le premier problème rencontré, ou un feu vert si tout est bon."""
    if not faces:
        return FrameReport("error", "Aucun visage : placez-vous face à la caméra.", "AUCUN VISAGE", None, 0.0)
    if len(faces) > 1:
        return FrameReport(
            "error", f"{len(faces)} visages détectés : une seule personne doit être visible.",
            "PLUSIEURS", None, 0.0,
        )

    face = max(faces, key=lambda d: d.score)
    x1, y1, x2, y2 = (int(v) for v in face.bbox)
    bbox = (x1, y1, x2, y2)
    height, width = image_rgb.shape[:2]
    size = min(x2 - x1, y2 - y1)

    center_x, center_y = (x1 + x2) / 2, (y1 + y2) / 2
    centered = (
        abs(center_x - width / 2) <= CENTER_TOLERANCE * width
        and abs(center_y - height / 2) <= CENTER_TOLERANCE * height
    )
    center_factor = 1.0 if centered else 0.5
    light = brightness(image_rgb)
    sharp = sharpness(image_rgb)
    quality_score = face.score * min(sharp / SHARPNESS_REFERENCE, 1.0) * center_factor

    if size < quality.min_face_px:
        return FrameReport("error", "Visage trop loin : rapprochez-vous.", "PLUS PRES", bbox, 0.0)
    if size < ENROLL_MIN_PX:
        return FrameReport("warning", "Encore un peu loin : rapprochez-vous.", "PLUS PRES", bbox, quality_score)
    if not centered:
        return FrameReport("warning", "Centrez votre visage dans le cadre.", "CENTREZ", bbox, quality_score)
    if light < BRIGHTNESS_LOW:
        return FrameReport("warning", "Trop sombre : ajoutez de la lumière.", "SOMBRE", bbox, quality_score)
    if light > BRIGHTNESS_HIGH:
        return FrameReport("warning", "Trop lumineux : éloignez-vous de la source de lumière.", "TROP CLAIR", bbox, quality_score)
    if sharp < quality.min_sharpness:
        return FrameReport("warning", "Image floue : restez immobile.", "FLOU", bbox, quality_score)
    if face.score < MIN_DETECTION_SCORE:
        return FrameReport("warning", "Visage partiellement visible : découvrez votre visage.", "PARTIEL", bbox, quality_score)
    return FrameReport("ok", "Parfait : restez immobile.", "OK", bbox, quality_score)