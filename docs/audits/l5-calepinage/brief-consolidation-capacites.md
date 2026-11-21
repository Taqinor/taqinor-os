# Brief commun — consolidation des capacités (campagne L5 calepinage, tour 1)

Before reporting progress, audit each claim against a tool result from this session. Only report work you can point to evidence for; if something is not yet verified, say so explicitly. If tests fail, say so with the output.

## Contexte
Reda (fondateur non-codeur d'un installateur solaire marocain) veut que son module « calepinage » (atelier 3D toit/sol,
ombrage, simulation, électrique, stockage, pompage, documents — dans son ERP) « really compete » avec PVsyst, PV*SOL,
Aurora, OpenSolar, HelioScope, Reonic… avec « much more functionalities », tout en étant « extremely simple » et « the
most pretty ». Onze lanes d'étude ont produit ≈ 4 700 lignes (manuels, notes de version, forums en 6 langues, avis,
dépôts open source). Elles se recoupent, se contredisent parfois sur ce que NOTRE code fait déjà, et proposent ≈ 250
capacités sous des identifiants différents. Ton travail : en faire, pour TON domaine, UNE liste propre, vérifiée dans le
code, classée — la matière première de la deuxième vague de tâches.

Dépôt (LECTURE seule, aucun fichier modifié, pas de docker, pas de tests) :
`C:\dev\taqinor-os\.claude\worktrees\calpinage-module-enhance-04bba5`
Dossier d'étude : `C:\Users\kasri\AppData\Local\Temp\claude\3e013d81c7d3451c\34e718a0-d494-4e8f-b5dd-46bfdf94a28e\scratchpad\l5\bench\`
- `B1-pvsyst-pvsol.md` (manuels ; propositions C01-C26 ; § 8.3 valeurs par défaut publiées ; § 6 comparaison des rapports)
- `B2-aurora-opensolar.md` (pages publiques ; 20 propositions) · `B3-outils-conception.md` (HelioScope, Reonic, PVcase… ; N1-N34 ; § 5 parcours de référence)
- `B4-voix-des-utilisateurs.md` (20 propositions) · `B5-forums-allemand.md` (K01-K51, P1-P19 + passe 2 si présente) · `B5-forums-francais.md` (19) · `B5-forums-anglais.md` (1-21) · `B5-forums-es-pt-it.md` (1-27 ; § 4.1 pompage) · `B5-forums-nl-pl-tr-ar.md` (8)
- `B6-notes-de-version.md` (96 grappes, R1-R63, « table stakes », directions 2025-26) · `B7-demandes-utilisateurs.md` (81 grappes, U1-U30)
Ces fichiers sont gros : lis d'abord, dans CHACUN, les sections de grappes et de propositions (pas toutes les lignes),
puis va chercher les lignes de preuve de ce que tu retiens (`grep -n "<mot>" <fichier>`).
Plan existant (ne pas dupliquer) : `docs/plans/PLAN_AUDIT_CALEPINAGE.md` (tâches ACAL382-ACAL490 du « complément du
2026-11-20 »), `docs/PLAN2.md` (CAL*, CALX*), dossier `docs/audits/2026-11-20-calepinage-l5.md`.

