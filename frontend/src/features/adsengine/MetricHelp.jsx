import { useState, useRef, useEffect } from 'react'
import { HelpCircle } from 'lucide-react'
import { METRIC_HELP } from './adsengine'

/* ============================================================================
   PUB54 — Aide contextuelle FR (« ? » pédagogiques), contenu STATIQUE, zéro
   dépendance.
   ----------------------------------------------------------------------------
   Un « ? » à côté de chaque métrique technique, cliquable ET focusable au
   clavier, qui affiche une explication en français simple. Le contenu vit
   ICI (``METRIC_HELP``, clé stable) — n'importe quel écran adsengine peut
   l'adopter (``<MetricHelp metric="frequency" />``), y compris le Cockpit
   quand sa lane le branche (cette lane ne modifie pas son corps).
   ========================================================================== */

// (PUB54) `METRIC_HELP` vit dans adsengine.js — un composant-fichier ne doit
// exporter que des composants (react-refresh/only-export-components).

export default function MetricHelp({ metric, label }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)
  const text = METRIC_HELP[metric]

  useEffect(() => {
    if (!open) return
    const onDoc = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [open])

  // Clé inconnue : ne rend rien plutôt qu'un « ? » vide (jamais de contenu
  // inventé côté écran).
  if (!text) return null

  return (
    <span className="ae-metric-help" data-testid={`ae-metric-help-${metric}`} ref={ref}
      style={{ position: 'relative', display: 'inline-flex', verticalAlign: 'middle', marginLeft: '0.25rem' }}>
      <button type="button" className="ae-metric-help-btn"
        data-testid={`ae-metric-help-toggle-${metric}`}
        aria-label={`Aide : ${label || metric}`}
        aria-expanded={open}
        onClick={(e) => { e.stopPropagation(); setOpen(o => !o) }}
        style={{ border: 'none', background: 'transparent', color: '#94a3b8', cursor: 'pointer',
          display: 'inline-flex', alignItems: 'center', padding: 0, lineHeight: 0 }}>
        <HelpCircle size={13} aria-hidden="true" />
      </button>
      {open && (
        <span role="tooltip" className="ae-metric-help-popover"
          data-testid={`ae-metric-help-popover-${metric}`}
          style={{ position: 'absolute', top: '130%', left: 0, zIndex: 30, width: 240,
            background: '#0f172a', color: '#f1f5f9', padding: '0.5rem 0.65rem', borderRadius: 6,
            fontSize: '0.78rem', lineHeight: 1.4, fontWeight: 400, boxShadow: '0 8px 20px rgba(0,0,0,0.25)' }}>
          {text}
        </span>
      )}
    </span>
  )
}
