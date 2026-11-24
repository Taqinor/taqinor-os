# Partie 2 — registre du préremplissage (ce qui est rempli, et d'où vient chaque valeur)

Écrit par script depuis les fichiers de recherche du 24/11/2026 (aucun chiffre retapé à la main). Tout ce qui suit
est appliqué à la COPIE anonymisée de la pile de revue seulement ; la production n'est jamais modifiée. Une ligne
« écart avec la fiche de production » est un constat pour le fondateur, pas une correction faite en production.

## 1. Recopié de la production (lecture seule du 24/11/2026)

- **93 fiches techniques** recopiées telles quelles : batterie 4, cable 14, limiteur 5, logger 2, module 3, onduleur 17, protection 41, structure 7.
- **Réglages du calepinage** : section `simulation` (albedo_mensuel, b0_iam, bifacial_mismatch_arriere_pct, mismatch_fabricant_pct, modele_iam, regle_qualite_module, resolution_minutes, thermique_par_pose), section `electrique_societe` (seuil_bas_dc_ac, tolerance_polystring_acceptable_pct, tolerance_polystring_bloquante_pct), section `norme_electrique` (norme, reference). Absents en production à cette date : le mode météo et ses années, la salissure, la dégradation initiale, l'indisponibilité, les pertes de câbles — donc, en production, « Remplir les réglages vides » n'a pas encore été appliqué après le déploiement du 23/11.
- **Forfaits C&I** (8 prestations, source écrite en production : « Reda (fondateur), 26/10/2026 ») ; délais « 48-72 h » (visite) et « 7-14 jours ouvrés » (installation).
- **Vides en production** (recopiés vides, à remplir ou à dire) : `agricole_marge_cable_descente_m`, `agricole_part_debit_forage_pct`, `agricole_salissure_supp_pct`, `bande_prix_kwc_ci`, `delai_intervention_suivi_heures`, `delai_reception_definitive_mois`, `entretien_minimum_mad_kwc_an`, `facteur_co2_reseau_date`, `facteur_co2_reseau_g_kwh`, `facteur_co2_reseau_source`, `garantie_production_autorisee`, `garantie_production_validation`, `recette_ecart_pmax_pct`, `recette_echantillon_iv_pct`, `recette_isolement_min_mohm`, `recette_pompage_ecart_max_pct`, `recette_pr_seuil_interne`.
- Profils de consommation de la société : **0** en production. Préférences de gammes : valeurs par défaut.

## 2. Panneaux et batteries — valeurs lues dans les fiches publiques des fabricants

### Panneau Canadien Solar 710W — PAN-CS-710

Modèle identifié : **Canadian Solar TOPBiHiKu7 CS7N-710TB-AG (N-type bifacial TOPCon, 132 half-cells)** · certitude : sure.

Note : Series datasheet printed for 695-730 W; 710 W row read (STC 710 W / 40.4 V / 17.59 A / 48.3 V / 18.59 A / 22.9 %; NMOT 537 W / 38.2 V / 14.06 A / 45.7 V / 14.99 A). 'Bifacial Gain' rows (5/10/20 %) are not the bifaciality factor.

