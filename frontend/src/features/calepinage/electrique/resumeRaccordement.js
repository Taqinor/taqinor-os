import { formatNumber } from '../../../lib/format'

/* ============================================================================
   Maquettes Électrique / Schéma (22/11) — CE QUE LA CARTE ET LE SCHÉMA DISENT DU RACCORDEMENT.
   ----------------------------------------------------------------------------
   Lu sur `GET resultat/` (contrat `calepinage_resultat.json`) : la table d'affectation SERVIE
   (`electrique.affectation[]`, avec `couleur_chaine`), l'onduleur dimensionné
   (`electrique.onduleurs[]`) et le cheminement mesuré (`troncons`, CALX228). Aucun chiffre
   n'est inventé : une grandeur que le serveur ne sert pas rend `null`, et l'écran OMET la case.
   ========================================================================== */

const nb = (v, decimals = 0) => formatNumber(v, { decimals, locale: 'fr' })
const estNombre = (v) => typeof v === 'number' && Number.isFinite(v)

/** Les chaînes de la table servie : `[{chaine, nombre, couleur, mppt}]`, rangées par numéro de chaîne
    (F3 : la table servie les donne dans l'ordre des modules — « Chaîne 3, 1, 4, 2 » sur la carte). */
export function chainesServies(resultat) {
  const lignes = resultat?.electrique?.affectation
  if (!Array.isArray(lignes)) return []
  const parChaine = new Map()
  for (const ligne of lignes) {
    if (!ligne || ligne.chaine == null) continue
    const cle = String(ligne.chaine)
    if (!parChaine.has(cle)) {
      parChaine.set(cle, {
        chaine: ligne.chaine,
        nombre: 0,
        couleur: typeof ligne.couleur_chaine === 'string' && ligne.couleur_chaine ? ligne.couleur_chaine : null,
        mppt: ligne.mppt ?? null,
      })
    }
    parChaine.get(cle).nombre += 1
  }
  return [...parChaine.values()]
    .sort((a, b) => Number(a.chaine) - Number(b.chaine) || String(a.chaine).localeCompare(String(b.chaine)))
}

/** « 2 × 6 panneaux » (chaînes égales) ou « 6 + 5 panneaux » ; `null` sans chaîne servie. */
export function texteChaines(chaines) {
  if (!chaines.length) return null
  const tailles = chaines.map((c) => c.nombre)
  if (tailles.every((t) => t === tailles[0])) {
    return `${chaines.length} × ${tailles[0]} panneau${tailles[0] > 1 ? 'x' : ''}`
  }
  return `${tailles.join(' + ')} panneaux`
}

/** « 6 kW » ou « 2 × 6 kW » : l'onduleur DIMENSIONNÉ servi ; `null` s'il n'est pas servi. */
export function texteOnduleur(resultat) {
  const onduleur = resultat?.electrique?.onduleurs?.[0]
  if (!onduleur || !estNombre(onduleur.taille_kw)) return null
  const kw = `${nb(onduleur.taille_kw, Number.isInteger(onduleur.taille_kw) ? 0 : 1)} kW`
  return estNombre(onduleur.nombre) && onduleur.nombre > 1 ? `${onduleur.nombre} × ${kw}` : kw
}

/** La longueur de câble côté panneaux (somme des tronçons `dc` MESURÉS), en mètres ; `null` si un
    tronçon DC n'a pas de longueur servie, ou si aucun cheminement n'est tracé (`troncons: null`). */
export function longueurCableDc(resultat) {
  const troncons = resultat?.troncons?.troncons
  if (!Array.isArray(troncons)) return null
  const dc = troncons.filter((t) => t?.cote === 'dc')
  if (!dc.length || !dc.every((t) => estNombre(t.longueur_m))) return null
  return dc.reduce((somme, t) => somme + t.longueur_m, 0)
}

/** Liaison DC tracée (suite ACAL1317) — la ligne de provenance sous « Câble côté panneaux » : quelle longueur la
    simulation et la chute de tension COMPTENT (`longueurs.source_dc` et `longueurs.dc.valeur_m` de `GET resultat/`,
    contrat `calepinage_resultat.json` › `liaison_dc_tracee`). `null` quand le serveur ne le dit pas. */
