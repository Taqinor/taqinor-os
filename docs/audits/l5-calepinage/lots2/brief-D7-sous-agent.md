# Brief sous-agent — lot D7 (corrections des constats du tour 1) — campagne L5 calepinage, 21/11/2026

Tu es un rédacteur de tâches v3 pour UN GROUPE du lot D7. Tu n'édites AUCUN fichier du dépôt (lecture seule : Read/Grep/Glob, `git grep`, `python` pour
`scripts/check_ownership.py` et le validateur ; ni docker, ni tests). Dépôt : `C:\dev\taqinor-os\.claude\worktrees\calpinage-module-enhance-04bba5`
(code lu = `origin/main@207c7a70e` ; les constats ont été relevés sur `da49cb55b`, ancêtre — le code des fichiers visés est le même, REVÉRIFIE).

Before reporting progress, audit each claim against a tool result from this session. Only report work you can point to evidence for; if something is not yet verified, say so explicitly. If tests fail, say so with the output.

## À lire d'abord, EN ENTIER, dans cet ordre (S = `C:\Users\kasri\AppData\Local\Temp\claude\3e013d81c7d3451c\34e718a0-d494-4e8f-b5dd-46bfdf94a28e\scratchpad`)
1. `S\l5\brief-redacteur-vague2.md` (addendum) puis `S\plan\brief-redacteur.md` (règle de FORME : 14 clauses v3, ancres, propriété, validateur) ; le présent brief
   MODIFIE ces deux-là sur les points ci-dessous.
2. Ta source : `S\l5\backlog\D7-constats-tour1.md` (les fiches `CAP-D7-nn` de ton groupe) ; puis, pour la CAUSE et les chiffres : `S\l5\T1\rejeu.md`,
   `S\l5\T1\consolidation.md`, les fiches de classe `S\l5\T1\classes\K-*.md` citées par ta fiche, et le verdict par constat :
   `S\l5\registre\evenements\T1-consolidation.jsonl` (une ligne JSON par constat ; `id` = `T1-<relecteur>-<nnn>`). Les constats bruts (texte du relecteur,
   étapes pour reproduire) sont dans `S\l5\registre\constats\T1-{F1,S1,B1,S2,T1}.jsonl` — lis-les pour écrire un Given/When/Then exact.
3. Tâches existantes citées (`docs/plans/PLAN_AUDIT_CALEPINAGE.md`, `grep -E "^- \[.\] ACALnnn "`) : lis celles que ta fiche nomme (ACAL382/383 goldens, 385, 397, 399, 401,
   404-405, 417, 420, 423, 427-432, 435-436, 478-480, 482…) pour ne rien contredire ni dupliquer.
4. Exemples de lignes v3 correctes (forme, longueur) : `S\l5\lots2\partB-lot.md` (3 premières tâches) — même gabarit.

## Ce qui est PROPRE à ce lot : ce sont des corrections de DÉFAUTS
- Une tâche = UN comportement observable corrigé, écrit avec son TEST ROUGE d'abord sur le CAS REPRODUIT (le rejeu donne les chiffres : 93 504 / 98 574 / 111 420 kWh/an ;
  72 kWc / 720 W contre 71,00 / 710 W ; 218 modules = 42 + 176 ; DEV-202611-0009, DEV-202611-0007 ; 168 800 MAD / 34 kWc sans facture ; 194 → 97 m² ; etc.). Le test est rouge
  aujourd'hui, vert après, et un MUTANT (« ligne changée ⇒ échec ») est nommé. Les relecteurs ont fait ces gestes sur le vrai produit : « Preuve en direct » = rejouer LE geste
  du constat (cal 16/18/19/21/22 du jeu REV-COUTURE) — l'orchestrateur la joue, jamais la lane ; écris-la quand même, précise.
- JUMEAUX : chaque tâche nomme ses jumeaux (rejeu : `plan_cablage.py::_coins`, `roofToolShared.ts` dblclick des simulateurs publics, `contexteToDevisPayload` mode devis,
  `Ombriere.jsx` « 180 = sud »…). Un jumeau est soit corrigé DANS la tâche (alors son fichier est dans `Files:`), soit nommé « autre geste : <raison> » avec le plan du propriétaire.
