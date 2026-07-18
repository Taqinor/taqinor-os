import { getField } from './draftCore'

// LW10 — Placeholder MINCE du rail identité (zone gauche, 288px).
// Contrat de props (blueprint) : { state, onAction(type), users }.
// Fleshed out par LANE 2 (LW14-LW18 : identité, score+raisons, triade,
// chips QX28, bannières, pile d'actions).
export default function IdentityRail({ state /* , onAction, users */ }) {
  const nom = `${getField(state, 'nom') || ''} ${getField(state, 'prenom') || ''}`.trim()
  const societe = getField(state, 'societe')
  const ville = getField(state, 'ville')
  return (
    <aside className="lw-zone lw-rail-identity" data-testid="lw-identity-rail">
      <p className="lw-rail-name">{nom || 'Lead'}</p>
      {(societe || ville) && (
        <p className="lw-rail-sub">{[societe, ville].filter(Boolean).join(' · ')}</p>
      )}
      <p className="lw-rail-hint">Rail identité — construit par LW14-LW18.</p>
    </aside>
  )
}
