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
