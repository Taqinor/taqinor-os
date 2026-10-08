# Décisions fondateur — audits (SAV, facturation, acquisition, moteur, chantiers, deploy, générateur, lead), 08/10/2026

Posées par AskUserQuestion le 08/10/2026 (plans `docs/plans/PLAN_AUDIT_*.md`). Rien n'est construit par cette
note : chaque décision débloque ses tâches de construction.

## SAV
- **ASAV90 — garantie d'un équipement posé en remplacement.** (a) La garantie repart à la date du remplacement,
  durée du neuf, au moins la fin restante de l'ancien.
- **ASAV91 — garantie de pose / légale d'un chantier réceptionné.** (a) Affichage « garantie à confirmer » ;
  jamais facturé d'office.
- **ASAV92 — facturation récurrente des contrats de maintenance.** (a) Retirer la case et les échéances de
  facturation récurrente ; le prix reste affiché.
- **ASAV93 — monitoring (supervision, SLA disponibilité, certificats carbone, pertes catégorisées).** (b) Les
  RENDRE UTILISABLES (API + écran), une tâche par fonction : ASAV100-ASAV103. ASAV72 (option « réserve hors MVP »)
  est remplacée, à ne pas construire.
- **ASAV94 — SLA d'un ticket.** Q1 (a) le délai repart de la réouverture ; Q2 (a) l'interrupteur
  `sla_breach_enabled` ne gouverne que les notifications (l'échéance est toujours calculée).
- **ASAV95 — couverture d'un ticket.** (a) Jugée à la date d'ouverture du ticket.
- **ACHT94 — parc SAV à la réception.** (a) Les biens à garantie sont suivis à l'unité.

## Facturation / PDF
- **AFAC80** annulation d'une facture qui porte de l'argent : (a) refus 400 + choix imposé (directive d'acompte).
- **AFAC81** paiement mal saisi : (a) état « annulé (erreur de saisie) » + contre-écriture.
- **AFAC82** mandat de prélèvement : (b) GARDER visible et inerte (PAS parqué).
- **AFAC83** paiement en ligne : (a) une seule pile (lien FG53).
- **AFAC84** note de débit émise : (a) annulation par avoir + note de débit partielle.
- **AFAC85** abandon de créance : (a) enregistrement daté cumulable.
- **AFAC86** garde légale J+7 (CAD122) : (a) sur tout encaissement, sous réserve du juriste (CADM3).
- **AFAC87** promesse de paiement partielle honorée : (a) oui.
- **AFAC88** générateur hors ERP : (a) retirer `tools/facture` + le JSON client versionné.
- **AFAC89** facture contestée : (a) drapeau « contestée ».
- **APDF92** langue des documents dérivés : (a) avoir, note de débit, reçu et relance traduits (client arabe) ;
  mention de repli ailleurs, y compris pour l'anglais.

## Acquisition
- **AACQ90** seuils/plafonds `*_mad` : (a) devise du compte, sans taux de change ; règle refusée si la devise
  change.
- **AACQ95 + AACQ96 — Odoo.** La synchro avec Odoo est MANUELLE, jamais automatique ; c'est TOUJOURS l'ERP qui
  fait foi ; on travaille dans l'ERP, pas dans Odoo : les leads sont traités dans l'ERP et restent à l'étape
  « Nouveau » dans Odoo. Conséquence : Odoo ne modifie jamais un lead ERP (aucun recul écrasé, aucune
  perte/signature appliquée depuis Odoo, un lead perdu dans Odoo ne change rien dans l'ERP). Construit par
  AACQ97 (couper les tâches beat et le réalignement 30 min D-CRX3) ; AACQ31/33/34 doivent suivre.

## Moteur PDF
- **AMOT1** langue des PDF résidentiel 3 p. / legacy : (a) tout traduire.
- **AMOT2** une-page signé au domicile : (a) annexe de rétractation en 2ᵉ page légale.
- **AMOT3** « Hypothèses ROI » vs PVGIS : (a) option recommandée.
- **AMOT4** horizon / dégradation / actualisation : (a) option recommandée.
- **AMOT5** lettres de relance : (a) sans délai chiffré ni intérêts sauf réglages société.
- **AMOT6** m³/jour par similitude : (a) imprimé « estimation » + mois le plus serré.
- **AMOT7** pompe existante à débit déclaré : (a) autoriser le m³/jour, étiqueté. Cela AMENDE la règle CLAUDE.md
  « Pompage sizing » : phrase corrigée à recopier par le fondateur (CLAUDE.md n'est pas édité ici) :
  « Never print m³/jour for curve-less pumps (omit the card), EXCEPT an existing pump with a declared flow
  (D-AGR-7), where m³/jour is printed labelled "débit déclaré". »
  Dépendants hors de ce périmètre : AMOT64 (AMOT3) et AMOT65 (AMOT6), dans PLAN_AUDIT_TRANSVERSE.md, à dégater
  par la session propriétaire.

## Chantiers
- **ACHT90** montants estimés d'une demande d'achat : masqués (même règle que le prix d'achat, D-ASTK-2).
- **ACHT91** synchro terrain : (a) étendre `/installations/sync/` (`client_ts` + `base_updated_at`, détection de
  conflit de `offlinesync/conflicts.py`).
- **ACHT95** modèle de checklist : (a) checklist figée à la création.

## Deploy
- **ADEP90** suites sécurité FastAPI : (a) lane PR légère `fastapi_ia`.
- **ADEP91** e-mail : (b) NE RIEN DÉRIVER ; Reda pose `EMAIL_BACKEND` lui-même, l'ERP affiche
  « e-mail non opérationnel » tant qu'il manque. (ADEP92 reste NON tranchée : lecture prod des noms de
  variables d'abord.)

## Générateur / Lead
- **AGNR4** devis avec deux factures (hiver / été) : (a) option recommandée. **AGNR43** : (a) retirer le curseur
  « Consommation diurne (%) ».
- **ADEV61** lead PERDU dont le client signe : (a) lever Perdu → Signé. **ADEV62** V2 d'un devis déjà accepté :
  (a) seulement une tâche « faire signer l'avenant » (aucune cadence « après devis »).

Ne jamais re-demander ces questions.
