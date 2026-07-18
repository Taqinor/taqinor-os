// LW10 — Placeholder MINCE du rail contexte (zone droite, 384px).
// Contrat de props (blueprint) : { state, refreshHistorique, users }.
// Fleshed out par LANE 3 (LW19-LW21 : onglets ui/Tabs Historique · Devis ·
// Activités · Pièces avec compteurs, chatter+composer, cartes devis).
export default function ContextRail({ state /* , refreshHistorique, users, historique, onAction */ }) {
  const nbDevis = (state.server?.devis ?? []).length
  return (
    <aside className="lw-zone lw-rail-context">
      <p className="lw-rail-hint">
        Contexte — Historique · Devis ({nbDevis}) · Activités · Pièces (LW19-LW21).
      </p>
    </aside>
  )
}
