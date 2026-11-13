---
name: decisions-audit-1311
description: 13/11/2026 — 13 réponses du fondateur (toutes l'option recommandée) aux décisions ouvertes des audits de parcours PF9 à PF12 (ACNC, ASUP, ACEL, AERR) ; 21 tâches débloquées
metadata:
  type: project
---

Reda a répondu le 13/11/2026 (questions interactives, session `loop audit`) aux 13 décisions restées ouvertes dans
`docs/audits/decisions.yml`. Toutes prennent l'option recommandée. Rien n'est construit par ces réponses : elles débloquent
21 tâches, sorties des sections « GATED » des plans.

**Suppression, archivage (D-ASUP)**
- D-ASUP-1 : à l'effacement d'une personne, ses anciennes valeurs sont caviardées dans le journal d'audit ; la trace du
  changement reste.
- D-ASUP-2 : un compte d'employé qui a laissé des traces se désactive, il ne se supprime pas.
- D-ASUP-3 : un produit qui a des mouvements de stock ne se supprime pas définitivement ; il reste archivé.
- D-ASUP-4 : l'export d'une demande d'accès est supprimé à l'effacement de la personne ; seule la trace de la demande reste.
- D-ASUP-5 : le journal d'audit des pièces comptables (factures, avoirs, paiements, mouvements de stock) se garde 10 ans,
  quel que soit le réglage.
- D-ASUP-6 : archiver un lead signé est refusé comme la sortie de « Signé » (409 tant qu'une facture, un BC ou un chantier
  avancé existe). Voir [[lead-sortie-signe-desaccepte]].

**Tâches planifiées (D-ACEL)**
- D-ACEL-1 : l'heure d'envoi choisie pour un rapport programmé est respectée (passage chaque heure de 6 h à 23 h).
- D-ACEL-2 : les réglages sans écran qui allument une tâche planifiée reçoivent leur interrupteur à l'écran ; ils ne sont pas
  retirés.
- D-ACEL-3 : la page d'état publique dit « inconnu, données périmées » au-delà de 15 minutes sans contrôle.

**Gestes rejoués (D-ACNC)**
- D-ACNC-1 : un second paiement identique (même facture, même montant, même jour) n'est accepté qu'après une confirmation
  explicite.
- D-ACNC-2 : un encaissement groupé dont toutes les factures sont déjà soldées est refusé ; il ne devient plus une avance.

**Erreurs à l'écran (D-AERR)**
- D-AERR-1 : une action publicitaire approuvée et pas encore appliquée chez Meta peut revenir à « proposée ».
- D-AERR-2 : changer l'étape d'un lead au clavier ou par la palette affiche un toast « Annuler » comme le kanban ;
  confirmation seulement vers « Signé ».

**Why:** ces décisions bloquaient 21 tâches d'audit ; sans réponse elles restaient hors file.

**How to apply:** lire la clé dans `docs/audits/decisions.yml` avant de construire une tâche marquée `D-<groupe>-<n> = <clé>` ;
ne jamais rouvrir ces questions. Constat du même jour : une tâche répondue reste invisible du planificateur tant qu'elle
est rangée sous un titre « GATED » — il faut la sortir de la section, pas seulement changer son marqueur.
