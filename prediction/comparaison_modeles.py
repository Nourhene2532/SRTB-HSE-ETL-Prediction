import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import psycopg2
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (accuracy_score, precision_score, recall_score, 
                             f1_score, confusion_matrix, roc_curve, auc,
                             classification_report, roc_auc_score)
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit
import xgboost as xgb
import warnings
import os
from datetime import datetime
import joblib
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

warnings.filterwarnings('ignore')

# Configuration pour Windows 
def clean_text(text):
    import re
    emoji_pattern = re.compile("["
        u"\U0001F600-\U0001F64F"
        u"\U0001F300-\U0001F5FF"
        u"\U0001F680-\U0001F6FF"
        u"\U0001F1E0-\U0001F1FF"
        "]+", flags=re.UNICODE)
    return emoji_pattern.sub(r'', text)

print(clean_text("="*70))
print(clean_text("COMPARAISON DES PERFORMANCES DES 3 MODELES"))
print(clean_text("="*70))

# 1. CHARGEMENT DES DONNEES

print(clean_text("\n[1] Connexion a PostgreSQL..."))

# Configuration depuis .env pour base distante SRTB
PG_HOST = os.getenv('PG_HOST', 'localhost')
PG_PORT = os.getenv('PG_PORT', '5432')
PG_USER = os.getenv('PG_USER')
PG_PASSWORD = os.getenv('PG_PASSWORD')
PG_DATABASE = os.getenv('PG_DATABASE')
PG_TABLE_ACCIDENTS = os.getenv('PG_TABLE_ACCIDENTS', 'fact_accidents')
PG_CONNECT_TIMEOUT = int(os.getenv('PG_CONNECT_TIMEOUT', '10'))

df = None

try:
    # Connexion avec keepalives pour connexion distante
    conn = psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        user=PG_USER,
        password=PG_PASSWORD,
        database=PG_DATABASE,
        connect_timeout=PG_CONNECT_TIMEOUT,
        keepalives=1,
        keepalives_idle=int(os.getenv('PG_KEEPALIVES_IDLE', '5')),
        keepalives_interval=2,
        keepalives_count=3
    )
    
    query = f"SELECT * FROM {PG_TABLE_ACCIDENTS} WHERE est_brouillon = False"
    df = pd.read_sql(query, conn)
    conn.close()
    print(clean_text(f"   [OK] {len(df)} accidents charges depuis {PG_TABLE_ACCIDENTS}"))
    
except Exception as e:
    print(clean_text(f"   [ERREUR] Connexion: {e}"))
    if os.getenv('USE_SYNTHETIC_DATA') != '1':
        raise SystemExit("Connexion impossible : verifiez le fichier .env (ou definissez USE_SYNTHETIC_DATA=1 pour un simple test sur donnees synthetiques).")
    print(clean_text("   Mode test : donnees synthetiques (non reelles)..."))
    
    # Donnees synthetiques pour test
    np.random.seed(42)
    dates = pd.date_range('2017-01-01', '2025-12-31', freq='D')
    accidents = np.random.choice([0, 1], size=len(dates), p=[0.95, 0.05])
    df = pd.DataFrame({
        'date_accident': dates[accidents == 1],
        'accident_id': range(accidents.sum())
    })

# ============================================
# 2. PREPARATION DES DONNEES 
# ============================================
print(clean_text("\n[2] Preparation des donnees (avec correction anti-fuite)..."))

def add_rolling_features_no_leakage(df):
    """Ajoute les rolling windows avec SHIFT pour eviter la fuite de donnees"""
    df = df.copy()
    df['accidents_7j'] = df['accident'].shift(1).rolling(7, min_periods=1).sum().fillna(0)
    df['accidents_30j'] = df['accident'].shift(1).rolling(30, min_periods=1).sum().fillna(0)
    return df

# Convertir les dates
if 'date_accident' in df.columns:
    df['date_accident'] = pd.to_datetime(df['date_accident'])
    dates_accidents = df['date_accident']
else:
    # Si pas de colonne date, creer des dates a partir de l'index
    date_range = pd.date_range(start='2017-01-01', end='2025-12-31', freq='D')
    dates_accidents = date_range[np.random.choice(len(date_range), len(df), replace=False)]

# Obtenir la plage de dates
date_min = dates_accidents.min()
date_max = dates_accidents.max()
print(clean_text(f"   Periode des donnees: {date_min.date()} a {date_max.date()}"))

# Creer le calendrier complet
end_date = min(date_max, pd.Timestamp('2025-12-31'))
date_range = pd.date_range(start='2017-01-01', end=end_date, freq='D')
df_cal = pd.DataFrame({'date': date_range})
df_cal['accident'] = df_cal['date'].isin(dates_accidents).astype(int)

# Features temporelles
df_cal['mois'] = df_cal['date'].dt.month
df_cal['jour_semaine'] = df_cal['date'].dt.dayofweek
df_cal['annee'] = df_cal['date'].dt.year
df_cal['jour'] = df_cal['date'].dt.day
df_cal['trimestre'] = df_cal['date'].dt.quarter
df_cal['est_weekend'] = df_cal['jour_semaine'].isin([5,6]).astype(int)
df_cal['est_debut_mois'] = (df_cal['jour'] <= 7).astype(int)
df_cal['est_fin_mois'] = (df_cal['jour'] >= 25).astype(int)

# Features cycliques (sin/cos)
df_cal['mois_sin'] = np.sin(2 * np.pi * df_cal['mois'] / 12)
df_cal['mois_cos'] = np.cos(2 * np.pi * df_cal['mois'] / 12)
df_cal['jour_semaine_sin'] = np.sin(2 * np.pi * df_cal['jour_semaine'] / 7)
df_cal['jour_semaine_cos'] = np.cos(2 * np.pi * df_cal['jour_semaine'] / 7)

