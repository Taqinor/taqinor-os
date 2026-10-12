import { toast } from '../../ui/confirm'

/* Gestes d'enregistrement PARTAGÉS des sections Paramètres (Statuts,
   Traductions, Documents) : un seul endroit, jamais recopiés section par section. */

/** Affiche « Enregistré ! » 2,5 s sur le bouton (setSaved du composant). */
export function marquerEnregistre(setSaved) {
  setSaved(true)
  setTimeout(() => setSaved(false), 2500)
}

/** Toast d'erreur serveur d'un enregistrement (detail > message générique). */
export function toastEnregistrementImpossible(e) {
  toast.error(e?.response?.data?.detail ?? 'Enregistrement impossible.')
}
