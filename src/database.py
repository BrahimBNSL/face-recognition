"""Base de connaissance : vecteurs de visage par personne, enregistrés en JSON, sans aucune photo."""

from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path

import numpy as np

from src.config import DATABASE_PATH

logger = logging.getLogger(__name__)

SCHEMA_VERSION: int = 1
EMBEDDING_DIM: int = 512
MAX_NAME_LENGTH: int = 64


class Database:
    """Stocke, pour chaque personne, la liste de ses vecteurs normalisés."""

    def __init__(self, path: Path = DATABASE_PATH) -> None:
        self.path = path
        self._lock = threading.Lock()
        self._persons: dict[str, list[list[float]]] = {}
        if self.path.is_file():
            self._load()

    def _load(self) -> None:
        with self.path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("version") != SCHEMA_VERSION:
            raise ValueError(f"Version de base inconnue : {data.get('version')}")
        self._persons = data["personnes"]
        logger.info("Base chargée : %d personnes", len(self._persons))

    def _save(self) -> None:
        """Écrit dans un fichier temporaire puis remplace l'original : pas de fichier partiel si l'écriture échoue."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        with temporary.open("w", encoding="utf-8") as f:
            json.dump({"version": SCHEMA_VERSION, "personnes": self._persons}, f, ensure_ascii=False)
        os.replace(temporary, self.path)

    @staticmethod
    def _validate_name(name: str) -> str:
        cleaned = name.strip()
        if not cleaned:
            raise ValueError("Le nom ne peut pas être vide")
        if len(cleaned) > MAX_NAME_LENGTH:
            raise ValueError(f"Le nom ne doit pas dépasser {MAX_NAME_LENGTH} caractères")
        if any(char in cleaned for char in '/\\:*?"<>|'):
            raise ValueError("Le nom contient des caractères interdits")
        return cleaned

    @staticmethod
    def _validate_vector(vector: np.ndarray) -> list[float]:
        if vector.shape != (EMBEDDING_DIM,):
            raise ValueError(f"Vecteur attendu de dimension {EMBEDDING_DIM}, reçu {vector.shape}")
        if not np.isclose(np.linalg.norm(vector), 1.0, atol=1e-3):
            raise ValueError("Le vecteur doit être normalisé (longueur 1)")
        return [float(x) for x in vector]

    def add(self, name: str, vector: np.ndarray) -> int:
        """Ajoute un vecteur à une personne, la crée si besoin, et retourne le nombre de vecteurs enregistrés."""
        clean_name = self._validate_name(name)
        values = self._validate_vector(np.asarray(vector, dtype=np.float32))
        with self._lock:
            self._persons.setdefault(clean_name, []).append(values)
            self._save()
            count = len(self._persons[clean_name])
        logger.info("Vecteur ajouté pour %s (%d au total)", clean_name, count)
        return count

    def remove(self, name: str) -> None:
        """Supprime une personne et tous ses vecteurs, pour respecter une demande de retrait."""
        with self._lock:
            if name not in self._persons:
                raise KeyError(f"Personne inconnue : {name}")
            del self._persons[name]
            self._save()
        logger.info("Personne supprimée : %s", name)

    def names(self) -> list[str]:
        """Liste les personnes enregistrées, triées par nom."""
        with self._lock:
            return sorted(self._persons)

    def count(self, name: str) -> int:
        """Nombre de vecteurs enregistrés pour une personne."""
        with self._lock:
            return len(self._persons.get(name, []))

    def all_vectors(self) -> tuple[list[str], np.ndarray]:
        """Retourne les noms et la matrice de tous les vecteurs, avec un nom par ligne."""
        with self._lock:
            labels: list[str] = []
            rows: list[list[float]] = []
            for name, vectors in self._persons.items():
                for vector in vectors:
                    labels.append(name)
                    rows.append(vector)
        if not rows:
            return [], np.zeros((0, EMBEDDING_DIM), dtype=np.float32)
        return labels, np.array(rows, dtype=np.float32)