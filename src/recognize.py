"""Reconnaissance : image vers vecteur (avec contrôles), comparaison à la base, décision au seuil."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np

from src.config import DetectionConfig, EmbeddingConfig, QualityConfig, RecognitionConfig
from src.database import Database
from src.detect import FaceDetector, align_face
from src.embed import FaceEmbedder

logger = logging.getLogger(__name__)

TOP_CANDIDATES: int = 3


class RecognitionError(ValueError):
    """Image non exploitable : le message est destiné à l'utilisateur."""


class NoFaceError(RecognitionError):
    """Aucun visage n'a été détecté."""


class MultipleFacesError(RecognitionError):
    """Plusieurs visages ont été détectés : la photo doit montrer une seule personne."""


class FaceTooSmallError(RecognitionError):
    """Le visage est trop petit pour une reconnaissance fiable."""


class ThresholdNotSetError(RuntimeError):
    """Le seuil de décision n'est pas défini : aucune décision n'est prise."""


@dataclass(frozen=True)
class Candidate:
    """Une personne de la base, avec sa meilleure similarité."""

    name: str
    score: float


@dataclass(frozen=True)
class Identification:
    """Résultat d'une reconnaissance."""

    name: str | None
    score: float | None
    threshold: float
    candidates: list[Candidate] = field(default_factory=list)

    @property
    def recognized(self) -> bool:
        """Vrai si la personne est reconnue au seuil."""
        return self.name is not None


class Recognizer:
    """Regroupe détection, embedding, base et décision. À créer une seule fois, puis réutiliser."""

    def __init__(
        self,
        database: Database,
        recognition: RecognitionConfig,
        detection: DetectionConfig = DetectionConfig(),
        quality: QualityConfig = QualityConfig(),
        embedding: EmbeddingConfig = EmbeddingConfig(),
    ) -> None:
        self.database = database
        self.recognition = recognition
        self.quality = quality
        self.detector = FaceDetector(detection)
        self.embedder = FaceEmbedder(embedding)

    def vector_from_image(self, image_rgb: np.ndarray) -> np.ndarray:
        """Transforme une photo en vecteur, après avoir vérifié qu'elle contient un visage exploitable."""
        faces = self.detector.detect(image_rgb)
        if not faces:
            raise NoFaceError("Aucun visage détecté. Essayez une photo plus nette, bien éclairée, de face.")
        if len(faces) > 1:
            raise MultipleFacesError(
                f"{len(faces)} visages détectés. Envoyez une photo où une seule personne est visible."
            )

        face = faces[0]
        x1, y1, x2, y2 = face.bbox
        size = min(x2 - x1, y2 - y1)
        if size < self.quality.min_face_px:
            raise FaceTooSmallError(
                f"Visage trop petit ({size:.0f} px). Rapprochez-vous de la caméra "
                f"(minimum {self.quality.min_face_px} px)."
            )

        aligned = align_face(image_rgb, face.landmarks)
        return self.embedder.embed(aligned)

    def enroll(self, name: str, image_rgb: np.ndarray) -> int:
        """Ajoute le visage de la photo à la personne donnée, et retourne le nombre de vecteurs enregistrés."""
        vector = self.vector_from_image(image_rgb)
        return self.database.add(name, vector)

    def identify(self, image_rgb: np.ndarray) -> Identification:
        """Identifie la personne de la photo parmi la base, ou retourne inconnu."""
        return self.identify_vector(self.vector_from_image(image_rgb))

    def identify_vector(self, vector: np.ndarray) -> Identification:
        """Compare un vecteur à toute la base : meilleure similarité par personne, puis décision au seuil."""
        threshold = self.recognition.threshold
        if threshold is None:
            raise ThresholdNotSetError("Seuil non défini : fixez RecognitionConfig.threshold avant de reconnaître.")

        labels, matrix = self.database.all_vectors()
        if matrix.shape[0] == 0:
            return Identification(name=None, score=None, threshold=threshold, candidates=[])

        similarities = matrix @ vector.astype(np.float32)
        best_per_person: dict[str, float] = {}
        for label, similarity in zip(labels, similarities):
            value = float(similarity)
            if label not in best_per_person or value > best_per_person[label]:
                best_per_person[label] = value

        ranked = sorted(best_per_person.items(), key=lambda item: item[1], reverse=True)
        candidates = [Candidate(name=name, score=score) for name, score in ranked[:TOP_CANDIDATES]]
        top_name, top_score = ranked[0]
        decided = top_name if top_score >= threshold else None
        logger.info("Décision : %s (similarité %.4f, seuil %.4f)", decided or "inconnu", top_score, threshold)
        return Identification(name=decided, score=top_score, threshold=threshold, candidates=candidates)