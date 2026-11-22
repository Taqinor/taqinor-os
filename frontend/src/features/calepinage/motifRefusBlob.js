// Le MOTIF d'un refus du serveur sur une réponse demandée en `blob` (DXF,
// classeur) : un 400 arrive lui aussi en Blob, son JSON (`{champ: motif}`) est
// relu pour afficher la phrase du serveur, jamais une phrase reformulée ici.
// Un corps illisible (panne réseau, HTML d'un proxy) rend `repli`, qui DIT
// qu'il est générique plutôt qu'un motif métier inventé.
import { erreurDeTelechargement } from './documents/telechargement'

export async function motifDuRefusBlob(erreur, repli) {
  // R3 — délai dépassé : la phrase de « Documents » (durée + quoi faire).
  if (erreur?.code === 'ECONNABORTED') {
    return (await erreurDeTelechargement(erreur, { delai: true }))[0].message
  }
  const donnees = erreur?.response?.data
  try {
    const texte = typeof donnees?.text === 'function' ? await donnees.text() : donnees
    const objet = typeof texte === 'string' ? JSON.parse(texte) : texte
    const premier = objet && typeof objet === 'object' ? Object.values(objet)[0] : null
    if (premier) return String(premier)
  } catch {
    return repli
  }
  return repli
}

export default motifDuRefusBlob
