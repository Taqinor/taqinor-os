// LW19 — Placeholder MINCE de l'onglet Devis (rendu par `ContextRail`).
// Fleshed out par LW21 (cartes devis, CTA « Devis automatique » / champs
// manquants cliquables, actions facture/chantier, mini-piste document) et
// LW22 (barre d'envoi WhatsApp multi-devis FR/Darija).
export default function DevisTab({ state }) {
  const nbDevis = (state?.server?.devis ?? []).length
  return (
    <div className="lw-context-devis">
      <p className="gen-hint">Devis — {nbDevis} (LW21-LW22).</p>
    </div>
  )
}
