# A1 - Calepinage BACKEND capability inventory (read-only)

Root: `backend/django_core`. Short paths: `AC` = `apps/calepinage`, `CC` = `core/calepinage` (pure engine), `SV` = `AC/services`, `ET` = `AC/services/etapes`.
Legend: A = computed AND served to a screen/PDF; B = computed server-side, no consumer proven; C = partial; D = absent.
Frontend-consumer proof method: `git grep` of route segment in `frontend/src` + `apps/web/src` (tests excluded), plus the documents/sorties inventories (frontend reads the `endpoint` from the served entry, `PanneauDocuments.jsx`). I did NOT open every screen; "A" for a computed item = a served endpoint/PDF section exists (frontend wiring checked only where stated).

## 0. Size metrics (measured)
- `AC/services/*.py`: ~108 top-level modules + `etapes/` (26 step modules) + `rapport/` (13) + `documents/` (8); ~53,900 lines in `services/*.py` top level (wc total).
- Core engine `CC`: ~35 modules + `surfaces/` (rectangle, polygone, arc, multi, sol, base) + `adaptateurs/villa.py` + `golden/` (frdisi_2026_07_27, villa). Plus `core/electrique/` (cables, chaines, nomenclature, note, onduleurs, protections, schema, types).
- Models in `AC/models.py`: 13 classes (Calepinage, CalepinageVersion, CalepinageVariante, ProvenanceTerrain(choices), PhotoSite, ReleveTerrain, ProfilTypeConsommation, ParametresCalepinage, GabaritDossierReglementaire, DossierReglementaire, PoseReelle, SystemeFixation, ComposantFixation).
- URLs: 9 explicit paths in `AC/urls.py` (moteur/calculer, moteur/pose, moteur/resultat/<job>, parametres/, parametres/suggestion-pente, parametres/profils-types, parametres/recalculer-simulations + router: `calepinages`, `gabarits-dossiers`) + 140 `@action` decorators in `AC/views/*` (grep count of `@action`) = ~150 endpoints. ~38 view modules.
- Tests: 491 `test_*` files in `AC/tests`, ~6,183 `def test_` (grep). Contract samples: 74 files in `AC/contract_samples/` (see section 6).
- pvlib: pinned `pvlib==0.16.1` in `requirements.txt` (decision CALX198); used ONLY as optional cross-check of the sun-position routine: `CC/soleil.py` docstring ("a `pvlib.solarposition.get_solarposition` quand pvlib est installe") + `AC/tests/test_calx146_soleil.py`. `AC/services/thermique.py` cites pvlib models in a docstring only (no import). No pvlib import in non-test code under `AC` (grep `pvlib` import = none).

## 1. Capability table

### 1. Weather
| Capability | Class | Evidence / note |
|---|---|---|
| PVGIS hourly series (seriescalc, plane-of-array, components gb/gd/gr, T2m, wind) | A | `SV/pvgis_serie.py::ClientPvgis.serie_irradiance`; chain input of `SV/chaine_pertes.py` |
| PVGIS TMY | A | `SV/pvgis_serie.py::ClientPvgis` (tmy base), `SV/temperatures_tmy.py::temperatures_tmy`, fixture `tests/fixtures_pvgis/tmy_casablanca.json` |
| Multi-year window (up to PLAFOND_FENETRE_ANNEES=10) + interannual variability | A | `SV/chaine_pertes.py::PLAFOND_FENETRE_ANNEES`, `SV/p50p90.py::variabilite_interannuelle` |
| Custom weather file import | C | `SV/meteo_fichier.py::lire_serie_meteo` + view `views/meteo_fichier.py`. ONLY a named-column CSV with ISO timestamps with explicit timezone and `gi_w_m2` (plane irradiance); hourly only. Missing: native PVsyst .MET, EPW, TMY3 CSV, Meteonorm formats; GHI-only files are REFUSED (`MOTIF_HORIZONTAL_SEUL`) because no transposition model exists |
| Meteonorm | D | no import path (only a label "Meteonorm (site.csv)" in `SV/rapport/site.py`, a deposited-file label) |
| P50/P75/P90/P95 | A | `SV/incertitude.py::bloc_incertitude/_quantiles` (Gaussian, `NormalDist.inv_cdf`, sigma from measured interannual + declared components), `SV/p50p90.py::bankable`; contract `calepinage_incertitude.json` |
| P99 | D | `DEPASSEMENTS` carries 75/90/95 only (not verified for 99; code takes any exceedance but only these are published) |
| Transposition model (Perez/Hay) | D | PVGIS does the GHI->plane transposition server-side (`pvcalculation=0`, angle/aspect sent); repo has none. `SV/pvgis_serie.py` comment: "aucune transposition horizontal -> plan" |

