/* VX117 — fin du doublon fiscal au retry (devis/facture/paie/rôles).
   ----------------------------------------------------------------------------
   Patron partagé pour tout flux « parent + N opérations » (lignes de
   devis/facture, bulletins de paie, réassignations de rôle…) : jamais
   `Promise.all` (qui rejette au premier échec et laisse les opérations déjà
   réussies dans un état invisible), toujours `Promise.allSettled` + un
   rapport NOMINATIF `{succeeded, failed:[{item,error}], allOk}`.

   Le composant appelant est responsable de :
   (a) n'avancer l'état du PARENT (statut VALIDÉE, suppression effective,
       fermeture de modale/dialogue…) que si `allOk` ;
   (b) garder le parent déjà créé/modifié EXPOSÉ (jamais un second POST au
       retry — dès qu'un id serveur existe, la relance passe en ÉDITION) ;
   (c) ne relancer QUE les items en échec (`failed.map(f => f.item)`), jamais
       la liste complète (fin du re-traitement des lignes déjà persistées).

   Fonction PURE (aucun React) → testable sous `node --test`. */
export async function resilientMutation(items, fn) {
  const list = items ?? []
  const results = await Promise.allSettled(list.map((item, i) => fn(item, i)))
  const succeeded = []
  const failed = []
  results.forEach((r, i) => {
    if (r.status === 'fulfilled') succeeded.push({ item: list[i], value: r.value })
    else failed.push({ item: list[i], error: r.reason })
  })
  return { succeeded, failed, allOk: failed.length === 0 }
}

// Construit un libellé nominatif « Nom A, Nom B » à partir des échecs, pour
// un message d'erreur qui NOMME ce qui n'a pas pu être enregistré au lieu
// d'un JSON brut ou d'un « Erreur » générique.
export function describeFailures(failed, nameOf) {
  return failed.map((f) => nameOf(f.item)).join(', ')
}

export default resilientMutation