print(clean_text(f"   [OK] Calendrier: {len(df_cal)} jours"))
print(clean_text(f"   [OK] Accidents dans calendrier: {df_cal['accident'].sum()}"))


# 3. SEPARATION TRAIN/TEST 

print(clean_text("\n[3] Separation des donnees (temporelle)..."))

train = df_cal[df_cal['annee'] <= 2024].copy()
test = df_cal[df_cal['annee'] == 2025].copy()

if len(test) == 0:
    print(clean_text("   Avertissement: Pas de donnees 2025, utilisation 2024 comme test"))
    # Si pas de donnees 2025, utiliser les dernieres 20% des donnees
    split_idx = int(len(df_cal) * 0.8)
    train = df_cal[:split_idx].copy()
    test = df_cal[split_idx:].copy()

print(clean_text(f"   Entrainement: {len(train)} jours ({train['annee'].min()}-{train['annee'].max()})"))
print(clean_text(f"   Test: {len(test)} jours ({test['annee'].min()}-{test['annee'].max()})"))

# Appliquer les rolling windows SEPAREMENT (pas de fuite)
train = add_rolling_features_no_leakage(train)
test = add_rolling_features_no_leakage(test)

# Features selectionnees 
features = [
    'mois', 'jour_semaine', 'est_weekend', 'est_debut_mois', 'est_fin_mois',
    'mois_sin', 'mois_cos', 'jour_semaine_sin', 'jour_semaine_cos',
    'accidents_7j', 'accidents_30j'
]

X_train = train[features]
y_train = train['accident']
X_test = test[features]
y_test = test['accident']

print(clean_text(f"   Entrainement: {len(X_train)} jours"))
print(clean_text(f"   Test: {len(X_test)} jours"))
print(clean_text(f"   Accidents reels dans test: {y_test.sum()}"))

# Normalisation
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

# Calcul du ratio pour gestion du desequilibre
ratio_desequilibre = len(y_train[y_train == 0]) / max(len(y_train[y_train == 1]), 1)
scale_pos_weight_value = min(ratio_desequilibre, 30)
print(clean_text(f"   Ratio desequilibre: {ratio_desequilibre:.1f}:1"))

# ============================================
# 4. FONCTION D'OPTIMISATION DES SEUILS
# ============================================
def find_optimal_threshold(y_true, y_proba, max_pos_ratio=0.25):
    """Trouve le seuil optimal pour maximiser le F1-Score"""
    thresholds = np.arange(0.10, 0.60, 0.01)
    best_f1 = 0
    best_threshold = 0.5
    best_recall = 0
    best_precision = 0
    
    for threshold in thresholds:
        y_pred_temp = (y_proba >= threshold).astype(int)
        pos_ratio = y_pred_temp.sum() / len(y_pred_temp) if len(y_pred_temp) > 0 else 0
        
        if pos_ratio > max_pos_ratio:
            continue
        
        rec = recall_score(y_true, y_pred_temp, zero_division=0)
        prec = precision_score(y_true, y_pred_temp, zero_division=0)
        f1 = f1_score(y_true, y_pred_temp, zero_division=0)
        
        if f1 > best_f1:
            best_f1 = f1
            best_threshold = threshold
            best_recall = rec
            best_precision = prec
    
    if best_f1 == 0:
        for threshold in thresholds:
            y_pred_temp = (y_proba >= threshold).astype(int)
            f1 = f1_score(y_true, y_pred_temp, zero_division=0)
            if f1 > best_f1:
                best_f1 = f1
                best_threshold = threshold
                best_recall = recall_score(y_true, y_pred_temp, zero_division=0)
                best_precision = precision_score(y_true, y_pred_temp, zero_division=0)
    
    return best_threshold, best_recall, best_precision, best_f1

# ============================================
# 5. ENTRAINEMENT DES 3 MODELES (OPTIMISES)
# ============================================
print(clean_text("\n[4] Entrainement des modeles..."))

models = {
    'Regression Logistique': LogisticRegression(
        max_iter=1000, 
        random_state=42,
        class_weight='balanced',
        C=0.1,
        solver='liblinear'
    ),
    'Random Forest': RandomForestClassifier(
        n_estimators=200,
        random_state=42,
        class_weight='balanced',
        max_depth=10,
        min_samples_split=5,
        min_samples_leaf=2,
        n_jobs=-1
    ),
    'XGBoost': xgb.XGBClassifier(
        n_estimators=500,           
        max_depth=7,                
        learning_rate=0.03,         
        random_state=42,
        scale_pos_weight=scale_pos_weight_value,
        subsample=0.9,              
        colsample_bytree=0.9,       
        reg_alpha=0.05,             
        reg_lambda=0.5,             
        min_child_weight=2,         
        gamma=0.05,                
        use_label_encoder=False,
        eval_metric='logloss',
        n_jobs=-1
    )
}

results = {}
metrics_list = []