### 2. Horizon
| PVGIS horizon (printhorizon) | A | `SV/horizon.py::ClientHorizon`, view `views/horizon.py`, step `ET/horizon.py::appliquer`; frontend `horizon` segment used |
| Manual horizon edit / typed profile | A | `SV/horizon.py::_profil_saisi/profil_depuis_document` (source 'saisie', local to doc) |
| Horizon file import | D | none found |

### 3. Near shading
| 3D beam shading engine | B-ish / outside backend | computed IN THE BROWSER (Three.js atelier + `apps/web/src/lib/shadingEngine.ts`, `roofPro11/prefill.ts`); backend only CONSUMES the result in `roof_layout` v2 (`solarAccess`, `shading12x24`). So server has no shading engine |
| Hourly shade matrix 12x24 -> derates DIRECT component hour by hour | A | `ET/ombrage_proche.py::appliquer`; schema `contract_samples/roof_layout_v2.schema.json`; report `SV/rapport_ombrage.py` (`_matrice_12x24`, `html_carte_de_chaleur`) |
| Per-module solar access (TOF/TSRF per pan; per module values) | A | `ET/acces_module.py`, `SV/ombrage_chaines.py::acces_par_module`, `SV/orientation.py` (TOF/TSRF vs PVGIS optimalangles), `rapport-ombrage.pdf` |
| Per-module simulation | A | `SV/simulation_modules.py` + `production.modules` block |
| Inter-row self-shading (hourly, sun position) | A | `ET/inter_rangees.py::appliquer`, `CC/ombre_rangees.py::fraction_ombree` (+ `fraction_ombree_est_ouest`), `CC/soleil.py::position_solaire` |
| Electrical shading effect per string / bypass diode | C | `ET/mismatch_ombrage.py::appliquer` (string-level I-V dispersion from shade, optimizer/micro exempt via `CHAMPS_SANS_CONTRAINTE`); `SV/ombrage_chaines.py::ombrage_des_chaines`. Cell-level / bypass-diode submodule model ABSENT: step `diodes` is declared but permanently omitted ("non modelise en v1", `SV/chaine_pertes.py::ORDRE_ETAPES`) |
| Diffuse / sky-view factor | C | direct only is derated; diffuse and reflected untouched (`ET/ombrage_proche.py`). No sky-view factor computed server-side; web engine keeps a fixed 25 % diffuse share (`apps/web/src/lib/shadingEngine.ts`) |
| Iso-shading diagram data (sun-path/shadow chart) | D | grep `iso`/`heliodon`: only a heat map 12x24 in `SV/rapport_ombrage.py` |

### 4. Irradiance and module physics
| IAM | A | `ET/iam.py` (Fresnel default n=1.526, AR-coating option from datasheet) |
| Soiling monthly | A | `ET/salissure.py` (12 monthly values, input only, omitted if unset) |
| Snow loss monthly | C | `neige` slot in `ORDRE_ETAPES`; "poste mensuel saisi par la societe (CALX161)"; no etape module `neige.py` in `ET/` (not verified how applied; likely via shared monthly machinery) |
| Spectral | D | `spectral` permanently omitted v1 (`SV/chaine_pertes.py::TOUJOURS_OMISES` text) |
| Thermal model | A | `SV/thermique.py::temperature_cellule/perte_thermique` (Faiman/PVsyst with Uc/Uv + wind, else NOCT), step `ET/thermique.py`, hourly `t_cell_c` |
| LID | A | `ET/lid.py` |
| Module quality / tolerance | A | `ET/qualite_module.py` |
| Mismatch (manufacturer) | A | `ET/mismatch_fabricant.py` |
| Low-light behaviour | A | `ET/niveau_irradiance.py` (efficiency vs irradiance table, field `rendement_par_irradiance`); one-diode model: D (the docs say CALX198 "modele a une diode" was not built; pvlib adopted but not used for it) |
| Bifacial | C | `SV/bifacial.py`, `ET/bifacial.py`: gain "calcule et publie a part" (view factors/albedo/height/GCR); simplified, no hourly backside raytracing |
| Degradation year by year (25 y, linear/exponential) | A | `ET/vieillissement.py` -> `production.annees` |

