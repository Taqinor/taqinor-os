# Lot 6 — le schéma électrique du calepinage devient celui du devis

Demande de Reda, 26/11/2026 (mot pour mot) : « i want this shema unifilaire i hade to be changed by the new
schema electique that calpinage use that shows the chaines of pannels in 4 colors and show the inverter the grid
and everything (if it does not show the battery make is show it) ».

Contrat (posé SEUL, commit `b4def8478`) : `backend/django_core/apps/ventes/contract_samples/schema_electrique.json`
et sa copie jumelle `apps/web/src/contract_samples/schema_electrique.json`. Règle de source : D-ACAL-131
(`docs/audits/decisions.yml`, prise par l'orchestrateur, **à confirmer**). Ce fichier est le plan des trois lanes ;
chaque lane ne coche que les lignes de SA section.

## 1. Ce qui existe (lu le 26/11/2026 sur `origin/dev-lot5` = `8059abb07`)

### Le dessin neuf (calepinage)
- `frontend/src/features/calepinage/SchemaUnifilairePanel.helpers.js::planSchemaEnBlocs` (l. 218-367) compose le
  dessin à partir de DEUX réponses : `schema-unifilaire/` (`blocs[]` : `clef/titre/sous_titre/repere`, l'édition
  `edition.libelles`, et le SVG — seulement pour savoir s'il trace une terre en pointillé) et `resultat/`
  (`electrique.affectation[]` → `resumeRaccordement.js::chainesServies` l. 17 : chaîne, nombre, `couleur_chaine`,
  `mppt` ; `electrique.onduleurs[0]` → `texteOnduleur` l. 49 et `n_mppt` ; `electrique.chainage.puissance_module_wc` ;
  `troncons.troncons[]` → sections/longueurs ; `hors_reseau`, `simule`). Dessiné par
  `SchemaUnifilairePanel.jsx::SchemaEnBlocs` (l. 267), monté par `atelier/coque/etapes/EtapeSchema.jsx` (l. 135-151).
- Couleurs : `apps/calepinage/services/chaines.py::PALETTE_CHAINES` (l. 1089, **8** teintes, les 4 premières
  bleu / orange / vert / magenta = la capture de Reda) appliquée par `_colorer` (l. 1104) dans l'ordre de première
  apparition ; servie ligne par ligne dans `electrique.affectation[].couleur_chaine`.
- Coffret DC / onduleur / coffret AC / compteur / TGBT / réseau : les `Bloc` de
  `core/electrique/schema.py::blocs_du_schema` (l. 201-305), servis par
  `apps/calepinage/services/sld.py::schema_du_calepinage` (l. 804) via `rendu_du_schema` (l. 686).
- **Batterie : le noyau la sait, l'écran ne la dessine pas, et le calepinage ne la passe presque jamais.**
  `blocs_du_schema` pose un bloc `batterie` (l. 274-277, détail `_detail_batterie` l. 436 : kWh · V) dès que
  `EntreeElectrique.batterie` est vrai. Côté calepinage, `apps/calepinage/services/electrique.py::_options_batterie`
  (l. 1236) ne l'allume que si la batterie est DÉCLARÉE dans l'entrée électrique (`donnees['batterie']`), et ne passe
  jamais la tension. Une batterie présente seulement sur la ligne du devis lié (cas de la capture : Deye hybride
  + 3 Dyness) n'est donc pas servie ; et même servie, `planSchemaEnBlocs` ne lit aucun bloc `batterie`. La
  résolution existe déjà : `chaines.py::batterie_du_calepinage` (l. 563 : produit, packs, fiche, y compris depuis
  la ligne du devis lié). Aucune protection batterie n'est jamais calculée : `core/electrique/protections.py` § 9
  (décision du 19/08/2026, aucun fusible ni sectionneur batterie).

### L'ancien schéma (devis)
- Moteur : `apps/ventes/electrical_service.py::rendre_schema_du_devis` (l. 1209) — redessine la planche détaillée
  `core.electrique.schema.rendre_schema` depuis l'étude RANGÉE `Devis.electrical_design`
  (`objets_moteur_depuis_contrat` l. 1050). L'étude est projetée par `projeter_contrat` (l. 883) :
  `chaines[{pan, mppt, nb_modules}]`, `protections[]`, `cables[]`, `materiel{nb_modules, module, onduleur{designation,
  ac_kw, n_mppt}, batterie{presente, designation, kwh, v_nominal}}`. **Le moteur connaît donc les chaînes sans
  calepinage** (nombre, panneaux par chaîne, entrée MPPT, calculés par `core.electrique.concevoir`) ; il ne connaît
  ni le nombre d'unités de batterie ni le nombre d'onduleurs (lisibles sur les lignes : `_batterie_du_devis` l. 535
  somme déjà `kwh_nominal × quantite`).
- Option dessinée : **une seule**, `_option_choisie` (l. 213, règle fondateur du 25/08/2026 « avec batterie quand
  elle est servable, sinon sans ») ; `groupes_du_devis` (l. 480) compte les panneaux de cette même option.
- (a) page client : `apps/ventes/public_views.py::_safe_sld_svg` (l. 645) → clé `sld_svg` (l. 1452) et
  `_conception_electrique_publique` (l. 738, liste blanche `_PUBLIC_CHAINE/_PUBLIC_PROTECTION/_PUBLIC_CABLE`
  l. 699-710) → clé `conception_electrique` (l. 1459) ; les deux derrière la case `sld` (l. 1363-1366). Page :
  `apps/web/src/pages/proposition/[...token].astro` l. 1811-1813 (`showSld`) et section `#sld` à partir de l. 6987 (le
  SVG injecté dans `#sld-svg-wrap` l. 7033, visionneuse `#sld-viewer` l. 7079, scripts de téléchargement et de
  visionneuse à partir de l. 10537) ; `apps/web/src/lib/proposition.ts::
  hasSldSvg` (l. 1491), `parseConceptionElectrique` (l. 1597). **Le même schéma (option avec) quelle que soit
  l'option que le client coche** ; en résidentiel seulement, `apps/ventes/calepinage_options.py::_pointeur_sld`
  (l. 1084) nomme l'option qu'il décrit.
- (b) annexe PDF PV46 : `apps/ventes/quote_engine/artefacts_rendu.py::_sld_svg` (l. 130), posée par
  `ajouter_artefacts_rendu` (l. 288, opt-in `include_annexe_technique`), imprimée par
  `generate_devis_premium.py::page_annexe_technique` (l. 2880, `SLD_SVG` l. 3644). Même option que (a).
- (c) fiche devis ERP : `frontend/src/features/ventes/ConceptionElectrique.jsx` (monté par
  `frontend/src/pages/ventes/devisList/DevisRow.jsx` l. 1063) affiche `GET ventes/devis/<id>/schema-unifilaire/
  ?format=json` = `apps/ventes/diagram_views.py::schema_unifilaire_devis` (l. 170) — **ni le moteur ni l'étude :
  l'esquisse historique `single_line_diagram.build_single_line_svg`**, dont `diagram_params_from_devis` (l. 352)
  additionne les panneaux de TOUTES les lignes (les deux options d'un devis à deux options) et lit le kW dans le
  libellé.
- « Nouveaux rendus seulement » : `apps/ventes/domain/regles_calcul.py::_ouvert_aux_nouveaux_rendus` (l. 167),
  patron `COUPURE_PDF_2511` / `phrases_pdf_2511_ouvertes` / `drapeaux_pdf_2511` (l. 162-220), regroupés par
  `drapeaux_nouveaux_rendus` (l. 223). `REGLES_COURANTES` (l. 164) ne bouge pas.
- Source calepinage d'un devis : `apps/ventes/selectors_calepinage.py::_conception_a_jour` (l. 176, empreintes
  `layout_hash` égales) ; lecture du calepinage lié par `apps/calepinage/selectors.py::calepinage_du_devis` (l. 670).

### Gardes qui tiennent l'ancien dessin
Backend : `apps/ventes/tests/test_pv81_proposition_sld.py` (liste blanche publique), `test_l_choix_avec_sld.py`,
`test_qjr_sld_variante.py`, `test_sld_batterie_packs.py`, `test_pv41_conception_electrique.py`,
`test_pv85_identites_schema.py`, `test_cal195_schema_unifilaire.py`, `test_l_niv_niveau.py`,
`test_l_sect_sections.py`, `test_l_1v_devis_dor.py`, `test_quote_engine.py` (pages : annexe = +1 page en opt-in),
`test_regles_calcul_rendu_origine.py` + `tests/golden/regles_calcul_origine.json`,
`test_moteur_golden_options_pdf.py` + `tests/golden/moteur/options_pdf.json` ; calepinage :
`apps/calepinage/tests/test_calx204_contrat_sld.py` (six clés exactes, mots d'argent), `test_acal_sld_conception_reelle.py`,
`test_acal_affectation_couleurs.py` ; noyau : `core/tests/test_electrique_schema.py`, `test_ciq664_schema_mt.py`,
`test_electrique_purete.py`. Front : `frontend/src/features/calepinage/SchemaUnifilairePanel.test.jsx` (bloc
« planSchemaEnBlocs / SchemaEnBlocs » l. 468), `atelier/coque/etapes/EtapeSchema.test.jsx`,
`frontend/src/features/ventes/ConceptionElectrique.test.jsx`, `frontend/e2e/calepinage-maquettes.libelles.json`
(libellés de l'écran Schéma). Site : `apps/web/tests/propositionSldWJ128.test.ts`,
`propositionSldViewerWJ129.test.ts`, `propositionPayload.test.ts`, `propositionChaptersPV80.test.ts`. Contrats :
`apps/ventes/contract_samples/proposal_data.json` (déclaré `forme_serveur: complete`, + copie web), 
`apps/calepinage/contract_samples/calepinage_sld.json`. `frontend/e2e/ci-site-mt-recette.spec.js` lit
`POST ventes/schema-unifilaire/` (planche générique) : non touché par ce lot.

## 2. La forme retenue

UN document `Doc` (contrat : `schema_electrique.json`, toutes clés toujours présentes, `null` = omis) :
`version, source (calepinage | conception_devis | lignes_devis), option, calibres_masques, panneaux{nombre,
module{designation, puissance_wc}}, chaines_reparties, chaines[{numero, couleur_index, couleur, nb_panneaux, onduleur,
entree}], coffret_dc{organes[{clef, repere, titre, calibre, quantite}]}|null, onduleurs[{designation, puissance_kw,
nombre, nb_entrees}], batterie{designation, unites, capacite_kwh, tension_v, protection}|null, coffret_ac{organes}|null,
compteur_production|null, tgbt|null, etage_mt[], reseau|null, cote_reseau{etat, motif}, liaisons{dc, ac{section_mm2,
longueur_m}}, terre`.

Servi à trois endroits, jamais recomposé ailleurs :
- calepinage : 7e clé `schema_electrique` de `GET/POST calepinages/<pk>/schema-unifilaire/` (un `Doc`, `null`
  quand `svg` est `null`) ;
- page client : clé additive `schema_electrique = {options: {sans_batterie, avec_batterie}}` (absente si la case
  `sld` est décochée ou si aucune option n'a de `Doc`) ;
- fiche devis ERP : clé `schema_electrique` (même enveloppe `{options}`, niveau confiance) de
  `GET ventes/devis/<pk>/schema-unifilaire/?format=json`.
- annexe PDF : SVG du `Doc` de l'option rangée, rendu côté serveur.

Règle de source (D-ACAL-131, à confirmer) : chaînes du calepinage quand `_conception_a_jour` est vrai et que
l'option est celle du calepinage (l'option dont le compte de panneaux, `domain/dimensionnement_devis.py::
comptes_panneaux_valides`, égale celui du calepinage ; à égalité, celle de `_option_choisie`) ; sinon la conception de
l'option ; sinon le champ sans découpage. Option rangée (`electrical_design`) : lue telle quelle. Autre option :
conception calculée À LA LECTURE avec `build_electrical_design(..., persister=False)` sur les lignes de CETTE option
(précédent : ADEV58), jamais écrite depuis une lecture publique ; `REGLES_COURANTES` intact.

Niveau « standard » : `calibres_masques: true`, calibres, sections, longueurs et tension de batterie à `null`, mêmes
organes. Aucun montant, aucun prix d'achat, aucune hypothèse interne, aucune tension de chaîne ni chute de tension.

Le dessin (les trois rendus suivent la capture et l'écran calepinage d'aujourd'hui) : bande « Côté panneaux · courant
continu » — une rangée par chaîne « Chaîne N · K panneaux », K vignettes à la couleur de la chaîne, « K × W Wc », fil à
la couleur de la chaîne vers « Coffret côté panneaux » puis « entrée E » vers l'onduleur ; carte « Onduleur » (X kW,
désignation, « N entrées : 1 et 2 », pastille « continu → alternatif ») ; **carte « Batterie »** (désignation,
« U × … », « C kWh » au total, « V » si servi) DANS la bande courant continu, reliée à l'onduleur par une liaison
NEUTRE à double flèche (charge / décharge) ; bande « Côté réseau · courant alternatif » de l'onduleur vers la gauche :
« Coffret côté réseau » (organes), « Compteur de production », « TGBT », [étage MT, « à confirmer »], « Réseau du
distributeur · Compteur ONEE ». `cote_reseau.etat = a_calculer` : blocs en creux sans valeur ; `hors_reseau` : rien.
Légende : une ligne par chaîne (couleur), « Côté réseau (courant alternatif) », « Liaison batterie » si batterie,
« Liaison à la terre » si `terre`, « Section du câble, puis sa longueur » si une section est écrite.

## 3. Les trois lanes (fichiers DISJOINTS)

Le contrat `schema_electrique.json` (les deux copies) est GELÉ : seule la lane B peut le changer, et elle prévient
E et W. Commit par tâche, message `SCHEL-<id> : …`. Contrôles hôte seulement (pas de docker, pas de base de test).

### B — backend (`@model:opus` : règle #4, `core` sous import-linter)
Fichiers : `backend/django_core/core/electrique/schema.py` (accueille `PALETTE_CHAINES`),
`backend/django_core/core/electrique/schema_electrique.py` (NOUVEAU — Nouveau fichier car : `schema.py` est la
planche détaillée, ce module est le document + le dessin en blocs, pur, sans Django),
`backend/django_core/core/tests/test_electrique_schema.py`, `backend/django_core/apps/calepinage/services/chaines.py`,
`backend/django_core/apps/calepinage/services/sld.py`, `backend/django_core/apps/calepinage/views/schema.py`,
`backend/django_core/apps/calepinage/selectors.py`, `backend/django_core/apps/calepinage/contract_samples/calepinage_sld.json`,
`backend/django_core/apps/calepinage/tests/test_calx204_contrat_sld.py`,
`backend/django_core/apps/calepinage/tests/test_acal_sld_conception_reelle.py`,
`backend/django_core/apps/ventes/electrical_service.py`, `backend/django_core/apps/ventes/public_views.py`,
`backend/django_core/apps/ventes/diagram_views.py`, `backend/django_core/apps/ventes/openapi_shapes.py`,
`backend/django_core/apps/ventes/domain/regles_calcul.py`, `backend/django_core/apps/ventes/quote_engine/artefacts_rendu.py`,
`backend/django_core/apps/ventes/quote_engine/generate_devis_premium.py` (seulement si la page d'annexe doit
dimensionner le SVG neuf), `backend/django_core/apps/ventes/contract_samples/proposal_data.json` ET
`apps/web/src/contract_samples/proposal_data.json` (les deux copies, B seule), et les modules de test
`backend/django_core/apps/ventes/tests/test_pv81_proposition_sld.py`, `test_l_choix_avec_sld.py`,
`test_qjr_sld_variante.py`, `test_sld_batterie_packs.py`, `test_regles_calcul_rendu_origine.py`,
`tests/golden/regles_calcul_origine.json`, `test_quote_engine.py` (pages inchangées).

- [ ] SCHEL-B1 — `core/electrique/schema_electrique.py::document_schema_electrique(entree, resultat, *, chaines,
  option, source, standard, cote_reseau, unites_batterie, nombre_onduleurs, libelles)` → `Doc` (organes tirés de
  `blocs_du_schema`, coffrets `null` sans organe, `liaisons` par la règle « section commune / longueur si un seul
  tronçon », `terre` = la condition de `_barrette_de_terre`) ; `chaines_colorees(...)` applique `PALETTE_CHAINES`
  (déplacée dans `core/electrique/schema.py`, importée par `apps/calepinage/services/chaines.py` — une seule
  source). Fonctions ≤ 60 lignes. Tests dans `core/tests/test_electrique_schema.py` (avec et sans batterie, 4
  chaînes sur 2 entrées, standard, MT, hors réseau, aucun mot d'argent).
- [ ] SCHEL-B2 — calepinage : `sld.py::schema_du_calepinage` sert `schema_electrique` (chaînes de l'affectation
  servie, `_couleurs_des_chaines` l. 669 réutilisé ; batterie quand l'option retenue par la conception
  `services/devis_retenu.py::conception_du_calepinage` est « avec » ou qu'elle est déclarée, résolue par
  `batterie_du_calepinage`, capacité = `kwh_nominal` de la fiche × packs, jamais la capacité utile supposée) ;
  `views/schema.py::CLES_SCHEMA` + `calepinage_sld.json` (chaque état) + `test_calx204_contrat_sld.py::CLES_REPONSE`.
  Sélecteur `apps/calepinage/selectors.py::schema_electrique_du_calepinage(calepinage)` pour `apps/ventes`.
- [ ] SCHEL-B3 — devis : `electrical_service.py::schema_electrique_du_devis(devis, *, standard=False)` →
  `{options: {...}}` selon D-ACAL-131 ; `_option_choisie` accepte une variante IMPOSÉE (l'autre option, calcul
  `persister=False`) ; `unites` / `nombre` lus sur les lignes de l'option. `diagram_views.py::schema_unifilaire_devis`
  ajoute `schema_electrique` au format json (+ `openapi_shapes.py`). `public_views.py` pose la clé additive derrière
  la case `sld` (fichier-mur, budget : ligne SCHEL-B3m) ; `proposal_data.json` (deux copies) porte la clé ;
  `test_pv81_proposition_sld.py` arme la liste blanche (aucune clé hors contrat, aucun prix, `prix_achat` absent).
- [ ] SCHEL-B3m — `backend/django_core/apps/ventes/public_views.py` : clé additive `schema_electrique`, lignes nettes attendues ≤ 12
- [ ] SCHEL-B4 — annexe PV46, nouveaux rendus seulement : `regles_calcul.py` gagne `COUPURE_SCHEMA_ELECTRIQUE =
  (2026, 11, 27)` (à confirmer avec Reda : jour suivant la décision, comme D-ACAL-102), `schema_electrique_ouvert(devis)`
  par `_ouvert_aux_nouveaux_rendus(devis, REGLES_POSE_REELLE_2111, …)` et son drapeau dans `drapeaux_nouveaux_rendus`
  posé SEULEMENT quand l'annexe est demandée ; `artefacts_rendu.py::_sld_svg` rend
  `core/electrique/schema_electrique.py::rendre_schema_electrique_svg(doc, langue)` (fr/en/ar comme le PDF) pour un
  devis ouvert, l'ancienne planche sinon. Même option qu'aujourd'hui. Nombre de pages inchangé
  (`test_quote_engine.py`), goldens de règles mis à jour (le drapeau n'existe que dans le cas ouvert). Si la page
  d'annexe change, budget : ligne SCHEL-B4m (à ne cocher que si le fichier est touché).
- [ ] SCHEL-B4m — `backend/django_core/apps/ventes/quote_engine/generate_devis_premium.py` : annexe PV46 au dessin neuf, lignes nettes attendues ≤ 10

Les lignes « m » portent le budget du fichier-mur sur UNE ligne (la garde `check_forme_code.py::FICHIER_MUR` ne lit
que la première ligne d'une tâche cochée, chemin exact entre accents graves).

Gardes vertes : `python scripts/check_api_shapes.py` (contrats, `proposal_data.json` complet), `lint-imports`
(`core` n'importe aucune app), `python scripts/check_forme_code.py` (fichiers-murs, fonctions neuves ≤ 60),
`flake8` + `py_compile` sur les `.py` touchés ; les modules de test ci-dessus jugés par la CI.

### E — front ERP (`@model:sonnet`)
Fichiers : `frontend/src/features/calepinage/SchemaUnifilairePanel.helpers.js`,
`frontend/src/features/calepinage/SchemaUnifilairePanel.jsx`,
`frontend/src/features/calepinage/atelier/coque/etapes/EtapeSchema.jsx`,
`frontend/src/features/ventes/ConceptionElectrique.jsx`, `frontend/src/styles/calepinage/53-etape-electrique.css`,
et les tests `frontend/src/features/calepinage/SchemaUnifilairePanel.test.jsx`,
`frontend/src/features/calepinage/atelier/coque/etapes/EtapeSchema.test.jsx`,
`frontend/src/features/ventes/ConceptionElectrique.test.jsx`. Fixtures : `fichierContrat('ventes',
'schema_electrique')` (`frontend/src/test/fixtures/contractSamples.js`, lecture seule) — jamais un mock écrit à la main
(PACT13).

- [ ] SCHEL-E1 — `planDepuisDocument(doc)` (helpers) : le plan d'aujourd'hui (bandes, rangées, coffrets, onduleur,
  blocs AC, liaisons, terre, légende) lu sur le `Doc` seul, + la carte batterie et sa liaison neutre ; `null` sans
  chaîne ni onduleur. `planSchemaEnBlocs` (l. 218, déjà > 100 lignes : ne grossit pas) devient l'appel de
  `planDepuisDocument(schema.schema_electrique)` ou disparaît ; fonctions neuves ≤ 60 lignes. `SchemaEnBlocs` dessine
  la batterie (clic → `CIBLE_DU_BLOC` de l'étape Électrique où la batterie se règle). Tests : les cas avec / sans
  batterie / champ sans découpage / standard du contrat.
- [ ] SCHEL-E2 — `EtapeSchema.jsx` lit `schema.schema_electrique` (plus `resultat/` pour le dessin ; `resultat`
  reste pour la phrase du côté réseau) ; libellés de `calepinage-maquettes.libelles.json` gardés.
- [ ] SCHEL-E3 — `ConceptionElectrique.jsx` : la planche affichée devient `SchemaEnBlocs` sur
  `schema_electrique.options` (bascule « Sans batterie / Avec batterie » quand les deux existent, l'option avec
  d'abord) ; l'esquisse historique n'est plus affichée ; le téléchargement PDF existant reste tel quel.

Gardes vertes : `npx eslint` sur les fichiers touchés, `npx vitest run` sur les trois tests, `python
scripts/check_api_shapes.py` (mocks sous contrat), `python scripts/check_forme_code.py`.

### W — site public `apps/web` (`@model:sonnet`)
Fichiers : `apps/web/src/lib/schemaElectrique.ts` (NOUVEAU — Nouveau fichier car : `proposition.ts` est un
fichier-mur de 5 000 lignes qui ne doit pas grossir ; lecture défensive du `Doc` + géométrie pure, testable),
`apps/web/src/components/proposition/SchemaElectrique.astro` (NOUVEAU — Nouveau fichier car : la page fait
11 000 lignes ; le dessin vit dans un composant), `apps/web/src/pages/proposition/[...token].astro` (section `#sld`
seulement + bascule d'option), `apps/web/tests/schemaElectrique.test.ts` (NOUVEAU — Nouveau fichier car : module
neuf), `apps/web/tests/propositionSldWJ128.test.ts`, `apps/web/tests/propositionSldViewerWJ129.test.ts`. Ne touche
PAS `apps/web/src/lib/proposition.ts` ni `apps/web/src/contract_samples/*` (lane B).

- [ ] SCHEL-W1 — `schemaElectrique.ts::parseSchemaElectrique(p)` (lit `schema_electrique.options`, rejette toute
  forme inattendue, ne fabrique aucune valeur) + `planSchema(doc)` (même géométrie que l'écran ERP, section 2) ;
  tests sur les trois exemples du contrat (lus dans `src/contract_samples/schema_electrique.json`).
- [ ] SCHEL-W2 — `SchemaElectrique.astro` : le SVG du `Doc`, textes en `data-i18n data-fr/data-en/data-ar` comme
  le reste de la page, couleurs de chaîne servies, le reste aux jetons de la page (`text-lune`, `cine-card`…) ; rendu
  dans `#sld-svg-wrap` (la visionneuse WJ129 et le bouton « Télécharger » continuent de cloner / sérialiser ce
  nœud). Un panneau par option servie ; celui de l'option cochée est visible (`selectedOption()` l. 8585, radios
  `input[name="option"]`, défaut `reco` l. 499) ; une option à `null` n'affiche aucun schéma. Sans
  `schema_electrique`, la section garde `sld_svg` comme aujourd'hui (aucune page ne régresse avant le déploiement
  du backend).

Gardes vertes : les tests `apps/web/tests` touchés (vitest), `astro check` / build du site, `python
scripts/check_api_shapes.py` (copie jumelle et chemins TS), `python scripts/check_forme_code.py`.

## 4. À faire confirmer par Reda
1. D-ACAL-131 (règle de source, un schéma par option, autre option calculée à la lecture sans écriture).
2. Annexe PDF d'un devis à deux options : aujourd'hui l'option « avec batterie » même quand le client a ACCEPTÉ
   « sans ». Recommandé : avant acceptation, inchangé ; après acceptation, l'option acceptée (`option_acceptee`).
   Non construit par ce lot.
3. La palette compte 8 couleurs (les 4 de la capture d'abord) ; au-delà de 4 chaînes, on continue avec sarcelle,
   rouge, violet, ocre plutôt que de répéter le bleu (une couleur = une chaîne, comme la carte et la 3D). Recommandé :
   garder les 8.
4. Coupure « nouveaux rendus » de l'annexe : le 27/11/2026 recommandé ; un devis envoyé avant garde l'annexe reçue.
   La page client, elle, est une vue en direct : elle change au déploiement.
5. La fiche devis ERP affichait l'esquisse historique qui additionne les panneaux des deux options : elle disparaît
   de l'écran (E3) ; son PDF téléchargeable et le dossier réglementaire (`views/regulatory.py::joindre_schema_unifilaire`)
   la gardent — à remplacer dans un lot suivant si Reda le veut.
6. Aucune protection batterie n'est dessinée (décision du 19/08/2026 : pas de fusible batterie). À reconfirmer
   pour le C&I haute tension (Deye 80 kW + BOS-B, 24/11) si Reda veut un sectionneur dessiné.
