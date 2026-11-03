import { Badge } from '../../../ui'

/* ACVI74 — l'état de parcage SERVI (`parc_etat`, `parc_raison`, `parc_jusqu_au`,
   contrat `crm/contract_samples/lead.json`), lu sur la carte kanban et le rail :
   écrit par le seul `parquer_lead` côté serveur, jamais ici. */
const RAISONS = {
  injoignable: 'Injoignable',
  pas_maintenant_sans_date: 'Pas maintenant (sans date)',
  plus_tard_date: 'Plus tard (date du client)',
  budget: 'Budget',
  trop_cher: 'Trop cher',
  concurrent: 'Concurrent',
  achete_ailleurs: 'Acheté ailleurs',
  non_proprietaire: 'Non propriétaire',
  pas_de_toit: 'Pas de toit',
  technique: 'Raison technique',
  faux_numero: 'Faux numéro',
  doublon: 'Doublon',
  test: 'Fiche de test',
  archive_odoo: 'Contact Odoo froid archivé',
}

// Une date seule, sans fuseau : jamais décalée d'un jour par un `new Date()`.
const jourFr = (iso) => iso.split('-').reverse().join('/')

export default function BadgeParcage({ lead }) {
  const etat = lead?.parc_etat
  if (!etat) return null
  const libelle = etat === 'standby'
    ? (lead.parc_jusqu_au ? `En attente jusqu'au ${jourFr(lead.parc_jusqu_au)}` : 'En attente')
    : { nurture: 'Nurture', archive: 'Archive' }[etat] ?? etat
  const raison = RAISONS[lead.parc_raison]
  return (
    <Badge tone="neutral" data-testid="badge-parcage" title={raison}>{libelle}</Badge>
  )
}
