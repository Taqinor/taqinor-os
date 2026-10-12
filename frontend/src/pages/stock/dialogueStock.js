/* Soumission commune des dialogues de formulaire Stock : verrouille le bouton,
   efface l'erreur, exécute `action`, notifie `onSaved`, ferme — ou affiche
   l'erreur serveur calculée par `erreur`. Un seul endroit, jamais recopié. */
export async function soumettreDialogue({
  action, onSaved, onClose, setError, setSaving, erreur,
}) {
  setSaving(true)
  setError(null)
  try {
    await action()
    onSaved?.()
    onClose()
  } catch (err) {
    setError(erreur(err))
  } finally { setSaving(false) }
}
