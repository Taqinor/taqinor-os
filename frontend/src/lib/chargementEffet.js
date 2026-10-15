/* Cadre de chargement PARTAGÉ des effets d'écran (monitoring, reporting) :
   attend un tick (aucun setState synchrone dans l'effet), bascule `setLoading`
   autour de `executer(actif)` et n'écrit plus rien une fois l'effet nettoyé.
   `actif()` doit être relu après chaque `await` avant d'écrire un état ; une
   exception de `executer` appelle `surErreur()` (seulement si l'effet vit
   encore). Renvoie la fonction de nettoyage de l'effet. */
export function lancerChargement({ setLoading, executer, surErreur }) {
  let active = true
  const actif = () => active
  const load = async () => {
    await Promise.resolve()
    if (!active) return
    setLoading(true)
    try {
      await executer(actif)
    } catch {
      if (active) surErreur()
    } finally {
      if (active) setLoading(false)
    }
  }
  load()
  return () => { active = false }
}
