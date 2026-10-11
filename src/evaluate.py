"""Évaluation de la vérification : seuil choisi sur la validation, mesure unique sur le test."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from sklearn.metrics import roc_auc_score, roc_curve

from src.config import OUTPUT_DIR
from src.extract_embeddings import EMBEDDINGS_PATH
from src.splits import SPLITS_PATH, load_splits

logger = logging.getLogger(__name__)

TARGET_FAR: float = 0.01
BOOTSTRAP_ROUNDS: int = 1000
SEED: int = 42
RESULTS_PATH: Path = OUTPUT_DIR / "metrics" / "palier1_verification.json"


@dataclass(frozen=True)
class PairSet:
    """Scores de similarité et étiquettes (1 = même personne, 0 = personnes différentes)."""

    scores: np.ndarray
    labels: np.ndarray


def load_embeddings(path: Path = EMBEDDINGS_PATH) -> dict:
    """Charge les embeddings, les renormalise, et indexe les photos par leur chemin."""
    if not path.is_file():
        raise FileNotFoundError(f"Embeddings introuvables : {path}. Lancez python -m src.extract_embeddings.")
    data = np.load(path)
    vectors = data["vectors"].astype(np.float32)
    vectors = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
    index = {str(photo): i for i, photo in enumerate(data["photos"])}
    return {"vectors": vectors, "index": index}


def build_pair_set(pairs: list[dict], emb: dict) -> PairSet:
    """Calcule la similarité cosinus de chaque paire dont les deux photos ont un embedding."""
    scores: list[float] = []
    labels: list[int] = []
    skipped = 0
    for pair in pairs:
        ia = emb["index"].get(pair["a"])
        ib = emb["index"].get(pair["b"])
        if ia is None or ib is None:
            skipped += 1
            continue
        scores.append(float(emb["vectors"][ia] @ emb["vectors"][ib]))
        labels.append(int(pair["label"]))
    if skipped:
        logger.info("%d paires ignorées (photo sans visage détecté)", skipped)
    if not scores:
        raise ValueError("Aucune paire exploitable")
    return PairSet(scores=np.array(scores), labels=np.array(labels))


def choose_threshold(pairs: PairSet, target_far: float) -> tuple[float, float, float]:
    """Choisit le seuil qui maximise le TAR tout en gardant le FAR sous la cible, sur la validation."""
    fpr, tpr, thresholds = roc_curve(pairs.labels, pairs.scores)
    valid = np.where(fpr <= target_far)[0]
    if valid.size == 0:
        raise ValueError(f"Aucun seuil ne respecte un FAR de {target_far}")
    best = valid[np.argmax(tpr[valid])]
    return float(thresholds[best]), float(tpr[best]), float(fpr[best])


def rates_at(pairs: PairSet, threshold: float) -> tuple[float, float]:
    """Retourne le TAR et le FAR obtenus avec un seuil fixé."""
    predicted = pairs.scores >= threshold
    tar = float(predicted[pairs.labels == 1].mean())
    far = float(predicted[pairs.labels == 0].mean())
    return tar, far


def bootstrap_rates(pairs: PairSet, threshold: float, rounds: int, seed: int) -> dict:
    """Intervalle de confiance à 95 % du TAR et du FAR, par rééchantillonnage des paires."""
    rng = np.random.default_rng(seed)
    n = len(pairs.labels)
    tars: list[float] = []
    fars: list[float] = []
    for _ in range(rounds):
        idx = rng.integers(0, n, n)
        labels = pairs.labels[idx]
        predicted = pairs.scores[idx] >= threshold
        positives = labels == 1
        negatives = labels == 0
        if positives.any() and negatives.any():
            tars.append(float(predicted[positives].mean()))
            fars.append(float(predicted[negatives].mean()))
    return {
        "TAR_IC95": [float(np.percentile(tars, 2.5)), float(np.percentile(tars, 97.5))],
        "FAR_IC95": [float(np.percentile(fars, 2.5)), float(np.percentile(fars, 97.5))],
    }


def run() -> dict:
    """Choisit le seuil sur la validation, mesure une seule fois sur le test, puis enregistre les résultats."""
    emb = load_embeddings()
    pairs = load_splits(SPLITS_PATH)["paires"]

    validation = build_pair_set(pairs["validation"], emb)
    test = build_pair_set(pairs["test"], emb)
    logger.info("Paires exploitables : validation %d, test %d", len(validation.labels), len(test.labels))

    threshold, val_tar, val_far = choose_threshold(validation, TARGET_FAR)
    logger.info("Seuil choisi sur la validation : %.4f (TAR %.4f, FAR %.4f)", threshold, val_tar, val_far)

    test_tar, test_far = rates_at(test, threshold)
    test_auc = float(roc_auc_score(test.labels, test.scores))
    intervals = bootstrap_rates(test, threshold, BOOTSTRAP_ROUNDS, SEED)

    results = {
        "protocole": "seuil choisi sur la validation au FAR cible, mesure unique sur le test",
        "FAR_cible": TARGET_FAR,
        "seuil": threshold,
        "validation": {"TAR": val_tar, "FAR": val_far, "paires": int(len(validation.labels))},
        "test": {
            "TAR": test_tar,
            "FAR": test_far,
            "ROC_AUC": test_auc,
            "paires": int(len(test.labels)),
            **intervals,
        },
    }
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with RESULTS_PATH.open("w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    logger.info(
        "Test : TAR %.4f (IC95 %s), FAR %.4f (IC95 %s), ROC AUC %.4f",
        test_tar, [round(x, 4) for x in intervals["TAR_IC95"]],
        test_far, [round(x, 4) for x in intervals["FAR_IC95"]],
        test_auc,
    )
    logger.info("Résultats enregistrés dans %s", RESULTS_PATH)
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    run()