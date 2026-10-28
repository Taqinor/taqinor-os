# AGC — validation R3 (agent opus frais, lecture seule) sur claude/agr-agc @ 61faa0a7b — À CORRIGER PAR LE PC2

Aucun test Django ni vitest lancé par le validateur (pas de Django sur l'hôte, Docker interdit) ; py_compile + flake8 CI verts.

## Constats confirmés (à corriger avant la PR)
1. **Golden legacy `apps/ventes/tests/golden/moteur/legacy/onepage_agricole.json` bouge** (carte eau « estimation, 7 h/j » au lieu de
   « … (hypothèse) ») — test `@tag('pdf')`, sauté en CI de PR mais rouge en `release-verify`. Recapturer avec UPDATE_GOLDEN=1 (seul golden qui bouge ;
   aucun `build_quote_data/agricole__*` ni `split_*` ne bouge d'après le validateur — à recouper après #1114 RPDF).
2. **AGC11 imprime « déclarée » sur des mois NON confirmés** : `agricole/pages.py::_depense_declaree` ne teste que `statut == 'calcule'` ;
   `economie_pompage()` (l. 1203-1207) rend non publiable avec `MOTIF_MOIS_CALENDRIER` (mois pré-cochés par le calendrier cultural, AGQ18 :
   « pas une déclaration »). Correctif : `return ""` si `MOTIF_MOIS_CALENDRIER in eco.get("motifs_non_publiable", [])`.
3. **Phrase AGC11 « L'économie sera chiffrée après la visite du point d'eau » fausse** quand le motif est le barème de charges non saisi
   (réglage société, pas la visite) ou `MOTIF_SANS_LIGNE`. Correctif recommandé : retirer la 2e phrase (FR/EN/AR de `agr_depense_declaree_neutre`
   dans `quote_engine/i18n_labels_agricole.py`), ou ne l'imprimer que pour un motif réellement levé par la visite (couverture non vérifiable).
4. **AGC7 (web) : la formule « (investissement + charges sur 10 ans) ÷ … » omet les remplacements** (pompe an 7) dans les cas carburant/réseau ;
   le serveur calcule `(invest + remplacements + charges × 10) ÷ (utile × 10)` (`economie_pompage.py:781-788`) ; le PDF ne l'imprime que pour
   `nouveau_forage`. Correctif : afficher `data-agri-formule-m3` seulement si `argent.economies.cas === 'nouveau_forage'` (SectionAgricole.astro).
5. **AGC9 peut dire « Votre pompe existante » sur un devis pompe NEUVE** dont le lead a renseigné sa pompe actuelle et dont aucune ligne n'a
   `role_pompage == 'pompe'` (ligne saisie à la main). `mode_pompe` n'est jamais persisté (absent de `CLES_ENTREES_POMPAGE`, domain/pompage.py:1356) :
   la lecture `_resolue(..., "mode_pompe")` est morte. Correctif propre : AGM persiste `mode_pompe` résolu dans `entrees_pompage` (+ contrat
   `forme_derivees_lues_par_le_rendu` + `test_amot63::test_forme_figee_au_contrat`) et AGC le lit ; à défaut, restreindre la règle plaque.

## Optionnel
- `i18n_labels_agricole.LIBELLES_AGRICOLE` hors des gardes AGR314 (3 langues + gabarits) et AGR317 (vocabulaire) : les étendre au catalogue neuf.
- Clés inutilisées : `agr_op_eau_jour`, `agr_op_debit_declare`, web `eauJourEstimation` (ce dernier attend l'appel d'une ligne de RWEB).
- `assertIn('Head', html)` faible (« Head office » possible) : viser la cellule.
- « 4,4 h/j en novembre » perd « équivalentes à plein débit ».
- Commentaires périmés : docstring `texte_heures_eau` (une-page), commentaire `CODES_NOTES_CLIENT`.
- `pages._depense_declaree` : continuations de ligne aplaties, à réécrire lisiblement.
- D-AGC-6 va contre la règle `_bloc_economies` « un chiffre non publiable n'atteint pas le document » — à revoir par Reda.
- « pas les panneaux, au taux réduit » ambigu (FR/EN) sur /pompage-solaire.
