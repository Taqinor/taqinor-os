import { Info, AlertTriangle } from 'lucide-react'

/* ============================================================================
   ADSDEEP23 — Bandeau « rétention 90 j » (partagé par les écrans leads).
   ----------------------------------------------------------------------------
   Meta EFFACE les leads après 90 jours ; l'historique complet vit dans
   l'ERP/Odoo. Ce bandeau le rappelle en permanence, et passe en ALERTE quand le
   dernier pull approche la fenêtre (``oldestLeadAgeDays`` ≥ seuil).
   Purement présentationnel — aucune donnée réseau.
   ========================================================================== */

const WINDOW_DAYS = 90
// À partir de cet âge (jours) du plus vieux lead encore côté Meta, on alerte.
const WARN_THRESHOLD_DAYS = 75

const BASE_MESSAGE =
  'Meta efface les leads après 90 jours — l’historique complet vit dans l’ERP/Odoo.'

export default function LeadRetentionNotice({ oldestLeadAgeDays = null }) {
  const warn =
    typeof oldestLeadAgeDays === 'number' &&
    oldestLeadAgeDays >= WARN_THRESHOLD_DAYS
  const Icon = warn ? AlertTriangle : Info

  return (
    <div
      data-testid="ae-lead-retention-notice"
      data-variant={warn ? 'warning' : 'info'}
      role="note"
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: '0.5rem',
        padding: '0.6rem 0.8rem',
        borderRadius: 8,
        margin: '0 0 0.9rem',
        fontSize: '0.85rem',
        background: warn ? '#fef3c7' : '#eff6ff',
        color: warn ? '#92400e' : '#1e40af',
        border: `1px solid ${warn ? '#fde68a' : '#bfdbfe'}`,
      }}
    >
      <Icon size={16} aria-hidden="true" style={{ flexShrink: 0, marginTop: 2 }} />
      <span>
        {BASE_MESSAGE}
        {warn && (
          <strong data-testid="ae-lead-retention-alert">
            {' '}Attention : certains leads approchent la fenêtre de {WINDOW_DAYS} jours —
            synchronisez avant leur suppression côté Meta.
          </strong>
        )}
      </span>
    </div>
  )
}
