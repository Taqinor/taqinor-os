---
name: lead-sortie-signe-desaccepte
description: Décision fondateur 08/10/2026 — un lead qui sort de « Signé » par une action utilisateur dés-accepte son devis (retour « envoyé », effets auto défaits) ; bloqué en 409 si une suite réelle existe
metadata:
  type: project
---

Décision de Reda (08/10/2026). Quand un lead QUITTE « Signé » par une action utilisateur (glisser kanban, édition d'étape, `set_stage` en masse — jamais les recyclages automatiques), ses devis acceptés actifs repassent « envoyé » : tampons d'acceptation effacés (une ré-acceptation est fraîche : `devis_accepted` repart, chantier recréé/réactivé, célébration du SigneDialog), sœurs refusées PAR cette acceptation rétablies, et ce que l'acceptation a créé tout seul est défait (chantier annulé — drapeau, jamais supprimé —, contrat SAV désactivé, commission « À payer » → « Approuvé », parrainage « Converti » → « En attente »). Les cadences arrêtées à la signature ne redémarrent pas seules (note au chatter).

S'il existe une suite RÉELLE — facture non annulée (brouillon comprise), bon de commande non annulé, dossier 82-21 déposé, chantier avancé (étape, pose planifiée, intervention, stock sorti), contrat SAV engagé — le changement d'étape est REFUSÉ (409, rien d'écrit) avec une phrase qui nomme la cause ; en masse, le lead est sauté avec la raison.

La preuve de signature du client (DevisSignature, PDF scellé) n'est JAMAIS supprimée : une note de chatter (devis + lead) dit qui a annulé, quand, et l'option annulée.

**Why:** avant, sortir de « Signé » ne changeait que l'étape ; le devis restait « accepté » et y revenir tombait en 409 « Ce devis est déjà accepté » (pas de célébration).

**How to apply:** porte unique `ventes.services.annuler_acceptation` + événement `core.events.devis_acceptation_annulee` (abonnés installations/sav/crm) ; blocages via les `selectors.py` de chaque app. `avancer_stage_pour_devis` reste « jamais en arrière ».
