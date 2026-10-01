
import pandas as pd
# pandas = pour lire les fichiers CSV et manipuler les tableaux

from sqlalchemy import create_engine, text, types as sa
# create_engine = pour se connecter à PostgreSQL
# text = pour écrire des commandes SQL en sécurité
# types as sa = pour définir le type des colonnes (DATE, INTEGER, etc.)

from urllib.parse import quote_plus
# quote_plus = pour encoder le mot de passe (caractères spéciaux comme @ ou !)

import os
# os = pour vérifier si les fichiers existent

from dotenv import load_dotenv
# load_dotenv = pour lire les mots de passe depuis le fichier .env

from sqlalchemy.pool import NullPool
# NullPool = pour ne pas garder de connexions ouvertes inutilement

load_dotenv()  # On charge le fichier .env


# AFFICHAGE DU TITRE

print("="*60)
print("💾 CHARGEMENT")
print("="*60)


# 1. CHARGEMENT DES FICHIERS CSV TRANSFORMÉS

print("\n📌 1. Chargement des CSV...")

# Dictionnaire pour stocker tous les tableaux
data = {}

# Liste de tous les fichiers CSV à charger (ceux créés par transform.py)
files = ['dim_date.csv', 'dim_agent.csv', 'dim_affectation.csv', 'dim_agence.csv',
         'dim_type_visite.csv', 'dim_gravite_accident.csv', 'dim_statut_accident.csv',
         'dim_utilisateur.csv', 'fact_accidents.csv', 'fact_visites.csv']

# Pour chaque fichier
for file in files:
    filepath = f'data_transformed/{file}'  # Chemin du fichier
    
    # Si le fichier existe
    if os.path.exists(filepath):
        # On le lit avec pandas
        # .replace('.csv', '') enlève l'extension .csv pour garder juste le nom
        data[file.replace('.csv', '')] = pd.read_csv(filepath, encoding='utf-8-sig')
        print(f"   ✅ {file}: {len(data[file.replace('.csv', '')])} lignes")
    else:
        # Si le fichier n'existe pas (erreur)
        print(f"   ⚠️ {file} non trouvé")
        data[file.replace('.csv', '')] = pd.DataFrame()  # Tableau vide



# 2. CONNEXION À POSTGRESQL

print("\n📌 2. Connexion PostgreSQL...")

# On récupère les paramètres de connexion depuis le fichier .env
# Si une variable n'existe pas, on utilise une valeur par défaut
pg_host = os.getenv('PG_HOST', 'localhost')
pg_port = os.getenv('PG_PORT', '5432')
pg_user = os.getenv('PG_USER')
pg_password = os.getenv('PG_PASSWORD')
pg_database = os.getenv('PG_DATABASE')
if not (pg_user and pg_password and pg_database):
    raise SystemExit("Variables PG_* manquantes : copiez .env.example en .env et renseignez-le.")

# On construit la chaîne de connexion
# Format : postgresql://utilisateur:motdepasse@hôte:port/nom_base
pg_engine = create_engine(
    f"postgresql://{pg_user}:{quote_plus(pg_password)}@{pg_host}:{pg_port}/{pg_database}",
    poolclass=NullPool  # On ferme la connexion après usage
)

print("   ✅ Connecté à PostgreSQL")


# 3. DÉFINITION DES TYPES DE COLONNES

print("\n📌 3. Définition des types...")

# Pourquoi ? Parce que pandas devine parfois mal les types.
# On force les bons types : DATE, INTEGER, VARCHAR, etc.

# Table dim_date (le calendrier)
dtypes_dim_date = {
    'date_complete': sa.Date(),        # Une vraie date
    'id_date': sa.Integer(),           # Nombre entier (ex: 20241225)
    'annee': sa.Integer(),             # Année (2024)
    'mois': sa.Integer(),              # Mois (1 à 12)
    'mois_nom': sa.String(20),         # Texte (Janvier, Février...)
    'trimestre': sa.Integer(),         # Trimestre (1,2,3,4)
    'semaine': sa.Integer(),           # Numéro de semaine
    'jour': sa.Integer(),              # Jour du mois
    'jour_semaine': sa.Integer()       # Jour de la semaine (1=Lundi)
}

