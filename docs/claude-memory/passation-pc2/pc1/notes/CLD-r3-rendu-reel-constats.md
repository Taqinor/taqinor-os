# CLD — tour 3 (27/10) : rendu réel de 5 devis C&I auto par le VRAI chemin /proposal (registre_renderers), branche CLD 8b9960c47

Rapport + PDF : C:\Users\kasri\AppData\Local\Temp\claude\C--dev-taqinor-os--claude-worktrees-pensive-panini-e7f910\4767e6b8-e9c7-494d-a07b-8f355ff6c9dd\scratchpad\rendu\v2\rapport.md
Brouillons DEV 1426 (2227 boulangerie), 1427 (2228 bureaux), 1428 (2229 hôtel), 1416 (2230 « supermarché »), 1423 (2231 usine MT).
Complet : commercial ×4, industriel ×1 ; une-page legacy (vrai chemin). Lus page par page : 5 complets FR + EN 2227.
Le premier rendu (chemin legacy) est ANNULÉ : 60 %/100 %, RECOMMANDÉ, écart complet/une-page, graphes coupés, chevauchement,
« revente BT », provision onduleur an 12, nb pages usine — tous DISPARUS sur le vrai chemin.

## CPDF (quote_engine/ci, commercial/industriel)
- **P1 — `quote_engine/ci/mentions.py:114` « Le soir et la nuit … l'option avec batterie la couvre » imprimé sur les 5 devis** :
  faux pour l'usine (batterie 107 kWh pour 945 kWh de besoin nocturne = 37 %). Phrase à conditionner au taux réel.
- **P1 — « (moteur C&I) » et « étude bancable du moteur » imprimés au client** (2231 p.3).
- **P1 — échéancier usine (2231 p.4) : libellé 50/39/10 %, dernier montant 117 744 MAD = 11 %.**
- P2 — note « la page indique TVA 18 % » imprimée (2231 p.1 et p.3).
- P2 — « Onduleur 10 ans » alors que Huawei 50/100 kW = 5 ans.
- P2 — méthode contradictoire (5 PDF) : « heure par heure » p.1 vs « journées moyennes » dans les hypothèses.
- P2 — formulations internes/défensives : « TVA récupérable non déclarée », « VAN omise », « sans rien promettre sur la cuisson ».
- P2 — EN : désignations catalogue + libellé maintenance restent en français. P3 — « 6-22 H » au lieu de « 6-22 h ».

## CMP (batterie/composition)
- P2 — bureaux 2228 option batterie : Deye 15 kW + 2 × 12 kW en parallèle (modèles mixtes).
- P2 — option batterie : champ ×2 (boulangerie 35→79 panneaux, hôtel 91→191) sans explication client.
- P2 — usine : option batterie plus petite (199,5 vs 260,3 kWc) et un peu moins rentable (plus marquée recommandée).

## Démo / pile
- Base DEV sans `crm.0142_categories_commerce_talon` ; lead démo « supermarché » classé `commerce`.

## CLD (moi)
- Bureaux 2228 : ~45 % de surplus non valorisé (écrit p.1). Règle des 10 ans appliquée telle quelle (palier 50 : 6,9 ans ;
  55 : 10,6 ans) → GARDÉ, « Décision prise pour le fondateur (à revoir) » au DONE LOG.
- Taille : identique étude = lignes = PDF complet = une-page (5 leads, 2 options).
