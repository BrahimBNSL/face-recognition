# Reconnaissance faciale : enregistrement, vérification et contrôle d'accès simulé

Système de reconnaissance faciale complet : détection des visages, alignement, embedding ArcFace, base de connaissance locale, décision par seuil, et interface web en temps réel.

> **Avertissement.** Ce projet est une démonstration académique. Il n'est pas un dispositif de sécurité ni un outil de contrôle d'accès réel. Les données biométriques doivent être traitées conformément à la réglementation applicable, et uniquement avec le consentement des personnes concernées.

## Fonctionnalités

- **Temps réel** : reconnaissance en direct, cadre vert avec le nom si la personne est reconnue, rouge « INCONNU » sinon. La décision est confirmée sur plusieurs images pour éviter les fluctuations.
- **Enregistrement** : capture guidée avec contrôle de qualité (taille, centrage, lumière, netteté), sélection automatique de la meilleure photo, consentement obligatoire, et gestion de la base.
- **Simulation d'accès** : vérification d'une photo, écran simulé vert ou rouge, et journal des tentatives. Aucun appareil réel n'est commandé.

## Architecture

```
face-recognition/
├── src/                  Moteur de reconnaissance (Python)
│   ├── config.py         Paramètres (seuils, tailles, règles)
│   ├── source.py         Lecture des images (fichiers, caméra)
│   ├── detect.py         Détection SCRFD et alignement ArcFace
│   ├── quality.py        Contrôle qualité des captures
│   ├── embed.py          Vecteur de visage (ResNet-50 ArcFace, ONNX)
│   ├── database.py       Base de vecteurs (JSON, sans photo)
│   ├── recognize.py      Comparaison et décision au seuil
│   ├── evaluate.py       Évaluation (TAR@FAR, ROC, intervalles de confiance)
│   └── lfw_protocol.py   Protocole officiel LFW (10 folds)
├── server/
│   └── main.py           API FastAPI
├── web/                  Interface React + Vite + Tailwind
│   └── src/
│       ├── components/   Temps réel, enregistrement, simulation
│       ├── api.js        Appels au serveur
│       └── sound.js      Sons d'accord et de refus
└── app/                  Ancienne interface Gradio (facultative)
```

## Modèles nécessaires

Les poids des modèles ne sont pas inclus dans ce dépôt, pour deux raisons : leur taille, et leur licence non commerciale.

1. Téléchargez l'archive **buffalo_l** depuis la page des releases d'InsightFace : `https://github.com/deepinsight/insightface/releases`.
2. Extrayez-la, puis copiez dans le dossier `models/` :
   - `w600k_r50.onnx` (reconnaissance, ResNet-50 entraîné avec ArcFace)
   - `det_10g.onnx` (détection, SCRFD)

Le dossier `models/` doit être créé à la racine du projet.

## Données

Les données ne sont pas incluses. Pour évaluer le système, le projet utilise le jeu public **LFW** (Labeled Faces in the Wild), placé dans `data/lfw/`. Les photos d'enregistrement sont saisies par l'utilisateur, avec son consentement.

## Installation

Environnement Python 3.11 recommandé.

```bash
conda create -n visage python=3.11 -y
conda activate visage
pip install -r requirements.txt
pip install fastapi uvicorn python-multipart opencv-python onnxruntime
```

Pour l'interface React, il faut Node.js (version LTS) :

```bash
cd web
npm install
```

## Utilisation

Lancez le serveur (terminal 1) :

```bash
uvicorn server.main:app --host 127.0.0.1 --port 8000
```

Lancez l'interface (terminal 2) :

```bash
cd web
npm run dev
```

Ouvrez ensuite `http://localhost:5173`.

Le seuil de décision est défini dans `src/config.py`, dans `RecognitionConfig.threshold`. Il doit être choisi sur un jeu de validation, et non deviné : la valeur par défaut `0.2626` correspond au point de fonctionnement retenu pour un taux de fausses acceptations de 1 %.

## Évaluation

Les résultats sont calculés sur un jeu de test séparé, avec un seuil choisi uniquement sur la validation.

| Mesure | Résultat |
|---|---|
| Protocole officiel LFW (10 folds) | à compléter après l'exécution de `python -m src.lfw_protocol` |
| TAR à 1 % de FAR (test interne) | 0,973 (IC 95 % : 0,954 à 0,990) |
| ROC AUC (test interne) | 0,992 |

Les intervalles de confiance sont calculés par bootstrap sur les paires de test.


## Références

- Deng, J. et al. (2019). *ArcFace: Additive Angular Margin Loss for Deep Face Recognition*. CVPR.
- Guo, J. et al. (2021). *Sample and Computation Redistribution for Efficient Face Detection* (SCRFD). ICLR.
- Huang, G. B. et al. (2007). *Labeled Faces in the Wild*. University of Massachusetts Amherst.
- Projet InsightFace : `https://github.com/deepinsight/insightface`.
