/* ============================================================================
   « RELEVÉ DE VISITE » AU TÉLÉPHONE — les règles pures de l'écran (maquette Telephone).
   ----------------------------------------------------------------------------
   OÙ VONT LES VALEURS (aucune porte neuve, aucun statut neuf) :
     * Longueur / Largeur → deux CHAÎNES DE COTES du relevé terrain (une cote chacune,
       nommée « Longueur » / « Largeur »), dans le MÊME corps que le panneau de l'atelier
       (`corpsReleve.js`) ; les autres chaînes du relevé courant sont gardées telles quelles.
     * Le toit regarde vers → l'azimut boussole du relevé + sa précision DÉCLARÉE.
     * Pente du toit → la pente du PAN (`zones[i].pitchDeg` + `pitchSource`) par la primitive
       d'écriture par section, exactement comme `SaisiePente.jsx` (provenance `telephone`
       quand elle vient du capteur, rien sinon).
     * Photos → les photos de site (genres de `PhotoSite.Genre` : drone / oblique / sol)
       par `fileEnvoiPhotos.deposerOuMettreEnFile` (la file hors ligne existante).
   ========================================================================== */

export const LONGUEUR = 'Longueur'
export const LARGEUR = 'Largeur'

/* Les 3 genres EXACTS de `PhotoSite.Genre` (models.py) : le serveur n'en stocke pas d'autre. */
export const CATEGORIES_PHOTO = [
  { genre: 'drone', libelle: 'Drone' },
  { genre: 'oblique', libelle: 'Oblique (aérienne)' },
  { genre: 'sol', libelle: 'Depuis le sol' },
]

/** « 12,4 » → « 12.4 » (on normalise, on ne refuse jamais une virgule). */
export const versPoint = (texte) => String(texte ?? '').trim().replace(',', '.')
/** 12.4 → « 12,4 » pour l'affichage français. */
export const versVirgule = (v) => (v === '' || v === null || v === undefined ? '' : String(v).replace('.', ','))

/** Une chaîne est vide quand ni son nom, ni son total, ni aucune cote ne porte de saisie. */
const vide = (c) => !c.nom && c.totalMesure === '' && c.cotes.every((k) => !k.nom && (k.valeur === '' || k.valeur === null))

/** Les chaînes RÉELLEMENT saisies (le gabarit vide du panneau de l'atelier est écarté). */
export const chainesSaisies = (chaines) => (chaines ?? []).filter((c) => !vide(c))

/** La valeur de la mesure `nom` (chaîne à une cote du même nom), ou ''. */
export function mesureDesChaines(chaines, nom) {
  const c = (chaines ?? []).find((x) => x.nom === nom && x.cotes.length === 1)
  return c ? String(c.cotes[0].valeur ?? '') : ''
}

/** Les chaînes avec la mesure `nom` posée (ou retirée si vide) — les autres chaînes intactes. */
export function avecMesure(chaines, nom, valeur) {
  const v = versPoint(valeur)
  const autres = (chaines ?? []).filter((x) => !(x.nom === nom && x.cotes.length === 1))
  if (v === '') return autres
  return [...autres, { nom, totalMesure: '', toleranceM: '', cotes: [{ nom, valeur: v }] }]
}

const DIRECTIONS = [
  'Nord', 'Nord-nord-est', 'Nord-est', 'Est-nord-est', 'Est', 'Est-sud-est', 'Sud-est', 'Sud-sud-est',
  'Sud', 'Sud-sud-ouest', 'Sud-ouest', 'Ouest-sud-ouest', 'Ouest', 'Ouest-nord-ouest', 'Nord-ouest', 'Nord-nord-ouest',
]

/** Azimut (0 = nord, sens horaire) → l'une des 16 directions de la rose, ou ''. */
export function nomDirection(azimutDeg) {
  const a = Number(azimutDeg)
  if (azimutDeg === '' || azimutDeg === null || !Number.isFinite(a)) return ''
  return DIRECTIONS[Math.round((((a % 360) + 360) % 360) / 22.5) % 16]
}

