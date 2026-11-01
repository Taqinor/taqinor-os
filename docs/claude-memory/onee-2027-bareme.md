# Barème ONEE 2027 (D-ONEE-2027, fondateur, 01/11/2026)

- Au 01/11/2026 aucun barème ONEE 2027 n'est publié ; l'ANRE prépare une refonte tarifaire
  annoncée pour le 1er mars 2027 (fin du 1er cycle tarifaire, 28/02/2027). TVA électricité :
  trajectoire finie (20 % depuis 01/01/2026), le PLF 2027 n'en change pas le taux ; le PLF
  prévoit la prise en charge par l'État des factures ≤ 100 DH/mois (pas un changement de prix au kWh).
- Décision (option A) : le barème 2026 reste appliqué jusqu'au 28/02/2027 —
  `MILLESIME_COURANT_VALABLE_JUSQUAU` dans `apps/ventes/quote_engine/bareme.py`, lue par la
  garde AMOT74 (`scripts/check_echeances_reglementaires.py`) à la place du 31/12.
- La garde rougit de nouveau le 30/12/2026 : re-sourcer alors la grille ANRE publiée
  (jamais extrapoler un chiffre).
