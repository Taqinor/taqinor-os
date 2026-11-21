# CRITIQUE ADVERSE FINALE — vague 2 du complément L5 calepinage (472 tâches), 21/11/2026

Critique unique, contexte neuf. Lecture seule : aucun fichier d'un dépôt modifié, aucun test, aucun docker, aucun serveur.
Code lu dans `C:\dev\taqinor-os\.claude\worktrees\l5-verif\` (HEAD `45eafba77`). Tâches lues dans `verif2/` (INDEX en
entier, lot D8 en entier, 40 tâches des autres lots ouvertes à la demande). Deux scripts en lecture seule lancés :
`scripts/plan_lanes.py docs/plans/PLAN_AUDIT_CALEPINAGE.md --workers 8 --wave-size 80` et
`scripts/check_ownership.py --owner-of <fichier>`. Chemins relatifs à `backend/django_core/` sauf mention.
Chaque constat cite ce qui a été lu dans CETTE session ; ce qui n'a pas été vérifié est en § 9.

---

## 0. Verdict

**La vague peut entrer au plan, mais pas telle quelle.** L'intention de l'architecture D8 est fidèle à la décision
corrigée (production et économie restent dans `apps/ventes`, une porte, géométrie seule dans `core/calepinage`, un niveau
de règles, aucun interrupteur d'environnement — vérifié : 0 tâche ne crée de variable d'environnement). Mais la chaîne
qui porte D-ACAL-36 (ACAL996-1001, 973, 927) ne peut pas être construite comme elle est écrite : elle n'atteint pas le
chiffre annoncé, crée une nouvelle contradiction visible du client, et sa porte fondateur se contourne dans les deux
ordres de construction. S'y ajoutent des défauts mécaniques de la vague entière (modèle sans migration, 32 dépendances
entre plans laissées en prose, règle « NE PAS FAIRE » du plan violée par 17 tâches, une vingtaine de doublons D7 ↔ D1-D6).

Corrections à faire AVANT l'entrée : B1 à B8 ci-dessous (≈ 45 tâches touchées, la plupart par une clause ou un tag).
Le reste (D1-D7 hors paires nommées) peut entrer sous réserve des 17 vérificateurs.

Comptes : **8 BLOQUANTS** · **19 À CORRIGER** · **7 MANQUES** · **7 OPTIONNELS**.

---

## 1. BLOQUANTS

### B1 — ACAL999 + ACAL973 : le chiffre annoncé n'est pas atteignable, et le client verrait deux productions au niveau 15
Tâches : ACAL999 (plan devis), ACAL973 (plan moteur). Décision portée : D-ACAL-36.

Cinq prémisses lues dans le code contredisent les deux tâches :

1. **Le moteur horaire réapplique les pertes.** `apps/ventes/etude_horaire.py::jours_types_annee` l.899 met la série
   mensuelle PVGIS à l'échelle de `productible_kwh_kwc`, puis l.926-928 applique
   `derate=PRODUCTION_DERATE * facteur_ombrage(perte_ombrage_pct)`. Passer 1 388,4 par ce paramètre rend
   71 × 1 388,4 × 0,9302 = **91 696 kWh** — exactement la valeur que le mutant d'ACAL973 doit faire échouer. ACAL999
   ne touche que `domain/entrees.py` ; ACAL973 écrit « `etude_horaire.py` non touché (la valeur y arrive par
   `productible_kwh_kwc`, ACAL999) ». Aucune tâche D8 ne déclare `etude_horaire.py`.
2. **Le bloc rangé ne passe pas par `entrees.py`.** Le bloc `etude_params.etude_horaire` est calculé par
   `etude_horaire.py::_etude_horaire_pour_devis` (l.1968), qui appelle directement `perte_ombrage_du_devis(devis)`
   (l.2048) et `productible_du_devis(devis)` (l.2061, import l.94 de `horaire/productible_societe.py`).
   `entrees.py::_productible_du_devis` (l.380-383), seul point édité par ACAL999, n'alimente que l'empreinte, le
   dimensionnement et le balayage. Résultat tel qu'écrit : la TAILLE lit la pose réelle, le BLOC (donc les économies)
   lit la ville.
3. **Le PDF imprime la production du bloc rangé quand il existe.** `quote_engine/pricing.py::calculate_savings_roi`
   l.1736-1741 : `_h = _lire_etude_horaire(...)` puis `production_annuelle = _h["prod_kwh"]`. La formule
   kWc × productible × `PRODUCTION_DERATE` (l.1604-1607) ne sert que SANS bloc. Le correctif d'ACAL973 (« point d'appel
   seul », `productible=`) est donc écrasé sur tout devis à facture connue — le cas normal.
4. **Les lecteurs de la page publique ne suivent pas.** `public/payload_horaire.py` l.267-277, l.372-382, l.412-415,
   `public/payload_batterie.py` l.502-530, `courbes_journalieres.py` l.1342-1345 (`facteur_production_saison`,
   `horaire/ombrage.py` l.103-117) et l'aperçu `etude_horaire_view.py` l.651-653 calculent tous sur PVGIS ville ×
   `PRODUCTION_DERATE` × ombrage. ACAL973 affirme « la page publique lit le bloc rangé » : faux pour ces blocs. Au
   niveau 15 le client lirait une production annuelle « pose réelle » et des courbes par saison « ville ».
5. **Le gel d'un devis envoyé n'a pas de valeur à relire.** Le patron cité (`horaire/ombrage.py::_perte_rangee`,
   l.70-80) relit `etude_horaire.ombrage.perte_pct`. ACAL999 ne persiste que `etude_horaire.production.source` : pour un
   devis non brouillon il n'y a ni `kwh_kwc_annuel` ni forme mensuelle rangés à relire.

Conséquence : « fini quand » inatteignable avec les `Files:` déclarés ; construit quand même, il laisse trois valeurs
de production sur un même devis de niveau 15 (taille, bloc/PDF, page publique) — la classe K-GRANDEUR-UNIQUE recréée
sur un chiffre client.

**Correction proposée.** Réécrire ACAL999 en UN résolveur et ses appelants :
- `horaire/productible_pose.py::base_de_production(devis)` rend `{productible_kwh_kwc, mensuel[12], pertes_incluses,
  perte_ombrage_pct, source}` ; brouillon = lecture vivante du sélecteur, non brouillon = valeur RANGÉE.
- `etude_horaire.py::jours_types_annee` reçoit `pertes_incluses` : vrai ⇒ `derate = 1.0` (ni `PRODUCTION_DERATE` ni
  ombrage) et la série mensuelle SERVIE (`kwh_kwc_mensuel` du contrat d'ACAL996) remplace la forme PVGIS de la ville.
- Les 9 sites lisent le résolveur : `etude_horaire.py` l.2048/2061, `domain/entrees.py` l.368-370,
  `dimensionnement_balayage.py::_productible_balayage` (l.31-37 : signature `(company, regles_2710)` sans devis — pas
  « ≈ 4 l. »), `etude_horaire_view.py` l.651-653, `public/payload_horaire.py` (3 sites), `public/payload_batterie.py`,
  `courbes_journalieres.py` l.1342, `quote_engine/etude_chiffrage.py` l.390-403.
- Persistance : `etude_horaire.production.{kwh_kwc_annuel, kwh_kwc_mensuel, source}` écrits par
  `domain/etudes.py::rafraichir_etude_horaire`.
- Test rouge ajouté : « brouillon rendu 98 576 → envoyé → calepinage re-simulé ou modifié → `/proposal` rend toujours
  98 576 » ; et « PDF = bloc = somme des courbes de la page publique à 1 kWh près ».
- Propriétaires : `etude_horaire.py`, `dimensionnement_balayage.py`, `etude_chiffrage.py` → moteur ; `entrees.py`,
  `public/payload_horaire.py` → devis (`check_ownership.py --owner-of`). Donc DEUX moitiés : moteur (paramètre
  `pertes_incluses`, d'abord) puis devis (résolveur + lecteurs, `@after`). ACAL973 se réduit au chemin sans bloc, à la
  mention de source en annexe et au cas de golden niveau 15.

### B2 — ACAL996 / ACAL997 : une borne haute serait servie au PDF client comme « la production »
`productible_pose_servi` rend `kwh_kwc_annuel = P50 ÷ kWc` avec `pertes_et_ombrage_inclus: true` écrit en dur. Or le
résultat servi porte `production.total.complete` : `apps/calepinage/services/chaine_pertes.py` l.1376 (« D-ACAL-7 — un
résultat incomplet ne publie ni PR ni quantile »), l.1391-1392, l.1472 (`'complete': not socle`) ; contrat
`calepinage_simulation.json` l.4 : « pertes non renseignées ⇒ P50 publié « borne haute — N pertes non renseignées » ».
La consolidation du tour 1 mesure « 35 réglages sur 37 vides » (K6) : le cas incomplet est le cas courant aujourd'hui.
Ni ACAL996 ni ACAL997 ne lisent `complete` (grep `complete|incompl|borne haute` dans le lot D8 : 0 hors une maquette).
Un plafond imprimé comme production = chiffre client faux.

**Correction.** ACAL996 : le contrat gagne `complete` et `etapes_omises` ; `pertes_et_ombrage_inclus` = `complete`.
ACAL997 : `complete is not True` ⇒ `{perime: true, motif: 'résultat incomplet : N pertes non renseignées'}` ; test rouge
« cascade incomplète ⇒ jamais servi » ; mutant « ignorer `complete` ».

### B3 — ACAL927 pose SON niveau de règles et le rend courant : la porte de D-ACAL-36 saute dans les deux ordres
ACAL998 : « niveau 15… qui porte, pour toute la vague, D-ACAL-36 et D-ACAL-39, sans le rendre courant ». ACAL927
(même plan, aucun `@after`) écrit l'inverse — Persistance : « le niveau de règles suivant (valeur libre…),
`REGLES_COURANTES` le porte, `Devis.regles_calcul` prend ce défaut ; migration… qui ne fait passer que les brouillons » ;
ses `Files:` portent `regles_calcul.py`, `models.py` et une migration ventes.
- ACAL927 d'abord : elle crée 15 et le rend courant ⇒ ACAL999/973, branchées sur `regles_au_moins(devis, 15)`
  (`domain/regles_calcul.py` l.120-132), s'allument à leur merge, sans liste d'écarts lue par Reda.
- ACAL998 d'abord : ACAL927 crée 16 courant ⇒ tout devis neuf est ≥ 15 ⇒ même résultat.
C'est le défaut que la première critique (B5 : « un niveau, une migration pour tout le lot ») avait demandé de fermer.

**Correction.** ACAL927 : retirer niveau, migration, `regles_calcul.py` et `models.py` de ses `Files:` ; se brancher sur
`regles_au_moins(devis, REGLES_POSE_REELLE_2111)` ; `(@after: ACAL998)` ; Persistance = « niveau 15 d'ACAL998, activé
par ACAL1001 ».

### B4 — ACAL1001 : la liste des écarts peut être produite AVANT le code qu'elle doit montrer
ACAL1001 `(@after: ACAL998, ACAL1000)`. ACAL1000 `(@after: ACAL998)`. Rien n'attend ACAL999, ACAL973 ni ACAL927. Lancé
tant que ces trois tâches ne sont pas mergées, `regles_calcul_ecarts_dryrun --niveau 15` rend ZÉRO écart (aucune branche
de niveau 15 n'existe encore) ; Reda lit une liste vide, la porte s'ouvre, le niveau devient courant, puis chaque tâche
de niveau 15 qui merge ensuite change les nouveaux devis sans liste.

Second défaut, même tâche : `Files:` ne porte pas `apps/ventes/models.py`, alors que le défaut est un littéral —
`models.py` l.225 `regles_calcul = models.PositiveSmallIntegerField(default=14)` — et que
`tests/test_regles_calcul_nouveaux_rendus.py` l.34 affirme `defaut == REGLES_COURANTES`. `REGLES_COURANTES = 15` seul :
test rouge et devis neufs nés à 14.

**Correction.** ACAL1001 : `(@after: ACAL998, ACAL1000, ACAL999, ACAL973, ACAL927)` ; tag GATED complété « sortie
d'ACAL1000 produite sur un commit qui contient ACAL999, ACAL973 et ACAL927 ; après l'activation, plus aucune branche
neuve sur le niveau 15 : tout changement ultérieur prend le niveau 16 » ; ajouter `apps/ventes/models.py` aux `Files:`.

### B5 — Quatre tâches posent un champ de modèle SANS sa migration ; la migration est rangée dans un autre plan
- ACAL567 (plan calepinage, `stock/models_fiche_technique.py`) ↔ ACAL570 (plan stock, migration seule).
- ACAL659, ACAL720, ACAL816 (trois lanes du plan calepinage, même modèle) ↔ ACAL660 (plan stock : UNE migration pour
  les trois). ACAL816 annonce dans son titre « modèle, sérialiseur, goldens et migration » et sa Persistance « migration
  `AddField` seule », sans fichier de migration dans ses `Files:` — contradiction avec ACAL660.
Aucun `@after`, aucun `@atomique`. La CI lance `makemigrations --check --dry-run` (`.github/workflows/ci.yml`
l.689-696) : la moitié modèle seule est rouge ; la moitié migration seule aussi (l'état des migrations porterait des
champs absents du modèle). Aucun ordre ne marche : il faut UN commit.

Le motif donné (« migrations = propriétaire stock ») ne tient pas : `docs/ownership.yml` l.920-922 classe
`apps/*/migrations/**` surface append-only, et `scripts/plan_lanes.py::_proprietaires` l.1019 (comme
`check_ownership.py` l.528) EXCLUT les surfaces append-only du calcul des propriétaires. Une tâche du plan calepinage
peut porter sa migration stock sans devenir multi-propriétaires.

Même défaut, autre paire : ACAL901 (plan calepinage, fonction publique de plus dans `ventes/selectors_calepinage.py`)
↔ ACAL1030 (plan devis, `ventes/tests/test_selectors_surface.py`, propriétaire devis, surface SPL144 l.59 et l.124) :
l'une sans l'autre est rouge.

**Correction.** Fondre ACAL570 dans ACAL567 ; fondre ACAL660 dans ACAL659 et donner à ACAL720 et ACAL816 leur propre
migration (elles partagent `models_fiche_technique.py` : même lane par construction) ; ACAL663 `(@after: ACAL659,
ACAL817)`. ACAL901 + ACAL1030 : une tâche `(@atomique: calepinage, devis)` au plan transverse (METHODE §C.5 a).

### B6 — Trois paires de tâches se contredisent : la seconde construite casse la première
1. **ACAL602 ↔ ACAL933** (même lane, même `planche.py`). ACAL602 : « jamais un rang normalisé ; 19,28 ⇒ 1/52 ; la liste
   de rangs de `_echelle_nommee` disparaît ; hors périmètre : choisir une échelle normalisée ». ACAL933 :
   « `_echelle_de_dessin` rend la plus grande échelle normalisée (un rang de `_echelle_nommee`)… la mention imprime ce
   rang ». L'une change l'étiquette, l'autre change le dessin. ACAL933 (2) double aussi ACAL603 (même toit 9,02 × 5,89).
   → garder ACAL602 + ACAL603, supprimer ACAL933 (ou l'inverse, mais une seule règle).
2. **ACAL532 ↔ ACAL599 + ACAL593.** Deux clés pour la même couche dans `roof_layout_v2.schema.json` : `reperes` (ACAL532)
   et `reperesChantier` (ACAL599), et le même fichier neuf `reperesChantier.ts` créé par ACAL532 ET par ACAL593.
   → supprimer ACAL532 ; ajouter ses types en plus (onduleur, tableau, note) à ACAL599.
3. **ACAL612/613 ↔ ACAL934/935.** Deux verdicts à trois états du même dossier électrique, deux contrats
   (`calepinage_evaluation_electrique.json::publication` : « publiable / publiable avec réserves / non publiable » ;
   `calepinage_publication_electrique.json::electrique.etat` : « prêt / à compléter / bloquant »), et le même composant
   `VerdictElectrique.jsx` réécrit deux fois avec deux vocabulaires. C'est le constat T1-S1-020 (« un seul verdict,
   même mot ») recréé par la vague. → garder ACAL934/935 (« calculé UNE fois ») ; ACAL612 se réduit à relayer cet état
   sous `publication` ; ACAL613 fusionnée dans ACAL935.

### B7 — 32 dépendances entre plans écrites en phrase, 0 en `@after`, alors que le planificateur les impose
Le dossier de la vague dit : « les dépendances vers une tâche d'un autre plan sont écrites en phrase, le planificateur ne
les impose pas ». C'est faux : `scripts/plan_lanes.py` l.123-126 et `apply_external_after_gate` l.1493-1556 refusent
une tâche tant qu'un `@after` vers un autre fichier plan n'est pas coché ; METHODE §D.3.3 exige « l'autre moitié
`@after` ». Relevé par script sur les 472 tâches : 32 arêtes en prose, aucune en tag.

Arêtes qui cassent une construction (le prérequis n'existe pas dans le code) :
ACAL993 → ACAL992 (appel d'une fonction absente) · ACAL999 → ACAL996, ACAL997 · ACAL973 → ACAL998, ACAL999 ·
ACAL1006 → ACAL1004 · ACAL589 → ACAL588 · ACAL597 → ACAL596 · ACAL667 → ACAL665 · ACAL806 → ACAL804, ACAL805 ·
ACAL810 → ACAL809 · ACAL815 → ACAL814 · ACAL820 → ACAL817, ACAL818 · ACAL821 → ACAL819 · ACAL818 → ACAL816 ·
ACAL839 → ACAL838 · ACAL846 → ACAL845 · ACAL585 → ACAL583 → ACAL581, ACAL582 · ACAL927 → ACAL1029 ·
ACAL912 → ACAL911, ACAL916 · ACAL982 → ACAL912 · ACAL976 → ACAL852 · ACAL670 → ACAL669 · ACAL571 → ACAL567 ·
ACAL817 → ACAL816. (ACAL570 et ACAL660 disparaissent avec B5.)
Hors relevé : ACAL1026 (WEB_PLAN) appelle « le réglage publié par ACAL487 » ; ACAL487 est toujours
`[GATED : autre propriétaire…]` (`docs/plans/PLAN_AUDIT_CALEPINAGE.md` l.899).

**Correction.** Écrire les 32 `@after` ; ACAL1026 `(@after: ACAL487)` et DÉGATER ACAL487 (son motif « autre
propriétaire » est levé : la moitié web existe, D-ACAL-38 a répondu — règle du 13/11 : une tâche répondue sort de GATED).

### B8 — 17 tâches violent le « NE PAS FAIRE » du plan : déclarer `selectors.py` ou `urls.py`
`docs/plans/PLAN_AUDIT_CALEPINAGE.md` l.166 (« NE PAS FAIRE (vérifié pendant l'audit) ») … l.189-190 : « déclarer
`urls.py`, `selectors.py` ou un fichier nommé `test_selectors.py` / `test_urls.py` dans `Files:` (porte PACT11) ».
Déclarent `apps/calepinage/selectors.py` : ACAL572, 588, 595, 596, 665, 770, 883, 895, 948, 960, 961, 964, 978, 997,
1008 ; `urls.py` : ACAL558, ACAL960. Effet mesuré (`plan_lanes.py` lancé ici) : 161 tâches refusées par PACT11 et 33 par
ricochet. Détail et réponse en § 4.

---

## 2. Le moteur partagé (D8) — le reste, À CORRIGER

Prémisses vérifiées et VRAIES : `regles_calcul.py` (14 niveaux, `REGLES_COURANTES = 14` l.117, migration 0159 qui ne
passe que `statut='brouillon', date_envoi__isnull=True`) ; `regles_calcul_ecarts_dryrun.py` (force le niveau 2 l.48, ne
parcourt que le niveau 1 l.68) ; `apps/calepinage/selectors.py::ombrage_servi` l.677-724 et ses aides ;
`resultat_servi` l.1230 ; `views/calepinages.py::design_context` l.1052-1054 ; `useAtelierBoot.js` l.27, 256-259,
393-396 ; `domain/geometrie.py::orientation_du_pan` l.85, `pans_du_document` l.445 (face = rangée + 90, l.553-554) ;
`core/calepinage/` pur et `core/tests/test_calepinage_purete.py::ImportsDuPaquet` l.77 ; `creation_auto.py` l.201, l.402 ;
`composition_imposee.py` l.633 ; `creation.py::adopter_ou_creer_pour_devis` l.304 (recopie le `roof_layout` du devis,
l.352) ; `coherence/regles_calepinage.py` l.88, l.108 ; `coherence/registre.py::TOLERANCES` l.48, l.78.
Aucun interrupteur d'environnement n'est créé par la vague (grep : 0).

- **C1 — ACAL992 recalcule au lieu de lire le rendu.** « Fini quand la porte rend la production et l'économie du rendu
  `/proposal` », mais le Given fait repasser les entrées dans `calculer_etude_horaire`. Le rendu, lui, sort de
  `build_quote_data` → `etude_chiffrage.py::chiffrer_etude` (bloc RANGÉ, production saisie souveraine l.553-560,
  économie imposée l.592-606, options divergentes l.498-523, jour de référence du devis). Sur ces devis la porte et le
  PDF divergeront. Clause à réécrire : calepinage lié à un devis ⇒ la porte LIT le rendu (`prod_kwh`, économie de
  l'option titrée — à nommer, le contrat n'a qu'une `economie_annee1_mad`) ; recalcul seulement sans devis.
- **C2 — La porte sans devis annoncera un chiffre que le devis démentira.** `productible_pose_servi(devis_id, company)`
  n'existe que par devis. Après ACAL1001, un calepinage simulé SANS devis affichera « standard ville » (111 420 dans
  l'exemple d'ACAL991) puis le PDF du devis généré imprimera la pose réelle. ACAL997 : ajouter la lecture par
  calepinage (`productible_pose_du_calepinage(calepinage, variante=None)`), dont la version « devis » est un habillage ;
  ACAL992 l'emploie quand les règles courantes sont ≥ 15.
- **C3 — ACAL997.** (a) La clause « un calepinage `rapide` rend `None` » dépend d'ACAL1006 (M2) alors qu'ACAL997 est M1
  `(@after: ACAL996)` : la déplacer dans ACAL1008 `(@after: ACAL997, ACAL1006)`. (b) `TOLERANCES['kwc_calepinage_ratio']`
  vit dans `apps/ventes/coherence/registre.py` : le calepinage importerait un module de ventes hors
  `selectors`/`services` — faire passer la tolérance par l'appelant. (c) Rien ne compare le kWc du DEVIS (lignes
  éditées à la main) au kWc simulé : à écrire côté ventes, hors tolérance ⇒ chemin ville + motif.
- **C4 — ACAL1004 : clé d'étude non déclarée.** `domain/etude_schema.py` tient un registre (`SCHEMA` l.106) ; `valider`
  l.543-573 reproche toute clé de tête inconnue et `fusionner` l.686-708 lève `ValueError`. `etude_schema.py` (et son
  test) manquent aux `Files:`.
- **C5 — ACAL1006.** `Files:` sans le sérialiseur de détail (cité à l'Emplacement) ni le service de la route
  d'enregistrement du document qui doit passer l'état à `complet`.
- **C6 — ACAL1008 : emplacement faux.** `services/planche.py::geometrie_de_planche(roof_layout)` l.233 reçoit le
  document, pas le calepinage : il ne connaît pas `etat_conception`. Le refus se pose à l'appelant qui tient le
  calepinage. Et `selectors.py::conception_du_devis` l.569-583 est LE lecteur de conception de `apps/ventes`
  (resynchronisation, composition) : y omettre quoi que ce soit pour un calepinage « rapide » casserait ces lecteurs.
  Nommer le lecteur exact des « paramètres du site » côté ventes (moitié moteur) ; ne jamais rendre `None`.
  Non vérifié : la visionneuse 3D de la page publique (alimentée par `proposal_data`) d'un devis « rapide ».
- **C7 — ACAL1002 ↔ ACAL911, ACAL916, ACAL921, ACAL1029 : ordre non dit sur `domain/geometrie.py`.** ACAL1002 (M2)
  écrit « les corrections se construisent ensuite DANS `pans_poses` », mais ACAL911/921 (M1) pointent `geometrie.py` et
  ne portent aucun `@after: ACAL1002` ; le mutant d'ACAL1002 (« face lue sans + 90 ⇒ échec ») contredit ACAL921 qui
  retire ce + 90. Choisir : M1 d'abord, puis ACAL1002 `(@after: ACAL911, ACAL916, ACAL921, ACAL1029)` avec un mutant
  neutre (« une surface perdue »).
- **C8 — ACAL921 ne périme pas les simulations existantes.** La lecture d'un document inchangé change (face = rangée,
  plus rangée + 90) ; l'empreinte de simulation n'a pas bougé ; les résultats déjà stockés (calculés à la mauvaise face)
  restent « frais » et seraient servis — y compris au devis par ACAL997. `services/simulation.py` l.103
  `VERSION_SIMULATION = 'sim-3'` entre dans l'empreinte (l.509) et le plan l.185 nomme ce levier. Ajouter le passage
  à `sim-4` et `services/simulation.py` aux `Files:`. Nommer aussi les deux lecteurs vivants à vérifier pour un devis
  envoyé : `apps/ventes/offres_tailles.py` l.1979, `domain/dimensionnement_devis.py` l.124.
- **C9 — ACAL999 : forme horaire.** La forme horaire des jours types reste celle de la ville à 30° sud
  (`_formes_production_par_saison`) pour un toit est-ouest : c'est une supposition, à NOMMER dans le bloc (règle du
  17/11 « tout ce qui est supposé est dit »).
- **C10 — ACAL1011.** La tolérance `production_calepinage_ratio` est « jamais devinée » mais aucune valeur ni source
  n'est donnée : écrire « égalité à 1 kWh près » (même formule des deux côtés) ou réemployer `kwc_calepinage_ratio`.
- **C11 — L'INTERDIT de tête n'est pas édité.** `PLAN_AUDIT_CALEPINAGE.md` l.176-177 interdit toujours « imprimer le
  P50 du calepinage sur le devis, le PDF ou la page publique » ; le registre dit « ligne non éditée ». Le constructeur
  d'ACAL997 lira une interdiction contraire à sa tâche. À amender dans le même commit que l'insertion (« sauf devis de
  niveau ≥ 15 à calepinage simulé complet — D-ACAL-36 »).

Chemins demandés :
- **Un devis ENVOYÉ peut-il changer ?** Oui, par B1 (5) (pas de valeur rangée), B3/B4 (niveau courant avant la liste) et
  C8 (simulation périmée servie). Non par la migration elle-même (patron 0159 lu, correct).
- **Un chiffre « rapide » peut-il atteindre le client ?** Le devis automatique reste ce qu'il est aujourd'hui (aucune
  porte ajoutée, conforme à la critique B7). Le calepinage « rapide » ne sert pas son productible (une fois C3 a
  corrigé). Reste ouvert : la 3D de la page publique (C6).

---

## 3. Fidélité aux décisions de Reda (D-ACAL-36 à 43)

Registre `docs/audits/decisions.yml` l.1525-1619 relu contre les réponses citées dans la consigne : les huit entrées
disent ce que Reda a répondu ; aucune ne l'étend. Côté tâches :

| Décision | Verdict | Détail |
|---|---|---|
| D-ACAL-36 | **non tenue telle qu'écrite** | B1, B2, B3, B4, C2, C8, C11. |
| D-ACAL-37 | fidèle | ACAL968 : une case par surface, toutes cochées à l'ouverture. |
| D-ACAL-38 | fidèle, une moitié non constructible | Aucun prix dans ACAL697, 896, 897, 1026 (clauses lues). ACAL1026 dépend d'ACAL487 encore GATED (B7). ACAL697 imprime des parts de pertes du CALEPINAGE, pas « les chiffres du devis » : préciser qu'elle n'imprime aucun kWh de production. |
| D-ACAL-39 | **étendue par défaut** | ACAL927 retire structures et socles, puis « ajoute UNE ligne kit de fixation… absent ⇒ ligne non ajoutée et avertissement ». Le constat de la tâche dit que le catalogue n'a aucun produit « kit de fixation ». À l'activation, un toit affleurant sortirait SANS aucune fixation chiffrée : ce n'est pas « kit de fixation seulement ». Voir M4. |
| D-ACAL-40 | fidèle (vérifié au code) | Le PDF résidentiel et la page publique omettent déjà toute la couche économies sans donnée réelle : `quote_engine/residential/renderer.py::ancrage_reel_absent` l.77, `synthese_economies` l.104-117, `cover.py` l.171-181, `public_views.py` l.1284 et l.1916. Non tracé : le format « une page » (`generate_devis_premium.py` l.2035-2046 imprime l'économie avec la mention « estimation ») — à faire affirmer par ACAL976. |
| D-ACAL-41 | fidèle | ACAL804, 807, 814 à l'écran ; ACAL834 au rapport interne ; rien au document agricole. |
| D-ACAL-42 | fidèle | ACAL895 : modèles « Exemple », sans lead ni client ni devis, semés par une commande à la main. |
| D-ACAL-43 | fidèle | ACAL822/824 : un gabarit générique, aucune pièce ni limite livrée ; 8 tâches par distributeur retirées. |

Règle « tout ce qui est supposé est dit » : quand un devis A un calepinage enregistré mais que le PDF retombe sur le
standard de la ville (simulation absente, périmée ou incomplète), rien ne le dit à la commerciale. Voir M3.

---

## 4. Question d'ordonnancement — `selectors.py` et la porte PACT11

**Réponse : (b) est déjà la règle écrite du plan (l.189-190), à appliquer aux fonctions NEUVES ; (a) « serveurs
d'abord », en vague 0 nommée, pour les tâches qui modifient une fonction EXISTANTE de `selectors.py` ; plus trois
corrections de `Files:`. Jamais 160 × `@after`, jamais `--force-wave`.**

Ce que la porte fait (lu, `plan_lanes.py` l.1365-1489) : est PRODUCTRICE toute tâche qui déclare `urls.py` ou
`selectors.py` d'une app ; est refusée toute tâche à fichier `frontend/src/{features,pages}/<app>/` ou
`frontend/src/api/<app>Api.js` qui ne porte pas `@after` sur CHAQUE productrice de la même app encore ouverte. Une
tâche mixte n'est jamais refusée pour sa propre app mais reste productrice pour les autres. Sur les 17 productrices
calepinage de la vague, les vraies paires écran ↔ serveur passant par `selectors.py` sont trois, et elles portent déjà
leur `@after` (ACAL600 → 594, 595 ; ACAL884 → 883 ; ACAL559/560 → 558). Tout le reste est du faux positif.

Tâche par tâche :

| Tâche | Ce qu'elle fait dans `selectors.py` | Décision |
|---|---|---|
| ACAL588 | fonction NEUVE `plan_pose_svg_pour_devis`, lue par `apps/installations` (ACAL589) | → `apps/calepinage/selectors_chantier.py` |
| ACAL596 | fonction NEUVE `points_de_controle_pose`, lue par ACAL597 | → même module |
| ACAL665 | fonction NEUVE `valeurs_attendues_par_chaine`, lue par ACAL667 | → même module |
| ACAL997 | fonction NEUVE `productible_pose_servi`, lue par `apps/ventes` | → `apps/calepinage/selectors_devis.py` (importe les aides privées de `selectors.py`) |
| ACAL960 | fonction NEUVE `catalogue_materiel_de_societe` + route dans `urls.py` | fonction dans un module frère ; route par `views/rattachements.py` comme ACAL683, 730, 860, 871, 887 |
| ACAL558 | routes `parametres/systemes-fixation/` dans `urls.py` | même patron de route si la vue le permet ; sinon vague 0 |
| ACAL1008 | 2 gardes dans `url_apercu_calepinage` et `conception_du_devis` | retirer `selectors.py` : la garde va aux appelants (C6) |
| ACAL572, 770, 964 | éditent `registre_des_reglages` (existant) | restent ; vague 0 (572 après 563 ; 964 après 770) |
| ACAL595, 883, 978 | éditent `comparer_variantes` / `_ligne_comparaison` (existants) | restent ; vague 0 ; retirer ACAL884 des `@after` d'ACAL978 (une productrice qui attend un écran refusé = ordre inversé) |
| ACAL895 | 2 lignes dans `appliquer_filtres_liste` | reste ; vague 0 |
| ACAL948 | `_condition_recherche` | reste ; vague 0 |
| ACAL961 | une clé dans `SECTIONS_LECTURE_SEULE` | reste ; vague 0 (après ACAL960) |

Précédents du dépôt pour le module frère (propriété déjà déclarée dans `docs/ownership.yml`) :
`ventes/selectors_calepinage.py` l.308, `ventes/selectors_stock.py` l.602, `ventes/selectors_portail.py` l.642,
`stock/selectors_fiche_technique.py` l.284, `crm/devis_selectors.py` l.709. Je n'ai trouvé dans `.importlinter` aucun
contrat sur le NOM du module de sélecteurs (grep `selectors` : seulement des exceptions `models -> selectors`) ; le
fichier n'a pas été lu en entier.

Vague 0 (une douzaine de tâches, une seule lane, lancée par `--only`, option documentée l.100-111 : « une tâche
backend hors portée n'est pas dans le même run ») : ACAL563, 572, 594, 595, 770, 964, 883, 895, 948, 947, 960, 961,
978, 557, 558. Compter jusqu'à trois passes : ACAL947 est un écran qu'ACAL960 attend, la porte le libère seulement
quand les autres productrices sont cochées. Une fois les quinze cochées, plus aucune productrice n'est ouverte : la
porte ne refuse plus rien.

Trois `Files:` à corriger, sinon des tâches « contrat d'abord » et la chaîne P0 sont classées « écran » et refusées :
- ACAL557 et ACAL614 (contrats posés seuls) déclarent `frontend/src/api/calepinageApi.js` : la ligne du client d'API
  va à la tâche d'écran (ACAL559, ACAL617). Tel quel, ACAL558 attend un contrat que la porte refuse.
- ACAL914 (P0, refus serveur de « Générer le devis ») déclare `frontend/src/features/calepinage/BoutonDevis.test.jsx`
  pour seule pièce d'écran : l'assertion va à ACAL915/923. Tel quel, ACAL914 est refusée et entraîne ACAL916, 921, 922,
  861, 983 (sortie du planificateur : section « Refusé — @after… »).

**Fait d'ordonnancement plus lourd que la porte.** Sortie de `plan_lanes.py` sur le plan : « 236 buildable task(s)
across 3 independent lane(s) » — une lane `calepinage/devis` de **231 tâches, model=opus**, plus deux lanes de 4 et 1.
Calcul direct sur les `Files:` de la vague : les 431 tâches du plan calepinage forment une composante connexe de 397
tâches (370 en ignorant tous les tests, goldens et documents partagés ; encore 96 en retirant les 30 fichiers source les
plus partagés). Les 36 étiquettes `@lane` sont décoratives : le bloc est UNE file en série, tirée au modèle de sa tâche
la plus risquée. Ce n'est pas corrigeable par des tags. À écrire dans le dossier : l'ordre du fichier EST l'ordre de
construction (M1/P0 en tête), et l'orchestrateur découpe par `--only` pour ne pas faire construire 214 tâches sonnet
par opus.

---

## 5. Cohérence d'ensemble — doublons et contradictions entre domaines (À CORRIGER)

D7 (constats du tour 1) a été écrit sans relire D1-D6. Paires vérifiées : mêmes fichiers, aucun `@after` entre elles,
aucune ne cite l'autre (script sur les `Files:` et les textes) :

| Paire | Fichiers communs | Proposition |
|---|---|---|
| ACAL687 ↔ ACAL936 (phases lues des Saisies électriques) | `raccordement.py`, `test_acal_raccordement_unique.py` | supprimer ACAL687 |
| ACAL766 ↔ ACAL943 (plus d'export horaire avant simulation) | `PanneauProduction.jsx`, `TapisHoraire.jsx` | supprimer ACAL943 ; ACAL987 pointe ACAL766 |
| ACAL768 + 769 ↔ ACAL944 (délai de téléchargement) | `PanneauDocuments.jsx`, `calepinageApi.js` | supprimer ACAL944 |
| ACAL770 ↔ ACAL941 (« tmy » désactivé) | `ReglagesSimulation.jsx` | supprimer ACAL941 |
| ACAL771 + 774 ↔ ACAL940 (un seul 409 listant tout) | `simulation.py`, `calepinage_simulation.json` (`exemple_refus_multiple` contre `exemple_refus_manquants`) | garder ACAL940 (M1) ; réduire 771/774 aux refus hors réglages |
| ACAL493 ↔ ACAL953 (hauteur d'obstacle) | `BuilderDom.jsx` | supprimer ACAL953 |
| ACAL607 ↔ ACAL917 (kWc du champ, même exemple 176 × 710 = 124,96) | `poseSurfaces.test.ts` | supprimer ACAL917 |
| ACAL606 ↔ ACAL919 (pas anti-ombrage, même terrain 30 × 22 m) | `moteur_service.py`, `pose.json` | fusionner ; garder le `sol` au contrat d'ACAL919 |
| ACAL609 ↔ ACAL920 (allée imposée qui ombre) | `ModeTerrain.jsx` | fusionner |
| ACAL776 + 777 ↔ ACAL924 (facture du lead dans l'atelier, même exemple 900 MAD) | — | supprimer ACAL924 ; ACAL985 pointe ACAL777 |
| ACAL572 ↔ ACAL938 (écran Lestage) ; ACAL939 en retire 2 paramètres alors qu'ACAL572 dit « dix » | `ReglagesSimulation.jsx` | une seule tâche, compte réaligné |
| ACAL644 ↔ ACAL733 (drapeau `optimiseur` par module) | `chaines.py`, `calepinage_entree_electrique.json`, `test_cal234_affectation_manuelle.py` | supprimer ACAL733 ; 723, 724, 725 pointent ACAL644 |
| ACAL647 ↔ ACAL725 (marquage à l'écran d'affectation) | `AffectationChaines.jsx` | fusionner |
| ACAL681 ↔ ACAL752 (colonne `p_dc_kw`) | `onduleur.py`, `test_calx170_onduleur.py` | supprimer ACAL752 ; ACAL738 pointe ACAL681 |
| ACAL682-684 ↔ ACAL736-737 (histogramme par classe de puissance) | `VerdictElectrique.jsx` ; deux contrats, deux composants | garder 736-737 (pas de route neuve) |
| ACAL549 ↔ ACAL881 (cause d'un pan vide) | à relire | probable, non vérifié clause par clause |

Autres incohérences :
- **Libellé du bouton.** « Créer le devis » (ACAL867, 868) contre « Générer le devis » (ACAL914, 915, 922, 923, 955, 968,
  989) : un seul mot, sinon la garde ACAL989 cherchera un bouton renommé.
- **Carte « Économies » de l'atelier.** ACAL778, 852, 924 améliorent l'estimation du navigateur ; ACAL994 la remplace par
  la valeur servie. Écrire l'état final une fois et poser ACAL994 `(@after: ACAL778, ACAL852)`.
- **Plan de pose.** ACAL889 imprime la tension à froid par chaîne sans `@after: ACAL618` (qui la sert) et une consigne
  en dur, alors qu'ACAL673 fait de la consigne DC un texte de la société.
- **Deux seuils d'accès solaire.** `optimisation.seuilAccesSolaire` au document (ACAL548) et réglage société
  `seuil_acces_retrait` (ACAL714) : dire lequel prime.
- **« Couvre le besoin ».** Calculé au navigateur (ACAL547) ET au serveur (ACAL835) : une grandeur, deux calculs.
- **Mesuré contre simulé.** Production (ACAL886-888 : table, étape Résultats) et consommation (ACAL846-847 : sans
  persistance, onglet « Pose réelle ») : deux patrons, deux emplacements.
- **20 tâches attendent une tâche `[BLOCKED : code livré… preuve due à ACAL490]`** (ACAL423, 427, 428, 430, 432, 434,
  436, 441, 442, 470, 478) : le planificateur les refuse (`apply_external_after_gate` l.1531-1544) tant que
  l'acceptation ACAL490 n'est pas jouée. À dire dans le dossier.
- Aucun cycle d'`@after` (script). Aucune dépendance vers un identifiant inexistant.

---

## 6. Ce qui manque (MANQUES)

- **M1 — T1-T1-013** (poignées de sommets au sol sous un toit extrudé, `roofPro11/scene3d.ts`, P2) : seul des 98
  constats retenus sans tâche (vérifié par script : 86 cités par une tâche de la vague, 11 portés par une tâche du tour
  0, 1 orphelin). Une tâche d'une ligne, lane atelier-web.
- **M2 — CAP-D3-17** (micro-onduleurs ≠ injection zéro, place et sens de la pince de mesure) : rang 10, score 6, en
  réserve avec la mention « raison non écrite » ; mieux classée que des fiches construites (CAP-D3-03, score 3).
  L'écrire ou donner la raison. Seule fiche du premier tiers sans tâche (D1-D6, par citation d'identifiant).
- **M3 — Contrôle « prêt à envoyer ? »** : « ce devis annoncera la production standard de la ville : la simulation du
  calepinage est absente, périmée ou incomplète », avec le geste. Sans lui, D-ACAL-36 retombe en silence.
- **M4 — Produit « kit de fixation »** : une tâche (plan stock) qui sème le produit SANS prix, grisé « prix à
  renseigner » (patron des pompes OSP), et un contrôle bloquant tant qu'il n'est pas tarifé. Sinon D-ACAL-39 livre des
  devis sans fixation.
- **M5 — Pendants d'ACAL869** pour les étapes Toit, Électrique, Résultats et Documents (§ 7).
- **M6 — Moitié web d'ACAL912** : la tâche nomme « autre geste : `docs/WEB_PLAN.md` (vérifier qu'une clé absente lit la
  production du moteur) » ; aucune tâche WEB_PLAN ne le porte.
- **M7 — Comparaison des deux remplissages** (CAP-D8-10 t2, en réserve « non repris ») : sans ce dry-run en lecture
  seule, la question « le compte de panneaux vient-il du serveur ? » ne pourra jamais être posée à Reda avec une
  preuve, et les deux moteurs de pose vivront indéfiniment. Une tâche, sans activation.

Réserve (53 lignes) relue : pas d'autre capacité écartée qui devrait être une tâche. Les coupes D8 suivent la première
critique. La ligne « CAP-D8-02 t3 : aucune garde sur l'économie » est inexacte : ACAL1010 compare bien l'économie
année 1.

---

## 7. Le risque inverse — « extremely simple »

Mesures (script sur les 216 tâches du plan calepinage qui déclarent un fichier d'écran ; lecture par motifs, donc
approximative) :
- 95 disent leur étape ET leur niveau ; 40 l'un des deux ; **81 ni l'un ni l'autre**, dont 25 dont le titre est un ajout.
- Environ 60 tâches se rangent au niveau ESSENTIEL ; l'étape Toit en reçoit 22.
- 15 tâches retirent, replient ou remplacent ; **une seule réduit une étape** (ACAL869, Panneaux, « au plus 5
  contrôles »).
- 11 tâches touchent `atelier/onglets.js` ; 6 ajoutent un écran ou une section de Réglages (dont deux fois « Lestage »).
- 2 tâches seulement citent le budget de simplicité (ACAL869, ACAL989).

Or ACAL478 (code livré) verrouille ce budget : la spec `frontend/e2e/calepinage-mesures-ecran.spec.js` échoue si les
contrôles visibles du premier écran dépassent `mode_guide.controles_premier_ecran` de
`calepinage-mesures-ecran.baseline.json`. Le tour 1 a mesuré 104 contrôles (31 au premier écran), 143 après le tracé.
Chaque ajout au niveau essentiel fera donc soit rougir cette garde, soit relever sa base — et le budget ne voudra plus
rien dire.

Tâches qui alourdissent le parcours guidé sans le dire (à ranger « expert, replié » ou à justifier) :
- **Étape Toit, essentiel** : ACAL1032 (« Dupliquer », « Poser en série »), 506-508 (coordonnées collées, source de
  l'image), 519 (pente au téléphone), 527 (écarts avec la visite), 529 et 897 (photo), 531 (obstacles détectés),
  780 (charges à venir), 837 et 840 (grille de 12 factures, photo de facture).
- **Sans étape ni niveau** : ACAL494, 495 (gabarits en Réglages), 562, 717, 719, 748, 754, 755, 764, 774, 795, 799, 815,
  854, 855, 880, 884, 964, 971, 979, 995.
- **Étape Électrique, essentiel** : ACAL617, 628, 634, 712, 784, 974.
- **Onglets** : ACAL531, 628, 641, 712, 719, 725, 762, 847, 848, 888, 1028 touchent `onglets.js` — dire pour chacune si
  elle AJOUTE une entrée et sous quelle étape.

Correction proposée, mécanique : (1) une clause obligatoire par tâche d'écran — « Simplicité : étape X, niveau
essentiel | expert ; effet sur le premier écran : +0 (replié) | +N » ; (2) règle écrite au groupe : seul un constat
P0/P1 peut ajouter un contrôle au niveau essentiel, et la tâche relève la base dans le même commit en le disant ;
(3) les quatre pendants d'ACAL869 (M5).

---

## 8. OPTIONNELS

1. Les exemples chiffrés du lot D8 se contredisent (ACAL991 : 71 kWc, 111 420 kWh « standard ville », économie 7 420
   MAD ; ACAL994/995 : 98 574 « servi » contre une simulation à 93 504, alors qu'au niveau 15 l'écart vaut 0 par
   construction). Sans effet sur le produit (échantillons), gênant pour le constructeur.
2. ACAL995 : après le niveau 15 la ligne « Le devis annonce… » n'apprend plus rien quand le calepinage est frais ; la
   réserver aux cas « standard ville » ou « périmé ».
3. ACAL1009 : relever aussi les imports de modules hors `selectors`/`services` (ex. `coherence.registre`).
4. ACAL697 : écrire « aucun kWh de production, seulement les parts de pertes » pour qu'un client n'ait jamais deux
   productions en main.
5. ACAL1026 : la page d'un devis déjà envoyé gagne un réglage (sans chiffre) — conforme à D-ACAL-38, à dire à Reda.
6. Déclarer append-only au registre les fichiers-colle de test (`test_cal223_contrats.py` : 34 tâches sur 12 étiquettes
   de lane ; `E2E_HOOKS.md`, `e2eHooks.test.mjs`, `calepinageApi.golden.json`) : ne défait pas la file unique (§ 4) mais
   évite des conflits de fusion si le bloc est un jour découpé.
7. `chiffrage_conception.json` : nommer l'option (sans / avec batterie) dont l'économie est servie.

---

## 9. Ce que je n'ai PAS couvert

- Aucune tâche de D1 à D7 vérifiée prémisse par prémisse (travail des 17 vérificateurs). J'ai lu en entier : le lot D8
  (23), ACAL927, 976, 912, 911, 921 ; par clauses : une quarantaine d'autres (paires de doublons, tâches citant une
  décision, tâches déclarant `selectors.py`).
- Le dossier `bench/` n'a pas été ouvert ; les fiches `backlog/D1…D6` n'ont pas été lues en entier (seul l'en-tête de
  D3) : la couverture du premier tiers est jugée par citation d'identifiant `CAP-…`, pas par relecture de la « plus
  petite version crédible » de chaque fiche. Le rang n'a été extrait que pour D3.
- La recherche de doublons : lecture de l'index en entier + un balayage par similarité de titres et de fichiers ; des
  doublons à titres très différents ont pu m'échapper.
- Maquettes `*.dc.html` et fiches `T1/classes/K-*.md` non ouvertes ; la demande « most pretty » n'est jugée que par la
  présence des tâches de style, pas par leur qualité.
- D-ACAL-40 au format « une page » et dans `public/payload_economie.py` l.455-470 : non tracé jusqu'au bout.
- ACAL911/921 : les lecteurs vivants d'un devis envoyé ne sont nommés que pour deux fichiers ; non suivis jusqu'au rendu.
- Les règles propres des autres plans (contrats de propriété et INTERDIT de `PLAN_AUDIT_DEVIS`, `_MOTEUR`, `_STOCK`,
  `_CHANTIERS`, `WEB_PLAN`…) n'ont pas été relues ; `check_ownership.py`, `check_ancres_taches.py`,
  `check_taches_cablage.py` n'ont pas été lancés sur les fichiers d'insertion.
- Aucun test exécuté : tout « rouge » annoncé ici est déduit de la lecture du code et de la CI, non observé.
- Le comptage « 161 + 33 refusées » vient du planificateur lancé sur le plan de `l5-verif` (tâches plus anciennes
  comprises) ; ma simulation sur les seules 472 tâches donne 160.
