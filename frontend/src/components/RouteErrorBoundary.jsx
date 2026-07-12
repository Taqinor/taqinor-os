import { Component } from 'react'
import { AlertTriangle } from 'lucide-react'
// VX185/wave-3 perf: import direct (jamais le barrel `../ui`) — importé
// statiquement par router/index.jsx (-> main.jsx), donc tout ce que le
// barrel touche (dont datatable -> recharts/pdfjs-dist) finirait en
// `<link rel="modulepreload">` sur chaque page, `/login` inclus.
import { Button } from '../ui/Button'

/* L880 — Error-boundary de route GLOBALE.
 *
 * Capture toute erreur de rendu (ou une erreur jetée pendant le rendu, ex. un
 * fetch synchrone qui échoue) survenue dans une page authentifiée et affiche un
 * écran FR de récupération AU LIEU d'une application blanche. Sans cette
 * barrière, une exception non capturée démonte tout l'arbre React → page vide.
 *
 * `key` est réinitialisée à chaque navigation (voir le router) pour que passer
 * à une autre page après une erreur reparte d'un état sain.
 */
export default class RouteErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  render() {
    if (!this.state.error) return this.props.children
    return (
      <div
        role="alert"
        className="ui-root page flex flex-col items-center justify-center gap-3 py-16 text-center"
      >
        <span className="flex size-12 items-center justify-center rounded-full bg-destructive/12 text-destructive">
          <AlertTriangle className="size-6" aria-hidden="true" />
        </span>
        <h2 className="font-display text-lg font-semibold">
          Une erreur est survenue
        </h2>
        <p className="max-w-sm text-sm text-muted-foreground">
          Cette page n’a pas pu s’afficher. Rechargez pour réessayer ; si le
          problème persiste, contactez votre administrateur.
        </p>
        <div className="mt-1">
          <Button onClick={() => window.location.reload()}>
            Recharger la page
          </Button>
        </div>
      </div>
    )
  }
}
