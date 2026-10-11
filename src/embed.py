"""Calcul de l'embedding : vecteur normalisé de 512 valeurs par visage, avec ResNet-50 ArcFace pré-entraîné."""

from __future__ import annotations

import logging
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort

from src.config import ROOT_DIR, EmbeddingConfig

logger = logging.getLogger(__name__)

DEFAULT_WEIGHTS: Path = ROOT_DIR / "models" / "w600k_r50.onnx"
MEAN: float = 127.5
SCALE: float = 127.5


def l2_normalize(vector: np.ndarray) -> np.ndarray:
    """Ramène un vecteur à une longueur de 1, pour que le produit scalaire soit une similarité cosinus."""
    norm = np.linalg.norm(vector)
    if norm == 0:
        raise ValueError("Impossible de normaliser un vecteur nul")
    return vector / norm


class FaceEmbedder:
    """Charge le réseau une seule fois et transforme un visage recadré en vecteur normalisé."""

    def __init__(self, cfg: EmbeddingConfig, providers: list[str] | None = None) -> None:
        weights = cfg.weights_path or DEFAULT_WEIGHTS
        if not weights.is_file():
            raise FileNotFoundError(
                f"Poids introuvables : {weights}. Téléchargez w600k_r50.onnx depuis l'archive buffalo_l "
                "d'InsightFace et placez-le dans le dossier models/."
            )

        available = ort.get_available_providers()
        if providers is None:
            providers = [p for p in ("CUDAExecutionProvider", "CPUExecutionProvider") if p in available]
        self.session = ort.InferenceSession(str(weights), providers=providers)
        self.active_provider = self.session.get_providers()[0]
        self.input_name = self.session.get_inputs()[0].name
        self.input_size = cfg.input_size
        self.embedding_dim = cfg.embedding_dim
        logger.info("Embedder chargé depuis %s (appareil : %s)", weights.name, self.active_provider)

    def preprocess(self, face_rgb: np.ndarray) -> np.ndarray:
        """Redimensionne le visage, normalise les valeurs entre -1 et 1, et met au format NCHW."""
        if face_rgb.ndim != 3 or face_rgb.shape[2] != 3:
            raise ValueError(f"Un visage RGB est attendu, reçu une forme {face_rgb.shape}")
        resized = cv2.resize(face_rgb, (self.input_size, self.input_size), interpolation=cv2.INTER_LINEAR)
        normalized = (resized.astype(np.float32) - MEAN) / SCALE
        return np.transpose(normalized, (2, 0, 1))[np.newaxis, ...]

    def embed(self, face_rgb: np.ndarray) -> np.ndarray:
        """Retourne le vecteur normalisé de 512 valeurs pour un visage recadré en RGB."""
        output = self.session.run(None, {self.input_name: self.preprocess(face_rgb)})[0]
        vector = output[0].astype(np.float32)
        if vector.shape[0] != self.embedding_dim:
            raise ValueError(f"Dimension inattendue : {vector.shape[0]}, attendue {self.embedding_dim}")
        return l2_normalize(vector)