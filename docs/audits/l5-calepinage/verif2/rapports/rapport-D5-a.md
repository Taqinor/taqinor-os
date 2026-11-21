# Rapport de vérification — lot D5-a (29 tâches : ACAL776-784, 786-803, 806-807)
Code lu dans `C:\dev\taqinor-os\.claude\worktrees\l5-verif\` (rien modifié). Notation : `B:` = `backend/django_core/apps/calepinage/`.

### ACAL776 — CORRIGER
Prémisse fausse : `detail_calepinage` (B:views/calepinages.py:1609) sert `GET calepinages/<pk>/`, il ne porte PAS `cible`. Le contexte de conception est servi par `contexte_conception` (B:views/calepinages.py:1290, dictionnaire littéral l.~1325-1356 avec `cible` l.1353), appelé par `design_context` (l.1054). « Appelants : detail_calepinage ← design_context et selectors (2 sites) » est donc faux aussi.
Aussi : le contrat `calepinage_design_context.json` `exemple` porte déjà 10 clés (calepinage, geometrie, cible, carte, modifiable, raison_lecture_seule, avertissements, revision_possible, natures_zones, variante), pas « sept → huit » ; le test `test_design_context.py:41,82` compare à `set(EXEMPLE_SERVI)` (dynamique) : seul l'échantillon `exemple` est à compléter, aucun compte à réaligner.
Correction : remplacer partout `detail_calepinage` par `views/calepinages.py::contexte_conception` (clé de plus dans le littéral renvoyé) ; Appelants = `design_context` (1 site) ; Listes figées = « clés de `exemple` du contrat (10 → 11) ». Le reste (lecture du lead par `get_company_lead`, `_profil_depuis_lead`/`annuel_mad` = 12 mois sinon None, consommation.py:97-175) est confirmé.

### ACAL777 — CORRIGER
Prémisses confirmées : `monthlyBill` ne lit que `rp9-bill` (apps/web/src/scripts/roof-tool-pro11.ts:1258), absent hors `estLead` (frontend/src/pages/ventes/ToitureDesign.jsx:1306) ; carte = `billToAnnualKwh(monthlyBill())` (optimizer.ts:613, 762).
Faux/oublié : `monthlyBill()` n'alimente pas que les cartes — il pilote aussi `solveLive` (optimizer.ts:888-904), `reoptimize` (roof-tool-pro11.ts:2247), `besoinAutoRelu` et `ctx.neededPanels` auto : injecter 900 MAD change le nombre de panneaux posés/proposés en mode calepinage, ce que la tâche (« les cartes calculent… ») ne dit pas et ne teste pas. Correction : soit limiter le repli aux deux appels de carte (une fonction `factureCarte()` = `monthlyBill() || opts.factureMensuelleMad`), soit ajouter au « fini quand » + « Test rouge » : « le nombre de panneaux posés/proposé est inchangé ». Mineur : roof-tool-pro11.ts fait 4 424 l. (pas 4 354) ; la fonction est `bootCalepinage` → `poursuivreBootCalepinage` (useAtelierBoot.js:299/372, l'appel `initRoofToolPro8` est l.390).

### ACAL778 — CORRIGER
(1) Le libellé actuel est « Économies estimées » (ToitureDesign.jsx:1389), pas « Économies » : réécrire « libellé actuel « Économies estimées » → « Économies (estimation de l'atelier, plafonnée à la facture) » ».
(2) `cibleVendue` vaut `true` PAR DÉFAUT (roof-tool-pro11.ts:652) et n'est posé que par `applyDevisHydration` (l.2013) : en mode lead (aucun devis, aucun onglet Économie), la note « Le chiffre du devis est dans l'onglet Économie » s'afficherait à tort. La condition doit être « calepinage avec devis lié » (ex. `cible.source === 'devis'` côté contexte, passé à l'atelier), pas `cibleVendue`. Ajouter un champ `CardData`/option et un cas de test « mode lead : pas de note ».
(3) `paintCard` : l.965 (confirmé). Goldens ×3 à régénérer : confirmés (`__golden__/toitureDesign.{calepinage,devis,lead}.html`). La carte « Total » (zones.ts:452) n'a pas d'étiquette propre à changer dans le JSX : « jumeaux » à vérifier ou retirer.

### ACAL779 — OK
`_charges_annuelles` (B:services/courbe_charge.py:737) ne connaît que `planifie` (l.764-771) ; `CourbeChargeInvalide(champ=…)` existe (l.139) ; simulation.py:1396-1400 la convertit en refus ; appelants vrais (simulation.py, etapes/batterie.py:225) ; les deux modules de test existent. Schéma : `$defs/consumption` ne liste pas `charges` (courbe24, saisons, appareils, methode, source) : la propriété documentée est bien à ajouter.

### ACAL780 — CORRIGER
Prémisse confirmée : `serializeConsumption` (apps/web/src/scripts/roofPro11/prefill.ts:734) rebâtit le bloc sans `charges` ; 0 occurrence de `km_par_jour|cop_points` côté front ; arguments de `courbe_vehicule/pac/climatisation` conformes (charges.py:206/376/494), `type` ∈ ('vehicule','pac','chauffe_eau','clim','piscine') (courbe_charge.py:87).
À corriger : (a) `prefill.ts` fait 2 013 l. (pas 1 999) ; émettre `charges` demande au moins DEUX sites (la ligne `touche` l.743, sinon `return {}` l.744 écarte une charge seule, et le littéral l.753-765) + un appel de relecture dans `deserializeConsumptionFromLayout` (l.1647) : « net 0, une seule ligne remplacée » est intenable. Correction : « extraire d'abord ≥ 30 l. de prefill.ts (ex. sérialisation de la consommation) vers un fichier neuf, puis câbler ; net prefill.ts ≤ 0 après extraction ». (b) Un conteneur ajouté dans ToitureDesign.jsx change le HTML des goldens (`toitureDesign.calepinage.html` au moins) : « golden inchangé tant que le panneau est replié » est faux si le conteneur est rendu ; ajouter les goldens concernés à `Files:` et « Listes figées », ou monter le panneau hors JSX statique. (c) Le type `chauffe_eau`/`piscine` est admis serveur : la tâche choisit trois types, à dire « (les deux autres types du serveur hors périmètre) ».

### ACAL781 — OK
`construire_courbe_charge` publie bien `consommation.charges[]` (code, libelle, kwh_an, planifie, plafonnee, methode, hypotheses…) et `total_charges_kwh` (courbe_charge.py:870-896) ; 0 lecteur front confirmé ; TapisHoraire monté par PanneauProduction (l.391, ACAL446 livré). Détail : l'`exemple` du contrat porte 1 800 kWh / `planifie: false`, pas 1 460 / vrai (le test devra poser sa propre variante).

### ACAL782 — OK
`regime_8221` (core/reglementaire/regime_8221.py:129) rend exactement code/libelle/base/guichet/guichet_statut/puissance_retenue_kw/base_puissance/a_qualifier ; grep `8221` dans apps/calepinage hors migrations : 0 ; `bloc_raccordement` (B:services/raccordement.py:1276) ; `_evaluation` fournit puissance DC/AC. Mineur : le bloc a déjà QUATRE clés racine (saisie, calcul, verdicts, proposition_lead — test_calx244:95), il passera à cinq, pas « trois → quatre ».

### ACAL783 — OK
`PLAFOND_INJECTION_PCT = 20`, `PLAFOND_INJECTION_SOURCE`, `MENTION_BT` : apps/ventes/quote_engine/constants_82_21.py:54-77 (source identique au texte de la tâche) ; `bilan_autoconsommation` publie `surplus_kwh`/`production_kwh` (autoconsommation.py:179-226) ; `ventes/selectors_calepinage.py` appartient à calepinage (check_ownership) ; aucune valeur recopiée.

### ACAL784 — OK
`Raccordement.jsx` (326 l.), `TONS_STATUT` (Raccordement.helpers.js:111), onglet `raccordement` (atelier/onglets.js:76, étape Électrique de parcoursGuide.js:21) confirmés ; 0 occurrence de `regime|8221|plafond_pct`. (Le test a 4 `describe`, pas 3 : sans effet.)

### ACAL786 — OK
`CLES_BATTERIE` = 11 clés (B:services/electrique.py:877) ; `_valider_batterie` refuse toute clé hors liste (l.903) ; schéma `champs_entree.py::_batterie` fermé (l.72-85) ; la simulation lit déjà `appareils/duree_secours_h/fenetres/part_effacable_pct/plafond_effacable_kw` (etapes/batterie.py:562-595) et les `champ` de `reserve_depuis_appareils`/`_fenetres`/`_part_effacable` existent (batterie.py:432-541) ; `_declaration_batterie` (simulation.py:301) laisse passer toute clé non nulle ; tests cités présents.

### ACAL787 — OK
`_pointe` produit les 4 clés (batterie.py:584-587), aucune n'est recopiée par `_publier` (etapes/batterie.py:700-796, grep 0) ; `vieillissement`, `ecretage_recupere_kwh`, `charge_reseau_kwh` publiés mais absents de l'échantillon (confirmé : `batterie.total` du contrat). Remarque : `test_calx5_simulation.py::ContratTest` ne compare pas `batterie.total` en profondeur ; la garde vient des nouveaux cas de `test_calx188_batterie.py` + `check_api_shapes.py`.

### ACAL788 — OK
`DeclarationBatterie` (PanneauBatterie.jsx:115), `corpsDeclaration/depuisEntree` (helpers :29,40), `refusParChamp` (electrique/entreeElectrique.js:12), `reserve_depuis_appareils.detail` existent ; aucune valeur préremplie ; `@after` cohérents.

### ACAL789 — OK
`modeExpert.js` + `useModeExpert` existent ; `LigneGroupe` n'affiche ni cycles ni vieillissement (l.223-236) ; `vieillissement_batterie` rend `annees[].capacite_batterie_pct` (None au-delà), `champ`, `motif_absence` (batterie.py:1990-2030).

### ACAL790 — OK
`CLES_HORS_RESEAU` contient déjà `seuils` (electrique.py:882) mais `_valider_hors_reseau` (l.943-) n'en contrôle pas la forme ; `_seuils_de_protection` (B:services/hors_reseau.py:159) lève `HorsReseauInvalide(champ='seuils.veille_pct')` avec la règle arrêt ≤ entretien ≤ veille ; schéma `_hors_reseau` = 3 clés (champs_entree.py:88-92) ; `RefusTest` présent (test_calx272:120).

### ACAL791 — OK
Fieldset hors réseau l.204-211 de PanneauBatterie.jsx, 0 champ de seuils ; `useModeExpert` présent ; dépend d'ACAL790.

### ACAL792 — OK
`_fenetres_saisies` (FENETRES_MAX=3, soc_cible_pct), `_fenetres`, `_part_effacable` confirmés (batterie.py:296-377, 524) ; `CHAMPS_BATTERIE` dans helpers.js:16 ; 0 `soc_cible_pct` côté front.

### ACAL793 — OK
`_publier` n'écrit que soc/flux (etapes/batterie.py:726-732) ; `bilan_autoconsommation` réutilisable ; `serie_de_test(heures=…)` existe (test_calx188:38) ; formules sans seuil ni défaut (aucun mot de verdict).

### ACAL794 — OK
`CLES_SIMULATION`/`TYPES_CLES` append-only (parametres_cles.py:94,225, type `pourcentage` existant) ; `reglage(contexte, cle)` (etapes/__init__.py:372) ; aucune valeur par défaut (D-ACAL-31 respectée) ; les deux tests cités existent. Rappel de câblage (pas une faute) : `_publier` ne reçoit pas `contexte`, il faudra le lui passer.

### ACAL795 — OK
`BlocBatterie` (PanneauBatterie.jsx:238), 0 lecteur de `faits_serie` ; dépend d'ACAL793-794.

### ACAL796 — OK
`CLES_BATTERIE` sans coupure ; patron de validation nommée identique à ACAL786 ; `@after: ACAL786` (qui crée `batterie_declaration.py`, absent aujourd'hui).

### ACAL797 — OK
`simuler_batterie` ne connaît que le réseau présent ; aucune coupure modélisée (grep 0) ; fonction pure neuve, aucun montant ; `@after: ACAL796, ACAL787`.

### ACAL798 — OK
`reserve_depuis_appareils` renvoie `detail` (nom, quantite, puissance_continue_kw, energie_kwh) et `energie_kwh` (batterie.py:432-523) : la formule est un quotient traçable ; test `ReserveDepuisAppareilsTest::test_deux_appareils_pendant_quatre_heures` et `ChaineDeSimulationTest` existent (test_calx270:45,150).

### ACAL799 — OK
`SecoursBatterie.jsx` créé par ACAL788 ; `coupures` du front = 1 occurrence sans rapport (ModeTerrain) ; chaîne `@after` 798 → 797 → 796 couvre le backend.

### ACAL800 — OK
`CLES_HORS_RESEAU` 4 clés → 5 ; `MENTION_ENTRETIEN_SANS_SOURCE_AC` (B:services/hors_reseau.py:146) confirme l'absence de source AC ; aucun carburant/prix.

### ACAL801 — OK
`_simuler_hors_reseau` (hors_reseau.py:216, 472 l.), `bloc_hors_reseau` (etapes/hors_reseau.py:163), `SansSeuilsTest::test_la_sortie_est_terme_a_terme_celle_d_aujourd_hui` (test_calx272:157-189), `contexte_de_test` (test_calx191:80) existent.

### ACAL802 — OK
`conso_journaliere = total_conso / jours_couverts` (etapes/hors_reseau.py:212) : la banque est bien dimensionnée sur la moyenne ; `dimensionner_hors_reseau` appelable deux fois (hors_reseau.py:453) ; `test_la_banque_vient_des_jours_saisis_et_de_la_fiche` existe (test_calx191:167).

### ACAL803 — OK
`BlocHorsReseau` (PanneauBatterie.jsx:458), fieldset hors réseau l.204 ; 0 occurrence `groupe_appoint` côté front ; `@after` 802/799/791.

### ACAL806 — À SCINDER
Quatre comportements distincts dans un seul « fini quand » (HMT mensuelle + choix de pompe par `choisir_pompe` avec calage/tubage + plafond forage + bilan réservoir) avec 6 nouvelles entrées et le remplacement de `selection_pompe` (B:views/pompage.py:270, 389 l.) par `choisir_pompe` (core/pompage/selection.py:323) : ≈ 70 l. annoncées, sûrement plus.
Imprécisions prouvées : (a) `choisir_pompe` ne produit que `immersion_minimale` et `diametre_tubage` (selection.py:507,516) avec les champs `source.profondeur_calage_m` / `source.diametre_tubage_mm` ; il n'existe AUCUN code `plafond_forage` : cette alerte est à fabriquer côté calepinage depuis `plafond_atteint` (volumes.py:433) ; « les trois lues de choisir_pompe » est faux ; (b) le mapping de champs (`source.…` → `profondeur_calage_m`) n'est pas dit ; (c) ACAL804/805 vivent dans `docs/plans/PLAN_AUDIT_DEVIS.md` (lanes `calepinage/pompage`, @model opus) et ACAL806 n'a aucun `@after` pour elles.
Correction : scinder en ACAL806a (HMT par mois : `hmt_mensuelle` + `volumes` suivent `hmt_m_mois`, @after ACAL805), 806b (`choisir_pompe` + calage/tubage + alertes `immersion_minimale`/`diametre_tubage` avec mapping de champ dit), 806c (`plafond_m3h` + alerte `plafond_forage` + `bilan_reservoir`, @after ACAL804) ; ajouter les `@after` ; chaque tâche garde le contrat `calepinage_pompage.json` (exemple ET exemple_vide) et `test_agr125_parite_devis.py::PariteVolumesDevisCalepinageTest::test_forme_du_contrat_calepinage` (existe, l.135).

### ACAL807 — OK
`PompagePanel.jsx` (366 l.), `CHAMPS` (l.46), `VolumesMensuels` (l.169), `Champ` (l.84), test « trois groupes » (PompagePanel.test.jsx:45), `E2E_HOOKS.md` section l.712 et `e2eHooks.test.mjs` existent ; onglet `pompage` dans `onglets.js:56`, étape Panneaux (parcoursGuide.js:19). Mineur : un seul appelant (`onglets.js`) — `module.config.jsx` ne référence pas `PompagePanel`. Dépend de ACAL806 : si celle-ci est scindée, passer `@after` sur 806a/b/c.

## OPTIONNEL (5 lignes max)
- ACAL779/780 : proposer une case « déjà dans mes factures » qui, cochée, fait REFUSER la simulation est contre-intuitif ; envisager « charge ignorée + avertissement » (D-RES-2710 : aucune couche ajoutée) — à décider avec le fondateur, non bloquant.
- ACAL783 : l'avertissement orange « dépasse le plafond légal » s'affichera aussi sur un site BT où `MENTION_BT` dit que la revente n'est pas ouverte ; la mention est servie, mais le voyant orange pourrait être neutre en BT.
- ACAL782 : `regime_8221` n'est appelé sans `niveau` (BT/MT) : un site MT < 11 kW sera dit « Déclaration » (par défaut BT) ; passer le niveau si le calepinage le connaît.
- ACAL777 : « null ⇒ comportement d'aujourd'hui » garde « 0 MAD » à l'écran sans facture, que D-ACAL-40 interdit ; l'écart est renvoyé à CAP-D6-05 (hors périmètre dit) : à ordonner avant livraison.
