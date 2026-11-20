# Instrument de revue — la pile PRIVÉE et jetable de <périmètre> (go-deep L4 / L5)

Statut : un INSTRUMENT, pas une porte de test. C'est la pile locale que la règle 3-bis de `CLAUDE.md` exige déjà pour
l'acceptation en direct ; il suit la règle `ci-avant-docker` (`docs/claude-memory/ci-avant-docker.md`) : il ne sert
que du code DÉJÀ POUSSÉ, tourne EN PARALLÈLE de la CI, jamais à sa place, et ne sert jamais à « valider avant de
pousser ». Sans lui (session cloud, Docker absent), pas de L4 : L3 + specs sur un runner (METHODE §C.4.7), et le
rapport le dit.

## 1. Le lanceur — OBLIGATOIRE tel quel (tant qu'aucun script de la maison n'existe, ce bloc EST le lanceur)
Git Bash, `export MSYS_NO_PATHCONV=1`, chemins Windows en `C:/…` pour `docker -v`. `<run>` = préfixe du run,
`<port>` = port libre, `<W>` = worktree suivi (`git merge --ff-only origin/<branche>`, jamais édité pendant une revue),
`<SP>` = scratchpad de la session, `<REPO>` = dépôt principal.
```sh
RUN=<run>; PORT=<port>; W=<W>; SP=<SP>; REPO=<REPO>
# 0. Port libre (8010 a déjà servi à une autre session)
netstat -ano | grep -qE "[:.]$PORT +.*LISTEN" && { echo "ARRET : port $PORT occupe"; exit 1; }
# 1. Environnement construit depuis .env.example SEUL — jamais --env-file du vrai .env (le run du 19/11 l'a fait :
#    ses clés de fournisseurs y passaient). Toute variable *KEY* / *TOKEN* / *SECRET* est vidée ; les variables posées
#    plus bas sont retirées d'abord (un doublon ne reste que pour une clé vide des deux côtés : aucune ambiguïté).
F='(DJANGO_SECRET_KEY|FASTAPI_SECRET_KEY|DB_[A-Z_]+|REDIS_[A-Z_]+|EMAIL_BACKEND|ASSISTANT_COPILOTE|FASTAPI_INTERNAL_URL|MINIO_ENDPOINT|WHATSAPP_ENABLED|META_AD_LIBRARY_ENABLED|VAPID_AUTOGENERATE)'
sed -E "/^[[:space:]]*(#|\$)/d; /^$F=/d; s/^([A-Z0-9_]*(KEY|TOKEN|SECRET)[A-Z0-9_]*)=.*/\\1=/" \
  "$W/.env.example" > "$SP/$RUN.env"
grep -E '^DB_(USER|PASSWORD)=' "$REPO/.env" >> "$SP/$RUN.env"     # seules ces deux lignes du vrai .env : la base partagée
cat >> "$SP/$RUN.env" <<EOF
DJANGO_SECRET_KEY=dev-$RUN
FASTAPI_SECRET_KEY=dev-$RUN
DB_HOST=host.docker.internal
DB_PORT=5433
DB_NAME=$RUN
DB_CONN_MAX_AGE=0
REDIS_HOST=$RUN-redis
REDIS_PORT=6379
REDIS_CACHE_HOST=$RUN-redis
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
SENDGRID_API_KEY=
BREVO_API_KEY=
CLAUDE_API_KEY=
GROQ_API_KEY=
OPENAI_API_KEY=
ZHIPU_API_KEY=
VEILLE_IA_CLE_API=
WHATSAPP_ENABLED=0
WHATSAPP_ACCESS_TOKEN=
WHATSAPP_CLOUD_ACCESS_TOKEN=
SAV_WHATSAPP_APP_SECRET=
META_LEAD_ADS_ACCESS_TOKEN=
META_AD_LIBRARY_ENABLED=0
META_AD_LIBRARY_ACCESS_TOKEN=
WEBSITE_LEAD_WEBHOOK_SECRET=
VAPID_AUTOGENERATE=0
ASSISTANT_COPILOTE=aucun
FASTAPI_INTERNAL_URL=http://127.0.0.1:9
MINIO_ENDPOINT=127.0.0.1:9
EOF
# 2. Réseau À SOI : jamais celui d'une autre pile (son FastAPI porte les vraies clés IA, son MinIO ses fichiers).
#    La base partagée se joint par son port publié sur l'hôte (docker-compose.yml : 5433:5432), pas par son réseau.
docker network create "$RUN-net"
docker run -d --name "$RUN-redis" --network "$RUN-net" redis:7.4-alpine
docker run -d --name "$RUN-django" --network "$RUN-net" -p "127.0.0.1:$PORT:8000" --env-file "$SP/$RUN.env" \
  -v "$W/backend/django_core:/app" -v "$W/STAGES.py:/opt/STAGES.py:ro" \
  erp-agentique-django_core python manage.py runserver 0.0.0.0:8000
```
Valeurs vérifiées sur `origin/main` le 20/11/2026 : noms des variables (`settings/base.py`, `.env.example`), valeur
éteinte `aucun` d'`ASSISTANT_COPILOTE` (défaut `admins`), image `erp-agentique-django_core`, montage `/app` et
`/opt/STAGES.py`, `redis:7.4-alpine`, port publié `5433`. Une variable à clé apparue depuis : le contrôle ci-dessous
l'attrape. Le MinIO est mort (`127.0.0.1:9`) : un PDF ou un envoi de fichier échoue, à dire aux relecteurs ; un MinIO à
soi (même image que le service `minio` de `docker-compose.yml`, réseau `$RUN-net`) seulement si le périmètre en a besoin.
Aucun worker Celery : les effets asynchrones sont absents, à dire aux relecteurs.

