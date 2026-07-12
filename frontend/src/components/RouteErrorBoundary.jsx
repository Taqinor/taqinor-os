import { Component } from 'react'
import { AlertTriangle } from 'lucide-react'
// VX185/wave-3 perf: import direct (jamais le barrel `../ui`) — importé
// statiquement par router/index.jsx (-> main.jsx), donc tout ce que le
// barrel touche (dont datatable -> recharts/pdfjs-dist) finirait en
// `<link rel="modulepreload">` sur chaque page, `/login` inclus.
import { Button } from '../ui/Button'
import { captureException } from '../lib/monitoring'

// VX206 — identifiant support « horodatage court » quand le monitoring
// distant est no-op (pas de DSN) : toujours quelque chose de transmissible,
// jamais un écran de récupération muet.
function shortTimestamp() {
  return new Date().toTimeString().slice(0, 8)
}

/* L880 — Error-boundary de route GLOBALE.
 *
 * Capture toute erreur de rendu (ou une erreur jetée pendant le rendu, ex. un
 * fetch synchrone qui échoue) survenue dans une page authentifiée et affiche un
 * écran FR de récupération AU LIEU d'une application blanche. Sans cette
 * barrière, une exception non capturée démonte tout l'arbre React → page vide.
 *
 * `key` est réinitialisée à chaque navigation (voir le router) pour que passer
 * à une autre page après une erreur reparte d'un état sain.
 *
 * VX206 — trace en console + capture vers le même chemin
 * captureException-ou-no-op que `ui/ErrorBoundary.jsx` (VX72) et affiche un
 * identifiant support sur l'écran de récupération.
 */
export default class RouteErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null, eventId: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    console.error('[RouteErrorBoundary]', error, info?.componentStack)
    captureException(error, { componentStack: info?.componentStack })
      .then((eventId) => this.setState({ eventId: eventId || shortTimestamp() }))
      .catch(() => this.setState({ eventId: shortTimestamp() }))
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
        {this.state.eventId && (
          <p className="text-xs text-muted-foreground">
            Code erreur à transmettre : <span className="font-mono">{this.state.eventId}</span>
          </p>
        )}
        <div className="mt-1">
          <Button onClick={() => window.location.reload()}>
            Recharger la page
          </Button>
        </div>
      </div>
    )
  }
}
