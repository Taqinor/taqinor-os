# Décisions fondateur — audit stock (ASTK), 06/10/2026

Posées par AskUserQuestion pendant `work on the plan audit stock` (docs/plans/PLAN_AUDIT_STOCK.md).

- **ASTK37 — écart d'inventaire.** Réponse : « Stock à la saisie ». L'écart = compté − stock AU MOMENT où
  le compté est saisi (snapshot pris à la saisie), pour les deux chemins (session d'inventaire et comptage
  cyclique). Exemple : stock 100, sortie 20 entre génération et comptage, compté 80 → stock final 80.
  Construit par ASTK39.
- **ASTK172 — `seed_catalogue` et les fiches produit.** Réponse : (a) « Ne remplir que le vide ». Au
  déploiement, le seeder ne comble que marque / description / garantie / garantie_mois VIDES ; écraser
  une saisie reste possible seulement à la main avec `--reappliquer-fiches`. Même règle pour le renommage
  « pendent → pendant » et la réforme TVA rejoués au déploiement. Construit par ASTK176. La phrase
  CLAUDE.md « re-applies product sheets (marque/description/garantie only) » devient fausse : à corriger
  par le fondateur.
- **ASTK171 — RAS-TVA et acompte (07/10/2026).** Réponse : (a) « Toute la TVA ». Facture biens TTC 1 200 /
  TVA 200 / retenue 100 %, réglée par acompte 360 + paiement 840 → retenue totale 200 (pas 140) ; la RAS due
  = TVA × taux de la facture, ventilée sur les règlements, le dernier portant le solde au centime. Aucun
  champ RAS sur l'acompte. Construit par ASTK175.

Ne jamais re-demander ces questions.
