# DECISION — Convergence des chatters historiques vers `records.Activity` (ARC9)

**Statut : Étape 1 livrée (additive). Étape 2 = GATE FONDATEUR — aucune migration
de données n'est lancée sans accord explicite de Reda.**

## Contexte

Le dépôt porte **14 modèles « chatter » maison quasi identiques** (le plan en
comptait 13 ; l'inventaire réel ci-dessous en trouve 14, `installations` en
ayant trois). Tous répètent la même forme `kind/field/old_value/new_value/
body/user/timestamp`, avec des noms de champs qui divergent légèrement
(`message` vs `body`, `auteur` vs `user`, `date_creation` vs `created_at`,
`type` vs `kind`). Depuis ARC8, `records.Activity` porte cette même forme en
GÉNÉRIQUE (GenericFK + `ALLOWED_TARGETS`) avec le service unique
`records.services.log_activity` et le mixin `ChatterViewSetMixin` (pilotes :
`contrats.Contrat`, `flotte.Vehicule`).

## Étape 1 — livrée dans ARC9 (additive, ZÉRO risque)

Une **enveloppe de lecture uniforme** pour que le frontend (VX23
ChatterTimeline) consomme UN format quel que soit le modèle source :

- Sérialiseur commun : `records.serializers.UniformChatterSerializer`
  (clés : `id, kind, field, field_label, old_value, new_value, body,
  user_username, created_at, source`).
- Selectors par app (lecture seule, aucune table modifiée) :
  - `apps/crm/selectors.lead_chatter_envelope(lead)`
  - `apps/sav/selectors.ticket_chatter_envelope(ticket)`
  - `apps/contrats/selectors.contrat_chatter_envelope(contrat)` — normalise
    `type→kind` (`log`→`modification`), `message→body`, `auteur→user_username`,
    `date_creation→created_at`.
- Testée sur les 3 apps : `apps/records/tests_chatter_envelope.py`.

Les autres apps s'ajoutent au même patron (un selector de ~15 lignes chacune)
au fil du besoin frontend — sans gate, c'est purement additif.

## Inventaire des tables (le périmètre de l'étape 2)

Volumétrie : les comptes de lignes ne sont PAS connus en local. **Requête à
exécuter par le fondateur sur la prod** (une seule, lecture seule) :

```sql
SELECT relname AS table_name, n_live_tup AS lignes_estimees
FROM pg_stat_user_tables
WHERE relname IN (
  'crm_leadactivity', 'sav_ticketactivity', 'ventes_devisactivity',
  'ventes_factureactivity', 'contrats_contratactivity',
  'flotte_activiteflotte', 'ged_documentactivity',
  'gestion_projet_projetactivity', 'litiges_reclamationactivity',
  'rh_dossieractivity', 'rh_candidatureactivity',
  'installations_installationactivity',
  'installations_interventionactivity',
  'installations_ordreassemblageactivity'
) ORDER BY n_live_tup DESC;
```

Estimation qualitative à partir des modèles (volume attendu ∝ activité métier ;
chaque modification de champ suivi = 1 ligne, plus les notes) :

| # | Modèle | Table | Volume attendu | Particularités de schéma |
|---|--------|-------|----------------|--------------------------|
| 1 | `crm.LeadActivity` | `crm_leadactivity` | **Élevé** (~40 champs suivis × leads + notes + kinds `appel`/`email` + `outcome` + `bulk`) | 2 kinds et 2 colonnes EN PLUS de la forme commune (`outcome`, `bulk`) → à porter dans `records.Activity` ou à geler en l'état |
| 2 | `sav.TicketActivity` | `sav_ticketactivity` | Moyen-élevé | Forme commune exacte |
| 3 | `ventes.DevisActivity` | `ventes_devisactivity` | Moyen-élevé | Forme commune exacte |
| 4 | `ventes.FactureActivity` | `ventes_factureactivity` | Moyen | Forme commune exacte |
| 5 | `installations.InstallationActivity` | `installations_installationactivity` | Moyen | Forme commune exacte |
| 6 | `installations.InterventionActivity` | `installations_interventionactivity` | Moyen | Forme commune |
| 7 | `contrats.ContratActivity` | `contrats_contratactivity` | Faible-moyen | Noms maison (`type/message/auteur/date_creation`), pas de `field_label` |
| 8 | `gestion_projet.ProjetActivity` | `gestion_projet_projetactivity` | Faible-moyen | Sous-ciblage `cible_type`/`cible_id` (Projet + Tache + Jalon dans la même table, XPRJ26) — mappe naturellement vers le GenericFK de records |
| 9 | `litiges.ReclamationActivity` | `litiges_reclamationactivity` | Faible | Forme commune |
| 10 | `ged.DocumentActivity` | `ged_documentactivity` | Faible-moyen | Journal d'événements majeurs (versions/statut/partage/signature) — vocabulaire de kinds propre |
| 11 | `rh.DossierActivity` | `rh_dossieractivity` | Faible | Noms maison `type`=log/note (patron ContratActivity) |
| 12 | `rh.CandidatureActivity` | `rh_candidatureactivity` | Faible | Noms maison `type`=log/note (patron ContratActivity) |
| 13 | `flotte.ActiviteFlotte` | `flotte_activiteflotte` | Faible | Champs FR (`champ/ancienne_valeur/nouvelle_valeur`), double clé `type_objet/objet_id` + FK `vehicule` — le moins conforme |
| 14 | `installations.OrdreAssemblageActivity` | `installations_ordreassemblageactivity` | Faible | Forme commune |

