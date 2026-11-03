// ENF19 — LA mécanique d'envoi d'un formulaire, UNE fois : plus de bloc
// « preventDefault → valider → occupé → try / finally » recopié d'un écran à
// l'autre (chaque copie dérivait seule).
//
// `valider()` rend `true` pour poursuivre, ou une promesse du verdict quand la
// validation interroge le serveur (anti-doublon). Un `true` synchrone n'attend
// aucune micro-tâche : l'état « occupé » se pose dans le même tour que le geste.
export function creerSoumission(valider, setOccupe, envoyer, surErreur) {
  return async (e) => {
    e.preventDefault()
    const verdict = valider()
    if (verdict !== true && !(await verdict)) return
    setOccupe(true)
    try {
      await envoyer()
    } catch (err) {
      surErreur(err)
    } finally {
      setOccupe(false)
    }
  }
}

// Création rapide : le nom est le seul champ requis ; toute erreur (validation
// ou envoi) s'affiche dans le même bandeau `setError`, effacé à chaque essai.
export function creerSoumissionNomRequis({ nom, setError, setBusy, envoyer, messageErreur }) {
  const valider = () => {
    setError(null)
    if (nom.trim()) return true
    setError('Le nom est requis.')
    return false
  }
  return creerSoumission(valider, setBusy, envoyer, (err) => setError(messageErreur(err)))
}
