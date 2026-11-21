# Rejeu T1 (rejeu-opus, compte rev_couture, 21/11) — 14 constats rejoués, 14 confirmés, 0 infirmé

Pile http://127.0.0.1:5231 (atelier démarré SANS montage de carte), gestes réels Playwright sur cal 16/18/19/21/22 (leads REV-COUTURE Casablanca 1, Marrakech 2, Agadir 3, Fes 4, Tanger 5). Preuves : `T1/rejeu/cap`, `T1/rejeu/dl` (layouts, devis 68/69/70, PDF /proposal, planche, DXF), mesures `T1/rejeu/mesure_docs.py`. Lignes : `registre/evenements/T1-orchestrateur-rejeu.jsonl`.

| Constat | Verdict | Cause | Client voit ? | Planifié ? |
|---|---|---|---|---|
| F1-004/024 « 8 × 720 W » | confirmé (48 × 720 W à 34,08 kWc ; doc et devis = 710 W, 34,08) | `roofPro11/optimizer.ts::paintCard` l.955 et `zones.ts::renderAreasPanel` l.440 : littéral 720 | non | non |
| F1-020 planche A3 | confirmé : modules couchés 130,4 pt au pas de 72,3 pt (45 % de chevauchement, débordent du cadre) ; réel ≈1/52, imprimé « 1/100 » | `planche.py::_dessin_des_modules` (grand côté toujours en X, aucune orientation enregistrée) + `planche.py::_echelle_nommee` (arrondit au rang SUPÉRIEUR) | non (dossier technique) | non |
| F1-031 DXF | confirmé : 48 × (2,384 × 1,303 m) au pas de 1,323 m ; TOITURE en double | `export_dxf.py::_rectangle` (même emprise) | non | non |
| F1-027 Terrain 25° / 0,6 m | confirmé : 176 mod., vide 0,60 m mesuré, aucun avertissement | `ModeTerrain.helpers.js::demandeMoteur` envoie `polygone` → `politique_pas.py::AlleeFixe` 0,60 m (défaut AO), jamais `surfaces/sol.py` AntiOmbrage | oui (chiffré au devis) | non |
| F1-030 devis du sol | confirmé : DEV-202611-0009 = 218 mod. (42 zone + 176 terrain), Canadian 710 W, PDF 154,78 kWc / 235 266 kWh/an ; nuance : le produit additionne toujours zone + terrain sans lien ni question | `ventes/domain/geometrie.py::pans_du_document` somme pans + poseSurfaces | oui (/proposal) | non |
| S1-017 0 MAD vs TRI | confirmé x2 (TRI 31,64 % / 38,12 %, retour 4 / 3 ans sans facture) | `estimatorBrainV2.ts::annualSavingsMad` (plafond facture=0) vs `quote_engine/pricing.py::calculate_savings_roi` (tarif repli 1,20 + autoconso forfaitaire) lu par `ventes/economie.py::_donnees_du_devis` | non (PDF n'imprime aucune économie) | non |
| S1-023 facture 900 → 0 MAD | confirmé (cible « 4 panneaux » mais 0 MAD, ≈ 0 %) | `atelier/contexteAtelier.js::contexteCalepinageVersPayload` ne passe que le nombre de panneaux ; pas de `#rp9-bill` en mode calepinage → `monthlyBill()` = 0 | non | non |
| S1-007 devis sans facture | confirmé : 168 800 MAD / 34 kWc / onduleur 50 kW, alors que l'écran dit « Données insuffisantes » | `calepinage/services/devis.py::generer_devis` sans garde de dimensionnement | oui (/proposal) | non |
| S1-005 deux productions | confirmé : carte 93 504, total + document 98 574, PDF 111 420 kWh/an | `optimizer.ts::renderLiveWinner` écrête DC/AC, `zones.ts::liveActiveResult` non ; le devis recalcule sur `geometrie.py::orientation_du_pan` (E-O → 22° Sud par défaut) | oui (/proposal) | non |
| S1-018 deux kWc | confirmé : 72 kWc (720 W par défaut) vs 71,00 (onglet Production, devis, PDF « 100 × 710 W » Canadian) | module par défaut hors catalogue remplacé par le 1er 710 W du catalogue | oui (/proposal) | non |
| S1-025 double-clic → triangle | confirmé (~194 → ~97 m²) | `roof-tool-pro11.ts` dblclick → `cancelPendingVertex()` jette le 4e coin | non | non |
| F1-010 / S1-020 « Publiable » | confirmé : onglet « Publiable » avec panneau/onduleur `null`, resume « indetermine », cadre « indéterminé » ; écrêtage MPPT de S1 NON rejoué | `services/electrique.py::_rapport_publication` ne compte pas NON_VERIFIABLE | non | partiel ACAL395 |

Jumeaux : `plan_cablage.py::_coins` (même emprise couchée) ; `roofToolShared.ts` dblclick des simulateurs publics ; `contexteToDevisPayload` (mode devis, sans facture) ; `Ombriere.jsx` « 180 = sud ».
Nouveaux (vus, non enregistrés comme verdicts) : rangées Terrain « 180 = sud » lues face 270° (Ouest) par `pans_du_document` ; même devis : production_annuelle 40 424 (zone seule) vs 154,78 kWc (zone + terrain) ; « Structures acier × 48 / Socles × 96 » chiffrés pour un toit en pente affleurant (DEV-202611-0007, PDF p.2) ; recommandation « Est-Ouest 0° ».

Classes :
1. **Une grandeur calculée à plusieurs endroits** (S1-005, S1-018, S1-017/023, F1-004, F1-010/S1-020) : production (`optimizer.ts::renderLiveWinner` ≠ `zones.ts::liveActiveResult` ≠ `quote_engine`), kWc (`geometry.kwc` 720 W ≠ composition 710 W), économie (`annualSavingsMad` ≠ `calculate_savings_roi`), verdict (`_rapport_publication` ≠ `_consigner_et_servir` ≠ `assistant.py::_bloc_electrique`).
2. **Un défaut présenté comme un choix** (S1-007, S1-018, F1-030, F1-027, F1-010) : module 720 Wc « par défaut » hors catalogue, « on pose ce qui tient » devenu devis, allée AO 0,60 m sous « politique du moteur », E-O décrit en 22° Sud, NON_VERIFIABLE affiché « Publiable ».
3. **Un document dessiné d'une autre géométrie que l'écran** (F1-020, F1-031, S1-005) : orientation portrait/paysage absente de `geometry` → planche/DXF/câblage couchés ; `orientation_du_pan` du devis ≠ pose de l'atelier ; échelle imprimée ≠ échelle dessinée.
4. **Une saisie perdue en route** (S1-023, S1-025) : la facture du lead n'atteint pas l'atelier ; le dernier coin d'un double-clic est jeté.
