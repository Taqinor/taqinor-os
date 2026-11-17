---
name: decisions-audit-1711
description: 17/11/2026 — D-ASUP-8 : refuser l'anonymisation d'un client (fiche ou demande de droit) tant qu'il doit encore de l'argent sur une facture émise ou porte un contentieux ouvert ; tâche ASUP70
metadata:
  type: project
---

Reda a répondu le 17/11/2026 (question interactive, session `loop audit`) à la question posée par les contre-visites ASUP
du 14 et du 17/11 : « Faut-il refuser l'anonymisation d'un client qui a une créance ouverte ou un contentieux ? »
Réponse : **refuser** (D-ASUP-8 dans `docs/audits/decisions.yml`). Rien n'est construit par la réponse : elle ouvre la
tâche ASUP70 (`docs/plans/PLAN_AUDIT_TRANSVERSE.md`, propriétaires lead, facturation, deploy).

**Why:** une créance à recouvrer est un intérêt légitime à garder l'identité. Sans refus, la lettre de relance, la balance
âgée et le dossier contentieux sortent au nom « Client anonymisé », sans adresse : on ne peut plus réclamer l'argent.

**How to apply:**
- Le refus vaut côté serveur (la porte fait foi : 409 avec un motif français qui dit quoi faire — encaisser le solde, ou le
  solder par un avoir ou un abandon de créance) ET à l'écran (le motif s'affiche dans la boîte de confirmation).
- Il vaut pour tous les chemins qui anonymisent le client : « Anonymiser (RGPD) » de la fiche et le traitement d'une
  demande d'effacement (garde d'effacement de `core.dsr`), y compris pour un client sans e-mail ni téléphone.
- « Créance ouverte » = l'encours déjà calculé (factures `emise`/`en_retard`, reste dû > 0) ; jamais un second calcul.
- « Contentieux » : les modules litiges et juridique sont parqués (aucun dossier vivant) ; une facture contestée non
  soldée compte comme créance. Rebrancher les dossiers contentieux au retour du module.
- La rétention automatique des prospects n'est pas concernée (elle ne touche que des clients sans facture).
