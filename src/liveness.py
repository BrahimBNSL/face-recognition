"""Anti-spoofing actif : défi de rotation de la tête, validé côté serveur par sessions à durée limitée."""

from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass, field

import numpy as np

SESSION_TTL_SECONDS: float = 30.0
TURN_THRESHOLD: float = 0.25
NEUTRAL_THRESHOLD: float = 0.10
DIRECTIONS: tuple[str, ...] = ("gauche", "droite")


def head_yaw(landmarks: np.ndarray) -> float:
    """Indice d'orientation horizontale : négatif vers l'image gauche, positif vers l'image droite."""
    left_eye, right_eye, nose = landmarks[0], landmarks[1], landmarks[2]
    eye_distance = float(np.linalg.norm(right_eye - left_eye))
    if eye_distance == 0:
        raise ValueError("Points de repère des yeux confondus")
    eye_middle_x = (left_eye[0] + right_eye[0]) / 2
    return float((nose[0] - eye_middle_x) / eye_distance)


@dataclass
class Session:
    """Une tentative de défi : direction demandée, état d'avancement et date d'expiration."""

    direction: str
    expires_at: float
    seen_neutral: bool = False
    passed: bool = False
    history: list[float] = field(default_factory=list)


class LivenessManager:
    """Crée, met à jour et consomme les sessions de défi, avec un verrou pour les accès concurrents."""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    def _purge(self, now: float) -> None:
        expired = [key for key, session in self._sessions.items() if session.expires_at < now]
        for key in expired:
            del self._sessions[key]

    def start(self) -> dict[str, object]:
        """Crée une session avec une direction tirée au hasard, et retourne son identifiant."""
        now = time.monotonic()
        direction = secrets.choice(DIRECTIONS)
        session_id = secrets.token_urlsafe(16)
        with self._lock:
            self._purge(now)
            self._sessions[session_id] = Session(direction=direction, expires_at=now + SESSION_TTL_SECONDS)
        return {"session_id": session_id, "direction": direction, "ttl": SESSION_TTL_SECONDS}

    def update(self, session_id: str, yaw: float | None) -> dict[str, object]:
        """Met à jour une session avec l'orientation d'une nouvelle image, et retourne son état."""
        now = time.monotonic()
        with self._lock:
            self._purge(now)
            session = self._sessions.get(session_id)
            if session is None:
                return {"status": "expired", "message": "Session expirée. Recommencez le défi."}
            if yaw is None:
                return {"status": "waiting", "message": "Visage non détecté."}

            session.history.append(yaw)
            if abs(yaw) <= NEUTRAL_THRESHOLD:
                session.seen_neutral = True

            turned = yaw <= -TURN_THRESHOLD if session.direction == "gauche" else yaw >= TURN_THRESHOLD
            if session.seen_neutral and turned:
                session.passed = True

            if session.passed:
                return {"status": "passed", "message": "Défi réussi."}
            if not session.seen_neutral:
                return {"status": "neutral", "message": "Regardez la caméra, face à vous."}
            return {"status": "turn", "message": f"Tournez doucement la tête vers la {session.direction}."}

    def consume(self, session_id: str | None) -> bool:
        """Vérifie qu'une session est validée et non expirée, puis la supprime : usage unique."""
        if not session_id:
            return False
        now = time.monotonic()
        with self._lock:
            self._purge(now)
            session = self._sessions.pop(session_id, None)
        return bool(session and session.passed)


liveness = LivenessManager()