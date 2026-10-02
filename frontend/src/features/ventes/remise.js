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

// ── QJR642 — LE noyau des totaux de l'écran ───────────────────────────────
// UNE chaîne « HT brut → remise globale → HT net (≥ 0) → TVA par taux → TTC »,
// partagée par le générateur (`solar.totauxCanoniquesTtc`) et la répartition
// de la remise par ligne (`repartirRemiseParLigne`). Même règle que
// `apps/ventes/selectors.py::_canonical_totaux` : arithmétique entière, arrondi
// moitié vers le haut, remise en NANOS de pourcent.

// ── ARRONDI-100 (fondateur, 02/10/2026) ───────────────────────────────────
// « Tous mes devis finissent par deux zéros, sans centimes : garde les prix
// des articles, baisse juste le total au palier de 100 DH inférieur. »
// MIROIR EXACT de `apps/ventes/selectors.py::_absorber_arrondi` (+
// `domain/argent.PAS_ARRONDI_DEVIS`, `_ARRONDI_CENTIMES_CEDES`) : même ordre
// d'essai, même arrondi moitié-vers-le-haut de la TVA, en centimes entiers.
export const PAS_ARRONDI_DEVIS = 100
const ARRONDI_CENTIMES_CEDES = 5n

function tvaDe(baseC, rH) {
  return diviserMoitieHaut(baseC * BigInt(rH), 10000n).valeur
}

// `paniers` : [{ rH (taux × 100), netC (HT net, centimes) }] ; rend les
// nouvelles bases (même ordre) ou `null` quand le TTC reste tel quel.
function absorberArrondi(paniers, ttcC, pasC) {
  if (pasC <= 0n || ttcC < pasC) return null
  const cible = (ttcC / pasC) * pasC
  if (cible === ttcC) return null
  const ordre = paniers.map((_, k) => k).sort((a, b) => paniers[b].rH - paniers[a].rH)
  for (const essai of [cible, cible - pasC]) {
    if (essai <= 0n) break
    for (const i of ordre) {
      // (autre panier qui cède, centimes cédés) — (null, 0) d'abord.
      const cessions = [[null, 0n]]
      for (const j of ordre) {
        if (j === i) continue
        for (let d = 1n; d <= ARRONDI_CENTIMES_CEDES; d += 1n) cessions.push([j, d])
      }
      for (const [j, d] of cessions) {
        const nouvelles = paniers.map(p => p.netC)
        if (j !== null) {
          nouvelles[j] -= d
          if (nouvelles[j] < 0n) continue
        }
        let autres = 0n
        nouvelles.forEach((b, k) => { if (k !== i) autres += b + tvaDe(b, paniers[k].rH) })
        const reste = essai - autres
        if (reste < 0n) continue
        const x0 = (reste * 10000n) / (10000n + BigInt(paniers[i].rH))
        for (const k of [-2n, -1n, 0n, 1n, 2n]) {
          const x = x0 + k
          if (x < 0n || x > paniers[i].netC) continue
          if (x + tvaDe(x, paniers[i].rH) === reste) {
            nouvelles[i] = x
            return nouvelles
          }
        }
      }
    }
  }
  return null
}

// Le HT d'une ligne en nanos : un BigInt déjà exact est pris tel quel.
function htNanoDe(ligne) {
  if (typeof ligne?.htNano === 'bigint') return ligne.htNano
  return nanos(montantHtLigne(ligne))
}

/**
 * Totaux canoniques d'un ensemble de lignes, au centime.
 *
 * @param {Array} lignes `{ htNano?: bigint, taux?, typeLigne?, optionnelle? }`
 *   (sinon le HT est `montantHtLigne`) ; seules les lignes qui
 *   `ligneCompteDansTotaux` entrent.
 * @param {number|string} remisePct remise GLOBALE, en pourcent.
 * @param {{arrondiPas?: number}} [options] ARRONDI-100 — palier (MAD) du TTC
 *   ramené au multiple inférieur ; absent / 0 = aucun arrondi.
 * @returns {{htBrut:number, remise:number, arrondi:number, htNet:number,
 *   tvaParTaux:Array<{taux:number, htNet:number, tva:number}>, tva:number,
 *   ttc:number, htNetCentimes:bigint, remiseCentimes:bigint}}
 *   `htNetCentimes` reste le HT net AVANT arrondi (la base que
 *   `repartirRemiseParLigne` répartit sur les lignes).
 */
