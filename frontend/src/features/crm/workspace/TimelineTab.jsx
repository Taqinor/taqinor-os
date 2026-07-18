// LW19 — Placeholder MINCE de l'onglet Historique (rendu par `ContextRail`,
// onglet par défaut). Fleshed out par LW20 : en-tête multi-touch
// (points-contact/), filtre par type persisté, notes épinglées en tête
// (ChatterTimeline pinned/onTogglePin), composer porté depuis LeadForm.jsx
// avec l'état du moteur (composer/setComposer/resetComposer).
export default function TimelineTab({ historique }) {
  const n = (historique ?? []).length
  return (
    <div className="lw-context-timeline">
      <p className="gen-hint">Historique — {n} entrée{n > 1 ? 's' : ''} (LW20).</p>
    </div>
  )
}
