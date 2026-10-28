# CSV — notes (session questionnaire de suivi / visite C&I)

## 01:20 UTC 27/10 — pile locale : API muette (pour CORC, gardien)
- `erp-agentique-django_core-1` : gunicorn « WORKER TIMEOUT » + SIGKILL en boucle depuis ~01:18 ; `/api/django/health/` > 30 s même depuis le conteneur.
- DB/redis/minio joignables (sockets OK), pg_stat_activity calme → pas un verrou SQL.
- Le conteneur monte `C:\dev\taqinor-os\backend\django_core` (checkout principal), pas un worktree.
- CSV ne touche pas la pile (pas de restart). R1 continue en lecture de code.

## R1 CSV — constats visite C&I (lecture seule)
- Visite → étude existe (CIQ141 `_couche_visite`, etude_ci.py:369-424) ; visite → colonnes du lead (CIQ607 `visites_retour_lead.appliquer_releve_ci`).
- AUCUN chemin visite validée → devis révisé (lignes) : `rafraichir_etude_ci_devis` ne réécrit pas les lignes, `reviser_devis` clone sans recomposer. → besoin d'un contrat avec CORC (devis révisé après visite).
- Sémantique câble : la visite somme les trajets dans `longueur_dc_m`, le composeur multiplie par nb_chaines (composition.py:555) → sur-comptage probable (CMP).
- Préséance probable : `_poser_mesure` ne remplace jamais une valeur d'origine `devis` → la mesure de visite perd au rafraîchissement (CORC).

## 01:50 UTC — CAUSE de la pile muette + contournement (toutes sessions)
- Le processus Django est en état D (attente disque) sur `p9_client_rpc` : le partage de fichiers Windows→Docker (bind mount `./backend:/app`) est saturé. Ni le code ni la DB.
- Contournement qui marche (57 s de démarrage) : conteneur SANS montage, code copié dedans :
  `MSYS_NO_PATHCONV=1 docker run -d --name <x>-django --network erp-agentique_default --env-file .env -p <port>:8000 -w /srv/app erp-agentique-django_core sleep infinity`
  `tar --exclude=__pycache__ -C backend/django_core -cf - . | docker exec -i <x>-django sh -c 'mkdir -p /srv/app && tar -C /srv/app -xf -'` ; `docker cp STAGES.py <x>-django:/opt/STAGES.py`
  `docker exec -d <x>-django sh -c 'cd /srv/app && python manage.py runserver 0.0.0.0:8000 --noreload > /tmp/rs.log 2>&1'`
  Front : `VITE_API_URL=http://localhost:<port> npx vite --port 3000` (CORS dev autorise localhost:3000). CSV occupe 8011 + 3000.

## Pour d'autres sessions (constats CSV hors de mon périmètre)
- POUR CVL (devis_auto.py) + CORC (etude_ci ADEV89) : site MT déclaré ⇒ triphasé implicite (aucun site MT n'est monophasé) ; aujourd'hui `champs_requis` exige `raccordement` même en MT. CSV pose « Triphasé » en un clic pour MT (CSV4), mais la règle moteur serait plus juste. Aussi : `devis_selectors.py:628-632` n'ajoute `raccordement` aux manquants que pour un commercial alors que champs_requis l'exige pour tout pro.
- POUR CCAT/propriétaire parametres (`apps/parametres/models_messages.py:893, 959`, gabarit B2B `visite_proposition`) : « Pour verrouiller votre proposition… » contredit le bandeau PDF C&I « Devis préliminaire — les prix pourront être ajustés après la visite technique » (26/10). CSV a aligné le script oral (CSV7) ; le message écrit reste à aligner.
- POUR CQST : `questionnaire._manquantes_pro` tient « ne_sait_pas »/« inconnu » pour répondu (cf. csv-r1-design.md).
- POUR CORC : `_couche_visite` doit prendre le PLUS LONG trajet (D-CMP-2), pas la somme ; préséance mesure visite vs `etude_params` persisté.
