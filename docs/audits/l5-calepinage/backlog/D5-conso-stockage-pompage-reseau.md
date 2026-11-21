# D5 — Consommation, stockage, hors réseau, pompage et règles du réseau (consolidation, tour 1, 21/11/2026)

Juge : D5. Lecture seule du dépôt `calpinage-module-enhance-04bba5` (HEAD 5a75a182b), aucun fichier du dépôt modifié,
ni docker ni test lancé. Les verdicts ci-dessous viennent de lectures de code faites dans cette session
(`fichier::symbole`) ; « non vérifié » est dit quand ce n'est pas le cas.

Sources lues : les sections de propositions et de grappes des onze fichiers `bench/` (B1 §1.I, §2.B, §2.F, §8 ; B2
propositions ; B3 §3 et §7.3 ; B4 §6.2 ; B5-de §2, §4 ET passe 2 §9-§12 ; B5-en §4, P2.2, P2.3 ; B5-es §2, §4.1, §5 ;
B5-fr §3, §5 ; B5-nl §4, §6, §7 ; B6 §3, §5 ; B7 §2, §3) et les backlogs voisins `D3-electrique.md` et
`D4-simulation-resultats-rapport.md` (titres seulement, pour ne pas doublonner).

Abréviations de chemins : `CA` = `backend/django_core/apps/calepinage`, `CP` = `backend/django_core/core/pompage`,
`FE` = `frontend/src/features/calepinage`, `RP` = `apps/web/src/scripts/roofPro11`.

**Ce qui revient le plus souvent dans ce domaine** : le serveur calcule déjà beaucoup plus que ce que l'écran laisse
saisir ou voir (batterie, charges VE/PAC, régime 82-21). Les quatre premières fiches branchent du travail déjà fait.
Côté pompage, le calcul vit dans `core/pompage/**`, dont le **propriétaire est `devis`** (vérifié par
`python scripts/check_ownership.py --owner-of backend/django_core/core/pompage/volumes.py` → `devis`). Le moteur
agricole client `apps/ventes/quote_engine/agricole/**` appartient à `moteur`. Le calepinage n'y garde que l'écran
`FE/pompage/PompagePanel.jsx` et la porte `CA/views/pompage.py` (propriétaire `calepinage`). Chaque fiche pompage dit
donc de quel côté vit chaque tâche.

---

## A. PRÉSENT SANS ÉCRAN — le calcul existe, il manque la saisie ou l'affichage (en tête, comme demandé)

| Trouvaille | Preuve dans le code | Ce qui manque | Fiche |
|---|---|---|---|
| Réserve de secours **déduite des appareils secourus** × durée (CALX270) | `CA/services/batterie.py::reserve_depuis_appareils` ; lue par `CA/services/etapes/batterie.py::_bloc_batterie_dispatch` (`declaration.get('appareils')`, `duree_secours_h`) | **La porte d'écriture la REFUSE** : `CA/services/electrique.py::CLES_BATTERIE` n'admet ni `appareils`, ni `duree_secours_h`, ni `fenetres`, ni `part_effacable_pct`, ni `plafond_effacable_kw` (`_valider_batterie` rejette toute clé inconnue). Seul un document `roof_layout.battery` rempli à la main y arrive (`etapes/batterie.py::_declaration_du_document`). Aucun champ dans `FE/atelier/PanneauBatterie.jsx` | CAP-D5-01 |
| Commande horaire à **SOC cible** (fenêtres de charge/décharge, CALX268) | `CA/services/batterie.py::_fenetres_saisies` | même refus que ci-dessus ; aucun écran | CAP-D5-01 |
| **Pointe avant/après effacement et dépassements restants** (CALX269) | `CA/services/batterie.py::_pointe` (`pointe_avant_kw`, `pointe_apres_kw`, `depassements_residuels`) | `CA/services/etapes/batterie.py::_publier` ne les recopie pas dans le bloc publié ; aucun écran | CAP-D5-01 |
| **Cycles par an** et **vieillissement par cycles** de la banque (CALX63) | `CA/services/etapes/batterie.py::_publier` (`groupes[].cycles_an`, `total.vieillissement`) | `FE/atelier/PanneauBatterie.jsx` n'affiche ni l'un ni l'autre (grep `cycles_an`/`vieillissement` dans `FE` : 0 hors tests) | CAP-D5-01 |
| **Seuils de protection hors réseau** (veille / entretien / arrêt, CALX272) | `CA/services/hors_reseau.py::_seuils_de_protection` ; clé `seuils` admise par `CA/services/electrique.py::CLES_HORS_RESEAU` | l'écran ne saisit que « hors réseau oui/non » et « jours d'autonomie » | CAP-D5-01 |
| **Charges VE, pompe à chaleur, climatisation** (km/jour, recharge « PV optimisée », borne bornée, COP selon la température, BTU/EER — CALX261-264) | `CA/services/charges.py::courbe_vehicule`, `courbe_pac`, `courbe_climatisation` ; lues par `CA/services/courbe_charge.py::construire_courbe_charge` (`charges`) via `CA/services/simulation.py::_declaration_consommation` | aucun écran n'écrit `consumption.charges` (grep `km_par_jour|cop_points|charges` dans `RP/consumption.ts` et `FE` : 0). L'atelier n'a qu'un appareil plat « Recharge voiture électrique » (`apps/web/src/lib/applianceConsumption.ts`, 7 400 W × 3 h, provenance `table_atelier`) | CAP-D5-02 |
| **Régime loi 82-21** (déclaration < 11 kW, accord, autorisation ≥ 5 MW, sourcé décret 2.25.100) | `backend/django_core/core/reglementaire/regime_8221.py::regime_8221` (lu par devis, chantiers, paramètres) | le calepinage ne l'appelle jamais (grep `8221` dans `CA` : 0 hors une migration) | CAP-D5-03 |
| **Plafond légal du surplus : 20 % de la production annuelle** | `backend/django_core/apps/ventes/quote_engine/constants_82_21.py::PLAFOND_INJECTION_PCT` (source « loi 82-21 art. 12 ; ANRE 04/26 art. 7 ») | le calepinage, qui simule l'injection heure par heure (`CA/services/autoconsommation.py::bilan_autoconsommation`), ne la compare jamais à ce plafond | CAP-D5-03 |

---

## B. Fiches de capacités (classées)

Barème : preuves 1-5 (lanes distinctes × force : forum > notes de version > page commerciale), adéquation 1-5 (cet
utilisateur : pompage, réseau faible, chaleur, toits béton, commerciales non ingénieures), effort S=1 / M=2 / L=3.
Score = preuves × adéquation ÷ effort.

### CAP-D5-01 — Batterie « mode expert » : saisir et voir ce que le serveur calcule déjà
- **Besoin** : « dire quels appareils doivent tenir pendant la coupure et combien d'heures » ; « charger jusqu'à X %
  avant telle heure » ; « combien de fois par an la pointe dépasse encore » ; « combien de cycles par jour ».
- **Preuves** : B2 #8 ; B1 C25, V354, S325, S324 ; B6 R5 (cycles/jour), K36, K37 ; B5-de K43 (37 fils, 50 lignes BATT,
  passe 2) et K53 (22 fils, 31 lignes BACKUP), contrôle §11 n° 11 (« secours : appareils secourus et durée », 44/49) ;
  B7 grappes 21, 35, 49. URL : https://aurorasolar.com/sell-battery-storage/ ;
  https://forum.valentin-software.com/topic/10489-backup-box-notstrom-gateway/ ;
  https://forum.valentin-software.com/topic/10064-batteriesystem-zyklenbelastung-lebensdauer/
- **Qui le fait** : PV*SOL « gestion d'énergie » (charge retardée, réserve, nombre de dépassements par an) ; OpenSolar
  « Enter by Appliance » (puissance continue et de pointe par appareil) ; Pylon (cycles/jour).
- **Chez nous** : PRÉSENT SANS ÉCRAN, avec un **refus à l'écriture** — `CA/services/electrique.py::CLES_BATTERIE`
  (11 clés) rejette `appareils`, `duree_secours_h`, `fenetres`, `part_effacable_pct`, `plafond_effacable_kw` que
  `CA/services/etapes/batterie.py::_bloc_batterie_dispatch` sait lire ; `CA/services/batterie.py::_pointe` calcule les
  dépassements que `_publier` ne publie pas ; `FE/atelier/PanneauBatterie.jsx` n'a que packs, seuil, réserve en bloc,
  heures, stratégie, couplage, hors réseau oui/non, jours.
- **Plus petite version crédible** : la commerciale coche « Secours » et choisit les appareils secourus (nom, kW continu,
  kW au démarrage, quantité, tout SAISI) et la durée de coupure ; le serveur en tire la réserve (déjà écrit). En
  « Mode expert » : fenêtres de charge avec SOC visé (≤ 3), part effaçable, seuils hors réseau. Sortie lue : cycles par an
  (et « ≈ N par jour » = cycles/an ÷ 365, dit comme une moyenne), capacité année par année, pointe avant/après et nombre
  de dépassements restants. Rien n'est supposé : un champ vide garde le comportement actuel (bloc omis avec son motif).
