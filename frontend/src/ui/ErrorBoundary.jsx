import { Component } from 'react'
import { AlertTriangle } from 'lucide-react'
import { Button } from './Button'

/* G30 — ErrorBoundary : capture une erreur de rendu et affiche un écran FR clair
   au lieu d'une page blanche. `fallback` personnalisable ; sinon écran par défaut. */
export class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
    this.reset = this.reset.bind(this)
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    if (typeof this.props.onError === 'function') this.props.onError(error, info)
  }

  reset() {
    this.setState({ error: null })
  }

  render() {
    if (!this.state.error) return this.props.children
    if (this.props.fallback) {
      return typeof this.props.fallback === 'function'
        ? this.props.fallback({ error: this.state.error, reset: this.reset })
        : this.props.fallback
    }
    return (
      <div
        role="alert"
        className="flex flex-col items-center justify-center gap-3 rounded-xl border border-border bg-card px-6 py-12 text-center text-card-foreground"
      >
        <span className="flex size-11 items-center justify-center rounded-full bg-destructive/12 text-destructive">
          <AlertTriangle className="size-5" aria-hidden="true" />
        </span>
        <p className="font-display text-base font-semibold">Une erreur est survenue</p>
        <p className="max-w-sm text-sm text-muted-foreground">
          Cette section n'a pas pu s'afficher. Vous pouvez réessayer ; si le problème persiste,
          rechargez la page.
        </p>
        <div className="mt-1 flex gap-2">
          <Button variant="outline" size="sm" onClick={this.reset}>
            Réessayer
          </Button>
          <Button size="sm" onClick={() => window.location.reload()}>
            Recharger
          </Button>
        </div>
      </div>
    )
  }
}

export default ErrorBoundary
