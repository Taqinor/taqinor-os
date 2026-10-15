import { Printer } from 'lucide-react'
import AlertCenter from './AlertCenter'
import CommandPalette from './CommandPalette'

/* Boutons d'en-tête PARTAGÉS de la console Ads (tableau de bord, rapports) :
   impression propre (A4, zéro dépendance nouvelle — distinct des PDF
   WeasyPrint client, règle #4), centre de notifications persistant (PUB48) et
   palette de commandes Ctrl-K (PUB51). */
export default function ActionsConsole({ printTestId }) {
  return (
    <>
      <button type="button" className="btn btn-light" data-testid={printTestId}
        onClick={() => window.print()}
        style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
        <Printer size={15} aria-hidden="true" /> Imprimer / PDF
      </button>
      <AlertCenter />
      <CommandPalette />
    </>
  )
}