## Méthode (dans cet ordre)
1. RASSEMBLER toutes les propositions et grappes de TON domaine dans les onze fichiers ; fusionner les doublons (une
   capacité = un besoin d'utilisateur, quel que soit le nom que chaque lane lui donne) en gardant TOUS les identifiants
   d'origine et le compte de preuves (lanes distinctes, fils/votes, outils qui la livrent).
2. VÉRIFIER dans le code, toi-même, chaque capacité retenue — les lanes ont classé sur des inventaires approximatifs et
   se contredisent (ex. import PAN/OND : « absent » pour l'une, `apps/stock/importers/fiche_pan_ond.py` pour l'autre).
   Lis le code réel (`backend/django_core/apps/calepinage/**`, `backend/django_core/core/calepinage/**`,
   `core/electrique/**`, `core/pompage/**`, `apps/stock/**` pour les fiches, `apps/installations/**`, `apps/visites/**`,
   `frontend/src/features/calepinage/**`, `frontend/src/pages/ventes/ToitureDesign.jsx`,
   `apps/web/src/scripts/roofPro11/**`, `apps/web/src/lib/**`). Verdict : PRÉSENT ET VISIBLE (écran nommé) ·
   PRÉSENT SANS ÉCRAN (calculé ou codé, aucun bouton/écran — à BRANCHER) · PARTIEL (le cas manquant, précis) · ABSENT ·
   DÉJÀ PLANIFIÉ (id exact ; si la tâche existante ne couvre qu'une partie, dis laquelle).
   Preuve = `fichier::symbole` (jamais un numéro de ligne seul).
3. ÉCARTER ce qui contredit une décision : aucune donnée ni logiciel payant (Google Solar, Meteonorm, Nearmap, LiDAR
   payant) ; pas de trackers ; pas de sous-horaire ; pas d'argent calculé dans le calepinage (finance = `apps/ventes`) ;
   pas de calcul normatif vent/neige (saisie société sourcée seulement) ; rien qui change le PDF client `/proposal` ni un
   statut de devis ; P99 refusé (D-ACAL-34) ; ZÉRO CHIFFRE INVENTÉ (toute valeur = réelle, sourcée, ou omise et nommée ;
   jamais un coefficient codé en dur — une valeur « par défaut » ne peut venir que du « profil de départ » sourcé,
   D-ACAL-31). Chaque écart va dans une liste « écarté » avec sa raison en une ligne.
4. CLASSER les capacités retenues : score = preuves (lanes distinctes × force : forum réel > notes de version > page
   commerciale) × adéquation à CET utilisateur (toits résidentiels, toits-terrasses béton avec châssis lestés, toits
   tertiaires/industriels et ombrières, champs au sol agricoles, POMPAGE solaire, réseau faible, chaleur et poussière ;
   commerciales non-ingénieures ; équipe de pose ; français) ÷ effort (S/M/L, d'après le code lu).
5. Pour chaque capacité retenue, écrire une FICHE :
   `### CAP-<D>-<nn> — <titre en français simple>`
   - Besoin (mots de l'utilisateur) · Preuves (ids d'origine + comptes + 2-3 URL parmi celles des lanes)
   - Qui le fait et comment (outil, geste, sortie — 1-2 lignes)
   - Chez nous aujourd'hui : verdict + `fichier::symbole`
   - Plus petite version crédible (ce que l'utilisateur voit et fait ; ce que le serveur calcule ; les entrées et leur
     SOURCE ; ce qui est omis et nommé si l'entrée manque)
   - Simplicité : comment cela reste invisible ou automatique pour une non-ingénieure (étape du parcours guidé :
     Toit / Panneaux / Électrique / Résultats / Documents ; « essentiel » ou « expert »)
   - Découpe en tâches : 1 à 5 tâches d'UN comportement chacune (titre « verbe + objet ; fini quand <observable> »,
     fichiers probables — tous du propriétaire `calepinage` : vérifie par
     `python scripts/check_ownership.py --owner-of <fichier>` ; un fichier d'un autre propriétaire ⇒ dis lequel et
     vers quel plan router), dépendances vers des tâches existantes (ACALnnn)
   - Score (preuves / adéquation / effort) et rang.
6. Finir par : la table de synthèse (rang, CAP, titre, verdict, nb de tâches, effort), la liste « écarté », la liste
   « contradictions entre lanes tranchées par le code » (qui avait tort), et « non vérifié ».

## Qualité
- Pas de remplissage : une capacité sans preuve d'au moins une lane ET sans manque prouvé dans le code n'est pas une
  fiche. Pas d'omission non plus : chaque proposition des lanes de ton domaine finit soit dans une fiche, soit dans
  « écarté », soit dans « déjà planifié » — donne le tableau de correspondance (id d'origine → sort).
- Une capacité « PRÉSENT SANS ÉCRAN » est précieuse (le travail est fait, il manque le bouton) : mets-la en tête.
- Écris en français simple ; garde les termes techniques entre parenthèses.
