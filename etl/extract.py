

import pandas as pd
# pandas permet de manipuler des données sous forme de tableaux (DataFrames)

from sqlalchemy import create_engine, text
# create_engine : crée une connexion à une base de données
# text : permet d'écrire des requêtes SQL en toute sécurité

from urllib.parse import quote_plus
# quote_plus : encode les caractères spéciaux dans un mot de passe
# exemple : "mot@depasse" devient "mot%40depasse" (valide dans une URL)

import os
# os : permet d'interagir avec le système d'exploitation
# (vérifier si un dossier existe, créer un dossier, etc.)

from dotenv import load_dotenv
# load_dotenv : lit les variables d'environnement depuis le fichier .env
# (mots de passe stockés en sécurité, pas dans le code)

from datetime import datetime
# datetime : donne la date et l'heure actuelles pour l'affichage

# CHARGEMENT DES VARIABLES D'ENVIRONNEMENT

load_dotenv()
# Cette ligne lit le fichier .env qui contient les mots de passe
# Exemple de .env : MYSQL_GLOBAL_PASSWORD=secret123


# AFFICHAGE DE L'EN-TÊTE

print("="*60)
print("📤 PHASE D'EXTRACTION DES DONNÉES (EXTRACT)")
print("="*60)
print(f"📅 Date d'exécution: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("="*60)

# 1. CONNEXION AUX BASES DE DONNÉES SOURCES

print("\n📌 1. Connexion aux bases sources...")

# ----- CONNEXION À MYSQL BASE GLOBALE -----
try:
    # On récupère le mot de passe depuis .env et on l'encode
    pwd1 = quote_plus(os.getenv('MYSQL_GLOBAL_PASSWORD'))
    
    # On construit la chaîne de connexion
    # Format : mysql+pymysql://utilisateur:motdepasse@hôte:port/nom_base
    mysql_global_engine = create_engine(
        f"mysql+pymysql://{os.getenv('MYSQL_GLOBAL_USER')}:{pwd1}@"
        f"{os.getenv('MYSQL_GLOBAL_HOST')}:{os.getenv('MYSQL_GLOBAL_PORT')}/"
        f"{os.getenv('MYSQL_GLOBAL_DATABASE')}"
    )
    
    # On teste la connexion en exécutant une requête simple "SELECT 1"
    with mysql_global_engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    
    print("   ✅ MySQL - Base Globale")
    
except Exception as e:
    # Si la connexion échoue, on affiche l'erreur et on arrête le script
    print(f"   ❌ Erreur: {e}")
    exit(1)


# ----- CONNEXION À MYSQL SANTÉ/SÉCURITÉ -----
try:
    # Même processus pour la deuxième base de données
    pwd2 = quote_plus(os.getenv('MYSQL_SANTE_PASSWORD'))
    mysql_sante_engine = create_engine(
        f"mysql+pymysql://{os.getenv('MYSQL_SANTE_USER')}:{pwd2}@"
        f"{os.getenv('MYSQL_SANTE_HOST')}:{os.getenv('MYSQL_SANTE_PORT')}/"
        f"{os.getenv('MYSQL_SANTE_DATABASE')}"
    )
    with mysql_sante_engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    print("   ✅ MySQL - Santé/Sécurité")
    
except Exception as e:
    print(f"   ❌ Erreur: {e}")
    exit(1)


# 2. EXTRACTION DES TABLES DE LA BASE GLOBALE

print("\n📌 2. Extraction base globale...")

# Liste des tables à extraire depuis la base globale
tables_global = ['agent', 'agence', 'affectation']

# Dictionnaire pour stocker les données extraites
# Exemple : extracted_global['agent'] = DataFrame contenant tous les agents
extracted_global = {}

# On parcourt chaque table une par une
for table in tables_global:
    print(f"   → {table}...")
    
    try:
        # pd.read_sql exécute la requête SQL et retourne un DataFrame pandas
        # La requête "SELECT * FROM agent" lit TOUTES les colonnes et TOUTES les lignes
        df = pd.read_sql(f"SELECT * FROM {table}", mysql_global_engine)
        
        # On stocke le DataFrame dans le dictionnaire
        extracted_global[table] = df
        
        # On affiche le nombre de lignes extraites
        print(f"      ✅ {len(df)} lignes")
        
    except Exception as e:
        # Si la table n'existe pas ou erreur, on stocke un DataFrame vide
        print(f"      ❌ Erreur: {e}")
        extracted_global[table] = pd.DataFrame()

# 3. EXTRACTION DES TABLES DE LA BASE SANTÉ

print("\n📌 3. Extraction base santé-sécurité...")

# Liste des tables à extraire depuis la base santé
tables_sante = ['accident', 'visite', 'utilisateur']

# Dictionnaire pour stocker les données extraites
extracted_sante = {}

# On parcourt chaque table une par une
for table in tables_sante:
    print(f"   → {table}...")
    
    try:
        # Même processus que pour la base globale
        df = pd.read_sql(f"SELECT * FROM {table}", mysql_sante_engine)
        extracted_sante[table] = df
        print(f"      ✅ {len(df)} lignes")
        
    except Exception as e:
        # avertissement, pas forcément bloquant (table peut ne pas exister)
        print(f"      ⚠️ {table} non trouvée: {e}")
        extracted_sante[table] = pd.DataFrame()


# 4. SAUVEGARDE DES DONNÉES EN FICHIERS CSV

print("\n📌 4. Sauvegarde...")

# On vérifie si le dossier "data_extracted" existe
# Si non, on le crée (os.makedirs)
if not os.path.exists('data_extracted'):
    os.makedirs('data_extracted')

# ----- Sauvegarde des tables de la base globale -----
# .items() donne (nom_du_tableau, tableau) pour chaque élément
for name, df in extracted_global.items():
    if not df.empty:  # On sauvegarde uniquement si le tableau n'est pas vide
        # df.to_csv écrit le DataFrame dans un fichier CSV
        # f'data_extracted/{name}.csv' : chemin du fichier
        # index=False : ne pas écrire les numéros de ligne
        # encoding='utf-8-sig' : gestion des accents (é, è, ç) compatible Excel
        df.to_csv(f'data_extracted/{name}.csv', index=False, encoding='utf-8-sig')

# ----- Sauvegarde des tables de la base santé -----
for name, df in extracted_sante.items():
    if not df.empty:
        df.to_csv(f'data_extracted/{name}.csv', index=False, encoding='utf-8-sig')

# FIN DE L'EXTRACTION

print("\n✅ EXTRACTION TERMINÉE")
print("="*60)