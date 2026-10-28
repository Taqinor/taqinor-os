# AGC (client agricole) — R1 du 27/10 : constats pour les autres sessions

Branche `claude/agr-agc` (locale, pas poussée — jeton n° 13).

## Ce que j'ai changé qui touche les autres
- `generate_devis_premium._cartes_pompage_synthese` délègue maintenant à `quote_engine/agricole/onepage.cartes_pompage(g, synthese)`
  (−50 lignes, aucune croissance). Plus de « (hypothèse) » sur la carte eau du une-page agricole.
- Golden legacy `golden/moteur/legacy/onepage_agricole.json` : bougera (je le recapture au push, je suis recapteur agricole).
  Aucun golden `build_quote_data` ne bouge (mes changements sont dans la synthèse de rendu).
- `lib/propositionAgricole.ts` : nouveau libellé `AGR_LBL_AGQ.eauJourEstimation` (pour la puce du héro, appel d'une ligne demandé à RWEB).
- `lib/serviceFaq.ts` : section POMPAGE seulement — « comme nos toitures » retiré (D-AGR-10).

## Constats hors de mes fichiers (messages envoyés)
- RWEB : puce héro `eau_m3_jour` de `[...token].astro:2527` sans « estimation » ; mon-toit agricole m³/jour (débit × 7 h par défaut) sans « estimation ».
- CCAT : `VEI-SI22-AFF` décrit « Afficheur déporté pour variateur VEICHI SI22 », imprimé sous un SI23 au une-page.
- RPDF : repli sans synthèse de `legacy_onepage.py:190-220` (« (hypothèse) », « Débit estimé » en dur).
- AGM (info) : un devis auto « pompe existante » ne persiste PAS `mode_pompe` dans `etude_params` (seulement `entrees_pompage.plaque`) ;
  je le déduis côté synthèse (AGC9), mais persister `entrees_pompage.mode_pompe` serait plus propre.
- Catalogue anonymisé : 3 CV / 50 m / 8 m³/h et 30 CV / 100 m / 41 m³/h refusés « aucune pompe chiffrable » (pas d'OSP à ces points).

## Recette rendu agricole
`backend/django_core/_agc_rendu.py` dans mon worktree (vigorous-banach-394458) : adaptation du script AGM, vrai chemin `registre_renderers()`,
prix de test + barème de charges patché en mémoire + délai SAV, tout en transaction annulée.
