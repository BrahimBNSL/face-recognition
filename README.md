# Face Recognition: Enrollment, Verification, and Simulated Access Control

A complete face recognition system featuring face detection, face alignment, ArcFace embeddings, a local identity database, threshold-based verification, and a real-time web interface.

> **Disclaimer:** This project is an academic demonstration. It is not a security device or a real access-control system. Biometric data must be processed in accordance with applicable regulations and only with the consent of the individuals concerned.

## Features

- **Real-Time Recognition:** Live face recognition with a green bounding box and the person's name when recognized, or a red bounding box labeled **"UNKNOWN"** otherwise. Recognition decisions are confirmed across multiple frames to reduce fluctuations.
- **Face Enrollment:** Guided face capture with quality checks for face size, centering, lighting, and sharpness. The system automatically selects the best image, requires explicit consent, and provides identity database management.
- **Access Simulation:** Verification of an image, a simulated green or red access screen, and an attempt log. No physical access-control device is operated.

## Architecture

```text
face-recognition/
├── src/                  Python recognition engine
│   ├── config.py         Configuration (thresholds, sizes, rules)
│   ├── source.py         Image input (files, camera)
│   ├── detect.py         SCRFD face detection and ArcFace alignment
│   ├── quality.py       Capture quality assessment
│   ├── embed.py          Face embeddings (ArcFace ResNet-50, ONNX)
│   ├── database.py       Embedding database (JSON, no photos)
│   ├── recognize.py      Similarity comparison and threshold decisions
│   ├── evaluate.py       Evaluation (TAR@FAR, ROC, confidence intervals)
│   ├── lfw_protocol.py   Official LFW protocol (10 folds)
├── server/
│   └── main.py           FastAPI backend
├── web/                  React + Vite + Tailwind interface
│   └── src/
│       ├── components/   Real-time recognition, enrollment, simulation
│       ├── api.js        Backend API requests
│       └── sound.js      Access granted and denied sounds
└── app/                  Legacy Gradio interface (optional)
```

## Required Models

The model weights are not included in this repository for two reasons: their file size and their non-commercial licensing restrictions.

1. Download the **`buffalo_l`** model archive from the InsightFace releases page: https://github.com/deepinsight/insightface/releases
2. Extract the archive and copy the following files into the `models/` directory:
   - `w600k_r50.onnx` — face recognition model based on ResNet-50 and trained with ArcFace.
   - `det_10g.onnx` — SCRFD face detection model.

Create the `models/` directory in the project root.

## Dataset

The dataset is not included in the repository. The project uses the public **Labeled Faces in the Wild (LFW)** dataset for evaluation, which should be placed in `data/lfw/`.

Enrollment photographs are captured from users with their explicit consent.

## Installation

Python 3.11 is recommended.

```bash
conda create -n face-recognition python=3.11 -y
conda activate face-recognition
pip install -r requirements.txt
pip install fastapi uvicorn python-multipart opencv-python onnxruntime
```

For the React frontend, install an LTS version of Node.js.

```bash
cd web
npm install
```

## Usage

### 1. Start the Backend

Open a terminal and run:

```bash
uvicorn server.main:app --host 127.0.0.1 --port 8000
```

### 2. Start the Frontend

Open a second terminal and run:

```bash
cd web
npm run dev
```

### 3. Open the Application

Navigate to:

http://localhost:5173

### Recognition Threshold

The decision threshold is defined in `src/config.py`, under `RecognitionConfig.threshold`.

It must be selected using a validation dataset rather than chosen arbitrarily. The default value of `0.2626` corresponds to the operating point selected for a 1% False Acceptance Rate (FAR).

## Evaluation

Results are calculated on a separate test set, with the decision threshold selected exclusively using the validation set.

| Metric | Result |
|---|---|
| Official LFW protocol (10 folds) | To be completed after running `python -m src.lfw_protocol` |
| TAR at 1% FAR (internal test set) | 0.973 (95% CI: 0.954–0.990) |
| ROC-AUC (internal test set) | 0.992 |

Confidence intervals are calculated using bootstrap resampling of the test pairs.

**Note:** The numerical results above are the values provided in the original project description. They should be independently reproduced before being presented as verified experimental results.

## References

- Deng, J. et al. (2019). *ArcFace: Additive Angular Margin Loss for Deep Face Recognition*. CVPR.
- Guo, J. et al. (2021). *Sample and Computation Redistribution for Efficient Face Detection (SCRFD)*. ICLR.
- Huang, G. B. et al. (2007). *Labeled Faces in the Wild*. University of Massachusetts Amherst.
- InsightFace project: https://github.com/deepinsight/insightface
