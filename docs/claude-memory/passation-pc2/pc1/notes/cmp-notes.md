# CMP — notes (composition, onduleurs, batterie C&I) — 27/10

## R1 (lecture seule, main + #1070) — constats qui touchent d'autres sessions
- **CORC** (`etude_ci._couche_visite`) : la visite SOMME les trajets dans `longueur_dc_m` / `longueur_ac_m`. CMP fixe la
  sémantique côté composition : `longueur_dc_m` = distance ALLER SIMPLE champ → onduleur, câble = 2 × chaînes × distance
  (D-CMP-2, aligné sur le défaut fondateur) ; `longueur_ac_m` = par onduleur. Avec plusieurs trajets, passer le PLUS LONG
  (ou la moyenne), pas la somme — sinon câble × nb_trajets. À toi de trancher (1 ligne dans `_couche_visite`).
- **CCAT** (fiches seed) : (a) Deye SG05LP3 n'a pas `ond_dc_max_kwc` — datasheets : 10K 20 kW, 15K 22,5 kW, 20K 30 kW ;
  (b) Dyness Powerbox Pro 10.24 : `bat_max_modules_par_banc` absent (datasheet 20241231-EN : 10 en parallèle) ;
  (c) Deye 10T `ond_i_max_mppt_a` 26 A / Isc 39 A non confirmés par la datasheet 240927 (20+20 A, Isc 30+30 A) ;
  (d) aucune fiche ne porte `ond_chaines_max_par_mppt` — Huawei 50KTL-M3 2 entrées/MPPT, 150K-MG0 3, M5 2.
- **CEC** : bien reçu P0 (retour option « avec ») — CMP branchera `economie_ci_options` dans `etude_ci_batterie._bloc`
  dès qu'il est sur main ; préviens ici.
- **CPDF / goldens** : CMP1 (chaînes) change les quantités câble DC / protections DC de tous les devis C&I.
- CMP4 (commit local 34282b9e6) : 1 ligne réalignée dans test_ciq118 (CORC) — câble DC déclaré × 2.
- **CORC** (`etude_ci.POSE_PAR_DEFAUT = 'toiture_inclinee'`, D-ACI-13) : la production d'un toit INCONNU est calculée en
  surimposition (montage « building », 30°) alors que la composition le CHIFFRE en toit plat lesté (fondateur 26/10,
  `composition.TYPE_POSE_DEFAUT`). Décision fondateur la plus récente = toit plat lesté ⇒ proposer d'aligner
  POSE_PAR_DEFAUT sur `composition.TYPE_POSE_DEFAUT`. Avec CMP5 (production.py), toit plat sans pente ⇒ 10° (−5,7 %).

## 27/10 après-midi — vague 2 (PR #1094)
- **CPDF** : `etude_ci.option_avec.retour_simple_ans` = retour du flux 25 ans de CEC (CMP6). Le PDF calcule encore son propre
  quotient dans `quote_engine/ci/mentions.py::valeur_option_avec` (~l. 379-401, coût ÷ économie an 1 : 13,5 ans au lieu de 22,1
  dans le cas de test). À faire chez CPDF : lire la clé servie, sinon omettre.
- **CORC** : passer `tva_recuperable` et `flux_options` {degradation, entretien, taux_actualisation_client} à
  `option_avec_de_l_etude` (message envoyé).
