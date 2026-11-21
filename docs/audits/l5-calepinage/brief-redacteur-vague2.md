# Vague 2 — addendum au brief des rédacteurs (campagne L5 calepinage, 21/11/2026)

Lis D'ABORD, en entier, le brief du tour 0 — il reste la règle de forme (14 clauses v3, ancres, propriété, validateur) :
`C:\Users\kasri\AppData\Local\Temp\claude\3e013d81c7d3451c\34e718a0-d494-4e8f-b5dd-46bfdf94a28e\scratchpad\plan\brief-redacteur.md`
Puis cet addendum, qui le MODIFIE sur les points suivants.

Before reporting progress, audit each claim against a tool result from this session. Only report work you can point to evidence for; if something is not yet verified, say so explicitly. If tests fail, say so with the output.

## Ce qui change par rapport au tour 0
1. **Ta source n'est plus un squelette : c'est une fiche de backlog** `…\scratchpad\l5\backlog\D<n>-….md` (cartes
   `CAP-D<n>-<nn>`), écrite par un juge qui a déjà vérifié chaque capacité dans le code et l'a découpée en tâches d'un
   comportement. Tu transformes ces tâches en lignes v3. Tu RE-VÉRIFIES quand même chaque prémisse : le dépôt a bougé
   (l'autre poste a mergé le bloc M0 : ACAL382, 383, 386-391 sont cochées), le worktree est à jour de
   `origin/main@207c7a70e`. Une capacité entre-temps construite ⇒ pas de tâche, dis-le.
2. **Quelles fiches deviennent des tâches** (les autres vont dans ta liste « réserve », une ligne chacune avec la raison) :
   toutes les fiches « PRÉSENT SANS ÉCRAN » ; toutes celles liées à un constat de relecteur (`T1-…`) ; toutes celles
   dont les preuves viennent d'au moins DEUX lanes indépendantes (forums de langues différentes, notes de version de
   plusieurs outils, manuel + forum…) ; et celles que le juge a classées dans son premier tiers. Une fiche portée par
   une seule page commerciale, ou d'effort L pour un besoin d'une seule source, va en réserve.
3. **Décisions de design : elles se tranchent par la PREUVE, jamais « à valider par Reda »** (Reda, 21/11 : « it is not
   me who have data on best practice and on what users perefer »). Ne mets une tâche en GATED que pour ce qui est
   VRAIMENT à lui : dépense ou dépendance payante, ce que voit le client hors du devis (lien, vidéo, photo, fiche
   « pertes expliquées »), règle légale ou commerciale, donnée propre à sa société (distributeurs marocains et leurs
   pièces), création de données d'exemple en production. Tout le reste (libellés, disposition, ordre, ce qui est
   « essentiel » ou « expert ») : décide d'après les fiches, les rapports des relecteurs (`…\l5\T1\*.md`) et les
   maquettes (`docs/audits/l5-calepinage/maquettes/*.dc.html`), et écris la tâche.
4. **Les maquettes font foi pour l'écran** : une tâche qui crée ou déplace de l'interface cite la maquette qu'elle
   réalise (`docs/audits/l5-calepinage/maquettes/<Fichier>.dc.html`, chemin sans `::`) dans sa clause « Given… Then »
   ou « Code net », et place l'élément dans le parcours guidé (étape Toit / Panneaux / Électrique / Résultats /
   Documents ; niveau essentiel ou expert). Système visuel : jetons de l'ERP, 6 tailles de texte (12/14/16/20/28/40),
   cibles ≥ 44 px, aucun texte sous 12 px, mots simples (« poussière », pas « salissure »).
