// FORFAITS AU PANNEAU — l'écran pose le prix que le serveur écrira.
//
// Un produit du catalogue peut porter un BARÈME au panneau
// (`Produit.prix_fixe_ht` + `Produit.prix_par_panneau_ht`, DH HT) : le serveur
// re-tarife ses lignes à CHAQUE écriture sur le nombre réel de panneaux
// (`apps/ventes/domain/lignes.py::retarifer_forfaits_par_panneau`). Le
// générateur, lui, posait toujours `prix_vente` (`solar.js::ligneProduitCatalogue`) :
// un devis agricole de 10 panneaux s'affichait 31 900 MAD TTC et s'enregistrait
// 37 300 (installation 0 → 4 500 HT). Ce module applique le MÊME barème aux
// lignes d'écran ; il ne calcule rien de physique (D-AGR-1) : le barème vient
// du catalogue, le compte vient des lignes.
//
// Module PUR (aucun React) : exécuté par `node --test` / vitest.
import { ttcExactFromHt, tauxTvaOf } from '../solar.js'
import { isPanel, classifyProduct } from '../calc/classification.js'
import { lignesEnvoyees } from './lignesEcran.js'

const TYPES_STRUCTURE = new Set(['section', 'note'])
const MICRO = 1000000n
const CENTIME_EN_MICRO = 10000n

const absent = (v) => v === null || v === undefined || v === ''

// Montant décimal (chaîne DRF « 52.0833 » ou nombre) → BigInt en millionièmes,
// sans flottant : l'arrondi au centime doit tomber comme `Decimal` côté serveur.
function enMillioniemes(v) {
  if (absent(v)) return 0n
  const m = /^\s*([-+]?)(\d*)(?:[.,](\d*))?\s*$/.exec(String(v))
  if (!m || (m[2] === '' && !m[3])) {
    const n = Number(v)
    return Number.isFinite(n) ? enMillioniemes(n.toFixed(6)) : 0n
  }
  const abs = BigInt(m[2] || '0') * MICRO + BigInt(((m[3] || '') + '000000').slice(0, 6))
  return m[1] === '-' ? -abs : abs
}

// ROUND_HALF_UP au centime (moitié en s'éloignant de zéro), rendu « 1234.50 ».
function auCentime(micro) {
  const neg = micro < 0n
  const abs = neg ? -micro : micro
  let c = abs / CENTIME_EN_MICRO
  if ((abs % CENTIME_EN_MICRO) * 2n >= CENTIME_EN_MICRO) c += 1n
  const txt = `${c / 100n}.${String(c % 100n).padStart(2, '0')}`
  return neg && c > 0n ? `-${txt}` : txt
}

/**
 * Miroir de `apps/ventes/domain/catalogue.py::porte_bareme_par_panneau` :
 * vrai dès qu'une des deux parts du barème est renseignée.
 */
export function porteBaremeParPanneau(produit) {
  if (!produit) return false
  // Coffret C&I : barème par onduleur + par panneau, chiffré par le moteur C&I.
  if (['coffret_dc', 'coffret_ac'].includes(produit.role_ci)) return false
  return !(absent(produit.prix_fixe_ht) && absent(produit.prix_par_panneau_ht))
}

/**
 * Miroir de `apps/ventes/domain/catalogue.py::prix_forfait_ht` :
 * `prix_fixe_ht + prix_par_panneau_ht × nb_panneaux`, arrondi au centime
 * (ROUND_HALF_UP). `null` quand le produit ne porte aucun barème — l'appelant
 * garde alors `prix_vente`, byte-identique. Rendu en chaîne HT « 4500.00 ».
 */
export function prixForfaitHt(produit, nbPanneaux) {
  if (!porteBaremeParPanneau(produit)) return null
  const n = Math.trunc(Number(nbPanneaux) || 0)
  let total = enMillioniemes(produit.prix_fixe_ht)
  if (n > 0) total += enMillioniemes(produit.prix_par_panneau_ht) * BigInt(n)
  return auCentime(total)
}

const produitDe = (l, produits) => (l?.produit
  ? produits.find((p) => String(p.id) === String(l.produit)) || null : null)

