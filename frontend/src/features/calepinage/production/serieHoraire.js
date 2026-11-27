/* ACAL446 — lecture du CSV horaire servi (sortie de TapisHoraire.jsx, réutilisée par ACAL447). */

/** Un nombre écrit à la française par le serveur (`1,25`), ou `null`. */
export function nombreFrancais(cellule) {
  const texte = String(cellule ?? '').trim()
  if (!texte) return null
  // `\s` en JS couvre DEJA l'espace insecable (U+00A0) et l'espace fin
  // insecable (U+202F) qu'un serveur peut emettre : aucun caractere
  // invisible n'entre dans ce fichier.
  const lu = Number(texte.replace(/\s/g, '').replace(',', '.'))
  return Number.isFinite(lu) ? lu : null
}

/** Le texte d'un fichier servi en blob (navigateur) ou déjà en chaîne. */
export async function texteDuFichier(donnees) {
  if (typeof donnees === 'string') return donnees
  if (donnees && typeof donnees.text === 'function') return donnees.text()
  return ''
}

/**
 * Les points de la série, lus dans le CSV que le serveur produit (CAL144).
 *
 * L'en-tête de provenance précède le tableau : on repère la ligne de titres
 * (`annee;mois;…`) et on ne lit que ce qui suit. Une cellule vide reste
 * `null` — le serveur l'a laissée vide parce que l'heure n'a pas de mesure.
 */
export function lireCsvHoraire(texte) {
  const brut = String(texte || '')
  // Le serveur prefixe le fichier du BOM qu'Excel attend (CAL144) : on le
  // retire par son POINT DE CODE, jamais par un caractere colle dans la
  // source.
  const sansBom = brut.charCodeAt(0) === 0xFEFF ? brut.slice(1) : brut
  const lignes = sansBom.split('\n').map((ligne) => ligne.replace('\r', ''))
  const depart = lignes.findIndex((ligne) => ligne.split(';')[0] === 'annee')
  if (depart < 0) return null
  // ACAL1664 — « Pas de temps » (ACAL1614) : une série agrégée au jour l'écrit AVANT les titres ; son texte servi, après
  // « — », est le motif de troncature (sinon la cellule entière). Absente : série horaire, aucun avertissement.
  const pas = lignes.slice(0, depart).find((ligne) => ligne.split(';')[0] === 'Pas de temps')
  const cellulePas = pas ? pas.slice(pas.indexOf(';') + 1).replace(/^"|"$/g, '').trim() : ''
  const auJour = /^jour(?![a-zà-ÿ])/i.test(cellulePas)
  const titres = lignes[depart].split(';').map((titre) => titre.trim())
  const points = []
  for (const ligne of lignes.slice(depart + 1)) {
    if (!ligne.trim()) continue
    const cellules = ligne.split(';')
    const point = {}
    titres.forEach((titre, rang) => { point[titre] = cellules[rang] })
    const annee = nombreFrancais(point.annee)
    if (annee === null) continue
    points.push({
      annee,
      mois: nombreFrancais(point.mois),
      jour: nombreFrancais(point.jour),
      heure: nombreFrancais(point.heure),
      p_ac_kw: nombreFrancais(point.production_kw),
      gi_w_m2: nombreFrancais(point.irradiance_plan_w_m2),
      // ACAL446 — colonnes optionnelles (`?colonnes=`, CALX313) : lues quand
      // le serveur les a servies, `null` sinon — jamais inventées.
      charge_kwh: nombreFrancais(point.charge_kwh),
      // ACAL738 — puissance continue à l'entrée de l'onduleur (ACAL752).
      p_dc_kw: nombreFrancais(point.p_dc_kw),
      batterie_soc_pct: nombreFrancais(point.batterie_soc_pct),
      reseau_import_kwh: nombreFrancais(point.reseau_import_kwh),
    })
  }
  return {
    points,
    colonnes: titres,
    tronquee: auJour ? true : null,
    motif_troncature: auJour ? (cellulePas.split(' — ').slice(1).join(' — ') || cellulePas) : '',
  }
}

/**
 * ACAL738 — la limite de l'onduleur (kW) lue sur l'étape `ecretage` de la
 * cascade (`entree.borne_kw`), ou `{ kw: null, motif }` : le motif d'omission
 * servi, jamais une valeur supposée.
 */
export function limiteOnduleur(cascade) {
  const etape = (cascade?.etapes ?? []).find((e) => e?.etape === 'ecretage')
  const kw = Number(etape?.entree?.borne_kw)
  if (etape?.entree?.borne_kw != null && Number.isFinite(kw)) return { kw, motif: '' }
  return { kw: null, motif: etape?.motif_omission || "la limite de l'onduleur n'est pas servie." }
}