5. **Zéro chiffre inventé, renforcé** : toute valeur proposée à l'utilisateur vient du « profil de départ » sourcé
   (D-ACAL-31 ; valeurs publiées relevées dans `…\l5\bench\B1-pvsyst-pvsol.md` § 8.3, à RELIRE à la source par le
   constructeur — la tâche le dit) ; un seuil est un réglage société sourcé, jamais une constante. Les constantes
   trouvées en dur (`SOLAR_ACCESS_LOW = 0.75`, `DIFFUSE_FRACTION_WHEN_SHADED = 0.25`, `CLEARANCE_BY_TYPE`,
   `IMAGERY_SUN_DEFAULT`, « × 720 W ») sont des défauts à corriger, pas des modèles à suivre.
6. **Routage par propriétaire** (vérifie CHAQUE fichier : `python scripts/check_ownership.py --owner-of <chemin>`) :
   une tâche dont tous les fichiers sont au propriétaire `calepinage` va dans ton fichier de lot principal ; une tâche
   dont les fichiers sont à un AUTRE propriétaire (ex. `core/pompage/**` → `devis`, `apps/crm/**` → `lead`,
   `apps/installations/**` → `chantiers`, `ProduitForm.jsx` et migrations stock → `stock`, `apps/web/src/lib/estimatorBrainV2.ts`
   → `web`) s'écrit AUSSI en v3, avec le préfixe ACAL, mais dans un second fichier `lot-<D>-autres-plans.md`, sous une
   ligne `## → <plan du propriétaire>` (le `plan:` de `docs/ownership.yml`). Une tâche à cheval sur deux propriétaires
   se SCINDE en deux moitiés mono-propriétaire (contrat d'abord). Le validateur ne juge que le propriétaire
   `calepinage` : pour le second fichier, lance-le quand même et ignore SEULEMENT ses lignes « proprietaire de … »
   après avoir vérifié toi-même que tous les fichiers de la tâche sont au même autre propriétaire.
7. **Forme** : constat `C-ACAL-L5-<numéro de la tâche>` ; mention de lecture
   `STATIQUE (lecture du 21/11 sur 207c7a70e)` ; tampon `(gen manuel 207c7a7)` ; la clause Constat cite la fiche
   (`CAP-D<n>-<nn>`), les ids d'origine des lanes et, s'il y en a, les constats de relecteurs. Priorité : P0 = chiffre
   faux visible du client ; P1 = présent sans écran, geste courant cassé ; P2 = capacité du premier tiers ; P3 = le reste.
8. **Sections de ton fichier de lot** (titres exacts, dans cet ordre) :
   `### ACAL — M1 bloquant-fondateur` (P0 et P1) · `### ACAL — M2` (P2, P3) · `### ACAL — GATED (ne PAS auto-construire)`
   (forme des lignes GATED : comme le tour 0 — `- [ ] ACALnnn — **[GATED : raison] titre**`, la raison nomme la décision
   attendue de Reda en une phrase).
9. **Volume et longueur** : écris TOUTES les tâches retenues de ta fiche (pas d'échantillon). Vise ≤ 3 500 caractères
   par tâche ; si ton lot dépasse ~25 tâches, tu peux te faire aider de sous-agents `sonnet` (un par groupe de fiches,
   même brief, plages d'ids disjointes dans la tienne) — tu restes responsable du fichier final et du validateur.
10. **Ne touche à aucun fichier du dépôt** : `docs/plans/PLAN_AUDIT_CALEPINAGE.md` est tenu par un autre poste ;
    l'orchestrateur insérera les lots quand le bail sera libre.

## Validateur (inchangé)
`PYTHONIOENCODING=utf-8 python "C:/Users/kasri/AppData/Local/Temp/claude/3e013d81c7d3451c/34e718a0-d494-4e8f-b5dd-46bfdf94a28e/scratchpad/valide_lot.py" "<ton fichier de lot>"` → « 0 en echec » (hors l'exception du point 6).

## Compte rendu (≤ 30 lignes)
Tâches écrites par section (ids) ; fiches mises en réserve (une ligne chacune) ; fiches devenues sans objet (déjà
construites : preuve) ; tâches routées vers d'autres plans (plan → ids) ; tâches GATED et la décision attendue ;
dernière ligne du validateur ; prémisses de la fiche trouvées fausses.
