"""Calcul des embeddings de toutes les photos de validation et de test, enregistrés une seule fois."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np

from src.config import DATA_DIR, DetectionConfig, EmbeddingConfig
from src.detect import FaceDetector
from src.embed import FaceEmbedder
from src.source import load_image_file
from src.splits import LFW_ROOT, list_photos, load_splits

logger = logging.getLogger(__name__)

EMBEDDINGS_PATH: Path = DATA_DIR / "embeddings.npz"
FAILURES_PATH: Path = DATA_DIR / "embeddings_echecs.json"
EVALUATED_SPLITS: tuple[str, ...] = ("validation", "test")
LOG_EVERY: int = 200


def collect_items(persons_by_split: dict[str, dict[str, int]]) -> list[tuple[str, str, str]]:
    """Liste toutes les photos, sous la forme (chemin relatif, personne, ensemble)."""
    items: list[tuple[str, str, str]] = []
    for split, persons in persons_by_split.items():
        for name in sorted(persons):
            for photo in list_photos(LFW_ROOT / name):
                items.append((f"{name}/{photo}", name, split))
    return items


def embed_photo(
    path: Path, detector: FaceDetector, embedder: FaceEmbedder
) -> tuple[np.ndarray, float] | None:
    """Retourne l'embedding du visage le plus confiant de la photo, ou None si aucun visage n'est trouvé."""
    image = load_image_file(path)
    faces = detector.extract_aligned(image)
    if not faces:
        return None
    best = max(faces, key=lambda face: face.detection.score)
    return embedder.embed(best.image), best.detection.score


def run(force: bool = False) -> dict:
    """Calcule les embeddings, les enregistre, et liste les photos où aucun visage n'a été trouvé."""
    if EMBEDDINGS_PATH.is_file() and not force:
        logger.info("Embeddings déjà calculés : %s (utilisez force=True pour recalculer)", EMBEDDINGS_PATH)
        data = np.load(EMBEDDINGS_PATH)
        return {key: data[key] for key in data.files}

    splits = load_splits()["personnes"]
    items = collect_items({key: splits[key] for key in EVALUATED_SPLITS})
    logger.info("Photos à traiter : %d", len(items))

    detector = FaceDetector(DetectionConfig())
    embedder = FaceEmbedder(EmbeddingConfig())

    vectors, photos, persons, split_names, scores, failures = [], [], [], [], [], []
    for index, (relpath, person, split) in enumerate(items, start=1):
        result = embed_photo(LFW_ROOT / relpath, detector, embedder)
        if result is None:
            failures.append({"photo": relpath, "ensemble": split})
        else:
            vector, score = result
            vectors.append(vector)
            photos.append(relpath)
            persons.append(person)
            split_names.append(split)
            scores.append(score)
        if index % LOG_EVERY == 0:
            logger.info("Traité %d / %d photos", index, len(items))

    if not vectors:
        raise RuntimeError("Aucun visage détecté : vérifiez le détecteur et les photos")

    arrays = {
        "vectors": np.stack(vectors).astype(np.float32),
        "photos": np.array(photos),
        "persons": np.array(persons),
        "splits": np.array(split_names),
        "scores": np.array(scores, dtype=np.float32),
    }
    EMBEDDINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(EMBEDDINGS_PATH, **arrays)
    with FAILURES_PATH.open("w", encoding="utf-8") as f:
        json.dump(failures, f, indent=2, ensure_ascii=False)

    for split in EVALUATED_SPLITS:
        total = sum(1 for s in split_names if s == split)
        failed = sum(1 for item in failures if item["ensemble"] == split)
        logger.info("%s : %d embeddings, %d photos sans visage", split, total, failed)
    logger.info("Embeddings enregistrés dans %s", EMBEDDINGS_PATH)
    return arrays


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    run()