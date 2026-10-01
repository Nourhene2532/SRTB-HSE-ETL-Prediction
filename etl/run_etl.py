# run_etl.py
import subprocess
import sys
from datetime import datetime

print("="*60)
print("🚀 ETL COMPLET - SRTB DATA WAREHOUSE")
print("="*60)
print(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("="*60)

steps = [
    ("extract.py", "EXTRACTION"),
    ("transform.py", "TRANSFORMATION"),
    ("load.py", "CHARGEMENT")
]

for step_file, step_name in steps:
    print(f"\n▶️  ÉTAPE {step_name}")
    result = subprocess.run([sys.executable, step_file])
    if result.returncode != 0:
        print(f"❌ Échec à l'étape {step_name}")
        sys.exit(1)
    print(f"✅ ÉTAPE {step_name} TERMINÉE")

print("\n" + "="*60)
print("🎉 ETL COMPLET TERMINÉ AVEC SUCCÈS")
print("="*60)
print("📁 Résultats: data_transformed/")
print("🎯 Connectez Power BI aux CSV ou PostgreSQL")
print("="*60)