// CADV74 / ERR-ACVI9-KANBAN-FROID — les raisons d'une mise au Froid : codes
// Nurture et Archive du contrat `crm/contract_samples/lead.json` (`plus_tard_date`
// exige une date et ne range pas au Froid : hors liste). UNE liste pour le lot et
// pour les gestes unitaires (kanban, liste, fiche).
export const RAISONS_FROID = [
  ['injoignable', 'Injoignable'],
  ['pas_maintenant_sans_date', 'Pas maintenant (sans date)'],
  ['budget', 'Budget'],
  ['trop_cher', 'Trop cher'],
  ['concurrent', 'Concurrent'],
  ['achete_ailleurs', 'Acheté ailleurs'],
  ['non_proprietaire', 'Non propriétaire'],
  ['pas_de_toit', 'Pas de toit'],
  ['technique', 'Raison technique'],
  ['faux_numero', 'Faux numéro'],
  ['doublon', 'Doublon'],
  ['test', 'Fiche de test'],
  ['archive_odoo', 'Contact Odoo froid archivé'],
]

/* Le refus serveur d'un changement d'étape, depuis le CORPS de la réponse : 409
   `{detail}`, `{stage: [...]}` ou `{parc_raison: [...]}` (ACVI9). Vide si aucun. */
export const refusEtape = (corps) => [corps?.detail, corps?.stage?.[0], corps?.parc_raison?.[0], corps?.error]
  .find((m) => typeof m === 'string' && m) ?? ''
