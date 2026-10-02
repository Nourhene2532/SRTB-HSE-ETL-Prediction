# SRTB – ETL et prédiction des accidents de travail (PFE)

Projet de fin d'études réalisé **en binôme** à la **Société Régionale de Transport de Bizerte (SRTB)**, de février à juin 2026, en méthode agile (sprints).
Le projet est une plateforme décisionnelle de suivi **santé-sécurité** (visites médicales, accidents de travail, risques professionnels), organisée en trois parties :

| Partie | Contenu | Où |
|---|---|---|
| Web | Plateforme web | [dépôt de ma binôme](https://github.com/Abassi708/Platform_Sante_securite) |
| BI / ETL | Entrepôt de données MySQL → Python → PostgreSQL | dossier [`etl/`](etl/) (ce dépôt) |
| Prédiction | Prédiction du risque d'accident par machine learning | dossier [`prediction/`](prediction/) (ce dépôt) |

## Structure du dépôt

```
etl/          extraction, transformation, chargement + scripts d'exécution
prediction/   comparaison de modèles, optimisation, résultats (graphiques et prédictions 2026)
docs/         schéma en constellation de l'entrepôt
```

## 1. ETL (dossier `etl/`)

Pipeline Python qui alimente un entrepôt de données PostgreSQL à partir de deux bases MySQL (base globale et base santé-sécurité).

1. **Extraction** (`extract.py`) : lecture des tables sources avec SQLAlchemy et export en CSV.
2. **Transformation** (`transform.py`) : nettoyage, enrichissement (par exemple l'âge des agents) et construction des **tables de faits et des dimensions** d'un schéma en constellation, avec deux tables de faits (accidents et visites médicales) qui partagent des dimensions communes (voir [`docs/schema_constellation.md`](docs/schema_constellation.md)).
3. **Chargement** (`load.py`) : écriture des tables dans PostgreSQL.
4. **Orchestration** : `run_etl.py` enchaîne les trois étapes ; `run_etl_auto.py` relance le pipeline automatiquement toutes les 2 minutes.

```bash
cd etl
pip install -r requirements.txt
cp .env.example .env      # puis renseigner vos accès
python run_etl.py
```

## 2. Prédiction (dossier `prediction/`)

**Objectif** : estimer, pour chaque jour, la probabilité qu'un accident de travail survienne (classification binaire, événement rare).

- **Données** : accidents issus de l'entrepôt (table `fact_accidents`), transformés en calendrier journalier.
- **Variables** : mois, jour de la semaine, trimestre, week-end, début et fin de mois, encodage cyclique (sin/cos), nombre d'accidents sur les 7 et 30 jours précédents (décalés pour **éviter la fuite de données**).
- **Modèles comparés** : régression logistique, Random Forest, XGBoost (classes déséquilibrées prises en compte).
- **Optimisation** : `GridSearchCV` avec `TimeSeriesSplit` (5 découpages) sur le meilleur modèle, puis recherche du **seuil de décision optimal**.
- **Sélection** : modèle retenu selon le meilleur F1-score (Random Forest).
- **Sortie** : probabilités et niveaux de risque pour chaque jour de 2026 (`prediction/resultats/predictions_2026.csv`).

### Résultats (jeu de test, voir `prediction/resultats/`)

| Modèle | AUC-ROC | Recall | Précision | F1 |
|---|---|---|---|---|
| Régression logistique | 0,446 | 0,444 | 0,033 | 0,062 |
| Random Forest | 0,555 | 0,222 | 0,074 | 0,111 |
| XGBoost | 0,574 | 0,444 | 0,046 | 0,083 |
| **Random Forest optimisé** | **0,576** | 0,222 | 0,067 | 0,103 |

Ces résultats ont été obtenus pendant le stage sur les données réelles de la SRTB. La base n'étant plus accessible, le script ne peut pas être relancé tel quel. Le jeu de test contient très peu de jours avec accident, donc les métriques sont peu stables.

Les performances restent **modestes** : les accidents sont rares et les variables disponibles (calendrier et historique récent) sont limitées. Le modèle donne une indication de risque, pas une prévision fiable à l'échelle d'un jour.

```bash
cd prediction
pip install -r requirements.txt
cp .env.example .env      # puis renseigner vos accès
python comparaison_modeles.py
```
Le script nécessite une base PostgreSQL contenant la table `fact_accidents`. Pour un simple test de fonctionnement sans cette base, définir `USE_SYNTHETIC_DATA=1` (données synthétiques aléatoires : les résultats n'ont alors aucune valeur).

## Confidentialité

Les données de la SRTB (agents, visites médicales, accidents) sont **confidentielles** et ne sont pas publiées. Les fichiers `.env` ne sont jamais versionnés : utilisez `.env.example` comme modèle.

## Technologies

Python (Pandas, NumPy, scikit-learn, XGBoost, Matplotlib, Seaborn), SQLAlchemy, MySQL, PostgreSQL.

## Auteure

Nourhene Saidani – étudiante en Master Système d'Information Décisionnel – Data Science, ISGB.
