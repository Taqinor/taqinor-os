/* Bandeaux de message serveur PARTAGÉS (erreur role=alert, information) des
   pages et dialogues : un seul endroit, jamais recopiés écran par écran. */

/** Bandeau d'erreur serveur (role=alert), rendu seulement si `error` est non vide. */
export function AlerteErreur({ error }) {
  if (!error) return null
  return (
    <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
      {error}
    </div>
  )
}

/** Ligne d'erreur serveur en texte simple (sans cadre), rendue seulement si `error` est non vide. */
export function ErreurTexte({ error }) {
  if (!error) return null
  return <p className="text-sm text-destructive">{error}</p>
}

/** Bandeau d'information (succès), rendu seulement si `info` est non vide. */
export function InfoSucces({ info }) {
  if (!info) return null
  return (
    <div className="rounded-lg border border-success/30 bg-success/10 p-3 text-sm text-success">
      {info}
    </div>
  )
}