### 5. Losses
| Ordered loss chain | A | `SV/chaine_pertes.py::ORDRE_ETAPES` (22 slots: horizon, ombrage_proche, acces_module, inter_rangees, bifacial, iam, spectral*, salissure, neige, niveau_irradiance, thermique, qualite_module, lid, mismatch_fabricant, mismatch_ombrage, diodes*, ohmique_dc, mppt, onduleur, ecretage, ohmique_ac, transformateur, auxiliaires, indisponibilite). *omitted always |
| Loss waterfall dataset + server SVG | A | `resultat['cascade']` (contract `calepinage_pertes_cascade.json`), `SV/diagramme_pertes.py` -> `GET calepinages/<pk>/diagramme-pertes.svg`; frontend `production/DiagrammePertes.jsx` |
| DC ohmic (from plan lengths) / AC ohmic | A | `ET/ohmique_dc.py`, `ET/ohmique_ac.py`, `SV/cables.py`, `SV/troncons.py` |
| Inverter efficiency curve eta(P), euro-eff fallback | A | `ET/onduleur.py` (field `ond_courbe_rendement`) |
| MPPT window hours (V out of range) | A | `ET/mppt.py` |
| Clipping | A | `ET/ecretage.py` |
| Transformer / auxiliaries / unavailability | A | `ET/transformateur.py`, `ET/auxiliaires.py`, `ET/indisponibilite.py` |
| Loss policy single-sum PVGIS | A | `SV/pertes_politique.py::politique_de_pertes` (loss is an input, no hidden 14 %) |

### 6. Components
| Module/inverter/battery/optimizer data model | A | `apps/stock/models_fiche_technique.py::FicheTechnique` (129 fields): module voc/isc/vmp/imp/noct/temp coeffs/bifacialite/`rendement_par_irradiance`; inverter `ond_n_mppt, ond_mppt_v_min/max, ond_v_max_abs, ond_i_max_mppt_a, ond_isc_max_mppt_a, ond_entrees_par_mppt, ond_chaines_max_par_mppt, ond_courbe_rendement, ond_rendement_euro/cec/max, ond_s_max_kva, ond_dc_max_kwc, ond_limitation_export, ond_cos_phi_*, ond_bat_*`; battery `bat_*` (kWh, DoD, C-rate, RT eff, chimie, cycles, retention, temp); optimizer `opt_*`. Read via `apps.stock.selectors.specs_for_produit` (`SV/equipements.py`, `SV/modules_stock.py`) |
| .PAN / .OND import | D | no parser (grep `.pan/.ond/importer_pan` = none in non-migration code) |
| Multi-MPPT, unequal strings per MPPT | A | `SV/chaines.py` (pan-by-pan), `SV/polystring.py` (several orientations on one MPPT input, never in one string), `SV/agregation_electrique.py` (energy per string/MPPT/inverter) |
| Optimizers | A | `ET/mismatch_ombrage.py::_optimiseur_du_document`, `opt_*` fields, `chaines.py` regime `sortie_regulee_optimiseur` |
| Micro-inverters | A | `SV/micro_onduleurs.py` (AC branches), `ET/mismatch_ombrage.py` exempt |
| Batteries / hybrid inverters | A | `SV/batterie.py` (6 strategies), `ET/batterie.py`, `ond_bat_*` fields; hybrid handled via those fields (brand-specific logic not verified) |