# Table dim_agent (les agents)
dtypes_dim_agent = {
    'matricule_agent': sa.Integer(),        # Numéro de matricule
    'nom': sa.String(100),                  # Nom (texte, max 100 caractères)
    'prenom': sa.String(100),               # Prénom
    'date_naissance': sa.Date(),            # Date de naissance
    'code_agence': sa.Integer(),            # Code de l'agence
    'code_affectation': sa.Integer(),       # Code du poste
    'direction': sa.String(100),            # Direction
    'date_derniere_visite': sa.Date(),      # Date de dernière visite
    'date_debut_inaptitude': sa.Date(),     # Début inaptitude
    'date_fin_inaptitude': sa.Date(),       # Fin inaptitude
    'date_prochaine_inaptitude': sa.Date(), # Prochaine inaptitude
    'statut': sa.String(20),                # Statut (actif, inactif...)
    'periodicite_jours': sa.Integer(),      # Périodicité des visites
    'date_prochaine_visite': sa.Date(),     # Prochaine visite prévue
    'created_at': sa.TIMESTAMP(),           # Date de création (avec heure)
    'updated_at': sa.TIMESTAMP(),           # Date de dernière modification
    'mot_de_passe': sa.String(255),         # Mot de passe (hashé)
    'role': sa.String(50),                  # Rôle (admin, agent...)
    'date_debut_reclassement': sa.Date(),   # Début reclassement
    'date_fin_reclassement': sa.Date(),     # Fin reclassement
    'date_prochaine_reclassement': sa.Date(), # Prochain reclassement
    'age': sa.Integer(),                    # Âge calculé
    'nom_complet': sa.String(200)           # Prénom + Nom
}

# Table dim_affectation (les postes de travail)
dtypes_dim_affectation = {
    'code_affectation': sa.Integer(),       # Code du poste
    'libelle_affectation': sa.String(100),  # Nom du poste
    'description': sa.String(255),          # Description
    'created_at': sa.TIMESTAMP(),           # Date de création
    'updated_at': sa.TIMESTAMP()            # Date de modification
}

# Table dim_agence (les agences)
dtypes_dim_agence = {
    'code_agence': sa.Integer(),            # Code de l'agence
    'nom_agence': sa.String(100),           # Nom de l'agence
    'ville': sa.String(100),                # Ville
    'adresse': sa.String(255),              # Adresse
    'telephone': sa.String(50),             # Téléphone
    'created_at': sa.TIMESTAMP(),           # Date de création
    'updated_at': sa.TIMESTAMP()            # Date de modification
}

# Table dim_utilisateur (les utilisateurs de l'application)
dtypes_dim_utilisateur = {
    'id_utilisateur': sa.Integer(),         # Identifiant unique
    'login': sa.String(100),                # Nom d'utilisateur
    'mot_de_passe': sa.String(255),         # Mot de passe (hashé)
    'role': sa.String(50),                  # Rôle (admin, agent...)
    'matricule_agent': sa.Integer(),        # Lien vers l'agent
    'derniere_connexion': sa.TIMESTAMP(),   # Date/heure dernière connexion
    'nombre_connexions': sa.Integer(),      # Compteur de connexions
    'date_creation': sa.TIMESTAMP()         # Date de création du compte
}

# Table dim_type_visite (les types de visite médicale)
dtypes_dim_type_visite = {
    'id_type_visite': sa.Integer(),          # Identifiant
    'libelle_type_visite': sa.String(50),    # Périodique, Reprise, etc.
    'duree_validite_jours': sa.Integer()     # Validité en jours (365, 1...)
}

# Table dim_gravite_accident (niveaux de gravité)
dtypes_dim_gravite = {
    'id_gravite': sa.Integer(),             # Identifiant
    'libelle_gravite': sa.String(50),       # Faible, Moyenne, Elevée, Critique
    'couleur_alerte': sa.String(20),        # Vert, Orange, Rouge, Noir
    'niveau': sa.Integer()                  # 1,2,3,4
}