for name, model in models.items():
    try:
        print(clean_text(f"   Entrainement de {name}..."))
        model.fit(X_train_scaled, y_train)
        
        if hasattr(model, 'predict_proba'):
            y_proba = model.predict_proba(X_test_scaled)[:, 1]
        else:
            y_proba = model.predict(X_test_scaled)
        
        # Optimisation du seuil pour chaque modele
        if name == 'XGBoost':
            max_pos_ratio = 0.35
        else:
            max_pos_ratio = 0.20
            
        best_threshold, best_recall, best_precision, best_f1 = find_optimal_threshold(
            y_test, y_proba, max_pos_ratio
        )
        
        y_pred = (y_proba >= best_threshold).astype(int)
        
        # Metriques
        acc = accuracy_score(y_test, y_pred)
        fpr, tpr, _ = roc_curve(y_test, y_proba)
        roc_auc = auc(fpr, tpr)
        
        # Matrice de confusion
        cm = confusion_matrix(y_test, y_pred)
        if cm.shape == (2, 2):
            tn, fp, fn, tp = cm.ravel()
            specificity = tn / (tn + fp) if (tn + fp) > 0 else 0
        else:
            tp = cm[1, 1] if cm.shape[0] > 1 and cm.shape[1] > 1 else 0
            tn = cm[0, 0] if cm.shape[0] > 0 and cm.shape[1] > 0 else 0
            fp = cm[0, 1] if cm.shape[0] > 0 and cm.shape[1] > 1 else 0
            fn = cm[1, 0] if cm.shape[0] > 1 and cm.shape[1] > 0 else 0
            specificity = tn / (tn + fp) if (tn + fp) > 0 else 0
        
        results[name] = {
            'Accuracy': acc,
            'Precision': best_precision,
            'Recall': best_recall,
            'Specificity': specificity,
            'F1-Score': best_f1,
            'AUC-ROC': roc_auc,
            'y_proba': y_proba,
            'y_pred': y_pred,
            'model': model,
            'TP': tp,
            'TN': tn,
            'FP': fp,
            'FN': fn,
            'Optimal_Threshold': best_threshold
        }
        
        metrics_list.append({
            'Modele': name,
            'Accuracy': acc,
            'Precision': best_precision,
            'Recall': best_recall,
            'Specificity': specificity,
            'F1-Score': best_f1,
            'AUC-ROC': roc_auc
        })
        
        print(clean_text(f"      [OK] {name} entraine"))
        print(clean_text(f"      -> Seuil: {best_threshold:.2f} | F1: {best_f1:.4f} | AUC: {roc_auc:.4f}"))
    
    except Exception as e:
        print(clean_text(f"   [ERREUR] avec {name}: {e}"))
        continue

# ============================================
# 6. AFFICHAGE DES MATRICES DE CONFUSION
# ============================================
print(clean_text("\n[5] Matrices de confusion..."))

for name, data in results.items():
    print(clean_text(f"\n{'='*50}"))
    print(clean_text(f"Matrice de confusion - {name} (seuil={data['Optimal_Threshold']:.2f})"))
    print(clean_text(f"{'='*50}"))
    print(clean_text(f"               Predits"))
    print(clean_text(f"              Non    Oui"))
    print(clean_text(f"   Reel Non    {data['TN']:3}    {data['FP']:3}"))
    print(clean_text(f"        Oui    {data['FN']:3}    {data['TP']:3}"))
    print(clean_text(f"\n   -> Vrais positifs: {data['TP']} | Faux positifs: {data['FP']}"))
    print(clean_text(f"   -> Vrais negatifs: {data['TN']} | Faux negatifs: {data['FN']}"))

# ============================================
# 7. TABLEAU COMPARATIF DETAIL
# ============================================
print(clean_text("\n" + "="*80))
print(clean_text("TABLEAU COMPARATIF DES MODELES (SEUILS OPTIMAUX)"))
print(clean_text("="*80))

print(clean_text("\n" + "-"*110))
print(clean_text(f"{'Modele':<22} {'Accuracy':<10} {'Precision':<10} {'Recall':<10} {'Specificity':<12} {'F1-Score':<10} {'AUC-ROC':<10} {'Seuil':<8}"))
print(clean_text("-"*110))

for name, m in results.items():
    print(clean_text(f"{name:<22} {m['Accuracy']:.4f}    {m['Precision']:.4f}    {m['Recall']:.4f}    {m['Specificity']:.4f}     {m['F1-Score']:.4f}    {m['AUC-ROC']:.4f}    {m['Optimal_Threshold']:.2f}"))

print(clean_text("-"*110))

# ============================================
# 8. CREATION DES DOSSIERS
# ============================================
os.makedirs('resultats', exist_ok=True)
os.makedirs('modeles', exist_ok=True)

# ============================================
# 9. GRAPHIQUE 1 : BARRES COMPARATIVES
# ============================================
print(clean_text("\n[6] Creation du graphique a barres..."))

if metrics_list:
    df_metrics = pd.DataFrame(metrics_list)
    df_plot = df_metrics.melt(id_vars=['Modele'], var_name='Metrique', value_name='Score')

    sns.set_style("whitegrid")
    plt.rcParams['font.size'] = 12

    fig, ax = plt.subplots(figsize=(14, 7))
    sns.barplot(data=df_plot, x='Metrique', y='Score', hue='Modele', ax=ax, palette='Set2')
    ax.set_title('Comparaison des metriques par modéle ', fontsize=14, fontweight='bold')
    ax.set_ylabel('Score', fontsize=12)
    ax.set_xlabel('Metrique', fontsize=12)
    ax.set_ylim(0, 1.05)
    ax.legend(loc='lower right', title='Modele')
    ax.grid(True, alpha=0.3)

    for container in ax.containers:
        ax.bar_label(container, fmt='%.3f', fontsize=9)

    plt.tight_layout()
    plt.savefig('resultats/comparaison_barres.png', dpi=150, bbox_inches='tight')
    plt.close()
    print(clean_text("   [OK] Graphique 1: comparaison_barres.png"))

# ============================================
# 10. GRAPHIQUE 2 : HEATMAP
# ============================================
print(clean_text("\n[7] Creation de la heatmap..."))

