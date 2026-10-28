# RSIZ — constats R1 (27/10/2026, nuit)

## Rendu réel — 8 devis auto résidentiels (société 156, Casablanca, terrasse béton, lecture seule)
| Facture/mois | Phase | kWc | Constat |
|---|---|---|---|
| 500 | mono | 2,84 | 2 options OK (3 / 4 panneaux) |
| 1 500 | mono | 5,68 | 2 options OK |
| 6 000 | mono | 19,88 | sans 14 pan. / 2× Huawei 5 kW ; avec 28 pan. / 2× Deye 10 kW mono + 3× Dyness 5 kWh |
| 6 000 | tri | 18,46 | 2 options OK |
| 25 000 | tri | 62,48 | **P0 : pas de variantes ; Huawei 50 kW ET 3× Deye 30 kW dans la même offre, aucune batterie** |
| 80 000 | tri | 187 | idem (1 Huawei 150 kW + 7 Deye 30 kW) |
| 80 000 tri, scenario='avec' | | 187 | **P0 : « avec batterie » sans aucune batterie** |
| 100 000 | tri | 277 | 2 Huawei 150 + 10 Deye 30 |
Câble DC = 60 m fixe pour 3 comme pour 390 panneaux.

## Pour d'autres sessions (hors fichiers RSIZ)
- **RHOR** (`etude_horaire_view.py`) — écart écran ≠ devis auto : en mode lead l'aperçu (a) ignore la facture tapée dans le corps (`_profil_depuis_lead` ne lit que le lead), (b) ne retombe pas sur `lead.raccordement` si le corps n'envoie pas la phase (`_dimensionner` ~l.807), (c) abandonne le GPS du lead si la ville envoyée ≠ `site_ville` (`_localisation` ~l.728), (d) ignore `occupation` envoyée (connu 23/10).
- **RGEN** (`creation_auto_residentiel.py` après CORC) : `taille_souhaitee_kwc` du lead court-circuite le moteur (`source_dimensionnement='taille_demandee'`) sans que l'écran le montre → devis ≠ écran sans bandeau.
- **CCAT** : `postes_pret_devis_residentiel(company)` → RSIZ le livrera au round 2/3 à la forme `pret_devis_ci.json`.
