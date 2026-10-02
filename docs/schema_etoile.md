# Schéma en constellation de l'entrepôt (PostgreSQL)

Deux tables de faits (accidents et visites médicales) qui partagent des dimensions communes. Structure produite par `etl/transform.py` puis chargée par `etl/load.py`. Seuls les noms de colonnes sont documentés ; aucune donnée réelle n'est publiée. Les colonnes d'authentification ne sont pas listées.


## Tables de faits

- **fact_accidents** : id_accident, numero_accident, matricule_agent, date_accident, heure_accident, lieu_accident, condition_accident, endroit_blessures, nature_blessures, facteurs_materiels, mode_survenue, temoin1, temoin2, pv_existe, numero_pv, date_pv, tiers_responsable, nom_tiers, jour_arret, statut, date_declaration_cnam, gravite, created_by, updated_by, id_gravite, id_statut, id_agence, id_affectation, id_date_accident, est_declare, est_brouillon
- **fact_visites** : matricule_visite, date_visite, heure_visite, type_visite, medecin, observation, resultat, id_planning, type_action, ancien_statut, nouveau_statut, motif_action, details_action, matricule_agent, source, created_at, created_by, updated_at, updated_by, visite_originale_id, source_originale, id_type_visite, id_agence, id_affectation, id_date_visite, visite_effectuee
- **fact_visites_medicales** : matricule_visite, date_visite, heure_visite, type_visite, medecin, observation, resultat, id_planning, type_action, ancien_statut, nouveau_statut, motif_action, details_action, matricule_agent, source, created_at, created_by, updated_at, updated_by, visite_originale_id, source_originale, id_type_visite, id_agence, id_affectation, id_date_visite, visite_effectuee

## Dimensions

- **dim_affectation** : code_affectation, libelle_affectation, description, created_at, updated_at
- **dim_agence** : code_agence, nom_agence, ville, adresse, telephone, created_at, updated_at
- **dim_agent** : matricule_agent, nom, prenom, date_naissance, code_agence, code_affectation, direction, date_derniere_visite, date_debut_inaptitude, date_fin_inaptitude, date_prochaine_inaptitude, statut, periodicite_jours, date_prochaine_visite, created_at, updated_at, role, date_debut_reclassement, date_fin_reclassement, date_prochaine_reclassement, age, nom_complet
- **dim_date** : date_complete, id_date, annee, mois, mois_nom, trimestre, semaine, jour, jour_semaine
- **dim_gravite_accident** : id_gravite, libelle_gravite, couleur_alerte, niveau
- **dim_planning** : id_planning, matricule_agent, date_visite, heure_visite, type_visite, statut, visite_effectuee, reprogrammee, source_reprogrammation, motif_reprogrammation, date_reprogrammation, visite_originale_id, creneau_bloque, nouvelle_date_visite, nouvelle_heure_visite, priorite, semaine, annee, created_by, created_at, convocation_envoyee, motif_annulation, source_planification, accident_lie_id, date_convocation, convocation_envoyee_par, convocation_envoyee_nom, source_originale
- **dim_statut_accident** : id_statut, libelle_statut, description, est_actif
- **dim_type_visite** : id_type_visite, libelle_type_visite, duree_validite_jours
- **dim_utilisateur** : id_utilisateur, matricule_agent, derniere_connexion, nombre_connexions, date_creation, role
