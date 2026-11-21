/* ACAL458 — lecture PURE d'un fichier texte d'horizon.
   Formats : (a) deux colonnes « azimut ; hauteur » (séparateur ; , tabulation ou
   espace, décimale , ou ., en-tête facultatif, # = commentaire) ; (b) une colonne
   = format « userhorizon » de PVGIS : N hauteurs, directions de 360/N degrés
   depuis le Nord, sens horaire (aide PVGIS, « horizon file » :
   https://joint-research-centre.ec.europa.eu/pvgis-photovoltaic-geographical-information-system_en).
   Le .HOR de PVsyst (propriétaire) n'est PAS lu. Sortie : azimut de face (0 = Nord, horaire). */
export const CONVENTION_NORD = 'nord'
export const CONVENTION_SUD = 'sud'

const num = (s) => (/^[+-]?(\d+([.,]\d*)?|[.,]\d+)$/.test(s) ? Number(s.replace(',', '.')) : null)

function champs(ligne) {
  if (/[;\t]/.test(ligne)) return ligne.split(/[;\t]+/).map((s) => s.trim())
  if (/\s/.test(ligne)) return ligne.trim().split(/\s+/)
  return ligne.includes(',') ? ligne.split(',').map((s) => s.trim()) : [ligne]
}

function lignesUtiles(texte) {
  const lignes = String(texte ?? '').split(/\r?\n/)
    .map((brut, i) => ({ n: i + 1, t: brut.trim() }))
    .filter((l) => l.t && !l.t.startsWith('#'))
  if (lignes.length && champs(lignes[0].t).some((c) => num(c) === null)) lignes.shift() // en-tête
  return lignes
}

/** Nombre de colonnes de la première ligne de données (0 si le fichier est vide). */
export function nombreDeColonnes(texte) {
  const l = lignesUtiles(texte)
  return l.length ? champs(l[0].t).length : 0
}

/** @returns {{points:{azimuthDeg:number,heightDeg:number}[],format:string}|{erreur:string}} */
export function lireFichierHorizon(texte, convention) {
  const lignes = lignesUtiles(texte)
  if (!lignes.length) return { erreur: 'fichier vide, aucune ligne lisible.' }
  const colonnes = champs(lignes[0].t).length
  if (colonnes !== 1 && colonnes !== 2) return { erreur: `ligne ${lignes[0].n} : une ou deux colonnes attendues.` }
  if (colonnes === 2 && convention !== CONVENTION_NORD && convention !== CONVENTION_SUD) {
    return { erreur: 'choisissez la convention d’azimut du fichier.' }
  }
  const points = []
  for (let i = 0; i < lignes.length; i += 1) {
    const { n, t } = lignes[i]
    const c = champs(t).map(num)
    if (c.length !== colonnes || c.some((v) => v === null)) return { erreur: `ligne ${n} illisible : « ${t} ».` }
    const h = colonnes === 1 ? c[0] : c[1]
    if (h < -90 || h > 90) return { erreur: `ligne ${n} : hauteur hors de [−90, 90].` }
    let az
    if (colonnes === 1) az = (i * 360) / lignes.length
    else if (convention === CONVENTION_NORD) {
      if (c[0] < 0 || c[0] > 360) return { erreur: `ligne ${n} : azimut hors de [0, 360].` }
      az = c[0] % 360
    } else {
      if (c[0] < -180 || c[0] > 180) return { erreur: `ligne ${n} : azimut hors de [−180, 180].` }
      az = (c[0] + 180) % 360
    }
    points.push({ azimuthDeg: az, heightDeg: h })
  }
  return { points, format: colonnes === 1 ? 'une colonne, userhorizon PVGIS' : 'deux colonnes' }
}