## 2. Le contrôle du tour 0 — il ARRÊTE le tour 0 s'il échoue (rejoué après tout redémarrage de l'instrument)
```sh
RUN=<run>; FPORT=<port front>   # l'état du shell ne survit pas d'un appel Bash à l'autre
ko=0
docker exec "$RUN-django" env | grep -E '^[A-Z0-9_]*(KEY|TOKEN|SECRET)[A-Z0-9_]*=.' \
  | grep -vE "^(DJANGO|FASTAPI)_SECRET_KEY=dev-$RUN\$" && { echo "ARRET : variable a cle non vide"; ko=1; }
[ "$(docker exec "$RUN-django" printenv EMAIL_BACKEND)" = django.core.mail.backends.console.EmailBackend ] \
  || { echo "ARRET : backend d'envoi reel"; ko=1; }
docker port "$RUN-django" | grep -v -- '-> 127\.0\.0\.1:' && { echo "ARRET : ecoute hors 127.0.0.1"; ko=1; }
[ "$(docker inspect -f '{{range $k, $v := .NetworkSettings.Networks}}{{$k}} {{end}}' "$RUN-django")" = "$RUN-net " ] \
  || { echo "ARRET : reseau partage avec une autre pile"; ko=1; }
for v in ASSISTANT_COPILOTE:aucun FASTAPI_INTERNAL_URL:http://127.0.0.1:9 WHATSAPP_ENABLED:0; do
  [ "$(docker exec "$RUN-django" printenv "${v%%:*}")" = "${v#*:}" ] || { echo "ARRET : ${v%%:*}"; ko=1; }
done
netstat -ano | grep LISTENING | grep -E "(0\.0\.0\.0|\[::\]):$FPORT +" && { echo "ARRET : front hors 127.0.0.1"; ko=1; }
[ $ko = 0 ] && echo "instrument sur" || { echo "ARRET DU TOUR 0"; exit 1; }
```
La sortie complète du contrôle est collée dans le fichier d'état. Un `ARRET` = démonter, corriger le lanceur, rejouer.

## 3. Exigences (aucune exception)
1. **Jamais la prod.** Écoute sur `127.0.0.1` seulement ; aucune donnée de prod (le jeu anonymisé de qa-explorer : voir
   `L5.md`, jamais ici en L4).
2. **Code poussé seulement** : le worktree monté suit `origin/<branche>` par `git merge --ff-only` ; on ne l'édite
   jamais pendant qu'un relecteur s'en sert. Les relecteurs jugent ce que la CI juge.
3. **Rien d'une autre session** : ni ses conteneurs (aucun `docker exec` dedans), ni ses bases, ni ses comptes, ni ses
   ports, ni son réseau ; aucune commande `docker compose` ; Docker n'est jamais DÉMARRÉ « pour voir » (il relance une
   autre pile, dont un planificateur qui envoie avec une vraie clé). Une base À SOI dans le Postgres partagé déjà en
   marche est permise, créée depuis TON conteneur ; ne jamais arrêter ni relancer ce Postgres.
4. **Démontage à la fin** : conteneurs et réseau à soi retirés, serveur front tué par son port, base `DROP`, comptes de
   revue avec elle, `<SP>/<run>.env` effacé ; le fichier d'état coche chaque geste.

