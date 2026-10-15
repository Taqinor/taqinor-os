import { PageHeader } from '../../ui/PageHeader'
import { VENTES_ACCENT_STYLE } from './accent'

/* En-tête de page du module Ventes : `PageHeader` avec l'accent laiton du module
   (rail d'accent). Mêmes props que PageHeader. Un seul endroit — jamais recopié
   écran par écran. */
export default function EnteteVentes(props) {
  return <PageHeader style={VENTES_ACCENT_STYLE} className="app-accent-rail" {...props} />
}