| Champ | Valeur | Unité | Comme imprimé | Source | Date | Type |
|---|---|---|---|---|---|---|
| `temp_coeff_isc_pct_c` | 0.05 | %/°C | 0.05 % / °C | [Canadian Solar TOPBiHiKu7 CS7N-695-730TB-AG datasheet, V1.91_F43M_L4A_TX (canadiansolar.com)](https://www.canadiansolar.com/wp-content/uploads/sites/3/2026/05/CS-Datasheet-TOPBiHiKu7_CS7N-TB-AG_v1.91_F43M_L4A_TX.pdf) | May 2026 (V1.91) | fabricant |
| `noct_c` | 41 | °C (NMOT, tolerance ±3) | 41 ± 3°C — The datasheet publishes NMOT (800 W/m2, 20 C ambient, 1 m/s), not NOCT. Printed NMOT row for this model: Pmax 537 W. | [Canadian Solar TOPBiHiKu7 CS7N-695-730TB-AG datasheet, V1.91_F43M_L4A_TX (canadiansolar.com)](https://www.canadiansolar.com/wp-content/uploads/sites/3/2026/05/CS-Datasheet-TOPBiHiKu7_CS7N-TB-AG_v1.91_F43M_L4A_TX.pdf) | May 2026 (V1.91) | fabricant |
| `tolerance_pmax_min_pct` | 0 | W (printed in watts, not %) | 0 ~ + 10 W | [Canadian Solar TOPBiHiKu7 CS7N-695-730TB-AG datasheet, V1.91_F43M_L4A_TX (canadiansolar.com)](https://www.canadiansolar.com/wp-content/uploads/sites/3/2026/05/CS-Datasheet-TOPBiHiKu7_CS7N-TB-AG_v1.91_F43M_L4A_TX.pdf) | May 2026 (V1.91) | fabricant |
| `tolerance_pmax_max_pct` | 1.408 | % of Pmax (CONVERTED by us: 10 W / 710 W) | +10 W — Conversion is our arithmetic, not a maker figure: 10/710 = 1.408 %. | [Canadian Solar TOPBiHiKu7 CS7N-695-730TB-AG datasheet, V1.91_F43M_L4A_TX (canadiansolar.com)](https://www.canadiansolar.com/wp-content/uploads/sites/3/2026/05/CS-Datasheet-TOPBiHiKu7_CS7N-TB-AG_v1.91_F43M_L4A_TX.pdf) | May 2026 (V1.91) | fabricant |
| `bifacialite_pct` | 80 | % (Pmax rear/front; tolerance ±5 %) | 80 %  (Bifaciality Tolerance: ± 5 %) — Page 1 also says 'Up to 85% Power Bifaciality' (marketing line); the specification table says 80 %. | [Canadian Solar TOPBiHiKu7 CS7N-695-730TB-AG datasheet, V1.91_F43M_L4A_TX (canadiansolar.com)](https://www.canadiansolar.com/wp-content/uploads/sites/3/2026/05/CS-Datasheet-TOPBiHiKu7_CS7N-TB-AG_v1.91_F43M_L4A_TX.pdf) | May 2026 (V1.91) | fabricant |
| `cellules_serie` | 132 [2x (11 x6)] | cells (half-cell arrangement) | 132 [2x (11 x6) ] | [Canadian Solar TOPBiHiKu7 CS7N-695-730TB-AG datasheet, V1.91_F43M_L4A_TX (canadiansolar.com)](https://www.canadiansolar.com/wp-content/uploads/sites/3/2026/05/CS-Datasheet-TOPBiHiKu7_CS7N-TB-AG_v1.91_F43M_L4A_TX.pdf) | May 2026 (V1.91) | fabricant |
| `techno_cellule` | N-type Bifacial TOPCon |  | N-type Bifacial TOPCon Technology; Cell Type: TOPCon cells | [Canadian Solar TOPBiHiKu7 CS7N-695-730TB-AG datasheet, V1.91_F43M_L4A_TX (canadiansolar.com)](https://www.canadiansolar.com/wp-content/uploads/sites/3/2026/05/CS-Datasheet-TOPBiHiKu7_CS7N-TB-AG_v1.91_F43M_L4A_TX.pdf) | May 2026 (V1.91) | fabricant |

**Écarts avec la fiche de production :**
- Pmax 710 W, Voc 48.30 V, Isc 18.59 A, Vmp 40.40 V, Imp 17.59 A, efficiency 22.90 %, 2384x1303x35 mm, 37.9 kg, Voc coeff -0.25 %/C, Pmax coeff -0.29 %/C, bifacial=true: all match V1.91 / V1.9_NA (no mismatch).
- Revision caveat: V1.9_EN global (Apr 2025) prints 33 mm / 37.8 kg instead of 35 mm / 37.9 kg; the sheet follows V1.91 / V1.9_NA.
- Catalogue description says 'TOPHiKu7' (monofacial family name); sheet and matching datasheet are TOPBiHiKu7 (bifacial, '-TB-AG'). No monofacial CS7N-710 datasheet was found.

### Panneau Canadien Solar 715W (pk 128, sku null) — sans référence

Modèle identifié : **Canadian Solar TOPBiHiKu7 CS7N-715TB-AG (bifacial TOPCon, 132 half-cells)** · certitude : sure.

Note : 715 W row: STC Vmp 40.6 V, Imp 17.63 A, Voc 48.5 V, Isc 18.64 A; NMOT 541 W / 38.4 V / 14.09 A / 45.9 V / 15.03 A. Thickness/weight conflict between revisions (35 mm/37.9 kg vs 33 mm/37.8 kg): both in champs.

| Champ | Valeur | Unité | Comme imprimé | Source | Date | Type |
|---|---|---|---|---|---|---|
| `temp_coeff_isc_pct_c` | 0.05 | %/°C | 0.05 % / °C | [Canadian Solar TOPBiHiKu7 CS7N-695-730TB-AG datasheet, V1.91_F43M_L4A_TX (canadiansolar.com)](https://www.canadiansolar.com/wp-content/uploads/sites/3/2026/05/CS-Datasheet-TOPBiHiKu7_CS7N-TB-AG_v1.91_F43M_L4A_TX.pdf) | May 2026 (V1.91) | fabricant |
| `noct_c` | 41 | °C (NMOT, tolerance ±3) | 41 ± 3°C — The datasheet publishes NMOT (800 W/m2, 20 C ambient, 1 m/s), not NOCT. Printed NMOT row for this model: Pmax 541 W. | [Canadian Solar TOPBiHiKu7 CS7N-695-730TB-AG datasheet, V1.91_F43M_L4A_TX (canadiansolar.com)](https://www.canadiansolar.com/wp-content/uploads/sites/3/2026/05/CS-Datasheet-TOPBiHiKu7_CS7N-TB-AG_v1.91_F43M_L4A_TX.pdf) | May 2026 (V1.91) | fabricant |
| `tolerance_pmax_min_pct` | 0 | W (printed in watts, not %) | 0 ~ + 10 W | [Canadian Solar TOPBiHiKu7 CS7N-695-730TB-AG datasheet, V1.91_F43M_L4A_TX (canadiansolar.com)](https://www.canadiansolar.com/wp-content/uploads/sites/3/2026/05/CS-Datasheet-TOPBiHiKu7_CS7N-TB-AG_v1.91_F43M_L4A_TX.pdf) | May 2026 (V1.91) | fabricant |
| `tolerance_pmax_max_pct` | 1.399 | % of Pmax (CONVERTED by us: 10 W / 715 W) | +10 W — Conversion is our arithmetic, not a maker figure: 10/715 = 1.399 %. | [Canadian Solar TOPBiHiKu7 CS7N-695-730TB-AG datasheet, V1.91_F43M_L4A_TX (canadiansolar.com)](https://www.canadiansolar.com/wp-content/uploads/sites/3/2026/05/CS-Datasheet-TOPBiHiKu7_CS7N-TB-AG_v1.91_F43M_L4A_TX.pdf) | May 2026 (V1.91) | fabricant |
| `bifacialite_pct` | 80 | % (Pmax rear/front; tolerance ±5 %) | 80 %  (Bifaciality Tolerance: ± 5 %) — Page 1 also says 'Up to 85% Power Bifaciality' (marketing line); the specification table says 80 %. | [Canadian Solar TOPBiHiKu7 CS7N-695-730TB-AG datasheet, V1.91_F43M_L4A_TX (canadiansolar.com)](https://www.canadiansolar.com/wp-content/uploads/sites/3/2026/05/CS-Datasheet-TOPBiHiKu7_CS7N-TB-AG_v1.91_F43M_L4A_TX.pdf) | May 2026 (V1.91) | fabricant |
| `cellules_serie` | 132 [2x (11 x6)] | cells (half-cell arrangement) | 132 [2x (11 x6) ] | [Canadian Solar TOPBiHiKu7 CS7N-695-730TB-AG datasheet, V1.91_F43M_L4A_TX (canadiansolar.com)](https://www.canadiansolar.com/wp-content/uploads/sites/3/2026/05/CS-Datasheet-TOPBiHiKu7_CS7N-TB-AG_v1.91_F43M_L4A_TX.pdf) | May 2026 (V1.91) | fabricant |
| `techno_cellule` | N-type Bifacial TOPCon |  | N-type Bifacial TOPCon Technology; Cell Type: TOPCon cells | [Canadian Solar TOPBiHiKu7 CS7N-695-730TB-AG datasheet, V1.91_F43M_L4A_TX (canadiansolar.com)](https://www.canadiansolar.com/wp-content/uploads/sites/3/2026/05/CS-Datasheet-TOPBiHiKu7_CS7N-TB-AG_v1.91_F43M_L4A_TX.pdf) | May 2026 (V1.91) | fabricant |
| `epaisseur_mm` | 35 | mm | 2384 × 1303 × 35 mm — CONFLICT between revisions: V1.9_EN global (Apr 2025) prints 33 mm / 37.8 kg; V1.9_NA (on canadiansolar.com) and V1.91 (May 2026) print 35 mm / 37.9 kg. Both given. Thickness and weight are printed once for the whole series, not per model. | [Canadian Solar TOPBiHiKu7 CS7N-695-730TB-AG datasheet, V1.91_F43M_L4A_TX (canadiansolar.com)](https://www.canadiansolar.com/wp-content/uploads/sites/3/2026/05/CS-Datasheet-TOPBiHiKu7_CS7N-TB-AG_v1.91_F43M_L4A_TX.pdf) | May 2026 (V1.91) | fabricant |
| `epaisseur_mm_variante_V1.9_EN` | 33 | mm | 2384 × 1303 × 33 mm | [Canadian Solar TOPBiHiKu7 CS7N-TB-AG datasheet V1.9_EN (copy hosted by solarproof.com.au; the maker-hosted copy at static.csisolar.com could not be downloaded)](https://solarproof.com.au/datasheets/panel_datasheet_CS-Datasheet-TOPBiHiKu7_CS7N-TB-AG_v1.9_EN.pdf) | Apr. 2025 (V1.9_EN) | distributeur |
| `poids_kg` | 37.9 | kg | 37.9 kg (83.6 lbs) | [Canadian Solar TOPBiHiKu7 CS7N-695-730TB-AG datasheet, V1.91_F43M_L4A_TX (canadiansolar.com)](https://www.canadiansolar.com/wp-content/uploads/sites/3/2026/05/CS-Datasheet-TOPBiHiKu7_CS7N-TB-AG_v1.91_F43M_L4A_TX.pdf) | May 2026 (V1.91) | fabricant |
| `poids_kg_variante_V1.9_EN` | 37.8 | kg | 37.8 kg (83.3 lbs) | [Canadian Solar TOPBiHiKu7 CS7N-TB-AG datasheet V1.9_EN (copy hosted by solarproof.com.au; the maker-hosted copy at static.csisolar.com could not be downloaded)](https://solarproof.com.au/datasheets/panel_datasheet_CS-Datasheet-TOPBiHiKu7_CS7N-TB-AG_v1.9_EN.pdf) | Apr. 2025 (V1.9_EN) | distributeur |
| `epaisseur_mm_confirmation_V1.9_NA` | 35 | mm | 2384 × 1303 × 3 5 mm | [Canadian Solar TOPBiHiKu7 CS7N-TB-AG datasheet, V1.9_F43M_D1_NA (canadiansolar.com)](https://www.canadiansolar.com/wp-content/uploads/sites/3/2026/01/CS-Datasheet-TOPBiHiKu7_CS7N-TB-AG_v1.9_F43M_D1_NA.pdf) | Apr. 2025 (V1.9) | fabricant |

**Écarts avec la fiche de production :**
- Imp: sheet 18.00 A, datasheet 17.63 A -> MISMATCH.
- Isc: sheet 22.30 A, datasheet 18.64 A -> MISMATCH (22.30 is close to the 'Bifacial Gain 20 %' Isc rows, 22.31 A for 710 W / 22.37 A for 715 W; the sheet probably took a bifacial-gain row, not STC).
- Voc 48.50 V, Vmp 40.60 V, Pmax 715 W, 2384x1303 mm, Voc coeff -0.25, Pmax coeff -0.29 %/C: match.
- bifacial: sheet false, datasheet is a bifacial (TB-AG) module -> MISMATCH.
- rendement_pct empty in sheet; datasheet prints 23.0 % at STC (24.2 / 25.3 / 27.6 % at 5 / 10 / 20 % bifacial gain).

### Panneau Jinko 710W — PAN-JK-710

Modèle identifié : **JinkoSolar Tiger Neo JKM710N-66HL5-BDV (datasheet JKM710-735N-66HL5-BDV; bifacial dual glass, N-type TOPCon, 132 half-cells)** · certitude : probable.

Note : 'probable' only because of the bifacial flag; the electrical match is exact. Revisions Z3/Z4 (jinkosolar.eu) were not compared.

| Champ | Valeur | Unité | Comme imprimé | Source | Date | Type |
|---|---|---|---|---|---|---|
| `temp_coeff_isc_pct_c` | 0.045 | %/°C | 0.045 %/°C | [Jinko Solar 66HL5-BDV 710-735 Watt datasheet JKM710-735N-66HL5-BDV-Z5-EN (jinkosolar.com)](https://www.jinkosolar.com/uploads/JKM710-735N-66HL5-BDV-Z5-EN.pdf) | © 2026 (PDF created 2026-02-26; revision Z5) | fabricant |
| `tolerance_pmax_min_pct` | 0 | % | 0 ~ + 3 % | [Jinko Solar 66HL5-BDV 710-735 Watt datasheet JKM710-735N-66HL5-BDV-Z5-EN (jinkosolar.com)](https://www.jinkosolar.com/uploads/JKM710-735N-66HL5-BDV-Z5-EN.pdf) | © 2026 (PDF created 2026-02-26; revision Z5) | fabricant |
| `tolerance_pmax_max_pct` | 3 | % | 0 ~ + 3 % | [Jinko Solar 66HL5-BDV 710-735 Watt datasheet JKM710-735N-66HL5-BDV-Z5-EN (jinkosolar.com)](https://www.jinkosolar.com/uploads/JKM710-735N-66HL5-BDV-Z5-EN.pdf) | © 2026 (PDF created 2026-02-26; revision Z5) | fabricant |
| `bifacialite_pct` | 80 | % (φPmax, tolerance ±5 %); also φIsc 80±5 %, φVoc 98±5 % | φPmax: 80±5 % | [Jinko Solar 66HL5-BDV 710-735 Watt datasheet JKM710-735N-66HL5-BDV-Z5-EN (jinkosolar.com)](https://www.jinkosolar.com/uploads/JKM710-735N-66HL5-BDV-Z5-EN.pdf) | © 2026 (PDF created 2026-02-26; revision Z5) | fabricant |
| `cellules_serie` | 132 (66×2) | cells (half-cells) | 132 (66×2) | [Jinko Solar 66HL5-BDV 710-735 Watt datasheet JKM710-735N-66HL5-BDV-Z5-EN (jinkosolar.com)](https://www.jinkosolar.com/uploads/JKM710-735N-66HL5-BDV-Z5-EN.pdf) | © 2026 (PDF created 2026-02-26; revision Z5) | fabricant |

Non publié par le fabricant : {"champ": "noct_c", "documents_verifies": ["JKM710-735N-66HL5-BDV-Z5-EN.pdf (2 pages, read in full as image)", "same sheet, Z5-EU copy hosted by solarmagazine.nl"], "remarque": "No NOCT/NMOT line anywhere in the datasheet."}.

**Écarts avec la fiche de production :**
- Pmax 710 W, Vmp 40.65 V, Imp 17.47 A, Voc 48.73 V, Isc 18.53 A, efficiency 22.86 %, 2384x1303x33 mm, 37.5 kg, Voc coeff -0.25, Pmax coeff -0.29 %/C: all match the 710 W column.
- bifacial: sheet false; the only datasheet matching these values is a BIFACIAL dual-glass module (BDV) -> MISMATCH (a monofacial JKM710N-66HL5-V datasheet was searched and not found).
- techno_cellule 'N-type TOPCon (Tiger Neo)': consistent (page 1 cites TOPCon; the cell-type line says 'N- type Mono-crystalline').

### Batterie Dyness 5 kWh — BAT-DEY-5

Modèle identifié : **Dyness DL5.0C (5.12 kWh, 51.2 V, 100 Ah); DL5.0 (non-C) has the same electrical values** · certitude : probable.

Note : DL5.0C vs DL5.0 differ by weight (54 vs 44 kg), size (558x545x150 vs 481x535x140 mm), peak current (110 A vs 100 A, 15 s); the catalogue itself says 'Modele suppose DL5.0C - a confirmer fondateur'. Warranty is regional: DL5.0C Africa = 10 y, but 'DL5.0C V2' = 7 y unless extended; DL5.0 (Australia, 20240726) = 10 y, 70 % of usable energy, throughput 18.68 MWh. Africa edition read; Morocco applicability not verified.

| Champ | Valeur | Unité | Comme imprimé | Source | Date | Type |
|---|---|---|---|---|---|---|
| `bat_chimie` | LiFePO4 |  | LiFePO4 | [Dyness DL5.0C datasheet (German edition) V1.0-20240618](https://dyness.com/Public/Uploads/uploadfile/files/20241128/DynessDL5.0CdatasheetDE.pdf) | V1.0-20240618 | fabricant |
| `bat_garantie_annees` | 10 | years | ten (10) years — Africa edition (V2-202502): 'DL5.0C' battery unit = ten (10) years, BUT 'DL5.0C V2' = seven (7) years basic, ten (10) only with a purchased extension. Which variant is sold is unknown. | [Dyness Warranty Terms DL5.0C, 202410 Limited Warranty (EU wording; file on mea.dyness.com)](https://mea.dyness.com/Public/Uploads/uploadfile/files/20250716/DynessWarrantyTermsDL5.0C9020241201.pdf) | 202410 (EU wording) | fabricant |
| `bat_garantie_annees_Afrique_DL5.0C` | 10 | years | Ten (10) years | [Dyness Warranty Terms for Energy Storage Solutions - DL5.0C ESS System (Africa), V2-202502](https://dyness.com/Public/Uploads/uploadfile/files/20251022/DynessWarrantyTermsDL5.0Cfeizhouban2.pdf) | V2-202502 | fabricant |
| `bat_garantie_annees_Afrique_DL5.0C_V2` | 7 | years (basic; 10 with paid extension) | seven (7) years / Ten (10) years | [Dyness Warranty Terms for Energy Storage Solutions - DL5.0C ESS System (Africa), V2-202502](https://dyness.com/Public/Uploads/uploadfile/files/20251022/DynessWarrantyTermsDL5.0Cfeizhouban2.pdf) | V2-202502 | fabricant |
| `bat_retention_fin_de_vie_pct` | 70 | % of Nominal Energy at 10 years or at minimum throughput (whichever first) | seventy percent (70%) of the Nominal Energy — Throughput printed: 14.3 MWh (EU/MEA edition, DL5.0C, nominal 5.12 kWh). Africa edition: 70 % of Usable Energy, 15.090 MWh (DL5.0C) / 10.563 MWh basic and 15.090 MWh advanced (DL5.0C V2). Conditions: ambient 25~30 C, 0.2C CC/CV charge to 57.6 V, 0.2C discharge to 44.8 V; EU precondition table: 0.75C max continuous charge, 1C max continuous discharge, 90 % DoD, 1 full cycle/day. | [Dyness Warranty Terms DL5.0C, 202410 Limited Warranty (EU wording; file on mea.dyness.com)](https://mea.dyness.com/Public/Uploads/uploadfile/files/20250716/DynessWarrantyTermsDL5.0C9020241201.pdf) | 202410 (EU wording) | fabricant |
| `bat_cycles_publies` | 6000 | cycles (0.2C charge/discharge, 25 C, 90 % DoD) | 6000 Zyklen; [1] 0.2C Charging/Discharging, @25°, 90% DOD | [Dyness DL5.0C datasheet (German edition) V1.0-20240618](https://dyness.com/Public/Uploads/uploadfile/files/20241128/DynessDL5.0CdatasheetDE.pdf) | V1.0-20240618 | fabricant |
| `bat_v_nominal` | 51.2 | V | 51.2V | [Dyness DL5.0C datasheet (German edition) V1.0-20240618](https://dyness.com/Public/Uploads/uploadfile/files/20241128/DynessDL5.0CdatasheetDE.pdf) | V1.0-20240618 | fabricant |
| `bat_kwh_nominal` | 5.12 | kWh | 5.12 kWh | [Dyness DL5.0C datasheet (German edition) V1.0-20240618](https://dyness.com/Public/Uploads/uploadfile/files/20241128/DynessDL5.0CdatasheetDE.pdf) | V1.0-20240618 | fabricant |
| `bat_dod_pct` | 90 | % | 90% | [Dyness DL5.0C datasheet (German edition) V1.0-20240618](https://dyness.com/Public/Uploads/uploadfile/files/20241128/DynessDL5.0CdatasheetDE.pdf) | V1.0-20240618 | fabricant |

Non publié par le fabricant : {"champ": "bat_rendement_ar_pct", "documents_verifies": ["DL5.0C datasheet DE V1.0-20240618", "DL5.0 datasheet EN V1.0-20240112", "DL5.0C warranty Africa V2-202502 and EU 202410"], "remarque": "No round-trip efficiency published."}.

**Écarts avec la fiche de production :**
- bat_max_modules_par_banc: sheet 200; DL5.0C and DL5.0 datasheets print 'Up to 50 units in parallel' -> MISMATCH.
- bat_rendement_ar_pct 98 %: NOT found in the DL5.0C / DL5.0 datasheets or warranty terms read -> unsourced.
- bat_kwh_usable 4.60: 90 % x 5.12 = 4.608; DL5.0 AU warranty prints 4.61; Africa DL5.0C warranty table prints 'Usable Energy 5.12' -> minor, inconsistent between documents.
- Match: 5.12 kWh, 51.2 V, DoD 90 %, charge 75 A max x 51.2 V = 3.84 kW, discharge 100 A max = 5.12 kW, 6000 cycles.

### Batterie Dyness 10 kWh — BAT-DEY-10

Modèle identifié : **Dyness Powerbox Pro 10.24 kWh (51.2 V, 200 Ah)** · certitude : probable.

Note : Powerbox G2 (also 10.24 kWh) was checked and excluded (95 % DoD, 9.728 kWh usable, 'unlimited cycles'). Catalogue says 'Modele suppose Powerbox Pro 10.24 - a confirmer fondateur', hence 'probable'. Warranty throughput differs by region: EU 28.59 MWh (usable 9.216) vs AU 37.37 MWh (nominal 10.24).

| Champ | Valeur | Unité | Comme imprimé | Source | Date | Type |
|---|---|---|---|---|---|---|
| `bat_chimie` | LiFePO4 |  | LiFePO4 | [Dyness Powerbox Pro datasheet, file version 20241231-EN](https://ua.dyness.com/Public/Uploads/uploadfile/files/20250102/PowerboxProdatasheetEN20241231.pdf) | 20241231 | fabricant |
| `bat_garantie_annees` | 10 | years | Ten (10) years — Australia edition (V1.0-202407, au.dyness.com/.../20250813/DynessWarrantyTermsPowerboxPro.pdf) also: 'The Products warranty period is ten (10) years from the warranty start date.' | [Dyness Warranty Terms - PowerBox Pro ESS System (Europe), V2-202502](https://www.dyness.com/Public/Uploads/uploadfile/files/20251022/DynessWarrantyTermsPowerBoxPro10nianouzhou2025071.pdf) | V2-202502 | fabricant |
| `bat_retention_fin_de_vie_pct` | 70 | % of Usable Energy at 10 years or at minimum throughput (whichever first) | seventy percent (70%) of its Usable Energy — EU table: Usable Energy 9.216 kWh, Minimum Throughput 28.59 MWh. Australia edition (separate doc): 70 % of Nominal Energy 10.24 kWh, Minimum Energy Throughput 37.37 MWh. Measurement 25~30 C, 0.2C CC/CV 57.6 V, discharge 0.2C to 44.8 V. | [Dyness Warranty Terms - PowerBox Pro ESS System (Europe), V2-202502](https://www.dyness.com/Public/Uploads/uploadfile/files/20251022/DynessWarrantyTermsPowerBoxPro10nianouzhou2025071.pdf) | V2-202502 | fabricant |
| `bat_cycles_publies` | 6000 | cycles (>=; 0.2C, 25 C, 90 % DoD) | ≥6000 Cycles; * Test conditions: 0.2C Charging& Discharging. @25°C, 90% DOD | [Dyness Powerbox Pro datasheet, file version 20241231-EN](https://ua.dyness.com/Public/Uploads/uploadfile/files/20250102/PowerboxProdatasheetEN20241231.pdf) | 20241231 | fabricant |
| `bat_v_nominal` | 51.2 | V | 51.2V | [Dyness Powerbox Pro datasheet, file version 20241231-EN](https://ua.dyness.com/Public/Uploads/uploadfile/files/20250102/PowerboxProdatasheetEN20241231.pdf) | 20241231 | fabricant |
| `bat_kwh_nominal` | 10.24 | kWh | 10.24 kWh | [Dyness Powerbox Pro datasheet, file version 20241231-EN](https://ua.dyness.com/Public/Uploads/uploadfile/files/20250102/PowerboxProdatasheetEN20241231.pdf) | 20241231 | fabricant |
| `bat_kwh_usable` | 9.216 | kWh | 9.216 | [Dyness Warranty Terms - PowerBox Pro ESS System (Europe), V2-202502](https://www.dyness.com/Public/Uploads/uploadfile/files/20251022/DynessWarrantyTermsPowerBoxPro10nianouzhou2025071.pdf) | V2-202502 | fabricant |

Non publié par le fabricant : {"champ": "bat_rendement_ar_pct", "documents_verifies": ["Powerbox Pro datasheet 20241231-EN", "Powerbox Pro warranty EU V2-202502 and AU V1.0-202407"], "remarque": "No round-trip efficiency published."}.

**Écarts avec la fiche de production :**
- bat_max_modules_par_banc: sheet 5; datasheet 20241231-EN prints 'Up to 10 units in parallel' -> MISMATCH (an older AU/NZ datasheet reportedly says 5, not read by us).
- bat_rendement_ar_pct 98 %: not found in datasheet or warranty documents -> unsourced.
- Match: 10.24 kWh, 51.2 V, usable 9.216 (sheet 9.22), DoD 90 %, 5.12 kW nominal power, 6000 cycles.

### Batterie Dyness PowerBrick SC 16 kWh (pk 215, sku null) — sans référence

Modèle identifié : **Dyness PowerBrick SC (16.08 kWh, 51.2 V, 314 Ah)** · certitude : sure.

Note : Weight 116 kg, 435/233/857 mm, IP20. The product page also says '10 years warranty' and '8000+ cycles'.

| Champ | Valeur | Unité | Comme imprimé | Source | Date | Type |
|---|---|---|---|---|---|---|
| `bat_chimie` | LiFePO4 (LFP) |  | LiFePO4 (LFP) | [Dyness PowerBrick SC datasheet, file version 20260520-EN (apac.dyness.com)](https://apac.dyness.com/Public/Uploads/uploadfile/files/20260729/DynessPowerBrickSCDatasheeten20260520.pdf) | 20260520 | fabricant |
| `bat_garantie_annees` | 10 | years | 10 Years — Footnote [2] says 'Refer to Dyness Warranty Letter'; no PowerBrick SC warranty letter was found/read. | [Dyness PowerBrick SC datasheet, file version 20260520-EN (apac.dyness.com)](https://apac.dyness.com/Public/Uploads/uploadfile/files/20260729/DynessPowerBrickSCDatasheeten20260520.pdf) | 20260520 | fabricant |
| `bat_retention_fin_de_vie_pct` | 70 | % (EOL criterion of the cycle-life test) | 70%EOL — This is the capacity at which the >=8000-cycle figure is quoted, NOT a warranty clause; the warranty letter (retention at end of warranty, throughput) was not found. | [Dyness PowerBrick SC datasheet, file version 20260520-EN (apac.dyness.com)](https://apac.dyness.com/Public/Uploads/uploadfile/files/20260729/DynessPowerBrickSCDatasheeten20260520.pdf) | 20260520 | fabricant |
| `bat_cycles_publies` | 8000 | cycles (>=; 0.2C, 25 C, 95 % DoD, to 70 % EOL) | ≥8000 Cycles | [Dyness PowerBrick SC datasheet, file version 20260520-EN (apac.dyness.com)](https://apac.dyness.com/Public/Uploads/uploadfile/files/20260729/DynessPowerBrickSCDatasheeten20260520.pdf) | 20260520 | fabricant |
| `bat_kwh_nominal` | 16.08 | kWh | 16.08 kWh | [Dyness PowerBrick SC datasheet, file version 20260520-EN (apac.dyness.com)](https://apac.dyness.com/Public/Uploads/uploadfile/files/20260729/DynessPowerBrickSCDatasheeten20260520.pdf) | 20260520 | fabricant |
| `bat_kwh_usable` | 15.28 | kWh | 15.28 kWh | [Dyness PowerBrick SC datasheet, file version 20260520-EN (apac.dyness.com)](https://apac.dyness.com/Public/Uploads/uploadfile/files/20260729/DynessPowerBrickSCDatasheeten20260520.pdf) | 20260520 | fabricant |
| `bat_v_nominal` | 51.2 | V | 51.2 V | [Dyness PowerBrick SC datasheet, file version 20260520-EN (apac.dyness.com)](https://apac.dyness.com/Public/Uploads/uploadfile/files/20260729/DynessPowerBrickSCDatasheeten20260520.pdf) | 20260520 | fabricant |
| `bat_dod_pct` | 95 | % | 95% | [Dyness PowerBrick SC datasheet, file version 20260520-EN (apac.dyness.com)](https://apac.dyness.com/Public/Uploads/uploadfile/files/20260729/DynessPowerBrickSCDatasheeten20260520.pdf) | 20260520 | fabricant |
| `puissance_recommandee_kw` | 7.168 | kW | 7.168 kW | [Dyness PowerBrick SC datasheet, file version 20260520-EN (apac.dyness.com)](https://apac.dyness.com/Public/Uploads/uploadfile/files/20260729/DynessPowerBrickSCDatasheeten20260520.pdf) | 20260520 | fabricant |
| `puissance_max_charge_decharge_kw` | 10.24 | kW | 10.24 kW | [Dyness PowerBrick SC datasheet, file version 20260520-EN (apac.dyness.com)](https://apac.dyness.com/Public/Uploads/uploadfile/files/20260729/DynessPowerBrickSCDatasheeten20260520.pdf) | 20260520 | fabricant |

Non publié par le fabricant : {"champ": "bat_rendement_ar_pct", "documents_verifies": ["PowerBrick SC datasheet 20260520-EN (2 pages, read as images)", "apac.dyness.com product page"], "remarque": "No round-trip efficiency published."}; {"champ": "warranty letter (retention at end of warranty, throughput)", "documents_verifies": ["searched dyness.com warranty PDFs: none for PowerBrick SC found"], "remarque": "Datasheet footnote refers to a 'Dyness Warranty Letter' that was not located; only the datasheet's 10 years and '70%EOL' are sourced."}.

**Écarts avec la fiche de production :**
- bat_kwh_usable: sheet 15.27, datasheet 15.28 -> minor mismatch (16.08 x 0.95 = 15.276).
- bat_max_charge_kw / bat_max_decharge_kw 7.17: this is the 'Recommended Charge & Discharge Power 7.168 kW'; the datasheet 'Max. Charge/Discharge Power' is 10.24 kW (200 A) -> the sheet's 'max' holds the recommended value.
- Match: 16.08 kWh, 51.2 V, DoD 95 %, >=8000 cycles, -20..55 C discharge (charge 0..55 C, -20 C optional), up to 50 units in parallel.

### Batterie Deye BOS-B Pro haute tension - 16 kWh — BAT-DYN-HV-16

Modèle identifié : **Deye BOS-B-Pack16-A3 module (BOS-B Pro-A3 system; control box BOS-B-PDU-2-A)** · certitude : sure.

Note : Round-trip 95 % comes from Annex I 'Manufacturer Self Declaration' of the manual, not from the sales datasheet. Datasheet hosted on Deye's AU site; its PDF title says EU brochure 20260226 V1.0.

| Champ | Valeur | Unité | Comme imprimé | Source | Date | Type |
|---|---|---|---|---|---|---|
| `bat_chimie` | LiFePO4 |  | LiFePO₄ | [Deye Installation and Operation Instructions, Lithium-ion Rechargeable Battery System BOS-B Pro-A3, Issue 04](https://deye.com/wp-content/uploads/2025/11/deye-ess-user-manual-bos-b-pro-a3-euen-v04-_2025011131.pdf) | Issue04, 2025-11-13 | fabricant |
| `bat_garantie_annees` | 10 | years | 10 years — Warranty conditions (throughput, retention clause) are not in the datasheet or manual read; no Deye warranty statement was fetched. | [Deye BOS-B Pro-A3 datasheet (PDF title 'Deye BOS-B Pro-A3 Brochure_EU_202602261V1.0'), au.deyeinverter.com](https://au.deyeinverter.com/deyeinverter/2026/06/05/BOS-BPro-A3Datasheet.pdf) | upload path 2026-06-05; doc ref 20260226 V1.0 | fabricant |
| `bat_retention_fin_de_vie_pct` | 70 | % (EOL) at >=6000 cycles | 25±2°C, 0.5C / 0.5C, EOL70%≥6000 — Manual Annex I (manufacturer self-declaration): 'Capacity Fading 6000 Cycles, fade≤30%' (0.5C, 90% DOD, 25±3 C) and 'Cycle Life ≥6000@70%SOH, 10 years'. End-of-life criterion, not a warranty clause. | [Deye BOS-B Pro-A3 datasheet (PDF title 'Deye BOS-B Pro-A3 Brochure_EU_202602261V1.0'), au.deyeinverter.com](https://au.deyeinverter.com/deyeinverter/2026/06/05/BOS-BPro-A3Datasheet.pdf) | upload path 2026-06-05; doc ref 20260226 V1.0 | fabricant |
| `bat_rendement_ar_pct` | 95 | % (energy efficiency E0/E1, 0.5C, 25±3 C; manufacturer self-declaration) | 95% — Test method: 0.5C CC 3.65 V charge (E1), discharge to 2.5 V (E0), E0/E1 = DC round trip of the pack. 'Energy efficiency Fading: 10 years, fade ≤3 %'. | [Deye Installation and Operation Instructions, Lithium-ion Rechargeable Battery System BOS-B Pro-A3, Issue 04](https://deye.com/wp-content/uploads/2025/11/deye-ess-user-manual-bos-b-pro-a3-euen-v04-_2025011131.pdf) | Issue04, 2025-11-13 | fabricant |
| `bat_cycles_publies` | 6000 | cycles (>=; 0.5C/0.5C, 25±2 C, EOL 70 %); 90 % recommended DoD | EOL70%≥6000 | [Deye BOS-B Pro-A3 datasheet (PDF title 'Deye BOS-B Pro-A3 Brochure_EU_202602261V1.0'), au.deyeinverter.com](https://au.deyeinverter.com/deyeinverter/2026/06/05/BOS-BPro-A3Datasheet.pdf) | upload path 2026-06-05; doc ref 20260226 V1.0 | fabricant |
| `bat_v_nominal` | 51.2 | V (per module; modules stack in series, 5-16) | 51.2 | [Deye BOS-B Pro-A3 datasheet (PDF title 'Deye BOS-B Pro-A3 Brochure_EU_202602261V1.0'), au.deyeinverter.com](https://au.deyeinverter.com/deyeinverter/2026/06/05/BOS-BPro-A3Datasheet.pdf) | upload path 2026-06-05; doc ref 20260226 V1.0 | fabricant |
| `bat_kwh_nominal` | 16.08 | kWh | 16.08kWh | [Deye BOS-B Pro-A3 datasheet (PDF title 'Deye BOS-B Pro-A3 Brochure_EU_202602261V1.0'), au.deyeinverter.com](https://au.deyeinverter.com/deyeinverter/2026/06/05/BOS-BPro-A3Datasheet.pdf) | upload path 2026-06-05; doc ref 20260226 V1.0 | fabricant |
| `bat_dod_pct` | 90 | % | 90% | [Deye BOS-B Pro-A3 datasheet (PDF title 'Deye BOS-B Pro-A3 Brochure_EU_202602261V1.0'), au.deyeinverter.com](https://au.deyeinverter.com/deyeinverter/2026/06/05/BOS-BPro-A3Datasheet.pdf) | upload path 2026-06-05; doc ref 20260226 V1.0 | fabricant |
| `bat_kwh_usable_systeme_5_modules` | 72.27 | kWh (BOS-B80 Pro-A3: 5 modules, 80.3 kWh) | 72.27 — Usable energy is published only per rack: 72.27 kWh for 5 modules; manual: 217.1 kWh for 15 modules (241.2 kWh nominal). Not published per module. | [Deye BOS-B Pro-A3 datasheet (PDF title 'Deye BOS-B Pro-A3 Brochure_EU_202602261V1.0'), au.deyeinverter.com](https://au.deyeinverter.com/deyeinverter/2026/06/05/BOS-BPro-A3Datasheet.pdf) | upload path 2026-06-05; doc ref 20260226 V1.0 | fabricant |
| `bat_courant_max_a` | 180 | A | 180A — Manual 4.3: recommended 157 A, max 180 A. | [Deye BOS-B Pro-A3 datasheet (PDF title 'Deye BOS-B Pro-A3 Brochure_EU_202602261V1.0'), au.deyeinverter.com](https://au.deyeinverter.com/deyeinverter/2026/06/05/BOS-BPro-A3Datasheet.pdf) | upload path 2026-06-05; doc ref 20260226 V1.0 | fabricant |

Non publié par le fabricant : {"champ": "bat_kwh_usable (per module)", "documents_verifies": ["BOS-BPro-A3Datasheet.pdf", "manual Issue04"], "remarque": "Only system-level usable energy printed."}; {"champ": "warranty conditions (throughput / retention clause)", "documents_verifies": ["datasheet", "manual Issue04"], "remarque": "Only '10 years'; no warranty statement read."}.

**Écarts avec la fiche de production :**
- Match: 16.08 kWh, DoD 90 %, 6000 cycles; max charge/discharge 9.22 kW = 180 A x 51.2 V (datasheet prints 180 A max; manual: 157 A recommended, Annex I power 8038 W).
- bat_kwh_usable empty in sheet: usable is published only per rack (72.27 kWh for 5 modules / 217.1 kWh for 15), implying 90 % of nominal; a per-module 14.47 kWh would be OUR computation (16.08 x 0.9), not a maker figure.
- Not a sheet field but noted: module weight 126 kg (datasheet) vs 122 kg (manual issue 04).

## 3. Onduleurs — valeurs lues dans les fiches publiques des fabricants

### Onduleur hybride Deye 10kW Triphasé — OND-H-DEY-10T

Modèle identifié : **Deye SUN-10K-SG05LP3-EU-SM2** · certitude : sure.

Note : Model confirmed by the catalogue description ("Modele confirme fondateur: SUN-10K-SG05LP3-EU-SM2"). ond_conso_nuit_w: not published - the Deye documents read print no standby / night / self-consumption row. Checked: datasheet 20260911, manual 20261029 section 8 (full spec table), older datasheet 240722.

| Champ | Valeur | Unité | Comme imprimé | Source | Date | Type |
|---|---|---|---|---|---|---|
| `ond_n_mppt` | 2 |  | 2/2+2 | [Deye - Three Phase Hybrid Inverter SUN-3/4/5/6/8/10/12K-SG05LP3-EU-SM2 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/09/14/BDatasheetSUN-3-12K-SG05LP3-EU-SM220260911en.pdf) | 20260911 (from file name; no date printed in the document) | fabricant |
| `ond_mppt_v_min` | 200 | V | 200-650 | [Deye - Three Phase Hybrid Inverter SUN-3/4/5/6/8/10/12K-SG05LP3-EU-SM2 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/09/14/BDatasheetSUN-3-12K-SG05LP3-EU-SM220260911en.pdf) | 20260911 (from file name; no date printed in the document) | fabricant |
| `ond_mppt_v_max` | 650 | V | 200-650 | [Deye - Three Phase Hybrid Inverter SUN-3/4/5/6/8/10/12K-SG05LP3-EU-SM2 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/09/14/BDatasheetSUN-3-12K-SG05LP3-EU-SM220260911en.pdf) | 20260911 (from file name; no date printed in the document) | fabricant |
| `ond_v_max_abs` | 800 | V | 800 | [Deye - Three Phase Hybrid Inverter SUN-3/4/5/6/8/10/12K-SG05LP3-EU-SM2 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/09/14/BDatasheetSUN-3-12K-SG05LP3-EU-SM220260911en.pdf) | 20260911 (from file name; no date printed in the document) | fabricant |
| `ond_i_max_mppt_a` | 26 | A | 26+26 | [Deye - Three Phase Hybrid Inverter SUN-3/4/5/6/8/10/12K-SG05LP3-EU-SM2 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/09/14/BDatasheetSUN-3-12K-SG05LP3-EU-SM220260911en.pdf) | 20260911 (from file name; no date printed in the document) | fabricant |
| `ond_isc_max_mppt_a` | 39 | A | 39+39 | [Deye - Three Phase Hybrid Inverter SUN-3/4/5/6/8/10/12K-SG05LP3-EU-SM2 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/09/14/BDatasheetSUN-3-12K-SG05LP3-EU-SM220260911en.pdf) | 20260911 (from file name; no date printed in the document) | fabricant |
| `ond_ac_kw` | 10.0 | kW | 10000 W | [Deye - Three Phase Hybrid Inverter SUN-3/4/5/6/8/10/12K-SG05LP3-EU-SM2 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/09/14/BDatasheetSUN-3-12K-SG05LP3-EU-SM220260911en.pdf) | 20260911 (from file name; no date printed in the document) | fabricant |
| `ond_phases` | 3 |  | 3L+N+PE | [Deye - Three Phase Hybrid Inverter SUN-3/4/5/6/8/10/12K-SG05LP3-EU-SM2 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/09/14/BDatasheetSUN-3-12K-SG05LP3-EU-SM220260911en.pdf) | 20260911 (from file name; no date printed in the document) | fabricant |
| `ond_rendement_euro_pct` | 97.0 | % | 97.0% | [Deye - Three Phase Hybrid Inverter SUN-3/4/5/6/8/10/12K-SG05LP3-EU-SM2 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/09/14/BDatasheetSUN-3-12K-SG05LP3-EU-SM220260911en.pdf) | 20260911 (from file name; no date printed in the document) | fabricant |
| `ond_dc_max_kwc` | {"max_pv_access_power_kwp": 20.0, "max_pv_input_power_kwp": 16.0} | kWp | Max. PV access power 20000 W; Max. PV Input Power 16000 W | [Deye - Three Phase Hybrid Inverter SUN-3/4/5/6/8/10/12K-SG05LP3-EU-SM2 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/09/14/BDatasheetSUN-3-12K-SG05LP3-EU-SM220260911en.pdf) | 20260911 (from file name; no date printed in the document) | fabricant |
| `ond_bat_v_min` | 40 | V | 40-60 | [Deye - Three Phase Hybrid Inverter SUN-3/4/5/6/8/10/12K-SG05LP3-EU-SM2 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/09/14/BDatasheetSUN-3-12K-SG05LP3-EU-SM220260911en.pdf) | 20260911 (from file name; no date printed in the document) | fabricant |
| `ond_bat_v_max` | 60 | V | 40-60 | [Deye - Three Phase Hybrid Inverter SUN-3/4/5/6/8/10/12K-SG05LP3-EU-SM2 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/09/14/BDatasheetSUN-3-12K-SG05LP3-EU-SM220260911en.pdf) | 20260911 (from file name; no date printed in the document) | fabricant |

Non publié par le fabricant : ond_conso_nuit_w.

### Onduleur hybride Deye 5kW Triphasé — SUN-5K-SG05LP3

Modèle identifié : **Deye SUN-5K-SG05LP3-EU-SM2** · certitude : probable.

Note : SKU SUN-5K-SG05LP3 = 5K column of the SG05LP3-EU-SM2 family; the suffix -EU-SM2 is not in the SKU, hence probable. The existing sheet does NOT match this model (see ecarts): its values look like another product. ond_conso_nuit_w: not published - the Deye documents read print no standby / night / self-consumption row. Checked: datasheet 20260911, manual 20261029.

| Champ | Valeur | Unité | Comme imprimé | Source | Date | Type |
|---|---|---|---|---|---|---|
| `ond_n_mppt` | 2 |  | 2/1+1 | [Deye - Three Phase Hybrid Inverter SUN-3/4/5/6/8/10/12K-SG05LP3-EU-SM2 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/09/14/BDatasheetSUN-3-12K-SG05LP3-EU-SM220260911en.pdf) | 20260911 (from file name; no date printed in the document) | fabricant |
| `ond_mppt_v_min` | 200 | V | 200-650 | [Deye - Three Phase Hybrid Inverter SUN-3/4/5/6/8/10/12K-SG05LP3-EU-SM2 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/09/14/BDatasheetSUN-3-12K-SG05LP3-EU-SM220260911en.pdf) | 20260911 (from file name; no date printed in the document) | fabricant |
| `ond_mppt_v_max` | 650 | V | 200-650 | [Deye - Three Phase Hybrid Inverter SUN-3/4/5/6/8/10/12K-SG05LP3-EU-SM2 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/09/14/BDatasheetSUN-3-12K-SG05LP3-EU-SM220260911en.pdf) | 20260911 (from file name; no date printed in the document) | fabricant |
| `ond_v_max_abs` | 800 | V | 800 | [Deye - Three Phase Hybrid Inverter SUN-3/4/5/6/8/10/12K-SG05LP3-EU-SM2 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/09/14/BDatasheetSUN-3-12K-SG05LP3-EU-SM220260911en.pdf) | 20260911 (from file name; no date printed in the document) | fabricant |
| `ond_i_max_mppt_a` | 20 | A | 20+20 | [Deye - Three Phase Hybrid Inverter SUN-3/4/5/6/8/10/12K-SG05LP3-EU-SM2 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/09/14/BDatasheetSUN-3-12K-SG05LP3-EU-SM220260911en.pdf) | 20260911 (from file name; no date printed in the document) | fabricant |
| `ond_isc_max_mppt_a` | 30 | A | 30+30 | [Deye - Three Phase Hybrid Inverter SUN-3/4/5/6/8/10/12K-SG05LP3-EU-SM2 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/09/14/BDatasheetSUN-3-12K-SG05LP3-EU-SM220260911en.pdf) | 20260911 (from file name; no date printed in the document) | fabricant |
| `ond_ac_kw` | 5.0 | kW | 5000 W | [Deye - Three Phase Hybrid Inverter SUN-3/4/5/6/8/10/12K-SG05LP3-EU-SM2 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/09/14/BDatasheetSUN-3-12K-SG05LP3-EU-SM220260911en.pdf) | 20260911 (from file name; no date printed in the document) | fabricant |
| `ond_phases` | 3 |  | 3L+N+PE | [Deye - Three Phase Hybrid Inverter SUN-3/4/5/6/8/10/12K-SG05LP3-EU-SM2 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/09/14/BDatasheetSUN-3-12K-SG05LP3-EU-SM220260911en.pdf) | 20260911 (from file name; no date printed in the document) | fabricant |
| `ond_rendement_euro_pct` | 97.0 | % | 97.0% | [Deye - Three Phase Hybrid Inverter SUN-3/4/5/6/8/10/12K-SG05LP3-EU-SM2 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/09/14/BDatasheetSUN-3-12K-SG05LP3-EU-SM220260911en.pdf) | 20260911 (from file name; no date printed in the document) | fabricant |
| `ond_dc_max_kwc` | {"max_pv_access_power_kwp": 10.0, "max_pv_input_power_kwp": 8.0} | kWp | Max. PV access power 10000 W; Max. PV Input Power 8000 W | [Deye - Three Phase Hybrid Inverter SUN-3/4/5/6/8/10/12K-SG05LP3-EU-SM2 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/09/14/BDatasheetSUN-3-12K-SG05LP3-EU-SM220260911en.pdf) | 20260911 (from file name; no date printed in the document) | fabricant |
| `ond_bat_v_min` | 40 | V | 40-60 | [Deye - Three Phase Hybrid Inverter SUN-3/4/5/6/8/10/12K-SG05LP3-EU-SM2 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/09/14/BDatasheetSUN-3-12K-SG05LP3-EU-SM220260911en.pdf) | 20260911 (from file name; no date printed in the document) | fabricant |
| `ond_bat_v_max` | 60 | V | 40-60 | [Deye - Three Phase Hybrid Inverter SUN-3/4/5/6/8/10/12K-SG05LP3-EU-SM2 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/09/14/BDatasheetSUN-3-12K-SG05LP3-EU-SM220260911en.pdf) | 20260911 (from file name; no date printed in the document) | fabricant |

Non publié par le fabricant : ond_conso_nuit_w.

**Écarts avec la fiche de production :**
- {"champ": "ond_n_mppt", "fiche_existante": 1, "datasheet": 2, "commentaire": "existing sheet value equals none of the datasheet value(s) read"}
- {"champ": "ond_mppt_v_min", "fiche_existante": "150.0", "datasheet": 200, "commentaire": "existing sheet value equals none of the datasheet value(s) read"}
- {"champ": "ond_mppt_v_max", "fiche_existante": "450.0", "datasheet": 650, "commentaire": "existing sheet value equals none of the datasheet value(s) read"}
- {"champ": "ond_v_max_abs", "fiche_existante": "52.0", "datasheet": 800, "commentaire": "existing sheet value equals none of the datasheet value(s) read"}
- {"champ": "ond_i_max_mppt_a", "fiche_existante": "27.0", "datasheet": 20, "commentaire": "existing sheet value equals none of the datasheet value(s) read"}
- {"champ": "ond_rendement_euro_pct", "fiche_existante": "98.0", "datasheet": 97.0, "commentaire": "existing sheet value equals none of the datasheet value(s) read"}

### Onduleur hybride Deye 12kW Triphasé-SG05LP3 — SUN-12K-SG05LP3

Modèle identifié : **Deye SUN-12K-SG05LP3-EU-SM2** · certitude : sure.

Note : SKU SUN-12K-SG05LP3 = 12K column of the SG05LP3-EU-SM2 family; all existing values match. ond_conso_nuit_w: not published - the Deye documents read print no standby / night / self-consumption row. Checked: datasheet 20260911, manual 20261029.

| Champ | Valeur | Unité | Comme imprimé | Source | Date | Type |
|---|---|---|---|---|---|---|
| `ond_n_mppt` | 2 |  | 2/2+2 | [Deye - Three Phase Hybrid Inverter SUN-3/4/5/6/8/10/12K-SG05LP3-EU-SM2 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/09/14/BDatasheetSUN-3-12K-SG05LP3-EU-SM220260911en.pdf) | 20260911 (from file name; no date printed in the document) | fabricant |
| `ond_mppt_v_min` | 200 | V | 200-650 | [Deye - Three Phase Hybrid Inverter SUN-3/4/5/6/8/10/12K-SG05LP3-EU-SM2 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/09/14/BDatasheetSUN-3-12K-SG05LP3-EU-SM220260911en.pdf) | 20260911 (from file name; no date printed in the document) | fabricant |
| `ond_mppt_v_max` | 650 | V | 200-650 | [Deye - Three Phase Hybrid Inverter SUN-3/4/5/6/8/10/12K-SG05LP3-EU-SM2 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/09/14/BDatasheetSUN-3-12K-SG05LP3-EU-SM220260911en.pdf) | 20260911 (from file name; no date printed in the document) | fabricant |
| `ond_v_max_abs` | 800 | V | 800 | [Deye - Three Phase Hybrid Inverter SUN-3/4/5/6/8/10/12K-SG05LP3-EU-SM2 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/09/14/BDatasheetSUN-3-12K-SG05LP3-EU-SM220260911en.pdf) | 20260911 (from file name; no date printed in the document) | fabricant |
| `ond_i_max_mppt_a` | 26 | A | 26+26 | [Deye - Three Phase Hybrid Inverter SUN-3/4/5/6/8/10/12K-SG05LP3-EU-SM2 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/09/14/BDatasheetSUN-3-12K-SG05LP3-EU-SM220260911en.pdf) | 20260911 (from file name; no date printed in the document) | fabricant |
| `ond_isc_max_mppt_a` | 39 | A | 39+39 | [Deye - Three Phase Hybrid Inverter SUN-3/4/5/6/8/10/12K-SG05LP3-EU-SM2 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/09/14/BDatasheetSUN-3-12K-SG05LP3-EU-SM220260911en.pdf) | 20260911 (from file name; no date printed in the document) | fabricant |
| `ond_ac_kw` | 12.0 | kW | 12000 W | [Deye - Three Phase Hybrid Inverter SUN-3/4/5/6/8/10/12K-SG05LP3-EU-SM2 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/09/14/BDatasheetSUN-3-12K-SG05LP3-EU-SM220260911en.pdf) | 20260911 (from file name; no date printed in the document) | fabricant |
| `ond_phases` | 3 |  | 3L+N+PE | [Deye - Three Phase Hybrid Inverter SUN-3/4/5/6/8/10/12K-SG05LP3-EU-SM2 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/09/14/BDatasheetSUN-3-12K-SG05LP3-EU-SM220260911en.pdf) | 20260911 (from file name; no date printed in the document) | fabricant |
| `ond_rendement_euro_pct` | 97.0 | % | 97.0% | [Deye - Three Phase Hybrid Inverter SUN-3/4/5/6/8/10/12K-SG05LP3-EU-SM2 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/09/14/BDatasheetSUN-3-12K-SG05LP3-EU-SM220260911en.pdf) | 20260911 (from file name; no date printed in the document) | fabricant |
| `ond_dc_max_kwc` | {"max_pv_access_power_kwp": 24.0, "max_pv_input_power_kwp": 19.2} | kWp | Max. PV access power 24000 W; Max. PV Input Power 19200 W | [Deye - Three Phase Hybrid Inverter SUN-3/4/5/6/8/10/12K-SG05LP3-EU-SM2 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/09/14/BDatasheetSUN-3-12K-SG05LP3-EU-SM220260911en.pdf) | 20260911 (from file name; no date printed in the document) | fabricant |
| `ond_bat_v_min` | 40 | V | 40-60 | [Deye - Three Phase Hybrid Inverter SUN-3/4/5/6/8/10/12K-SG05LP3-EU-SM2 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/09/14/BDatasheetSUN-3-12K-SG05LP3-EU-SM220260911en.pdf) | 20260911 (from file name; no date printed in the document) | fabricant |
| `ond_bat_v_max` | 60 | V | 40-60 | [Deye - Three Phase Hybrid Inverter SUN-3/4/5/6/8/10/12K-SG05LP3-EU-SM2 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/09/14/BDatasheetSUN-3-12K-SG05LP3-EU-SM220260911en.pdf) | 20260911 (from file name; no date printed in the document) | fabricant |

Non publié par le fabricant : ond_conso_nuit_w.

### Onduleur hybride Deye 15kW Triphasé — OND-H-DEY-15T

Modèle identifié : **Deye SUN-15K-SG05LP3-EU-SM2** · certitude : sure.

Note : Model confirmed by the catalogue description (SUN-15K-SG05LP3-EU-SM2); 14-20K family datasheet. ond_conso_nuit_w: not published - the Deye documents read print no standby / night / self-consumption row. Checked: datasheet 20260911 (14-20K); the 14-20K user manual was NOT fetched.

| Champ | Valeur | Unité | Comme imprimé | Source | Date | Type |
|---|---|---|---|---|---|---|
| `ond_n_mppt` | 2 |  | 2/2+2 | [Deye - Three Phase Hybrid Inverter SUN-14/15/16/18/20K-SG05LP3-EU-SM2 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/09/14/BDatasheetSUN-14-20K-SG05LP3-EU-SM220260911en.pdf) | 20260911 (from file name; no date printed) | fabricant |
| `ond_mppt_v_min` | 160 | V | 160-650 | [Deye - Three Phase Hybrid Inverter SUN-14/15/16/18/20K-SG05LP3-EU-SM2 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/09/14/BDatasheetSUN-14-20K-SG05LP3-EU-SM220260911en.pdf) | 20260911 (from file name; no date printed) | fabricant |
| `ond_mppt_v_max` | 650 | V | 160-650 | [Deye - Three Phase Hybrid Inverter SUN-14/15/16/18/20K-SG05LP3-EU-SM2 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/09/14/BDatasheetSUN-14-20K-SG05LP3-EU-SM220260911en.pdf) | 20260911 (from file name; no date printed) | fabricant |
| `ond_v_max_abs` | 800 | V | 800 | [Deye - Three Phase Hybrid Inverter SUN-14/15/16/18/20K-SG05LP3-EU-SM2 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/09/14/BDatasheetSUN-14-20K-SG05LP3-EU-SM220260911en.pdf) | 20260911 (from file name; no date printed) | fabricant |
| `ond_i_max_mppt_a` | 36 | A | 36+36 | [Deye - Three Phase Hybrid Inverter SUN-14/15/16/18/20K-SG05LP3-EU-SM2 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/09/14/BDatasheetSUN-14-20K-SG05LP3-EU-SM220260911en.pdf) | 20260911 (from file name; no date printed) | fabricant |
| `ond_isc_max_mppt_a` | 54 | A | 54+54 | [Deye - Three Phase Hybrid Inverter SUN-14/15/16/18/20K-SG05LP3-EU-SM2 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/09/14/BDatasheetSUN-14-20K-SG05LP3-EU-SM220260911en.pdf) | 20260911 (from file name; no date printed) | fabricant |
| `ond_ac_kw` | 15.0 | kW | 15000 W | [Deye - Three Phase Hybrid Inverter SUN-14/15/16/18/20K-SG05LP3-EU-SM2 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/09/14/BDatasheetSUN-14-20K-SG05LP3-EU-SM220260911en.pdf) | 20260911 (from file name; no date printed) | fabricant |
| `ond_phases` | 3 |  | 3L+N+PE | [Deye - Three Phase Hybrid Inverter SUN-14/15/16/18/20K-SG05LP3-EU-SM2 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/09/14/BDatasheetSUN-14-20K-SG05LP3-EU-SM220260911en.pdf) | 20260911 (from file name; no date printed) | fabricant |
| `ond_rendement_euro_pct` | 97.0 | % | 97.0% | [Deye - Three Phase Hybrid Inverter SUN-14/15/16/18/20K-SG05LP3-EU-SM2 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/09/14/BDatasheetSUN-14-20K-SG05LP3-EU-SM220260911en.pdf) | 20260911 (from file name; no date printed) | fabricant |
| `ond_dc_max_kwc` | {"max_pv_access_power_kwp": 30.0, "max_pv_input_power_kwp": 24.0} | kWp | Max. PV access power 30000 W; Max. PV Input Power 24000 W | [Deye - Three Phase Hybrid Inverter SUN-14/15/16/18/20K-SG05LP3-EU-SM2 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/09/14/BDatasheetSUN-14-20K-SG05LP3-EU-SM220260911en.pdf) | 20260911 (from file name; no date printed) | fabricant |
| `ond_bat_v_min` | 40 | V | 40-60 | [Deye - Three Phase Hybrid Inverter SUN-14/15/16/18/20K-SG05LP3-EU-SM2 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/09/14/BDatasheetSUN-14-20K-SG05LP3-EU-SM220260911en.pdf) | 20260911 (from file name; no date printed) | fabricant |
| `ond_bat_v_max` | 60 | V | 40-60 | [Deye - Three Phase Hybrid Inverter SUN-14/15/16/18/20K-SG05LP3-EU-SM2 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/09/14/BDatasheetSUN-14-20K-SG05LP3-EU-SM220260911en.pdf) | 20260911 (from file name; no date printed) | fabricant |

Non publié par le fabricant : ond_conso_nuit_w.

### Onduleur hybride Deye 20kW Triphasé — OND-H-DEY-20T

Modèle identifié : **Deye SUN-20K-SG05LP3-EU-SM2** · certitude : sure.

Note : Model confirmed by the catalogue description (SUN-20K-SG05LP3-EU-SM2); 14-20K family datasheet. ond_conso_nuit_w: not published - the Deye documents read print no standby / night / self-consumption row. Checked: datasheet 20260911 (14-20K); the 14-20K user manual was NOT fetched.

| Champ | Valeur | Unité | Comme imprimé | Source | Date | Type |
|---|---|---|---|---|---|---|
| `ond_n_mppt` | 2 |  | 2/2+2 | [Deye - Three Phase Hybrid Inverter SUN-14/15/16/18/20K-SG05LP3-EU-SM2 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/09/14/BDatasheetSUN-14-20K-SG05LP3-EU-SM220260911en.pdf) | 20260911 (from file name; no date printed) | fabricant |
| `ond_mppt_v_min` | 160 | V | 160-650 | [Deye - Three Phase Hybrid Inverter SUN-14/15/16/18/20K-SG05LP3-EU-SM2 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/09/14/BDatasheetSUN-14-20K-SG05LP3-EU-SM220260911en.pdf) | 20260911 (from file name; no date printed) | fabricant |
| `ond_mppt_v_max` | 650 | V | 160-650 | [Deye - Three Phase Hybrid Inverter SUN-14/15/16/18/20K-SG05LP3-EU-SM2 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/09/14/BDatasheetSUN-14-20K-SG05LP3-EU-SM220260911en.pdf) | 20260911 (from file name; no date printed) | fabricant |
| `ond_v_max_abs` | 800 | V | 800 | [Deye - Three Phase Hybrid Inverter SUN-14/15/16/18/20K-SG05LP3-EU-SM2 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/09/14/BDatasheetSUN-14-20K-SG05LP3-EU-SM220260911en.pdf) | 20260911 (from file name; no date printed) | fabricant |
| `ond_i_max_mppt_a` | 36 | A | 36+36 | [Deye - Three Phase Hybrid Inverter SUN-14/15/16/18/20K-SG05LP3-EU-SM2 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/09/14/BDatasheetSUN-14-20K-SG05LP3-EU-SM220260911en.pdf) | 20260911 (from file name; no date printed) | fabricant |
| `ond_isc_max_mppt_a` | 54 | A | 54+54 | [Deye - Three Phase Hybrid Inverter SUN-14/15/16/18/20K-SG05LP3-EU-SM2 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/09/14/BDatasheetSUN-14-20K-SG05LP3-EU-SM220260911en.pdf) | 20260911 (from file name; no date printed) | fabricant |
| `ond_ac_kw` | 20.0 | kW | 20000 W | [Deye - Three Phase Hybrid Inverter SUN-14/15/16/18/20K-SG05LP3-EU-SM2 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/09/14/BDatasheetSUN-14-20K-SG05LP3-EU-SM220260911en.pdf) | 20260911 (from file name; no date printed) | fabricant |
| `ond_phases` | 3 |  | 3L+N+PE | [Deye - Three Phase Hybrid Inverter SUN-14/15/16/18/20K-SG05LP3-EU-SM2 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/09/14/BDatasheetSUN-14-20K-SG05LP3-EU-SM220260911en.pdf) | 20260911 (from file name; no date printed) | fabricant |
| `ond_rendement_euro_pct` | 97.0 | % | 97.0% | [Deye - Three Phase Hybrid Inverter SUN-14/15/16/18/20K-SG05LP3-EU-SM2 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/09/14/BDatasheetSUN-14-20K-SG05LP3-EU-SM220260911en.pdf) | 20260911 (from file name; no date printed) | fabricant |
| `ond_dc_max_kwc` | {"max_pv_access_power_kwp": 40.0, "max_pv_input_power_kwp": 32.0} | kWp | Max. PV access power 40000 W; Max. PV Input Power 32000 W | [Deye - Three Phase Hybrid Inverter SUN-14/15/16/18/20K-SG05LP3-EU-SM2 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/09/14/BDatasheetSUN-14-20K-SG05LP3-EU-SM220260911en.pdf) | 20260911 (from file name; no date printed) | fabricant |
| `ond_bat_v_min` | 40 | V | 40-60 | [Deye - Three Phase Hybrid Inverter SUN-14/15/16/18/20K-SG05LP3-EU-SM2 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/09/14/BDatasheetSUN-14-20K-SG05LP3-EU-SM220260911en.pdf) | 20260911 (from file name; no date printed) | fabricant |
| `ond_bat_v_max` | 60 | V | 40-60 | [Deye - Three Phase Hybrid Inverter SUN-14/15/16/18/20K-SG05LP3-EU-SM2 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/09/14/BDatasheetSUN-14-20K-SG05LP3-EU-SM220260911en.pdf) | 20260911 (from file name; no date printed) | fabricant |

Non publié par le fabricant : ond_conso_nuit_w.

### Onduleur hybride Deye 30kW Triphasé — SUN-30K-SG02HP3-EU-BM3

Modèle identifié : **Deye SUN-30K-SG02HP3-EU-BM3** · certitude : sure.

Note : SKU is the maker reference. Two revisions: ...-BM3 (datasheet 20260505, max charge/discharge 100 A) and ...-BM3-P (20260911, 160 A); every field above is identical in both (both read). The older SG01HP3-EU-BM3 generation prints different figures (e.g. max DC 39000 W) - not this product. ond_conso_nuit_w: not published - the Deye documents read print no standby / night / self-consumption row. Checked: datasheets 20260505 and 20260911; no manual fetched.

| Champ | Valeur | Unité | Comme imprimé | Source | Date | Type |
|---|---|---|---|---|---|---|
| `ond_n_mppt` | 3 |  | 3/2+2+2 | [Deye - Three Phase Hybrid Inverter SUN-29.9/30/35K-SG02HP3-EU-BM3, SUN-40/50K-SG02HP3-EU-BM4 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/05/05/BDatasheetSUN-299-50K-SG02HP3-EU-BM420260505-lrrG.pdf) | 20260505 (from file name) | fabricant |
| `ond_mppt_v_min` | 150 | V | 150-850 | [Deye - Three Phase Hybrid Inverter SUN-29.9/30/35K-SG02HP3-EU-BM3, SUN-40/50K-SG02HP3-EU-BM4 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/05/05/BDatasheetSUN-299-50K-SG02HP3-EU-BM420260505-lrrG.pdf) | 20260505 (from file name) | fabricant |
| `ond_mppt_v_max` | 850 | V | 150-850 | [Deye - Three Phase Hybrid Inverter SUN-29.9/30/35K-SG02HP3-EU-BM3, SUN-40/50K-SG02HP3-EU-BM4 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/05/05/BDatasheetSUN-299-50K-SG02HP3-EU-BM420260505-lrrG.pdf) | 20260505 (from file name) | fabricant |
| `ond_v_max_abs` | 1000 | V | 1000 | [Deye - Three Phase Hybrid Inverter SUN-29.9/30/35K-SG02HP3-EU-BM3, SUN-40/50K-SG02HP3-EU-BM4 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/05/05/BDatasheetSUN-299-50K-SG02HP3-EU-BM420260505-lrrG.pdf) | 20260505 (from file name) | fabricant |
| `ond_i_max_mppt_a` | 36 | A | 36+36+36 | [Deye - Three Phase Hybrid Inverter SUN-29.9/30/35K-SG02HP3-EU-BM3, SUN-40/50K-SG02HP3-EU-BM4 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/05/05/BDatasheetSUN-299-50K-SG02HP3-EU-BM420260505-lrrG.pdf) | 20260505 (from file name) | fabricant |
| `ond_isc_max_mppt_a` | 55 | A | 55+55+55 | [Deye - Three Phase Hybrid Inverter SUN-29.9/30/35K-SG02HP3-EU-BM3, SUN-40/50K-SG02HP3-EU-BM4 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/05/05/BDatasheetSUN-299-50K-SG02HP3-EU-BM420260505-lrrG.pdf) | 20260505 (from file name) | fabricant |
| `ond_ac_kw` | 30.0 | kW | 30000 W | [Deye - Three Phase Hybrid Inverter SUN-29.9/30/35K-SG02HP3-EU-BM3, SUN-40/50K-SG02HP3-EU-BM4 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/05/05/BDatasheetSUN-299-50K-SG02HP3-EU-BM420260505-lrrG.pdf) | 20260505 (from file name) | fabricant |
| `ond_phases` | 3 |  | 3L+N+PE | [Deye - Three Phase Hybrid Inverter SUN-29.9/30/35K-SG02HP3-EU-BM3, SUN-40/50K-SG02HP3-EU-BM4 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/05/05/BDatasheetSUN-299-50K-SG02HP3-EU-BM420260505-lrrG.pdf) | 20260505 (from file name) | fabricant |
| `ond_rendement_euro_pct` | 97.0 | % | 97.0% | [Deye - Three Phase Hybrid Inverter SUN-29.9/30/35K-SG02HP3-EU-BM3, SUN-40/50K-SG02HP3-EU-BM4 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/05/05/BDatasheetSUN-299-50K-SG02HP3-EU-BM420260505-lrrG.pdf) | 20260505 (from file name) | fabricant |
| `ond_dc_max_kwc` | {"max_pv_access_power_kwp": 60.0, "max_pv_input_power_kwp": 48.0} | kWp | Max. PV access power 60000 W; Max. PV Input Power 48000 W | [Deye - Three Phase Hybrid Inverter SUN-29.9/30/35K-SG02HP3-EU-BM3, SUN-40/50K-SG02HP3-EU-BM4 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/05/05/BDatasheetSUN-299-50K-SG02HP3-EU-BM420260505-lrrG.pdf) | 20260505 (from file name) | fabricant |
| `ond_bat_v_min` | 160 | V | 160-800 | [Deye - Three Phase Hybrid Inverter SUN-29.9/30/35K-SG02HP3-EU-BM3, SUN-40/50K-SG02HP3-EU-BM4 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/05/05/BDatasheetSUN-299-50K-SG02HP3-EU-BM420260505-lrrG.pdf) | 20260505 (from file name) | fabricant |
| `ond_bat_v_max` | 800 | V | 160-800 | [Deye - Three Phase Hybrid Inverter SUN-29.9/30/35K-SG02HP3-EU-BM3, SUN-40/50K-SG02HP3-EU-BM4 - Technical Data (datasheet)](https://www.deyeinverter.com/deyeinverter/2026/05/05/BDatasheetSUN-299-50K-SG02HP3-EU-BM420260505-lrrG.pdf) | 20260505 (from file name) | fabricant |

Non publié par le fabricant : ond_conso_nuit_w.

### Onduleur hybride Deye 5kW Monophasé — OND-H-DEY-5M

Modèle identifié : **Deye SUN-5K-SG05LP1-EU(-SM2) - exact generation unknown** · certitude : ambigu.

Note : Catalogue: "SUN-5K-SG05LP1-EU(-SM2) - a confirmer fondateur". Three generations exist; values per candidate above (they share the voltage window and efficiency, differ on input currents). A datasheet for the 5K of the exact "-EU-SM2" (no -P) generation was NOT found (the SM2 datasheet found covers 7/7.6/8/10K only: 26+26 A / 34+34 A). The sheet values 22 A / 22 A fit none of them. ond_conso_nuit_w: not published - the Deye documents read print no standby / night / self-consumption row. Checked: datasheets 20260911 (-P) and 20260316 (-EU, German); manual SG05LP1-EU-SM2-P 20260427 searched for standby/night/consumption: nothing.

| Champ | Valeur | Unité | Comme imprimé | Source | Date | Type |
|---|---|---|---|---|---|---|
| `ond_n_mppt` | {"SUN-5K-SG05LP1-EU-SM2-P": 2, "SUN-5K-SG05LP1-EU": 2} |  |  |  |  | fabricant |
| `ond_mppt_v_min` | {"SUN-5K-SG05LP1-EU-SM2-P": 150, "SUN-5K-SG05LP1-EU": 150} | V |  |  |  | fabricant |
| `ond_mppt_v_max` | {"SUN-5K-SG05LP1-EU-SM2-P": 425, "SUN-5K-SG05LP1-EU": 425} | V |  |  |  | fabricant |
| `ond_v_max_abs` | {"SUN-5K-SG05LP1-EU-SM2-P": 500, "SUN-5K-SG05LP1-EU": 500} | V |  |  |  | fabricant |
| `ond_i_max_mppt_a` | {"SUN-5K-SG05LP1-EU-SM2-P": 18, "SUN-5K-SG05LP1-EU": 13} | A |  |  |  | fabricant |
| `ond_isc_max_mppt_a` | {"SUN-5K-SG05LP1-EU-SM2-P": 27, "SUN-5K-SG05LP1-EU": 17} | A |  |  |  | fabricant |
| `ond_ac_kw` | {"SUN-5K-SG05LP1-EU-SM2-P": 5.0, "SUN-5K-SG05LP1-EU": 5.0} | kW |  |  |  | fabricant |
| `ond_phases` | {"SUN-5K-SG05LP1-EU-SM2-P": 1, "SUN-5K-SG05LP1-EU": 1} |  |  |  |  | fabricant |
| `ond_rendement_euro_pct` | {"SUN-5K-SG05LP1-EU-SM2-P": 96.5, "SUN-5K-SG05LP1-EU": 96.5} | % |  |  |  | fabricant |
| `ond_dc_max_kwc` | {"SUN-5K-SG05LP1-EU-SM2-P": {"max_pv_access_power_kwp": 10.0, "max_pv_input_power_kwp": 8.0}, "SUN-5K-SG05LP1-EU": {"max_pv_access_power_kwp": 10.0, "max_pv_input_power_kwp": 8.0}} | kWp |  |  |  | fabricant |
| `ond_bat_v_min` | {"SUN-5K-SG05LP1-EU-SM2-P": 40, "SUN-5K-SG05LP1-EU": 40} | V |  |  |  | fabricant |
| `ond_bat_v_max` | {"SUN-5K-SG05LP1-EU-SM2-P": 60, "SUN-5K-SG05LP1-EU": 60} | V |  |  |  | fabricant |

Non publié par le fabricant : ond_conso_nuit_w.

**Écarts avec la fiche de production :**
- {"champ": "ond_v_max_abs", "fiche_existante": "600.0", "datasheet": {"SUN-5K-SG05LP1-EU-SM2-P": 500, "SUN-5K-SG05LP1-EU": 500}, "commentaire": "existing sheet value equals none of the datasheet value(s) read"}
- {"champ": "ond_i_max_mppt_a", "fiche_existante": "22.0", "datasheet": {"SUN-5K-SG05LP1-EU-SM2-P": 18, "SUN-5K-SG05LP1-EU": 13}, "commentaire": "existing sheet value equals none of the datasheet value(s) read"}
- {"champ": "ond_isc_max_mppt_a", "fiche_existante": "22.0", "datasheet": {"SUN-5K-SG05LP1-EU-SM2-P": 27, "SUN-5K-SG05LP1-EU": 17}, "commentaire": "existing sheet value equals none of the datasheet value(s) read"}

### Onduleur hybride Deye 10kW Monophasé — OND-H-DEY-10M

Modèle identifié : **Deye SUN-10K-SG02LP1-EU-AM3 (catalogue: "modele suppose, a confirmer")** · certitude : probable.

Note : Catalogue names SUN-10K-SG02LP1-EU-AM3 (no -P). Two datasheet revisions (240802 without -P; 20260911 with -P) differ on input currents. The datasheets say 3 MPPT; the existing sheet says 2. ond_conso_nuit_w: not published - the Deye documents read print no standby / night / self-consumption row. Checked: datasheets 240802 and 20260911; no manual fetched.

| Champ | Valeur | Unité | Comme imprimé | Source | Date | Type |
|---|---|---|---|---|---|---|
| `ond_n_mppt` | {"AM3 (240802)": 3, "AM3-P (20260911)": 3} |  |  |  |  | fabricant |
| `ond_mppt_v_min` | {"AM3 (240802)": 150, "AM3-P (20260911)": 150} | V |  |  |  | fabricant |
| `ond_mppt_v_max` | {"AM3 (240802)": 425, "AM3-P (20260911)": 425} | V |  |  |  | fabricant |
| `ond_v_max_abs` | {"AM3 (240802)": 500, "AM3-P (20260911)": 500} | V |  |  |  | fabricant |
| `ond_i_max_mppt_a` | {"AM3 (240802)": 26, "AM3-P (20260911)": 32} | A |  |  |  | fabricant |
| `ond_isc_max_mppt_a` | {"AM3 (240802)": 44, "AM3-P (20260911)": 60} | A |  |  |  | fabricant |
| `ond_ac_kw` | {"AM3 (240802)": 10.0, "AM3-P (20260911)": 10.0} | kW |  |  |  | fabricant |
| `ond_phases` | {"AM3 (240802)": 1, "AM3-P (20260911)": 1} |  |  |  |  | fabricant |
| `ond_rendement_euro_pct` | {"AM3 (240802)": 96.5, "AM3-P (20260911)": 96.5} | % |  |  |  | fabricant |
| `ond_dc_max_kwc` | {"AM3 (240802)": {"max_pv_access_power_kwp": 20.0, "max_pv_input_power_kwp": 15.0}, "AM3-P (20260911)": {"max_pv_access_power_kwp": 20.0, "max_pv_input_power_kwp": 16.0}} | kWp |  |  |  | fabricant |
| `ond_bat_v_min` | {"AM3 (240802)": 40, "AM3-P (20260911)": 40} | V |  |  |  | fabricant |
| `ond_bat_v_max` | {"AM3 (240802)": 60, "AM3-P (20260911)": 60} | V |  |  |  | fabricant |

Non publié par le fabricant : ond_conso_nuit_w.

**Écarts avec la fiche de production :**
- {"champ": "ond_n_mppt", "fiche_existante": 2, "datasheet": {"AM3 (240802)": 3, "AM3-P (20260911)": 3}, "commentaire": "existing sheet value equals none of the datasheet value(s) read"}
- {"champ": "ond_v_max_abs", "fiche_existante": "600.0", "datasheet": {"AM3 (240802)": 500, "AM3-P (20260911)": 500}, "commentaire": "existing sheet value equals none of the datasheet value(s) read"}
- {"champ": "ond_rendement_euro_pct", "fiche_existante": "97.0", "datasheet": {"AM3 (240802)": 96.5, "AM3-P (20260911)": 96.5}, "commentaire": "existing sheet value equals none of the datasheet value(s) read"}

### Deye off-Grid 6kw — OND-OG-DEY-6M

Modèle identifié : **Deye SUN-6K-OG01LP1-EU-AM2 (unconfirmed)** · certitude : ambigu.

Note : The catalogue gives NO model (name "Deye off-Grid 6kw", no description, no sheet). The only Deye 6 kW off-grid inverter found in the maker range is SUN-6K-OG01LP1-EU-AM2 (single-phase, 3.6/5/6K family); I could not confirm it is the stocked product - ask the founder / check the supplier invoice. Only the French Deye datasheet was used (maker domain); no English one was fetched. ond_conso_nuit_w: not published - the Deye documents read print no standby / night / self-consumption row. Checked: FR datasheet 20251030 only.

| Champ | Valeur | Unité | Comme imprimé | Source | Date | Type |
|---|---|---|---|---|---|---|
| `ond_n_mppt` | 2 |  | 2/1+1 | [Deye - Onduleur Hors Off-Grid Monophase SUN-3.6/5/6K-OG01LP1-EU-AM2 - Donnees techniques (French datasheet)](https://fr.deyeinverter.com/deyeinverter/2025/10/30/%E3%80%90B%E3%80%91Datasheet_SUN-3-6K-OG01LP1-EU-AM2_20251030_fr.pdf) | 20251030 (from file name) | fabricant |
| `ond_mppt_v_min` | 150 | V | 150-425 | [Deye - Onduleur Hors Off-Grid Monophase SUN-3.6/5/6K-OG01LP1-EU-AM2 - Donnees techniques (French datasheet)](https://fr.deyeinverter.com/deyeinverter/2025/10/30/%E3%80%90B%E3%80%91Datasheet_SUN-3-6K-OG01LP1-EU-AM2_20251030_fr.pdf) | 20251030 (from file name) | fabricant |
| `ond_mppt_v_max` | 425 | V | 150-425 | [Deye - Onduleur Hors Off-Grid Monophase SUN-3.6/5/6K-OG01LP1-EU-AM2 - Donnees techniques (French datasheet)](https://fr.deyeinverter.com/deyeinverter/2025/10/30/%E3%80%90B%E3%80%91Datasheet_SUN-3-6K-OG01LP1-EU-AM2_20251030_fr.pdf) | 20251030 (from file name) | fabricant |
| `ond_v_max_abs` | 500 | V | 500 | [Deye - Onduleur Hors Off-Grid Monophase SUN-3.6/5/6K-OG01LP1-EU-AM2 - Donnees techniques (French datasheet)](https://fr.deyeinverter.com/deyeinverter/2025/10/30/%E3%80%90B%E3%80%91Datasheet_SUN-3-6K-OG01LP1-EU-AM2_20251030_fr.pdf) | 20251030 (from file name) | fabricant |
| `ond_i_max_mppt_a` | 18 | A | 18+18 | [Deye - Onduleur Hors Off-Grid Monophase SUN-3.6/5/6K-OG01LP1-EU-AM2 - Donnees techniques (French datasheet)](https://fr.deyeinverter.com/deyeinverter/2025/10/30/%E3%80%90B%E3%80%91Datasheet_SUN-3-6K-OG01LP1-EU-AM2_20251030_fr.pdf) | 20251030 (from file name) | fabricant |
| `ond_isc_max_mppt_a` | 27 | A | 27+27 | [Deye - Onduleur Hors Off-Grid Monophase SUN-3.6/5/6K-OG01LP1-EU-AM2 - Donnees techniques (French datasheet)](https://fr.deyeinverter.com/deyeinverter/2025/10/30/%E3%80%90B%E3%80%91Datasheet_SUN-3-6K-OG01LP1-EU-AM2_20251030_fr.pdf) | 20251030 (from file name) | fabricant |
| `ond_ac_kw` | 6.0 | kW | 6000 (VA/W) | [Deye - Onduleur Hors Off-Grid Monophase SUN-3.6/5/6K-OG01LP1-EU-AM2 - Donnees techniques (French datasheet)](https://fr.deyeinverter.com/deyeinverter/2025/10/30/%E3%80%90B%E3%80%91Datasheet_SUN-3-6K-OG01LP1-EU-AM2_20251030_fr.pdf) | 20251030 (from file name) | fabricant |
| `ond_phases` | 1 |  | L+N+PE | [Deye - Onduleur Hors Off-Grid Monophase SUN-3.6/5/6K-OG01LP1-EU-AM2 - Donnees techniques (French datasheet)](https://fr.deyeinverter.com/deyeinverter/2025/10/30/%E3%80%90B%E3%80%91Datasheet_SUN-3-6K-OG01LP1-EU-AM2_20251030_fr.pdf) | 20251030 (from file name) | fabricant |
| `ond_rendement_euro_pct` | 96.5 | % | 96.5% | [Deye - Onduleur Hors Off-Grid Monophase SUN-3.6/5/6K-OG01LP1-EU-AM2 - Donnees techniques (French datasheet)](https://fr.deyeinverter.com/deyeinverter/2025/10/30/%E3%80%90B%E3%80%91Datasheet_SUN-3-6K-OG01LP1-EU-AM2_20251030_fr.pdf) | 20251030 (from file name) | fabricant |
| `ond_dc_max_kwc` | {"max_pv_access_power_kwp": 12.0, "max_pv_input_power_kwp": 9.6} | kWp | Puissance d'acces PV max. 12000 W; Puissance d'entree PV max. 9600 W | [Deye - Onduleur Hors Off-Grid Monophase SUN-3.6/5/6K-OG01LP1-EU-AM2 - Donnees techniques (French datasheet)](https://fr.deyeinverter.com/deyeinverter/2025/10/30/%E3%80%90B%E3%80%91Datasheet_SUN-3-6K-OG01LP1-EU-AM2_20251030_fr.pdf) | 20251030 (from file name) | fabricant |
| `ond_bat_v_min` | 40 | V | 40-60 | [Deye - Onduleur Hors Off-Grid Monophase SUN-3.6/5/6K-OG01LP1-EU-AM2 - Donnees techniques (French datasheet)](https://fr.deyeinverter.com/deyeinverter/2025/10/30/%E3%80%90B%E3%80%91Datasheet_SUN-3-6K-OG01LP1-EU-AM2_20251030_fr.pdf) | 20251030 (from file name) | fabricant |
| `ond_bat_v_max` | 60 | V | 40-60 | [Deye - Onduleur Hors Off-Grid Monophase SUN-3.6/5/6K-OG01LP1-EU-AM2 - Donnees techniques (French datasheet)](https://fr.deyeinverter.com/deyeinverter/2025/10/30/%E3%80%90B%E3%80%91Datasheet_SUN-3-6K-OG01LP1-EU-AM2_20251030_fr.pdf) | 20251030 (from file name) | fabricant |

Non publié par le fabricant : ond_conso_nuit_w.

### Deye off grid 6kw — sans référence

Modèle identifié : **Deye SUN-6K-OG01LP1-EU-AM2 (unconfirmed) - archived entry, same name as pk 119** · certitude : ambigu.

Note : Archived entry, no brand, no model. The catalogue gives NO model (name "Deye off-Grid 6kw", no description, no sheet). The only Deye 6 kW off-grid inverter found in the maker range is SUN-6K-OG01LP1-EU-AM2 (single-phase, 3.6/5/6K family); I could not confirm it is the stocked product - ask the founder / check the supplier invoice. Only the French Deye datasheet was used (maker domain); no English one was fetched. ond_conso_nuit_w: not published - the Deye documents read print no standby / night / self-consumption row. Checked: FR datasheet 20251030 only.

| Champ | Valeur | Unité | Comme imprimé | Source | Date | Type |
|---|---|---|---|---|---|---|
| `ond_n_mppt` | 2 |  | 2/1+1 | [Deye - Onduleur Hors Off-Grid Monophase SUN-3.6/5/6K-OG01LP1-EU-AM2 - Donnees techniques (French datasheet)](https://fr.deyeinverter.com/deyeinverter/2025/10/30/%E3%80%90B%E3%80%91Datasheet_SUN-3-6K-OG01LP1-EU-AM2_20251030_fr.pdf) | 20251030 (from file name) | fabricant |
| `ond_mppt_v_min` | 150 | V | 150-425 | [Deye - Onduleur Hors Off-Grid Monophase SUN-3.6/5/6K-OG01LP1-EU-AM2 - Donnees techniques (French datasheet)](https://fr.deyeinverter.com/deyeinverter/2025/10/30/%E3%80%90B%E3%80%91Datasheet_SUN-3-6K-OG01LP1-EU-AM2_20251030_fr.pdf) | 20251030 (from file name) | fabricant |
| `ond_mppt_v_max` | 425 | V | 150-425 | [Deye - Onduleur Hors Off-Grid Monophase SUN-3.6/5/6K-OG01LP1-EU-AM2 - Donnees techniques (French datasheet)](https://fr.deyeinverter.com/deyeinverter/2025/10/30/%E3%80%90B%E3%80%91Datasheet_SUN-3-6K-OG01LP1-EU-AM2_20251030_fr.pdf) | 20251030 (from file name) | fabricant |
| `ond_v_max_abs` | 500 | V | 500 | [Deye - Onduleur Hors Off-Grid Monophase SUN-3.6/5/6K-OG01LP1-EU-AM2 - Donnees techniques (French datasheet)](https://fr.deyeinverter.com/deyeinverter/2025/10/30/%E3%80%90B%E3%80%91Datasheet_SUN-3-6K-OG01LP1-EU-AM2_20251030_fr.pdf) | 20251030 (from file name) | fabricant |
| `ond_i_max_mppt_a` | 18 | A | 18+18 | [Deye - Onduleur Hors Off-Grid Monophase SUN-3.6/5/6K-OG01LP1-EU-AM2 - Donnees techniques (French datasheet)](https://fr.deyeinverter.com/deyeinverter/2025/10/30/%E3%80%90B%E3%80%91Datasheet_SUN-3-6K-OG01LP1-EU-AM2_20251030_fr.pdf) | 20251030 (from file name) | fabricant |
| `ond_isc_max_mppt_a` | 27 | A | 27+27 | [Deye - Onduleur Hors Off-Grid Monophase SUN-3.6/5/6K-OG01LP1-EU-AM2 - Donnees techniques (French datasheet)](https://fr.deyeinverter.com/deyeinverter/2025/10/30/%E3%80%90B%E3%80%91Datasheet_SUN-3-6K-OG01LP1-EU-AM2_20251030_fr.pdf) | 20251030 (from file name) | fabricant |
| `ond_ac_kw` | 6.0 | kW | 6000 (VA/W) | [Deye - Onduleur Hors Off-Grid Monophase SUN-3.6/5/6K-OG01LP1-EU-AM2 - Donnees techniques (French datasheet)](https://fr.deyeinverter.com/deyeinverter/2025/10/30/%E3%80%90B%E3%80%91Datasheet_SUN-3-6K-OG01LP1-EU-AM2_20251030_fr.pdf) | 20251030 (from file name) | fabricant |
| `ond_phases` | 1 |  | L+N+PE | [Deye - Onduleur Hors Off-Grid Monophase SUN-3.6/5/6K-OG01LP1-EU-AM2 - Donnees techniques (French datasheet)](https://fr.deyeinverter.com/deyeinverter/2025/10/30/%E3%80%90B%E3%80%91Datasheet_SUN-3-6K-OG01LP1-EU-AM2_20251030_fr.pdf) | 20251030 (from file name) | fabricant |
| `ond_rendement_euro_pct` | 96.5 | % | 96.5% | [Deye - Onduleur Hors Off-Grid Monophase SUN-3.6/5/6K-OG01LP1-EU-AM2 - Donnees techniques (French datasheet)](https://fr.deyeinverter.com/deyeinverter/2025/10/30/%E3%80%90B%E3%80%91Datasheet_SUN-3-6K-OG01LP1-EU-AM2_20251030_fr.pdf) | 20251030 (from file name) | fabricant |
| `ond_dc_max_kwc` | {"max_pv_access_power_kwp": 12.0, "max_pv_input_power_kwp": 9.6} | kWp | Puissance d'acces PV max. 12000 W; Puissance d'entree PV max. 9600 W | [Deye - Onduleur Hors Off-Grid Monophase SUN-3.6/5/6K-OG01LP1-EU-AM2 - Donnees techniques (French datasheet)](https://fr.deyeinverter.com/deyeinverter/2025/10/30/%E3%80%90B%E3%80%91Datasheet_SUN-3-6K-OG01LP1-EU-AM2_20251030_fr.pdf) | 20251030 (from file name) | fabricant |
| `ond_bat_v_min` | 40 | V | 40-60 | [Deye - Onduleur Hors Off-Grid Monophase SUN-3.6/5/6K-OG01LP1-EU-AM2 - Donnees techniques (French datasheet)](https://fr.deyeinverter.com/deyeinverter/2025/10/30/%E3%80%90B%E3%80%91Datasheet_SUN-3-6K-OG01LP1-EU-AM2_20251030_fr.pdf) | 20251030 (from file name) | fabricant |
| `ond_bat_v_max` | 60 | V | 40-60 | [Deye - Onduleur Hors Off-Grid Monophase SUN-3.6/5/6K-OG01LP1-EU-AM2 - Donnees techniques (French datasheet)](https://fr.deyeinverter.com/deyeinverter/2025/10/30/%E3%80%90B%E3%80%91Datasheet_SUN-3-6K-OG01LP1-EU-AM2_20251030_fr.pdf) | 20251030 (from file name) | fabricant |

Non publié par le fabricant : ond_conso_nuit_w.

### Onduleur réseau Huawei 5kW Monophasé — OND-R-HUA-5M

Modèle identifié : **Huawei SUN2000-5KTL-L1** · certitude : probable.

Note : Catalogue: "Modele suppose SUN2000-5KTL-L1, a confirmer". Existing sheet matches this model on voltages/efficiency/ac/dc_max but NOT on the input currents (22 A / 22 A vs 12.5 A / 18 A). Same figures in the EU compilation (page L1).

| Champ | Valeur | Unité | Comme imprimé | Source | Date | Type |
|---|---|---|---|---|---|---|
| `ond_n_mppt` | 2 |  | 2 | [Huawei - FusionSolar SUN2000-2/3/3.68/4/4.6/5/6KTL-L1 datasheet (Technical Specification)](https://solar.huawei.com/admin/asset/v1/pro/view/1e029d00296a4b87a9823fd083db547e.pdf) | Version No.: 01-202509 | fabricant |
| `ond_mppt_v_min` | 90 | V | 90-560 | [Huawei - FusionSolar SUN2000-2/3/3.68/4/4.6/5/6KTL-L1 datasheet (Technical Specification)](https://solar.huawei.com/admin/asset/v1/pro/view/1e029d00296a4b87a9823fd083db547e.pdf) | Version No.: 01-202509 | fabricant |
| `ond_mppt_v_max` | 560 | V | 90-560 | [Huawei - FusionSolar SUN2000-2/3/3.68/4/4.6/5/6KTL-L1 datasheet (Technical Specification)](https://solar.huawei.com/admin/asset/v1/pro/view/1e029d00296a4b87a9823fd083db547e.pdf) | Version No.: 01-202509 | fabricant |
| `ond_v_max_abs` | 600 | V | 600 | [Huawei - FusionSolar SUN2000-2/3/3.68/4/4.6/5/6KTL-L1 datasheet (Technical Specification)](https://solar.huawei.com/admin/asset/v1/pro/view/1e029d00296a4b87a9823fd083db547e.pdf) | Version No.: 01-202509 | fabricant |
| `ond_i_max_mppt_a` | 12.5 | A | 12.5 A | [Huawei - FusionSolar SUN2000-2/3/3.68/4/4.6/5/6KTL-L1 datasheet (Technical Specification)](https://solar.huawei.com/admin/asset/v1/pro/view/1e029d00296a4b87a9823fd083db547e.pdf) | Version No.: 01-202509 | fabricant |
| `ond_isc_max_mppt_a` | 18 | A | 18 A | [Huawei - FusionSolar SUN2000-2/3/3.68/4/4.6/5/6KTL-L1 datasheet (Technical Specification)](https://solar.huawei.com/admin/asset/v1/pro/view/1e029d00296a4b87a9823fd083db547e.pdf) | Version No.: 01-202509 | fabricant |
| `ond_ac_kw` | 5.0 | kW | 5,000 W | [Huawei - FusionSolar SUN2000-2/3/3.68/4/4.6/5/6KTL-L1 datasheet (Technical Specification)](https://solar.huawei.com/admin/asset/v1/pro/view/1e029d00296a4b87a9823fd083db547e.pdf) | Version No.: 01-202509 | fabricant |
| `ond_phases` | 1 |  | Single-phase | [Huawei - FusionSolar SUN2000-2/3/3.68/4/4.6/5/6KTL-L1 datasheet (Technical Specification)](https://solar.huawei.com/admin/asset/v1/pro/view/1e029d00296a4b87a9823fd083db547e.pdf) | Version No.: 01-202509 | fabricant |
| `ond_rendement_euro_pct` | 97.8 | % | 97.8% | [Huawei - FusionSolar SUN2000-2/3/3.68/4/4.6/5/6KTL-L1 datasheet (Technical Specification)](https://solar.huawei.com/admin/asset/v1/pro/view/1e029d00296a4b87a9823fd083db547e.pdf) | Version No.: 01-202509 | fabricant |
| `ond_dc_max_kwc` | 7.5 | kWp | 7,500 Wp | [Huawei - FusionSolar SUN2000-2/3/3.68/4/4.6/5/6KTL-L1 datasheet (Technical Specification)](https://solar.huawei.com/admin/asset/v1/pro/view/1e029d00296a4b87a9823fd083db547e.pdf) | Version No.: 01-202509 | fabricant |
| `ond_conso_nuit_w` | 2.5 | W | < 2.5 W | [Huawei - FusionSolar SUN2000-2/3/3.68/4/4.6/5/6KTL-L1 datasheet (Technical Specification)](https://solar.huawei.com/admin/asset/v1/pro/view/1e029d00296a4b87a9823fd083db547e.pdf) | Version No.: 01-202509 | fabricant |

**Écarts avec la fiche de production :**
- {"champ": "ond_i_max_mppt_a", "fiche_existante": "22.0", "datasheet": 12.5, "commentaire": "existing sheet value equals none of the datasheet value(s) read"}
- {"champ": "ond_isc_max_mppt_a", "fiche_existante": "22.0", "datasheet": 18, "commentaire": "existing sheet value equals none of the datasheet value(s) read"}

### Onduleur réseau Huawei 10kW Triphasé — OND-R-HUA-10T

Modèle identifié : **Huawei SUN2000-10KTL-M1 (two versions: standard / High Current)** · certitude : ambigu.

Note : Catalogue: "Modele suppose SUN2000-10KTL-M1, a confirmer". Two M1 versions exist, distinguished only by input currents: standard 11 A / 15 A, High Current 13.5 A / 19.5 A. The existing sheet (13.5 A) matches the High Current Version; its isc is empty (19.5 A if High Current). Other 10 kW three-phase Huawei lines (M0, M2, M5) were not examined because the catalogue names M1.

| Champ | Valeur | Unité | Comme imprimé | Source | Date | Type |
|---|---|---|---|---|---|---|
| `ond_n_mppt` | {"M1 High Current Version": 2, "M1 standard version": 2} |  |  |  |  | fabricant |
| `ond_mppt_v_min` | {"M1 High Current Version": 140, "M1 standard version": 140} | V |  |  |  | fabricant |
| `ond_mppt_v_max` | {"M1 High Current Version": 980, "M1 standard version": 980} | V |  |  |  | fabricant |
| `ond_v_max_abs` | {"M1 High Current Version": 1100, "M1 standard version": 1100} | V |  |  |  | fabricant |
| `ond_i_max_mppt_a` | {"M1 High Current Version": 13.5, "M1 standard version": 11} | A |  |  |  | fabricant |
| `ond_isc_max_mppt_a` | {"M1 High Current Version": 19.5, "M1 standard version": 15} | A |  |  |  | fabricant |
| `ond_ac_kw` | {"M1 High Current Version": 10.0, "M1 standard version": 10.0} | kW |  |  |  | fabricant |
| `ond_phases` | {"M1 High Current Version": 3, "M1 standard version": 3} |  |  |  |  | fabricant |
| `ond_rendement_euro_pct` | {"M1 High Current Version": 98.1, "M1 standard version": 98.1} | % |  |  |  | fabricant |
| `ond_dc_max_kwc` | {"M1 High Current Version": 15.0, "M1 standard version": 15.0} | kWp |  |  |  | fabricant |
| `ond_conso_nuit_w` | {"M1 High Current Version": 5.5, "M1 standard version": 5.5} | W |  |  |  | fabricant |

### Onduleur réseau Huawei 15kW Triphasé — OND-R-HUA-15T

Modèle identifié : **Huawei SUN2000-15KTL-M5** · certitude : probable.

Note : Catalogue: "Modele suppose SUN2000-15KTL-M5, a confirmer". The existing sheet matches M5 (1100 V, 200-1000 V, euro, dc_max); the older M2 generation prints 1,080 V / 160-950 V and does not match. ond_conso_nuit_w: not published - no night/standby row in the Huawei M5 spec page, nor in the M5 datasheet (reseller copy, Version No. 03-202403, checked) nor in the M5 user manual issue 08 (searched "night", "consumption", "standby"). For ond_i_max_mppt_a see the complement.

| Champ | Valeur | Unité | Comme imprimé | Source | Date | Type |
|---|---|---|---|---|---|---|
| `ond_n_mppt` | 2 |  | 2 | [Huawei product page - SUN2000-12/15/17/20/25KTL-M5 Technical Specification (Thailand site, English table)](https://solar.huawei.com/th/professionals/all-products/SUN2000-12-15-17-20-25KTL-M5/specs) | page read 2026-11-24; no version printed | fabricant |
| `ond_mppt_v_min` | 200 | V | 200 V ~ 1000 V | [Huawei product page - SUN2000-12/15/17/20/25KTL-M5 Technical Specification (Thailand site, English table)](https://solar.huawei.com/th/professionals/all-products/SUN2000-12-15-17-20-25KTL-M5/specs) | page read 2026-11-24; no version printed | fabricant |
| `ond_mppt_v_max` | 1000 | V | 200 V ~ 1000 V | [Huawei product page - SUN2000-12/15/17/20/25KTL-M5 Technical Specification (Thailand site, English table)](https://solar.huawei.com/th/professionals/all-products/SUN2000-12-15-17-20-25KTL-M5/specs) | page read 2026-11-24; no version printed | fabricant |
| `ond_v_max_abs` | 1100 | V | 1100 V | [Huawei product page - SUN2000-12/15/17/20/25KTL-M5 Technical Specification (Thailand site, English table)](https://solar.huawei.com/th/professionals/all-products/SUN2000-12-15-17-20-25KTL-M5/specs) | page read 2026-11-24; no version printed | fabricant |
| `ond_i_max_mppt_a` | {"two_strings": 30, "single_string": 20} | A | 30 A (two string) / 20 A (single string) | [Huawei product page - SUN2000-12/15/17/20/25KTL-M5 Technical Specification (Thailand site, English table)](https://solar.huawei.com/th/professionals/all-products/SUN2000-12-15-17-20-25KTL-M5/specs) | page read 2026-11-24; no version printed | fabricant |
| `ond_isc_max_mppt_a` | 40 | A | 40 A | [Huawei product page - SUN2000-12/15/17/20/25KTL-M5 Technical Specification (Thailand site, English table)](https://solar.huawei.com/th/professionals/all-products/SUN2000-12-15-17-20-25KTL-M5/specs) | page read 2026-11-24; no version printed | fabricant |
| `ond_ac_kw` | 15.0 | kW | 15,000 W | [Huawei product page - SUN2000-12/15/17/20/25KTL-M5 Technical Specification (Thailand site, English table)](https://solar.huawei.com/th/professionals/all-products/SUN2000-12-15-17-20-25KTL-M5/specs) | page read 2026-11-24; no version printed | fabricant |
| `ond_phases` | 3 |  | Three phase | [Huawei product page - SUN2000-12/15/17/20/25KTL-M5 Technical Specification (Thailand site, English table)](https://solar.huawei.com/th/professionals/all-products/SUN2000-12-15-17-20-25KTL-M5/specs) | page read 2026-11-24; no version printed | fabricant |
| `ond_rendement_euro_pct` | 98.0 | % | 98.0% | [Huawei product page - SUN2000-12/15/17/20/25KTL-M5 Technical Specification (Thailand site, English table)](https://solar.huawei.com/th/professionals/all-products/SUN2000-12-15-17-20-25KTL-M5/specs) | page read 2026-11-24; no version printed | fabricant |
| `ond_dc_max_kwc` | 22.5 | kWp | 22,500 Wp | [Huawei product page - SUN2000-12/15/17/20/25KTL-M5 Technical Specification (Thailand site, English table)](https://solar.huawei.com/th/professionals/all-products/SUN2000-12-15-17-20-25KTL-M5/specs) | page read 2026-11-24; no version printed | fabricant |

Non publié par le fabricant : ond_conso_nuit_w.

### Onduleur réseau Huawei 20kW Triphasé — OND-R-HUA-20T

Modèle identifié : **Huawei SUN2000-20KTL-M5** · certitude : probable.

Note : Catalogue: "Modele suppose SUN2000-20KTL-M5, a confirmer". The existing sheet matches M5 (1100 V, 200-1000 V, euro, dc_max); the older M2 generation prints 1,080 V / 160-950 V and does not match. ond_conso_nuit_w: not published - no night/standby row in the Huawei M5 spec page, nor in the M5 datasheet (reseller copy, Version No. 03-202403, checked) nor in the M5 user manual issue 08 (searched "night", "consumption", "standby"). For ond_i_max_mppt_a see the complement.

| Champ | Valeur | Unité | Comme imprimé | Source | Date | Type |
|---|---|---|---|---|---|---|
| `ond_n_mppt` | 2 |  | 2 | [Huawei product page - SUN2000-12/15/17/20/25KTL-M5 Technical Specification (Thailand site, English table)](https://solar.huawei.com/th/professionals/all-products/SUN2000-12-15-17-20-25KTL-M5/specs) | page read 2026-11-24; no version printed | fabricant |
| `ond_mppt_v_min` | 200 | V | 200 V ~ 1000 V | [Huawei product page - SUN2000-12/15/17/20/25KTL-M5 Technical Specification (Thailand site, English table)](https://solar.huawei.com/th/professionals/all-products/SUN2000-12-15-17-20-25KTL-M5/specs) | page read 2026-11-24; no version printed | fabricant |
| `ond_mppt_v_max` | 1000 | V | 200 V ~ 1000 V | [Huawei product page - SUN2000-12/15/17/20/25KTL-M5 Technical Specification (Thailand site, English table)](https://solar.huawei.com/th/professionals/all-products/SUN2000-12-15-17-20-25KTL-M5/specs) | page read 2026-11-24; no version printed | fabricant |
| `ond_v_max_abs` | 1100 | V | 1100 V | [Huawei product page - SUN2000-12/15/17/20/25KTL-M5 Technical Specification (Thailand site, English table)](https://solar.huawei.com/th/professionals/all-products/SUN2000-12-15-17-20-25KTL-M5/specs) | page read 2026-11-24; no version printed | fabricant |
| `ond_i_max_mppt_a` | {"two_strings": 30, "single_string": 20} | A | 30 A (two string) / 20 A (single string) | [Huawei product page - SUN2000-12/15/17/20/25KTL-M5 Technical Specification (Thailand site, English table)](https://solar.huawei.com/th/professionals/all-products/SUN2000-12-15-17-20-25KTL-M5/specs) | page read 2026-11-24; no version printed | fabricant |
| `ond_isc_max_mppt_a` | 40 | A | 40 A | [Huawei product page - SUN2000-12/15/17/20/25KTL-M5 Technical Specification (Thailand site, English table)](https://solar.huawei.com/th/professionals/all-products/SUN2000-12-15-17-20-25KTL-M5/specs) | page read 2026-11-24; no version printed | fabricant |
| `ond_ac_kw` | 20.0 | kW | 20,000 W | [Huawei product page - SUN2000-12/15/17/20/25KTL-M5 Technical Specification (Thailand site, English table)](https://solar.huawei.com/th/professionals/all-products/SUN2000-12-15-17-20-25KTL-M5/specs) | page read 2026-11-24; no version printed | fabricant |
| `ond_phases` | 3 |  | Three phase | [Huawei product page - SUN2000-12/15/17/20/25KTL-M5 Technical Specification (Thailand site, English table)](https://solar.huawei.com/th/professionals/all-products/SUN2000-12-15-17-20-25KTL-M5/specs) | page read 2026-11-24; no version printed | fabricant |
| `ond_rendement_euro_pct` | 98.1 | % | 98.1% | [Huawei product page - SUN2000-12/15/17/20/25KTL-M5 Technical Specification (Thailand site, English table)](https://solar.huawei.com/th/professionals/all-products/SUN2000-12-15-17-20-25KTL-M5/specs) | page read 2026-11-24; no version printed | fabricant |
| `ond_dc_max_kwc` | 30.0 | kWp | 30,000 Wp | [Huawei product page - SUN2000-12/15/17/20/25KTL-M5 Technical Specification (Thailand site, English table)](https://solar.huawei.com/th/professionals/all-products/SUN2000-12-15-17-20-25KTL-M5/specs) | page read 2026-11-24; no version printed | fabricant |

Non publié par le fabricant : ond_conso_nuit_w.

### Onduleur réseau Huawei 25kW Triphasé — OND-R-HUA-25T

Modèle identifié : **Huawei SUN2000-25KTL-M5** · certitude : probable.

Note : Catalogue: "Modele suppose SUN2000-25KTL-M5, a confirmer". The existing sheet matches M5 (1100 V, 200-1000 V, euro, dc_max); the older M2 generation prints 1,080 V / 160-950 V and does not match. ond_conso_nuit_w: not published - no night/standby row in the Huawei M5 spec page, nor in the M5 datasheet (reseller copy, Version No. 03-202403, checked) nor in the M5 user manual issue 08 (searched "night", "consumption", "standby"). For ond_i_max_mppt_a see the complement.

| Champ | Valeur | Unité | Comme imprimé | Source | Date | Type |
|---|---|---|---|---|---|---|
| `ond_n_mppt` | 2 |  | 2 | [Huawei product page - SUN2000-12/15/17/20/25KTL-M5 Technical Specification (Thailand site, English table)](https://solar.huawei.com/th/professionals/all-products/SUN2000-12-15-17-20-25KTL-M5/specs) | page read 2026-11-24; no version printed | fabricant |
| `ond_mppt_v_min` | 200 | V | 200 V ~ 1000 V | [Huawei product page - SUN2000-12/15/17/20/25KTL-M5 Technical Specification (Thailand site, English table)](https://solar.huawei.com/th/professionals/all-products/SUN2000-12-15-17-20-25KTL-M5/specs) | page read 2026-11-24; no version printed | fabricant |
| `ond_mppt_v_max` | 1000 | V | 200 V ~ 1000 V | [Huawei product page - SUN2000-12/15/17/20/25KTL-M5 Technical Specification (Thailand site, English table)](https://solar.huawei.com/th/professionals/all-products/SUN2000-12-15-17-20-25KTL-M5/specs) | page read 2026-11-24; no version printed | fabricant |
| `ond_v_max_abs` | 1100 | V | 1100 V | [Huawei product page - SUN2000-12/15/17/20/25KTL-M5 Technical Specification (Thailand site, English table)](https://solar.huawei.com/th/professionals/all-products/SUN2000-12-15-17-20-25KTL-M5/specs) | page read 2026-11-24; no version printed | fabricant |
| `ond_i_max_mppt_a` | {"two_strings": 30, "single_string": 20} | A | 30 A (two string) / 20 A (single string) | [Huawei product page - SUN2000-12/15/17/20/25KTL-M5 Technical Specification (Thailand site, English table)](https://solar.huawei.com/th/professionals/all-products/SUN2000-12-15-17-20-25KTL-M5/specs) | page read 2026-11-24; no version printed | fabricant |
| `ond_isc_max_mppt_a` | 40 | A | 40 A | [Huawei product page - SUN2000-12/15/17/20/25KTL-M5 Technical Specification (Thailand site, English table)](https://solar.huawei.com/th/professionals/all-products/SUN2000-12-15-17-20-25KTL-M5/specs) | page read 2026-11-24; no version printed | fabricant |
| `ond_ac_kw` | 25.0 | kW | 25,000 W | [Huawei product page - SUN2000-12/15/17/20/25KTL-M5 Technical Specification (Thailand site, English table)](https://solar.huawei.com/th/professionals/all-products/SUN2000-12-15-17-20-25KTL-M5/specs) | page read 2026-11-24; no version printed | fabricant |
| `ond_phases` | 3 |  | Three phase | [Huawei product page - SUN2000-12/15/17/20/25KTL-M5 Technical Specification (Thailand site, English table)](https://solar.huawei.com/th/professionals/all-products/SUN2000-12-15-17-20-25KTL-M5/specs) | page read 2026-11-24; no version printed | fabricant |
| `ond_rendement_euro_pct` | 98.2 | % | 98.2% | [Huawei product page - SUN2000-12/15/17/20/25KTL-M5 Technical Specification (Thailand site, English table)](https://solar.huawei.com/th/professionals/all-products/SUN2000-12-15-17-20-25KTL-M5/specs) | page read 2026-11-24; no version printed | fabricant |
| `ond_dc_max_kwc` | 37.5 | kWp | 37,500 Wp | [Huawei product page - SUN2000-12/15/17/20/25KTL-M5 Technical Specification (Thailand site, English table)](https://solar.huawei.com/th/professionals/all-products/SUN2000-12-15-17-20-25KTL-M5/specs) | page read 2026-11-24; no version printed | fabricant |

Non publié par le fabricant : ond_conso_nuit_w.

### Onduleur réseau Huawei 50kW Triphasé — OND-R-HUA-50T

Modèle identifié : **Huawei SUN2000-50KTL-M3** · certitude : probable.

Note : Catalogue: "Modele suppose SUN2000-50KTL-M3, a confirmer". Maker spec page and datasheet 230907 agree. ond_dc_max_kwc: not published (no "recommended max PV power" row in either). The existing sheet says 6 MPPT; the maker prints 4 MPPT (8 inputs).

| Champ | Valeur | Unité | Comme imprimé | Source | Date | Type |
|---|---|---|---|---|---|---|
| `ond_n_mppt` | 4 |  | 4 | [Huawei product page - SUN2000-50KTL-M3 Technical Specification](https://solar.huawei.com/pk/products/SUN2000-50KTL-M3/specs) | page read 2026-11-24; no version printed | fabricant |
| `ond_mppt_v_min` | 200 | V | 200 V ~ 1,000 V | [Huawei product page - SUN2000-50KTL-M3 Technical Specification](https://solar.huawei.com/pk/products/SUN2000-50KTL-M3/specs) | page read 2026-11-24; no version printed | fabricant |
| `ond_mppt_v_max` | 1000 | V | 200 V ~ 1,000 V | [Huawei product page - SUN2000-50KTL-M3 Technical Specification](https://solar.huawei.com/pk/products/SUN2000-50KTL-M3/specs) | page read 2026-11-24; no version printed | fabricant |
| `ond_v_max_abs` | 1100 | V | 1,100 V | [Huawei product page - SUN2000-50KTL-M3 Technical Specification](https://solar.huawei.com/pk/products/SUN2000-50KTL-M3/specs) | page read 2026-11-24; no version printed | fabricant |
| `ond_i_max_mppt_a` | 30 | A | 30 A | [Huawei product page - SUN2000-50KTL-M3 Technical Specification](https://solar.huawei.com/pk/products/SUN2000-50KTL-M3/specs) | page read 2026-11-24; no version printed | fabricant |
| `ond_isc_max_mppt_a` | 40 | A | 40 A | [Huawei product page - SUN2000-50KTL-M3 Technical Specification](https://solar.huawei.com/pk/products/SUN2000-50KTL-M3/specs) | page read 2026-11-24; no version printed | fabricant |
| `ond_ac_kw` | 50.0 | kW | 50,000 W | [Huawei product page - SUN2000-50KTL-M3 Technical Specification](https://solar.huawei.com/pk/products/SUN2000-50KTL-M3/specs) | page read 2026-11-24; no version printed | fabricant |
| `ond_phases` | 3 |  | 3W+(N)+PE | [Huawei product page - SUN2000-50KTL-M3 Technical Specification](https://solar.huawei.com/pk/products/SUN2000-50KTL-M3/specs) | page read 2026-11-24; no version printed | fabricant |
| `ond_rendement_euro_pct` | 98.0 | % | 98.0% | [Huawei product page - SUN2000-50KTL-M3 Technical Specification](https://solar.huawei.com/pk/products/SUN2000-50KTL-M3/specs) | page read 2026-11-24; no version printed | fabricant |
| `ond_conso_nuit_w` | 5.5 | W | <= 5.5W | [Huawei product page - SUN2000-50KTL-M3 Technical Specification](https://solar.huawei.com/pk/products/SUN2000-50KTL-M3/specs) | page read 2026-11-24; no version printed | fabricant |

Non publié par le fabricant : ond_dc_max_kwc.

**Écarts avec la fiche de production :**
- {"champ": "ond_n_mppt", "fiche_existante": 6, "datasheet": 4, "commentaire": "existing sheet value equals none of the datasheet value(s) read"}

### Onduleur réseau Huawei 100kW Triphasé — OND-R-HUA-100T

Modèle identifié : **Huawei SUN2000-100KTL-M2** · certitude : probable.

Note : Catalogue: "Modele suppose SUN2000-100KTL-M2, a confirmer". The M1 sibling prints 26 A per MPPT (not 30 A); the existing sheet (30 A, 98.4%) matches M2. ond_dc_max_kwc: not published (no recommended-max-PV-power row in the M2 datasheet).

| Champ | Valeur | Unité | Comme imprimé | Source | Date | Type |
|---|---|---|---|---|---|---|
| `ond_n_mppt` | 10 |  | 10 | [Huawei - Smart Energy Controller SUN2000-100KTL-M2 datasheet](https://solar.huawei.com/admin/asset/v1/pro/view/e40e432cf2bc4c60b76e1905ea67f324.pdf) | no version printed; PDF metadata 2024-09-03 | fabricant |
| `ond_mppt_v_min` | 200 | V | 200 V - 1000 V | [Huawei - Smart Energy Controller SUN2000-100KTL-M2 datasheet](https://solar.huawei.com/admin/asset/v1/pro/view/e40e432cf2bc4c60b76e1905ea67f324.pdf) | no version printed; PDF metadata 2024-09-03 | fabricant |
| `ond_mppt_v_max` | 1000 | V | 200 V - 1000 V | [Huawei - Smart Energy Controller SUN2000-100KTL-M2 datasheet](https://solar.huawei.com/admin/asset/v1/pro/view/e40e432cf2bc4c60b76e1905ea67f324.pdf) | no version printed; PDF metadata 2024-09-03 | fabricant |
| `ond_v_max_abs` | 1100 | V | 1100 V | [Huawei - Smart Energy Controller SUN2000-100KTL-M2 datasheet](https://solar.huawei.com/admin/asset/v1/pro/view/e40e432cf2bc4c60b76e1905ea67f324.pdf) | no version printed; PDF metadata 2024-09-03 | fabricant |
| `ond_i_max_mppt_a` | 30 | A | 30 A | [Huawei - Smart Energy Controller SUN2000-100KTL-M2 datasheet](https://solar.huawei.com/admin/asset/v1/pro/view/e40e432cf2bc4c60b76e1905ea67f324.pdf) | no version printed; PDF metadata 2024-09-03 | fabricant |
| `ond_isc_max_mppt_a` | 40 | A | 40 A | [Huawei - Smart Energy Controller SUN2000-100KTL-M2 datasheet](https://solar.huawei.com/admin/asset/v1/pro/view/e40e432cf2bc4c60b76e1905ea67f324.pdf) | no version printed; PDF metadata 2024-09-03 | fabricant |
| `ond_ac_kw` | 100.0 | kW | 100000 W | [Huawei - Smart Energy Controller SUN2000-100KTL-M2 datasheet](https://solar.huawei.com/admin/asset/v1/pro/view/e40e432cf2bc4c60b76e1905ea67f324.pdf) | no version printed; PDF metadata 2024-09-03 | fabricant |
| `ond_phases` | 3 |  | 3W+(N)+PE | [Huawei - Smart Energy Controller SUN2000-100KTL-M2 datasheet](https://solar.huawei.com/admin/asset/v1/pro/view/e40e432cf2bc4c60b76e1905ea67f324.pdf) | no version printed; PDF metadata 2024-09-03 | fabricant |
| `ond_rendement_euro_pct` | 98.4 | % | 98.4% @ 400 V | [Huawei - Smart Energy Controller SUN2000-100KTL-M2 datasheet](https://solar.huawei.com/admin/asset/v1/pro/view/e40e432cf2bc4c60b76e1905ea67f324.pdf) | no version printed; PDF metadata 2024-09-03 | fabricant |
| `ond_conso_nuit_w` | 3.5 | W | < 3.5 W | [Huawei - Smart Energy Controller SUN2000-100KTL-M2 datasheet](https://solar.huawei.com/admin/asset/v1/pro/view/e40e432cf2bc4c60b76e1905ea67f324.pdf) | no version printed; PDF metadata 2024-09-03 | fabricant |

Non publié par le fabricant : ond_dc_max_kwc.

### Onduleur réseau Huawei 150kW Triphasé — OND-R-HUA-150T

Modèle identifié : **Huawei SUN2000-150K-MG0** · certitude : probable.

Note : Catalogue: "Modele suppose SUN2000-150K-MG0". All existing values match. Not published: ond_dc_max_kwc (no recommended-max-PV-power row; only a DC/AC ratio table 0.8-1.6 in the preliminary SUN5000-150K sibling sheet, not a kWp) and ond_conso_nuit_w (no night-consumption row), checked in the product spec page, the datasheet PDF https://solar.huawei.com/dam/asset/view/2c96bf796f074d8c9b1c8593351451bc.pdf (marked Preliminary Version) and a second Huawei brochure PDF.

| Champ | Valeur | Unité | Comme imprimé | Source | Date | Type |
|---|---|---|---|---|---|---|
| `ond_n_mppt` | 7 |  | 7 | [Huawei product page - SUN2000-150K-MG0 Technical Specification](https://solar.huawei.com/pk/products/SUN2000-150K-MG0/specs) | page read 2026-11-24; no version printed | fabricant |
| `ond_mppt_v_min` | 200 | V | 200 V ~ 1,000 V | [Huawei product page - SUN2000-150K-MG0 Technical Specification](https://solar.huawei.com/pk/products/SUN2000-150K-MG0/specs) | page read 2026-11-24; no version printed | fabricant |
| `ond_mppt_v_max` | 1000 | V | 200 V ~ 1,000 V | [Huawei product page - SUN2000-150K-MG0 Technical Specification](https://solar.huawei.com/pk/products/SUN2000-150K-MG0/specs) | page read 2026-11-24; no version printed | fabricant |
| `ond_v_max_abs` | 1100 | V | 1,100 V | [Huawei product page - SUN2000-150K-MG0 Technical Specification](https://solar.huawei.com/pk/products/SUN2000-150K-MG0/specs) | page read 2026-11-24; no version printed | fabricant |
| `ond_i_max_mppt_a` | 48 | A | 48 A | [Huawei product page - SUN2000-150K-MG0 Technical Specification](https://solar.huawei.com/pk/products/SUN2000-150K-MG0/specs) | page read 2026-11-24; no version printed | fabricant |
| `ond_isc_max_mppt_a` | 66 | A | 66 A | [Huawei product page - SUN2000-150K-MG0 Technical Specification](https://solar.huawei.com/pk/products/SUN2000-150K-MG0/specs) | page read 2026-11-24; no version printed | fabricant |
| `ond_ac_kw` | 150.0 | kW | 150,000 W | [Huawei product page - SUN2000-150K-MG0 Technical Specification](https://solar.huawei.com/pk/products/SUN2000-150K-MG0/specs) | page read 2026-11-24; no version printed | fabricant |
| `ond_phases` | 3 |  | 380 V/400 V/480 Vac | [Huawei product page - SUN2000-150K-MG0 Technical Specification](https://solar.huawei.com/pk/products/SUN2000-150K-MG0/specs) | page read 2026-11-24; no version printed | fabricant |
| `ond_rendement_euro_pct` | 98.4 | % | 98.4% | [Huawei product page - SUN2000-150K-MG0 Technical Specification](https://solar.huawei.com/pk/products/SUN2000-150K-MG0/specs) | page read 2026-11-24; no version printed | fabricant |

Non publié par le fabricant : ond_dc_max_kwc; ond_conso_nuit_w.

### Onduleur injection 30kW Triphasé — sans référence

Modèle identifié : **Huawei SUN2000-30KTL-M3 (inferred from the existing sheet values)** · certitude : probable.

Note : Catalogue: name "Onduleur injection 30kW" (three-phase), brand "Huazei" (typo for Huawei), no SKU, no description. The existing sheet (4 MPPT, 200-1000 V, 26 A, 40 A, 98.4%) matches the SUN2000-30KTL-M3 column exactly, hence probable - an inference from the sheet, not a maker statement. ond_dc_max_kwc: not published (no recommended-max-PV-power row on the 30/36/40KTL-M3 page). The only datasheet found for this model is the EU compilation (PDF metadata 2022); no newer 30KTL-M3 document was found.

| Champ | Valeur | Unité | Comme imprimé | Source | Date | Type |
|---|---|---|---|---|---|---|
| `ond_n_mppt` | 4 |  | 4 | [Huawei - FusionSolar Residential Commercial Datasheet (EU), page SUN2000-30/36/40KTL-M3](https://solar.huawei.com/-/media/Solar/attachment/pdf/eu/datasheet/FusionSolar_Residential_Commercial_Datasheet.pdf) | no version printed on the page; PDF metadata 2022-06-20 | fabricant |
| `ond_mppt_v_min` | 200 | V | 200 V ~ 1000 V | [Huawei - FusionSolar Residential Commercial Datasheet (EU), page SUN2000-30/36/40KTL-M3](https://solar.huawei.com/-/media/Solar/attachment/pdf/eu/datasheet/FusionSolar_Residential_Commercial_Datasheet.pdf) | no version printed on the page; PDF metadata 2022-06-20 | fabricant |
| `ond_mppt_v_max` | 1000 | V | 200 V ~ 1000 V | [Huawei - FusionSolar Residential Commercial Datasheet (EU), page SUN2000-30/36/40KTL-M3](https://solar.huawei.com/-/media/Solar/attachment/pdf/eu/datasheet/FusionSolar_Residential_Commercial_Datasheet.pdf) | no version printed on the page; PDF metadata 2022-06-20 | fabricant |
| `ond_v_max_abs` | 1100 | V | 1,100 V | [Huawei - FusionSolar Residential Commercial Datasheet (EU), page SUN2000-30/36/40KTL-M3](https://solar.huawei.com/-/media/Solar/attachment/pdf/eu/datasheet/FusionSolar_Residential_Commercial_Datasheet.pdf) | no version printed on the page; PDF metadata 2022-06-20 | fabricant |
| `ond_i_max_mppt_a` | 26 | A | 26 A (per MPPT) / 20 A (per Input) | [Huawei - FusionSolar Residential Commercial Datasheet (EU), page SUN2000-30/36/40KTL-M3](https://solar.huawei.com/-/media/Solar/attachment/pdf/eu/datasheet/FusionSolar_Residential_Commercial_Datasheet.pdf) | no version printed on the page; PDF metadata 2022-06-20 | fabricant |
| `ond_isc_max_mppt_a` | 40 | A | 40 A | [Huawei - FusionSolar Residential Commercial Datasheet (EU), page SUN2000-30/36/40KTL-M3](https://solar.huawei.com/-/media/Solar/attachment/pdf/eu/datasheet/FusionSolar_Residential_Commercial_Datasheet.pdf) | no version printed on the page; PDF metadata 2022-06-20 | fabricant |
| `ond_ac_kw` | 30.0 | kW | 30,000 W | [Huawei - FusionSolar Residential Commercial Datasheet (EU), page SUN2000-30/36/40KTL-M3](https://solar.huawei.com/-/media/Solar/attachment/pdf/eu/datasheet/FusionSolar_Residential_Commercial_Datasheet.pdf) | no version printed on the page; PDF metadata 2022-06-20 | fabricant |
| `ond_phases` | 3 |  | 3W/N+PE | [Huawei - FusionSolar Residential Commercial Datasheet (EU), page SUN2000-30/36/40KTL-M3](https://solar.huawei.com/-/media/Solar/attachment/pdf/eu/datasheet/FusionSolar_Residential_Commercial_Datasheet.pdf) | no version printed on the page; PDF metadata 2022-06-20 | fabricant |
| `ond_rendement_euro_pct` | 98.4 | % | 98.4% | [Huawei - FusionSolar Residential Commercial Datasheet (EU), page SUN2000-30/36/40KTL-M3](https://solar.huawei.com/-/media/Solar/attachment/pdf/eu/datasheet/FusionSolar_Residential_Commercial_Datasheet.pdf) | no version printed on the page; PDF metadata 2022-06-20 | fabricant |
| `ond_conso_nuit_w` | 5.5 | W | <=5.5W | [Huawei - FusionSolar Residential Commercial Datasheet (EU), page SUN2000-30/36/40KTL-M3](https://solar.huawei.com/-/media/Solar/attachment/pdf/eu/datasheet/FusionSolar_Residential_Commercial_Datasheet.pdf) | no version printed on the page; PDF metadata 2022-06-20 | fabricant |

Non publié par le fabricant : ond_dc_max_kwc.

## 4. Produits sans fabricant — impossibles à sourcer

Aucune fiche publique n'existe pour ces articles génériques ; rien n'est inventé pour eux : Panneau mono 550W (PAN-550M); Panneau mono 450W (PAN-450M); Panneau poly 330W (PAN-330P); Batterie 5 kWh (BAT-5K); Batterie Lithium 5 kWh (BAT-LIT-5); Batterie Gel 2.2 kWh (BAT-GEL-22); Onduleur réseau Huawei 10kW Monophasé (OND-R-HUA-10M); Onduleur réseau Huawei 12kW Monophasé (OND-R-HUA-12M); Onduleur réseau 10kW (OND-10KR); Onduleur hybride 5kW (OND-5KH); Micro-onduleur 800W (OND-800M).

