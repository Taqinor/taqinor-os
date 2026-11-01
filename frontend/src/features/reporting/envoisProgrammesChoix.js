/* AANA45 / D-AANA-036-BRANCHER — choix de l'écran « Envois programmés ».
   Reprise des énumérations du modèle (`SavedReport.TargetKind`/`Schedule`/
   `CANAL_CHOICES`, `EnvoiRapport.Statut`) ; le vitest les égale à la section
   `choix` de `apps/reporting/contract_samples/rapports_programmes.json` et
   `envois_rapports.json`, que le
   test backend égale lui-même aux choix du modèle. */

export const TARGET_KINDS = [
  ['sales', 'Ventes'], ['stock', 'Stock'], ['service', 'Service'],
  ['dashboard', 'Tableau de bord'], ['query', 'Requête sauvegardée'],
]
// Cibles qui exigent un `cible_id` (`SavedReport.KINDS_AVEC_CIBLE`).
export const KINDS_AVEC_CIBLE = ['dashboard', 'query']
export const SCHEDULES = [
  ['none', 'Aucune'], ['daily', 'Quotidien'], ['weekly', 'Hebdomadaire'],
  ['monthly', 'Mensuel'],
]
export const CANAUX = [['email', 'Email'], ['whatsapp', 'WhatsApp']]
export const STATUTS = [
  ['envoye', 'Envoyé'], ['echec', 'Échec'],
  ['non_configure', 'Canal non configuré'], ['sans_destinataire', 'Aucun destinataire'],
]