- **Simplicité** : étape **Résultats** › Batterie ; « Secours » en essentiel, le reste en expert.
- **Tâches** (propriétaire `calepinage` pour toutes ; fichiers vérifiés par `check_ownership.py`) :
  1. Admettre `appareils`, `duree_secours_h`, `fenetres`, `part_effacable_pct`, `plafond_effacable_kw` dans la
     déclaration de batterie ; fini quand `POST entree-electrique/` avec `batterie.appareils` + `duree_secours_h` rend
     200 et que la simulation suivante publie la réserve déduite (mention `MENTION_RESERVE_APPAREILS`), et qu'une forme
     fausse est refusée en nommant `batterie.appareils[i].<champ>` — `CA/services/electrique.py` (`CLES_BATTERIE`,
     `_valider_batterie`), test du module existant `CA/tests` de l'entrée électrique.
  2. Publier `pointe_avant_kw`, `pointe_apres_kw`, `heures_au_dessus_du_seuil` et le **nombre** de
     `depassements_residuels` dans `resultat['batterie']['total']` ; fini quand le contrat
     `CA/contract_samples/calepinage_simulation.json` les porte et qu'une simulation `peak_shaving` les remplit —
     `CA/services/etapes/batterie.py::_publier` (contrat d'abord, PACT10).
  3. Ajouter à l'écran la liste « Appareils secourus » et la durée ; fini quand enregistrer deux appareils et 4 h
     affiche « réserve déduite : X kWh » relue du serveur — `FE/atelier/PanneauBatterie.jsx`.
  4. Afficher cycles/an, vieillissement, pointe avant/après et dépassements dans un bloc replié « Mode expert » ; fini
     quand les quatre lignes se lisent sur l'exemple du contrat et disent « non calculé » sinon — `FE/atelier/PanneauBatterie.jsx`.
  5. Saisir les trois seuils hors réseau (et la fenêtre SOC) sous « Mode expert » ; fini quand un seuil d'arrêt saisi
     change `hors_reseau.mentions` après recalcul — `FE/atelier/PanneauBatterie.jsx`.
  Dépendances : ACAL447 (courbe de SOC sur une semaine) se lit à côté ; ACAL394 (interrupteur « Mode expert »).
- **Score** : 5 × 5 ÷ 2 = **12,5** — rang 1.

### CAP-D5-02 — Charges VE, pompe à chaleur et climatisation du modèle serveur, enfin saisissables
- **Besoin** : « la voiture électrique qu'il va acheter », « la pompe à chaleur l'hiver », « la clim de juillet ».
- **Preuves** : B1 S023, S087, S314, S316 ; B6 K39 (7 outils), K40 (7 outils), K66 ; B5-de K38 (27 fils, 34 lignes LOAD,
  passe 2) et §11 contrôle n° 17 (hypothèses de consommation affichées, 25/29) ; B5-en P2.2 (clim de nuit) ; B7 grappe
  36. URL : https://forum.valentin-software.com/topic/10303-unschl%C3%BCssige-reichweitenberechnung-elektrofahrzeug/ ;
  https://forum.valentin-software.com/topic/10849-anlagenart-in-pv-sol-premium-ausw%C3%A4hlen/
- **Qui le fait** : PV*SOL (groupes de véhicules, km, mode « PV optimisé » ; PAC à COP par température) ; Reonic, Eturnity.
- **Chez nous** : PRÉSENT SANS ÉCRAN — `CA/services/charges.py::courbe_vehicule` (2 modes, borne bornée),
  `courbe_pac` (`_points_cop`, aucun COP par défaut), `courbe_climatisation` ; lus par
  `CA/services/courbe_charge.py::construire_courbe_charge` depuis `consumption.charges` ; aucun écran ne l'écrit.
- **Plus petite version crédible** : dans le panneau consommation de l'atelier, un bouton « Ajouter une charge à venir »
  (VE, PAC, clim) avec les seuls champs que le serveur exige (km/jour + kWh/100 km, ou kW + COP par température, ou BTU
  + EER), tous saisis ; le serveur ajoute la courbe ; l'écran affiche « charges ajoutées : X kWh/an » relu du bloc
  `consommation`. **D-RES-2710 respectée** : la case « déjà dans les factures » interdit l'ajout (un VE déjà possédé
  n'ajoute aucune couche).
- **Simplicité** : étape **Toit** (relevé de la consommation) ; essentiel = type + 2 champs ; le reste caché.
- **Tâches** :
  1. Écrire `consumption.charges[]` depuis l'atelier (VE, PAC, clim) ; fini quand une charge VE saisie survit à
     l'enregistrement et au rechargement, et que la simulation publie son énergie — `RP/consumption.ts`, `RP/prefill.ts`
     (propriétaire `calepinage`).
  2. Refuser côté serveur une charge marquée « déjà comprise dans la facture » en NOMMANT le champ (D-RES-2710) ;
     fini quand le refus cite `consumption.charges[i]` — `CA/services/courbe_charge.py`.
  3. Afficher les charges ajoutées et leur énergie sous la courbe journalière ; fini quand la ligne se lit sur l'exemple
     du contrat — `FE/production/PanneauProduction.jsx` (après ACAL446).
  Hors propriétaire : retirer ou garder l'appareil plat « ev » de `apps/web/src/lib/applianceConsumption.ts`
  (propriétaire `web`, `docs/WEB_PLAN.md`) — seulement si Reda veut une seule porte ; non proposé d'office.
- **Score** : 5 × 4 ÷ 2 = **10** — rang 2.

### CAP-D5-03 — Loi 82-21 au raccordement : régime, base de puissance et part injectée face au plafond de 20 %
- **Besoin** : « est-ce une déclaration ou une demande de raccordement ? », « est-ce que j'injecte plus que la loi
  permet ? », « déclarer les kVA et pas seulement les kWc ».
- **Preuves** : B5-fr §3 (loi 82-21, décret publié, surplus ≤ 20 %) ; B5-de K47 (43 fils, 48 lignes GRIDDOC, passe 2),
  P16, §11 contrôle n° 12 (21/23) ; B5-es K16 (15 fils) ; B7 U15. URL : https://akkudoktor.net/t/10kwp-selbstbau-pv/27745 ;
  https://canalsolar.com.br/projetos-7-5-kw-podem-ser-reprovados-por-inversao-de-fluxo/
- **Qui le fait** : aucun outil international ne connaît la 82-21 ; c'est notre avantage local.
- **Chez nous** : PRÉSENT SANS ÉCRAN dans le calepinage — `core/reglementaire/regime_8221.py::regime_8221` (seuils
  sourcés, `BASE_PUISSANCE = 'a_confirmer_avec_le_distributeur'`, guichet « à confirmer ») et
  `apps/ventes/quote_engine/constants_82_21.py::PLAFOND_INJECTION_PCT` (20, sourcé) ; le calepinage publie déjà
  l'injection simulée (`CA/services/autoconsommation.py::bilan_autoconsommation`) et la puissance injectée en kVA
  (`CA/services/raccordement.py::verdicts_raccordement`, `_puissance_injectee_kva`).
- **Plus petite version crédible** : l'onglet Raccordement affiche « Régime 82-21 : <déclaration | accord | autorisation>
  — puissance retenue max(kWc, kW AC) = X, base à confirmer avec le distributeur (source : décret 2.25.100 art. 5) » et
  « Injection simulée : N % de la production annuelle ; plafond légal 20 % (loi 82-21 art. 12) », avertissement non
  bloquant au-delà, avec la mention « revente non ouverte en basse tension » que la constante porte déjà. Aucun chiffre
  neuf : seuils et plafond sont lus, jamais recopiés.
- **Simplicité** : étape **Électrique** › Raccordement, toujours visible (une ligne + un voyant).
- **Tâches** :
  1. Publier `regime_8221` (code, libellé, base, source) dans le bloc raccordement, depuis la puissance TOTALE du site ;
     fini quand un calepinage de 12 kWc publie « accord de raccordement » avec sa source — `CA/services/raccordement.py::bloc_raccordement`
     (lecture de `core/reglementaire`, couche fondation ; aucun fichier `securite` modifié).
  2. Lire le plafond 20 % et sa source par un sélecteur mince dans `apps/ventes/selectors_calepinage.py` (propriétaire
     `calepinage`, vérifié) et publier `part_injectee_pct` contre ce plafond ; fini quand une simulation à 35 %
     d'injection publie un avertissement nommé — `CA/services/raccordement.py`, contrat `calepinage_raccordement` du module.
  3. Afficher les deux lignes ; fini quand elles se lisent sur l'exemple du contrat — `FE/electrique/Raccordement.jsx`.
  Voisin : CAP-D3-25 (garde kVA/kWc, part électrique) — la part « régime » reste ici.
- **Score** : 4 × 5 ÷ 1,5 = **13,3** (effort S-M) — classé rang 3 parce que la tâche 2 dépend d'une vérification à faire
  (voir « non vérifié » : la règle des 20 % porte-t-elle sur le surplus vendu ou sur toute injection ?).

### CAP-D5-04 — Pompage : le réservoir jour par jour, le niveau d'eau qui baisse l'été, la profondeur maximale et l'arrêt à sec
- **Besoin** : « le réservoir se vide-t-il en juillet ? », « le niveau baisse de 10 m l'été », « la pompe tourne à sec ».
- **Preuves** : B1 C22, V337, V338, V340, V341 ; B7 U25 ; B5-es §4.1 (20 fils de pompage ; erreurs n° 1, 6, 9),
  grappes K43 (15 fils), K45 (5), K47 (11) ; B5-fr #10 ; B5-en P2.2 (pompage, 7 fils). URL :
  https://www.solarweb.net/forosolar/fotovoltaica-sistemas-aislados-la-red/25396-pozo.html ;
  https://www.solarweb.net/forosolar/fotovoltaica-sistemas-aislados-la-red/31579-instalacion-fotovoltaica-aislada-bombeo-riego.html ;
  https://www.solarweb.net/forosolar/fotovoltaica-sistemas-aislados-la-red/15166-bombeo-solar-directo-bomba-convencional.html
- **Qui le fait** : PVsyst pompage (réservoir avec pompe arrêtée quand plein, profondeur maximale = arrêt anti-marche à
  sec, niveau statique mensuel, eau manquante mensuelle).
- **Chez nous** : PARTIEL.
  - Couverture MENSUELLE et autonomie = volume ÷ besoin : `CP/volumes.py::couverture_besoin_eau`,
    `CP/conception.py::conception` (« aucun bassin dimensionné ») ; aucun bilan jour par jour.
  - Niveau statique UNIQUE : `CA/views/pompage.py::_NOMBRES_POMPAGE` (`niveau_statique_m`) ; HMT
    `CP/hydraulique.py::hmt_composantes` sans variation saisonnière.
  - Côté devis SEULEMENT : immersion minimale contre hauteur d'eau au-dessus de la pompe et diamètre contre tubage
    (`CP/selection.py::choisir_pompe`), plafond du débit d'exploitation du forage (`CP/volumes.py::production_mensuelle`,
    `plafond_m3h`, AGQ40), option de kit « Sonde de niveau (marche à sec) » et mention de la protection du variateur
    (`CP/kit.py::OPTIONS`, `composer_kit` ; champ de fiche `var_protection_marche_a_sec`). La porte du calepinage
    appelle l'ancienne `CP/selection.py::selection_pompe` et ne passe ni profondeur de calage, ni tubage, ni débit
    d'exploitation.