export function totauxCanoniques(lignes, remisePct = 0, { arrondiPas = 0 } = {}) {
  const pctNano = nanos(parseFloat(remisePct) || 0)
  let htBrutNano = 0n
  const buckets = new Map() // taux ×100 → Σ HT (nanos)
  for (const ligne of (lignes || []).filter(ligneCompteDansTotaux)) {
    const n = htNanoDe(ligne)
    htBrutNano += n
    const taux = parseFloat(ligne?.taux ?? ligne?.taux_tva)
    const rH = Math.round((Number.isFinite(taux) ? taux : 20) * 100)
    buckets.set(rH, (buckets.get(rH) || 0n) + n)
  }
  const remiseC = pctNano === 0n
    ? 0n
    : diviserMoitieHaut(htBrutNano * pctNano, NANO * NANO).valeur
  // ERR-QAH-PROP-TOTAUX-REMISE-100-NEGATIF — la borne HT net ≥ 0 vit ICI, une
  // seule fois (à remise 100 %, un HT brut à demi-centime rendait −0,01).
  const htNetBrutC = diviserMoitieHaut(
    htBrutNano - remiseC * CENTIME_EN_NANO, CENTIME_EN_NANO).valeur
  const htNetC = htNetBrutC < 0n ? 0n : htNetBrutC
  const rates = [...buckets.keys()].sort((a, b) => a - b)
  const nets = new Map()
  if (rates.length <= 1) {
    nets.set(rates.length ? rates[0] : 2000, htNetC)
  } else {
    const facteur = 100n * NANO - pctNano
    rates.forEach(r => nets.set(
      r, diviserMoitieHaut(buckets.get(r) * facteur, NANO * NANO).valeur))
    const somme = [...nets.values()].reduce((s, v) => s + v, 0n)
    const dernier = rates[rates.length - 1]
    nets.set(dernier, nets.get(dernier) + (htNetC - somme))
  }
  let tvaParTaux = [...nets.entries()].map(([r, net]) => ({
    taux: r / 100, rH: r, htNetC: net, tvaC: tvaDe(net, r),
  }))
  let tvaC = tvaParTaux.reduce((s, t) => s + t.tvaC, 0n)
  // ARRONDI-100 — le TTC ramené au palier inférieur par une baisse de HT
  // (même calcul que `_absorber_arrondi`) ; `arrondiC` = baisse totale de HT.
  let arrondiC = 0n
  const pasC = BigInt(Math.round((parseFloat(arrondiPas) || 0) * 100))
  const bases = absorberArrondi(
    tvaParTaux.map(t => ({ rH: t.rH, netC: t.htNetC })), htNetC + tvaC, pasC)
  if (bases) {
    tvaParTaux = tvaParTaux.map((t, k) => ({
      ...t, htNetC: bases[k], tvaC: tvaDe(bases[k], t.rH),
    }))
    arrondiC = htNetC - bases.reduce((s, b) => s + b, 0n)
    tvaC = tvaParTaux.reduce((s, t) => s + t.tvaC, 0n)
  }
  const htNetFinalC = htNetC - arrondiC
  const enDh = (c) => Number(c) / 100
  return {
    htBrut: enDh(diviserMoitieHaut(htBrutNano, CENTIME_EN_NANO).valeur),
    remise: enDh(remiseC),
    arrondi: enDh(arrondiC),
    htNet: enDh(htNetFinalC),
    tvaParTaux: tvaParTaux.map(t => ({ taux: t.taux, htNet: enDh(t.htNetC), tva: enDh(t.tvaC) })),
    tva: enDh(tvaC),
    ttc: enDh(htNetFinalC + tvaC),
    htNetCentimes: htNetC,
    remiseCentimes: remiseC,
  }
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

  // QJR642 — remise et HT net viennent du NOYAU (`totauxCanoniques`) : le
  // pourcentage n'est jamais ré-appliqué ligne à ligne, et la borne ≥ 0 n'existe
  // qu'à un endroit.
  const { htNetCentimes: htNetC } = totauxCanoniques(
    comptees.map(i => ({ htNano: montants.get(i) })), remisePct)

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
