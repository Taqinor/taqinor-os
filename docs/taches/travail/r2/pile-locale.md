# Pile locale privée « Tâches » (r2)

Code servi : worktree `C:\dev\taqinor-os\.claude\worktrees\taches-r2` (branche `dev-taches-r2` = `origin/main`).
Aucun `docker compose` : la pile `erp-agentique-*` de l'autre session n'est pas touchée.

## Adresses
- Application (front + relais d'API) : http://127.0.0.1:5180  (`/login`, puis `/taches/aujourdhui`)
- Django (dev, DEBUG) : http://127.0.0.1:8010  (le front relaie `/api/django` et `/static` vers lui)
- Base : `erp_taches_r2` dans le Postgres de `erp-agentique-db-1` (créée par `CREATE DATABASE … TEMPLATE test_erp_db_base`,
  puis `migrate` : le gabarit n'avait pas les migrations récentes, ~10 min la première fois).
- Redis à part : conteneur `taches-r2-redis` (le cache Django est codé en dur sur la base Redis 1 ; un Redis dédié est la
  seule façon de ne pas se mélanger à l'autre session sans toucher au code).

## Comptes (même société « demo-taches », rôle « Test tâches demo_taches » portant `taches_voir`)
`revue1` … `revue6` : journée d'exemple identique (jour = le jour du semis, 09:10, agenda de démonstration rempli).
`revide` : compte sans aucune tâche (écran « journée vide »).
Le mot de passe commun est dans la variable `TACHES_DEMO_PASSWORD`, fichier non suivi
`C:\Users\kasri\AppData\Local\Temp\claude\75bbe857427ccce5\b797bc27-f912-4ba8-a54b-d982221d7224\scratchpad\r2\env.local`.

## Django : arrêter / relancer
- Relancer (recrée le conteneur, applique `migrate`, `init_roles`, `runserver`) : `bash docs/taches/travail/r2/lancer-django.sh`
  (~1-2 min avant que le port réponde). Arrêter : `docker rm -f taches-r2-django` (et `docker rm -f taches-r2-redis` pour tout).
- Journal : `docker logs taches-r2-django`.
- Le code est monté en direct (`backend/django_core` du worktree sur `/app`) : `runserver` recharge seul après un changement Python.

## Front : arrêter / relancer / reconstruire
- Le serveur est `vite preview` sur le dossier `frontend\dist` du worktree, processus détaché (`cmd /c`), journal
  `…\scratchpad\r2\front.log`. Arrêter : tuer le `node.exe` dont la ligne de commande contient `vite` et `5180`.
- Relancer : `cmd /c "set E2E_PROXY=1&& set E2E_API_TARGET=http://127.0.0.1:8010&& cd /d C:\dev\taqinor-os\.claude\worktrees\taches-r2\frontend&& node_modules\.bin\vite.cmd preview --port 5180 --host 127.0.0.1 --strictPort"`
  (via PowerShell `Start-Process -WindowStyle Hidden` pour le détacher).
- Reconstruire après un changement de code : dans `taches-r2\frontend`, `npm run build` (~1-2 min ; la jonction
  `node_modules` pointe sur `C:\dev\taqinor-os\frontend\node_modules`), puis relancer le preview (il sert `dist` : un
  simple rechargement suffit en général, le service worker peut garder l'ancien : vider les données du site).

## Réinitialiser un compte
`bash docs/taches/travail/r2/reinit-compte.sh revue3 [HH:MM]` (≈ 1 min : démarrage du shell Django). `--vide` en 2e argument :
compte sans tâche. Plusieurs comptes d'un coup : variable `COMPTE=a,b,c` (voir `semer_compte.py`).
Méthode : `manage.py shell` importe la commande `seed_taches_demo`, remplace sa constante `NOM_COMPTE` le temps de l'appel
et l'exécute avec `--jour <aujourd'hui> --heure 09:10 --rendez-vous --reinitialiser`. Aucun fichier du dépôt n'est modifié.
Un relecteur qui coche/déplace des tâches doit réinitialiser son compte avant de recommencer.

## Recapturer
`node docs/taches/travail/r2/capturer-reel.cjs <compte> <dossier> [filtre]` (filtre = sous-chaînes d'écrans séparées par
des virgules, ex. `projet,agenda`). Sortie : `<dossier>/<ecran>-<iphone|bureau>-<clair|sombre>.png` + `index.md`
(avec la maquette de `docs/taches/maquettes/` quand il y en a une). Captures du tour 0 :
`…\scratchpad\r2\captures\tour0\`. Le script lit le mot de passe dans `env.local`, bascule le thème par
`localStorage['taqinor-theme']` + `colorScheme`, et ne valide aucune saisie. Les captures iPhone sont en 2x (780×1688).
Ne pas lancer deux captures sur le MÊME compte en même temps ; une capture change l'état du compte si un geste coche
quelque chose (le script évite de le faire, mais réinitialiser en cas de doute).

## Copilote
`.env` local : `GROQ_API_KEY`, `CLAUDE_API_KEY`, `OPENAI_API_KEY`, `ZHIPU_API_KEY` sont posées, `SQL_AGENT_PROVIDER=groq`.
Aucun service FastAPI/IA n'est lancé dans cette pile : le panneau Copilote s'ouvre mais ne répondra pas à une question.

## Pièges rencontrés
1. **Postgres partagé saturé (« too many clients already »)** : max 100 connexions, partagées avec les tests de l'autre
   session ; `runserver` gardait ~1 connexion par thread (CONN_MAX_AGE 60) -> 500 sur `/auth/me/` -> l'appli affiche
   « Hors ligne — réessayer » ou une page vide. Corrigé : `DB_CONN_MAX_AGE=0` dans `lancer-django.sh`. Si l'écran « Hors
   ligne » revient : `docker logs taches-r2-django | grep "too many"`.
2. `pip install -r requirements.txt` au démarrage échoue (le conteneur n'a pas de DNS vers PyPI) : sans conséquence, l'image
   suffit ; il est retiré de la commande de lancement.
3. Le gabarit `test_erp_db_base` est ancien : `migrate` applique beaucoup de migrations (long, sans erreur).
4. Avertissement Django `W_TZ_MAROC_POSTGRES_PERIMEE` : la base de fuseaux du Postgres est périmée (UTC+0 depuis le
   20/09/2026), les regroupements par jour peuvent être décalés d'une heure côté SQL ; sans effet sur les captures.
5. Dans la ligne d'une tâche, le premier bouton est la CASE À COCHER : pour ouvrir la fiche, cliquer `.titre`
   (la première version du script cochait la tâche).
6. Dans la liste des projets, le clic d'ouverture est sur `[data-projet] .ep-ouvrir` (pas sur la ligne).
7. `init_roles` répond « Aucune entreprise trouvée » sur une base neuve : normal, les rôles sont créés par le semis.
8. Le serveur Django a un seul processus dev : 4 captures en parallèle le ralentissent ; un tour complet = ~25 min.