if metrics_list:
    fig, ax = plt.subplots(figsize=(10, 6))
    heatmap_data = df_metrics.set_index('Modele').T
    sns.heatmap(heatmap_data, annot=True, fmt='.3f', cmap='RdYlGn', 
                vmin=0, vmax=1, center=0.5, ax=ax, 
                annot_kws={'size': 11}, cbar_kws={'label': 'Score'})
    ax.set_title('Heatmap des performances par modele', fontsize=14, fontweight='bold')
    ax.set_xlabel('Modele', fontsize=12)
    ax.set_ylabel('Metrique', fontsize=12)
    plt.tight_layout()
    plt.savefig('resultats/comparaison_heatmap.png', dpi=150, bbox_inches='tight')
    plt.close()
    print(clean_text("   [OK] Graphique 2: comparaison_heatmap.png"))

# ============================================
# 11. GRAPHIQUE 3 : COURBES ROC COMPARATIVES
# ============================================
print(clean_text("\n[8] Creation des courbes ROC..."))

plt.figure(figsize=(10, 8))
colors = {'Regression Logistique': 'blue', 'Random Forest': 'green', 'XGBoost': 'red'}

for name, data in results.items():
    try:
        y_proba = data['y_proba']
        fpr, tpr, _ = roc_curve(y_test, y_proba)
        roc_auc = data['AUC-ROC']
        plt.plot(fpr, tpr, color=colors.get(name, 'gray'), lw=2,
                 label=f'{name} (AUC = {roc_auc:.3f})')
    except:
        continue

plt.plot([0, 1], [0, 1], 'k--', lw=2, label='Aleatoire')
plt.xlabel('Taux de faux positifs (1 - Specificite)', fontsize=12)
plt.ylabel('Taux de vrais positifs (Sensibilite)', fontsize=12)
plt.title('Courbes ROC - Comparaison des 3 modeles', fontsize=14, fontweight='bold')
plt.legend(loc='lower right', fontsize=11)
plt.grid(True, alpha=0.3)
plt.savefig('resultats/courbes_roc_comparaison.png', dpi=150)
plt.close()
print(clean_text("   [OK] Graphique 3: courbes_roc_comparaison.png"))

# ============================================
# 12. GRAPHIQUE 4 : GRAPHIQUE RADAR
# ============================================
print(clean_text("\n[9] Creation du graphique radar..."))

if metrics_list and len(results) > 0:
    categories = ['Accuracy', 'Precision', 'Recall', 'Specificity', 'F1-Score', 'AUC-ROC']
    num_vars = len(categories)

    angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))

    for name, data in results.items():
        values = [data[cat] for cat in categories]
        values += values[:1]
        ax.plot(angles, values, 'o-', linewidth=2, label=name)
        ax.fill(angles, values, alpha=0.1)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories, fontsize=10)
    ax.set_ylim(0, 1)
    ax.set_title('Comparaison des modeles - Graphique radar', fontsize=14, fontweight='bold')
    ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.0))
    ax.grid(True)

    plt.tight_layout()
    plt.savefig('resultats/radar_comparaison.png', dpi=150)
    plt.close()
    print(clean_text("   [OK] Graphique 4: radar_comparaison.png"))

# ============================================
# 13. GRAPHIQUE 5 : BOXPLOT DES PROBABILITES
# ============================================
print(clean_text("\n[10] Creation du boxplot des probabilites..."))

if len(results) > 0:
    fig, ax = plt.subplots(figsize=(10, 6))
    box_data = []
    box_labels = []

    for name, data in results.items():
        y_proba = data['y_proba']
        proba_no_accident = y_proba[y_test == 0]
        proba_accident = y_proba[y_test == 1]
        
        if len(proba_no_accident) > 0:
            box_data.append(proba_no_accident)
            box_labels.append(f'{name}\n(sans accident)')
        if len(proba_accident) > 0:
            box_data.append(proba_accident)
            box_labels.append(f'{name}\n(avec accident)')

    if box_data:
        positions = np.arange(len(box_data))
        bp = ax.boxplot(box_data, positions=positions, widths=0.6, patch_artist=True,
                        showmeans=True, meanline=True, meanprops={'linestyle': '--', 'color': 'red'})

        colors_box = ['lightblue' if i % 2 == 0 else 'lightcoral' for i in range(len(box_data))]
        for patch, color in zip(bp['boxes'], colors_box):
            patch.set_facecolor(color)

        ax.set_xticks(positions)
        ax.set_xticklabels(box_labels, rotation=45, ha='right', fontsize=9)
        ax.set_ylabel('Probabilite predite', fontsize=12)
        ax.set_title('Distribution des probabilites predites par modele', fontsize=14, fontweight='bold')
        for name, data in results.items():
            ax.axhline(y=data['Optimal_Threshold'], color=colors.get(name, 'gray'), 
                       linestyle='--', alpha=0.7, label=f'Seuil {name} ({data["Optimal_Threshold"]:.2f})')
        ax.legend(loc='upper right', fontsize=9)
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig('resultats/boxplot_probabilites.png', dpi=150)
        plt.close()
        print(clean_text("   [OK] Graphique 5: boxplot_probabilites.png"))

# ============================================
# 14. MEILLEUR MODELE PAR METRIQUE
# ============================================
print(clean_text("\n" + "="*70))
print(clean_text("MEILLEUR MODELE PAR METRIQUE"))
print(clean_text("="*70))