## 4. Composants (noms préfixés par le run)
| Composant | Exigence | Pourquoi (mesuré au run du 19-20/11, module Tâches) |
|---|---|---|
| Base | `CREATE DATABASE <run> TEMPLATE test_erp_db_base` puis `migrate`, depuis `<run>-django` | clone en secondes ; le gabarit ancien rattrape ses migrations (long la 1re fois) |
| Connexions | `DB_CONN_MAX_AGE=0` (dans le lanceur) | Postgres partagé plafonné à 100 connexions : `too many clients` → 500 → écran « Hors ligne » |
| Cache | le Redis À SOI du lanceur | le cache est codé en dur sur une base Redis ; partagé, on se mélange à l'autre session |
| Serveur | `<run>-django`, `runserver` | rechargement seul ; un seul processus : 4 captures en parallèle le ralentissent déjà |
| Front | `npm run build` puis `E2E_PROXY=1 E2E_API_TARGET=http://127.0.0.1:$PORT npx vite preview --host 127.0.0.1 --port $FPORT --strictPort` (sans `--host`, preview hérite de `server.host: true`) | le service worker peut garder l'ancien build : vider les données du site |
| Comptes | un par relecteur, un VIDE, un pour la couture ; même société de démonstration | aucun relecteur ne casse l'état d'un autre |
| Semis | commande idempotente `--reinitialiser` par compte (exemple Tâches : journée d'exemple datée du jour) | un relecteur qui coche doit pouvoir repartir à neuf en ≈ 1 min |
| Capture | script qui capture chaque écran listé en 4 vues (iPhone 390×844 tactile, bureau 1440×900, clair et sombre) ; `<dossier>/<écran>-<vue>.png` + `index.md` avec la maquette en regard | une galerie du tour 0 évite que chaque relecteur recapture tout |
| Mesures | un script DOM fixe (positions, tailles de texte, cibles) rejoué à l'identique à chaque tour, lancé une fois sur le commit intact | les critères `K` de beauté se mesurent ; tant qu'il manque, ils se jugent par paires |

**Outils** : ni le lanceur, ni les scripts de capture, de semis, de remise à zéro ou de mesures DOM ne sont sur `main`.
Le premier L4 les écrit depuis ce gabarit, dans son dossier de travail ; les promouvoir sous `scripts/` est une suite à
part (`conception.md`), jamais glissée dans une PR de documentation. **Prérequis à demander au périmètre** (sinon une
tâche de son propriétaire au tour 0) : un semeur idempotent avec `--reinitialiser`, un rôle de revue portant le droit
d'accès, la liste des écrans à capturer.

## 5. Pièges connus (chacun vérifié au tour 0, résultat au fichier d'état)
1. Le poste n'est pas la CI : dépendances en retard sur le lock (`npm ls` contre le lock), horloge réelle (exemple
   Tâches : une carte liée à l'heure demande de régler l'heure du compte ou de réécrire la réponse par `page.route` —
   dire lequel), base de fuseaux de Postgres périmée (décalage d'une heure côté SQL), version d'axe différente : toute
   preuve qui dépend d'une version se lit contre celle de la CI.
2. `pip install` au démarrage échoue sans DNS vers PyPI : l'image suffit ; ne pas le mettre dans la commande.
3. Une commande d'initialisation des rôles peut répondre « aucune entreprise » sur une base neuve : les rôles viennent
   du semis.
4. Les sélecteurs des scripts de capture : le premier bouton d'une ligne peut être une case à cocher (un clic
   « ouvrir » coche) ; viser l'élément d'ouverture nommé.
5. Fichiers temporaires : dans le scratchpad de la session seulement (un fichier hors arbre a été impossible à
   supprimer).

## 6. Fiche de l'instrument du run (à remplir et à donner aux relecteurs)
- Front : http://127.0.0.1:<port front> · serveur : http://127.0.0.1:<port> · base `<run>` · Redis `<run>-redis`
- Code servi : `origin/<branche>@<sha9>` (mis à jour le <date> <heure>)
- Contrôle du tour 0 : « instrument sur » le <date> <heure> (sortie dans le fichier d'état)
- Comptes : `<relecteurs>`, `<vide>`, `<couture>` ; mot de passe dans `<SP>/env.local` (non suivi, jamais affiché)
- Réinitialiser un compte : `<commande>` · capturer : `<commande> <compte> <dossier> [filtre]` · mesurer : `<commande>`
- Absents à dire : worker Celery, MinIO (sauf mention), fonctions à clé
- Arrêter / relancer : `<commandes>` (puis rejouer le contrôle) · journal : `docker logs <run>-django`
