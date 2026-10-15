import { Spinner } from './Spinner'

/* Enchaînement chargement → indisponible → vide → contenu PARTAGÉ des widgets de
   liste (comptes dormants, portefeuille…). `estVide` + `messageVide` pilotent
   l'état vide ; `children` n'est rendu que sinon. */
export function EtatListe({ loading, error, estVide, messageVide, children }) {
  if (loading) return <Spinner />
  if (error) return <p className="text-sm text-muted-foreground">Indisponible pour le moment.</p>
  if (estVide) return <p className="text-sm text-muted-foreground">{messageVide}</p>
  return children
}