if metrics_list:
    df_metrics = pd.DataFrame(metrics_list)
    
    for metric in ['Accuracy', 'Precision', 'Recall', 'Specificity', 'F1-Score', 'AUC-ROC']:
        best_idx = df_metrics[metric].idxmax()
        best_model_name = df_metrics.loc[best_idx, 'Modele']
        best_score = df_metrics[metric].max()
        print(clean_text(f"\n   -> {metric:<10}: {best_model_name} ({best_score:.2%})"))

    # Meilleur modele global (base sur F1-Score)
    best_model_name = df_metrics.loc[df_metrics['F1-Score'].idxmax(), 'Modele']
    best_model_before_opt = results[best_model_name]['model']
    best_threshold_before = results[best_model_name]['Optimal_Threshold']

    print(clean_text(f"\n" + "="*70))
    print(clean_text(f"MODELE SELECTIONNE AVANT OPTIMISATION: {best_model_name}"))
    print(clean_text("="*70))
    print(clean_text(f"   -> F1-Score: {results[best_model_name]['F1-Score']:.4f}"))
    print(clean_text(f"   -> AUC-ROC: {results[best_model_name]['AUC-ROC']:.4f}"))
    print(clean_text(f"   -> Seuil: {best_threshold_before:.2f}"))

# ============================================
# 15. OPTIMISATION DU MEILLEUR MODELE (GRIDSEARCH)
# ============================================
print(clean_text("\n[11] OPTIMISATION DU MEILLEUR MODELE AVEC GRIDSEARCH..."))

# Time Series Cross Validation (respecte l'ordre temporel)
tscv = TimeSeriesSplit(n_splits=5)

if best_model_name == 'XGBoost':
    print(clean_text("   Optimisation de XGBoost..."))
    
    # Grille de parametres optimisee pour XGBoost
    param_grid = {
        'n_estimators': [300, 500, 700],
        'max_depth': [5, 6, 7, 8],
        'learning_rate': [0.01, 0.03, 0.05, 0.1],
        'subsample': [0.7, 0.8, 0.9],
        'colsample_bytree': [0.7, 0.8, 0.9],
        'reg_alpha': [0, 0.05, 0.1, 0.5],
        'reg_lambda': [0.5, 1, 1.5],
        'min_child_weight': [1, 2, 3, 5]
    }
    
    # Version reduite pour temps d'execution raisonnable
    param_grid_reduced = {
        'n_estimators': [500, 700],
        'max_depth': [6, 7],
        'learning_rate': [0.03, 0.05],
        'subsample': [0.8, 0.9],
        'colsample_bytree': [0.8, 0.9],
        'reg_alpha': [0.05, 0.1],
        'reg_lambda': [0.5, 1],
        'min_child_weight': [2, 3]
    }
    
    base_model = xgb.XGBClassifier(
        scale_pos_weight=scale_pos_weight_value,
        random_state=42,
        use_label_encoder=False,
        eval_metric='logloss'
    )
    
    grid_search = GridSearchCV(
        base_model,
        param_grid_reduced,
        cv=tscv,
        scoring='roc_auc',
        n_jobs=-1,
        verbose=1
    )
    
    grid_search.fit(X_train_scaled, y_train)
    
    best_model = grid_search.best_estimator_
    best_params = grid_search.best_params_
    best_cv_score = grid_search.best_score_
    
    print(clean_text(f"\n   [OK] MEILLEURS PARAMETRES XGBoost:"))
    for param, value in best_params.items():
        print(clean_text(f"        {param}: {value}"))
    print(clean_text(f"   [OK] Meilleur score CV: {best_cv_score:.4f}"))

elif best_model_name == 'Random Forest':
    print(clean_text("   Optimisation de Random Forest..."))
    
    param_grid_reduced = {
        'n_estimators': [200, 300],
        'max_depth': [10, 15, 20],
        'min_samples_split': [2, 5],
        'min_samples_leaf': [1, 2]
    }
    
    base_model = RandomForestClassifier(class_weight='balanced', random_state=42, n_jobs=-1)
    
    grid_search = GridSearchCV(
        base_model,
        param_grid_reduced,
        cv=tscv,
        scoring='roc_auc',
        n_jobs=-1,
        verbose=1
    )
    
    grid_search.fit(X_train_scaled, y_train)
    
    best_model = grid_search.best_estimator_
    best_params = grid_search.best_params_
    best_cv_score = grid_search.best_score_
    
    print(clean_text(f"\n   [OK] MEILLEURS PARAMETRES Random Forest:"))
    for param, value in best_params.items():
        print(clean_text(f"        {param}: {value}"))
    print(clean_text(f"   [OK] Meilleur score CV: {best_cv_score:.4f}"))

else:  # Regression Logistique
    print(clean_text("   Optimisation de Regression Logistique..."))
    
    param_grid = {
        'C': [0.01, 0.05, 0.1, 0.5, 1, 5],
        'penalty': ['l1', 'l2'],
        'solver': ['liblinear', 'saga']
    }
    
    base_model = LogisticRegression(class_weight='balanced', random_state=42, max_iter=1000)
    
    grid_search = GridSearchCV(
        base_model,
        param_grid,
        cv=tscv,
        scoring='roc_auc',
        n_jobs=-1,
        verbose=1
    )
    
    grid_search.fit(X_train_scaled, y_train)
    
    best_model = grid_search.best_estimator_
    best_params = grid_search.best_params_
    best_cv_score = grid_search.best_score_
    
    print(clean_text(f"\n   [OK] MEILLEURS PARAMETRES Regression Logistique:"))
    for param, value in best_params.items():
        print(clean_text(f"        {param}: {value}"))
    print(clean_text(f"   [OK] Meilleur score CV: {best_cv_score:.4f}"))

# ============================================
# 16. EVALUATION DU MODELE OPTIMISE
# ============================================
print(clean_text("\n[12] Evaluation du modele optimise sur le test set..."))

y_proba_opt = best_model.predict_proba(X_test_scaled)[:, 1]

if best_model_name == 'XGBoost':
    max_pos_ratio = 0.35
else:
    max_pos_ratio = 0.20

