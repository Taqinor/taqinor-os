# CLD — R1 (27/10/2026) : constats hors de mes fichiers, pour leurs propriétaires

Preuves exécutées dans le scratchpad CLD (scripts r1_*.py, q*.py). Moteur sur main + #1070 + #1074 fusionnées en local.

## Pour CORC (`apps/ventes/domain/etude_ci.py`)
- **Toit inconnu : la BORNE de toit est calculée en surimposition** (`POSE_PAR_DEFAUT`, D-ACI-13 du 24/10) alors que la
  composition chiffre un toit plat lesté (décision fondateur du 26/10, plus récente). 300 m² → borne 68,16 kWc au lieu de
  34,08 kWc (contenance lestée). CLD ne touche pas `etude_ci.py`.
- **Fériés jamais passés à `courbe_declaree`** (alerte `feries_non_saisis` systématique) alors que
  `notifications.calendar_utils.feries_entre` existe. CLD fera AU PLUS l'appel d'une ligne (règle du bloc commun) — sauf
  si CORC préfère le faire : dites-le dans ce dossier.
- `annee_reference = année − 1` : CLD corrige le décalage GMT des profils DÉCLARÉS côté `charge.py` (le Maroc est à UTC+0
  depuis le 20/09/2026 ; l'année 2025 donnait +1 h hors Ramadan). Aucun changement requis dans `etude_ci.py`.

## Pour CMP (`moteur_ci/production.py`, `onduleurs.py`, `batterie.py`, `composition.py`)
- Charge admissible du toit (CIQ114) : ne borne jamais la taille, seulement des alertes ; masse de lest du calepinage jamais
  transmise ; pose inconnue ⇒ « masse inconnue » même avec 5 kg/m² déclarés.
- Perf : 875 kWc = 215 évaluations, 19,9 s, ~90 % dans `onduleurs._chercher` (recherche refaite à chaque palier) ;
  2-3 MWc estimés 30-70 s (gunicorn 120 s) ; l'option avec batterie refait un balayage.
- `batterie.py` : même fenêtre de regard de 4 paliers que `taille.py` (CLD l'élargit dans `taille.py` ; à aligner) ;
  critères d'arrêt différents entre option sans / avec batterie.
- Étiquette « Structure C&I (toit_plat_leste) » portée par un article bac acier quand aucun article lesté n'existe.

## Pour le propriétaire lead (CQST / CSV / CVL — `apps/crm/categories_commerciales.py`)
- `REPONSES_CATEGORIE_CLES` est fermé et n'a PAS les clés d'heures que le moteur lit (`heures`, `heures_cuisson`,
  `heures_garde`, `fermeture_du`, `fermeture_au`) : le serializer les rejette, aucun écran ne les produit ⇒ sur un lead, les
  branches restaurant / boulangerie (cuisson de nuit) / école (fermeture) / santé (garde) ne donnent que des alertes
  « à préciser ».

## Mise à jour 27/10 — branchement demandé à CORC (CLD6, CLD4)
- `charge.valeurs_horaires_depuis_points(points, *, pas_min, unite='kwh')` (PR CLD vague 1) : tout pas divisant 60 min, heure `None` si un point manque, `ValueError` FR sinon. À appeler dans `etude_ci._courbe_mesuree_resolue` à la place de `[_num(p) or 0.0 …]` + bloc `pas_minutes == 15` (ValueError → ValidationError `courbe_mesuree`).
- Même geste : `conso = round(sum(mesuree[0]), 3)` (etude_ci ~l.1216) plante sur `None` et sous-compte un relevé partiel.
- Le décalage GMT du régime en vigueur (CLD3) s'applique SANS rien changer dans etude_ci (défaut `decalage_h=None`).
