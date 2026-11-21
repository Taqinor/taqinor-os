# CRITIQUE ADVERSE — « un moteur de conception partagé » (DECISION-moteur-partage.md + D8, 13 fiches, 53 tâches)

Critique unique, contexte neuf, 21/11/2026. Dépôt lu en LECTURE SEULE
(`C:\dev\taqinor-os\.claude\worktrees\calpinage-module-enhance-04bba5`, HEAD `33c076d00`, `origin/main` = `067b76f0c`).
Aucun fichier du dépôt modifié, aucun test, aucun docker. Chaque fait cite le `fichier::symbole` lu ou la commande
lancée dans CETTE session ; ce qui n'a pas été vérifié est en (f). Chemins relatifs à `backend/django_core/` sauf mention.

---

## (a) VERDICT

1. **Sain dans son intention, MALSAIN tel qu'écrit — « sound with corrections », et les corrections sont lourdes** : la
   cible « une grandeur, un calcul, deux surfaces » est la bonne ; le chemin proposé (déplacer production et économie
   dans `core`, interrupteurs par grandeur, devis rapide par la porte du calepinage) ne tient pas face au code.
2. **Le plus gros risque** : la cause donnée au chiffre faux n° 1 est FAUSSE. Les 111 420 kWh du PDF ne viennent pas
   d'`orientation_du_pan` : c'est `71 kWc × 1 687 (productible ville Agadir) × 0,9302`, la formule du moteur de devis qui
   ignore TOUTE orientation, par décision (D-ACAL-6 + QJR107). Aucune tâche D7/D8 telle qu'écrite ne corrige ce chiffre.
3. Le corriger = rendre la production client dépendante du dessin : cela touche presque tous les nouveaux devis qui ont
   un calepinage (taille, économies, retour, page publique), pas « seulement est-ouest et toit + sol ». C'est une
   décision fondateur (précision de D-ACAL-6 / QJR107), présentée ici comme un détail d'adresse.
4. Le « déplacement pur » de la production et de l'économie vers `core` n'a pas été vérifié par l'architecte (son § 9) ;
   vérifié ici : ≈ 10 000 lignes, I/O PVGIS, cache Django, 4 propriétaires, 14 niveaux de règles. À retirer du plan.
5. Ce que Reda demande (« chiffrer depuis le CRM sans ouvrir le calepinage ») EXISTE déjà et n'est menacé par rien :
   le plan peut être réduit de 53 à ≈ 25 tâches, les chiffres contradictoires traités en jours, pas en semaines.

---

## (b) Constats BLOQUANTS (exactitude ou règle violée)

### B1 — La cause du chiffre client faux est mal attribuée ; la correction prévue ne change pas le PDF
- **Affirmé** (DECISION § 1.1, § 1.5 ; D7-01 ; D8-05, D8-07) : « pose est-ouest 15° décrite 22° Sud par
  `orientation_du_pan` → PDF 111 420 kWh/an ». D7-01 note elle-même « probable (rejeu) ».