// Les lignes que le serveur RECEVRA (même filtre que `lignesEcranVersPayload`).
const ligneEnvoyee = (l) => l && !TYPES_STRUCTURE.has(l.typeLigne)
  && lignesEnvoyees([l]).length > 0

/**
 * Le compte de panneaux de chaque vue, miroir de
 * `apps/ventes/domain/lignes.py::_comptes_panneaux` : une ligne est un panneau
 * sur sa désignation OU le nom de son produit (`_classe_ligne` + `isPanel`,
 * le classifieur de l'écran aligné sur `solar_classification.is_panel`) ;
 * quantité tronquée à l'entier. Aucune ligne panneau variantée ⇒ les trois
 * clés valent le total ; sinon « sans »/« avec » = communes + les leurs, et la
 * clé commune ('') vaut `null` quand les deux divergent.
 */
export function comptesPanneauxEcran(lines, produits = []) {
  const cat = Array.isArray(produits) ? produits : []
  const panneaux = (lines || []).filter((l) => ligneEnvoyee(l)
    && (isPanel(l.designation || '') || isPanel(produitDe(l, cat)?.nom || '')))
  const somme = (ls) => ls.reduce((s, l) => s + Math.trunc(parseFloat(l.quantite) || 0), 0)
  if (!panneaux.some((l) => l.variante)) {
    const total = somme(panneaux)
    return { '': total, sans: total, avec: total }
  }
  const sans = somme(panneaux.filter((l) => ['', 'sans'].includes(l.variante || '')))
  const avec = somme(panneaux.filter((l) => ['', 'avec'].includes(l.variante || '')))
  return { '': sans === avec ? sans : null, sans, avec }
}

/**
 * Les lignes d'écran, chaque ligne d'un produit À BARÈME tarifée au barème du
 * compte de panneaux COURANT de son option — comme
 * `apps/ventes/domain/lignes.py::retarifer_forfaits_par_panneau` à
 * l'enregistrement. Mêmes abstentions que le serveur : prix tapé
 * (`prixManuel`, D12), forfait commun à deux options divergentes, produit
 * sans barème (prix inchangé, byte-identique).
 * Un prix RELU du serveur (`prixRelu`, AGNR16) n'est re-tarifé que si le
 * compte de panneaux a CHANGÉ depuis sa relecture (marqueur
 * `forfaitPanneaux`, posé au premier passage) : un devis rouvert garde son
 * prix tant qu'aucun geste ne change le compte.
 * Rend le MÊME tableau quand rien ne change (aucun re-rendu en boucle).
 */
export function retarifierForfaitsEcran(lines, produits) {
  if (!Array.isArray(lines) || !Array.isArray(produits) || !produits.length) return lines
  const comptes = comptesPanneauxEcran(lines, produits)
  let change = false
  const sortie = lines.map((l) => {
    if (!l || TYPES_STRUCTURE.has(l.typeLigne) || !l.produit || l.prixManuel) return l
    const p = produitDe(l, produits)
    if (!porteBaremeParPanneau(p)) return l
    const variante = l.variante || ''
    const n = Object.hasOwn(comptes, variante) ? comptes[variante] : comptes['']
    if (n === null || n === undefined) return l
    const marque = l.forfaitPanneaux
    if (l.prixRelu && !marque) {
      // Premier passage d'un prix relu : on note le compte, sans toucher au prix.
      change = true
      return { ...l, forfaitPanneaux: { produit: String(l.produit), n } }
    }
    if (l.prixRelu && marque.produit === String(l.produit) && marque.n === n) return l
    const ht = prixForfaitHt(p, n)
    const ttc = ttcExactFromHt(ht, l.taux_tva ?? tauxTvaOf(p))
    const dejaAuBareme = l.prixHtOrigine === ht
      && Math.abs((parseFloat(l.prix_unit_ttc) || 0) - ttc) < 0.005
    if (dejaAuBareme && !l.prixRelu) return l
    change = true
    return {
      ...l,
      prix_unit_ttc: typeof l.prix_unit_ttc === 'string' ? String(ttc) : ttc,
      prixHtOrigine: ht,
      forfaitPanneaux: { produit: String(l.produit), n },
    }
  })
  return change ? sortie : lines
}

