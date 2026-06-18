import { cn } from '../lib/cn'
import { badgeVariants } from './Badge'

/* G29 — StatusPill : UNE taxonomie de statut commune (leads / devis / factures /
   chantiers / tickets SAV). Mappe une valeur de statut connue vers un ton ; un
   `tone` explicite l'emporte. Un point coloré aide ceux qui ne distinguent pas
   bien les couleurs (la couleur n'est jamais le seul signal). */

const norm = (v) =>
  String(v ?? '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '') // diacritiques
    .replace(/[\s-]+/g, '_')

export const STATUS_TONES = {
  // Devis
  brouillon: 'neutral', envoye: 'info', accepte: 'success', refuse: 'danger', expire: 'warning',
  // Factures / paiement
  payee: 'success', paye: 'success', impayee: 'danger', impaye: 'danger',
  partielle: 'warning', partiel: 'warning', en_retard: 'danger',
  // Chantiers
  signe: 'neutral', materiel_commande: 'info', planifie: 'info', en_cours: 'warning',
  installe: 'info', receptionne: 'success', cloture: 'success',
  // SAV
  ouvert: 'danger', resolu: 'success', clos: 'neutral',
  // Leads (étapes STAGES.py + perdu)
  new: 'neutral', contacted: 'info', quote_sent: 'info', follow_up: 'warning',
  signed: 'success', cold: 'neutral', perdu: 'danger',
  // Génériques
  actif: 'success', inactif: 'neutral', annule: 'danger',
}

const DOT = {
  neutral: 'bg-muted-foreground', primary: 'bg-primary', info: 'bg-info',
  success: 'bg-success', warning: 'bg-warning', danger: 'bg-destructive', outline: 'bg-foreground',
}

export function statusTone(value) {
  return STATUS_TONES[norm(value)] ?? 'neutral'
}

export function StatusPill({ status, label, tone, dot = true, className, ...props }) {
  const resolved = tone ?? statusTone(status)
  return (
    <span className={cn(badgeVariants({ tone: resolved }), className)} {...props}>
      {dot && <span aria-hidden="true" className={cn('size-1.5 rounded-full', DOT[resolved])} />}
      {label ?? status}
    </span>
  )
}

export default StatusPill