### 7. Electrical design
| Auto string sizing (Voc cold, Vmpp window, Imax) | A | `core/electrique/chaines.py`, `SV/electrique.py` (site cold/hot temperatures from TMY, CAL123, `temperatures_tmy`) |
| DC/AC ratio | A | `core/electrique/onduleurs.py::ratios` (ratio_dc_ac + alert threshold), report `SV/rapport/electrique.py` |
| Auto-stringing on layout (pan-by-pan, one azimuth per string) | A | `SV/chaines.py::concevoir_par_pan/affectation`, `SV/polystring.py` |
| Cable sizing and voltage drop, per-segment metre | A | `SV/cables.py`, `SV/troncons.py` (CALX224-226; routes `troncons`), `core/electrique/cables.py` |
| Cable schedule / cable routing | C | `SV/troncons.py` + `plan-cablage.pdf/.dxf` (`SV/documents/plan_cablage.py`); doc says "pas de routage de cables" automatic (`docs/moteur-calepinage.md` section 7) - metre from drawn/declared paths |
| Protections (fuses, breakers, SPD, DDR) with rule citation, overridable | A | `SV/protections.py`, `core/electrique/protections.py` |
| Earthing checklist | A | `SV/terre.py` |
| DC/AC combiner boxes | A | `SV/coffrets.py` |
| Grid connection / voltage rise limit | A | `SV/raccordement.py`, view `views/raccordement.py` (frontend 102 hits) |
| Single-line diagram generation, edit (labels/refs), SVG + DXF export | A | `SV/sld.py` (editable), `SV/sld_export.py`, view `views/schema.py` (`schema-unifilaire`, `schema-unifilaire.dxf`) |
| Standard selection (NF C 15-100 / IEC) | A | `SV/norme.py` |
| Autotransformer/MV design, string current mismatch IEC62548 detail | not verified | |

### 8. Mounting topologies
| Pitched roof | A | engine `CC/surfaces/{rectangle,polygone,arc,multi}.py`, DP exact + uniform phase (`CC/optimum.py`, `CC/pose_uniforme.py`) |
| Flat roof tilt frames, pitch / shading-free pitch / GCR | A | `CC/politique_pas.py`, `CC/ombre_rangees.py` (`elevation_critique_deg`, `jeu_libre_m`), ground-cover ratio measured in `CC/surfaces/sol.py` |
| East-west | A | `fraction_ombree_est_ouest`, `SV/polystring.py`, `SV/chaines.py` |
| Ground mount | C | `CC/surfaces/sol.py::SurfaceSol` (flat terrain, row pitch, GCR); not in JSON exchange contract at CAL88 time (docs: refused by serialiser) - current state not re-verified; pan genre `sol` handled in `SV/planche.py::LIBELLE_GENRE_SURFACE`; no terrain following (declared non-goal) |
| Carport / ombriere | C | genre `ombriere` in `SV/planche.py`, mode in `CC/contenance_declaree.py`; no specific structural/clearance model beyond declared capacity |
| Trackers + backtracking | D | declared non-goal (`docs/moteur-calepinage.md` section 7); only text citing PVsyst backtracking in `ET/inter_rangees.py` |
| Bifacial | C | see 4 |
| Metal-sheet (bac acier) pose mode | A | migration `0020_ciq112_mode_pose_bac_acier` |

### 9. Structural
| Ballast sheet, per-company parameters | A | `SV/lestage.py` (all coefficients SAISIS by company, no code constants; route `masse-lestage`) |
| Mounting BOM (rails, clamps, hooks) + rules | A | `SV/fixation.py`, `SV/catalogue_fixation.py`, models `SystemeFixation/ComposantFixation`, route `bom-fixation` |
| Attachment spacing / rail layout | A | `SV/rangees.py` (oriented row definition), fixation BOM |
| Wind/snow load calculation (Eurocode / NV65) | D | explicit non-objective; grep `Eurocode|NV65|EN 1991` = none. Only inputs entered by company in `lestage` section |