- **Plus petite version crédible** : trois saisies facultatives dans l'écran pompage (niveau statique d'été et d'hiver,
  profondeur de calage, débit d'exploitation du forage relevé à l'essai) ; le serveur fait le bilan jour par jour sur
  l'année type (production horaire déjà calculée × besoin × volume du réservoir) et rend : jours où l'eau manque, jours
  où le réservoir est plein (pompe à l'arrêt), part du besoin couverte ; alerte « ni sonde de niveau ni protection
  intégrée au variateur » quand aucune des deux n'est prévue. Rien d'inventé : sans réservoir déclaré ou sans besoin,
  le bilan est omis en le disant.
- **Simplicité** : un onglet Pompage existant (`FE/pompage/PompagePanel.jsx`) ; une carte de plus, calculée seule.
- **Tâches** (deux propriétaires) :
  1. [→ `docs/plans/PLAN_AUDIT_DEVIS.md`, propriétaire `devis`] Écrire `bilan_reservoir_journalier(...)` (pur) :
     remplissage, jours de manque, jours plein, % couvert ; fini quand un cas de 30 m³ de réservoir et un besoin
     constant donne les jours de manque attendus d'un tableur témoin — `CP/volumes.py`.
  2. [→ PLAN_AUDIT_DEVIS] HMT par mois depuis un niveau statique d'été/d'hiver SAISI ; fini quand la HMT de juillet
     reprend le niveau d'été — `CP/hydraulique.py`.
  3. [calepinage] Accepter `niveau_statique_ete_m`, `niveau_statique_hiver_m`, `profondeur_calage_m`,
     `diametre_tubage_mm`, `debit_exploitation_m3h` et appeler les contrôles d'immersion/tubage et le bilan ; fini quand
     le contrat `CA/contract_samples/calepinage_pompage.json` porte `bilan_reservoir` et `alertes[]` — `CA/views/pompage.py`
     (contrat d'abord).
  4. [calepinage] Carte « Réservoir jour par jour » + alertes sous le champ fautif ; fini quand la carte se lit sur
     l'exemple du contrat et disparaît sans réservoir — `FE/pompage/PompagePanel.jsx`.
  5. [→ PLAN_AUDIT_DEVIS] Avertir quand ni `sonde_niveau` n'est cochée ni `var_protection_marche_a_sec` vrai ; fini
     quand le kit d'un variateur sans protection publie l'alerte — `CP/kit.py::composer_kit`.
  Le document client agricole (`apps/ventes/quote_engine/agricole/**`, propriétaire `moteur`) n'est PAS touché ;
  l'imprimer serait une tâche de `docs/plans/PLAN_AUDIT_MOTEUR.md` à décider par Reda (règle #4).
- **Score** : 5 × 5 ÷ 2,5 = **10** — rang 4.

### CAP-D5-05 — Verdict batterie en trois mots, appuyé sur des faits de la série, et garde-fou d'autoconsommation
- **Besoin** : « la batterie est-elle trop grosse ? » (« réserve inutilisée 99,98 % du temps », B5-de passe 2) ;
  « avant d'ajouter une batterie, regarde si tu consommes déjà ta production ».
- **Preuves** : B2 #8 ; B6 R5, K36 ; B5-es #26 (5 fils) ; B5-de K43 (37 fils), §11 n° 11 ; B7 grappe 49. URL :
  https://www.plcforum.it/f/topic/338494-parere-su-preventivo-impianto-fotovoltaico-con-accumulo/ ;
  https://akkudoktor.net/t/anlagenplanung-eure-meinung/41846 ; https://www.getpylon.com
- **Qui le fait** : Pylon « Battery Recommender » (carte PV × batterie, cycles/jour) ; Aurora (autosuffisance).
- **Chez nous** : PARTIEL — le classement de capacités du stock existe et se voit (`CA/services/batterie.py::capacites_candidates`,
  bouton « Comparer des capacités du stock » de `FE/atelier/PanneauBatterie.jsx`) ; la série publie l'état de charge
  heure par heure (`CA/services/etapes/batterie.py::_publier`, colonne `batterie_soc_pct`) ; aucun mot de verdict,
  aucun fait « jamais pleine / vide avant l'aube », aucune phrase de garde-fou ; aucune grille PV × batterie.
- **Plus petite version crédible** : trois faits tirés de la série (jours où la batterie atteint 100 %, nuits où elle
  touche son plancher, part du surplus encore injecté) et le taux d'autoconsommation SANS batterie ; le mot « adaptée /
  trop petite / trop grande » ne s'affiche que si la société a saisi ses seuils avec leur source (sinon : les faits
  seuls, et la raison de l'absence du mot). Garde-fou : « votre production est déjà consommée à N % sans batterie » en
  tête de l'onglet. La grille PV × batterie vient ensuite, sur le balayage d'ACAL468.
- **Simplicité** : étape **Résultats** › Batterie ; trois lignes de texte, aucune courbe.
- **Tâches** (calepinage) :
  1. Publier les trois faits de SOC dans `resultat['batterie']['total']` ; fini quand l'exemple du contrat les porte —
     `CA/services/etapes/batterie.py::_publier`, contrat `calepinage_simulation.json`.
  2. Ajouter deux réglages société sourcés (seuils de verdict) au registre et le mot dérivé ; fini quand, sans réglage,
     le bloc publie `verdict: null` avec son motif — `CA/services/parametres_cles.py`, `CA/services/etapes/batterie.py`.
  3. Afficher faits + mot + garde-fou ; fini quand les trois lignes se lisent — `FE/atelier/PanneauBatterie.jsx`.
  4. Grille PV × batterie : `capacites_candidates` sur les kWc du balayage ; fini quand la grille rend une case par
     (kWc, capacité) — `CA/services/etapes/batterie.py` ; @after ACAL468.
- **Score** : 5 × 4 ÷ 2 = **10** — rang 5.

### CAP-D5-06 — Pompage : les chaînes du champ dessiné contrôlées contre la fenêtre DC du variateur, dans l'atelier
- **Besoin** : « 21 panneaux au lieu de 18-19 : Voc à froid au-dessus du bus du variateur » (B5-es, le « piège majeur ») ;
  « chaîne série < 300 V au jour le plus froid pour une SQF » (B5-en).
- **Preuves** : B5-es §4.1 (étape 6, erreur n° 4, souhait « avertissement tension »), K44 (10 fils) ; B5-en P2.2
  (SPT 443796 et 4 autres). URL :
  https://www.solarweb.net/forosolar/fotovoltaica-sistemas-aislados-la-red/32378-bombeo-solar-35cv-26kw-posibles-soluciones.html ;
  https://www.solarweb.net/forosolar/fotovoltaica-sistemas-aislados-la-red/30122-bombeo-solar-variador.html
- **Chez nous** : PARTIEL — côté devis, `CP/champ.py::_chaines_pour` (fenêtre `fenetre_admissible`, températures TMY,
  plages `var_voc_reco_min_v`/`var_voc_reco_max_v`) et `CP/champ.py::dimensionner_champ` ; côté calepinage, le pas
  électrique ne connaît pas les variateurs (grep `variateur` dans `CA/services/electrique.py` : 0) et
  `CA/views/pompage.py` ne contrôle pas les chaînes des modules posés. La compatibilité de sortie (pompe monophasée sur
  variateur triphasé) est PRÉSENTE : `CP/selection.py::variateurs_compatibles_plaque`.
- **Plus petite version crédible** : quand un calepinage de pompage a des modules posés et un variateur retenu, l'écran
  pompage dit « N modules en série : Voc à froid X V (T min du site), fenêtre du variateur A-B V : conforme / hors
  fenêtre » ; omis sans fiche complète, en le disant.
- **Simplicité** : étape **Électrique** pour un calepinage pompage ; une ligne verte/orange/rouge.
- **Tâches** :
  1. [→ PLAN_AUDIT_DEVIS] Exposer une fonction PUBLIQUE de contrôle de chaîne pour un variateur (aujourd'hui privée
     `_chaines_pour`) ; fini quand un appel avec 21 modules publie l'alerte hors fenêtre — `CP/champ.py`.
  2. [calepinage] Appeler ce contrôle sur les modules posés et publier `chaines_variateur` dans la réponse ; fini quand
     le contrat le porte — `CA/views/pompage.py`, `CA/contract_samples/calepinage_pompage.json`.
  3. [calepinage] Ligne de verdict dans l'écran ; fini quand elle se lit sur l'exemple — `FE/pompage/PompagePanel.jsx`.
- **Score** : 4 × 5 ÷ 2 = **10** — rang 6 (après CAP-D5-05 à égalité : moins de preuves récentes).

### CAP-D5-07 — Profil de distributeur : pièces exigées, limites, version du formulaire, « vérifié le »
- **Besoin** : « formulaire périmé = refus » ; « chaque gestionnaire veut ses pièces ».
- **Preuves** : B5-es #3 (21 fils + 3 éditeurs), K16 ; B5-de P9, K15, K47 (43 fils en passe 2 ; priorité relevée en
  §12) ; B7 U15 ; B5-nl cluster 3. URL : https://canalsolar.com.br/homologacao-energia-solar/ ;
  https://forum.valentin-software.com/topic/10077-kabel-schaltplan-vnb-w%C3%BCnsche/ ;
  https://akkudoktor.net/t/was-tun-mit-meiner-altanlage-worauf-auslegen/41395
- **Chez nous** : PARTIEL — `CA/models.py::GabaritDossierReglementaire` (pays, code, genre, `pieces_attendues` avec
  `source_reference`, `champs`, `version`) et `CA/services/reglementaire.py::dossiers_du_calepinage` ; aucune clé
  distributeur, aucune limite, aucune date de vérification. Le lead porte déjà le distributeur (12 SRM) :
  `backend/django_core/apps/crm/models.py` (`Lead.distributeur`, `Distributeur`).
- **Plus petite version crédible** : un gabarit peut viser un distributeur (vide = tous) et porte « vérifié le » et des
  limites saisies `{code, valeur, unité, source}` ; le dossier du calepinage choisit le gabarit du distributeur du lead ;
  « vérifié il y a plus de N jours » s'affiche quand N est réglé par la société. Aucune règle marocaine inventée.
- **Simplicité** : étape **Documents** ; rien à faire tant que la société n'a rien saisi.
- **Tâches** (calepinage) :
  1. Ajouter `distributeur`, `verifie_le`, `limites` au gabarit (migration additive) ; fini quand un gabarit SRM
     Casablanca se crée et se relit — `CA/models.py`, migration du module.
  2. Choisir le gabarit par le distributeur du lead lu via `apps.crm.selectors` ; fini quand deux gabarits (SRM Souss,
     tous) donnent le bon dossier — `CA/services/reglementaire.py::dossiers_du_calepinage`.
  3. Saisir ces champs dans l'écran des gabarits ; fini quand ils survivent au rechargement — `FE/reglages/ReglagesGabarits.jsx`.
  4. Comparer le plafond d'injection saisi aux limites du profil ; fini quand un écart publie un avertissement nommé —
     `CA/services/raccordement.py`.
  Voisin : CAP-D3-18 (modèle de SCHÉMA par distributeur) — ici, seulement pièces et limites.
- **Score** : 5 × 4 ÷ 2 = **10** — rang 7.

### CAP-D5-08 — Limites du point de livraison : en ampères par phase, par plage horaire, et plafond de soutirage
- **Besoin** : « le gestionnaire impose 16 h-18 h » ; « ma limite est en A par phase » ; « je ne dois pas dépasser ma
  puissance souscrite en soutirage ».
- **Preuves** : B5-en #10 (3 fils), #18 (3 fils) ; B4 #9 ; B7 U18 (6 lignes, 5 sources), grappe 30 ; B5-de K47 (passe 2 :
  « 600 W de limite », règle des 70 %). URL : https://forum.valentin-software.com/topic/9962-timed-export-limitation-windows/ ;
  https://forum.valentin-software.com/topic/2466-whats-the-best-way-to-limitdown-regulate-the-current-a-output-from-the-inverter-in-pvsol/ ;
  https://forum.valentin-software.com/topic/10826-anti-reverse-feed-and-limited-grid-connection/
