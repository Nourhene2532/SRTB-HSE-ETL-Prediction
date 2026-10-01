
import pandas as pd
# pandas = une boîte à outils pour manipuler des tableaux de données
# (comme Excel, mais dans Python)

import numpy as np
# numpy = fait des calculs mathématiques (moyennes, sommes, etc.)

from datetime import datetime
# datetime = donne la date et l'heure actuelles (pour les afficher)

import os
# os = permet de travailler avec les dossiers et les fichiers
# (ex: vérifier si un dossier existe)

import re
# re = pour travailler avec du texte (chercher, remplacer)
# (pas vraiment utilisé ici, mais importé au cas où)


# AFFICHAGE DU TITRE DANS LA CONSOLE

print("="*60)    # Affiche une ligne de 60 signes égal (pour faire joli)
print("🔄 PHASE DE TRANSFORMATION DES DONNÉES (TRANSFORM)")
print("="*60)
print(f"📅 Date d'exécution: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
# datetime.now() = maintenant
# strftime(...) = transforme la date en texte lisible
print("="*60)
print(f"🎯 Base cible: entrepôt PostgreSQL")
print("="*60)


# FONCTION POUR ENLEVER LES DOUBLONS

def deduplicate_df(df, subset=None, keep='first'):
    """
    Cette fonction enlève les lignes en double dans un tableau.
    
    Exemple : si le même agent apparaît deux fois, on garde une seule ligne.
    
    df : le tableau à nettoyer
    subset : sur quelle(s) colonne(s) on regarde les doublons
             (ex: ['matricule_agent'] = on regarde le matricule)
    keep : 'first' = on garde la première ligne, 'last' = on garde la dernière
    """
    
    # Si le tableau est vide, on le retourne tel quel (rien à faire)
    if df.empty:
        return df
    
    # On compte combien de lignes il y a avant
    before = len(df)
    
    # Si on a dit sur quelles colonnes vérifier
    if subset:
        # On supprime les doublons sur ces colonnes
        df = df.drop_duplicates(subset=subset, keep=keep)
        # On affiche combien de lignes ont été supprimées
        print(f"      - Déduplication sur {subset}: {before} → {len(df)} lignes (supprimé {before - len(df)})")
    else:
        # Sinon, on vérifie toutes les colonnes
        df = df.drop_duplicates(keep=keep)
        print(f"      - Déduplication sur toutes les colonnes: {before} → {len(df)} lignes (supprimé {before - len(df)})")
    
    return df


# FONCTION POUR NETTOYER LES HEURES

def clean_heure(heure):
    """
    Cette fonction prend une heure dans n'importe quel format bizarre
    et la transforme en format standard HH:MM:SS
    
    Exemples :
    - "14:30"     → "14:30:00"
    - "2 days 14:30:00" → "14:30:00"
    - "14:30:25.123" → "14:30:25"
    """
    
    # Si l'heure est vide ou manquante, on retourne Rien (None)
    if pd.isna(heure) or heure == '':
        return None
    
    # On transforme en texte et on enlève les espaces
    h = str(heure).strip()
    
    # Cas 1 : l'heure contient "days" (ex: "2 days 14:30:00")
    if 'days' in h:
        parts = h.split('days')  # On coupe en deux : avant "days" et après "days"
        if len(parts) > 1:
            time_part = parts[1].strip()  # La partie après "days" contient l'heure
            if time_part.isdigit():
                # Si c'est juste un nombre (ex: "2 days 3") → c'est une heure
                hour = int(time_part)
                return f"{hour:02d}:00:00" if hour < 24 else None
            elif ':' in time_part:
                # Sinon, c'est une heure normale
                time_clean = time_part.split('.')[0]  # On enlève les millisecondes
                if len(time_clean) == 5:  # ex: "14:30"
                    time_clean += ':00'   # devient "14:30:00"
                return time_clean if len(time_clean) == 8 else None
    # Cas 2 : l'heure contient ":" (ex: "14:30")
    elif ':' in h:
        parts = h.split(':')
        if len(parts) >= 2:
            # On ajoute des zéros devant si nécessaire (ex: "4:30" → "04:30")
            return f"{parts[0].zfill(2)}:{parts[1].zfill(2)}:00"
    
    # Si rien ne correspond, on retourne Rien
    return None


# 1. CHARGEMENT DES FICHIERS CSV EXTRAITS

print("\n📌 1. Chargement des données extraites...")

# Dictionnaire pour stocker tous les tableaux
data = {}

# Liste des fichiers à charger
files = ['agent.csv', 'agence.csv', 'affectation.csv', 
         'accident.csv', 'visite.csv', 'utilisateur.csv']

# Pour chaque fichier
for file in files:
    filepath = f'data_extracted/{file}'  # Chemin du fichier
    
    # Si le fichier existe
    if os.path.exists(filepath):
        # On le lit avec pandas
        data[file.replace('.csv', '')] = pd.read_csv(filepath, encoding='utf-8-sig')
        print(f"   ✅ {file} chargé ({len(data[file.replace('.csv', '')])} lignes)")
    else:
        # Sinon, on affiche un avertissement
        print(f"   ⚠️ {file} non trouvé")
        data[file.replace('.csv', '')] = pd.DataFrame()  # Tableau vide



# 2. CRÉATION DU CALENDRIER (dim_date)

print("\n📌 2. Création de dim_date...")

# Liste pour stocker toutes les dates qu'on va trouver
all_dates = []

# On cherche toutes les dates d'accidents
if 'accident' in data and 'date_accident' in data['accident'].columns:
    # On convertit les dates en format date, on ignore les erreurs, on enlève les vides
    all_dates.extend(pd.to_datetime(data['accident']['date_accident'], errors='coerce').dropna())

# On cherche toutes les dates de visites
if 'visite' in data and 'date_visite' in data['visite'].columns:
    all_dates.extend(pd.to_datetime(data['visite']['date_visite'], errors='coerce').dropna())

# Si on a trouvé au moins une date
if all_dates:
    # Date la plus ancienne (arrondie au jour)
    min_date = min(all_dates).floor('D')
    # Date la plus récente (arrondie au jour)
    max_date = max(all_dates).ceil('D')
    # On crée une liste de TOUS les jours entre min et max
    date_range = pd.date_range(start=min_date, end=max_date, freq='D')
    
    # On crée un tableau avec une colonne 'date_complete'
    dim_date = pd.DataFrame({'date_complete': date_range})
    
    # On ajoute une colonne 'id_date' (ex: 20241225 pour le 25 décembre 2024)
    dim_date['id_date'] = dim_date['date_complete'].dt.strftime('%Y%m%d').astype(int)
    
    # On ajoute les autres colonnes utiles pour les analyses
    dim_date['annee'] = dim_date['date_complete'].dt.year        # 2024
    dim_date['mois'] = dim_date['date_complete'].dt.month       # 12
    dim_date['mois_nom'] = dim_date['date_complete'].dt.strftime('%B')  # Décembre
    dim_date['trimestre'] = dim_date['date_complete'].dt.quarter  # 4
    dim_date['semaine'] = dim_date['date_complete'].dt.isocalendar().week  # 52
    dim_date['jour'] = dim_date['date_complete'].dt.day         # 25
    dim_date['jour_semaine'] = dim_date['date_complete'].dt.dayofweek + 1  # 4 (mercredi)
    
    print(f"   ✅ dim_date: {len(dim_date)} lignes générées")
else:
    # Si aucune date trouvée, tableau vide
    dim_date = pd.DataFrame()



# 3. CRÉATION DES DIMENSIONS DE RÉFÉRENCE (CODÉES EN DUR)

print("\n📌 3. Création des dimensions de référence...")

# Les types de visite (liste fixe)
dim_type_visite = pd.DataFrame([
    {'id_type_visite': 1, 'libelle_type_visite': 'Périodique', 'duree_validite_jours': 365},
    {'id_type_visite': 2, 'libelle_type_visite': 'Reprise', 'duree_validite_jours': 1},
    {'id_type_visite': 3, 'libelle_type_visite': 'Reclassement', 'duree_validite_jours': 1},
    {'id_type_visite': 4, 'libelle_type_visite': 'Embauche', 'duree_validite_jours': 365}
])
print(f"   ✅ dim_type_visite: {len(dim_type_visite)} lignes")

# Les niveaux de gravité (liste fixe)
dim_gravite_accident = pd.DataFrame([
    {'id_gravite': 1, 'libelle_gravite': 'Faible', 'couleur_alerte': 'Vert', 'niveau': 1},
    {'id_gravite': 2, 'libelle_gravite': 'Moyenne', 'couleur_alerte': 'Orange', 'niveau': 2},
    {'id_gravite': 3, 'libelle_gravite': 'Elevée', 'couleur_alerte': 'Rouge', 'niveau': 3},
    {'id_gravite': 4, 'libelle_gravite': 'Critique', 'couleur_alerte': 'Noir', 'niveau': 4}
])
print(f"   ✅ dim_gravite_accident: {len(dim_gravite_accident)} lignes")

# Les statuts d'accident (liste fixe)
dim_statut_accident = pd.DataFrame([
    {'id_statut': 1, 'libelle_statut': 'brouillon', 'description': 'En cours de saisie', 'est_actif': False},
    {'id_statut': 2, 'libelle_statut': 'declare', 'description': 'Déclaré officiellement', 'est_actif': True}
])
print(f"   ✅ dim_statut_accident: {len(dim_statut_accident)} lignes")


# 4. TRANSFORMATION DE dim_agent (TABLE DES AGENTS)

print("\n📌 4. Transformation de dim_agent...")

# Si le fichier agent.csv a été chargé et n'est pas vide
if 'agent' in data and not data['agent'].empty:
    # On copie le tableau (pour ne pas modifier l'original)
    dim_agent = data['agent'].copy()
    print(f"   → {len(dim_agent)} lignes brutes")
    
    # On enlève les doublons (même matricule)
    dim_agent = deduplicate_df(dim_agent, subset=['matricule_agent'], keep='first')
    
    # Liste des colonnes qui contiennent des dates
    date_cols = ['date_naissance', 'date_derniere_visite', 'date_prochaine_visite',
                 'date_debut_inaptitude', 'date_fin_inaptitude', 'created_at', 'updated_at']
    
    # Pour chaque colonne de date
    for col in date_cols:
        if col in dim_agent.columns:
            # On convertit en vrai format date (pas du texte)
            dim_agent[col] = pd.to_datetime(dim_agent[col], errors='coerce')
    
    # On convertit les numéros d'agence en nombres (pas du texte)
    if 'code_agence' in dim_agent.columns:
        dim_agent['code_agence'] = pd.to_numeric(dim_agent['code_agence'], errors='coerce').fillna(-1).astype(int)
    
    # Pareil pour l'affectation
    if 'code_affectation' in dim_agent.columns:
        dim_agent['code_affectation'] = pd.to_numeric(dim_agent['code_affectation'], errors='coerce').fillna(-1).astype(int)
    
    # Pareil pour la périodicité
    if 'periodicite_jours' in dim_agent.columns:
        dim_agent['periodicite_jours'] = pd.to_numeric(dim_agent['periodicite_jours'], errors='coerce').fillna(0).astype(int)
    
    # Colonnes qui doivent être du texte
    text_cols = ['nom', 'prenom', 'direction', 'statut', 'role', 'mot_de_passe']
    for col in text_cols:
        if col in dim_agent.columns:
            # On remplace les valeurs vides par "" (texte vide)
            dim_agent[col] = dim_agent[col].fillna('').astype(str)
    
    # On calcule l'âge de l'agent (si on a sa date de naissance)
    if 'date_naissance' in dim_agent.columns:
        today = datetime.now()  # Date d'aujourd'hui
        # On calcule la différence en jours, on divise par 365, on arrondit
        dim_agent['age'] = ((today - dim_agent['date_naissance']).dt.days / 365).fillna(0).astype(int)
    
    # On crée une colonne avec le nom complet (prénom + nom)
    dim_agent['nom_complet'] = (dim_agent['prenom'] + ' ' + dim_agent['nom']).str.strip()
    
    # On remplace les code_agence = 0 par -1 (signifie "Non renseigné")
    dim_agent['code_agence'] = dim_agent['code_agence'].apply(lambda x: -1 if x == 0 else x)
    dim_agent['code_affectation'] = dim_agent['code_affectation'].apply(lambda x: -1 if x == 0 else x)
    
    # On crée deux dictionnaires : pour chaque matricule, quel code_agence et code_affectation
    # Ce dictionnaire servira plus tard pour les accidents et visites
    agent_agence = dict(zip(dim_agent['matricule_agent'].astype(str), dim_agent['code_agence']))
    agent_affectation = dict(zip(dim_agent['matricule_agent'].astype(str), dim_agent['code_affectation']))
    
    print(f"   ✅ dim_agent: {len(dim_agent)} lignes")
else:
    # Si le fichier n'existe pas, on crée des tableaux vides
    dim_agent = pd.DataFrame()
    agent_agence = {}
    agent_affectation = {}



# 5. TRANSFORMATION DE dim_affectation (TABLE DES POSTES)

print("\n📌 5. Transformation de dim_affectation...")

if 'affectation' in data and not data['affectation'].empty:
    dim_affectation = data['affectation'].copy()
    print(f"   → {len(dim_affectation)} lignes brutes")
    
    # On enlève les doublons (même code_affectation)
    dim_affectation = deduplicate_df(dim_affectation, subset=['code_affectation'], keep='first')
    
    # On convertit les codes en nombres
    dim_affectation['code_affectation'] = pd.to_numeric(dim_affectation['code_affectation'], errors='coerce').fillna(-1).astype(int)
    
    # On remplit les valeurs vides par ""
    dim_affectation['libelle_affectation'] = dim_affectation['libelle_affectation'].fillna('').astype(str)
    dim_affectation['description'] = dim_affectation['description'].fillna('').astype(str)
    
    # On convertit les dates si elles existent
    if 'created_at' in dim_affectation.columns:
        dim_affectation['created_at'] = pd.to_datetime(dim_affectation['created_at'], errors='coerce')
    if 'updated_at' in dim_affectation.columns:
        dim_affectation['updated_at'] = pd.to_datetime(dim_affectation['updated_at'], errors='coerce')
    
    print(f"   ✅ dim_affectation: {len(dim_affectation)} lignes")
else:
    dim_affectation = pd.DataFrame()



# 6. TRANSFORMATION DE dim_agence (TABLE DES AGENCES)

print("\n📌 6. Transformation de dim_agence...")

if 'agence' in data and not data['agence'].empty:
    dim_agence = data['agence'].copy()
    print(f"   → {len(dim_agence)} lignes brutes")
    
    # On enlève les doublons (même code_agence)
    dim_agence = deduplicate_df(dim_agence, subset=['code_agence'], keep='first')
    
    # On convertit les codes en nombres
    dim_agence['code_agence'] = pd.to_numeric(dim_agence['code_agence'], errors='coerce').fillna(-1).astype(int)
    
    # On remplit les valeurs vides par ""
    dim_agence['nom_agence'] = dim_agence['nom_agence'].fillna('').astype(str)
    dim_agence['ville'] = dim_agence['ville'].fillna('').astype(str)
    dim_agence['adresse'] = dim_agence['adresse'].fillna('').astype(str)
    dim_agence['telephone'] = dim_agence['telephone'].fillna('').astype(str)
    
    # On convertit les dates si elles existent
    if 'created_at' in dim_agence.columns:
        dim_agence['created_at'] = pd.to_datetime(dim_agence['created_at'], errors='coerce')
    if 'updated_at' in dim_agence.columns:
        dim_agence['updated_at'] = pd.to_datetime(dim_agence['updated_at'], errors='coerce')
    
    print(f"   ✅ dim_agence: {len(dim_agence)} lignes")
else:
    dim_agence = pd.DataFrame()


# 7. TRANSFORMATION DE dim_utilisateur (TABLE DES UTILISATEURS)

print("\n📌 7. Transformation de dim_utilisateur...")

if 'utilisateur' in data and not data['utilisateur'].empty:
    dim_utilisateur = data['utilisateur'].copy()
    print(f"   → {len(dim_utilisateur)} lignes brutes")
    
    # On enlève les doublons (même id_utilisateur)
    dim_utilisateur = deduplicate_df(dim_utilisateur, subset=['id_utilisateur'], keep='first')
    
    # On convertit les identifiants en nombres
    dim_utilisateur['id_utilisateur'] = pd.to_numeric(dim_utilisateur['id_utilisateur'], errors='coerce').fillna(0).astype(int)
    
    # les colonnes s'appellent 'Login', 'Mot_de_passe', 'Role' (majuscules)
    dim_utilisateur['login'] = dim_utilisateur['Login'].fillna('').astype(str)
    dim_utilisateur['mot_de_passe'] = dim_utilisateur['Mot_de_passe'].fillna('').astype(str)
    dim_utilisateur['role'] = dim_utilisateur['Role'].fillna('agent').astype(str).str.lower()
    dim_utilisateur['matricule_agent'] = dim_utilisateur['matricule_agent'].fillna(0).astype(int)
    
    # On convertit les dates
    dim_utilisateur['derniere_connexion'] = pd.to_datetime(dim_utilisateur['derniere_connexion'], errors='coerce')
    dim_utilisateur['nombre_connexions'] = pd.to_numeric(dim_utilisateur['nombre_connexions'], errors='coerce').fillna(0).astype(int)
    dim_utilisateur['date_creation'] = pd.to_datetime(dim_utilisateur['date_creation'], errors='coerce')
    
    # On supprime les anciennes colonnes (Login, Mot_de_passe, Role) car on les a renommées
    dim_utilisateur = dim_utilisateur.drop(columns=['Login', 'Mot_de_passe', 'Role'], errors='ignore')
    
    print(f"   ✅ dim_utilisateur: {len(dim_utilisateur)} lignes")
    print(f"   📊 Colonnes: {list(dim_utilisateur.columns)}")
else:
    dim_utilisateur = pd.DataFrame()


# 8. TRANSFORMATION DE fact_accidents (TABLE DES ACCIDENTS)

print("\n📌 8. Transformation de fact_accidents...")

if 'accident' in data and not data['accident'].empty:
    # On copie le tableau des accidents
    fact_accidents = data['accident'].copy()
    print(f"   → {len(fact_accidents)} lignes brutes")
    
    # On enlève les doublons (si plusieurs fois le même accident)
    if 'id_accident' in fact_accidents.columns:
        fact_accidents = deduplicate_df(fact_accidents, subset=['id_accident'], keep='first')
    else:
        fact_accidents = deduplicate_df(fact_accidents, keep='first')
    
    # On convertit les colonnes au bon type
    fact_accidents['id_accident'] = fact_accidents['id_accident'].astype(int)
    fact_accidents['numero_accident'] = fact_accidents['numero_accident'].fillna('').astype(str)
    fact_accidents['matricule_agent'] = fact_accidents['matricule_agent'].astype(str)
    fact_accidents['date_accident'] = pd.to_datetime(fact_accidents['date_accident'], errors='coerce')
    
    # On nettoie l'heure avec la fonction clean_heure
    fact_accidents['heure_accident'] = fact_accidents['heure_accident'].apply(clean_heure)
    
    # On remplit les champs texte vides par ""
    text_acc_fields = ['lieu_accident', 'condition_accident', 'endroit_blessures', 
                       'nature_blessures', 'facteurs_materiels', 'mode_survenue', 
                       'temoin1', 'temoin2', 'numero_pv', 'nom_tiers']
    for col in text_acc_fields:
        if col in fact_accidents.columns:
            fact_accidents[col] = fact_accidents[col].fillna('').astype(str)
    
    # On convertit les booléens (vrai/faux)
    if 'pv_existe' in fact_accidents.columns:
        fact_accidents['pv_existe'] = fact_accidents['pv_existe'].astype(str).str.lower().isin(['1', 'true', 'yes', 'oui'])
    if 'tiers_responsable' in fact_accidents.columns:
        fact_accidents['tiers_responsable'] = fact_accidents['tiers_responsable'].astype(str).str.lower().isin(['1', 'true', 'yes', 'oui'])
    
    # On convertit la date du PV
    if 'date_pv' in fact_accidents.columns:
        fact_accidents['date_pv'] = pd.to_datetime(fact_accidents['date_pv'], errors='coerce')
    
    # On convertit les jours d'arrêt en nombre (0 si vide)
    fact_accidents['jour_arret'] = pd.to_numeric(fact_accidents['jour_arret'], errors='coerce').fillna(0).astype(int)
    
    # Nettoyage du statut
    fact_accidents['statut'] = fact_accidents['statut'].fillna('brouillon').astype(str).str.lower()
    fact_accidents['statut'] = fact_accidents['statut'].apply(lambda x: 'declare' if x == 'declare' else 'brouillon')
    
    # Date de déclaration CNAM
    if 'date_declaration_cnam' in fact_accidents.columns:
        fact_accidents['date_declaration_cnam'] = pd.to_datetime(fact_accidents['date_declaration_cnam'], errors='coerce')
    
    # On convertit la gravité (texte → id)
    gravite_map = {'Faible': 1, 'Moyenne': 2, 'Elevée': 3, 'Critique': 4}
    fact_accidents['gravite'] = fact_accidents['gravite'].fillna('Faible').astype(str)
    fact_accidents['id_gravite'] = fact_accidents['gravite'].map(gravite_map).fillna(1).astype(int)
    
    # On convertit le statut (texte → id)
    statut_map = {'brouillon': 1, 'declare': 2}
    fact_accidents['id_statut'] = fact_accidents['statut'].map(statut_map).fillna(1).astype(int)
    
    # On ajoute les clés étrangères (agence, affectation) à partir du matricule
    fact_accidents['id_agence'] = fact_accidents['matricule_agent'].map(agent_agence).fillna(-1).astype(int)
    fact_accidents['id_affectation'] = fact_accidents['matricule_agent'].map(agent_affectation).fillna(-1).astype(int)
    
    # On ajoute la clé vers la date (format YYYYMMDD)
    fact_accidents['id_date_accident'] = fact_accidents['date_accident'].dt.strftime('%Y%m%d').fillna('0').astype(int)
    
    # Qui a créé/modifié l'accident ?
    if 'created_by' in fact_accidents.columns:
        fact_accidents['created_by'] = pd.to_numeric(fact_accidents['created_by'], errors='coerce').fillna(0).astype(int)
    if 'updated_by' in fact_accidents.columns:
        fact_accidents['updated_by'] = pd.to_numeric(fact_accidents['updated_by'], errors='coerce').fillna(0).astype(int)
    
    # On ajoute des colonnes booléennes pratiques
    fact_accidents['est_declare'] = fact_accidents['statut'] == 'declare'
    fact_accidents['est_brouillon'] = fact_accidents['statut'] == 'brouillon'
    
    # Résumé pour l'affichage
    print(f"   ✅ fact_accidents: {len(fact_accidents)} lignes")
    print(f"      - Statuts: brouillon={fact_accidents['est_brouillon'].sum()}, declare={fact_accidents['est_declare'].sum()}")
    print(f"      - Gravités: {fact_accidents['gravite'].value_counts().to_dict()}")
else:
    fact_accidents = pd.DataFrame()



# 8.5 AJOUT DES AGENTS MANQUANTS

print("\n📌 8.5 Vérification et ajout des agents manquants...")

# les accidents peuvent concerner des agents qui ne sont pas dans dim_agent
# Sinon, les jointures échoueraient

if 'fact_accidents' in locals() and not fact_accidents.empty and 'dim_agent' in locals() and not dim_agent.empty:
    # Liste des matricules présents dans les accidents
    matricules_fact = set(fact_accidents['matricule_agent'].unique())
    # Liste des matricules présents dans la table des agents
    matricules_dim = set(dim_agent['matricule_agent'].astype(str))
    # Les matricules qui sont dans les accidents mais pas dans la table agent
    matricules_manquants = matricules_fact - matricules_dim
    
    if matricules_manquants:
        print(f"   → {len(matricules_manquants)} agents manquants détectés, ajout automatique...")
        
        # On crée des lignes "Agent inconnu" pour chaque matricule manquant
        agents_manquants_data = []
        for matricule in matricules_manquants:
            agents_manquants_data.append({
                'matricule_agent': matricule,
                'nom': 'INCONNU',
                'prenom': '',
                'date_naissance': None,
                'code_agence': -1,
                'code_affectation': -1,
                'direction': '',
                'date_derniere_visite': None,
                'date_debut_inaptitude': None,
                'date_fin_inaptitude': None,
                'date_prochaine_inaptitude': None,
                'statut': 'actif',
                'periodicite_jours': 0,
                'date_prochaine_visite': None,
                'created_at': None,
                'updated_at': None,
                'mot_de_passe': '',
                'role': 'agent',
                'date_debut_reclassement': None,
                'date_fin_reclassement': None,
                'date_prochaine_reclassement': None,
                'age': 0,
                'nom_complet': f'Agent inconnu ({matricule})'
            })
        
        # On transforme la liste en tableau pandas
        agents_manquants = pd.DataFrame(agents_manquants_data)
        
        # On ajoute les nouveaux agents à la table dim_agent
        dim_agent = pd.concat([dim_agent, agents_manquants], ignore_index=True)
        
        # On met à jour les dictionnaires pour ces nouveaux agents
        for matricule in matricules_manquants:
            agent_agence[str(matricule)] = -1
            agent_affectation[str(matricule)] = -1
        
        print(f"   ✅ {len(matricules_manquants)} agents manquants ajoutés à dim_agent")
    else:
        print("   ✅ Tous les agents sont déjà présents dans dim_agent")
else:
    print("   ⚠️ Impossible de vérifier les agents manquants")


# 9. TRANSFORMATION DE fact_visites (TABLE DES VISITES)

print("\n📌 9. Transformation de fact_visites...")

if 'visite' in data and not data['visite'].empty:
    fact_visites = data['visite'].copy()
    print(f"   → {len(fact_visites)} lignes brutes")
    
    # On enlève les doublons
    if 'matricule_visite' in fact_visites.columns:
        fact_visites = deduplicate_df(fact_visites, subset=['matricule_visite'], keep='first')
    else:
        fact_visites = deduplicate_df(fact_visites, keep='first')
    
    # On convertit les colonnes
    fact_visites['matricule_visite'] = fact_visites['matricule_visite'].astype(int)
    fact_visites['date_visite'] = pd.to_datetime(fact_visites['date_visite'], errors='coerce')
    fact_visites['heure_visite'] = fact_visites['heure_visite'].apply(clean_heure)
    
    # On convertit le type de visite (texte → id)
    type_map = {'Périodique': 1, 'Reprise': 2, 'Reclassement': 3, 'Embauche': 4}
    fact_visites['type_visite'] = fact_visites['type_visite'].fillna('Périodique').astype(str)
    fact_visites['id_type_visite'] = fact_visites['type_visite'].map(type_map).fillna(1).astype(int)
    
    # On remplit les champs texte vides
    text_vis_fields = ['medecin', 'observation', 'resultat', 'type_action', 
                       'ancien_statut', 'nouveau_statut', 'motif_action', 
                       'details_action', 'source', 'source_originale']
    for col in text_vis_fields:
        if col in fact_visites.columns:
            fact_visites[col] = fact_visites[col].fillna('').astype(str)
    
    # On convertit les nombres
    if 'id_planning' in fact_visites.columns:
        fact_visites['id_planning'] = pd.to_numeric(fact_visites['id_planning'], errors='coerce').fillna(0).astype(int)
    
    fact_visites['matricule_agent'] = fact_visites['matricule_agent'].astype(str)
    
    # On convertit les dates
    if 'created_at' in fact_visites.columns:
        fact_visites['created_at'] = pd.to_datetime(fact_visites['created_at'], errors='coerce')
    if 'updated_at' in fact_visites.columns:
        fact_visites['updated_at'] = pd.to_datetime(fact_visites['updated_at'], errors='coerce')
    
    # On convertit les IDs
    if 'created_by' in fact_visites.columns:
        fact_visites['created_by'] = pd.to_numeric(fact_visites['created_by'], errors='coerce').fillna(0).astype(int)
    if 'updated_by' in fact_visites.columns:
        fact_visites['updated_by'] = pd.to_numeric(fact_visites['updated_by'], errors='coerce').fillna(0).astype(int)
    if 'visite_originale_id' in fact_visites.columns:
        fact_visites['visite_originale_id'] = pd.to_numeric(fact_visites['visite_originale_id'], errors='coerce').fillna(0).astype(int)
    
    # On ajoute les clés étrangères
    fact_visites['id_agence'] = fact_visites['matricule_agent'].map(agent_agence).fillna(-1).astype(int)
    fact_visites['id_affectation'] = fact_visites['matricule_agent'].map(agent_affectation).fillna(-1).astype(int)
    
    # Clé vers la date
    fact_visites['id_date_visite'] = fact_visites['date_visite'].dt.strftime('%Y%m%d').fillna('0').astype(int)
    
    # Flag : visite effectuée ou non
    fact_visites['visite_effectuee'] = (fact_visites['type_action'].astype(str).str.upper() == 'EFFECTUEE')
    
    # Résumé pour l'affichage
    print(f"      - Visites effectuées: {fact_visites['visite_effectuee'].sum()}")
    print(f"      - Types action: {fact_visites['type_action'].value_counts().to_dict()}")
    
    print(f"   ✅ fact_visites: {len(fact_visites)} lignes")
    print(f"      - Types visite: {fact_visites['type_visite'].value_counts().to_dict()}")
else:
    fact_visites = pd.DataFrame()



# 10. AJOUT DES LIGNES "NON RENSEIGNÉ"

print("\n📌 10. Ajout des lignes 'Non renseigné'...")

#  les clés étrangères qui pointent vers -1 aient une correspondance
# Sinon, les jointures échouent

# Pour dim_agence
if not dim_agence.empty:
    if -1 not in dim_agence['code_agence'].values:
        new_row = pd.DataFrame({
            'code_agence': [-1],
            'nom_agence': ['Non renseigné'],
            'ville': [''],
            'adresse': [''],
            'telephone': [''],
            'created_at': [None],
            'updated_at': [None]
        })
        dim_agence = pd.concat([dim_agence, new_row], ignore_index=True)
        print(f"   ✅ Ligne 'Non renseigné' ajoutée à dim_agence")
    else:
        print(f"   ✅ Ligne 'Non renseigné' existe déjà dans dim_agence")

# Pour dim_affectation
if not dim_affectation.empty:
    if -1 not in dim_affectation['code_affectation'].values:
        new_row = pd.DataFrame({
            'code_affectation': [-1],
            'libelle_affectation': ['Non renseigné'],
            'description': [''],
            'created_at': [None],
            'updated_at': [None]
        })
        dim_affectation = pd.concat([dim_affectation, new_row], ignore_index=True)
        print(f"   ✅ Ligne 'Non renseigné' ajoutée à dim_affectation")
    else:
        print(f"   ✅ Ligne 'Non renseigné' existe déjà dans dim_affectation")

# Pour dim_agent
if not dim_agent.empty:
    if -1 not in dim_agent['matricule_agent'].values:
        new_row = pd.DataFrame({
            'matricule_agent': [-1],
            'nom': ['Non renseigné'],
            'prenom': [''],
            'date_naissance': [None],
            'code_agence': [-1],
            'code_affectation': [-1],
            'direction': [''],
            'date_derniere_visite': [None],
            'date_debut_inaptitude': [None],
            'date_fin_inaptitude': [None],
            'date_prochaine_inaptitude': [None],
            'statut': ['actif'],
            'periodicite_jours': [0],
            'date_prochaine_visite': [None],
            'created_at': [None],
            'updated_at': [None],
            'mot_de_passe': [''],
            'role': ['agent'],
            'date_debut_reclassement': [None],
            'date_fin_reclassement': [None],
            'date_prochaine_reclassement': [None],
            'age': [0],
            'nom_complet': ['Agent non renseigné']
        })
        dim_agent = pd.concat([dim_agent, new_row], ignore_index=True)
        print(f"   ✅ Ligne 'Agent non renseigné' ajoutée à dim_agent")
    else:
        print(f"   ✅ Ligne 'Agent non renseigné' existe déjà dans dim_agent")

# On met à jour les dictionnaires pour l'agent -1
agent_agence[-1] = -1
agent_affectation[-1] = -1



# 11. SAUVEGARDE DES FICHIERS TRANSFORMÉS

print("\n📌 11. Sauvegarde des données transformées...")

# On crée le dossier s'il n'existe pas
if not os.path.exists('data_transformed'):
    os.makedirs('data_transformed')

# Liste de toutes les tables à sauvegarder
tables_to_save = [
    ('dim_date', dim_date),
    ('dim_agent', dim_agent),
    ('dim_affectation', dim_affectation),
    ('dim_agence', dim_agence),
    ('dim_type_visite', dim_type_visite),
    ('dim_gravite_accident', dim_gravite_accident),
    ('dim_statut_accident', dim_statut_accident),
    ('dim_utilisateur', dim_utilisateur),
    ('fact_accidents', fact_accidents),
    ('fact_visites', fact_visites)
]

# Pour chaque table
for name, df in tables_to_save:
    if not df.empty:
        # On sauvegarde en CSV
        df.to_csv(f'data_transformed/{name}.csv', index=False, encoding='utf-8-sig')
        print(f"   ✅ {name}.csv sauvegardé ({len(df)} lignes)")


# FIN

print("\n" + "="*60)
print("📊 RÉSUMÉ FINAL")
print("="*60)
print("✅ TRANSFORMATION TERMINÉE")
print("="*60)