### 10. Storage and consumption
| Load profile (monthly + hourly, from invoices, presets, imported curve) | A | `SV/consommation.py`, `SV/courbe_charge.py`, model `ProfilTypeConsommation`, route `parametres/profils-types` |
| Self-consumption/coverage | A | `SV/autoconsommation.py` (COUV-AUTO rule), `ET/autoconsommation.py` |
| Battery dispatch simulation | A | `SV/batterie.py::simuler_batterie` - strategies `autoconso, peak_shaving, backup, decalage, plafond_injection, heures_tarif` |
| Export limit / zero injection | A | strategy `plafond_injection` + `SV/raccordement.py` |
| Peak shaving | A | strategy `peak_shaving` |
| EV / heat pump loads | A | `SV/charges.py::courbe_vehicule/courbe_pac` |
| Off-grid sizing (J days autonomy, risk) | A | `SV/hors_reseau.py::dimensionner_hors_reseau`, `ET/hors_reseau.py` |
| Pumping | A | `SV/pompage.py` (feeds `apps.ventes.solar_design.pumping_cycle_yield`; route `pompage`) |
| Battery ageing | A | in `batterie` block (vieillissement), field `bat_cycles_publies` |

### 11. Economics
| LCOE / NPV / IRR / payback inside calepinage | D | none (`LCOE` grep = 0; payback hits incidental). Money stays in `apps/ventes` (`SV/devis.py` only bridges: build/sync quote from layout). Frontend has `features/calepinage/economie/PanneauEconomie.jsx` (reads quote data, not served by calepinage backend) - not verified |

### 12. Optimisation and variants
| Variants per project, compare on production | A | model `CalepinageVariante`, `SV/variantes.py`, `SV/comparaison.py`, `comparatif.xlsx`, route `variantes`, contract `variantes_comparer.json` |
| Compare up to 5 projects | A | `SV/comparaison_projets.py`, route `comparer-projets` |
| Max-module layout optimum (exact DP) + proof regimes | A | `CC/optimum.py`, `CC/types.py::MethodePreuve` |
| Adverse sensitivities batch + applicable recommendations (gain recomputed) | B | `CC/sensibilites.py::batterie`, `CC/recommandations.py::proposer`; reached via `AC/moteur_service.py`/`views/moteur.py` (frontend has `moteur/calculer|pose` hits=5/4; `recommandations` consumer not verified) |
| Parametric sweeps (tilt/azimuth/pitch/DC-AC) | D | no sweep service (grep `balayage|sweep` only in `moteur_service.py` for phase sweep of pose); TOF vs PVGIS optimal angles only (`SV/orientation.py`) |
| Optimisation targets (target kWh / self-consumption) | D | only max-modules and sizing for contenance (`SV/contenance.py`, `CC/contenance_declaree.py`) |

### 13. Roof/site data
| Imagery provider/country settings | A | `SV/site.py` (CAL47), model section `imagerie` |
| Roof outline from OSM footprint | A | contract `calepinage_empreinte_osm.json` |
| DSM/LIDAR slope-azimuth suggestion | C | `SV/lidar_ign.py` - FRANCE ONLY (IGN LiDAR HD/RGE ALTI), route `suggestion-pente`; no Morocco source |
| Cadastre/parcel | D | declared non-objective |
| AI roof detection | D | declared non-objective (no computer vision) |
| Photos with scale calibration, field survey, visit data | A | model `PhotoSite`, `ReleveTerrain`, `SV/photos.py`, `SV/releve.py`, `SV/reprise_visite.py`; solveur de cotes `CC/solveur_cotes.py` |
| Plan import DXF/PDF vector | A | `SV/import_plan.py`, `analyse_plan.py` (ezdxf, PyMuPDF) |
| Elevation / terrain-following | D | declared non-goal |
| GPS handling | A | `SV/repere.py`, `CC/geo.py` |
| Public map draw -> lead -> calepinage | A | `SV/reprise_public.py`, contract `lead_layout_public.json` |