- **Chez nous** : PARTIEL — un plafond unique en kW (zéro admis) avec justification obligatoire :
  `CA/services/autoconsommation.py::plafond_injection`, `CA/services/raccordement.py::CHAMPS_SAISIE`
  (`plafond_injection_kw`), visible dans `FE/electrique/Raccordement.jsx` ; aucune unité A, aucune plage, aucun plafond
  de soutirage (le seuil d'effacement de la batterie n'est pas une limite du réseau).
- **Plus petite version crédible** : le plafond se saisit en kW ou en A (+ phases ; la tension et le cos φ sont ceux
  déjà saisis, la conversion est publiée) ; jusqu'à 3 plages horaires avec leur plafond ; un plafond de soutirage kW
  saisi → « N heures au-dessus » et, si une batterie en effacement existe, il devient son seuil (dit).
- **Simplicité** : étape **Électrique** › Raccordement, replié ; utile seulement quand le distributeur l'impose.
- **Tâches** (calepinage) :
  1. Admettre `plafond_injection_a` et le convertir ; fini quand 16 A tri à 400 V cos φ 1 publie le kW converti —
     `CA/services/raccordement.py`.
  2. Plages horaires de plafond appliquées heure par heure ; fini quand une plage 16-18 h écrête seulement ces heures —
     `CA/services/autoconsommation.py::plafond_injection`.
  3. Plafond de soutirage et son verdict ; fini quand une charge de 9 kW sur 6 kVA souscrits publie les heures
     au-dessus — `CA/services/raccordement.py`, `CA/services/autoconsommation.py`.
  4. Champs à l'écran ; fini quand ils survivent au rechargement — `FE/electrique/Raccordement.jsx`.
- **Score** : 4 × 4 ÷ 2 = **8** — rang 8.

### CAP-D5-09 — Consommation : compléter les mois qui manquent depuis quelques factures, et lire une photo de facture
- **Besoin** : « le client n'a que 3 factures », « il m'envoie une photo de sa facture ».
- **Preuves** : B6 R8 / K42 (7 outils : Scanifly 2026-11-02, OpenSolar 3.3, Pylon) ; B3 N17 (Reonic) ; B1 S017. Pas de
  fil de forum : preuve « notes de version ».
- **Chez nous** : PARTIEL — `CA/services/consommation.py::_interpoler_factures` ne connaît que DEUX factures
  (hiver/été, port de `solar.js`) ; un mois peut être corrigé (`saisies`, source `saisi`), mais 3 à 11 mois connus ne
  servent pas à estimer les autres ; `proposer_consommation` (source `factures`) n'accepte que `hiver_mad`/`ete_mad`.
  La photo de facture est déjà lue par l'OCR **côté CRM seulement** : `apps/crm/intake_photo.py::_run_capture_ocr`
  (QK6, drapeau `CRM_CAPTURE_OCR_ENABLED` + clé Zhipu ; remplit `conso_mensuelle_kwh` et `tranche_onee` du lead à
  partir d'une photo du webhook public) — aucun lien avec le calepinage.
- **Plus petite version crédible** : la source « factures » accepte 1 à 12 mois (MAD ou kWh) ; les mois vides prennent
  la FORME saisonnière du profil type de la société (ou la règle des deux factures si c'est tout ce qu'on a), marqués
  « estimé » et dessinés en pointillé ; jamais présentés comme mesurés. Photo : bouton « Lire une photo de facture »
  qui propose (mois, kWh) à confirmer ligne par ligne ; caché sans clé IA.
- **Simplicité** : étape **Toit** (consommation) ; essentiel.
- **Tâches** :
  1. [calepinage] Source `factures.mois[]` + estimation par la forme du profil type, source `estime` ; fini quand
     3 factures donnent 12 mois dont 9 marqués `estime` — `CA/services/consommation.py`, `CA/views/consommation.py`
     (contrat `calepinage_consommation_proposee.json` d'abord).
  2. [calepinage] Grille de 12 mois dans le panneau consommation avec « estimé » ; fini quand la grille relit la
     proposition — `RP/consumption.ts`.
  3. [→ `docs/plans/PLAN_AUDIT_LEAD.md`, propriétaire `lead` de `apps/crm/intake_photo.py`, + ajout append-only à
     `apps/crm/services.py`] Un service qui rend une PROPOSITION `[{mois, kwh}]` depuis une photo, sans écrire le lead ;
     fini quand, OCR coupé, il rend « indisponible » nommé.
  4. [calepinage] Bouton qui appelle ce service et préremplit la grille à confirmer ; @after tâche 3.
- **Score** : 3 × 4 ÷ 2 = **6** — rang 9.

### CAP-D5-10 — Secours : coupures déclarées, heures tenues par appareil secouru, et ce qui reste alimenté
- **Besoin** : « combien d'heures tient le frigo et la pompe pendant une coupure ? », « on a 3 coupures de 4 h par mois ».
- **Preuves** : B2 #8 ; B1 C26, V354 ; B5-de K53 (22 fils, nouveau en passe 2), P21 ; B5-en P2.2 (réseau faible, Victron
  4 fils, « batterie de 28,5 à 63,5 kWh après les coupures ») ; B7 grappe 35. URL :
  https://forum.valentin-software.com/topic/10489-backup-box-notstrom-gateway/ ;
  https://www.energiesparhaus.at/forum-30kw-hybrid-wechselrichter-batteriespeicher-zum-bestpreis/84274_2
- **Chez nous** : PARTIEL — stratégie `backup` qui garde une réserve (`CA/services/batterie.py::simuler_batterie`,
  plancher = réserve) ; réserve déduite des appareils pour une durée (`reserve_depuis_appareils`, sans écran : voir
  CAP-D5-01) ; aucune série de coupures, aucune heure tenue par appareil.
- **Plus petite version crédible** : « combien de coupures par an, de combien d'heures, vers quelle heure ? » (saisi,
  jamais de défaut) ; le serveur coupe le réseau sur ces heures de l'année type et publie l'énergie non fournie et les
  heures tenues ; par appareil secouru : heures = énergie de la réserve ÷ puissance continue (dérivé, traçable).
- **Simplicité** : étape **Résultats** › Batterie, sous « Secours » ; une question en langage clair.
- **Tâches** (calepinage) : 1. coupures déclarées dans la stratégie `backup` (`CA/services/batterie.py`,
  `CA/services/etapes/batterie.py`) ; fini quand 12 coupures de 4 h publient `energie_non_fournie_kwh` ;
  2. heures tenues par appareil ; fini quand deux appareils publient deux durées ; 3. écran
  (`FE/atelier/PanneauBatterie.jsx`). @after CAP-D5-01 tâche 1. La branche de secours du schéma unifilaire = CAP-D3-15.
- **Score** : 4 × 4 ÷ 2 = **8** — rang 10 (dépend de CAP-D5-01).