# Table dim_statut_accident (statut de déclaration)
dtypes_dim_statut = {
    'id_statut': sa.Integer(),              # Identifiant
    'libelle_statut': sa.String(20),        # brouillon, declare
    'description': sa.String(255),          # Description
    'est_actif': sa.Boolean()               # Vrai/Faux
}

# Table fact_accidents (les accidents)
dtypes_fact_accidents = {
    'id_accident': sa.Integer(),            # Identifiant unique
    'numero_accident': sa.String(50),       # Numéro officiel
    'matricule_agent': sa.String(20),       # Agent concerné
    'date_accident': sa.Date(),             # Date de l'accident
    'heure_accident': sa.Time(),            # Heure de l'accident
    'lieu_accident': sa.String(150),        # Où ?
    'condition_accident': sa.String(255),   # Conditions météo, etc.
    'endroit_blessures': sa.String(100),    # Où sur le corps ?
    'nature_blessures': sa.String(100),     # Type de blessure
    'facteurs_materiels': sa.String(255),   # Matériel impliqué
    'mode_survenue': sa.String(255),        # Comment c'est arrivé
    'temoin1': sa.String(100),              # Premier témoin
    'temoin2': sa.String(100),              # Deuxième témoin
    'pv_existe': sa.Boolean(),              # Procès-verbal ?
    'numero_pv': sa.String(50),             # Numéro du PV
    'date_pv': sa.Date(),                   # Date du PV
    'tiers_responsable': sa.Boolean(),      # Tiers responsable ?
    'nom_tiers': sa.String(100),            # Nom du tiers
    'jour_arret': sa.Integer(),             # Nombre de jours d'arrêt
    'statut': sa.String(20),                # brouillon / declare
    'date_declaration_cnam': sa.Date(),     # Date déclaration à la CNAM
    'gravite': sa.String(20),               # Libellé gravité
    'created_by': sa.Integer(),             # Qui a créé
    'updated_by': sa.Integer(),             # Qui a modifié
    'id_agence': sa.Integer(),              # Lien vers dim_agence
    'id_affectation': sa.Integer(),         # Lien vers dim_affectation
    'id_date_accident': sa.Integer(),       # Lien vers dim_date
    'id_gravite': sa.Integer(),             # Lien vers dim_gravite
    'id_statut': sa.Integer(),              # Lien vers dim_statut
    'est_declare': sa.Boolean(),            # Vrai si déclaré
    'est_brouillon': sa.Boolean()           # Vrai si brouillon
}

# Table fact_visites (les visites médicales)
dtypes_fact_visites = {
    'matricule_visite': sa.Integer(),       # Identifiant de la visite
    'date_visite': sa.Date(),               # Date de la visite
    'heure_visite': sa.Time(),              # Heure de la visite
    'type_visite': sa.String(50),           # Périodique, Reprise...
    'medecin': sa.String(100),              # Nom du médecin
    'observation': sa.String(500),          # Observations du médecin
    'resultat': sa.String(100),             # Apte, Inapte, etc.
    'id_planning': sa.Integer(),            # Lien vers planning (si existe)
    'type_action': sa.String(50),           # Effectuée, Reportée...
    'ancien_statut': sa.String(50),         # Statut avant modification
    'nouveau_statut': sa.String(50),        # Statut après modification
    'motif_action': sa.String(255),         # Pourquoi modification ?
    'details_action': sa.String(1000),      # Détails de l'action
    'matricule_agent': sa.String(20),       # Agent concerné
    'source': sa.String(50),                # Source de la donnée
    'created_at': sa.TIMESTAMP(),           # Date de création
    'created_by': sa.Integer(),             # Qui a créé
    'updated_at': sa.TIMESTAMP(),           # Date de modification
    'updated_by': sa.Integer(),             # Qui a modifié
    'visite_originale_id': sa.Integer(),    # Visite originale (si modifiée)
    'source_originale': sa.String(50),      # Source originale
    'id_agence': sa.Integer(),              # Lien vers dim_agence
    'id_affectation': sa.Integer(),         # Lien vers dim_affectation
    'id_date_visite': sa.Integer(),         # Lien vers dim_date
    'id_type_visite': sa.Integer(),         # Lien vers dim_type_visite
    'visite_effectuee': sa.Boolean()        # Vrai si effectuée
}


