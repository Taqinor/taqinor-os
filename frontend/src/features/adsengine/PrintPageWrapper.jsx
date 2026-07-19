import { Printer } from 'lucide-react'

/* ============================================================================
   PUB47 — enveloppe d'impression pour un écran possédé par une AUTRE lane
   (ici : AdsCockpitScreen, `frontend/adsengine-wiring`/`-console` selon la
   vague — cette lane NE modifie PAS son corps).
   ----------------------------------------------------------------------------
   Ajoute un bouton « Imprimer / PDF » (`window.print()`, zéro dépendance) +
   la classe d'ancrage `ae-print-area` autour des enfants, SANS toucher au
   composant enveloppé : la feuille globale `src/styles/print.css` (VX80) fait
   le reste (chrome masqué, tables complètes, noir-sur-blanc, `@page` A4/2cm).
   Monté UNIQUEMENT au point d'enregistrement de route (`module.config.jsx`),
   jamais à l'intérieur de l'écran lui-même.

   PUB52 — `extraActions` (optionnel) : autres liens/boutons posés dans la
   même barre `no-print` (ex. un lien vers le Comparateur depuis le Cockpit),
   même patron « au point d'enregistrement de route », jamais dans l'écran.
   ========================================================================== */
export default function PrintPageWrapper({ children, extraActions }) {
  return (
    <div className="ae-print-wrapper">
      <div className="no-print" data-testid="ae-print-wrapper-bar"
        style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: '0.5rem',
          padding: '0.5rem 1rem 0' }}>
        {extraActions}
        <button type="button" className="btn btn-light" data-testid="ae-print-wrapper-btn"
          onClick={() => window.print()}
          style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
          <Printer size={15} aria-hidden="true" /> Imprimer / PDF
        </button>
      </div>
      <div className="ae-print-area">{children}</div>
    </div>
  )
}
