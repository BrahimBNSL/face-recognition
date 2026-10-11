# Face Recognition Project Architecture

## Overview

The system operates in two phases that share exactly the same image-processing pipeline. The recognition engine is written in Python, while the user interface is a React application that communicates with the engine through an HTTP API.

```text
Enrollment
  photo ─► detection (SCRFD) ─► quality checks ─► ArcFace alignment ─► embedding ─► database

Recognition (real-time or simulated)
  image ─► detection ─► quality checks ─► ArcFace alignment ─► embedding ─► database comparison ─► threshold-based decision
```

The same model and preprocessing pipeline are used in both phases. Otherwise, similarity scores would no longer be meaningful.

## Project Structure

```text
face-recognition/
├── src/                      Recognition engine (Python)
│   ├── config.py             Settings: thresholds, sizes, enrollment rules
│   ├── source.py             Image input (files, folders, camera)
│   ├── detect.py             SCRFD detection and alignment to the 112 × 112 ArcFace template
│   ├── quality.py            Quality checks: face count, size, centering, lighting, sharpness
│   ├── embed.py              Normalized 512-dimensional vector (ArcFace ResNet-50, ONNX)
│   ├── database.py           JSON vector database, without photos
│   ├── recognize.py          Validation, comparison, and threshold-based decisions
│   ├── evaluate.py            Evaluation: TAR@FAR, ROC, confidence intervals
│   ├── splits.py             LFW split by identity, with no overlap
│   ├── extract_embeddings.py  Embedding extraction for validation and test sets
│   └── lfw_protocol.py       Official 10-fold LFW protocol
├── server/
│   ├── __init__.py
│   └── main.py               FastAPI: analysis, enrollment, and verification endpoints
├── web/                      React + Vite + Tailwind interface
│   └── src/
│       ├── App.jsx           Application layout and tabs
│       ├── api.js            API requests and image capture
│       ├── sound.js          Approval and denial sounds (Web Audio)
│       └── components/
│           ├── RealTime.jsx      Live recognition with a colored bounding box
│           ├── Enroll.jsx        Guided capture, enrollment, and database management
│           ├── Access.jsx        Access simulation
│           ├── AccessCamera.jsx  Camera capture for access simulation
│           └── AccessPanel.jsx   Simulated access screen and event log
├── app/                      Legacy Gradio interface (optional)
├── data/                     Datasets (not version-controlled)
├── database/visages.json     Face database (not version-controlled)
├── models/                   ONNX model weights (not version-controlled; license restrictions apply)
└── outputs/                  Metrics and results (not version-controlled)
```

## Responsibilities and Contracts of Each Module

| Module | Input | Output | Dependencies |
|---|---|---|---|
| `source.py` | File path, folder, or camera index | RGB image (NumPy) | config |
| `detect.py` | RGB image | List of faces: bounding box, 5 landmarks, confidence score | config, SCRFD model |
| `quality.py` | Image and detected faces | Assessment: level, message, region, quality score | config |
| `embed.py` | Aligned 112 × 112 RGB face | 512-dimensional unit-length vector | config, ArcFace model |
| `database.py` | Name and vector | JSON database with locking and atomic writes | config |
| `recognize.py` | Image or vector, database, threshold | Identity, similarity score, candidates | detect, embed, database, config |
| `evaluate.py` | Labeled pairs and embeddings | TAR, FAR, ROC, confidence intervals | embeddings |
| `splits.py` | LFW directory | Identity-based splits and pairs | config |
| `lfw_protocol.py` | `pairs.csv` and LFW images | Accuracy across 10 folds | detect, embed, splits |
| `server/main.py` | HTTP requests (images, forms) | JSON responses | recognize, quality, detect, database |

## API Endpoints

| Method and endpoint | Purpose |
|---|---|
| `GET /api/health` | Server status and decision threshold |
| `POST /api/analyze` | Face detection, quality assessment, and identity recognition for a frame |
| `POST /api/enroll` | Enroll a person from a photo after consent |
| `GET /api/people` | List enrolled people and the number of embeddings per person |
| `DELETE /api/people/{name}` | Delete a person and all associated data |
| `POST /api/verify` | Identify a person from a photo and log the attempt |
| `GET /api/journal` | Retrieve the most recent access attempts |

## React Interface

- **Real-time recognition:** The video stream is displayed continuously. A frame is sent to `/api/analyze` every 0.5 seconds, and a bounding box is drawn on an overlay. Decisions are smoothed across five frames: the same identity must be detected three times before it is announced.
- **Enrollment:** Guided image capture. The bounding box and status banner indicate what needs to be corrected. After five consecutive acceptable frames, the best image is selected. Enrollment requires explicit consent.
- **Access simulation:** A photo can be captured or uploaded. The simulated screen turns green or red, and each attempt is recorded in the log.

Sound is played whenever the decision changes: an approval sound for a recognized person and a denial sound for an unknown person or a failed verification.

## Design Principles

- **Single preprocessing pipeline:** Enrollment and recognition use the same processing steps.
- **No default threshold:** `recognize.py` refuses to make a decision until `threshold` has been configured.
- **Data minimization:** The database stores embeddings only, never the original photos.
- **Deletion on request:** A person can be removed from the database at any time.
- **Non-blocking processing:** Computationally intensive analysis runs in a separate thread so the server remains responsive.
- **Test set used only once:** The decision threshold is selected using the validation set, never the test set.