- **Lu** : le PDF rend la production du moteur de devis, jamais celle du layout —
  `apps/ventes/quote_engine/etude_chiffrage.py` l.543-560 (« AMOT15, D-ACAL-6 — la production VUE PAR LE CLIENT est celle
  du moteur devis : une production posée par le CALEPINAGE n'est plus recopiée »). Ce moteur calcule
  `apps/ventes/quote_engine/pricing.py::calculate_savings_roi` l.1604-1607 : `kWc × productible × PRODUCTION_DERATE`,
  ou le bloc horaire `apps/ventes/etude_horaire.py::jours_types_annee` (l.865) dont la signature n'a NI pente NI azimut :
  il lit `apps/parametres/pvgis_profils.py` l.126-127 `PVGIS_ANGLE_DEG = 30`, `PVGIS_ASPECT_DEG = 0`.
- **Preuve arithmétique** (script lancé ici sur `quote_engine/productible.py`) : `71 × 1687 × 0,930233 = 111 420` (Agadir) ;
  `34,08 × 1651 × 0,930233 = 52 341` (le « 52 341 PDF » de la matrice K) ; `154,78 × 1634 × 0,930233 = 235 266`
  (le PDF de F1-030, Tanger). Les trois chiffres PDF du rejeu sont la formule ville × kWc, au kWh près.
- **Conséquence** : `orientation_du_pan` n'influence que le LIBELLÉ d'orientation (annexe « paramètres du site »,
  `geometrie.py::extract_roof_config`) et l'étude bancable. D7-01 t2 et D8-05 t2 peuvent être vertes avec le PDF
  toujours à 111 420. La garde D8-02 t1 (« carte = Total = document = etude_params = PDF ») est rouge PAR CONSTRUCTION
  tant que D-ACAL-6 tient : deux modèles différents, pas un bug.
- **Correction** : réécrire § 1.1/§ 1.5 et la cause de D7-01 ; sortir « production du PDF » de D8-05 ; poser la question
  fondateur Q1 (e) AVANT toute tâche de production ; réécrire D8-02 t1 en trois gardes séparées (B9).

### B2 — F1 est très sous-estimé : c'est le modèle de production de TOUS les devis à calepinage qui change
- `jours_types_annee` / `calculer_etude_horaire` sont lus par (grep lancé) : `dimensionnement.py`,
  `dimensionnement_balayage.py` (la TAILLE, donc le nombre de panneaux et le PRIX), `offres_tailles.py` (cartes Éco /
  Recommandé / Max), `profils_comparatifs.py`, `horaire/public.py` + `public/payload_horaire.py` (page publique du
  devis), `horaire/batterie_lignes.py` (taille de batterie), `domain/dimensionnement_devis.py`, `moteur_ci/production.py`.
- Si la « production commerciale » lit les pans posés, soit tous ces lecteurs suivent (taille, prix, cartes, page
  publique changent pour tout toit qui n'est pas à 30° plein sud), soit ils restent sur le plan fixe et la taille est
  choisie avec un rendement que le PDF contredit. La DECISION § 8 dit « ne changent QUE là où ils sont faux (E-O,
  toit + sol) » : faux.
- Décision existante contredite sans être nommée : mémoire `residentiel-decisions-2710.md` (D-RES-2710-1) — « D-ACAL-6
  reste vrai… QJR107/D7 reste vrai pour orientation / inclinaison (jamais câblés : pas de coefficient sourcé) ; sans
  calepinage : PVGIS 30°/sud ». Et l'INTERDIT de tête de `docs/plans/PLAN_AUDIT_CALEPINAGE.md` (l.176-177) : « imprimer
  le P50 du calepinage sur le devis, le PDF ou la page publique ».
- **Correction** : F1 devient la question Q1 ; le patron à suivre est celui de D-RES-2710-1 (le moteur de devis CONSOMME
  une donnée SERVIE par le calepinage, il ne déménage pas) et de CIQ109 (`moteur_ci/production.py` l.281-299 : le
  calepinage retenu passe devant PVGIS pour le C&I — le précédent existe déjà et la DECISION ne le cite pas).

### B3 — « Déplacement PUR » de la production et de l'économie vers `core` : infaisable tel qu'écrit (D8-07 t2, D8-08 t1)
- `.importlinter::core-foundation-is-a-base-layer` : `core` n'importe AUCUN `apps`, « ce contrat n'a plus AUCUNE
  exception ». Or `apps/ventes/etude_horaire.py` importe (l.74-109) `django.utils.timezone`,
  `apps.parametres.pvgis_profils` (appels HTTP PVGIS, `PVGIS_TIMEOUT_S = 6`, cache Django), `apps.ventes.courbes_journalieres`,
  `apps.ventes.horaire.*` (qui lit `crm.selectors`, `parametres.selectors`, `regles_au_moins(devis, …)`),
  `apps.ventes.moteur_ci.production`, `quote_engine.bareme`, `quote_engine.pricing`, `solar_design`.
- Fermeture mesurée (`wc -l`) : `etude_horaire.py` 2 076 + `pricing.py` 1 936 + `courbes_journalieres.py` 1 521 +
  `horaire/` 2 054 + `bareme.py` 756 + `pvgis_profils.py` 1 304 + `moteur_ci/production.py` 330 ≈ 10 000 lignes,
  propriétaires `moteur`, `devis`, `parametres` (`check_ownership.py --owner-of` lancé ici), 14 niveaux de règles
  tressés dedans (`regles_au_moins|calcul_corrige` : 144 occurrences dans 41 fichiers hors tests).
- Un ré-export ne suffit pas : 8 `mock.patch('apps.ventes.etude_horaire.…')` et 9 lignes de patch sur
  `apps.ventes.domain.geometrie.…` cesseraient d'agir en silence (tests verts qui ne testent plus rien) ;
  `apps/web/tests/systemLoss20pct.test.ts` l.98-100 LIT `quote_engine/pricing.py` par chemin pour y vérifier les
  constantes de pertes ; `frontend/src/features/ventes/solar.test.mjs` l.486-489 en est le miroir déclaré.
- Les trois noyaux cités en précédent (calepinage, électrique, pompage) sont NÉS purs ; aucun n'a été extrait d'un
  module Django de cette taille. Le précédent ne vaut pas.
- Règle écrite violée : contrat L5 § 5 (`docs/audits/2026-11-20-calepinage-l5.md` l.112-113) — « Hors périmètre
  (signalé, jamais touché) : PDF client /proposal, moteur de devis (la production que voit le client reste la sienne —
  D-ACAL-6), pages du site public, argent (reste dans `ventes`) ». `core/conception/economie.py` sort l'argent de ventes.
- L'argument qui écarte la variante D2 (« le moteur vit dans ventes : l'atelier en dépendrait ») ne tient pas :
  `apps/calepinage` importe déjà `apps.ventes.services` 20 fois et `apps.ventes.selectors` 29 fois (grep lancé), et la
  propre façade M2 du plan « délègue à `ventes.services` (production/économie du devis) ». Le placement en fondation
  n'est justifié que quand deux consommateurs NE PEUVENT PAS s'importer (commentaire AOF33) — ce n'est pas le cas ici.
- **Correction** : SUPPRIMER D8-07 t2 et D8-08 t1 ; la production commerciale et l'économie RESTENT dans `apps/ventes`
  (propriétaire moteur), exposées par UNE fonction de service (`apps.ventes.services.chiffrer_conception(...)`) que
  l'adaptateur calepinage appelle. `core/conception` (si on le crée) ne porte que du SANS-ARGENT : lecture des pans
  posés, kWc, orchestration remplissage/électrique. D8-01 t2 (propriété « moteur » de `core/conception/production.py`
  et `economie.py`) disparaît.

### B4 — Interrupteur d'environnement + niveau de règles = un devis ENVOYÉ change de chiffre le jour de la bascule
- Mécanisme lu : `apps/ventes/domain/regles_calcul.py` — niveau porté par `Devis.regles_calcul` (14 niveaux), posé par
  une migration à la livraison (« ne passe que les brouillons jamais envoyés ») ; `/proposal` re-rend à chaque appel.
- Le plan pose EN PLUS `MOTEUR_CONCEPTION_<GRANDEUR>` (défaut OFF, levé « après 7 nuits »). Séquence : J0 la migration
  passe les brouillons et devis neufs au niveau N, interrupteur OFF → ancien chiffre ; J0..J1 des devis de niveau N
  sont ENVOYÉS avec l'ancien chiffre ; J1 l'interrupteur passe ON → ces devis envoyés se re-rendent avec le nouveau
  chiffre. Violation directe de « un devis envoyé garde ce que le client a reçu » (`devis-envoyes-nouveaux-rendus.md`).
- **Correction** : pour toute grandeur imprimée, UN seul verrou — le niveau de règles (activé à la livraison, comme
  les 13 précédents). Aucun interrupteur d'environnement sur un chiffre client. Les interrupteurs ne restent
  admissibles que pour l'AFFICHAGE de l'atelier (non imprimé).

### B5 — Le dry-run cité ne fait pas ce que le plan lui demande
- `apps/ventes/management/commands/regles_calcul_ecarts_dryrun.py::ecarts_du_devis` force `REGLES_CORRIGEES` (= 2) et
  `Command.handle` ne parcourt que `Devis.objects.filter(regles_calcul=REGLES_ORIGINE)` : il compare 1 → 2, rien
  d'autre. Lancé pour un niveau 15, il ne montrerait AUCUN écart de ce niveau.
- Chaque niveau exige aussi une migration ventes (0138, 0142…0159) : D8 monte le niveau dans 4 tâches (D8-05 t2,
  D8-07 t5, D8-10 t4, D8-11 t4) sans dire « un seul niveau pour le lot » (précédent AMOT118 : « contrat UNIQUE »).
- **Correction** : ajouter une tâche (propriétaire devis) « dry-run paramétré `--niveau N` sur tous les devis non
  brouillon de niveau < N, FIGURES étendues à nb panneaux et total TTC » ; UN niveau, UNE migration pour tout le lot.

### B6 — M5 « retirer les jumeaux morts » : plusieurs ne peuvent pas mourir
- Les branches d'avant un niveau de règles servent à vie les devis envoyés (re-rendu vivant) : l'ancienne production,
  l'ancienne lecture ne se suppriment pas (D8-13 t3 pour tout ce qui est imprimé).
- `apps/ventes/electrical_service.py` (docstring l.1-30) conçoit l'électrique d'un devis depuis ses LIGNES quand il n'a
  pas de calepinage (devis du générateur `/ventes/devis/nouveau`) ; D8-09 t2 « devis → calepinage lié » et D8-13 t5
  « adaptateur retiré » cassent ces devis.
- D8-09 t3 remplace `solar_design.string_design` dans `apps/ventes/solar_design.py` l.829-844 (`match_inverter` : le
  CHOIX de l'onduleur chiffré) et `apps/ventes/domain/catalogue.py::_paires_par_conception` l.285 (paires MPPT →
  quantités de la composition) : cela peut changer l'onduleur et les quantités, donc le PRIX des nouveaux devis, sans
  qu'aucun golden ni aucune décision ne soit nommé dans la tâche.
- D-ACAL-17..20 : « BRANCHER plutôt que retirer » ; l'INTERDIT de `PLAN_AUDIT_CALEPINAGE.md` l.187-189 protège
  `traduction.py`, `villa_service.py`.
- **Correction** : D8-13 t3 et t5 supprimées ; D8-09 t2 limitée aux devis QUI ONT un calepinage lié ; D8-09 t3 sortie
  du lot (tâche moteur/devis séparée, gate `tests/golden/moteur/**` + `split_dm_*.json`, changement de prix nommé).

### B7 — Le « devis rapide » par la porte du calepinage RETIRE des capacités au CRM et publie du deviné
- Ce qui existe (lu) : `apps/ventes/domain/creation_auto.py::build_devis_auto` chiffre depuis le lead en résidentiel,
  C&I ET agricole, avec `target_kwc`, `scenario`, `etude_extra`, `plafond_toit`, structure ; bouton de la fiche
  (`frontend/src/features/crm/workspace/DevisTab.jsx` l.154-259, `ventesApi.creerDevisAuto` → `/ventes/devis/auto/`),
  tunnel du site sans utilisateur (`creer_devis_automatique_depuis_lead`), générateur, copilote. **La demande de Reda
  est déjà satisfaite aujourd'hui.**
- D8-11 t3/t4 fait passer ce bouton par `apps/calepinage/services/devis.py::generer_devis`, qui (l.181-195) exige
  `feu_vert.verifier_avant_publication` (feu vert de visite + approbation à jour, D-ACAL-11/24, quand la société les
  exige), la garde électrique (D-ACAL-9), refuse l'agricole, et rend 409 si le calepinage tient déjà un devis non
  réutilisable. `build_devis_auto` n'a AUCUNE de ces portes (grep `feu_vert|approbation` vide). Résultat : dans une
  société à feu vert, plus de devis avant la visite ; plus de second devis automatique sur le même lead ; tunnel sans
  utilisateur face à `lead_en_portee(company, lead_id, user)`.
- Erreur de fonction : § 4.4 étape 1 cite `creation.py::adopter_ou_creer_pour_devis` — sa signature prend un `devis_id`
  (l.304) ; la porte lead est `ouvrir_ou_creer_pour_lead`. Le plan ne dit pas quoi faire d'un calepinage OUVERT déjà
  dessiné à la main (le re-remplir écraserait un dessin ; D-ACAL-12 interdit d'en créer un second).
- Principe déjà gravé dans le code et contredit : `apps/ventes/domain/geometrie.py` l.1228-1247 (« CE QUE LA ZONE
  AUTOMATIQUE NE DIT PAS » : ni type de toit, ni pente, ni face, parce que le CLIENT lisait « Sud 180° · 22° » sur un
  toit que personne n'a mesuré — « un chiffre n'est publié qu'une fois qu'un humain l'a regardé ») et
  `::plafond_physique_du_contour` l.1318-1335 (« poser ici un second moteur (pente et azimut devinés) donnerait un
  nombre que l'écran contredirait : c'est exactement le piège que USE_MOTEUR_CALEPINAGE tient fermé »). Un remplissage
  serveur sur emprise OSM écrit dans LE calepinage du lead (D-ACAL-1) fait exactement cela, et F2 rabote un devis sur
  cette base.
- L'atelier re-pave au démarrage (`geometrie.py` l.1435-1436 : « deserializeLayout… repave au boot de toute façon ») :
  tant que le remplissage navigateur vit (interrupteur POSE OFF), ouvrir l'atelier sur un calepinage « rapide » donne
  un second compte → le défaut qu'on veut tuer, recréé.
- **Correction** : M4 réécrit — le bouton « Devis automatique » RESTE sur `build_devis_auto` (aucune porte ajoutée,
  trois marchés) ; « rapide » = un MARQUAGE du calepinage que ce devis adopte/crée, jamais un remplissage publié ; un
  calepinage ouvert déjà dessiné n'est jamais réécrit ; rien d'un dessin « rapide » ne sort côté client (planche, 3D,
  paramètres du site) ; F2 retiré (Q3) ; D8-11 t4 supprimée ; D8-11 dépend de Q2/Q3/Q4.

### B8 — `USE_MOTEUR_CALEPINAGE` : le plan promet ce que le code et le plan d'audit interdisent
- `erp_agentique/settings/base.py` l.1714 : `os.environ.get('USE_MOTEUR_CALEPINAGE', '0') == '1'` — variable GLOBALE
  d'environnement, pas un réglage par société ; « levé société par société » (DECISION § 6 M3) n'existe pas.
- `PLAN_AUDIT_CALEPINAGE.md` l.189 : « activer USE_MOTEUR_CALEPINAGE en production » est dans les INTERDITS d'un run.
- OFF depuis le commit `3f522c549` du 05/10/2026 (47 jours) ; `docs/claude-memory/deploy-decisions-fondateur.md` :
  aucune clé optionnelle n'est dans le `.env` de prod, chaque bascule est un geste de Reda. Six interrupteurs de plus
  sur le même patron finiront pareil : deux chemins vivants à vie, donc DEUX fois plus de calculs qu'aujourd'hui.
- **Correction** : D8-10 t3/t4 et la levée du drapeau deviennent GATED (question Q5, dry-run d'abord) ; plus aucun
  nouvel interrupteur d'environnement (B4) ; critère d'arrêt par marche (d).

### B9 — La preuve « M2 ne change aucun chiffre » ne couvre pas les chiffres du devis
- ACAL382 = `apps/calepinage/tests/test_golden_trois_projets.py` : golden de `simuler_calepinage` (l'ÉTUDE TECHNIQUE).
  ACAL383 = `apps/web/tests/userJourneyPro11.test.ts` l.607-630 : le document `roof_layout` émis par une séance
  navigateur. Aucun des deux ne lit un chiffre du moteur de devis, du C&I ni de l'agricole.
- Les vrais goldens des chiffres client ne sont PAS cités par le plan : `apps/ventes/tests/test_moteur_golden_build_quote_data.py`
  (SPL160 : sha256 du `data` rendu — résidentiel 2 options, mono, divergents, industriel, commercial, pompage,
  multi-villas, langues, options PDF ; « une tâche SPL ne re-capture JAMAIS »), `tests/golden/moteur/**`,
  `tests/golden/regles_calcul_origine.json`, `split_dm_*.json`, `test_quote_engine_snapshot.py`, `test_figures_parite.py`.
  Limite lue dans son en-tête : réseau coupé, PVGIS en repli hors ligne — le chemin PVGIS vivant n'y est pas figé.
- D8-02 t1 veut comparer dans UN test Django la carte et le Total (TypeScript navigateur) au PDF : impossible sans
  pont de golden entre les deux suites.
- **Correction** : gate de TOUTE marche qui touche `apps/ventes` = les goldens SPL160 ci-dessus inchangés au bit, sans
  re-capture ; D8-02 t1 scindée en (i) carte = Total = document (vitest `apps/web`, golden ACAL383 étendu), (ii)
  production servie à l'atelier = production du rendu `/proposal` du même devis (Django), (iii) l'écart étude technique
  ↔ devis est SERVI et affiché (`EcartDevis`), jamais « égalité ».

### B10 — C&I et agricole absents de « un calcul par grandeur »
- Le tableau § 4.1 nomme UNE production client (« le modèle horaire du devis »). Le C&I a la sienne
  (`apps/ventes/moteur_ci/production.py` : PVGIS seriescalc 8 760 h au plan déclaré, calepinage retenu devant PVGIS —
  D-CIQ, autoconsommation heure par heure) ; l'agricole a `core.pompage` et `generer_devis` le refuse
  (`services/devis.py::_refuser_lead_agricole`). `etude_schema.py::cles_etude_du_layout` l.489 n'écrit RIEN pour le C&I.
- Un `chiffrer` d'atelier qui applique le modèle résidentiel à un calepinage C&I afficherait un chiffre que le devis
  C&I contredit — un doublon de plus, créé par le plan.
- **Correction** : le contrat `conception.json` porte le `marche` et le service de chiffrage DISPATCHE vers le moteur
  du marché (résidentiel / C&I / agricole) ; fiche D8-07 réécrite en ce sens ; rien de l'agricole ne passe par M4.

---

## (c) Améliorations NON bloquantes (séparées)

- **Carte des doublons — précisions** : « USE_MOTEUR_CALEPINAGE OFF depuis des mois » → 47 jours ; imports croisés
  « 18 / 36 » : mon grep (mentions comprises) donne 25 / 47 fichiers, même ordre de grandeur ; « Publiable à vide »
  est en partie VOULU (`services/electrique.py::_rapport_publication` l.2848-2852 : matériel non désigné = indéterminé,
  D-ACAL-9, « publié, jamais bloquant ») — D8-09 doit ajouter un ÉTAT, pas changer la règle. Vrais et vérifiés :
  `orientation_du_pan` garde la lecture du toit pour une pose est-ouest (exception écrite l.95-97, C-ACAL-081) ;
  `pans_du_document` additionne toit + surfaces et lit la face = `rowAzimuthDeg + 90` (l.554) ; `PANEL2_WATT = 720`
  (`apps/web/src/lib/roofPro2.ts` l.25) contre `PANEL_W_DEFAUT = 710` (`solar.js` l.283) ; `useAtelierBoot.js` l.26,
  255, 392 (`rendementPvgis: null`, `fallbackPerKwc`) ; écrêtage dans `optimizer.ts::renderLiveWinner` l.754 seulement ;
  un moteur électrique, trois adaptateurs.
- **Latence** : `PVGIS_TIMEOUT_S = 6` — sur un point GPS jamais vu, le premier chiffrage attend PVGIS ; le budget
  « 500 ms au 95e centile » est inventé. Le chiffrage doit être demandé à l'ouverture et à l'enregistrement, pas à
  chaque geste ; le kWc (n × Wc du module servi par `design-context`) reste calculé sur place, c'est de l'arithmétique.
- **Hors ligne / téléphone** : aujourd'hui l'atelier affiche un chiffre de table sans réseau ; le plan le remplace par
  « à recalculer ». Acceptable pour production et économie, pas pour le compte et le kWc (terrain, toit).
- **Site public** : `apps/web/src/scripts/roofPro11/**` est PARTAGÉ entre le site (déployé seul par Cloudflare à chaque
  merge) et l'atelier ERP (déployé à la main par Reda). Toute tâche D8 qui touche ces fichiers sort sur le site
  public avant l'ERP ; chaque « mode ERP » doit être inerte côté site et le dire dans son critère de fin.
- **D8-12 t2** touche le flux de données du formulaire du site (webhook lead) : c'est un « stop-and-ask » de la
  commande web (CLAUDE.md) — à poser à Reda, pas à router en silence.
- **D8-04 t6** (cliquet des imports croisés) : bon, à garder ; compter les IMPORTS, pas les mentions.
- **Coût** : 20 tâches opus ; après coupes il en reste ≈ 8. `core/conception` peut ne pas exister : `pans_poses` est
  une lecture de document qui a sa place dans `core/calepinage` (déjà propriétaire calepinage), ce qui supprime D8-01
  t2-t4 (ligne d'ownership, contrat import-linter, test de pureté).

---

## (d) Ordre de migration que je signerais

**Étape 0 — les chiffres contradictoires, sans moteur neuf (jours).** D7-02 (module de départ catalogue, 720 → module
réel), D7-01 t1 (même écrêtage carte / Total), D7-03 t1-t2 (surfaces chiffrées), D7-04 (pas au sol, convention
d'azimut — contrat d'abord), D7-05 (taille sans facture), D7-06 t2-t3, D7-10 (état « non vérifiable »). Gardes M1
RÉÉCRITES (B9) + les trois règles de nuit D8-03. Arrêt : une garde ne passe pas rouge sur `da49cb55b` → elle ne
compte pas. NE corrige PAS les 111 420 : le dire à Reda tel quel.

**Étape 1 — décision fondateur Q1 (production client et dessin).** Rien ne se construit sur la production avant.

**Étape 2 — une seule porte de chiffrage, DANS ventes.** Contrat seul sur `main` (`conception.json` avec `marche`,
PACT10) ; `apps.ventes.services.chiffrer_conception` (propriétaire moteur) = le calcul du rendu, dispatch par marché ;
route calepinage qui l'appelle ; les cartes de l'atelier affichent production et économie SERVIES (à l'ouverture et à
l'enregistrement), kWc local. Aucun chiffre imprimé ne bouge : gate = goldens SPL160 au bit. Arrêt : un golden bouge
→ on revient en arrière, pas de re-capture.

**Étape 3 — si Q1 = oui : le moteur de devis CONSOMME le rendement des pans posés** servi par le calepinage (patron
D-RES-2710-1 / CIQ109), seulement pour un dessin enregistré par un humain ; UN niveau de règles, UNE migration,
dry-run paramétré montré à Reda AVANT (B5) ; taille, cartes de tailles et page publique lisent le même rendement.
Arrêt : le dry-run montre un écart qu'on ne sait pas expliquer devis par devis.

**Étape 4 — lecture unique des pans posés** (`pans_poses` pur, dans `core/calepinage`), `geometrie.py` en appelant
mince, déplacement prouvé par `split_dm_cal.json` + goldens ; D7-01 t2 et D7-04 t3 s'y construisent.

**Étape 5 — « rapide »** : marquage + « Affiner dans l'atelier », sur `build_devis_auto` inchangé (B7), après Q2-Q4.

**Étape 6 (GATED fondateur) — remplissage serveur autoritaire** : dry-run `comparer_compte_moteur_calepinage` étendu
(D8-10 t2) montré à Reda ; puis seulement D8-10 t3/t4 et ACAL421. Arrêt : écarts hors tolérance PVG2 sur plus de
quelques leads → on garde le dessin navigateur et on retire la promesse.

**Coupé** : D8-07 t2, D8-08 t1, D8-01 t2-t4 (si `core/calepinage` accueille la lecture), D8-09 t3, D8-11 t4, D8-13 t3
/ t5 / t7, tous les `MOTEUR_CONCEPTION_*`, D8-12 (reporté, question web). **À ne PAS couper** : contrat d'abord,
gardes rouges d'abord, niveau de règles + dry-run avant tout chiffre client, D7 P0, cliquet d'imports, l'écart étude
technique ↔ devis affiché en interne.

---

## (e) Décisions fondateur réellement nécessaires (une question simple chacune, réponse recommandée)

- **Q1 — Production sur le devis.** « Aujourd'hui le devis annonce la production standard de la ville (panneaux à 30°
  plein sud), quel que soit le dessin : un toit est-ouest dessiné à 98 574 kWh sort à 111 420 sur le PDF. Voulez-vous
  que les NOUVEAUX devis qui ont un calepinage enregistré annoncent la production du dessin réel ? Presque tous ces
  devis changeront (taille, économies, retour), les devis envoyés ne bougent pas, et vous voyez la liste des écarts
  avant. » — **Recommandé : OUI**, limité aux dessins enregistrés par quelqu'un, liste des écarts d'abord. (Précise
  D-ACAL-6 et QJR107.)
- **Q2 — Dessin automatique et client.** « Un dessin posé tout seul (contour du client ou bâtiment de la carte), que
  personne n'a vérifié, peut-il apparaître dans ce que voit le client (plan, vue 3D, orientation du toit) ? » —
  **Recommandé : NON**, interne seulement, marqué « rapide — à vérifier sur place ».
- **Q3 — Plafond du devis automatique (F2).** « Le devis automatique doit-il réduire le nombre de panneaux à ce que
  l'ordinateur arrive à poser sur le contour, sans que personne ait regardé le toit ? » — **Recommandé : NON pour
  l'instant** : garder la borne large d'aujourd'hui et afficher en interne « le toit rempli tient N panneaux ».
- **Q4 — Devis automatique avant la visite.** « Dans une société qui exige le feu vert de visite ou une approbation,
  le devis automatique depuis la fiche lead reste-t-il possible avant la visite, comme aujourd'hui ? » —
  **Recommandé : OUI**, inchangé (devis préliminaire ; la case « Devis final » du 19/11 dit déjà le reste).
- **Q5 — Compte de panneaux par le serveur.** « Voulez-vous que le nombre de panneaux vienne du calcul du serveur
  plutôt que du dessin de l'écran, après avoir vu la comparaison sur vos calepinages ? » — **Recommandé : décider
  après la comparaison**, pas maintenant. (Lève l'INTERDIT « activer USE_MOTEUR_CALEPINAGE en production ».)
- **Q6 — Toit + champ au sol (précise D-ACAL-5).** « Quand un dessin a un toit ET un champ au sol, le devis prend
  tout, ou vous cochez les surfaces à chiffrer ? » — **Recommandé : cases cochées par défaut**, visibles avant de générer.
- Pas une question fondateur si les corrections B3/B4 sont prises : l'argent hors de ventes, les interrupteurs.

---

## (f) Non vérifié (dit tel quel)

- Aucun test lancé : « rouge sur `da49cb55b` » des gardes M1 reste attendu, non mesuré ; aucun `lint-imports` lancé.
- Les trois PDF du rejeu n'ont pas été rouverts : l'attribution à la formule ville × kWc repose sur l'égalité
  arithmétique exacte des trois chiffres (111 420, 52 341, 235 266) et sur la lecture du code ; je n'ai pas vérifié
  la ville de chaque lead dans le dossier `T1/rejeu/`.
- Le contenu exact des fixtures SPL160 (présence d'un devis avec `roof_layout` est-ouest, d'un bloc horaire PVGIS
  vivant) : en-tête lu seulement.
- Le code TypeScript : seuls les symboles cités ont été greppés (`renderLiveWinner` l.754, `liveActiveResult`,
  `PANEL2_WATT`) ; « re-pave au démarrage » vient des commentaires de `geometrie.py` et de `roof-tool-pro11.ts`, pas
  d'une lecture complète de `deserializeLayout`.
- Latence réelle d'un chiffrage, usage hors ligne réel de l'atelier sur téléphone, comportement du tunnel du site
  face à une création de calepinage sans utilisateur : non mesurés, non rejoués.
- QJR107 : cité d'après `residentiel-decisions-2710.md` ; la tâche d'origine n'a pas été retrouvée dans `docs/done_task.md`.
- `docs/claude-memory/ci-decisions-fondateur.md`, `agricole-decisions-fondateur.md`, `kwh-declare-vs-factures.md` : non
  relus en entier ; B10 s'appuie sur le code (`moteur_ci/production.py`, `etude_schema.py`, `services/devis.py`).
- Les sources de marché du § 2 de la DECISION : non relues.
