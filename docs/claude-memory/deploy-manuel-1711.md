---
name: deploy-manuel-1711
description: 17/11/2026 — l'auto-deploy de l'ERP est ARRÊTÉ sur le serveur à la demande de Reda ; l'ERP ne se déploie plus que quand il lance scripts/deploy-prod.ps1
metadata:
  type: project
---

**Décision du fondateur (17/11/2026) : « stop the automatic deploy and only let me do it manually ».**

- Mesuré ce jour-là : 10 deploys automatiques dans la journée de travail, chacun redémarre les conteneurs 3 à 9 minutes.
- Fait sur le serveur le 17/11 à 13:06 UTC : `systemctl disable --now taqinor-autodeploy.timer` (minuterie éteinte et
  désactivée). Le service `taqinor-autodeploy.service` reste : `scripts/deploy-prod.ps1` le démarre à la main, comme avant.
- Conséquence : un merge sur `main` n'est PAS en ligne tant que Reda n'a pas déployé. Le dire dans chaque rapport
  (« mergé — à déployer par toi »), et ne jamais annoncer « en ligne » sans l'avoir vu.
- Ne jamais réactiver la minuterie (ni lancer `scripts/serveur/installer-serveur.sh` ou l'étape 9 de
  `docs/production.md`, qui l'activent) sans demande de Reda. Pour la rallumer : `systemctl enable --now taqinor-autodeploy.timer`.
- Le site public (`apps/web`) reste déployé automatiquement par Cloudflare à chaque merge : rien n'a changé là.

**Why:** les redémarrages en pleine journée coupent le travail des commerciales.
**How to apply:** après un merge, s'arrêter et dire à Reda ce qui attend son deploy ; ne pas lire le journal de deploy du
serveur en s'attendant à y voir le merge.

**Incident du 18/11/2026 — premier deploy manuel après l'arrêt de la minuterie : Django n'a pas été redémarré.**
CLOS le 18/11 à 16 h 35 UTC : séquence courante relancée par Reda (`DEPLOY a0e492a1f8 — OK`), puis relu de l'extérieur :
0 erreur sur 60 appels, l'adresse-témoin répond 401, `dernier_demarrage.sha` = `a0e492a1f8`.

- Constaté de l'extérieur, en lecture seule, de 11:28 à 12:25 UTC : le site servi porte les écrans du matin (fusions 2
  et 3 de Tâches), mais Django répond avec le code de la VEILLE — l'adresse
  `/api/django/ventes/etude-ci/recomposer-batteries/`, née le 17/11 à 14:18 UTC, répond 404 sans connexion au lieu de
  401 (0 réponse 401 sur 50) — et 47 % des appels (214 sur 453), tous chemins confondus, reçoivent la page nue
  « Internal Server Error » de gunicorn (141 octets, sans `x-request-id`).
- Mécanisme, reproduit en local : gunicorn `--preload` garde en mémoire le code de son démarrage, mais les routes et
  les vues ne sont importées qu'à la PREMIÈRE requête de chaque worker. Un worker né après le changement des fichiers
  importe des vues neuves contre des modules anciens : erreur d'import à chaque requête, hors de la gestion d'erreur de
  Django. Les workers nés avant continuent de servir l'ancien code ; à mesure qu'ils meurent, tout tombe.
- Cause CONFIRMÉE (sortie du serveur collée par Reda, et sa parole) : les deux deploys du jour sont partis de son
  PORTABLE, dont `scripts/deploy-prod.ps1` date d'avant le 10/11 (ADCG1). L'ancienne séquence manuelle avançait le
  code, reconstruisait le front, migrait, mais ne redémarrait pas Django quand le front était reconstruit. Signature
  sur le serveur : `/opt/autodeploy/deploy.log` SANS aucune ligne du jour (la séquence courante en écrit une à chaque
  passage), `last_deployed_commit` resté à la veille, `django_core : Up 28 hours` à côté de `frontend : Up 14 minutes`.
- Second défaut trouvé au deploy de clôture, dans la séquence COURANTE cette fois : `fastapi_ia` est resté
  « Up 28 hours » sous un « DEPLOY — OK » (et le journal disait « rebuild ciblé : frontend », sans nginx). Cause :
  `echo "$CHANGES" | grep -q` sous `pipefail` — `grep -q` sort au premier chemin trouvé, `echo` meurt de SIGPIPE et le
  test rend FAUX ; toujours au-delà de 64 Ko de noms de fichiers, parfois en dessous (lot du jour : 737 fichiers).
  Django et Celery n'ont été sauvés que par `DEPLOYED_SHA`, qui les fait recréer. Corrigé le 18/11
  (`lot_contient()`, sans tube ; test `test_gros_lot_backend_et_nginx_toujours_vus`).
- Remède : la séquence d'`origin/main`, jamais une copie locale ancienne. Une ligne, depuis le PC de Reda :
  `ssh -i $env:USERPROFILE\.ssh\taqinor_hetzner root@178.105.192.116 "cd /opt/taqinor-os && git fetch origin main && git show origin/main:scripts/auto-deploy.sh > /opt/autodeploy/auto-deploy.sh.neuf && chmod +x /opt/autodeploy/auto-deploy.sh.neuf && mv /opt/autodeploy/auto-deploy.sh.neuf /opt/autodeploy/auto-deploy.sh && rm -f /opt/autodeploy/commit_en_echec && systemctl start taqinor-autodeploy.service; tail -n 12 /opt/autodeploy/deploy.log"`
  (c'est exactement ce que fait le `deploy-prod.ps1` courant) ; puis mettre à jour le dossier local (`git pull` sur `main`).

**How to apply :** après un deploy de Reda, vérifier de l'extérieur que le BACKEND sert le commit attendu, pas seulement
le front, avant d'écrire « en ligne » : (1) une adresse née du dernier merge backend répond 401 sans connexion, pas
404 ; (2) aucune page nue de gunicorn sur 30 appels à `health/ready` ; (3) `health/ready` → `dernier_demarrage.sha` porte
le commit (il est resté nul tout ce temps : signe que la séquence courante ne tournait pas).
Quand le doute porte sur le serveur, ne pas donner une commande de deploy de plus : faire coller d'abord la lecture
seule (`git log -1` dans `/opt/taqinor-os`, `cat /opt/autodeploy/last_deployed_commit`, `docker ps` avec les durées,
`tail /opt/autodeploy/deploy.log`, première erreur de `django_core`) — c'est elle qui a tranché en une minute, après
des heures de mesures de l'extérieur. Après un « DEPLOY — OK », lire aussi les durées de `docker ps` : un conteneur
resté « Up N hours » n'a pas pris le code.
