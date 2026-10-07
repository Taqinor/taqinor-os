/* ASTK215-ASTK228 — lecture des erreurs serveur des écrans entrepôt / négoce.
   Règle d'écran : le message du serveur est affiché MOT POUR MOT (jamais
   réécrit, jamais de JSON brut). Module pur, partagé par les wrappers API. */

function aplatir(valeur) {
  if (valeur == null) return []
  if (typeof valeur === 'string') return [valeur]
  if (Array.isArray(valeur)) return valeur.flatMap(aplatir)
  if (typeof valeur === 'object') return Object.values(valeur).flatMap(aplatir)
  return [String(valeur)]
}

/** Message FR d'une erreur axios : `detail`, texte brut, ou erreurs de champs. */
export function messageServeur(err, repli = 'Une erreur est survenue.') {
  const data = err?.response?.data
  if (!data) return repli
  if (typeof data === 'string') return data
  if (data.detail) return aplatir(data.detail).join(' ')
  // Enveloppe de validation : `error.fields` répète déjà les messages de champs.
  const { error, ...champs } = data
  const textes = aplatir(Object.keys(champs).length ? champs : error?.fields ?? error)
  return textes.length ? textes.join(' ') : repli
}

/** Message serveur attaché à UN champ (`{champ: ['…']}`), sinon null. */
export function erreurChamp(err, champ) {
  const v = err?.response?.data?.[champ]
  if (v == null) return null
  return aplatir(v).join(' ')
}

/** Corps d'erreur d'un téléchargement binaire (Blob) → message lisible. */
export async function messageServeurBlob(err, repli = 'Une erreur est survenue.') {
  const data = err?.response?.data
  if (typeof Blob !== 'undefined' && data instanceof Blob) {
    try {
      const texte = await data.text()
      try {
        return messageServeur({ response: { data: JSON.parse(texte) } }, repli)
      } catch { return texte || repli }
    } catch { return repli }
  }
  return messageServeur(err, repli)
}

/** Télécharge un contenu texte (ex. un ASN JSON) comme fichier local. */
export function telechargerTexte(nom, contenu, type = 'application/json') {
  const url = URL.createObjectURL(new Blob([contenu], { type }))
  const a = document.createElement('a')
  a.href = url
  a.download = nom
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 60000)
}

/** Ouvre un Blob reçu (PDF…) dans un nouvel onglet. */
export function ouvrirBlob(blob, type = 'application/pdf') {
  const url = URL.createObjectURL(new Blob([blob], { type }))
  window.open(url, '_blank', 'noopener')
  setTimeout(() => URL.revokeObjectURL(url), 60000)
}