/** Le jour local AAAA-MM-JJ : la date du relevé fait SUR PLACE, aujourd'hui. */
export function dateDuJour(d = new Date()) {
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

/** Téléphone posé à plat sur le pan, le haut vers le faîte (convention de `SaisiePente`). */
export function mesureDuCapteur(inclinaison, visee) {
  const c = Math.cos(inclinaison.betaDeg * Math.PI / 180) * Math.cos(inclinaison.gammaDeg * Math.PI / 180)
  return {
    penteDeg: Math.acos(Math.max(-1, Math.min(1, c))) * 180 / Math.PI,
    azimutDeg: visee && !visee.indisponible ? (visee.azimutDeg + 180) % 360 : null,
  }
}

/** D'où vient la pente enregistrée sur le pan — jamais « mesurée » sans le capteur. */
function provenancePente(zone) {
  const source = zone?.pitchSource
  if (source && typeof source === 'object') {
    if (source.provenance === 'telephone') return 'mesurée'
    if (source.provenance === 'visite') return 'de la visite'
    return 'saisie à la main'
  }
  return null
}

/**
 * La carte « Pente du toit » : la pente DU PAN telle que le document la stocke, lue comme
 * l'atelier la lit (`EtapeToit.penteAffichee`). Un pan `roofType: 'flat'` est un TOIT PLAT :
 * son `pitchDeg` (22 posé par `panVierge`, zones.ts) n'est pas une pente, et l'inclinaison
 * des TABLES (`geometry.tiltDeg`, celle que l'API publie dans `pose`) n'est pas celle du toit.
 * `pente` = la valeur en attente de « Terminer » ({ degres, capteur }), elle prime.
 * Rend { valeur, aide, bouton } ; `valeur` null = rien de stocké.
 */
export function penteDuPan(zone, pente = null) {
  if (pente) {
    return { valeur: `${degres(pente.degres)} · ${pente.capteur ? 'mesurée' : 'saisie à la main'}`, aide: null, bouton: 'Mesurer encore' }
  }
  if (zone?.roofType === 'flat') return { valeur: 'Toit plat', aide: null, bouton: 'Mesurer' }
  const deg = zone?.pitchDeg === null || zone?.pitchDeg === undefined ? NaN : Number(zone.pitchDeg)
  if (!Number.isFinite(deg)) return { valeur: null, aide: null, bouton: 'Mesurer' }
  const provenance = provenancePente(zone)
  if (!provenance) {
    return { valeur: `${degres(deg)} · à confirmer`, aide: 'Valeur de départ du pan, jamais mesurée.', bouton: 'Mesurer' }
  }
  return { valeur: `${degres(deg)} · ${provenance}`, aide: null, bouton: provenance === 'mesurée' ? 'Mesurer encore' : 'Mesurer' }
}

/** La ligne sous « Relevé de visite » : le client (ou le lead) — ville, lus sur le détail servi
 *  (`GET /calepinages/<id>/` : `client`/`lead` = {nom, ville}) ; repli : le nom du calepinage. */
export function ligneProjet(detail) {
  if (!detail) return ''
  const qui = (detail.client?.nom || detail.lead?.nom || detail.nom || '').trim()
  const ville = (detail.lead?.ville || detail.client?.ville || '').trim()
  return ville && qui && !qui.includes(ville) ? `${qui} — ${ville}` : qui
}

/** La note hors ligne, avec le compte RÉEL de la file (les photos, et le relevé terminé s'il attend le réseau). */
export function noteHorsLigne(enAttente, enLigne, releveEnFile = false) {
  const n = Number(enAttente) || 0
  const photos = n === 0 ? ''
    : n === 1 ? '1 photo gardée sur ce téléphone. Elle partira dès le retour du réseau.'
      : `${n} photos gardées sur ce téléphone. Elles partiront dès le retour du réseau.`
  const mesures = releveEnFile ? 'Le relevé terminé est gardé sur ce téléphone : il partira dès le retour du réseau.'
    : (enLigne ? '' : 'Les mesures s’enregistrent avec « Terminer le relevé », réseau revenu.')
  return [photos, mesures].filter(Boolean).join(' ')
}

/** Degrés à l'entier pour l'affichage (« 24° ») ; la valeur stockée reste exacte. */
export const degres = (v) => `${Math.round(Number(v))}°`