# 4. SUPPRESSION DES ANCIENNES TABLES

print("\n📌 4. Suppression des anciennes tables...")

# L'ordre est important : on supprime d'abord les tables de faits (qui ont des clés étrangères),
# puis les dimensions. CASCADE supprime aussi les dépendances.

with pg_engine.connect() as conn:
    # dim_planning était dans une ancienne version, on le supprime au cas où
    conn.execute(text("DROP TABLE IF EXISTS dim_planning CASCADE"))
    
    # Tables de faits (dépendent des dimensions)
    conn.execute(text("DROP TABLE IF EXISTS fact_visites CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS fact_accidents CASCADE"))
    
    # Dimensions spécifiques aux faits
    conn.execute(text("DROP TABLE IF EXISTS dim_utilisateur CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS dim_statut_accident CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS dim_gravite_accident CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS dim_type_visite CASCADE"))
    
    # Dimensions partagées
    conn.execute(text("DROP TABLE IF EXISTS dim_agence CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS dim_affectation CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS dim_agent CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS dim_date CASCADE"))
    
    conn.commit()  # On valide toutes les suppressions
print("   ✅ Tables supprimées")


# 5. CHARGEMENT DES DONNÉES

print("\n📌 5. Chargement dans PostgreSQL...")

# On associe chaque nom de table à son dictionnaire de types
table_dtypes = {
    'dim_date': dtypes_dim_date,
    'dim_agent': dtypes_dim_agent,
    'dim_affectation': dtypes_dim_affectation,
    'dim_agence': dtypes_dim_agence,
    'dim_type_visite': dtypes_dim_type_visite,
    'dim_gravite_accident': dtypes_dim_gravite,
    'dim_statut_accident': dtypes_dim_statut,
    'dim_utilisateur': dtypes_dim_utilisateur,
    'fact_accidents': dtypes_fact_accidents,
    'fact_visites': dtypes_fact_visites
}

# Pour chaque table qu'on a chargée depuis les CSV
for name, df in data.items():
    if not df.empty:  # Si la table n'est pas vide
        try:
            # On récupère le dictionnaire de types pour cette table
            dtype = table_dtypes.get(name)
            
            if dtype:
                # to_sql = écrire dans PostgreSQL
                # name = nom de la table
                # pg_engine = connexion PostgreSQL
                # if_exists='replace' = supprime et recrée la table
                # index=False = ne pas écrire l'index pandas
                # dtype=dtype = force les types des colonnes
                df.to_sql(name, pg_engine, if_exists='replace', index=False, dtype=dtype)
            else:
                # Si pas de types définis (normalement ça n'arrive pas)
                df.to_sql(name, pg_engine, if_exists='replace', index=False)
            
            print(f"   ✅ {name}: {len(df)} lignes")
            
        except Exception as e:
            # Si une erreur arrive pendant le chargement
            print(f"   ❌ Erreur sur {name}: {e}")
            # On annule la transaction (ROLLBACK) pour ne pas avoir de données corrompues
            with pg_engine.connect() as conn:
                conn.execute(text("ROLLBACK"))
                conn.commit()



# 6. VÉRIFICATION FINALE

print("\n" + "="*60)
print("✅ CHARGEMENT TERMINÉ")
print("="*60)

print("\n📌 6. Vérification...")

# On vérifie que la table fact_visites a bien été créée
with pg_engine.connect() as conn:
    print("\n   fact_visites:")
    # On interroge PostgreSQL pour connaître les colonnes de la table fact_visites
    result = conn.execute(text("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'fact_visites' 
        ORDER BY ordinal_position
    """))
    # On affiche chaque colonne et son type
    for row in result:
        print(f"      - {row[0]}: {row[1]}")


# FIN

print("\n" + "="*60)
print("🎉 PRÊT POUR POWER BI")
print("="*60)