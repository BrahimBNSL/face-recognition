"""Protocole officiel LFW : 10 folds, seuil appris sur 9 folds, accuracy sur le fold restant."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np

from src.config import DATA_DIR, DetectionConfig, EmbeddingConfig, OUTPUT_DIR
from src.detect import FaceDetector
from src.embed import FaceEmbedder
from src.extract_embeddings import embed_photo
from src.splits import LFW_ROOT

logger = logging.getLogger(__name__)

OFFICIAL_PAIRS_PATH: Path = DATA_DIR / "lfw" / "pairs.csv"
CACHE_PATH: Path = DATA_DIR / "lfw_protocol_embeddings.npz"
RESULTS_PATH: Path = OUTPUT_DIR / "metrics" / "lfw_protocol.json"
SAVE_EVERY: int = 1000


def photo_path(name: str, index: int) -> str:
    """Chemin relatif d'une photo LFW, à partir du nom de la personne et de son index."""
    return f"{name}/{name}_{index:04d}.jpg"


def parse_pairs(path: Path, per_class_per_fold: int = 300, folds_count: int = 10) -> list[list[tuple[str, str, int]]]:
    """Lit pairs.csv : une ligne d'en-tête, puis les paires positives (3 champs) et négatives (4 champs).

    Les paires sont réparties en folds consécutifs de per_class_per_fold positives et autant de négatives.
    Une vérification stricte des effectifs évite de produire des folds faux sans le signaler.
    """
    if not path.is_file():
        raise FileNotFoundError(f"Fichier officiel introuvable : {path}")

    lines = path.read_text(encoding="utf-8").splitlines()[1:]
    positives: list[tuple[str, str, int]] = []
    negatives: list[tuple[str, str, int]] = []
    for line in lines:
        if not line.strip():
            continue
        parts = line.rstrip(",").split(",")
        if len(parts) == 3:
            name, i, j = parts
            positives.append((photo_path(name, int(i)), photo_path(name, int(j)), 1))
        elif len(parts) == 4:
            name_a, i, name_b, j = parts
            negatives.append((photo_path(name_a, int(i)), photo_path(name_b, int(j)), 0))
        else:
            raise ValueError(f"Ligne inattendue dans pairs.csv : {line!r}")

    expected = per_class_per_fold * folds_count
    if len(positives) != expected or len(negatives) != expected:
        raise ValueError(
            f"Effectifs inattendus : {len(positives)} positives et {len(negatives)} négatives, "
            f"attendu {expected} de chaque"
        )

    folds: list[list[tuple[str, str, int]]] = []
    for k in range(folds_count):
        start_k = k * per_class_per_fold
        stop_k = start_k + per_class_per_fold
        folds.append(positives[start_k:stop_k] + negatives[start_k:stop_k])
    logger.info("pairs.csv lu : %d folds de %d paires", folds_count, 2 * per_class_per_fold)
    return folds


def load_cache(path: Path) -> dict[str, np.ndarray]:
    """Charge les embeddings déjà calculés, pour ne pas recalculer après une interruption."""
    if not path.is_file():
        return {}
    data = np.load(path)
    return dict(zip(data["photos"].tolist(), data["vectors"]))


def save_cache(cache: dict[str, np.ndarray], path: Path) -> None:
    """Enregistre les embeddings calculés."""
    path.parent.mkdir(parents=True, exist_ok=True)
    photos = np.array(list(cache.keys()))
    vectors = np.stack(list(cache.values())).astype(np.float32) if cache else np.zeros((0, 512), np.float32)
    np.savez_compressed(path, photos=photos, vectors=vectors)


def compute_embeddings(photos: list[str], cache: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """Calcule les embeddings des photos absentes du cache, en sauvegardant régulièrement."""
    missing = [p for p in photos if p not in cache]
    logger.info("Photos totales : %d, déjà en cache : %d, à calculer : %d", len(photos), len(photos) - len(missing), len(missing))
    if not missing:
        return cache

    detector = FaceDetector(DetectionConfig())
    embedder = FaceEmbedder(EmbeddingConfig())
    failures = 0
    for count, relpath in enumerate(missing, start=1):
        result = embed_photo(LFW_ROOT / relpath, detector, embedder)
        if result is None:
            failures += 1
        else:
            cache[relpath] = result[0]
        if count % SAVE_EVERY == 0:
            save_cache(cache, CACHE_PATH)
            logger.info("Progression : %d / %d (sauvegardé)", count, len(missing))
    save_cache(cache, CACHE_PATH)
    logger.info("Photos sans visage détecté : %d", failures)
    return cache


def score_fold(fold: list[tuple[str, str, int]], cache: dict[str, np.ndarray]) -> tuple[np.ndarray, np.ndarray, int]:
    """Calcule les similarités d'un fold ; les paires dont une photo n'a pas de visage sont écartées."""
    scores, labels, skipped = [], [], 0
    for a, b, label in fold:
        if a not in cache or b not in cache:
            skipped += 1
            continue
        scores.append(float(cache[a] @ cache[b]))
        labels.append(label)
    return np.array(scores), np.array(labels), skipped


def best_threshold(scores: np.ndarray, labels: np.ndarray) -> float:
    """Seuil qui maximise l'accuracy sur les paires d'entraînement."""
    candidates = np.unique(scores)
    best_t, best_acc = float(candidates[0]), -1.0
    for t in candidates:
        acc = float(np.mean((scores >= t) == labels))
        if acc > best_acc:
            best_t, best_acc = float(t), acc
    return best_t


def run() -> dict:
    """Applique le protocole officiel LFW à 10 folds, puis enregistre les résultats."""
    folds = parse_pairs(OFFICIAL_PAIRS_PATH)
    unique_photos = sorted({p for fold in folds for pair in fold for p in pair[:2]})

    cache = compute_embeddings(unique_photos, load_cache(CACHE_PATH))

    fold_scores = []
    skipped_total = 0
    for fold in folds:
        scores, labels, skipped = score_fold(fold, cache)
        fold_scores.append((scores, labels))
        skipped_total += skipped
    logger.info("Paires écartées (photo sans visage) : %d", skipped_total)

    accuracies, thresholds = [], []
    for k in range(len(folds)):
        train_scores = np.concatenate([s for i, (s, _) in enumerate(fold_scores) if i != k])
        train_labels = np.concatenate([l for i, (_, l) in enumerate(fold_scores) if i != k])
        threshold = best_threshold(train_scores, train_labels)
        test_scores, test_labels = fold_scores[k]
        accuracy = float(np.mean((test_scores >= threshold) == test_labels))
        accuracies.append(accuracy)
        thresholds.append(threshold)
        logger.info("Fold %d : seuil %.4f, accuracy %.4f", k + 1, threshold, accuracy)

    results = {
        "protocole": "LFW officiel, 10 folds, seuil appris sur 9 folds",
        "accuracy_moyenne": float(np.mean(accuracies)),
        "accuracy_ecart_type": float(np.std(accuracies, ddof=1)),
        "accuracy_par_fold": accuracies,
        "seuil_moyen": float(np.mean(thresholds)),
        "paires_ecartees": skipped_total,
    }
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with RESULTS_PATH.open("w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    logger.info(
        "Accuracy LFW : %.4f ± %.4f (seuil moyen %.4f)",
        results["accuracy_moyenne"], results["accuracy_ecart_type"], results["seuil_moyen"],
    )
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    run()