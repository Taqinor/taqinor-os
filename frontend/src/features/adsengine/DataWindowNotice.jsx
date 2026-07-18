import { Info, AlertTriangle } from 'lucide-react'
import { DATA_WINDOWS } from './adsengine'

/* ============================================================================
   ADSDEEP66 — Bandeau générique « fenêtre / limite de données ».
   ----------------------------------------------------------------------------
   Généralise `LeadRetentionNotice` (ADSDEEP23, leads 90 j) à TOUTES les
   fenêtres de données Meta que le moteur affiche sans jamais le dire :
   - ``leads``      : Meta efface les leads après 90 jours.
   - ``insights``   : insights détaillés disponibles 37 mois glissants.
   - ``uniques``    : métriques UNIQUES (portée/reach, fréquence) 13 mois.
   - ``breakdowns`` : ventilations audience/diffusion synchronisées sur 28 j.
   - ``retention``  : rétention brute générale Meta, 13 mois.
   Les presets (fenêtre + messages FR) vivent dans ``adsengine.js`` (helpers
   PURS, sans JSX) — ce fichier reste 100 % composant.

   Doctrine (« pas de plafond silencieux ») : un écran qui affiche un nombre
   borné dans le temps DOIT dire sa fenêtre — sinon le chiffre a l'air complet
   alors qu'il ne l'est pas. Purement présentationnel (aucune donnée réseau) ;
   passe en variante ALERTE quand ``ageDays`` (âge de la donnée la plus
   ancienne encore visible) approche la limite de la fenêtre.
   ========================================================================== */

// Seuil d'alerte = 5/6 de la fenêtre (identique au ratio 75/90 j historique
// de LeadRetentionNotice pour ``leads``), appliqué à toutes les fenêtres.
const WARN_RATIO = 5 / 6

export default function DataWindowNotice({ kind, ageDays = null, message, testId }) {
  const preset = DATA_WINDOWS[kind]
  const windowDays = preset ? preset.windowDays : null
  const warnThreshold = windowDays != null ? windowDays * WARN_RATIO : null
  const warn =
    typeof ageDays === 'number' &&
    warnThreshold != null &&
    ageDays >= warnThreshold
  const Icon = warn ? AlertTriangle : Info
  const baseMessage = message || preset?.message || ''
  const tid = testId || `ae-data-window-${kind || 'custom'}`

  if (!baseMessage) return null

  return (
    <div
      data-testid={tid}
      data-variant={warn ? 'warning' : 'info'}
      data-kind={kind || ''}
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
        {baseMessage}
        {warn && (
          <strong data-testid={`${tid}-alert`}>
            {' '}{preset?.warnMessage || 'Attention : fenêtre de données proche de sa limite.'}
          </strong>
        )}
      </span>
    </div>
  )
}