### CAP-D5-11 — Hors réseau : groupe électrogène d'appoint et banque calculée sur le mois le plus défavorable
- **Besoin** : « l'onduleur pour les pointes, le groupe pour la queue » ; « 12 kWc / 38 kWh demandent quand même le
  groupe en novembre ».
- **Preuves** : B1 C14, V110, V345, S089, S321, S328 ; B6 R32, K67 (7 outils) ; B5-en #15 (6 fils), P2.2. URL :
  https://www.solarpaneltalk.com/forum/off-grid-solar/off-grid-solar-panel-systems/14114-sizing-off-grid-systems-and-using-gen-support ;
  https://community.victronenergy.com/t/anderung-der-einbindung-eines-230v-generators-in-ein-standalone-3-phasen-system/65241
- **Chez nous** : PARTIEL/ABSENT — `CA/services/hors_reseau.py` le dit lui-même (`MENTION_ENTRETIEN_SANS_SOURCE_AC` :
  « aucune source de recharge côté alternatif (groupe électrogène) n'est modélisée ») ; le pire mois est publié et
  visible (`mois_le_plus_defavorable`, carte « Pire mois » de `FE/atelier/PanneauBatterie.jsx`) mais la banque se
  calcule sur la consommation MOYENNE de l'année (`CA/services/etapes/hors_reseau.py`, `conso_journaliere = total ÷
  jours`).
- **Plus petite version crédible** : un interrupteur « Il y a un groupe sur le site » : puissance, SOC de démarrage et
  d'arrêt, heures max par jour (tout saisi) ; le serveur fait démarrer le groupe sous le seuil et publie heures de
  marche et énergie fournie par mois (aucun litre, aucun prix). Option « banque calculée sur le pire mois » publiée à
  côté de la banque moyenne. Le courant de démarrage des moteurs n'est pas modélisé (aucun champ de fiche) et c'est dit.
- **Simplicité** : n'apparaît qu'en mode hors réseau.
- **Tâches** (calepinage) : 1. clé `groupe` dans `CLES_HORS_RESEAU` + validation (`CA/services/electrique.py`) ;
  2. simulation du groupe (`CA/services/hors_reseau.py::_simuler_hors_reseau`) ; fini quand un groupe de 5 kW à
  SOC 20 → 80 % publie des heures de marche par mois et une défaillance réduite ; 3. banque « pire mois »
  (`CA/services/etapes/hors_reseau.py`) ; 4. champs à l'écran.
- **Score** : 4 × 3 ÷ 2 = **6** — rang 11 (peu d'autonome au Maroc selon B1 V111, mais réseau faible fréquent).

### CAP-D5-12 — Extension d'une installation existante : l'énergie de l'existant comptée, son âge réel, l'avant/après
- **Besoin** : « j'ajoute 8 modules à mes 12 de 2019 » ; « ne chiffrer que l'extension » ; « ajouter une batterie à
  une installation existante ».
- **Preuves** : B4 #7 ; B5-de P3, K50 (13 fils p1+p2), K35 ; B5-en #3 (4 fils) ; B5-es #9 (14 fils), #16, K19 (14) ;
  B6 R31, K93 ; B7 U21. URL : https://www.energiesparhaus.at/forum-solaredge-anlage-erweitern-upgraden-wie/84984 ;
  https://www.photovoltaikforum.com/thread/154205-erweiterung-einer-9-92kwp-ost-west-anlage-auf-maximale-belegung/ ;
  https://forum.valentin-software.com/topic/10736-pvsol-for-retrofit-string-redesign-of-existing-rooftop-pv-system/
- **Chez nous** : ABSENT — aucun drapeau « existant » ni année de mise en service sur un pan (grep `existant`,
  `mise_en_service` dans `CA/services` et `RP` : aucun usage dans ce sens).
- **Plus petite version crédible** : case « déjà posé » + année de mise en service par pan ; la production de ce pan
  compte, sa dégradation part de son âge ; le résultat publie « existant / ajouté / total » ; la batterie et
  l'autoconsommation voient la production totale.
- **Simplicité** : étape **Toit** ; une case cachée tant qu'elle n'est pas cochée.
- **Tâches** : 1. [calepinage] contrat `roof_layout_v2` : `zones[].existant {annee_mise_en_service}` (contrat d'abord) ;
  2. [calepinage] vieillissement décalé de l'âge pour ces pans (`CA/services/etapes/vieillissement.py`, @after
  CAP-D4-03) ; 3. [calepinage] répartition existant/ajouté dans `resultat['production']` ; 4. case dans l'atelier
  (`RP/…`, propriétaire `calepinage`). **Hors domaine** : exclusion de la nomenclature et du plan de pose (D2/D3),
  mélange de modules sur une chaîne et entrée MPPT réservée (CAP-D3-23).
- **Score** : 5 × 4 ÷ 3 = **6,7** — rang 12.

### CAP-D5-13 — Consommation et eau mesurées contre simulées, pour une installation livrée
- **Besoin** : « le client dit qu'il consomme encore autant » ; « la pompe sort-elle les m³ promis ? ».
- **Preuves** : B1 C08, V358, V359 ; B5-fr #2 (7 sources) ; B7 U5 (27 lignes), grappe 42 ; B5-de K14. URL :
  https://forum-photovoltaique.fr/viewtopic.php?t=11987 ; https://github.com/NatLabRockies/SAM/issues/1775
- **Chez nous** : PARTIEL — le SAV tient déjà des index cumulés kWh et m³ par équipement :
  `backend/django_core/apps/sav/models.py::ReleveCompteurEquipement` (`Type.KWH`, `Type.M3`, AGR615) ; l'as-built
  compare le POSÉ au prévu (`CA/services/asbuilt.py::ecarts_du_calepinage`) ; rien ne compare l'énergie ou l'eau.
- **Plus petite version crédible** : ici, la part CONSOMMATION et EAU (la production mesurée = CAP-D4-17) : 12 valeurs
  mensuelles (tapées, ou différences d'index SAV) face à la consommation simulée et aux m³ simulés ; écart en %. Sans
  engagement de garantie.
- **Simplicité** : onglet « Pose réelle » élargi ; réservé SAV/gérant, jamais dans le flux commercial.
- **Tâches** : 1. [→ `docs/plans/PLAN_AUDIT_SAV.md`, propriétaire `sav`] sélecteur
  `volumes_mensuels_mesures(company, equipement_ids)` depuis les index ; 2. [calepinage] comparaison
  (`CA/services/asbuilt.py`) ; 3. [calepinage] tableau dans `FE/atelier/PoseReelle.jsx`. @after CAP-D4-17 (même écran).
- **Score** : 4 × 3 ÷ 2 = **6** — rang 13.

### CAP-D5-14 — Rapport d'étude interne : pages hors réseau, pompage et hypothèses de consommation
- **Besoin** : « hypothèses prises pour le client (consommation) et date de l'offre » (B5-de §11 n° 17).
- **Preuves** : B5-de §11 n° 11 et 17 ; B1 §6.2 (rapport PV*SOL de 37 pages lu) ; B7 grappe 55. URL :
  https://www.spiritenergy.co.uk/hubfs/Solar%20Consultation%20Advanced%20Modelling%20-%20PVSol.pdf
- **Chez nous** : PARTIEL — `CA/services/rapport/systeme.py::_bloc_batterie` imprime seulement groupes, packs,
  capacité, stratégie, cycles/an ; aucune section hors réseau, pompage ni consommation (fichiers de `CA/services/rapport/` :
  systeme, production, pertes, ombrage, electrique, site, nomenclature, preuve, annexe_hypotheses).
- **Plus petite version crédible** : trois sections nourries par ce qui est servi : « Consommation et hypothèses »
  (méthode, origine, `saisi_le`, charges ajoutées), « Hors réseau » (défaillance par mois, pire mois, banque), « Pompage »
  (HMT et composantes, m³ par mois, couverture, bilan réservoir s'il existe). La section batterie/autoconsommation est
  CAP-D4-18. Le PDF client `/proposal` ne change pas.
- **Tâches** (calepinage) : une tâche par section dans `CA/services/rapport/` + l'entrée au contrat de sections ; fini
  quand `rapport-etude.pdf` porte la section et l'omet sans données.
- **Score** : 3 × 3 ÷ 2 = **4,5** — rang 14.

### CAP-D5-15 — Orientation du champ choisie pour le mois critique (pompage et hors réseau)
- **Besoin** : « pour que l'eau ne manque pas en juillet : 22° plutôt que 29° » ; « dimensionner sur le pire mois ».
- **Preuves** : B1 C23, V344 ; B5-es §4.1 étape 2 et erreur n° 9 ; B5-en P2.2 (7 fils, mois le plus pauvre) ;
  B5-fr #15 (inclinaison saisonnière). URL :
  https://www.solarweb.net/forosolar/fotovoltaica-sistemas-aislados-la-red/15166-bombeo-solar-directo-bomba-convencional.html
- **Chez nous** : ABSENT — le mois critique est connu (`CP/volumes.py::mois_critique`,
  `CA/services/hors_reseau.py`, `mois_le_plus_defavorable`) mais le balayage planifié (ACAL468/ACAL469) vise le
  rendement ANNUEL.
- **Plus petite version crédible** : un critère « mois critique » dans le balayage ; proposition « X° pour le mois
  critique, Y° pour l'année » et l'écart en kWh de ce mois.
- **Tâches** : 1. [calepinage] critère `mois_critique` dans la demande du balayage (contrat `calepinage_balayage.json`
  d'ACAL388) ; 2. carte dans l'onglet « Optimiser ». @after ACAL468, ACAL469.
- **Score** : 4 × 4 ÷ 2 = **8** mais bloqué derrière deux tâches planifiées — rang 15.

### CAP-D5-16 — Cible d'autoconsommation ou de couverture → nombre de panneaux
- **Besoin** : « viser 80 % d'autoconsommation » ; « couvrir 70 % de ma consommation ».
- **Preuves** : B5-en #8 ; B7 U16 (10 lignes, 23 votes, 3 sources), grappe 29 ; B1 S046. URL :
  https://forum.valentin-software.com/topic/10602-system-sizing-and-self-consumption/ ;
  https://electronics.stackexchange.com/questions/38380/how-do-i-calculate-how-much-solar-power-i-need-for-a-system
- **Chez nous** : DÉJÀ PLANIFIÉ en partie — ACAL470 (cible de PRODUCTION en kWh/an) ; la cible d'autoconsommation ou de
  couverture n'est dans aucune tâche (le bilan horaire existe : `CA/services/autoconsommation.py::bilan_autoconsommation`).
- **Plus petite version crédible** : à côté de « Production visée », « Couverture visée (%) » : le balayage sur le
  nombre de modules rend le plus petit nombre qui l'atteint, avec l'hypothèse de charge dite.
- **Tâches** : 1. [calepinage] extension d'ACAL470 côté serveur (balayage du nombre de modules sur le bilan horaire) ;
  @after ACAL470, ACAL468.
- **Score** : 4 × 3 ÷ 2 = **6** — rang 16.

### CAP-D5-17 — Pompage : « réservoir + pompe plus petite » comparé au pompage direct
- **Besoin** : « 1 200 m³/jour en direct, c'est excessif » ; « un réservoir réduit la puissance de moitié ».
- **Preuves** : B5-es #22 (4 fils), erreur n° 10. URL : https://www.solarweb.net/forosolar/fotovoltaica-sistemas-aislados-la-red/28494-bombeo-solar.html
- **Chez nous** : ABSENT — `CP/conception.py::conception` calcule une seule configuration.
- **Plus petite version crédible** : deux cartes côte à côte (direct / avec le réservoir déclaré), kWc nécessaires et
  jours de manque pour chacune ; aucun prix.
- **Tâches** : 1. [→ PLAN_AUDIT_DEVIS] variante « réservoir » dans `CP/conception.py` (pompage étalé sur la journée) ;
  2. [calepinage] carte dans `FE/pompage/PompagePanel.jsx` via `CA/views/pompage.py`. @after CAP-D5-04 tâche 1.
- **Score** : 3 × 4 ÷ 2 = **6** — rang 17.

### CAP-D5-18 — Pompage : appoint réseau ou groupe sur le bus DC du variateur, et un variateur pour plusieurs pompes ou secteurs
- **Besoin** : « remplacer le groupe par des panneaux sans abîmer les condensateurs » ; « le variateur de 5,5 kW tient-il
  quatre pompes ? » ; « 3-4 secteurs sur un cycle de 12 jours ».
- **Preuves** : B5-es #20 (3 fils), #21 (3 fils), K44 ; B5-en P2.2 (pompe de secours sur l'alternatif). URL :
  https://www.solarweb.net/forosolar/fotovoltaica-sistemas-aislados-la-red/29878-bombeo-sustituir-grupo-electrogeno-placas-parece-ser-complicadisimo.html ;
  https://www.solarweb.net/forosolar/fotovoltaica-sistemas-aislados-la-red/32378-bombeo-solar-35cv-26kw-posibles-soluciones.html
- **Chez nous** : ABSENT — aucun mode hybride ni liste de pompes par variateur dans `CP/` (grep `hybride`, `secteur`,
  `groupe électrogène` : 0 au sens pompage).
- **Plus petite version crédible** : CONTRÔLE de conception seulement (la composition du kit ne change pas : CLAUDE.md
  « pompage = aucun onduleur, aucune batterie ») : appoint déclaré → Vmp du champ au-dessus de la tension redressée lue
  sur la fiche du variateur (saisie), Voc à froid sous la limite du bus ; plusieurs pompes → somme des kW de plaque contre
  la plaque du variateur et calendrier de secteurs sur `couverture_besoin_eau`. Sans valeur de fiche : omis, nommé.
- **Tâches** : 1. [→ PLAN_AUDIT_DEVIS] mode « appoint » dans `CP/champ.py` ; 2. [→ PLAN_AUDIT_DEVIS] liste de pompes
  par variateur dans `CP/conception.py` ; 3. [calepinage] champs et verdicts dans `CA/views/pompage.py` et
  `FE/pompage/PompagePanel.jsx`. Un champ de fiche « tension DC redressée admise » irait dans
  `apps/stock/models_fiche_technique.py` (propriétaire `calepinage`, vérifié) mais sa MIGRATION dans
  `apps/stock/migrations/` (propriétaire `stock`, surface append-only) et son écran
  `frontend/src/features/stock/FicheTechnique.jsx` (propriétaire `stock`, `docs/plans/PLAN_AUDIT_STOCK.md`).
- **Score** : 3 × 4 ÷ 3 = **4** — rang 18 (fils anciens, 2007-2014).

### CAP-D5-19 — Énergie réactive (kVArh) et cos φ par mois
- **Besoin** : « la facture réactive du site industriel ».
- **Preuves** : B1 C24, V349 ; B6 K84 (4 outils). Aucun fil de forum.
- **Chez nous** : PARTIEL — cos φ imposé et repli société (`CA/services/raccordement.py::_cos_phi_saisi`,
  `_cos_phi_societe`) ; aucun kVArh.
- **Plus petite version crédible** : kVAh et kVArh mensuels dérivés de l'énergie AC injectée et du cos φ saisi, sans
  prix, avec « à vérifier avec le distributeur » (CIQM4 attend la position écrite ONEE/SRM).
- **Tâches** : 1. [calepinage] publication mensuelle dans le bloc raccordement ; 2. ligne à l'écran.
- **Score** : 2 × 3 ÷ 1 = **6** — rang 19 (preuve « notes de version » seule).

### CAP-D5-20 — Batterie hors de sa plage de température au site
- **Besoin** : « LFP sous 0 °C : capacité réduite, charge coupée » ; chaleur du désert.
- **Preuves** : B5-en #21 (1 fil, preuve mince), P2.2 (chaleur, Victron). URL :
  https://community.victronenergy.com/t/expanding-a-12-8v-lifepo4-solar-system-using-a-dc-dc-charger/65088
- **Chez nous** : ABSENT comme contrôle, données PRÉSENTES — fiche `bat_temp_min_c`, `bat_temp_max_c`
  (`apps/stock/models_fiche_technique.py`, propriétaire `calepinage`) relues par `CA/services/equipements.py` ;
  températures du site TMY déjà servies au pas électrique (`CA/services/electrique.py`, `temp_min_c`/`temp_max_c`).
- **Plus petite version crédible** : un avertissement « T min du site X °C sous la plage publiée de la batterie (Y °C) »
  (et de même pour T max) ; AUCUNE courbe de capacité inventée — omis sans fiche.
- **Tâches** : 1. [calepinage] avertissement dans `CA/services/etapes/batterie.py` ; fini quand une fiche à 0 °C et un
  TMY à −3 °C le publient.
- **Score** : 1,5 × 3 ÷ 1 = **4,5** — rang 20 (effort S, preuve mince).

### CAP-D5-21 — Gabarits de profils de consommation nommés, vides, à remplir par la société
- **Besoin** : « clim d'été », « télétravail », « retraités », « Ramadan » prêts à choisir.
- **Preuves** : B6 R22 (4 outils : PV*SOL 2026 R1, archelios, SolarEdge, PVsyst) ; B1 S310.
- **Chez nous** : PARTIEL — profils société éditables (`CA/services/profils_types.py::enregistrer_profils`, écran
  `FE/Bibliotheque.jsx`), familles et type de jour (CALX258), décalage Ramadan (`CA/services/consommation.py::_appliquer_ramadan`) ;
  aucun gabarit NOMMÉ proposé ; les replis sont des courbes de `ventes` étiquetées « hypothèse interne »
  (`CA/services/profils_types.py::REPLIS`, `MENTION_REPLI`).
- **Plus petite version crédible** : 4-6 noms de gabarits listés VIDES dans la bibliothèque, à remplir avec leur
  source ; aucune valeur livrée.
- **Tâches** : 1. [calepinage] liste de gabarits nommés vides dans `FE/Bibliotheque.jsx` + validation serveur.
- **Score** : 2 × 2 ÷ 1 = **4** — rang 21.

### CAP-D5-22 — Règles de batterie par saison (une stratégie par mois)
- **Besoin** : « décharger vers le réseau l'hiver seulement ».
- **Preuves** : B5-en #11 (2 fils, en partie fondés sur un tarif spot — exclu) ; B1 V353.
- **Chez nous** : PARTIEL — la grille horaire de la société peut varier par saison (`CA/services/batterie.py::_grille_tou`,
  `{saison: [24 libellés]}`, CALX275) ; une seule stratégie pour toute l'année (`simuler_batterie`, `strategie`).
- **Plus petite version crédible** : une stratégie par mois (sans tarif) dans la déclaration.
- **Tâches** : 1. [calepinage] `strategie_par_mois` dans `CA/services/batterie.py` ; @after CAP-D5-01 tâche 1.
- **Score** : 1 × 2 ÷ 2 = **1** — rang 22 (gardée parce qu'elle a une preuve et un manque prouvé ; à ne construire
  qu'à la demande).

---

## C. Table de synthèse

| Rang | CAP | Titre | Verdict | Tâches | Effort |
|---|---|---|---|---|---|
| 1 | CAP-D5-01 | Batterie « mode expert » : saisir et voir ce que le serveur calcule | PRÉSENT SANS ÉCRAN (+ refus à l'écriture) | 5 | M |
| 2 | CAP-D5-02 | Charges VE / PAC / clim du modèle serveur | PRÉSENT SANS ÉCRAN | 3 | M |
| 3 | CAP-D5-03 | Loi 82-21 : régime et part injectée vs plafond 20 % | PRÉSENT SANS ÉCRAN (dans le calepinage) | 3 | S-M |
| 4 | CAP-D5-04 | Pompage : réservoir jour par jour, niveau d'été, profondeur, arrêt à sec | PARTIEL | 5 (3 devis, 2 calepinage) | M-L |
| 5 | CAP-D5-05 | Verdict batterie en 3 mots + garde-fou d'autoconsommation | PARTIEL | 4 | M |
| 6 | CAP-D5-06 | Pompage : chaînes du champ contre la fenêtre du variateur | PARTIEL (présent côté devis) | 3 (1 devis) | M |
| 7 | CAP-D5-07 | Profil de distributeur : pièces, limites, « vérifié le » | PARTIEL | 4 | M |
| 8 | CAP-D5-08 | Limites du point de livraison : A/phase, plages, soutirage | PARTIEL | 4 | M |
| 9 | CAP-D5-09 | Mois de consommation manquants + photo de facture | PARTIEL | 4 (1 lead) | M |
| 10 | CAP-D5-10 | Secours : coupures déclarées, heures par appareil | PARTIEL | 3 | M |
| 11 | CAP-D5-11 | Hors réseau : groupe électrogène + banque du pire mois | ABSENT (groupe) / PARTIEL (pire mois) | 4 | M |
| 12 | CAP-D5-12 | Extension d'une installation existante (énergie) | ABSENT | 4 | L |
| 13 | CAP-D5-13 | Consommation et eau mesurées contre simulées | PARTIEL (données SAV) | 3 (1 sav) | M |
| 14 | CAP-D5-14 | Rapport interne : hors réseau, pompage, hypothèses de conso | PARTIEL | 3 | M |
| 15 | CAP-D5-15 | Orientation pour le mois critique | ABSENT (après ACAL468/469) | 2 | M |
| 16 | CAP-D5-16 | Cible d'autoconsommation → nombre de panneaux | DÉJÀ PLANIFIÉ en partie (ACAL470 = kWh seulement) | 1 | M |
| 17 | CAP-D5-17 | Réservoir + petite pompe contre pompage direct | ABSENT | 2 (1 devis) | M |
| 18 | CAP-D5-18 | Pompage : appoint réseau/groupe, plusieurs pompes/secteurs | ABSENT | 3 (2 devis) | L |
| 19 | CAP-D5-19 | Énergie réactive et cos φ par mois | PARTIEL | 2 | S |
| 20 | CAP-D5-20 | Batterie hors de sa plage de température au site | ABSENT (données présentes) | 1 | S |
| 21 | CAP-D5-21 | Gabarits de profils nommés, vides | PARTIEL | 1 | S |
| 22 | CAP-D5-22 | Batterie : stratégie par saison | PARTIEL | 1 | M |

22 fiches, 65 tâches (dont 7 routées vers PLAN_AUDIT_DEVIS, 1 vers PLAN_AUDIT_LEAD, 1 vers PLAN_AUDIT_SAV ; les
autres sont du propriétaire `calepinage`).

---

## D. Routage vers les plans d'autres propriétaires

| Ce qui part ailleurs | Fichier | Propriétaire (vérifié) | Plan |
|---|---|---|---|
| Bilan réservoir journalier, HMT par mois (niveau saisonnier), alerte « ni sonde ni protection », variante réservoir, mode appoint, plusieurs pompes, fonction publique de contrôle de chaîne | `core/pompage/volumes.py`, `hydraulique.py`, `kit.py`, `conception.py`, `champ.py` | `devis` | `docs/plans/PLAN_AUDIT_DEVIS.md` |
| Toute impression côté client (réservoir, jours de manque) dans le document agricole | `apps/ventes/quote_engine/agricole/**` | `moteur` | `docs/plans/PLAN_AUDIT_MOTEUR.md` — NON proposé (règle #4 ; à décider par Reda) |
| Lecture d'une photo de facture → mois proposés | `apps/crm/intake_photo.py` (+ ajout à `apps/crm/services.py`, surface append-only `crm`) | `lead` | `docs/plans/PLAN_AUDIT_LEAD.md` |
| Volumes mensuels mesurés depuis les index | `apps/sav/selectors.py` | `sav` | `docs/plans/PLAN_AUDIT_SAV.md` |
| Fiches techniques (stock) | `apps/stock/models_fiche_technique.py`, `serializers_fiche_technique.py`, `selectors_fiche_technique.py` | **`calepinage`** (pas `stock`) | reste au plan calepinage ; MAIS la migration (`apps/stock/migrations/`, `stock`, append-only) et l'écran `frontend/src/features/stock/FicheTechnique.jsx` (`stock`) → `docs/plans/PLAN_AUDIT_STOCK.md` |
| Régime 82-21 (lecture seule) | `core/reglementaire/regime_8221.py` | `securite` | rien à modifier : le calepinage LIT ce module (couche fondation) |
| Plafond 20 % (lecture seule) | `apps/ventes/quote_engine/constants_82_21.py` | `moteur` | rien à modifier : lu par `apps/ventes/selectors_calepinage.py` (propriétaire `calepinage`) |
| Appareil plat « ev » de l'atelier (optionnel) | `apps/web/src/lib/applianceConsumption.ts` | `web` | `docs/WEB_PLAN.md` — seulement si Reda veut une seule porte |

---

## E. Tableau de correspondance (id d'origine → sort)

| Ids d'origine | Sort |
|---|---|
| B2 #8 ; B1 C25, V354, S324, S325 ; B6 R5 (cycles/jour), K36, K37 ; B5-de K43, K53, §11 n° 11 ; B7 g.21, 35, 49 | CAP-D5-01, CAP-D5-05, CAP-D5-10 |
| B1 S023, S087, S088 (part PAC), S314, S316 (part PAC) ; B6 K39, K40, K66 ; B5-de K38, §11 n° 17 ; B7 g.36 | CAP-D5-02 (ballon/ECS : écarté) |
| B5-fr §3 (82-21) ; B5-de P16, K47, §11 n° 12 ; B5-es K16 | CAP-D5-03 (part électrique de P16 → CAP-D3-25) |
| B1 C22, V337, V338, V340, V341, V342 (contrôleur) ; B7 U25, g.47 ; B5-es §4.1 étapes 1-3, 7, erreurs 1, 6, 9, #23, K45, K47 ; B5-fr #10 ; B6 K44 | CAP-D5-04 |
| B5-es #26 | CAP-D5-05 |
| B5-es §4.1 étape 6, erreur 4, souhait « avertissement tension », K44 ; B5-en P2.2 (pompage) | CAP-D5-06 |
| B5-es #3 ; B5-de P9, K15 (part pièces/limites) ; B7 U15 | CAP-D5-07 (part schéma → CAP-D3-18) |
| B4 #9 ; B5-en #10, #18 ; B7 U18, g.30 ; B1 V352, V353 (plages) | CAP-D5-08 |
| B6 R8, K42 ; B3 N17 ; B1 S017 (mois manquants) | CAP-D5-09 |
| B1 C26 ; B5-de P21 (liste de ce qui reste alimenté) ; B5-en P2.2 (réseau faible, batterie agrandie) | CAP-D5-10 (schéma de secours → CAP-D3-15) |
| B1 C14, V110, V345, V346, V347, S089, S090, S321, S326, S327, S328 ; B6 R32, K67 ; B5-en #15, P2.2 (pire mois) | CAP-D5-11 |
| B4 #7 ; B5-de P3, K50, K35 ; B5-en #3 ; B5-es #9, #16, K19 ; B6 R31, K93 ; B7 U21 | CAP-D5-12 (BOM/pose → D2/D3 ; MPPT réservé → CAP-D3-23) |
| B1 C08, V358, V359 ; B5-fr #2 ; B7 U5, g.42 | CAP-D5-13 (production mesurée → CAP-D4-17) |
| B5-de §11 n° 11 et 17 ; B1 §6 | CAP-D5-14 (batterie/autoconso du rapport → CAP-D4-18) |
| B1 C23, V344 ; B5-fr #15 | CAP-D5-15 |
| B5-en #8 ; B7 U16, g.29 ; B1 S046 | CAP-D5-16 (ACAL470 couvre la cible kWh) |
| B5-es #22, erreur 10 | CAP-D5-17 |
| B5-es #20, #21 | CAP-D5-18 |
| B1 C24, V349 ; B6 K84 | CAP-D5-19 |
| B5-en #21 ; B1 S312 (part froid) | CAP-D5-20 |
| B6 R22 ; B1 S310 | CAP-D5-21 |
| B5-en #11 | CAP-D5-22 (part tarif/spot écartée) |
| B1 V112, V113, V333, V335, V336, V343 ; B5-es §4.1 étapes 4, 5, 8 ; erreurs 3, 7, 8, 11, 13 ; B5-nl cl. 11, 12 ; B7 g.47 | DÉJÀ PRÉSENT — courbe de pompe (`CP/selection.py::choisir_pompe`), HMT itérée et Hazen-Williams (`CP/hydraulique.py::hmt_composantes`, `pertes_hazen_williams`), besoin mensuel (`CP/volumes.py::couverture_besoin_eau`), sortie du variateur assortie (`CP/selection.py::variateurs_compatibles_plaque`), températures TMY (`CP/champ.py::_temperatures`), écran `FE/pompage/PompagePanel.jsx` |
| B5-fr #10 (données manquantes) ; B5-es §4.1 étape 1 | DÉJÀ PRÉSENT — champ fautif nommé (`CA/services/pompage.py::LIBELLES_COMPOSANTES_HMT`, `CA/views/pompage.py`) + visite avant devis si forage inconnu (D-AGR-4) ; le courant de démarrage → nommé « non modélisé » dans CAP-D5-11 |
| B1 V115, V116, V118, V119 ; S015, S016, S018, S019 ; B5-es #27 ; B6 K41, K43 ; B7 g.55 | DÉJÀ PRÉSENT — `CA/services/consommation.py::_courbe_appareils` (provenance `saisi`/`table_atelier`, CALX256), `apercu_courbe_csv` (CALX259), `CA/services/profils_types.py` (CALX30/258), Ramadan (CALX260) |
| B1 S085, S086 (stratégies), S311, V351, V352 (plafond) ; B6 K35 ; B7 g.21, 27 ; B5-es K20, K40 ; B5-en P2.2 (clim de nuit, jours d'autonomie) | DÉJÀ PRÉSENT — `CA/services/batterie.py::STRATEGIES`, `CA/services/hors_reseau.py::_banque_pour_autonomie`, `CA/services/charges.py::courbe_climatisation`, écran `FE/atelier/PanneauBatterie.jsx` |
| B1 S006, V349 (cos φ imposé) ; B6 K28 ; zéro injection | DÉJÀ PRÉSENT — `CA/services/raccordement.py::CHAMPS_SAISIE`, plafond 0 kW admis (`CA/services/autoconsommation.py::plafond_injection`), écran `FE/electrique/Raccordement.jsx` |
| B1 V120 ; B6 courbes importées | DÉJÀ PLANIFIÉ / FAIT — CALX259 (courbe) ; séries d'albédo/limitation : hors domaine (D4) |
| ACAL445, ACAL446, ACAL447, ACAL453 | DÉJÀ PLANIFIÉ — autoconsommation par mois, consommation sur la journée type, SOC d'une semaine, graphique mensuel ; dépendances de CAP-D5-02, 05 |
| B1 S003 (sélecteur de type de système) ; B6 K66 | Hors domaine — parcours guidé (D6, ACAL392-394) |
| B1 C01 ; B6 R46 ; B7 U30 (Sankey) | Hors domaine — CAP-D4-19 |
| B5-fr #12 ; B5-es #25, K48 (micro-onduleurs et pince CT) | Hors domaine — CAP-D3-17 (règle et schéma) |
| B5-en #6, B7 U11 (fichier de charge refusé, diagnostic nommé) | Hors domaine — CAP-D4-27 (diagnostic d'import) ; le CSV de charge refuse déjà en nommant la ligne (`CA/services/consommation.py::ImportCourbeInvalide`) |
| B2 #11 (stock dans la nomenclature) | Hors domaine — D2/D3 |

---

## F. Écarté (une ligne chacun)

- B1 V114 (comparer couplage direct / booster / cascade / **batterie** en pompage) : on ne vend que des variateurs, et
  CLAUDE.md interdit onduleur et batterie dans une composition de pompage.
- B1 V339 (modèle dynamique du forage, τ ≈ 4 min) : infra-horaire, hors décision.
- B1 V330, S312, S319 (tension, résistance interne, Peukert, auto-décharge) : aucun de ces paramètres n'est publié sur
  nos fiches ; les poser serait inventer.
- Capacité de batterie corrigée par une courbe de température (B5-en #21, part capacité) : aucune courbe publiée ; on
  garde le seul contrôle de plage (CAP-D5-20).
- B1 S313 (plans de charge plomb) : plomb quasi absent du marché.
- B1 S088, S316 (ballon d'eau chaude, chauffage, gains internes) : hors métier PV.
- B1 V117 (profils de probabilité, réseaux DC), V111 (classes de systèmes autonomes) : hors marché.
- B1 S020, S322, B5-en #11 (part spot), B6 K71 (tarifs, net-metering, revenus) : argent dans le calepinage, interdit.
- Consommation de carburant et litres du groupe électrogène (B1 S321, B5-en P2.2) : prix/argent ; on garde heures et kWh.
- B1 S021 (consommateur qui absorbe le surplus) : une seule page éditeur, aucun fil.
- B5-es erreur n° 2 (onduleur standard ou sinus modifié sur une pompe) : nous ne vendons que des variateurs.
- B5-es erreur n° 5 (étrangler la sortie) et n° 12 (entretien de la pompe) : exploitation/SAV, pas conception ; le kit
  propose déjà « Contrat d'entretien » (`CP/kit.py::OPTIONS`).
- B5-en P2.2 « réseau faible pendant l'exploitation » (Grid Lost, 52,7 Hz) : comportement d'exploitation, hors conception.
- B7 « charges pilotables » emhass : D-RES-2710 (un VE déjà possédé n'ajoute aucune couche) et pilotage = exploitation.
- B7 « règle des 120 % » : norme américaine ; l'équivalent marocain est le profil de distributeur (CAP-D5-07).
- B5-de §12 « non retenu » (prix, paiement, subvention) : hors module (règle #4).

---

## G. Contradictions entre lanes, tranchées par le code

1. **Marche à sec** — B5-es §4.1 dit « aucune règle de protection trouvée » : faux en partie. Le kit a l'option « Sonde
   de niveau (marche à sec) » et la mention de la protection du variateur (`CP/kit.py::OPTIONS`, `composer_kit`), la
   fiche a `var_protection_marche_a_sec`, et le devis contrôle l'immersion minimale (`CP/selection.py::choisir_pompe`).
   Ce qui manque est vrai : aucune alerte quand ni l'une ni l'autre n'est prévue, rien de cela côté calepinage
   (`CA/views/pompage.py` appelle `selection_pompe`).
2. **Où vit le calcul de pompage** — B6 K44 renvoie à `apps.ventes.solar_design.pumping_cycle_yield` : périmé. Le
   moteur a déménagé dans `CP/volumes.py::production_mensuelle` / `pumping_cycle_yield` (AGR109, AGR125, docstring de
   `CA/services/pompage.py`). Et ce noyau appartient à `devis`, pas à `calepinage` — aucune lane ne l'avait vu.
3. **VE et pompe à chaleur** — B1 S023/S087 « PRÉSENT » contre B7 grappe 36 « ABSENT (git grep = 0) » : les deux ont
   tort. Le modèle serveur existe (`CA/services/charges.py`) mais aucun écran n'écrit `consumption.charges` ; l'atelier
   n'a qu'un appareil plat. Verdict : PRÉSENT SANS ÉCRAN.
4. **Recommandeur de batterie** — B6 R5/K36 « PARTIEL, git grep `cycles par jour` : 0 » : le comparateur de capacités du
   stock EXISTE et se voit (`CA/services/batterie.py::capacites_candidates`, bouton de `FE/atelier/PanneauBatterie.jsx`),
   et les cycles par AN sont calculés (`etapes/batterie.py::_publier`). Manquent : l'affichage des cycles, le verdict,
   la grille PV × batterie.
5. **Réserve des appareils secourus** — B2 #8, B5-de K53 et B7 g.35 la croient soit absente, soit simplement à afficher :
   en réalité le serveur la calcule (`reserve_depuis_appareils`) mais **la porte d'écriture la refuse**
   (`CA/services/electrique.py::CLES_BATTERIE`). Personne ne l'avait vu.
6. **Photo de facture** — B3 N17 dit « l'OCR existe dans `backend/fastapi_ia` mais n'est pas câblé » : vrai pour le
   calepinage, mais incomplet — le CRM la lit déjà (`apps/crm/intake_photo.py::_run_capture_ocr`, QK6, désactivé par
   défaut).
7. **Fiches techniques « stock »** — le brief et plusieurs lanes les rangent chez `stock` : `check_ownership.py` dit
   `apps/stock/models_fiche_technique.py` → `calepinage` (seuls la migration et l'écran sont `stock`).
8. **Loi 82-21** — B5-fr la classe « spécifique, sans outil » : le calcul sourcé existe déjà dans le dépôt
   (`core/reglementaire/regime_8221.py`, `constants_82_21.py::PLAFOND_INJECTION_PCT`) ; il ne manque que la lecture
   par le calepinage.
9. **Rabattement** — B5-en P2.2 cite des installateurs « sans rabattement du puits » : le module le prend
   (`coefficient_rabattement_m_par_m3h` dans `CA/views/pompage.py::_NOMBRES_POMPAGE`) ; B1 V338 avait raison.
10. **Hors réseau « pire mois »** — B5-en P2.2 « PRÉSENT » : vrai pour la défaillance et l'affichage du pire mois, mais la
    banque est dimensionnée sur la consommation MOYENNE (`CA/services/etapes/hors_reseau.py`) : PARTIEL.

---

## H. Non vérifié

- **Aucun écran n'a été ouvert** : les verdicts « visible » reposent sur la lecture des composants (`FE/…`) et de la
  présence des `data-testid`, pas sur un rendu. Aucune acceptation en direct.
- **Plafond 20 % (CAP-D5-03)** : je n'ai pas vérifié si la règle porte sur le surplus VENDU seulement ou sur toute
  injection, ni comment `constants_82_21.py` l'applique dans le devis ; la constante elle-même dit « revente non ouverte
  en basse tension ». À relire avant la tâche 2 (et à demander à Reda si le texte reste ambigu).
- Je n'ai pas vérifié si `CA/services/pompage.py` / `CA/views/pompage.py` et l'étude de pompage du devis
  (`apps/ventes/domain/pompage.py`) rendent le MÊME m³/jour pour le même site (AGR125 l'affirme dans la docstring).
- La constante `_PUMP_START_IRRADIANCE_FRACTION = 0.15` de `CP/volumes.py` (seuil de démarrage codé en dur, propriétaire
  `devis`) : la docstring de `production_mensuelle` dit qu'il est remplacé sur ce chemin ; non vérifié s'il sert encore
  ailleurs — à signaler au plan devis s'il sert.
- L'appareil « Recharge voiture électrique » de `apps/web/src/lib/applianceConsumption.ts` porte 7 400 W × 3 h
  (provenance `table_atelier`) : non vérifié si CALX256 l'accepte comme valeur de table annoncée ou si c'est un chiffre
  à sourcer.
- Les nombres de fils/lignes viennent des lanes, non recomptés ici ; les lignes de la passe 2 allemande (§8) n'ont été
  échantillonnées que par grappe (K38, K43, K47, K50, K53).
- Les sondes de propriété ont été lancées une par fichier (`python scripts/check_ownership.py --owner-of …`) ; un fichier
  NOUVEAU (ex. module de test) n'a pas été vérifié.
