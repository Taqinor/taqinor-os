# RHOR — constats hors de mes fichiers (27/10/2026)

PR RHOR : #1087 (vague 1 : ombrage du calepinage, VE possédée, courbe de saison au derate, étude bancable TTC) et #1095 (vague 2 : AMOT64 productible, RHOR5 « jamais remboursé », RHOR6 économie « avec batterie » nette hors horaire). Toutes les corrections de chiffres sont gardées par `regles_au_moins(devis, 3)`.

## RGEN (solar.js / DevisGenerator.jsx)
1. Parité RHOR6 : hors moteur horaire, le PDF imprime l'économie « avec » nette (`pricing._economie_avec_nette`) ; l'écran (`solar.js` ~600-650) imprime encore le brut avec `battPart` dans le seul cashflow. Pour la parité : `ecoAnnuelleAvec × (1 − 0,10 × battPart)` à l'affichage et `batteryShare: 0` dans le cashflow.
2. AMOT64 : `rendement_global` est retiré de Paramètres, mais `DevisGenerator.jsx` ~1277-1292 le lit encore dans `quoteLogic.efficiency` (`solar.js:462`), ce qui laisse un multiplicateur invisible. Recommandé : `efficiency: EFFICIENCY` en dur.
3. Ombrage : le kWh/an de l'écran (`solar.js`) ignore `ombrage_servi`. Avec un calepinage, l'écran affiche donc une production plus haute que l'étude et le PDF.

## RPDF (PDF résidentiel)
1. « Retour en 3.0 ans » : séparateur décimal en point (devis anonymisé 1271, 1086 « 5.3 ans »), alors que le reste du document est à la française.
2. Repli legacy `generate_devis_premium.py` ~1898-1914 : « Retour en 0.0 ans » possible quand l'économie est nulle (pas de garde ROI ≤ 0).
3. Le bloc garanties de la page 3 contredit les fiches de la page 2 : panneau « 25 ans » contre fiche « 30 ans », onduleur « 10 ans » contre fiche « 5 ans ».
4. « Provision onduleur année 12 » imprime le prix de l'onduleur de la seule option 2.
5. Hypothèse « Tarif électricité 1,60 MAD/kWh saisi » alors qu'en modèle horaire l'économie est valorisée au barème du distributeur (devis 1086 : ≈ 1,97 MAD/kWh implicite). La ligne vient de `etude_restitution.py`.
6. Goldens : la PR #1087 ne bouge pas la production sans calepinage. Seuls bougent `courbes_journalieres.production` (−7 %) et, via #1095, l'économie « avec » des devis sans bloc horaire.

## RWEB (page /proposition)
1. `proposition.ts` (`formatPayback(q.roi_s|roi_a)`, ~2293 / ~4438) et `[...token].astro` ~2490 ignorent `roi_*_jamais` : la page affiche « Rentabilisé en 25 ans » quand le PDF dit « non rentabilisé ».

## RSIZ (dimensionnement)
1. `perte_ombrage_du_devis(devis)` existe (`apps/ventes/horaire/ombrage.py`). Le balayage de taille (`dimensionnement.py`, `offres_tailles.py`) ne passe pas encore `perte_ombrage_pct`, et l'empreinte de `domain/entrees.py` n'inclut pas la perte.
