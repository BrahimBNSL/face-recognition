"""Source d'images : fichiers, dossiers ou caméra, avec un contrat de sortie identique."""

from __future__ import annotations

import logging
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps

from src.config import SourceConfig

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS: frozenset[str] = frozenset({".jpg", ".jpeg", ".png", ".bmp", ".webp"})


@dataclass(frozen=True)
class Frame:
    """Une image fournie au reste du pipeline."""

    image: np.ndarray
    index: int
    origin: str


def load_image_file(path: Path) -> np.ndarray:
    """Charge une image en RGB uint8, en corrigeant l'orientation indiquée par les métadonnées EXIF."""
    if not path.is_file():
        raise FileNotFoundError(f"Image introuvable : {path}")
    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img)
        return np.asarray(img.convert("RGB"), dtype=np.uint8).copy()


def iter_image_folder(folder: Path) -> Iterator[Frame]:
    """Parcourt un dossier d'images dans l'ordre alphabétique, en ignorant les fichiers non image."""
    if not folder.is_dir():
        raise NotADirectoryError(f"Dossier introuvable : {folder}")
    paths = sorted(p for p in folder.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS)
    if not paths:
        raise FileNotFoundError(f"Aucune image dans {folder}")
    for index, path in enumerate(paths):
        logger.debug("Lecture de %s", path.name)
        yield Frame(image=load_image_file(path), index=index, origin=path.name)


def open_camera(camera_index: int) -> cv2.VideoCapture:
    """Ouvre la caméra avec le backend adapté au système, et vérifie qu'elle répond."""
    backend = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY
    capture = cv2.VideoCapture(camera_index, backend)
    if not capture.isOpened():
        capture.release()
        raise RuntimeError(f"Impossible d'ouvrir la caméra d'index {camera_index}")
    return capture


def iter_camera_frames(cfg: SourceConfig) -> Iterator[Frame]:
    """Produit une frame sur N depuis la caméra, jusqu'à max_frames images échantillonnées."""
    capture = open_camera(cfg.camera_index)
    try:
        read_index = 0
        yielded = 0
        while yielded < cfg.max_frames:
            ok, bgr = capture.read()
            if not ok:
                raise RuntimeError("Lecture de la caméra interrompue")
            if read_index % cfg.sample_every == 0:
                rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                yield Frame(image=rgb, index=read_index, origin="camera")
                yielded += 1
            read_index += 1
    finally:
        capture.release()


def iter_frames(cfg: SourceConfig, path: Path | None = None) -> Iterator[Frame]:
    """Point d'entrée unique : une image, un dossier, ou la caméra si aucun chemin n'est fourni."""
    if path is None:
        yield from iter_camera_frames(cfg)
    elif path.is_dir():
        yield from iter_image_folder(path)
    else:
        yield Frame(image=load_image_file(path), index=0, origin=path.name)