export function provenanceLiaisonDc(resultat) {
  const source = resultat?.longueurs?.source_dc
  const dc = resultat?.longueurs?.dc
  // Sans longueur, la perte du câble est la valeur de conception de la société (`ohmique_dc_conception_pct`,
  // dite « supposé ») quand elle en a une — jamais « aucune » : on ne le dit donc pas.
  if (source === 'defaut') return 'Longueur inconnue de la simulation : la perte de ce câble y est supposée, ou non comptée'
  if (!estNombre(dc?.valeur_m)) return null
  // La liaison comptée est la PIRE (module le plus éloigné → onduleur, descente comprise) : elle n'est pas la
  // somme des tronçons de la pastille, et n'y est jamais comparée. Une longueur SAISIE l'emporte toujours sur
  // le plan (descente avant l'altitude du tracé, coffret → onduleur avant le tracé) : la phrase le dit.
  const textes = {
    saisie: 'longueurs saisies',
    trace: 'relevée sur le plan',
    trace_et_saisie: 'tracé du plan et longueurs saisies — une longueur saisie l’emporte sur le plan',
  }
  if (!Object.hasOwn(textes, source)) return null
  // Simulation fraîche : le W1 servi est celui qu'elle a calculé ; sinon celui que la prochaine comptera.
  const verbe = resultat?.simule === true && !resultat?.simulation_perimee ? 'compte' : 'comptera'
  const metres = (v) => `${nb(v, Number.isInteger(v) ? 0 : 1)} m`
  const parts = (Array.isArray(dc.composantes) ? dc.composantes : [])
    .filter((c) => c && estNombre(c.valeur_m) && c.poste)
    .map((c) => `${metres(c.valeur_m)} ${c.poste}${c.origine ? ` (${c.origine})` : ''}`)
  return `La simulation ${verbe} ${metres(dc.valeur_m)} (${textes[source]})${parts.length ? ` : ${parts.join(' + ')}` : ''}`
}

/** ACAL1317 — le libellé de la case du câble : la provenance du tracé de l'onduleur s'y range dessous. */
export const CASE_CABLE = 'Câble côté panneaux'

/** ACAL1317 — la valeur de la case du câble tant qu'un geste sur l'onduleur n'est pas enregistré et relu. */
export const CABLE_A_MESURER = 'à mesurer à l’enregistrement'

/** Les trois cases de la pastille de carte (« Chaînes | Onduleur | Câble côté panneaux ») : seules les
    cases servies, `[{libelle, valeur}]`. `cableEnAttente` (ACAL1317) : la longueur servie décrit l'ancien tracé,
    elle est retenue. */
export function casesPastille(resultat, { cableEnAttente = false } = {}) {
  const metres = cableEnAttente ? null : longueurCableDc(resultat)
  return [
    { libelle: 'Chaînes', valeur: texteChaines(chainesServies(resultat)) },
    { libelle: 'Onduleur', valeur: texteOnduleur(resultat) },
    { libelle: CASE_CABLE, valeur: cableEnAttente ? CABLE_A_MESURER : metres === null ? null : `${nb(metres)} m` },
  ].filter((c) => c.valeur)
}

/** « Chaîne 1 · entrée 2 » — le libellé d'une chaîne de la légende (l'entrée MPPT seulement si servie). */
export function libelleChaine(c) {
  return c.mppt == null ? `Chaîne ${c.chaine}` : `Chaîne ${c.chaine} · entrée ${c.mppt}`
}

/** La phrase sous le schéma : « Dessiné tout seul à partir du raccordement : 2 chaînes de 6 panneaux,
    52 m de câble côté panneaux au total. » — seulement les morceaux servis ; `null` sans chaîne. */
export function phraseRaccordement(resultat) {
  const chaines = chainesServies(resultat)
  if (!chaines.length) return null
  const tailles = chaines.map((c) => c.nombre)
  const egales = tailles.every((t) => t === tailles[0])
  const morceaux = [egales
    ? `${chaines.length} chaîne${chaines.length > 1 ? 's' : ''} de ${tailles[0]} panneau${tailles[0] > 1 ? 'x' : ''}`
    : `${chaines.length} chaînes (${tailles.join(', ')} panneaux)`]
  const metres = longueurCableDc(resultat)
  if (metres !== null) morceaux.push(`${nb(metres)} m de câble côté panneaux au total`)
  return `Dessiné tout seul à partir du raccordement : ${morceaux.join(', ')}.`
}