/* T4-X4-001 — LES QUANTITÉS QUI DÉPENDENT DU NOMBRE DE PANNEAUX. Le composeur serveur pose N structures et 2 × N socles
   pour N panneaux (`composition.py::quantites_fixation`). Changer la quantité de la ligne panneau laissait ces deux lignes
   à l'ancien compte (6 structures, 12 socles pour 8 panneaux) sans le dire. Règle : une ligne structure / socle SUIT le
   compte de panneaux de son option tant que sa quantité est celle que la règle donnait au dernier compte connu
   (marqueur d'écran `suitPanneaux`, posé quand la quantité vaut la règle) et qu'elle n'est pas figée à la main. Une
   quantité FIGÉE (`quantiteManuelle`) ou écartée de la règle ne bouge jamais : elle est MARQUÉE (`qteAttenduePanneaux`,
   lu par la ligne : « ne suit pas les panneaux — N attendu ») quand elle diffère de la règle. Fonction pure ; le même
   tableau revient quand rien ne change. */
const FACTEUR_FIXATION = { structure: 1, socle: 2 }
const roleFixation = (l, produits) => {
  const role = classifyProduct(produitDe(l, produits)?.nom || l.designation || '')
  return role === 'socle' ? 'socle' : (role === 'structure' || String(role || '').startsWith('structure') ? 'structure' : null)
}

export function suivreQuantitesPanneauxEcran(lines, produits) {
  if (!Array.isArray(lines)) return lines
  const comptes = comptesPanneauxEcran(lines, produits || [])
  let change = false
  const sortie = lines.map((l) => {
    if (!l || TYPES_STRUCTURE.has(l.typeLigne) || !l.produit || l.optionnelle || !ligneEnvoyee(l)) return l
    const role = roleFixation(l, produits || [])
    if (!role) return l
    const variante = l.variante || ''
    const n = Object.hasOwn(comptes, variante) ? comptes[variante] : comptes['']
    if (n === null || n === undefined || !(n > 0)) return l
    const attendu = n * FACTEUR_FIXATION[role]
    const q = parseFloat(l.quantite) || 0
    if (l.quantiteManuelle) {
      const ecart = q !== attendu ? attendu : undefined
      if (l.qteAttenduePanneaux === ecart) return l
      change = true
      const { qteAttenduePanneaux: _x, ...reste } = l
      return ecart === undefined ? reste : { ...reste, qteAttenduePanneaux: ecart }
    }
    if (l.qteAttenduePanneaux !== undefined) { // libérée : l'alerte de la figée tombe
      const { qteAttenduePanneaux: _x, ...libre } = l
      change = true
      return libre
    }
    const marque = l.suitPanneaux
    if (marque === undefined) {
      if (q !== attendu) return l // jamais suivie : écart d'origine, rien n'est deviné
      change = true
      return { ...l, suitPanneaux: n }
    }
    if (marque === n) return l
    if (q === attendu) { change = true; return { ...l, suitPanneaux: n } } // recomposée : déjà au compte
    if (q !== marque * FACTEUR_FIXATION[role]) return l // quantité retouchée autrement : on ne la réécrit pas
    change = true
    return { ...l, quantite: typeof l.quantite === 'string' ? String(attendu) : attendu, suitPanneaux: n }
  })
  return change ? sortie : lines
}

/* R5A-N2 — « Auto-remplir » recompose l'option AVEC batterie à la taille SANS quand le nombre de panneaux a été saisi à la
   main (règle voulue : un compte saisi vaut pour les deux options, `resolveKwcAvec`). Un devis de 8 panneaux « avec batterie »
   retombait à 6 sans que rien ne le dise au moment où ça arrive. Rend `{ avant, apres }` quand l'option avec perd des panneaux,
   sinon `null` ; l'écran le dit alors, en nommant les deux comptes. */
export function reductionOptionAvec(avant, apres, produits = []) {
  const a = comptesPanneauxEcran(avant, produits).avec
  const b = comptesPanneauxEcran(apres, produits).avec
  return a > 0 && b > 0 && b < a ? { avant: a, apres: b } : null
}