- Un chiffre que voit un CLIENT dans le PDF `/proposal` : la tâche le dit dans Given/When/Then et ajoute exactement « devis déjà envoyés : inchangés (ils gardent ce que le client a reçu) ;
  dry-run des écarts avant toute réparation » (mémoire fondateur 08/10). Jamais de réparation de devis existants. `/proposal` lui-même (règle #4) ne change pas de forme ; le moteur
  `apps/ventes/quote_engine/**` n'est jamais édité.
- Une étude d'architecture tourne en parallèle sur « un seul moteur pour le devis rapide du CRM et l'atelier » (lot D8) : NE LA CONÇOIS PAS. Corrige chaque défaut à sa cause ; quand la vraie
  correction est « calculer en un seul endroit », écris la plus petite correction maintenant et nomme dans `Hors périmètre` : « l'unification appartient au lot D8 ».
- Décisions de design : tranchées par la PREUVE (fiches, rapports des relecteurs, maquettes `docs/audits/l5-calepinage/maquettes/*.dc.html`), jamais « à valider par Reda ». GATED
  seulement pour : dépense/dépendance payante, ce que voit le client hors du devis, règle légale ou commerciale, donnée propre à sa société, création de données d'exemple en prod.
  Seule tâche GATED prévue dans ce lot : la règle « structures acier et socles » (id 927) — raison en UNE phrase qui nomme la décision.
- Zéro chiffre inventé : aucune constante « par défaut » en dur ; une valeur proposée vient du profil de départ sourcé (D-ACAL-31 / ACAL404) ou la tâche dit que le constructeur la relit à la source.
- Conformité au guidage : toute tâche qui crée/déplace de l'interface cite la maquette qu'elle réalise (chemin `docs/audits/l5-calepinage/maquettes/<Fichier>.dc.html`, sans `::`) et place
  l'élément dans une étape (Toit / Panneaux / Électrique / Résultats / Documents), niveau essentiel ou expert ; cibles ≥ 44 px, texte ≥ 12 px, mots simples.

## Forme : ce qui est précisé ou changé
- Constat : `C-ACAL-L5-<numéro de la tâche>` ; entre parenthèses `(C<n>, S<n>, STATIQUE (lecture du 21/11 sur 207c7a70e))` où C<n> = critère de `docs/audits/METHODE.md` §A.4 (C1 chiffres client,
  C3 un seul calcul, C6 saisie jamais perdue, C7 un seul calcul/rapprochement, C10 coutures/contrat, C13 fiabilité d'exécution, C15 parcours, C18 état visible…) et S<n> = la gravité du relecteur ;
  la clause cite la fiche (`CAP-D7-nn`), les ids de constat (`T1-S1-005`…), les « vu au rejeu » (`REJEU-NEW-n`) et la cause `fichier::symbole` relue par TOI aujourd'hui. Priorité P0 / P1 / P2 / P3 comme la fiche.
- Tampon fin : `(gen manuel 207c7a7)` puis `Files:` en dernier, puis `(ROUTINE|SCHEMA|ARCH)` `(@after: …)` `(@lane: …)` `(@model: …)` — exactement comme `partB-lot.md`.
- `@model` : `opus` pour le moteur de devis, l'argent, `core/**`, droits ; `sonnet` sinon ; `haiku` pour le purement mécanique (texte, CSS).
- `@lane` : réutilise `calepinage/atelier-web` (tout fichier `apps/web/src/scripts/roof-tool-pro11.ts`, `roofPro11/**`), `calepinage/atelier-erp` (ToitureDesign, BuilderDom, rail, onglets), `calepinage/resultats`,
  `calepinage/simulation`, `calepinage/documents` (planche, DXF, plans), `calepinage/reglages`, `calepinage/style`, `calepinage/electrique`, `calepinage/mobile`, `calepinage/devis` (generer_devis, geometrie.py) —
  fichiers mono-écrivain = même lane pour toutes les tâches qui les touchent.
- Routage par propriétaire : `python scripts/check_ownership.py --owner-of <chemin>` pour CHAQUE fichier de `Files:` (déjà vérifiés : `apps/web/src/lib/roofPro2.ts`, `estimatorBrainV7.ts`, `apps/ventes/domain/geometrie.py`,
  `core/calepinage/**`, `frontend/src/api/calepinageApi.js` = calepinage ; `apps/web/src/lib/estimatorBrainCommun.ts`, `apps/web/src/scripts/roofToolShared.ts` = web ; `apps/ventes/domain/pipeline.py`, `composition.py` = devis ;
  `apps/ventes/economie.py` = moteur ; `frontend/src/api/axios.js`, `frontend/src/styles/deploy/*.css` = deploy). Tâche mono-propriétaire calepinage → fichier principal ; autre propriétaire → fichier « autres plans »
  sous `## → <plan du propriétaire>` (devis = `docs/plans/PLAN_AUDIT_DEVIS.md`, web = `docs/WEB_PLAN.md`, moteur = `docs/plans/PLAN_AUDIT_MOTEUR.md`, deploy = `docs/plans/PLAN_AUDIT_DEPLOY.md`, lead = `docs/plans/PLAN_AUDIT_LEAD.md`).
  Tâche à cheval sur deux propriétaires : la SCINDER (contrat d'abord) — mais le budget d'ids est exact : utilise celui qui t'est donné, sinon ramène la tâche à UN propriétaire et nomme l'autre moitié « autre geste » (Hors périmètre).
  NE touche PAS `frontend/src/api/axios.js` (propriétaire deploy) : un délai de téléchargement se règle dans `calepinageApi.js` par la config de la requête.
- Un fichier de test : le module de test EXISTANT du symbole (jamais `test_<id>_*.py`) ; un cas nouveau s'écrit « (nouveau cas « … »)». Un fichier ≥ 2 000 lignes (`wc -l`) ne grossit pas : fichier voisin + un point d'appel.
- Backend ET frontend : `Contrat partagé :` nomme l'échantillon `backend/django_core/apps/calepinage/contract_samples/<x>.json` (existant : vérifie par `ls`), affirmé par le test backend ET importé par le test frontend.
- Longueur : ≤ 3 500 caractères par ligne (le validateur signale la longueur). UNE ligne physique par tâche, sans retour à la ligne.
- Dépendances de ce lot (utilise-les en `@after`) : ids du lot = 911-990 ; le tableau d'ids de TON groupe est plus bas ; tâches existantes ouvertes : ACAL385, 397, 399, 401, 404, 405, 420, 427-432, 435, 436, 478-480, 482 ;
  tâches cochées : ACAL382, 383, 386-391.
- Si la prémisse d'une tâche est FAUSSE aujourd'hui (déjà corrigée, ou la cause n'existe pas) : n'écris pas la tâche, dis-le avec la preuve `fichier::symbole`. Si elle est partiellement fausse : réécris le titre sur le vrai manque.
  Si deux tâches de ta liste se révèlent une seule cause : fusionne et libère un id (dis-le). N'invente aucune tâche hors liste.
- Les causes marquées « probable » dans la fiche : TU les lis (le fichier) avant d'écrire ; si elle reste invérifiable, écris la tâche avec une clause « Constat » qui dit « cause lue : … ; non rejouée » et fais de la PREMIÈRE étape du Given/When/Then un contrôle qui échoue si la cause est autre.

## Sorties (crée les fichiers ; dossier `S\l5\lots2\`)
- `D7-part-<G>.md` : tes tâches propres au propriétaire calepinage, réparties sous les titres EXACTS, dans cet ordre :
  `### ACAL — M1 bloquant-fondateur` (P0 et P1) · `### ACAL — M2` (P2, P3) · `### ACAL — GATED (ne PAS auto-construire)` (forme : `- [ ] ACALnnn — **[GATED : raison] titre**` + le reste de la ligne v3).
- `D7-part-<G>-autres.md` : tes tâches d'un autre propriétaire, sous `## → <plan>` (puis les mêmes trois sous-titres si besoin).
- Valide : `PYTHONIOENCODING=utf-8 python "S/valide_lot.py" "<fichier>"` (S en `/`) → « 0 en echec » pour le fichier calepinage ; pour le fichier « autres », ignore SEULEMENT les lignes « proprietaire de … » après avoir vérifié toi-même que
  tous les fichiers de la tâche ont le même autre propriétaire.
- Compte rendu (≤ 25 lignes, via SubagentHandback) : ids écrits par fichier/section ; tâches supprimées/fusionnées (preuve) ; prémisses fausses ; jumeaux « autre geste » nommés ; dépendances à poser sur des tâches EXISTANTES
  (ex. « ACAL397 doit porter `@after: ACAL937` ») ; dernière ligne du validateur ; ce qui n'est pas vérifié.
