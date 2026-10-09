---
name: apdf-decisions-fondateur
description: 09/10/2026 — décisions D-APDF-1/2/4 de l'audit pdf (bande légale du devis, identifiants légaux sur les documents chantier, place des prestations)
metadata:
  type: project
---

Audit pdf du 08/10/2026 (groupe APDF, en-tête dans `docs/plans/PLAN_AUDIT_MOTEUR.md`). Option (a) recommandée retenue à chaque fois, choisi par Reda via la question interactive du 09/10/2026 (ne jamais re-demander) :

- **D-APDF-1 = (a)** (APDF90) : la bande légale du devis est lue du seul profil société, avec deux champs nouveaux (capital social, forme juridique) ; AUCUN gérant imprimé ; le profil TAQINOR réel est renseigné AVANT la suppression des littéraux.
- **D-APDF-2 = (a)** (APDF91) : ICE / IF / RC / patente sur le BL chantier (FR et AR), le PV de réception et le dossier de remise. La règle légale exacte n'a pas été vérifiée sur texte de loi (dit au fondateur).
- **D-APDF-3** (APDF92) : tranchée le 08/10/2026, voir `docs/plans/PLAN_AUDIT_FACTURATION.md`.
- **D-APDF-4 = (a)** (APDF93) : prestations (Installation, Transport) exclues du PV et du BL ; section « Prestations » sans garantie dans le dossier de remise ; recatégorisation en type service au seed et rattrapage des nomenclatures gelées.

**Why:** impressions légales et garanties client-visibles incohérentes selon le format (deux ICE, « Transport — Garantie selon conditions constructeur »).
**How to apply:** les tâches APDF portant @after APDF90/91/93 lisent ces décisions.
