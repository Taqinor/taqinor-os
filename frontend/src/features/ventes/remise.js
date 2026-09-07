// QJRREM (fondateur, 07/09/2026) — « la remise de 5 % est gardée partout et
// s'applique aussi à chaque poste de la liste des composants, de l'installation,
// de tout ».
//
// CE MODULE EST LE MIROIR EXACT du noyau Python
// `apps/ventes/domain/argent.py::repartir_remise_par_ligne` : même population
// de lignes (ligne PRODUIT non optionnelle), même part exacte
// (`montant × ht_net / ht_brut`), même arrondi MOITIÉ-VERS-LE-HAUT au centime,
// même attribution des centimes résiduels par la méthode du PLUS FORT RESTE
// (ex æquo départagés par l'ORDRE DES LIGNES). Les deux implémentations sont
// épinglées sur LA MÊME table de cas :
//   backend : apps/ventes/tests/test_remise_par_ligne.py (FIXTURES)
//   ici     : remise.test.mjs (FIXTURES)
// Un écran et un PDF du même devis ne peuvent donc pas se contredire d'un
// centime.
//
// POURQUOI EN ENTIERS (BigInt), ET PAS EN FLOTTANTS. `Decimal` côté Python
// arrondit une valeur DÉCIMALE exacte ; un flottant JS arrondi par `toFixed`
// arrondit la valeur BINAIRE (1,005 → « 1,00 » en JS, 1,01 côté Python). Toute
// l'arithmétique se fait donc sur des entiers exacts, et la comparaison
// « moitié » se fait sur des ENTIERS (`2 × reste >= dénominateur`) — jamais sur
// un flottant, jamais sur un epsilon. Les montants de ligne sont portés au
// MILLIARDIÈME de dirham (9 décimales) : `quantité × prix × (1 − remise/100)`
// ne dépasse jamais cette précision avec des champs à 2-3 décimales, et le
// noyau Python ne quantifie ce produit qu'AU MOMENT de la répartition — pas
// avant (cf. `LigneDevis.total_ht`, non arrondi).
//
// Fonctions PURES : aucun React, aucun DOM, exécutables sous `node --test`.

const NANO = 1000000000n          // 1 dirham = 1e9 « nano »
const CENTIME_EN_NANO = 10000000n // 1 centime = 1e7 « nano »

// Le nombre tel que JS l'ÉCRIT (repr décimale la plus courte — la même que
// `str(float)` côté Python), découpé en partie entière / partie décimale.
function partiesDecimales(valeur) {
  let s = String(valeur ?? 0)
  if (s.includes('e') || s.includes('E')) s = Number(valeur).toFixed(20)
  const negatif = s.startsWith('-')
  if (negatif || s.startsWith('+')) s = s.slice(1)
  const [entier, decimales = ''] = s.split('.')
  return { negatif, entier: entier || '0', decimales }
}

// Un montant en dirhams → son entier de « nano », moitié vers le haut.
function nanos(valeur) {
  if (valeur === null || valeur === undefined || valeur === '') return 0n
  const nombre = typeof valeur === 'number' ? valeur : parseFloat(valeur)
  if (!Number.isFinite(nombre)) return 0n
  const { negatif, entier, decimales } = partiesDecimales(nombre)
  const neufPremieres = (decimales + '000000000').slice(0, 9)
  const reste = decimales.slice(9)
  let n = BigInt(entier) * NANO + BigInt(neufPremieres)
  // ROUND_HALF_UP s'applique à la VALEUR ABSOLUE (« moitié loin de zéro »),
  // exactement comme `Decimal.quantize(rounding=ROUND_HALF_UP)`.
  if (reste && Number(`0.${reste}`) >= 0.5) n += 1n
  return negatif ? -n : n
}

// `num / den` arrondi MOITIÉ-VERS-LE-HAUT, en entiers (den > 0). Rend aussi le
// NUMÉRATEUR du reste : tous les restes d'une même répartition partagent le
// même dénominateur, donc les ordonner par ce numérateur est EXACTEMENT
// l'ordre des restes fractionnaires — sans jamais passer par un flottant.
function diviserMoitieHaut(num, den) {
  const negatif = num < 0n
  const absolu = negatif ? -num : num
  const quotient = absolu / den
  const reste = absolu - quotient * den
  const arrondiAbsolu = 2n * reste >= den ? quotient + 1n : quotient
  const valeur = negatif ? -arrondiAbsolu : arrondiAbsolu
  return { valeur, resteNum: num - valeur * den }
}

/**
 * Un montant en dirhams arrondi au centime, MOITIÉ VERS LE HAUT — miroir de
 * `core.money.quantize_mad`. Rend un nombre (jamais une chaîne).
 */
export function arrondiCentime(valeur) {
  return Number(diviserMoitieHaut(nanos(valeur), CENTIME_EN_NANO).valeur) / 100
}

/**
 * Une ligne entre-t-elle dans les totaux ? Miroir de
 * `apps/ventes/selectors.py::ligne_compte_dans_totaux` : ligne PRODUIT non
 * optionnelle. Une ligne de section/note ou un add-on non activé est exclu —
 * comme il l'est des totaux.
 */