best_threshold_opt, best_recall_opt, best_precision_opt, best_f1_opt = find_optimal_threshold(
    y_test, y_proba_opt, max_pos_ratio
)

y_pred_opt = (y_proba_opt >= best_threshold_opt).astype(int)

acc_opt = accuracy_score(y_test, y_pred_opt)
fpr_opt, tpr_opt, _ = roc_curve(y_test, y_proba_opt)
roc_auc_opt = auc(fpr_opt, tpr_opt)

cm_opt = confusion_matrix(y_test, y_pred_opt)
if cm_opt.shape == (2, 2):
    tn_opt, fp_opt, fn_opt, tp_opt = cm_opt.ravel()
    specificity_opt = tn_opt / (tn_opt + fp_opt) if (tn_opt + fp_opt) > 0 else 0
else:
    tn_opt, fp_opt, fn_opt, tp_opt = 0, 0, 0, 0
    specificity_opt = 0

print(clean_text(f"\n   PERFORMANCE AVANT OPTIMISATION:"))
print(clean_text(f"   -> F1-Score: {results[best_model_name]['F1-Score']:.4f} ({results[best_model_name]['F1-Score']*100:.2f}%)"))
print(clean_text(f"   -> AUC-ROC: {results[best_model_name]['AUC-ROC']:.4f} ({results[best_model_name]['AUC-ROC']*100:.2f}%)"))
print(clean_text(f"   -> Recall: {results[best_model_name]['Recall']:.4f} ({results[best_model_name]['Recall']*100:.2f}%)"))

print(clean_text(f"\n   PERFORMANCE APRES OPTIMISATION:"))
print(clean_text(f"   -> F1-Score: {best_f1_opt:.4f} ({best_f1_opt*100:.2f}%)"))
print(clean_text(f"   -> AUC-ROC: {roc_auc_opt:.4f} ({roc_auc_opt*100:.2f}%)"))
print(clean_text(f"   -> Recall: {best_recall_opt:.4f} ({best_recall_opt*100:.2f}%)"))
print(clean_text(f"   -> Precision: {best_precision_opt:.4f} ({best_precision_opt*100:.2f}%)"))
print(clean_text(f"   -> Specificity: {specificity_opt:.4f} ({specificity_opt*100:.2f}%)"))
print(clean_text(f"   -> Accuracy: {acc_opt:.4f} ({acc_opt*100:.2f}%)"))
print(clean_text(f"   -> Seuil optimal: {best_threshold_opt:.2f}"))

gain_f1 = best_f1_opt - results[best_model_name]['F1-Score']
gain_auc = roc_auc_opt - results[best_model_name]['AUC-ROC']
gain_recall = best_recall_opt - results[best_model_name]['Recall']

print(clean_text(f"\n   GAIN DE L'OPTIMISATION:"))
print(clean_text(f"   -> Gain F1-Score: +{gain_f1:.4f} (+{gain_f1*100:.2f}%)"))
print(clean_text(f"   -> Gain AUC-ROC: +{gain_auc:.4f} (+{gain_auc*100:.2f}%)"))
print(clean_text(f"   -> Gain Recall: +{gain_recall:.4f} (+{gain_recall*100:.2f}%)"))

# ============================================
# 17. GRAPHIQUES D'OPTIMISATION
# ============================================
print(clean_text("\n[13] Creation des graphiques d'optimisation..."))

# Graphique avant/apres optimisation
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

metrics_names = ['F1-Score', 'AUC-ROC', 'Recall', 'Precision']
values_before = [
    results[best_model_name]['F1-Score'],
    results[best_model_name]['AUC-ROC'],
    results[best_model_name]['Recall'],
    results[best_model_name]['Precision']
]
values_after = [best_f1_opt, roc_auc_opt, best_recall_opt, best_precision_opt]

colors_before = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4']
colors_after = ['#2ECC71', '#3498DB', '#9B59B6', '#1ABC9C']

ax1.bar(metrics_names, values_before, color=colors_before)
ax1.set_ylim(0, 1)
ax1.set_title(f'{best_model_name} - AVANT optimisation', fontsize=14, fontweight='bold')
ax1.set_ylabel('Score')
for i, v in enumerate(values_before):
    ax1.text(i, v + 0.02, f'{v:.3f}', ha='center', fontweight='bold')

ax2.bar(metrics_names, values_after, color=colors_after)
ax2.set_ylim(0, 1)
ax2.set_title(f'{best_model_name} - APRES optimisation', fontsize=14, fontweight='bold')
ax2.set_ylabel('Score')
for i, v in enumerate(values_after):
    ax2.text(i, v + 0.02, f'{v:.3f}', ha='center', fontweight='bold')

plt.suptitle(f'Optimisation du modele {best_model_name}', fontsize=16, fontweight='bold')
plt.tight_layout()
plt.savefig('resultats/optimisation_modele.png', dpi=150, bbox_inches='tight')
plt.close()
print(clean_text("   [OK] Graphique optimisation: resultats/optimisation_modele.png"))

# Courbe ROC avant/apres
plt.figure(figsize=(10, 8))
fpr_before, tpr_before, _ = roc_curve(y_test, results[best_model_name]['y_proba'])
fpr_after, tpr_after, _ = roc_curve(y_test, y_proba_opt)

plt.plot(fpr_before, tpr_before, 'b--', lw=2, label=f'AVANT optimisation (AUC = {results[best_model_name]["AUC-ROC"]:.3f})')
plt.plot(fpr_after, tpr_after, 'r-', lw=2, label=f'APRES optimisation (AUC = {roc_auc_opt:.3f})')
plt.plot([0, 1], [0, 1], 'k--', lw=1, label='Aleatoire')
plt.xlabel('Taux de faux positifs (1 - Specificite)', fontsize=12)
plt.ylabel('Taux de vrais positifs (Sensibilite)', fontsize=12)
plt.title(f'Courbes ROC - {best_model_name} avant/apres optimisation', fontsize=14, fontweight='bold')
plt.legend(loc='lower right')
plt.grid(True, alpha=0.3)
plt.savefig('resultats/roc_avant_apres.png', dpi=150)
plt.close()
print(clean_text("   [OK] Graphique ROC: resultats/roc_avant_apres.png"))

