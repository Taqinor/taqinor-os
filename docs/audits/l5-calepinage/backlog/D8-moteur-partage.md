# D8 — Moteur de conception partagé (« le module caché ») — lane architecte, 21/11/2026

Dépôt lu en LECTURE SEULE : `C:\dev\taqinor-os\.claude\worktrees\calpinage-module-enhance-04bba5` (HEAD `33c076d00`).
Aucun fichier du dépôt modifié, aucun test, aucun docker. Décision et carte des doublons :
`architecture/DECISION-moteur-partage.md`. Chaque propriétaire ci-dessous vient de
`python scripts/check_ownership.py --owner-of <fichier>` lancé dans cette session ; `AUCUN` = surface append-only sans
propriétaire (orchestrateur). Chemins courts comme D6/D7 : `SV` = `backend/django_core/apps/calepinage/services`,
`VD` = `backend/django_core/apps/ventes/domain`, `QE` = `backend/django_core/apps/ventes/quote_engine`, `RP` =
`apps/web/src/scripts/roofPro11`, `WL` = `apps/web/src/lib`, `FC` = `frontend/src/features/calepinage`, `FV` =
`frontend/src/features/ventes`, `FCRM` = `frontend/src/features/crm`, `CC` = `backend/django_core/core/conception` (neuf).