### 14. Deliverables
| Planche PDF/SVG | A | `SV/planche.py`, `planche.pdf/.svg` |
| Plan de pose / toiture / masse PDFs | A | `views/sorties.py` (`plan-pose.pdf`, `plan-toiture.pdf`, `plan-masse.pdf`) |
| Note de calcul PDF | A | `SV/note_calcul.py`, `note-calcul.pdf` |
| Technical study report (rapport-etude.pdf, composable sections) | A | `SV/rapport/` sections: systeme, site, production, pertes, electrique, ombrage, nomenclature, preuve, annexe_hypotheses, sections_societe; contract `rapport_etude.json`; company can choose sections (`documents.rapport_etude.sections`) |
| Shading report PDF | A | `SV/rapport_ombrage.py`, `rapport-ombrage.pdf` (heat map 12x24, monthly means, horizon table) |
| Wiring plan PDF/DXF; owner manual; as-built doc; compact one-page presentation | A | `SV/documents/{plan_cablage,manuel_proprietaire,document_asbuilt,presentation_compacte}.py`; no direct route-segment hit in frontend but served through the `documents`/`sorties` inventories whose `endpoint` the panel uses |
| DXF export (roof) / SLD DXF | A | `SV/export_dxf.py`, `SV/sld_export.py` |
| XLSX/CSV (modules, strings, BOM, hourly series, fixation lines) | A | `SV/export_tableur.py`, `SV/export_csv.py` (frontend `calepinage-...-horaire.csv`) |
| JSON project export/import | A | `SV/export_projet.py`, `views/projet_json.py` (`export-projet.json`, `import-projet`) |
| BOM | A | `SV/export_tableur.py` + `SV/fixation.py` + nomenclature `core/electrique/nomenclature.py` |
| Regulatory dossiers (prefilled, "a completer" never invented), gabarits | A | `SV/reglementaire.py`, `SV/gabarits.py`, models `DossierReglementaire/GabaritDossierReglementaire` |
| Technical pack (merged PDFs, 8 pieces) | A | `SV/pack_technique.py` (via `apps.ged.services.fusionner_pdf`) |
| Etiquettes | A | `SV/etiquettes.py` |
| 3D render image | C | sortie `image_3d` PNG (`views/sorties.py`); no shareable client 3D viewer / public link on backend (no token/public-link code in calepinage except `SV/assistant.py` grep hit) |
| As-built (posed vs planned) | A | `SV/asbuilt.py`, model `PoseReelle`, frontend `atelier/PoseReelle.jsx` |
| Bankable shading / bankable export | D by decision | `docs/moteur-calepinage.md` section 7: no bankable shading, export gated on AOF59 |

### 15. Workflow
| Versions, diff, restore | A | `CalepinageVersion`, `SV/versions.py`, `SV/diff_versions.py`, routes `versions`, `diff`, `restaurer` |
| Journal / chatter | A | `SV/journal.py`, route `chatter/noter` |
| Approval | A | `SV/approbation.py`, route `approbation`; field-test green light (`SV/feu_vert.py`, reuses visites feu vert) |
| Publication to quote | A | `SV/devis.py` (build/sync via `apps.ventes.services`), routes `generer-devis`, `publier-devis`, `sync-devis`, `publier-devis/apercu`; frontend segment `publier-devis` = 0 hits (consumer not proven) but `generer-devis`/`sync-devis` have hits |
| Library/templates/kits/presets | A | `SV/modeles.py`, `SV/presets.py`, `SV/kits.py`, `SV/kits_catalogue.py`, `SV/gabarits.py`, `views/bibliotheque.py` |
| Lifecycle statuses, archive, trash, duplicate | A | `SV/archivage.py`, `SV/creation.py`, routes `archiver`, `restaurer-corbeille`, `dupliquer` |
| Public API event | B | `selectors.py` comment + `SV/simulation.py` emits `calepinage.simule` to `apps.publicapi` (best effort) |
| Assistant/AI cards | A | `AC/assistant`, `views/assistant.py` (`a-traiter`, `du-lead`, `preparer`...), frontend `features/ia/cartes/modules/CartesCalepinage.jsx`; gated by flags below |