export function ligneCompteDansTotaux(ligne) {
  if (!ligne) return false
  if (ligne.optionnelle) return false
  const type = ligne.typeLigne ?? ligne.type_ligne ?? 'produit'
  return type === 'produit'
}

/**
 * Le montant HT d'une ligne, remise DE LIGNE incluse — la même formule que
 * `lineNetHT` des deux éditeurs (`quantité × prix unitaire × (1 − remise/100)`,
 * exactement `LigneDevis.total_ht`). Une ligne qui porte déjà son total
 * (`totalHt`) le garde.
 */
export function montantHtLigne(ligne) {
  if (ligne?.totalHt !== undefined && ligne?.totalHt !== null) {
    return parseFloat(ligne.totalHt) || 0
  }
  const quantite = parseFloat(ligne?.quantite) || 0
  const prix = parseFloat(ligne?.prix_unitaire ?? ligne?.prixUnitaire) || 0
  const remiseLigne = parseFloat(ligne?.remise) || 0
  return quantite * prix * (1 - remiseLigne / 100)
}

/**
 * Le montant APRÈS remise globale de chaque ligne — somme EXACTE.
 *
 * @param {Array} lignes lignes dans leur ordre d'affichage.
 * @param {number|string} remisePct la remise GLOBALE du devis, en pourcent.
 * @returns {Array<number|null>} liste ALIGNÉE sur `lignes` : le montant remisé
 *   (nombre en dirhams, au centime) pour une ligne comptée, `null` sinon.
 *
 * GARANTIE (invariant #10) : la somme des montants rendus vaut EXACTEMENT le
 * Total HT net du devis, `arrondi(Σ montants − remise)`, au centime.
 */
export function repartirRemiseParLigne(lignes, remisePct) {
  const liste = Array.from(lignes || [])
  const comptees = []
  liste.forEach((ligne, i) => {
    if (ligneCompteDansTotaux(ligne)) comptees.push(i)
  })
  if (!comptees.length) return liste.map(() => null)

  const montants = new Map()
  let htBrutNano = 0n
  comptees.forEach((i) => {
    const n = nanos(montantHtLigne(liste[i]))
    montants.set(i, n)
    htBrutNano += n
  })

  // `remise = arrondi(ht_brut × pct / 100)`, au CENTIME — la seule chaîne, la
  // même qu'au backend : le pourcentage n'est jamais ré-appliqué ligne à ligne.
  const pctNano = nanos(parseFloat(remisePct) || 0)
  const remiseC = pctNano === 0n
    ? 0n
    : diviserMoitieHaut(htBrutNano * pctNano, NANO * NANO).valeur
  const htNetC = diviserMoitieHaut(
    htBrutNano - remiseC * CENTIME_EN_NANO, CENTIME_EN_NANO).valeur

  const parts = new Map()
  const restes = new Map()
  if (htBrutNano === 0n) {
    // Rien à répartir proportionnellement : chaque ligne garde son montant.
    comptees.forEach((i) => {
      parts.set(i, diviserMoitieHaut(montants.get(i), CENTIME_EN_NANO).valeur)
      restes.set(i, 0n)
    })
  } else {
    // `diviserMoitieHaut` attend un dénominateur POSITIF : un document dont la
    // somme des lignes est négative (que des avoirs) garde le même partage en
    // renversant le signe des deux termes.
    const signe = htBrutNano < 0n ? -1n : 1n
    comptees.forEach((i) => {
      const { valeur, resteNum } = diviserMoitieHaut(
        montants.get(i) * htNetC * signe, htBrutNano * signe)
      parts.set(i, valeur)
      restes.set(i, resteNum)
    })
  }

  // ── Le plus fort reste ────────────────────────────────────────────────────
  let residu = htNetC
  comptees.forEach((i) => { residu -= parts.get(i) })
  if (residu !== 0n) {
    const croissant = residu < 0n
    const cibles = comptees.slice().sort((a, b) => {
      const ra = restes.get(a)
      const rb = restes.get(b)
      if (ra !== rb) {
        if (croissant) return ra < rb ? -1 : 1
        // Reste DÉCROISSANT ; à reste égal, la ligne la plus HAUTE d'abord.
        return ra > rb ? -1 : 1
      }
      return a - b
    })
    const pas = croissant ? -1n : 1n
    const combien = croissant ? -residu : residu
    for (let rang = 0n; rang < combien; rang += 1n) {
      const i = cibles[Number(rang % BigInt(cibles.length))]
      parts.set(i, parts.get(i) + pas)
    }
  }

  return liste.map((_, i) => (
    parts.has(i) ? Number(parts.get(i)) / 100 : null))
}

/**
 * Le PRIX UNITAIRE d'une ligne après remise globale, au centime — dérivé du
 * TOTAL réparti divisé par la quantité (jamais l'inverse : c'est le total qui
 * porte l'invariant). Miroir de `domain.argent.pu_remise`.
 */
export function puRemise(totalRemise, quantite) {
  let den = nanos(quantite)
  if (den === 0n) return 0
  let num = nanos(totalRemise) * 100n
  if (den < 0n) { num = -num; den = -den }
  return Number(diviserMoitieHaut(num, den).valeur) / 100
}
