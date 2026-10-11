"""Détection des visages (SCRFD, ONNX) et alignement vers le gabarit ArcFace 112 × 112."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort

from src.config import ROOT_DIR, DetectionConfig

logger = logging.getLogger(__name__)

DEFAULT_WEIGHTS: Path = ROOT_DIR / "models" / "det_10g.onnx"
INPUT_SIZE: int = 640
STRIDES: tuple[int, ...] = (8, 16, 32)
NUM_ANCHORS: int = 2
NMS_THRESHOLD: float = 0.4
ARCFACE_TEMPLATE_112: np.ndarray = np.array(
    [
        [38.2946, 51.6963],
        [73.5318, 51.5014],
        [56.0252, 71.7366],
        [41.5493, 92.3655],
        [70.7299, 92.2041],
    ],
    dtype=np.float32,
)


@dataclass(frozen=True)
class Detection:
    """Un visage détecté dans l'image d'origine."""

    bbox: np.ndarray
    landmarks: np.ndarray
    score: float


@dataclass(frozen=True)
class AlignedFace:
    """Un visage aligné, prêt pour l'embedding, avec sa détection d'origine."""

    image: np.ndarray
    detection: Detection


def align_face(image_rgb: np.ndarray, landmarks: np.ndarray, out_size: int = 112) -> np.ndarray:
    """Aligne le visage sur le gabarit ArcFace à l'aide d'une transformation de similarité."""
    if landmarks.shape != (5, 2):
        raise ValueError(f"5 points de repère attendus, reçu une forme {landmarks.shape}")
    template = ARCFACE_TEMPLATE_112 * (out_size / 112.0)
    matrix, _ = cv2.estimateAffinePartial2D(landmarks.astype(np.float32), template, method=cv2.LMEDS)
    if matrix is None:
        raise ValueError("Alignement impossible : repères trop dégénérés")
    return cv2.warpAffine(image_rgb, matrix, (out_size, out_size), borderValue=0.0)


def _nms(boxes: np.ndarray, scores: np.ndarray, threshold: float) -> np.ndarray:
    """Suppression des boîtes qui se chevauchent : garde la plus confiante de chaque groupe."""
    x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
    areas = (x2 - x1 + 1) * (y2 - y1 + 1)
    order = scores.argsort()[::-1]
    keep: list[int] = []
    while order.size > 0:
        i = order[0]
        keep.append(i)
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        inter = np.maximum(0.0, xx2 - xx1 + 1) * np.maximum(0.0, yy2 - yy1 + 1)
        iou = inter / (areas[i] + areas[order[1:]] - inter)
        order = order[1:][iou <= threshold]
    return np.array(keep, dtype=np.int64)


class FaceDetector:
    """Charge SCRFD une seule fois, puis détecte les visages dans une image RGB."""

    def __init__(
        self,
        cfg: DetectionConfig,
        weights: Path | None = None,
        providers: list[str] | None = None,
    ) -> None:
        weights = weights or DEFAULT_WEIGHTS
        if not weights.is_file():
            raise FileNotFoundError(
                f"Poids introuvables : {weights}. Placez det_10g.onnx (archive buffalo_l) dans models/."
            )
        available = ort.get_available_providers()
        if providers is None:
            providers = [p for p in ("CUDAExecutionProvider", "CPUExecutionProvider") if p in available]
        self.session = ort.InferenceSession(str(weights), providers=providers)
        self.active_provider = self.session.get_providers()[0]
        self.input_name = self.session.get_inputs()[0].name
        self.threshold = cfg.min_confidence
        self.centers = {stride: self._anchor_centers(stride) for stride in STRIDES}
        logger.info("Détecteur SCRFD chargé (appareil : %s)", self.active_provider)

    @staticmethod
    def _anchor_centers(stride: int) -> np.ndarray:
        """Centres des ancres pour une résolution de feature map donnée."""
        size = INPUT_SIZE // stride
        xs, ys = np.meshgrid(np.arange(size), np.arange(size))
        centers = np.stack([xs, ys], axis=-1).reshape(-1, 2).astype(np.float32) * stride
        return np.repeat(centers, NUM_ANCHORS, axis=0)

    def _preprocess(self, image_rgb: np.ndarray) -> tuple[np.ndarray, float]:
        """Met l'image à l'échelle 640 avec marge, puis la normalise au format NCHW."""
        h, w = image_rgb.shape[:2]
        scale = INPUT_SIZE / max(h, w)
        resized = cv2.resize(image_rgb, (int(round(w * scale)), int(round(h * scale))))
        canvas = np.zeros((INPUT_SIZE, INPUT_SIZE, 3), dtype=np.uint8)
        canvas[: resized.shape[0], : resized.shape[1]] = resized
        blob = (canvas.astype(np.float32) - 127.5) / 128.0
        return blob.transpose(2, 0, 1)[np.newaxis, ...], scale

    def detect(self, image_rgb: np.ndarray) -> list[Detection]:
        """Retourne les visages détectés, triés par confiance décroissante, en coordonnées de l'image d'origine."""
        blob, scale = self._preprocess(image_rgb)
        outputs = self.session.run(None, {self.input_name: blob})

        boxes, scores, landmarks = [], [], []
        for idx, stride in enumerate(STRIDES):
            score = outputs[idx].reshape(-1)
            distances = outputs[idx + len(STRIDES)].reshape(-1, 4) * stride
            points = outputs[idx + 2 * len(STRIDES)].reshape(-1, 10) * stride
            centers = self.centers[stride]

            keep = score >= self.threshold
            if not keep.any():
                continue
            c, d, p, s = centers[keep], distances[keep], points[keep], score[keep]
            boxes.append(np.stack([c[:, 0] - d[:, 0], c[:, 1] - d[:, 1],
                                   c[:, 0] + d[:, 2], c[:, 1] + d[:, 3]], axis=1))
            landmarks.append(p.reshape(-1, 5, 2) + c[:, np.newaxis, :])
            scores.append(s)

        if not scores:
            return []

        boxes = np.concatenate(boxes) / scale
        landmarks = np.concatenate(landmarks) / scale
        scores = np.concatenate(scores)

        kept = _nms(boxes, scores, NMS_THRESHOLD)
        return [
            Detection(bbox=boxes[i].astype(np.float32),
                      landmarks=landmarks[i].astype(np.float32),
                      score=float(scores[i]))
            for i in kept
        ]

    def extract_aligned(self, image_rgb: np.ndarray) -> list[AlignedFace]:
        """Détecte les visages et retourne chacun aligné en 112 × 112."""
        return [
            AlignedFace(image=align_face(image_rgb, det.landmarks), detection=det)
            for det in self.detect(image_rgb)
        ]