### 16. Validation
| Simulation vs PVGIS informative gap | A | `SV/validation.py` (CALX195, informative, never adjusts), `AC/tests/test_calx195_validation.py` |
| Goldens with reference values | A | `AC/tests/golden_simulation/{casablanca_ramadan, cascade_pluriannuelle_casablanca, multi_pans_est_ouest_un_onduleur}.json`, `AC/tests/test_calx196_golden.py`; engine goldens `CC/golden/frdisi_2026_07_27` (148/120/314 modules), `CC/golden/villa` |
| PVGIS fixtures | A | `AC/tests/fixtures_pvgis/` (seriescalc sud/est/ouest, components, tmy, printhorizon, pvcalc_optimalangles) |
| Benchmark vs PVsyst / PV*SOL reference numbers | D | no test comparing to a PVsyst run (the PVsyst mention in tests is a doc reference in docstrings; filenames with "pvsyst" hits are citations) |
| Solar position vs pvlib | A (test) | `AC/tests/test_calx146_soleil.py`, `CC/soleil.py` |

## 2. Counts (my classification of the ~125 capability lines above)
Approx: A ~ 88, B 2, C 13, D 14 (rows labelled "not verified" excluded). Exact counts are approximate: lines were not strictly one-per-capability.

D (absent): custom weather formats .MET/EPW/TMY3/Meteonorm (only POA CSV exists = C for file import, D for the formats); P99; transposition model (Perez/Hay) and GHI-only weather; horizon file import; iso-shading/sun-path diagram data; spectral; diodes / bypass-diode cell-level; one-diode model; .PAN/.OND import; trackers + backtracking; wind/snow load calculation; LCOE/NPV/IRR/payback; parametric sweeps; optimisation targets (kWh/self-consumption); cadastre; AI roof detection; DEM/terrain-following; shareable client 3D viewer / public link; PVsyst benchmark validation.

B (server-only, no proven consumer): sensitivities battery + recommandations (`CC/sensibilites.py`, `CC/recommandations.py`; frontend consumer not proven); public API event `calepinage.simule`; endpoints below.

C (partial, missing case): file weather (CSV POA only); electrical shading (string-level only, no sub-module/diode); diffuse shading (direct only, no SVF); bifacial (simplified gain, no raytracing); snow (input monthly, no etape module); ground mount (flat only, no terrain); carport (declared capacity only); cable routing (metre from paths, no auto routing); LIDAR (France only); 3D render (PNG only); wind/snow structural (company-entered inputs only); hybrid/battery brand logic (not verified).

## 3. Feature flags / settings that switch capabilities OFF by default
| Name | Default | Where read |
|---|---|---|
| `USE_MOTEUR_CALEPINAGE` | 0 (off) | `.env.example:378`; `apps/ventes/domain/geometrie.py::DRAPEAU_MOTEUR_CALEPINAGE`, `apps/ventes/domain/creation_calepinage.py`, `AC/management/commands/acal_dryrun_degagements.py`. Off => quote PDF/devis use legacy surface count, engine A/B (`apps.ventes.services.arbitrer_compte_calepinage`) |
| `ASSISTANT_COPILOTE`, `ASSISTANT_MOTEUR` | off (per memory MEMORY.md copilote entry; not re-read in this lane) | assistant cards for calepinage (`views/assistant.py`) - not verified in `AC` code |
| Company-level settings (empty = step omitted, never a default): `ParametresCalepinage.simulation` keys (soiling monthly, snow monthly, degradation model, sigma components, weather window/mode...), `electrique_societe`, `lestage`, `norme_electrique`, `documents` | empty (steps omitted with named reason, D-CALX 7 "zero invented number") | `AC/services/parametres_cles.py` (registry), `AC/models.py::ParametresCalepinage.SECTIONS`. Consequence: until set, soiling, snow, LID, quality, mismatch, transformer, auxiliaries, unavailability, ballast, sigma/P90 produce no value |
| Weather mode must be CHOSEN (series multiannual vs TMY) or simulation refused | none | `SV/simulation.py` (CALX153) |
| `ezdxf`, `PyMuPDF` required | installed | `requirements.txt` (ezdxf==1.4.5; weasyprint==70.0) |
No `getattr(settings, ...)` flag found in `AC` code apart from the above (grep). Module visibility via the module manifest key `calepinage`.

