"""Découpage de LFW par personne : validation, test et distracteurs, sans chevauchement."""

from __future__ import annotations

import json
import logging
import random
from dataclasses import dataclass
from pathlib import Path

from src.config import DATA_DIR

logger = logging.getLogger(__name__)

LFW_ROOT: Path = DATA_DIR / "lfw" / "lfw-deepfunneled" / "lfw-deepfunneled"
SPLITS_PATH: Path = DATA_DIR / "splits.json"


@dataclass(frozen=True)
class SplitConfig:
    """Paramètres du découpage."""

    min_photos: int = 10
    n_val: int = 40
    n_test: int = 40
    seed: int = 42

    def __post_init__(self) -> None:
        if self.min_photos < 2:
            raise ValueError(f"min_photos doit être au moins 2 pour former des paires, reçu {self.min_photos}")
        if self.n_val < 2 or self.n_test < 2:
            raise ValueError("n_val et n_test doivent être au moins 2")


def list_photos(person_dir: Path) -> list[str]:
    """Liste les photos JPG d'une personne, en noms de fichiers triés."""
    return sorted(p.name for p in person_dir.glob("*.jpg"))


def list_eligible_persons(root: Path, min_photos: int) -> dict[str, int]:
    """Retourne les personnes ayant au moins min_photos photos, avec leur nombre de photos."""
    if not root.is_dir():
        raise FileNotFoundError(f"Dossier LFW introuvable : {root}")
    eligible: dict[str, int] = {}
    for person_dir in root.iterdir():
        if not person_dir.is_dir():
            continue
        count = len(list_photos(person_dir))
        if count >= min_photos:
            eligible[person_dir.name] = count
    return eligible


def build_splits(root: Path, cfg: SplitConfig) -> dict[str, dict[str, int]]:
    """Répartit les personnes éligibles en validation, test et distracteurs, sans chevauchement."""
    eligible = list_eligible_persons(root, cfg.min_photos)
    names = sorted(eligible)
    needed = cfg.n_val + cfg.n_test
    if len(names) < needed + 1:
        raise ValueError(f"Pas assez de personnes éligibles : {len(names)}, il en faut au moins {needed + 1}")

    rng = random.Random(cfg.seed)
    shuffled = names[:]
    rng.shuffle(shuffled)

    val_names = shuffled[: cfg.n_val]
    test_names = shuffled[cfg.n_val : needed]
    distractor_names = shuffled[needed:]

    splits = {
        "validation": {name: eligible[name] for name in val_names},
        "test": {name: eligible[name] for name in test_names},
        "distracteurs": {name: eligible[name] for name in distractor_names},
    }
    check_disjoint(splits)
    return splits


def check_disjoint(splits: dict[str, dict[str, int]]) -> None:
    """Vérifie qu'aucune personne n'apparaît dans deux ensembles."""
    keys = list(splits)
    for i, first in enumerate(keys):
        for second in keys[i + 1 :]:
            shared = set(splits[first]) & set(splits[second])
            if shared:
                raise ValueError(f"Personnes communes entre {first} et {second} : {sorted(shared)[:5]}")


def save_splits(splits: dict, path: Path = SPLITS_PATH) -> None:
    """Enregistre le découpage en JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(splits, f, indent=2, ensure_ascii=False)


def load_splits(path: Path = SPLITS_PATH) -> dict:
    """Charge un découpage enregistré."""
    if not path.is_file():
        raise FileNotFoundError(f"Découpage introuvable : {path}. Lancez python -m src.splits.")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def make_pairs(
    persons: dict[str, int], root: Path, n_per_class: int, seed: int
) -> list[dict]:
    """Crée des paires équilibrées : n_per_class paires de même personne et n_per_class de personnes différentes."""
    rng = random.Random(seed)
    names = sorted(persons)
    photos = {name: list_photos(root / name) for name in names}

    positives: list[dict] = []
    while len(positives) < n_per_class:
        name = rng.choice(names)
        a, b = rng.sample(photos[name], 2)
        positives.append({"a": f"{name}/{a}", "b": f"{name}/{b}", "label": 1})

    negatives: list[dict] = []
    while len(negatives) < n_per_class:
        first, second = rng.sample(names, 2)
        a = rng.choice(photos[first])
        b = rng.choice(photos[second])
        negatives.append({"a": f"{first}/{a}", "b": f"{second}/{b}", "label": 0})

    pairs = positives + negatives
    rng.shuffle(pairs)
    return pairs


def run(cfg: SplitConfig = SplitConfig()) -> dict:
    """Construit le découpage, l'enregistre, puis génère les paires de validation et de test."""
    splits = build_splits(LFW_ROOT, cfg)

    for name, persons in splits.items():
        logger.info("%s : %d personnes, %d photos", name, len(persons), sum(persons.values()))

    pairs = {
        "validation": make_pairs(splits["validation"], LFW_ROOT, 300, cfg.seed),
        "test": make_pairs(splits["test"], LFW_ROOT, 300, cfg.seed + 1),
    }
    save_splits({"personnes": splits, "paires": pairs}, SPLITS_PATH)
    logger.info("Paires : validation %d, test %d", len(pairs["validation"]), len(pairs["test"]))
    return {"personnes": splits, "paires": pairs}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    run()