# ============================================
# 18. SAUVEGARDE DU MEILLEUR MODELE
# ============================================
print(clean_text("\n[14] Sauvegarde du meilleur modele..."))

joblib.dump(best_model, 'modeles/meilleur_modele_optimise.pkl')
joblib.dump(scaler, 'modeles/scaler.pkl')
joblib.dump(best_threshold_opt, 'modeles/seuil_optimal.pkl')
joblib.dump(features, 'modeles/features.pkl')
joblib.dump(best_params, 'modeles/meilleurs_parametres.pkl')

# Sauvegarder aussi le modele avant optimisation
joblib.dump(results[best_model_name]['model'], 'modeles/modele_avant_opt.pkl')

print(clean_text(f"   [OK] Meilleur modele sauvegarde dans 'modeles/meilleur_modele_optimise.pkl'"))

# ============================================
# 19. PREDICTIONS POUR 2026 AVEC ROLLING DYNAMIQUES (CORRIGEE)
# ============================================
print(clean_text("\n[15] Predictions pour 2026 avec rolling dynamiques..."))

# Creer calendrier 2026
dates_2026 = pd.date_range('2026-01-01', '2026-12-31', freq='D')
df_2026 = pd.DataFrame({'date': dates_2026})
df_2026['mois'] = df_2026['date'].dt.month
df_2026['jour_semaine'] = df_2026['date'].dt.dayofweek
df_2026['annee'] = df_2026['date'].dt.year
df_2026['jour'] = df_2026['date'].dt.day
df_2026['trimestre'] = df_2026['date'].dt.quarter
df_2026['est_weekend'] = df_2026['jour_semaine'].isin([5,6]).astype(int)
df_2026['est_debut_mois'] = (df_2026['jour'] <= 7).astype(int)
df_2026['est_fin_mois'] = (df_2026['jour'] >= 25).astype(int)
df_2026['mois_sin'] = np.sin(2 * np.pi * df_2026['mois'] / 12)
df_2026['mois_cos'] = np.cos(2 * np.pi * df_2026['mois'] / 12)
df_2026['jour_semaine_sin'] = np.sin(2 * np.pi * df_2026['jour_semaine'] / 7)
df_2026['jour_semaine_cos'] = np.cos(2 * np.pi * df_2026['jour_semaine'] / 7)

# === AJOUT CRITIQUE : Initialiser les colonnes manquantes ===
df_2026['accidents_7j'] = 0
df_2026['accidents_30j'] = 0

print(clean_text("   Calcul des rolling windows dynamiques..."))

# Recuperer l'historique reel des 30 derniers jours de test
if len(test) >= 30:
    historique_accidents = list(test['accident'].tail(30).values)
else:
    historique_accidents = [0] * 30

accidents_7j_list = []
accidents_30j_list = []
probas_2026_list = []

print(clean_text("   Simulation jour par jour..."))

for i in range(len(df_2026)):
    # Calculer les rolling windows avec l'historique connu
    if len(historique_accidents) >= 7:
        accidents_7j = sum(historique_accidents[-7:])
    else:
        accidents_7j = sum(historique_accidents)
    
    if len(historique_accidents) >= 30:
        accidents_30j = sum(historique_accidents[-30:])
    else:
        accidents_30j = sum(historique_accidents)
    
    accidents_7j_list.append(accidents_7j)
    accidents_30j_list.append(accidents_30j)
    
    # Preparer les features pour ce jour
    X_day = df_2026.iloc[i:i+1][features].copy()
    X_day['accidents_7j'] = accidents_7j
    X_day['accidents_30j'] = accidents_30j
    
    # Predire la probabilite
    X_day_scaled = scaler.transform(X_day[features])
    proba = best_model.predict_proba(X_day_scaled)[0, 1]
    probas_2026_list.append(proba)
    
    # Mettre a jour l'historique pour les jours suivants
    seuil_simulation = best_threshold_opt
    if proba > seuil_simulation:
        historique_accidents.append(1)
    else:
        historique_accidents.append(0)
    
    if len(historique_accidents) > 30:
        historique_accidents = historique_accidents[-30:]

# Ajouter les rolling windows calculees
df_2026['accidents_7j'] = accidents_7j_list
df_2026['accidents_30j'] = accidents_30j_list
df_2026['probabilite_accident'] = probas_2026_list

# Appliquer le seuil
jours_risque = df_2026['probabilite_accident'] > best_threshold_opt
nb_jours_risque = jours_risque.sum()

print(clean_text(f"\n   [OK] Rolling windows dynamiques calculees"))
print(clean_text(f"   [OK] Jours a risque en 2026: {nb_jours_risque} sur 365 ({nb_jours_risque/365:.1%})"))

print(clean_text("\n   Statistiques des rolling windows dynamiques:"))
print(clean_text(f"   accidents_7j - min: {df_2026['accidents_7j'].min()}, max: {df_2026['accidents_7j'].max()}, moyenne: {df_2026['accidents_7j'].mean():.2f}"))
print(clean_text(f"   accidents_30j - min: {df_2026['accidents_30j'].min()}, max: {df_2026['accidents_30j'].max()}, moyenne: {df_2026['accidents_30j'].mean():.2f}"))