## 4. Endpoints without a frontend consumer proven (git grep of segment, tests excluded, in `frontend/src` + `apps/web/src`)
0 hits for the literal segment: `a-traiter`, `du-lead` (found instead as `a_traiter`/`du_lead` in `features/ia/cartes/contrats.js` -> consumed by assistant cards), `publier-devis` (0 literal hits; `publier-devis/apercu` = "apercu-document" 1 hit - likely consumed), `export.dxf` (roof DXF; "export-layout"/other DXF routes consumed, literal `export.dxf` not found - candidate B), `plan-cablage`, `plan-pose`, `plan-toiture`, `note-calcul`, `manuel-proprietaire`, `document-asbuilt`, `presentation-compacte` (these PDFs are served through the `documents`/`sorties` inventories; `PanneauDocuments.jsx` uses entries' `endpoint`, and has `plan_pose_pdf`, `plan_toiture_pdf`, `note_calcul_pdf`: so A). Low-hit (1 hit, check quality): `comparer-projets`, `diagramme-pertes`, `rapport-ombrage`, `rapport-etude`, `dossier-fin-chantier`, `joindre-piece`, `pack-technique`, `recalculer-simulations`, `demarquer-modele`, `plan-masse`, `export.csv`.
Real candidate B endpoints to double check: `export.dxf` (roof DXF), `publier-devis` (non-preview), `sync-devis` etc. have hits so fine. Not verified: `recommandations` / sensibilites endpoint (no route named so; lives behind `moteur/calculer`).

## 5. Architectural facts that bound the gap
- Engine `CC` is pure (stdlib + numpy, no Django); two consumers (`apps.ventes` villa, `apps.calepinage` atelier). Four proof regimes (`dp_exact_1cm`, `exhaustif_par_segment`, `heuristique_bornee`, `impose_utilisateur`), the word "prouve" never an opinion.
- Zero-invented-number doctrine (D-CALX 7): every loss step omitted with a named reason when its input is missing - so out-of-the-box numbers depend on company settings being filled.
- Shading is computed client-side (Three.js, `apps/web`); the backend takes the matrix/solarAccess from the saved `roof_layout` v2 document and only derates the direct component; exclusivity rule (D-CALX 16) avoids counting shade twice.
- PVGIS is the only weather provider besides the POA-CSV file; transposition is done by PVGIS.
- Money is out of scope in calepinage; quote bridge in `SV/devis.py`.

## 6. contract_samples (74 files) `AC/contract_samples/`
README.md, calepinage_{apercu_document, approbation, asbuilt_ecarts, assistant_a_traiter, assistant_contenance, assistant_du_lead, assistant_preparer, assistant_publier_apercu, assistant_publier_devis, assistant_resume, batterie, comparaison_projets, conception_du_devis, consommation_proposee, creation_conflit, design_context, detail, documents, du_devis, dupliquer, empreinte_osm, entree_electrique, equipements, etiquettes, export_layout, fixation_bom, horizon, import_plan, incertitude, layout_section, liste, masse_lestage, meteo, meteo_fichier, modeles, modules_disponibles, pertes, pertes_cascade, photos, plan_importe, pompage, profils_types, projet_json, publication, publication_electrique, raccordement, releve, releve_visite, resultat, serie_horaire, simulation, sld, sorties, suggestion_pente, troncons, variante_detail, variantes_liste, versions_diff, versions_liste}.json, dossiers_reglementaires.json, electrique_cheminements.json, electrique_equipements.json, export_projet.json, gabarits_dossier_reglementaire.json, lead_layout_public.json, moteur_calculer.json, parametres_calepinage.json, pose.json, rapport_etude.json, roof_layout_v2.schema.json, site_imagerie.json, variantes_comparer.json, zones.json.

## 7. What I could not verify
- Exact A/B/C/D counts are approximate (rows grouped).
- Whether `neige` has an etape implementation (no `ET/neige.py`; the chain slot and monthly-input text exist).
- Whether `SurfaceSol` is now serialised in the JSON contract (grep in `CC/serialisation.py` for `SurfaceSol`/`'sol'` returned nothing).
- Brand-specific hybrid/battery logic (Deye/Dyness) not found in calepinage services; the fields are generic (`ond_bat_*`, `bat_*`).
- Frontend consumption was proven only by route-segment text hits and the documents inventory, not by opening screens. No tests were run.
- `ASSISTANT_COPILOTE`/`ASSISTANT_MOTEUR` defaults come from project memory text, not re-read in code in this lane.
