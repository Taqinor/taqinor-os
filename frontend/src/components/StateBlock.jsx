// N-Transversal (L11) — patron partagé états « chargement / vide / erreur ».
//
// Beaucoup de pages avalaient leurs échecs (`.catch(() => {})`) et rendaient une
// liste vide en silence : impossible de distinguer « rien à afficher » d'« échec
// de chargement ». StateBlock unifie les trois états avec des libellés FR et un
// bouton « Réessayer » optionnel.
//
// Usage : afficher le bloc tant que la donnée n'est pas prête, sinon le contenu.
//   <StateBlock loading={loading} error={error} empty={!items.length}
//               onRetry={reload} />
//
// Déploiement : appliqué ici dans les surfaces coquille/recherche/notifications.
// Le déploiement plus large (Dashboard, Rapports, BalanceAgeePage…) est DIFFÉRÉ
// — chacune appartient à une autre lane et sera migrée séparément.
import { AlertTriangle, Inbox, Loader2 } from 'lucide-react'
import { cn } from '../lib/cn'

const LOADING_FR = 'Chargement…'
const EMPTY_FR = 'Aucune donnée à afficher.'
const ERROR_FR = 'Échec du chargement.'

export function StateBlock({
  loading = false,
  error = null,
  empty = false,
  loadingText = LOADING_FR,
  emptyText = EMPTY_FR,
  errorText = ERROR_FR,
  onRetry,
  className,
}) {
  // Priorité : erreur > chargement > vide. Rien à afficher sinon (null).
  const state = error ? 'error' : loading ? 'loading' : empty ? 'empty' : null
  if (!state) return null

  const Icon = state === 'error' ? AlertTriangle
    : state === 'loading' ? Loader2 : Inbox
  const text = state === 'error'
    ? (typeof error === 'string' ? error : errorText)
    : state === 'loading' ? loadingText : emptyText

  return (
    <div
      role={state === 'error' ? 'alert' : 'status'}
      aria-live="polite"
      className={cn(
        'flex flex-col items-center justify-center gap-2 px-4 py-8 text-center text-sm',
        state === 'error' ? 'text-destructive' : 'text-muted-foreground',
        className,
      )}
    >
      <Icon
        className={cn('size-5', state === 'loading' && 'animate-spin')}
        aria-hidden="true"
      />
      <p>{text}</p>
      {state === 'error' && typeof onRetry === 'function' && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-1 rounded-md border border-border px-3 py-1 text-xs font-medium text-foreground hover:bg-accent"
        >
          Réessayer
        </button>
      )}
    </div>
  )
}

export default StateBlock
