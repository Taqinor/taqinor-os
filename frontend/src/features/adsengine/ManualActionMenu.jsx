import { useState } from 'react'
import { actionsForScope } from './manualActions'
import ManualActionComposer from './ManualActionComposer'

/* ============================================================================
   PUB22 — Sélecteur d'action manuel PAR LIGNE (Cockpit / Campagnes).
   ----------------------------------------------------------------------------
   Offre les kinds applicables au `scope` de la cible (campaign|adset|ad), et
   ouvre le composeur générique du kind choisi. Toute soumission passe par
   propose_action (boîte d'approbation) — jamais un write Meta direct.
   ========================================================================== */

export default function ManualActionMenu({ target, onProposed }) {
  const options = actionsForScope(target?.scope)
  const [openKind, setOpenKind] = useState('')
  if (!target || !target.metaId || options.length === 0) return null
  const descriptor = openKind ? options.find(o => o.kind === openKind) : null

  return (
    <div className="ae-maction-menu" data-testid="ae-maction-menu"
      style={{ marginTop: '0.6rem' }}>
      <label>
        <span style={{ fontSize: '0.85rem', color: '#475569', marginRight: '0.4rem' }}>
          Proposer une action
        </span>
        <select className="form-input" data-testid="ae-maction-select"
          value={openKind} onChange={e => setOpenKind(e.target.value)}
          style={{ maxWidth: 320, display: 'inline-block' }}>
          <option value="">Choisir…</option>
          {options.map(o => (
            <option key={o.kind} value={o.kind}>{o.label}</option>
          ))}
        </select>
      </label>

      {descriptor && (
        <ManualActionComposer
          key={descriptor.kind}
          descriptor={descriptor}
          target={target}
          onProposed={() => { onProposed?.() }}
        />
      )}
    </div>
  )
}