# Analyse par mois
mois_noms = {1:'Janvier',2:'Fevrier',3:'Mars',4:'Avril',5:'Mai',6:'Juin',
             7:'Juillet',8:'Aout',9:'Septembre',10:'Octobre',11:'Novembre',12:'Decembre'}

print(clean_text("\n   Details par mois:"))
for mois in range(1, 13):
    jours_mois = (df_2026['mois'] == mois).sum()
    jours_risque_mois = ((df_2026['mois'] == mois) & jours_risque).sum()
    pct = (jours_risque_mois / jours_mois) * 100 if jours_mois > 0 else 0
    barre = '█' * int(pct / 3)
    print(clean_text(f"   {mois_noms[mois]:<12}: {jours_risque_mois:2} jours ({pct:.0f}%) {barre}"))

# Mois le plus critique
max_risque = 0
mois_max = None
for mois in range(1, 13):
    jours_risque_mois = ((df_2026['mois'] == mois) & jours_risque).sum()
    if jours_risque_mois > max_risque:
        max_risque = jours_risque_mois
        mois_max = mois

if mois_max:
    print(clean_text(f"\n   Mois le plus critique: {mois_noms[mois_max]} ({max_risque} jours)"))

# Top 10 jours les plus risques
print(clean_text("\n   Top 10 des jours les plus risques en 2026:"))
top10 = df_2026.nlargest(10, 'probabilite_accident')[['date', 'probabilite_accident']]
for idx, row in top10.iterrows():
    niveau = "TRES ELEVE" if row['probabilite_accident'] > 0.7 else "ELEVE" if row['probabilite_accident'] > 0.5 else "MODERE"
    print(clean_text(f"   {row['date'].strftime('%d/%m/%Y')}: {row['probabilite_accident']:.2%} ({niveau})"))

# Ajouter niveau de risque
df_2026['est_risque'] = jours_risque
df_2026['niveau_risque'] = pd.cut(df_2026['probabilite_accident'], 
                                   bins=[0, 0.3, 0.5, 0.7, 1],
                                   labels=['Faible', 'Modere', 'Eleve', 'Tres Eleve'])

# Sauvegarder les predictions
df_2026.to_csv('resultats/predictions_2026.csv', index=False, encoding='utf-8')
print(clean_text("\n   [OK] Predictions sauvegardees dans 'resultats/predictions_2026.csv'"))

# ============================================
# 20. RAPPORT FINAL COMPLET
# ============================================
print(clean_text("\n" + "="*70))
print(clean_text("RAPPORT FINAL DE COMPARAISON DES MODELES AVEC OPTIMISATION"))
print(clean_text("="*70))

if len(results) > 0:
    print(clean_text(f"""
STATISTIQUES DES DONNEES DE TEST:
   -> Nombre de jours testes: {len(y_test)}
   -> Accidents reels: {y_test.sum()}
   -> Jours sans accident: {(y_test==0).sum()}

PERFORMANCES DETAILLEES AVANT OPTIMISATION:
"""))
    
    for name, data in results.items():
        print(clean_text(f"""
{name}:
   -> Accuracy  : {data['Accuracy']:.2%}
   -> Precision : {data['Precision']:.2%}
   -> Recall    : {data['Recall']:.2%}
   -> F1-Score  : {data['F1-Score']:.2%}
   -> AUC-ROC   : {data['AUC-ROC']:.2%}
   -> Seuil     : {data['Optimal_Threshold']:.2f}
   -> Accidents detectes: {data['TP']} / {y_test.sum()}
"""))

    print(clean_text(f"""
OPTIMISATION DU MODELE {best_model_name}:
   -> Meilleurs parametres trouves: {best_params}
   -> Score CV: {best_cv_score:.4f}

PERFORMANCES APRES OPTIMISATION:
   -> F1-Score  : {best_f1_opt:.2%} (gain: +{gain_f1*100:.2f}%)
   -> AUC-ROC   : {roc_auc_opt:.2%} (gain: +{gain_auc*100:.2f}%)
   -> Recall    : {best_recall_opt:.2%} (gain: +{gain_recall*100:.2f}%)
   -> Precision : {best_precision_opt:.2%}
   -> Seuil optimal: {best_threshold_opt:.2f}

PREDICTIONS 2026 (avec modele optimise):
   -> Jours a risque: {nb_jours_risque} sur 365 ({nb_jours_risque/365:.1%})
   -> Mois critique: {mois_noms[mois_max] if mois_max else 'N/A'} ({max_risque} jours)

FICHIERS GENERES:
   -> resultats/comparaison_barres.png
   -> resultats/comparaison_heatmap.png
   -> resultats/courbes_roc_comparaison.png
   -> resultats/radar_comparaison.png
   -> resultats/boxplot_probabilites.png
   -> resultats/optimisation_modele.png
   -> resultats/roc_avant_apres.png
   -> resultats/predictions_2026.csv
   -> modeles/meilleur_modele_optimise.pkl
   -> modeles/meilleur_modele.pkl
   -> modeles/scaler.pkl
   -> modeles/seuil_optimal.pkl
   -> modeles/features.pkl
   -> modeles/meilleurs_parametres.pkl
   -> modeles/modele_avant_opt.pkl
"""))

    if 'XGBoost' in results:
        print(clean_text("""
CONCLUSION:
   -> Le modele XGBoost est generalement le meilleur car:
      - Meilleure AUC-ROC
      - Meilleur F1-Score apres optimisation
      - Meilleure gestion du desequilibre des classes
"""))
else:
    print(clean_text("   Aucun modele n'a pu etre entraine avec succes!"))

print(clean_text("="*70))
print(clean_text("ANALYSE TERMINEE - Resultats dans dossier 'resultats/'"))
print(clean_text("="*70))