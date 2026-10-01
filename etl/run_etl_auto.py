import time
import subprocess
from datetime import datetime

print("🚀 ETL AUTO - Démarrage")
print("📅 Exécution automatique toutes les 2 minutes")
print("="*50)

while True:
    heure = datetime.now().strftime("%H:%M:%S")
    print(f"\n[{heure}] Démarrage ETL...")
    
    # Lancer votre ETL normal
    result = subprocess.run(["python", "run_etl.py"])
    
    if result.returncode == 0:
        print(f"[{heure}] ✅ ETL réussi")
    else:
        print(f"[{heure}] ❌ ETL échoué")
    
    print(f"⏰ Prochaine exécution dans 5 minutes...")
    time.sleep(120)  # 2 minutes