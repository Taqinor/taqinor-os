# r2 — état du chantier (à lire en premier pour reprendre)

Demande de Reda (19/11) : regarder ce que l'autre session a livré, puis refaire plusieurs tours sur les fonctions, la
simplicité et la beauté. Règle en vigueur : AUCUNE question à Reda (décider seul, noter le choix). S'arrêter au merge.

## Où sont les choses
- Notes de travail (cette branche docs `claude/erp-task-manager-ai-f8db1b`, dossier `docs/taches/travail/r2/`) :
  `etat-des-lieux.md` (ce que l'autre session a livré), `brief-revue.md` (relecteurs), `brief-lane.md` (lanes, avec
  la section « Vague 3 » et les fautes de CI à ne pas refaire), `pile-locale.md` (pile privée), `tour1/` et `tour2/`
  (rapports + `consolidation.md`), `vague2.md` (restes de la vague 1), `vague3-ajouts.md`, `tour2/contrat-L1.md`.
- Code : branche `dev-taches-r2`, PR **#1481** (brouillon, Auto-fix allumé). Deux worktrees :
  `…\worktrees\taches-r2` (monté par la pile privée : ne pas le modifier pendant qu'un relecteur s'en sert ; le mettre à
  jour par `git merge --ff-only origin/dev-taches-r2`, puis `bash docs/taches/travail/r2/lancer-django.sh` si des
  migrations sont arrivées, et `npm run build` dans `frontend`) et `…\worktrees\taches-r2-ci` (plis, fusion de main,
  dérivés ; pousser par `git push origin HEAD:dev-taches-r2`).
- Pile privée : front http://127.0.0.1:5180, Django :8010 (conteneurs `taches-r2-django`, `taches-r2-redis`), comptes
  `revue1…6`, `revide`, `lane1…8` ; mot de passe dans `…\scratchpad\r2\env.local`.
- Claims : `file:docs/plans/PLAN_TACHES.md app:taches` tenues par `Reda_Laptop/dev-taches-r2` (à relâcher APRÈS le merge ;
  `python scripts/plan_claims.py renew|release …`).
- Plan : `docs/plans/PLAN_TACHES.md` porte TCH180 à TCH189 (vagues 1 et 2) ; la vague 3 reste à y inscrire (TCH190+),
  avec « Nouveau fichier car : » pour tout fichier de test neuf.

## Déroulé
1. Tour 1 : 6 relecteurs opus sur l'écran réel → 152 constats → 102 corrections `R2-NNN` → 8 lanes + 3 lanes de
   seconde vague + couture, toutes pliées. Suite front du module : 1 074 verts.
2. CI de la PR : gardes (liste paginée, paramètres de requête, placement des tests, déterminisme), cloche (axe 4.14),
   api-fuzz (≈ 46 constats latents : le schéma dit maintenant la vérité du serveur, refus d'état en 409), z-index,
   trois tests du rythme : corrigés et pliés (tête `74f52651b`). Reste à confirmer par le prochain run.
3. Tour 2 : 5 relecteurs neufs → sur 191 contre-vérifications : 143 réglées, 37 à moitié, 5 pas réglées, 3 régressions ;
   78 constats neufs → 84 corrections `R3-NNN`, 7 lanes (`tour2/consolidation.md`), choix C-13 à C-24.
4. Vague 3 PLIÉE (19/11) : L1 serveur, L2 Aujourd'hui, L3 saisie, L4 fiche, L5 enveloppe, L6 agenda et projets, L7
   lexique + couture, plus quatre passes de CI (api-fuzz entièrement vert, refus d'état en 409). Tête d'intégration
   `4422ae885` ; plan : TCH190 à TCH197 ; restes : `vague3-restes.md` ; budget du bundle posé à 3 905 Ko.
   Suite front du module : 1 198 verts ; specs `taches-*.spec.js` : 92 / 92 contre le build assemblé.
5. Tour 3 EN COURS : quatre relecteurs neufs (T3-F fonctions, T3-S simplicité, T3-B1 beauté iPhone, T3-B2 beauté
   bureau), rapports `tour3/` ; chaque constat neuf est marqué « avant le merge » ou « peut attendre ».
6. Ensuite : trier le tour 3 (ne corriger que les « avant le merge » + les régressions), une dernière lane de
   correction, CI verte sur la PR #1481 (dernier run connu : rouge seulement sur le budget du bundle, la garde
   anti-jargon et À trier — corrigés par L7, à confirmer), critique finale (un passage Fable permis), sortir la PR du
   brouillon, `gh pr merge 1481 --auto --merge` (ne plus toucher la PR une fois en file), relâcher les claims
   (`python scripts/plan_claims.py release file:docs/plans/PLAN_TACHES.md app:taches --owner Reda_Laptop/dev-taches-r2`),
   arrêter la pile privée (`docker rm -f taches-r2-django taches-r2-redis`, tuer le `vite preview` du port 5180,
   `DROP DATABASE erp_taches_r2`), mémoire partagée, rapport à Reda (deploy = lui).

## À dire à Reda dans le rapport final
- Rien n'a été vu sur un vrai iPhone (tout en Chromium émulé) ; notifications, Siri, tuile, calendrier abonné : ses
  gestes (README « À essayer par Reda sur son iPhone », « Vos gestes sur le serveur »).
- Les choix pris seul (C-1 à C-24), réversibles.
- Hors module, signalés et non touchés : barre et recherche de l'ERP (blanche en sombre, « Tâches » ×5 au bureau),
  onglet « Apps », menu déroulant de l'ERP, fenêtre « Bienvenue », l'assistant (`features/ia` : silence quand le service
  ne répond pas — session « Copilote v2 »).
- Le contrôle api-fuzz ne lisait pas les routes Tâches avant le 18/11 (compte de fuzz sans droit) : corrigé à la racine.
