# Architecture du projet de reconnaissance faciale

## Vue d'ensemble

Le système fonctionne en deux phases, qui partagent exactement le même traitement d'image. Le moteur de reconnaissance est écrit en Python ; l'interface est une application React qui communique avec lui par une API HTTP.

```
Enregistrement
  photo ─► détection (SCRFD) ─► contrôle qualité ─► alignement ArcFace ─► embedding ─► base

Reconnaissance (temps réel ou simulation)
  image ─► détection ─► contrôle qualité ─► alignement ArcFace ─► embedding ─► comparaison à la base ─► décision au seuil
```

Le même modèle et le même prétraitement servent aux deux phases. Sans cela, les similarités n'ont plus de sens.

## Arborescence

```
face-recognition/
├── src/                      Moteur de reconnaissance (Python)
│   ├── config.py             Paramètres : seuils, tailles, règles d'enregistrement
│   ├── source.py             Lecture des images (fichiers, dossiers, caméra)
│   ├── detect.py             Détection SCRFD et alignement sur le gabarit ArcFace 112 × 112
│   ├── quality.py            Contrôle qualité : nombre de visages, taille, centrage, lumière, netteté
│   ├── embed.py              Vecteur normalisé de 512 valeurs (ResNet-50 ArcFace, ONNX)
│   ├── database.py           Base de vecteurs en JSON, sans aucune photo
│   ├── recognize.py          Contrôles, comparaison et décision au seuil
│   ├── evaluate.py           Évaluation : TAR@FAR, ROC, intervalles de confiance
│   ├── splits.py             Découpage de LFW par personne, sans chevauchement
│   ├── extract_embeddings.py Embeddings des jeux de validation et de test
│   └── lfw_protocol.py       Protocole officiel LFW à 10 folds
├── server/
│   ├── __init__.py
│   └── main.py               API FastAPI : routes d'analyse, d'enregistrement, de vérification
├── web/                      Interface React + Vite + Tailwind
│   └── src/
│       ├── App.jsx           Structure et onglets
│       ├── api.js            Appels à l'API et capture d'image
│       ├── sound.js          Sons d'accord et de refus (Web Audio)
│       └── components/
│           ├── RealTime.jsx      Reconnaissance en direct, cadre coloré
│           ├── Enroll.jsx        Capture guidée, enregistrement, gestion de la base
│           ├── Access.jsx        Simulation d'accès
│           ├── AccessCamera.jsx  Capture caméra pour la simulation
│           └── AccessPanel.jsx   Écran simulé et journal
├── app/                      Ancienne interface Gradio (facultative)
├── data/                     Données (non versionnées)
├── database/visages.json     Base de connaissance (non versionnée)
├── models/                   Poids ONNX (non versionnés, licence à respecter)
└── outputs/                  Métriques et résultats (non versionnés)
```

## Rôle et contrat de chaque module

| Module | Entrée | Sortie | Dépend de |
|---|---|---|---|
| `source.py` | chemin de fichier, dossier ou index de caméra | image RGB (numpy) | config |
| `detect.py` | image RGB | liste de visages : boîte, 5 points de repère, score | config, modèle SCRFD |
| `quality.py` | image et visages détectés | verdict : niveau, message, zone, score de qualité | config |
| `embed.py` | visage aligné 112 × 112 RGB | vecteur de 512 valeurs, de longueur 1 | config, modèle ArcFace |
| `database.py` | nom et vecteur | base JSON, avec verrou et écriture atomique | config |
| `recognize.py` | image ou vecteur, base, seuil | identité, similarité, candidats | detect, embed, database, config |
| `evaluate.py` | paires étiquetées et vecteurs | TAR, FAR, ROC, intervalles de confiance | embeddings |
| `splits.py` | dossier LFW | découpage par personne et paires | config |
| `lfw_protocol.py` | `pairs.csv` et photos LFW | accuracy sur 10 folds | detect, embed, splits |
| `server/main.py` | requêtes HTTP (images, formulaires) | réponses JSON | recognize, quality, detect, database |

## Routes de l'API

| Méthode et route | Rôle |
|---|---|
| `GET /api/health` | État du serveur et seuil de décision |
| `POST /api/analyze` | Visages, qualité et identité d'une image du flux |
| `POST /api/enroll` | Enregistrement d'une photo, après consentement |
| `GET /api/people` | Liste des personnes et de leur nombre de vecteurs |
| `DELETE /api/people/{nom}` | Suppression d'une personne et de toutes ses données |
| `POST /api/verify` | Identification d'une photo et journalisation de la tentative |
| `GET /api/journal` | Dernières tentatives d'accès |

## Interface React

- **Temps réel** : la vidéo est affichée en continu. Une image est envoyée toutes les 0,5 seconde à `/api/analyze`, et le cadre est dessiné sur une couche superposée. La décision est lissée sur 5 images : il faut 3 identifications identiques pour l'annoncer.
- **Enregistrement** : capture guidée. Le cadre et le bandeau indiquent ce qui doit être corrigé. Après 5 images correctes d'affilée, la meilleure est retenue. Le bouton d'enregistrement exige le consentement.
- **Simulation d'accès** : une photo, capturée ou importée. L'écran simulé devient vert ou rouge, et le journal enregistre chaque tentative.

Le son est joué au changement de décision : accord pour une personne reconnue, refus pour une personne inconnue ou une vérification échouée.

## Principes de conception

- **Un seul prétraitement** : la chaîne est la même pour l'enregistrement et la reconnaissance.
- **Seuil non défini par défaut** : `recognize.py` refuse de décider tant que `threshold` n'est pas fixé.
- **Données biométriques minimales** : la base ne contient que des vecteurs, jamais les photos.
- **Suppression sur demande** : une personne peut être retirée de la base à tout moment.
- **Calcul hors du serveur principal** : les analyses lourdes s'exécutent dans un thread séparé, pour que le serveur reste réactif.
- **Test utilisé une seule fois** : le seuil est choisi sur la validation, jamais sur le test.


