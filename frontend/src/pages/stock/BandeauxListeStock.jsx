import { Spinner } from '../../ui'

/* Éléments d'écran PARTAGÉS des listes / formulaires Stock : bandeau d'erreur
   serveur, ligne « Chargement… » et enchaînement erreur → chargement → vide →
   contenu. Un seul endroit — jamais recopiés page par page. */

/** Bandeau d'erreur serveur (role=alert) ; `enForm` : pleine largeur de grille. */
export function AlerteErreurStock({ error, enForm = false }) {
  if (!error) return null
  return (
    <div role="alert" className={`${enForm ? 'sm:col-span-2 ' : ''}rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive`}>
      {error}
    </div>
  )
}

/** Ligne « Chargement… » d'une liste Stock. */
export function ChargementStock() {
  return (
    <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground"><Spinner /> Chargement…</div>
  )
}

/** Liste Stock : bandeau d'erreur, puis chargement / état vide / contenu
 *  (`children` est une fonction : rendue seulement quand `items` est chargé). */
export function ListeStock({ error, items, vide, children }) {
  return (
    <>
      <AlerteErreurStock error={error} />
      {items === null ? (
        <ChargementStock />
      ) : items.length === 0 ? (
        <p className="text-sm text-muted-foreground">{vide}</p>
      ) : (
        children()
      )}
    </>
  )
}
