/* T4-X3-019 — formes des tables des réglages (voir ChampTableLisible.jsx). */

const SOURCE_REF = [
  { k: 'source', label: 'Source du texte' },
  { k: 'reference', label: 'Référence' },
]

//: Les familles de lignes connues (clé servie → mot français) — d'autres clés
//: déjà stockées s'affichent avec leur clé ; aucune n'est inventée en plus.
export const SPECS_TABLES = {
  lid_par_techno: {
    mode: 'dict',
    familles: { perc: 'Cellules PERC', topcon: 'Cellules TOPCon', hjt: 'Cellules HJT', inconnue: 'Autre technologie' },
    champs: [{ k: 'pct', label: 'Perte LID (%)', nombre: true }, ...SOURCE_REF],
  },
  thermique_par_pose: {
    mode: 'dict',
    familles: { pose_libre: 'Pose libre', dos_isole: 'Dos isolé' },
    champs: [
      { k: 'uc_w_m2k', label: 'Uc (W/m²K)', nombre: true },
      { k: 'uv_w_m3sk', label: 'Uv (W/m³sK)', nombre: true },
      ...SOURCE_REF,
    ],
  },
  indisponibilite_fenetres: {
    mode: 'liste',
    nom: 'Fenêtre d’arrêt',
    ajout: 'Ajouter une fenêtre',
    champs: [
      { k: 'debut', label: 'Début (AAAA-MM-JJ)' },
      { k: 'fin', label: 'Fin (AAAA-MM-JJ)' },
      { k: 'motif', label: 'Motif' },
    ],
  },
  regle_bom_structure: {
    mode: 'objet',
    champs: [
      { k: 'rails_par_module', label: 'Rails par module', nombre: true },
      { k: 'pinces_par_module', label: 'Pinces par module', nombre: true },
      { k: 'pinces_supplement', label: 'Pinces en supplément', nombre: true },
      { k: 'crochets_par_module', label: 'Crochets par module', nombre: true },
      { k: 'crochets_minimum', label: 'Crochets au minimum', nombre: true },
      { k: 'source', label: 'Source du texte' },
    ],
  },
  // {repère ou catégorie: identifiant produit (texte OU entier)} — services/parametres_cles.py::FORMES_TABLES.
  correspondances_nomenclature: {
    mode: 'paires',
    nom: 'Correspondance',
    ajout: 'Ajouter une correspondance',
    cle: { label: 'Repère ou catégorie' },
    valeur: { label: 'Identifiant du produit' },
  },
  consigne_dc_plan_cablage: {
    mode: 'objet',
    champs: [{ k: 'texte', label: 'Texte imprimé sur le plan de câblage' }],
  },
}

const estObjet = (v) => v !== null && typeof v === 'object' && !Array.isArray(v)

/** Lit le texte JSON de la ligne dans la forme de la clé ; `null` si la forme
 *  n'est pas celle attendue (la ligne retombe alors sur l'éditeur JSON). */
export function lireTable(cle, texte) {
  const spec = SPECS_TABLES[cle]
  if (!spec) return null
  const brut = (texte || '').trim()
  if (!brut) return spec.mode === 'liste' ? [] : {}
  let valeur
  try { valeur = JSON.parse(brut) } catch { return null }
  if (spec.mode === 'paires') {
    // Les clés « entières » seraient réordonnées par JS : la ligne reste alors sur l'éditeur JSON (rien ne bouge).
    const bonne = estObjet(valeur) && Object.entries(valeur).every(([k, v]) => !/^\d+$/.test(k)
      && (typeof v === 'string' || Number.isInteger(v)))
    return bonne ? valeur : null
  }
  const connus = new Set(spec.champs.map((c) => c.k))
  const ligneOk = (o) => estObjet(o) && Object.keys(o).every((k) => connus.has(k))
    && spec.champs.every((c) => o[c.k] === undefined || (c.nombre ? typeof o[c.k] === 'number' : typeof o[c.k] === 'string'))
  if (spec.mode === 'liste') return Array.isArray(valeur) && valeur.every(ligneOk) ? valeur : null
  if (spec.mode === 'objet') return ligneOk(valeur) ? valeur : null
  return estObjet(valeur) && Object.values(valeur).every(ligneOk) ? valeur : null
}

/** Réécrit la table EDITÉE en texte JSON ; une ligne vidée disparaît, une
 *  table vide donne un texte vide (= clé non saisie, comme avant). */
export function ecrireTable(spec, valeur) {
  if (spec.mode === 'paires') return Object.keys(valeur).length ? JSON.stringify(valeur) : ''
  const net = (o) => Object.fromEntries(Object.entries(o).filter(([, v]) => v !== undefined && v !== ''))
  if (spec.mode === 'liste') {
    return valeur.length ? JSON.stringify(valeur.map(net)) : ''
  }
  if (spec.mode === 'objet') {
    const o = net(valeur)
    return Object.keys(o).length ? JSON.stringify(o) : ''
  }
  const o = {}
  for (const [k, ligne] of Object.entries(valeur)) {
    const n = net(ligne)
    if (Object.keys(n).length) o[k] = n
  }
  return Object.keys(o).length ? JSON.stringify(o) : ''
}


/** Un identifiant produit tapé : entier strict (sans zéro de tête) → nombre, sinon texte, comme l'accepte le serveur. */
export const identifiantProduit = (texte) => (/^[1-9]\d*$/.test(texte) ? Number(texte) : texte)

/** Une ligne de correspondance laissée à moitié (repère ou identifiant vide) : la phrase qui le dit, sous le champ. */
export function erreurTable(cle, valeur) {
  if (SPECS_TABLES[cle]?.mode !== 'paires' || !estObjet(valeur)) return null
  const vide = Object.entries(valeur).some(([k, v]) => k.trim() === '' || (typeof v === 'string' && v.trim() === ''))
  return vide
    ? 'Une correspondance est à moitié remplie : indiquez son repère ET l’identifiant du produit, ou retirez la ligne.'
    : null
}
