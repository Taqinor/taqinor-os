# CORC — constats R1 hors de ma surface (rendu réel, 27/10/2026)

Pile locale : instantané anonymisé (société 156) + leads démo 2227-2231 + lead 2195 (copie du vrai lead boulangerie).
Code : `main` + #1070 + mon split #1079. Devis automatiques composés dans une transaction annulée (rien écrit), PDF
`build_quote_data(devis, {...})` + `generate_premium_pdf`. Mesures : ~5 s par devis auto (15 s à froid), 2 appels `etudier_ci`
par devis (création + rafraîchissement), 16-88 appels `economie_ci.valoriser` (balayage de taille), 29-68 s pour 2 PDF.

Tailles retenues (sans batterie / avec batterie si différente) :
- boulangerie 6 000 kWh/mois 7/7 6-22 h → 30,03 kWc / 52,2 kWc ; 157 700 MAD / 473 100 MAD TTC ; retour 6,4 / 7,2 ans
- bureaux 5 000 kWh/mois 5/7 8-18 h → **60,06 kWc** (≈ 92 MWh/an produits pour 60 MWh/an consommés, week-ends vides) — **CLD : à vérifier**, sur-dimensionné ?
- hôtel 15 000 kWh/mois 7/7 24 h → 65 kWc / **136 kWc avec 18 batteries 16 kWh (288 kWh)** — **CMP : taille de l'option « avec » à vérifier**
- supermarché 20 000 kWh/mois → 135 kWc ; usine textile MT 60 000 kWh/mois → 255 kWc (1 053 000 MAD)

## PDF boulangerie (lead 2227, 3 pages) — CPDF / CEC
> **ATTENTION (correction CPDF, 27/10 après-midi)** : ces PDF ont été rendus par `generate_premium_pdf(build_quote_data(...))`,
> qui sert le GABARIT RÉSIDENTIEL, pas le vrai rendu C&I de `/proposal` (`builder.generate_premium_devis_pdf` →
> `commercial.renderer` / `industriel.renderer`). Les points 1-8 ci-dessous sont donc **à revérifier sur le vrai rendu**
> (recette : `CPDF-recette-rendu.md`) avant toute correction ; ne pas construire sur eux tels quels. Le point 9
> (`recommended`) porte sur la DONNÉE servie par `build_quote_data` : il reste valable (corrigé par CORC9, #1080).
1. **« Autoconsommation retenue : 60 % sans batterie · 96 % avec batterie »** (page 3, hypothèses) — taux FIXES, interdits
   (« aucun taux fixe C&I ») ; ce bloc ne lit pas l'étude horaire C&I. Idem « Tarif électricité : référence prudente (estimation) »
   alors que le lead déclare BT patenté. → CPDF/CEC.
2. Page 3 : bloc « NOTRE ENGAGEMENT » imprimé PAR-DESSUS l'en-tête « BON POUR ACCORD » (chevauchement). → CPDF.
3. Page 2 : le graphique « Économies mensuelles » est coupé par le pied de page (débordement). → CPDF.
4. Incertitudes imprimées (interdites, fondateur 26/10) : « Économies estimées (approximatif) — à confirmer sur vos factures »,
   « hypothèse de référence, le constructeur de ce produit ne publie pas cette valeur », « Estimations non contractuelles ». → CPDF.
5. « Provision de remplacement de l'onduleur en année 12 : 96 000 MAD (le prix de l'onduleur de ce devis) » : l'option sans
   batterie a UN onduleur à 29 167 MAD HT ; 96 000 = les 2 hybrides de l'option avec ? Ambigu sur un devis à deux options. → CEC/CPDF.
6. Panneaux : colonne garantie « — » (fiche sans garantie dans le catalogue) ; « Coffret DC », « Disjoncteur AC… » sans marque. → CCAT.
7. L'option « avec » a un Logger de supervision, l'option « sans » non (« Suivi en temps réel … via le matériel chiffré au devis »
   reste affiché pour les deux). → CMP/CPDF.
8. `build_quote_data(devis, {'format': 'onepage'})` produit le MÊME PDF que `'full'` (même taille) : quelle est la bonne clé
   d'options pour la une-page ? (§4 du guide à préciser). → CPDF.
9. RECOMMANDÉ sur « Avec batterie » : **corrigé côté CORC (CORC9, PR #1080)** — mais `builder.py` retombe encore sur
   « Avec batterie » pour un C&I sans `recommended_option` stocké (anciens devis, devis du générateur) : la règle
   `utils.options.option_mise_en_avant` (C&I → SANS) devrait servir de repli dans `builder`. → CPDF.

## Catalogue / instantané — CCAT + propriétaire securite
- L'instantané anonymisé n'emporte ni `stock.FicheTechnique` (0 fiche → tout devis C&I refusé « Pmax ») ni
  `CompanyProfile.forfaits_ci`. Je les ai recopiés en local. Tâche à router au propriétaire de `authentication/anonymise.py`.
