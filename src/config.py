"""Configuration centralisée du projet de reconnaissance faciale."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

ROOT_DIR: Path = Path(__file__).resolve().parents[1]
DATA_DIR: Path = ROOT_DIR / "data"
DATABASE_PATH: Path = ROOT_DIR / "database" / "visages.json"
OUTPUT_DIR: Path = ROOT_DIR / "outputs"


@dataclass(frozen=True)
class SourceConfig:
    """Paramètres de la source d'images."""

    camera_index: int = 0
    sample_every: int = 5
    max_frames: int = 10_000

    def __post_init__(self) -> None:
        if self.sample_every < 1:
            raise ValueError(f"sample_every doit être au moins 1, reçu {self.sample_every}")
        if self.max_frames < 1:
            raise ValueError(f"max_frames doit être positif, reçu {self.max_frames}")


@dataclass(frozen=True)
class DetectionConfig:
    """Paramètres de détection du visage."""

    min_confidence: float = 0.5
    crop_margin: float = 0.2

    def __post_init__(self) -> None:
        if not 0.0 < self.min_confidence <= 1.0:
            raise ValueError(f"min_confidence doit être dans ]0, 1], reçu {self.min_confidence}")
        if not 0.0 <= self.crop_margin < 1.0:
            raise ValueError(f"crop_margin doit être dans [0, 1[, reçu {self.crop_margin}")


@dataclass(frozen=True)
class QualityConfig:
    """Critères de rejet des visages de mauvaise qualité."""

    min_face_px: int = 80
    min_sharpness: float = 30.0

    def __post_init__(self) -> None:
        if self.min_face_px < 32:
            raise ValueError(f"min_face_px doit être au moins 32, reçu {self.min_face_px}")
        if self.min_sharpness < 0:
            raise ValueError(f"min_sharpness doit être positif, reçu {self.min_sharpness}")


@dataclass(frozen=True)
class EmbeddingConfig:
    """Paramètres du réseau qui produit les vecteurs de visage."""

    backbone: str = "resnet50"
    input_size: int = 112
    embedding_dim: int = 512
    weights_path: Path | None = None

    def __post_init__(self) -> None:
        if self.backbone not in {"resnet18", "resnet50"}:
            raise ValueError(f"backbone non supporté : {self.backbone}")
        if self.input_size not in {112, 160, 224}:
            raise ValueError(f"input_size inattendu : {self.input_size}")
        if self.embedding_dim < 16:
            raise ValueError(f"embedding_dim trop petit : {self.embedding_dim}")


@dataclass(frozen=True)
class EnrollmentConfig:
    """Règles d'enregistrement d'une personne dans la base."""

    min_photos: int = 3
    recommended_photos: int = 8

    def __post_init__(self) -> None:
        if self.min_photos < 1:
            raise ValueError(f"min_photos doit être au moins 1, reçu {self.min_photos}")
        if self.recommended_photos < self.min_photos:
            raise ValueError("recommended_photos ne peut pas être inférieur à min_photos")


@dataclass(frozen=True)
class RecognitionConfig:
    """Règles de décision lors de la reconnaissance."""

    threshold: float | None = 0.2626
    window_size: int = 5
    required_matches: int = 3

    def __post_init__(self) -> None:
        if self.threshold is not None and not -1.0 <= self.threshold <= 1.0:
            raise ValueError(f"threshold doit être une similarité cosinus dans [-1, 1], reçu {self.threshold}")
        if self.required_matches > self.window_size:
            raise ValueError("required_matches ne peut pas dépasser window_size")
        if self.required_matches < 1:
            raise ValueError(f"required_matches doit être au moins 1, reçu {self.required_matches}")


@dataclass(frozen=True)
class AppConfig:
    """Regroupe toutes les configurations du projet."""

    source: SourceConfig = field(default_factory=SourceConfig)
    detection: DetectionConfig = field(default_factory=DetectionConfig)
    quality: QualityConfig = field(default_factory=QualityConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    enrollment: EnrollmentConfig = field(default_factory=EnrollmentConfig)
    recognition: RecognitionConfig = field(default_factory=RecognitionConfig)
    seed: int = 42