Hors périmètre (PAS des chatters — jamais migrés par ce plan) :
`crm.PlanActivite`, `crm.EtapePlanActivite` (gabarits de plans d'activités),
`sav.TicketActiviteAFaire` (à-faire planifié), `flotte.JournalStatutVehicule`
(journal de statut dédié XFLT4).

## Étape 2 — plan de migration table-par-table (GATE FONDATEUR)

Principe absolu : **pont réversible — jamais de drop**. Chaque table migre en 3
phases, indépendamment des autres, dans l'ordre du moins risqué au plus gros :

**Ordre proposé** : 14→9 du tableau (volumes faibles d'abord :
`OrdreAssemblageActivity`, `ActiviteFlotte`, `CandidatureActivity`,
`DossierActivity`, `DocumentActivity`*, `ReclamationActivity`…), puis les
moyens (`ProjetActivity`, `ContratActivity`, `InterventionActivity`,
`InstallationActivity`, `FactureActivity`, `DevisActivity`,
`TicketActivity`), et **`LeadActivity` en DERNIER** (le plus gros volume ET
2 colonnes hors forme commune). *`DocumentActivity` pourrait aussi être gelé
définitivement en journal spécialisé (décision au moment de sa phase A).

Pré-requis technique (une migration additive sur `records.Activity`, à faire
au lancement de la phase A de la 1ʳᵉ table) : deux colonnes de provenance
`legacy_source` (varchar, ex. `'crm.leadactivity'`) + `legacy_id` (int,
nullable), avec contrainte d'unicité `(legacy_source, legacy_id)` — c'est ce
qui rend le backfill IDEMPOTENT et le pont réversible.

- **Phase A — double-écriture** (réversible en désactivant un flag) : le module
  d'écriture de l'app (ex. `apps/crm/activity.py`) écrit sa ligne legacy COMME
  AUJOURD'HUI **et** appelle `records.services.log_activity(...)`. Un flag par
  table (`CHATTER_DOUBLE_WRITE = {'crm.leadactivity': True, ...}` dans
  settings) permet d'armer/désarmer sans déploiement de schéma. Un backfill
  `manage.py backfill_chatter <app.model>` copie l'historique (idempotent via
  `(legacy_source, legacy_id)`).
- **Phase B — bascule lecture** (réversible en re-basculant le selector) : le
  selector d'enveloppe de l'app (étape 1) lit `records.Activity` au lieu de la
  table maison. Le frontend ne voit AUCUNE différence (même enveloppe). On
  vérifie l'égalité des timelines (commande de diff : legacy vs records sur N
  jours) avant de basculer.
- **Phase C — gel** : l'écriture legacy est retirée (la double-écriture devient
  écriture simple côté records). La table maison reste EN PLACE, en lecture
  seule, indéfiniment — **jamais de DropTable ni de suppression de lignes**.
  Le garde-fou `scripts/check_platform.py` (ARC8) empêche déjà toute NOUVELLE
  table chatter d'apparaître pendant la convergence.

Chaque phase de chaque table = un point d'arrêt naturel ; un incident se
résout en revenant d'une phase (flag off / re-bascule du selector), sans perte
de données puisque les deux écritures coexistent en phase A/B.

## Ce qui est explicitement demandé au fondateur

1. Exécuter la requête de volumétrie ci-dessus et coller le résultat ici.
2. Valider (ou amender) l'ordre de migration proposé.
3. Donner le GO table par table pour la phase A (la 1ʳᵉ table proposée :
   `installations_ordreassemblageactivity`, la plus petite).