Format : celui de D6 (besoin, preuves, qui le fait, chez nous = verdict, plus petite version, simplicité, tâches d'UN
comportement chacune avec fichiers et propriétaire, dépendances). Pas de score : les fiches sont rangées dans l'ORDRE DE
MIGRATION (contrat seul d'abord, puis gardes, puis chaque grandeur, puis le chemin rapide, puis le retrait des jumeaux).
`@model: opus` sur toute tâche qui touche `core/**`, le moteur de devis (`QE`, `etude_horaire.py`, `economie.py`) ou
l'architecture inter-apps. Règle de périmètre L5 (contrat § 5) : les tâches **moteur** et **devis** sont routées au plan de
leur propriétaire et ne changent que les NOUVEAUX rendus.

Interrupteur commun aux marches M3 : réglage `MOTEUR_CONCEPTION_<GRANDEUR>` (défaut OFF ; ABSENT = OFF, même patron que
`VD/geometrie.py::moteur_calepinage_actif`) dans `backend/django_core/erp_agentique/settings/base.py` (deploy, append-only),
levé seulement quand la garde de la grandeur (CAP-D8-02) est verte sur les goldens ET que 7 nuits d'`audit_coherence`
n'ont rien levé sur elle.

---

## M0 — Contrat d'abord

### CAP-D8-01 — Le contrat du moteur de conception, SEUL sur `main`
- **Besoin** : « un module caché utilisé par les deux » (Reda, 21/11) ; deux lanes file-disjointes inventent deux
  contrats si aucun fichier partagé n'existe (PACT10, incident du 03/08).
- **Preuves** : marché — un modèle + un moteur, deux surfaces (Reonic quick planning dans la même fiche système, Aurora
  Sales/Design Mode « un modèle », Scanifly « stripped down view of our design software ») ; dépôt — `.importlinter`
  commentaires AOF33/PV33/AGR109 (moteur partagé = fondation pure) ; rejeu T1 : 14 divergences sur 14.
- **Qui le fait** : Aurora, OpenSolar (Auto Design dans le studio), Scanifly.
- **Chez nous** : **ABSENT.** Trois noyaux purs existent (`core/calepinage`, `core/electrique`, `core/pompage`), aucun ne
  peut importer l'autre (contrats `electrique-est-un-noyau-pur`, `pompage-est-un-noyau-pur`) ; aucun objet « conception »
  commun ; `core/conception/**` retombe sur le résiduel `securite` (vérifié).
- **Plus petite version** : un échantillon de contrat + un paquet vide verrouillé, aucun chiffre ne bouge.
- **Simplicité** : invisible pour l'utilisateur.
- **Tâches** :
  1. Poser `apps/calepinage/contract_samples/conception.json` : entrée canonique (site, pans posés, surfaces au sol, module
     et onduleur, conso 12 mois ou horaire + provenance, barème, ombrage servi) et sortie (`kwc`, `production_commerciale`,
     `etude_technique` avec `ecart`, `economie`, `verdict_electrique` à trois états, `taille_cible`, `controles[]`), chaque
     grandeur `{valeur, unite, source, etat}` ; fini quand un test de contrat du module lit l'exemple et refuse une clé
     absente. Fichiers : le JSON (**calepinage**) + test dans le module de test de contrat existant du calepinage
     (**calepinage**). `@model: opus`
  2. Ajouter à `docs/ownership.yml` : `core/conception/production.py`, `core/conception/economie.py` → **moteur** ; le reste
     de `core/conception/**` → **calepinage** ; fini quand `check_ownership.py --owner-of backend/django_core/core/conception/__init__.py`
     ne rend plus `securite`. Fichier : `docs/ownership.yml` (**AUCUN**, append-only — orchestrateur).
  3. Contrat import-linter `conception-est-un-noyau-pur` (source `core.conception` ; interdits : `apps`, `authentication`,
     `core.models`, `core.views`, `core.services`, `core.selectors`, `core.tasks`, `core.events`… comme les trois autres) et
     `core.conception` ajouté aux interdits de `calepinage-`, `electrique-`, `pompage-est-un-noyau-pur` ; fini quand
     `lint-imports` passe et qu'un import `core.calepinage → core.conception` le fait échouer. Fichier :
     `backend/django_core/.importlinter` (**deploy**). `@model: opus`
  4. Paquet `core/conception/__init__.py` (version du moteur, aucun calcul) + `core/tests/test_conception_purete.py`
     (analyse AST, patron `test_calepinage_purete.py`) ; fini quand le test refuse un `import django` ajouté. Fichiers :
     `core/conception/**` (**calepinage** après t2), test (**calepinage** après t2 ; aujourd'hui `securite`). `@after` t2.
     `@model: opus`
  5. Section « Le moteur de conception » dans `docs/moteur-calepinage.md` (qui calcule quoi, l'adaptateur, les
     interrupteurs) ; fini quand chaque grandeur du contrat y nomme son seul calcul. Fichier : **AUCUN**.
- **Dépend** : rien. Bloque toutes les fiches suivantes.

---

## M1 — Gardes « une grandeur, une valeur » (rouges d'abord)

### CAP-D8-02 — Un test qui échoue dès que deux écrans donnent deux chiffres pour la même grandeur
- **Besoin** : « production 93 504 sur la carte, 98 574 au document, 111 420 au PDF » ; « 0 MAD ici, 208 381 là ».
- **Preuves** : rejeu T1 (S1-005, S1-018, S1-017, S1-020 confirmés) ; `T1/classes/K-GRANDEUR-UNIQUE.md` (matrice
  grandeur × condition, 9 cases « casse ») ; marché : « A new date on the proposal does not prove the annual energy was
  recalculated » (https://www.surgepv.com/blog/6-ways-the-proposal-can-drift-from-what-the-customer-saw-on-site).
- **Qui le fait** : personne ne le publie ; c'est notre garde de classe.
- **Chez nous** : **PARTIEL.** Goldens ACAL382 (chiffres de la simulation, [x]) et ACAL383 (document émis, [x]) ;
  ACAL480 (parité productible navigateur ↔ serveur, [ ]) ; `apps/calepinage/tests/test_acal_verdict_unique.py` (ne couvre
  pas `NON_VERIFIABLE`) ; `apps/ventes/tests/test_solar_differential.py` (classification + kWc des lignes) ; aucune
  comparaison carte ↔ Total ↔ document ↔ `etude_params` ↔ PDF.
- **Plus petite version** : un module de test unique, une assertion par case de la matrice, tolérance publiée en tête.
- **Simplicité** : invisible.
- **Tâches** (chacune écrite ROUGE sur `da49cb55b` avant toute correction, puis laissée en place) :
  1. Production : sur les goldens ACAL382 (toit incliné, toit plat E-O, champ au sol), carte = Total = document =
     `etude_params.production_annuelle` = chiffre PDF, ou écart nommé `etude_technique.ecart` ; fini quand le cas E-O est
     rouge avec les trois valeurs dans le message. Fichier : `apps/calepinage/tests/test_moteur_partage_parite.py`
     (**calepinage** ; « Nouveau fichier car : » aucune garde transverse existante ne lit les cinq surfaces) + le côté PDF
     dans `apps/ventes/tests/test_quote_engine.py` (**moteur**). `@model: opus`
  2. kWc et Wc unitaire : module du document = module des lignes = « N × W » des cartes ; fini quand le cas « sans choix de
     module » (golden ACAL383) est rouge (720 ≠ 710). Même fichier (**calepinage**).
  3. Économie année 1 : carte de l'atelier = `ventes/economie.py::economie_pour_devis` (ou « pas de facture » nommé,
     jamais 0 MAD muet) ; fini quand le cas « facture 900 MAD » est rouge. Même fichier (**calepinage**).
  4. Verdict : `SV/electrique.py::_rapport_publication` = verdict servi à `FC/BoutonDevis.jsx` = `SV/assistant.py::_bloc_electrique`
     sur un calepinage SANS matériel (`NON_VERIFIABLE`) ; fini quand le cas est rouge. Fichier :
     `apps/calepinage/tests/test_acal_verdict_unique.py` (**calepinage**, module existant étendu).
  5. Garde du site public : production et économie de `WL/estimatorBrainV2.ts` sur les trois goldens ≤ écart PUBLIÉ au
     moteur ; fini quand un écart qui grandit échoue en nommant le projet. Fichier : `apps/web/tests/estimatorParite.test.ts`
     (**web**). `@after` CAP-D8-07 t2 (le chiffre serveur de référence).
- **Dépend** : ACAL382, ACAL383 ([x]) ; recouvre ACAL480 (t1 ici l'inclut — ne pas la construire deux fois) ; deviennent
  vertes avec CAP-D7-01 (production), CAP-D7-02 (module), CAP-D7-06 t1 (facture), CAP-D7-10 (verdict).

### CAP-D8-03 — Le correcteur de nuit regarde aussi production, économie et verdict
- **Besoin** : « le système l'attraperait-il tout seul ? » — non aujourd'hui (question de sortie de K-GRANDEUR-UNIQUE).
- **Preuves** : `backend/django_core/apps/ventes/coherence/regles_calepinage.py` porte `CAL_MODULES_DEVIS_VS_CALEPINAGE`,
  `CAL_KWC_DEVIS_VS_CALEPINAGE`, `CAL_EMPREINTE_IMPRIMEE_PERIMEE` et rien sur la production, l'économie ni le verdict.
- **Chez nous** : **PARTIEL** (2 grandeurs sur 5).
- **Plus petite version** : trois règles de plus, même registre, même seuil publié que CAP-D8-02.
- **Tâches** :
  1. Règle `CAL_PRODUCTION_DEVIS_VS_CALEPINAGE` (production `etude_params` vs document lié, écart > tolérance publiée et non
     nommé) ; fini quand un devis du cas E-O la lève. Fichier : `ventes/coherence/regles_calepinage.py` (**moteur**).
  2. Règle `CAL_ECONOMIE_ATELIER_VS_DEVIS` ; fini quand le cas « facture 900 MAD » la lève. Même fichier (**moteur**).
  3. Règle `CAL_VERDICT_PUBLIABLE_SANS_MATERIEL` ; fini quand le cas « Publiable à vide » la lève. Même fichier (**moteur**).
- **Dépend** : CAP-D8-02 (mêmes tolérances).

---

## M2 — Une seule porte d'entrée (byte-identique)

### CAP-D8-04 — La façade `concevoir()` : tous les appelants passent par elle, aucun chiffre ne bouge
- **Besoin** : « chaque grandeur une fois » n'est atteignable que si tous les écrans demandent à la même porte.
- **Preuves** : deux `design-context` (`apps/calepinage/views/calepinages.py::design_context` l.1051 et
  `apps/ventes/views/devis_calepinage.py::design_context` l.343) ; trois adaptateurs électriques (D8-09) ; le devis
  automatique lit son propre arbitrage (`VD/creation_calepinage.py::_arbitrage_du_calepinage`).
- **Qui le fait** : modèle unique Aurora/Scanifly (pages éditeur).
- **Chez nous** : **ABSENT.**
- **Plus petite version** : `SV/conception.py` qui APPELLE les fonctions d'aujourd'hui et rend l'objet du contrat ;
  goldens ACAL382/383, `test_quote_engine.py`, `test_solar_differential.py` inchangés au bit près.
- **Tâches** :
  1. `SV/conception.py::concevoir(calepinage)` et `chiffrer(document)` délèguent à `SV/simulation.py`, `SV/electrique.py`,
     `ventes.services` (production/économie du devis) et rendent `conception.json` ; fini quand le test de la façade rend
     l'exemple du contrat sur le golden résidentiel, identique aux valeurs servies aujourd'hui. Fichiers : `SV/conception.py`,
     `apps/calepinage/tests/test_conception_facade.py` (**calepinage**). `@model: opus`
  2. Le `design-context` du calepinage lit la façade ; fini quand son contrat `calepinage_design_context.json` ne change pas.
     Fichier : `apps/calepinage/views/calepinages.py` (**calepinage**).
  3. Le `design-context` du devis délègue à celui du calepinage lié (D-ACAL-1) au lieu de recomposer ; fini quand les deux
     réponses d'un même devis sont égales. Fichier : `apps/ventes/views/devis_calepinage.py` (**devis** — à confirmer par
     `--owner-of` au moment de la tâche, non lancé ici).
  4. `VD/pipeline.py::ecrire_etude_params` reçoit la `Conception` au lieu de `layout.result` ; fini quand les goldens
     devis ne bougent pas. Fichier : `VD/pipeline.py`, `VD/etude_schema.py` (**devis**). `@model: opus`
  5. `SV/contenance.py` (assistant) passe par la façade ; fini quand `calepinage_assistant_contenance.json` ne change pas.
     Fichier : `SV/contenance.py` (**calepinage**).
  6. Cliquet des imports croisés : un test compte les fichiers non-test de `apps/ventes` qui importent `apps.calepinage` (18
     au 21/11) et l'inverse (36) et refuse toute hausse ; fini quand un import ajouté le fait échouer. Fichier :
     `scripts/tests/` (propriétaire à résoudre par `--owner-of` — non lancé ici).
- **Dépend** : CAP-D8-01.

---

## M3 — Chaque grandeur derrière le moteur (ordre : chiffres faux que voit le client d'abord)

### CAP-D8-05 — La géométrie POSÉE lue une seule fois (est-ouest, toit + sol, sens des rangées)
- **Besoin** : « un E-O 15° décrit 22° Sud au devis » ; « toit + champ additionnés sans question ».
- **Preuves** : rejeu S1-005, F1-030, REJEU-NEW-1/2 ; `VD/geometrie.py::orientation_du_pan`, `pans_du_document` (lus).
- **Chez nous** : **PRÉSENT, FAUX** (deux lecteurs du document : `VD/geometrie.py` et `RP/panStats.ts`).
- **Plus petite version** : `CC/geometrie.py::pans_poses(document)` pur ; `VD/geometrie.py` en devient un appelant mince.
- **Tâches** :
  1. Déplacer `orientation_du_pan` + `pans_du_document` dans `CC/geometrie.py::pans_poses` SANS changer un résultat
     (déplacement pur, `VD/geometrie.py` ré-exporte) ; fini quand les goldens et `test_acal_parite_compte_modules.py` ne
     bougent pas. Fichiers : `CC/geometrie.py`, `VD/geometrie.py` (**calepinage**). `@model: opus`
  2. Les corrections de CAP-D7-01 t2 (jambes E-O posées), CAP-D7-03 t2 (composition par surface) et CAP-D7-04 t3 (une
     convention d'azimut) se construisent DANS `CC/geometrie.py` — pas une seconde fois dans `VD/` ; fini quand CAP-D8-02 t1
     est vert sur le cas E-O. Fichier : `CC/geometrie.py` (**calepinage**). `@model: opus`. Change un chiffre client →
     niveau de règles (`VD/regles_calcul.py`, **devis**) + dry-run `regles_calcul_ecarts_dryrun`.
- **Dépend** : CAP-D8-04 ; recouvre CAP-D7-01 t2, CAP-D7-03 t2, CAP-D7-04 t3 (ces tâches ne sont faites qu'ici).

### CAP-D8-06 — Le matériel et le kWc d'une seule source
- **Besoin** : « 72 kWc à l'écran, 71 au PDF, module jamais choisi ».
- **Preuves** : S1-018 (rejeu), B1-004 ; `WL/roofPro2.ts::PANEL2_WATT` (720), `FV/solar.js::PANEL_W_DEFAUT` (710), `SV/chaines.py::bloc_pose`.
- **Chez nous** : **PRÉSENT, FAUX** (quatre défauts de module).
- **Plus petite version** : le module de départ est une ENTRÉE du moteur résolue une fois du catalogue ; `CC::kwc` pur.
- **Tâches** :
  1. `CC/__init__` ou `CC/materiel.py::kwc(pans, modules)` ; `SV/chaines.py::bloc_pose` et la carte lisent ce kWc ; fini
     quand CAP-D8-02 t2 est vert. Fichiers : `CC/materiel.py`, `SV/chaines.py` (**calepinage**). `@model: opus`
  2. CAP-D7-02 t1/t2 (module de départ servi par `design-context`, refus nommé dans `generer_devis`) se construit en lisant
     l'entrée du moteur ; fini comme D7-02. Fichiers : `RP/context.ts`, `FC/atelier/useAtelierBoot.js`, `SV/devis.py`
     (**calepinage**).
- **Dépend** : CAP-D8-04 ; recouvre CAP-D7-02 t1-t2. Pas de chiffre client changé (le PDF imprime déjà 710 W).

### CAP-D8-07 — UNE production client, servie aussi à l'atelier
- **Besoin** : « trois productions pour un dessin » ; « quel chiffre croire ».
- **Preuves** : S1-005 ; l'atelier ERP n'a aucun rendement serveur (`FC/atelier/useAtelierBoot.js` : `rendementPvgis: null`,
  `productionAtelierErp = () => fallbackPerKwc()`) ; `VD/etude_schema.py` l.496 recopie `layout.result.annualKwh` du
  navigateur ; `QE/pricing.py::calculate_savings_roi` recalcule ; D-ACAL-6 : le chiffre client est celui du moteur de devis.
- **Qui le fait** : Aurora (production « instantly updated with every design change », page éditeur).
- **Chez nous** : **PRÉSENT, 6 CALCULS.**
- **Plus petite version** : la fonction de production du devis (modèle horaire) devient `CC/production.py`, nourrie par
  `pans_poses` ; l'atelier affiche SON chiffre.
- **Tâches** :
  1. Constat d'extraction : lister ce que `etude_horaire.py::calculer_etude_horaire` / `jours_types_annee` et la partie
     production de `QE/pricing.py` lisent hors de leurs arguments (Django, réglages, réseau) ; fini quand la liste est dans
     le message de commit et que chaque lecture a son entrée dans `conception.json` (sinon : ajout au contrat, PACT10).
     Fichiers : lecture seule ; contrat (**calepinage**). `@model: opus`
  2. Déplacement PUR de la production horaire dans `CC/production.py::production_commerciale` (`etude_horaire.py`
     ré-exporte) ; fini quand `test_quote_engine.py`, `test_solar_differential.py` et ACAL382 ne bougent pas au bit près.
     Fichiers : `CC/production.py` (**moteur** après CAP-D8-01 t2), `backend/django_core/apps/ventes/etude_horaire.py`
     (**moteur**). `@model: opus`
  3. Route `POST calepinages/<pk>/conception/chiffrer/` (façade `chiffrer`) ; fini quand son contrat rend
     `production_commerciale` du golden en ≤ 500 ms au 95e centile sur la pile locale (mesuré et collé dans le commit).
     Fichiers : `apps/calepinage/views/conception.py`, `views/rattachements.py` (append-only), `frontend/src/api/calepinageApi.js`
     (append-only) (**calepinage**).
  4. L'atelier ERP affiche le chiffre servi (anti-rebond après geste ; « calcul… » pendant l'attente ; « à recalculer »
     hors ligne) et n'utilise plus `fallbackPerKwc` ; fini quand CAP-D8-02 t1 lit carte = Total = document. Fichiers :
     `FC/atelier/useAtelierBoot.js`, `RP/prodWindow.ts`, `RP/zones.ts`, `RP/optimizer.ts` (**calepinage**). Derrière
     `MOTEUR_CONCEPTION_PRODUCTION`.
  5. `ecrire_etude_params` écrit la `production_commerciale` du moteur (plus jamais `layout.result.annualKwh`) et somme
     toutes les surfaces chiffrées (= CAP-D7-01 t3) ; fini quand le devis toit + sol a une production cohérente avec ses kWc.
     Fichiers : `VD/etude_schema.py`, `VD/pipeline.py` (**devis**). `@model: opus`. **Change un chiffre client** → niveau de
     règles + dry-run ; lecteurs à prévenir : `WL/proposition.ts`, `components/proposition/ci/SectionAutoconso.astro`,
     `contract_samples/proposal_data.json` (**web**).
- **Dépend** : CAP-D8-05 (pans posés) ; recouvre CAP-D7-01 t1 et t3 (t1 D7 devient inutile une fois t4 ici faite :
  la carte et le Total lisent le même chiffre servi — à trancher à la construction, ne pas faire les deux).

### CAP-D8-08 — Autoconsommation et économie calculées une fois (la facture du lead arrive à l'atelier)
- **Besoin** : « 0 MAD sur une carte, 208 381 sur l'autre » ; « la facture du lead n'arrive pas à l'atelier ».
- **Preuves** : S1-017, S1-023 (rejeu) ; `WL/estimatorBrainV2.ts::annualSavingsMad` (10 appelants), `FV/calc/roi.js::computeROI`,
  `QE/pricing.py::calculate_savings_roi`, `FC/atelier/contexteAtelier.js::contexteCalepinageVersPayload` (nombre de panneaux seul).
- **Chez nous** : **PRÉSENT, 4 CALCULS.**
- **Plus petite version** : `CC/economie.py` (barème, flux, retour) déplacé de `pricing.py` ; la carte de l'atelier lit
  `chiffrer` ; sans facture, la carte dit « aucune facture — économie non calculée ».
- **Tâches** :
  1. Déplacement PUR de l'économie (autoconsommation horaire, barème, retour) dans `CC/economie.py` ; fini quand
     `test_quote_engine.py` ne bouge pas. Fichiers : `CC/economie.py` (**moteur**), `QE/pricing.py` (**moteur**). `@model: opus`
  2. La conso annuelle du lead (kWh + source) entre dans l'entrée du moteur depuis `crm.selectors` (= CAP-D7-06 t1) ; fini
     quand `chiffrer` sur un lead à facture 900 MAD rend une économie non nulle. Fichiers : `SV/conception.py`,
     `FC/atelier/contexteAtelier.js` (**calepinage**).
  3. La carte « Économie » de l'atelier lit `chiffrer` au lieu d'`annualSavingsMad` en mode ERP ; fini quand CAP-D8-02 t3
     est vert. Fichiers : `RP/optimizer.ts`, `RP/consumptionMarkup.ts` (**calepinage**). Derrière `MOTEUR_CONCEPTION_ECONOMIE`.
- **Dépend** : CAP-D8-07 t2 ; recouvre CAP-D7-06 t1. Pas de chiffre client changé (le PDF n'imprime pas l'économie de
  l'atelier ; il imprime déjà celle de `pricing.py`).

### CAP-D8-09 — Un seul adaptateur électrique, un verdict à trois états
- **Besoin** : « trois verdicts électriques » ; « Publiable » sans panneau ni onduleur.
- **Preuves** : F1-010/S1-020 (rejeu) ; adaptateurs `backend/django_core/apps/ventes/electrical_service.py`, `SV/electrique.py`,
  `SV/assistant.py::_bloc_electrique` ; second calcul de chaînes `backend/django_core/apps/ventes/solar_design.py::string_design`.
- **Chez nous** : **PRÉSENT, 3 ADAPTATEURS + 1 JUMEAU.**
- **Plus petite version** : `SV/conception.py` appelle `core.electrique.concevoir` une fois ; les trois lecteurs lisent son verdict.
- **Tâches** :
  1. `SV/conception.py::electrique` = seul appel de `core.electrique.concevoir`, verdict `publiable | bloquant |
     non_verifiable` (= CAP-D7-10) ; fini quand CAP-D8-02 t4 est vert. Fichier : `SV/conception.py`, `SV/electrique.py`
     (**calepinage**). `@model: opus`
  2. `ventes/electrical_service.py` délègue à la façade (devis → calepinage lié) ; fini quand `conception_electrique.json`
     ne change pas sur les goldens devis. Fichier : `ventes/electrical_service.py` (**calepinage**).
  3. `SV/chaines.py`, `ventes/compatibilites.py`, `VD/catalogue.py` cessent d'appeler `solar_design.string_design` au profit
     de `core.electrique` ; fini quand `string_design` n'a plus d'appelant hors tests. Fichiers : `SV/chaines.py`
     (**calepinage**), `ventes/compatibilites.py`, `VD/catalogue.py` (propriétaires à résoudre — non lancés ici). `@model: opus`
- **Dépend** : CAP-D8-04 ; recouvre CAP-D7-10 (une seule construction).

### CAP-D8-10 — Un seul remplisseur de toit (le serveur), pour l'atelier, le rapide et les options
- **Besoin** : « combien de panneaux tiennent » a quatre réponses (dessin navigateur, `core.calepinage`, `plafond_physique_du_contour`,
  `calepinage_options._Trame`).
- **Preuves** : `SV/contenance.py` (« le calepinage dessiné fait foi », moteur serveur non autoritaire) ; drapeau
  `USE_MOTEUR_CALEPINAGE` OFF (`erp_agentique/settings/base.py` l.1714), dry-run `comparer_compte_moteur_calepinage` ;
  D-ACAL-17..20 « brancher plutôt que retirer » (le drapeau est cité).
- **Qui le fait** : AutoDesigner (Aurora), Ada Auto Design (OpenSolar), SimpleDesign (Scanifly) — un remplissage serveur.
- **Chez nous** : **PRÉSENT SANS PORTE** (moteur pur prêt, éteint).
- **Plus petite version** : `CC/pose.py::remplir` = `core.calepinage` + `SV/traduction.py::politique_de_pose` ; le bouton
  « Remplir le toit » de l'atelier l'appelle ; le dessin reste éditable à la main ensuite.
- **Tâches** :
  1. `CC/pose.py::remplir(pans, module, politique, cible)` ; fini quand le golden FRDISI (`core/calepinage/golden/`) et le
     compte de `SV/contenance.py` sont rendus à l'identique. Fichier : `CC/pose.py` (**calepinage**). `@model: opus`
  2. Dry-run `comparer_compte_moteur_calepinage` étendu à tous les calepinages ouverts d'une société, écarts PVG2 listés ;
     fini quand le rapport liste par lead l'écart moteur ↔ dessin. Fichier :
     `backend/django_core/apps/ventes/management/commands/comparer_compte_moteur_calepinage.py` (**devis**).
  3. « Remplir le toit » de l'atelier appelle `remplir` (le remplissage navigateur reste derrière `MOTEUR_CONCEPTION_POSE`
     OFF) ; fini quand un toit tracé se remplit du compte serveur. Fichiers : `RP/optimizer.ts`, `SV/conception.py`,
     `views/conception.py` (**calepinage**).
  4. `calepinage_options.layout_derive` (dessins Éco/Recommandé/Max) demande `remplir(cible=N)` au lieu de prolonger la
     `_Trame` ; fini quand les trois dessins d'un golden ont le compte de leur option. Fichier :
     `backend/django_core/apps/ventes/calepinage_options.py` (**calepinage**). Visible à la page client (dessin) → niveau de règles.
- **Dépend** : CAP-D8-05 ; ACAL421 (« Conception automatique ») se construit sur t1 (pas un second remplisseur).

---

## M4 — Le chemin rapide depuis le CRM

### CAP-D8-11 — « Devis rapide » depuis la fiche lead, sans ouvrir l'atelier, qui crée LA conception du lead
- **Besoin** : « we still should be able to make quotes in the crm module without having to open calepinage » (Reda, 21/11).
- **Preuves** : marché — Reonic quick planning (même fiche système, sans 3D), Scanifly SimpleDesign (adresse + module →
  calepinage IA), OpenSolar Ada ; B3-N15 / B6-R35 « passerelle devis rapide → atelier » (R35 corrigé : le Quick Quote
  d'OpenSolar est hors solaire) ; dépôt — `FCRM/workspace/LeadWorkspace.jsx::ouvrirConceptionToiture` crée un devis auto
  puis ENVOIE vers `/ventes/devis/<id>/design` (l'atelier) ; `FCRM/workspace/IdentityRail.jsx::ouvrirModuleCalepinage`.
- **Qui le fait** : Reonic, Scanifly, OpenSolar, Pylon (« under 2 minutes », page éditeur).
- **Chez nous** : **PARTIEL.** « Devis automatique » existe (`VD/creation_auto.py::creer_devis_automatique_depuis_lead`,
  `build_devis_auto`), dimensionne par la facture (`VD/taille.py`) et pose une zone brute
  (`VD/geometrie.py::zone_toit_depuis_contour`) dans le devis ; il ne crée pas de calepinage, ne remplit pas le toit et
  son chiffre change quand l'atelier pose enfin les panneaux.
- **Plus petite version** : le bouton existant « Devis automatique » passe par `concevoir_rapide_pour_lead` ; même geste,
  même endroit ; le résultat porte un calepinage `rapide`.
- **Simplicité** : 1 clic sur un lead « prêt » (gating `crm/devis_auto.py` inchangé) ; aucune carte à ouvrir.
- **Tâches** :
  1. Contrat : `etat_conception` (`rapide | complet`) + `origine_geometrie` (`trace_client | osm | aucune`) dans
     `apps/calepinage/contract_samples/calepinage_detail.json` et `conception.json`, SEUL sur `main` ; fini quand le test
     de contrat lit l'exemple. Fichiers : contrats (**calepinage**).
  2. Champ `Calepinage.etat_conception` (+ migration additive, défaut `complet` pour l'existant) ; fini quand le détail le
     sert. Fichier : `apps/calepinage/models.py` (**calepinage**).
  3. `SV/conception.py::concevoir_rapide_pour_lead(lead)` : adopte le calepinage ouvert (`SV/creation.py::adopter_ou_creer_pour_devis`,
     D-ACAL-12) ou en crée un `rapide` ; géométrie contour client > OSM (`crm.selectors` → `crm/roof_detect.py`) > aucune ;
     `remplir` borné par `recommander_taille` ; devis par `SV/devis.py::generer_devis` (porte unique ACAL108, ses gardes) ;
     fini quand un lead à GPS + facture rend un devis ET un calepinage `rapide` dont les panneaux sont dessinés.
     Fichiers : `SV/conception.py` (**calepinage**). `@model: opus` (flux inter-apps neuf).
  4. `VD/creation_auto.py::build_devis_auto` (résidentiel) délègue à `concevoir_rapide_pour_lead` (l'ancien chemin derrière
     `MOTEUR_CONCEPTION_RAPIDE` OFF) ; fini quand `tests_devis_auto.py` passe dans les deux positions. Fichiers :
     `VD/creation_auto.py`, `VD/creation_auto_residentiel.py` (**devis**). `@model: opus`. **Change un chiffre client**
     (compte borné par le toit rempli) → confirmation fondateur F2 + niveau de règles.
  5. La fiche lead montre kWc, production et économie SERVIS du calepinage `rapide` et le bouton « Affiner dans l'atelier »
     (ouvre `/calepinage/<id>`) ; fini quand le test de `IdentityRail` lit les trois chiffres du contrat. Fichiers :
     `FCRM/workspace/IdentityRail.jsx`, `FCRM/workspace/DevisTab.jsx` (**lead**). `@after` t3 (PACT11).
  6. L'atelier ouvert sur un calepinage `rapide` affiche « Conception rapide — à vérifier sur place » et passe `complet` au
     premier enregistrement ; fini quand l'e2e d'atelier voit le bandeau puis plus. Fichier : `frontend/src/pages/ventes/ToitureDesign.jsx`
     (**calepinage**).
- **Dépend** : CAP-D8-07, D8-08, D8-09, D8-10 (les chiffres viennent du moteur) ; ACAL421 ([ ]) réutilise t3.

---

## M5 — Estimateurs publics et retrait des jumeaux

### CAP-D8-12 — Le site public reste une estimation, nommée, bornée par le moteur
- **Besoin** : « le site promet un chiffre que le devis contredit ».
- **Preuves** : `WL/roofPro2.ts` en-tête « JAMAIS un devis : une fourchette » ; `apps/web/src/pages/api/roof-production.ts`
  (« × 0,72 kWc Canadian 720 W ») ; B5-de K14 (« prévision 20 % au-dessus du réel », cité en D6).
- **Chez nous** : **PRÉSENT** (estimation), **SANS BORNE** au moteur.
- **Plus petite version** : la garde CAP-D8-02 t5 + la mention « estimation — le devis la précise » au même endroit que le chiffre.
- **Tâches** :
  1. Mention « estimation » à côté de la production et de l'économie des estimateurs publics ; fini quand le golden de page
     la porte. Fichiers : pages `apps/web/src/pages/preview/toiture-3d-pro-11.astro` et composants (**web** — propriétaire à
     résoudre au moment de la tâche).
  2. Le webhook lead n'accepte du site que de la géométrie (contour, panneaux posés), jamais une production ou une économie
     reprise par un devis ; fini quand un test du webhook (`crm/tests_acal_webhook_roof_layout.py`, **lead** — à confirmer)
     prouve que `etude_params` ne reçoit rien du site.
- **Dépend** : CAP-D8-02 t5.

### CAP-D8-13 — Retirer les jumeaux morts (chacun APRÈS sa garde verte et son interrupteur levé 7 nuits)
- **Besoin** : « aucun second moteur » (règle tenue par CIQ128 et AGR132 pour le C&I et le pompage).
- **Preuves** : `docs/PLAN.md` l.1022 (CIQ128 [x]) ; `debitAtHmt` absent de `solar.js` (AGR132).
- **Chez nous** : **À FAIRE** après M3/M4.
- **Tâches** (une suppression chacune ; fini quand le symbole n'a plus d'appelant hors tests et que les gardes restent vertes) :
  1. Aperçu résidentiel navigateur du générateur (`FV/calc/roi.js::computeROI`, `FV/solar.js::productibleForCity` côté
     aperçu, branches « apercu » de `pages/ventes/generator/hooks/useApercuEtude.js`) → valeurs « moteur » seules
     (**generateur**).
  2. `fallbackPerKwc` en mode ERP (`FC/atelier/useAtelierBoot.js`, **calepinage**) — gardé pour le site public.
  3. `VD/geometrie.py::orientation_du_pan`, `pans_du_document` (ré-exports), `zone_toit_depuis_contour`,
     `plafond_physique_du_contour` (**calepinage**) `@model: opus`.
  4. `calepinage_options._Trame` et la prolongation de rangées (**calepinage**).
  5. Adaptateur `ventes/electrical_service.py` réduit à un renvoi puis retiré ; `solar_design.string_design` retiré
     (**calepinage**, **moteur**) `@model: opus`.
  6. Remplissage navigateur de l'atelier (`RP/optimizer.ts::liveResolveFlat/pentes` en mode ERP) — gardé pour le site
     public (**calepinage**).
  7. Interrupteurs `MOTEUR_CONCEPTION_*` retirés de `settings/base.py` une fois tous levés (**deploy**).
- **Dépend** : chaque tâche `@after` la fiche M3/M4 de sa grandeur.

---

## Correspondance avec l'existant (ne rien construire deux fois)
| Existant | Où il se construit désormais |
|---|---|
| ACAL480 (parité navigateur ↔ serveur) | CAP-D8-02 t1 |
| ACAL421 (conception automatique) | sur CAP-D8-10 t1 + CAP-D8-11 t3 |
| CAP-D7-01 t1 / t2 / t3 | D8-07 t4 / D8-05 t2 / D8-07 t5 |
| CAP-D7-02 t1-t2 | D8-06 t2 |
| CAP-D7-03 t2, CAP-D7-04 t3 | D8-05 t2 |
| CAP-D7-06 t1 | D8-08 t2 |
| CAP-D7-10 | D8-09 t1 |
| CAP-D7-05 (garde de taille dans `generer_devis`) | inchangé ; D8-11 t3 passe par cette porte |
| D-ACAL-17..20 (`USE_MOTEUR_CALEPINAGE` branché) | D8-10 |

## Comptes
13 fiches · 53 tâches (M0 : 5 · M1 : 8 · M2 : 6 · M3 : 19 · M4 : 6 · M5 : 9 — compté par grep des lignes de tâche) ·
`@model: opus` : 20 tâches.

## Non vérifié
- Propriétaires non résolus par `--owner-of` dans cette session : `apps/ventes/views/devis_calepinage.py`,
  `ventes/compatibilites.py`, `VD/catalogue.py`, `scripts/tests/*`, `apps/web/src/pages/preview/toiture-3d-pro-11.astro`,
  `crm/tests_acal_webhook_roof_layout.py` — marqués « à résoudre » dans leur tâche.
- Extractibilité pure d'`etude_horaire.py` / `pricing.py` : non lue en entier (CAP-D8-07 t1 est ce constat).
- Budget de latence 500 ms : choisi ici, non mesuré.
