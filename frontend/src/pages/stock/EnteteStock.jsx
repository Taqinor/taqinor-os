import { PageHeader } from '../../ui/PageHeader'
import { INVENTAIRE_ACCENT } from '../../features/stock/inventaireAccent'

/* Éléments d'écran PARTAGÉS des écrans entrepôt / négoce (ASTK215+) : l'en-tête
   avec le liseré d'accent Inventaire et les bandeaux erreur / information.
   Un seul endroit — jamais recopié page par page (garde de duplicat littéral). */

/** En-tête de page : mêmes props que PageHeader, accent Inventaire posé. */
export function EnteteStock(props) {
  return (
    <PageHeader
      {...props}
      style={{ '--module-accent': INVENTAIRE_ACCENT }}
      className="app-accent-rail mb-0"
      headingAs="h1"
    />
  )
}

const FORME = 'rounded-lg border p-3 text-sm'
const TEINTES = {
  erreur: ['border-destructive/30', 'bg-destructive/10', 'text-destructive'],
  info: ['border-success/30', 'bg-success/10', 'text-success'],
}

function Bandeau({ role, teinte, children }) {
  return (
    <div role={role} className={[FORME, ...TEINTES[teinte]].join(' ')}>
      {children}
    </div>
  )
}

/** Bandeau d'erreur (role=alert) et d'information (role=status), s'ils sont non vides. */
export function BandeauxStock({ erreur, info }) {
  return (
    <>
      {erreur && <Bandeau role="alert" teinte="erreur">{erreur}</Bandeau>}
      {info && <Bandeau role="status" teinte="info">{info}</Bandeau>}
    </>
  )
}
