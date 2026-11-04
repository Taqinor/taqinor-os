---
name: problemes-prod
description: >-
  Tri du matin des problemes vecus en production par les utilisateurs de TAQINOR OS
  (BPQ5). LECTURE SEULE sur la prod : lit health/ready, le resume des problemes
  (GET /api/django/reporting/problemes/resume/?jours=1&tri=1), les issues/runs GitHub
  des alertes nocturnes, deduplique sur la Signature contre docs/ERROR_PLAN.md, note la
  severite (personnes x gene) et depose des lignes ERR-PROD-<MODULE>-<SLUG> par UNE PR
  docs-only. Lance par la routine cloud 07:07 (docs/problemes-prod.md) ou
  scripts/nightly-qa.ps1 -Skill problemes-prod. Respecter le kill switch
  docs/problemes-prod.config.yml.
---

# problemes-prod — le tri du matin

Tu ne corriges rien. Tu LIS ce que la production a fait vivre aux gens, tu decides ce qui est un
vrai probleme, et tu le DEPOSES dans `docs/ERROR_PLAN.md` pour que `work on error plan` le
construise. Conception : `docs/boucle-problemes-quotidienne.md` ; capture serveur et allumage :
`docs/problemes-prod.md`. Auto-suffisant : tu tournes sans humain.

## Regles absolues

- **Jamais d'ecriture en production** : uniquement des GET. Aucun `ssh`, aucun `docker exec`,
  aucun `manage.py` contre la prod, aucune ecriture SQL, aucun appel Sentry/GitHub en ecriture
  hors la PR docs-only decrite plus bas. Le seul effet de bord permis cote prod est
  `tri=1` (battement de coeur du tri, BPQ4).
- Jamais de secret dans un fichier, une PR ou ta sortie. Le jeton `PROBLEMES_RESUME_TOKEN` est
  injecte en `Authorization: Bearer` par le reseau de la routine cloud (BPQ8) ; en local, il
  vient de la variable d'environnement du meme nom. Ne l'affiche jamais.
- Regles #1-#5 de `CLAUDE.md` toujours. Aucune donnee personnelle client dans un item (ni nom,
  ni telephone, ni email) : des identifiants techniques, des routes, des comptes anonymes.

## ETAPE 0 — Kill switch et preconditions

1. Lis `docs/problemes-prod.config.yml`. Si `enabled: false` : imprime exactement
   `PROBLEMES_PROD: DISABLED (config flag off)` et termine SANS aucun changement, commit ni PR.
2. Charge `max_minutes`, `max_findings_per_run`, `base_url`. Respecte le budget de temps.
3. Preconditions (sinon une ligne d'explication et fin, rien ecrit) : checkout git de
   `taqinor/taqinor-os` ; pas de modification non liee en cours ; `gh` utilisable.
4. Mode : si aucun acces SSH n'existe (routine cloud) — c'est le cas normal — tu ne lis QUE
   l'API. Ne tente jamais de te connecter au serveur.

## ETAPE 1 — Lire (4 sources, toutes en lecture)

1. `GET {base_url}/api/django/health/ready/` : etat des services, `dernier_demarrage`
   (horodatage + sha, BPQ2). Un service `down` est un constat en soi.
2. `GET {base_url}/api/django/reporting/problemes/resume/?jours=1&tri=1` (contrat :
   `backend/django_core/apps/reporting/contract_samples/problemes_resume.json`). Chaque ligne
   porte genre, methode, route, statut, code, nombre, personnes, classe, tendance et un
   `exemple_request_id`. Les blocs `outbox_en_echec`, `sauvegardes_en_echec` et `sante` couvrent
   « ce que personne ne vit encore ». `tri_horodate` doit valoir `true` ; sinon note-le dans
   l'intake (Redis muet).
3. `gh issue list --state open --label <etiquettes des alertes nocturnes>` (auditeur de
   coherence, release-verify, mutation) : une issue ouverte et recente est un constat.
4. `gh run list --workflow <workflow planifie> --limit 5` pour chaque workflow planifie : un run
   `failure` sur le `main` est un constat.

## ETAPE 2 — Trier

- **Ignorer** les lignes de classe `deploiement`, `connectivite` et `maintenance`, SAUF
  recurrence : meme signature dans la fenetre ET au moins 2 jours differents de la tendance J-7.
- **Signature** d'un probleme : `Signature: genre|methode|route|statut|code` (route normalisee
  telle que le resume la rend, sans identifiant numerique). C'est la cle de deduplication.
- **Dedoublonner** : cherche la signature (texte exact) dans TOUTES les lignes de
  `docs/ERROR_PLAN.md`, cochees ou non, et dans son journal d'intake. Deja presente et ouverte :
  ne rien deposer. Presente et cochee : voir la regle de cloture de `docs/problemes-prod.md`.
- **Severite = personnes x gene** : 1 personne bloquee sur un geste metier (creer/envoyer un
  devis, signer, facturer, se connecter) = **High** ; au moins 3 personnes touchees = **Critical** ;
  une gene sans blocage = Medium ; cosmetique sans perte de geste = Low (non deposee si
  `max_findings_per_run` est atteint).
- Garde au plus `max_findings_per_run` items, par severite decroissante puis nombre de personnes.

## ETAPE 3 — Deposer

Pour chaque probleme retenu, ajoute UNE ligne au gabarit des lignes `ERR-QAH-*` de
`docs/ERROR_PLAN.md` (meme forme que ses voisines), avec :

- l'id `ERR-PROD-<MODULE>-<SLUG>` (`[A-Z0-9-]+`, MODULE = app proprietaire de la route) ;
- `Signature: genre|methode|route|statut|code` ;
- `found via: journal prod <AAAA-MM-JJ>` ; `Confiance : constat prod, lecture seule` ;
- la severite et le nombre de personnes, le `request_id` d'exemple (relie la ligne au
  cas Sentry), la reproduction la plus courte possible, le comportement attendu ;
- **un test rouge dans le module de test existant** de l'app concernee (jamais un fichier
  `test_err_*.py`) : nomme le module et ecris l'assertion qui echoue aujourd'hui.

Ajoute ensuite UNE ligne au journal d'intake de `docs/ERROR_PLAN.md` (date, nombre d'items,
source). Puis `python scripts/check_err_prod.py` doit afficher `OK`.

**Rien depose : aucun commit, aucune PR.** Imprime `PROBLEMES_PROD_STATUS: EMPTY`.

## ETAPE 4 — Livrer (docs-only)

Une branche, un commit (modifie uniquement `docs/ERROR_PLAN.md`), UNE PR docs-only, puis
`gh pr merge --auto --merge` (file de fusion ; jamais d'attente active) et Auto-fix actif sur
la PR. Jamais `--squash`, jamais de force.

Termine par une ligne : `PROBLEMES_PROD_STATUS: MORE` si des problemes deposables restent
(budget atteint), sinon `PROBLEMES_PROD_STATUS: EMPTY`.
