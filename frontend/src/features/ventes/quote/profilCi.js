// CIQ125 — LE PROFIL C&I DÉCLARÉ : état d'écran ⇄ corps de l'aperçu serveur
// ⇄ entrées v2 de `etude_params`.
//
// Contrat partagé : `backend/django_core/apps/ventes/contract_samples/
// etude_ci_preview.json` (`corps`, `cles_etude_params_ci_v2.entrees`). L'écran
// garde ce que le vendeur a TAPÉ (texte) ; ce module le met à la forme du
// contrat (`normaliserCorpsCi`, la MÊME normalisation que le corps de
// l'aperçu) et fait l'aller-retour inverse à la réouverture (`?edit=`).
//
// RÈGLES : aucun défaut n'est posé (un champ vide part `null`) ; aucun nombre
// n'est arrondi ; aucun jour n'est coché d'office (le week-end n'est jamais
// supposé) ; fonctions PURES, sans React ni réseau (node --test).
import { normaliserCorpsCi, construireCorpsCi } from '../etudeCiPreviewPur.js'
import { ttcFromHt, tauxTvaOf } from '../solar.js'

export const JOURS_SEMAINE = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim']

/** Types de jour dont les plages horaires se saisissent. */
export const TYPES_JOUR = [
  { cle: 'ouvre', libelle: 'Jours ouvrés' },
  { cle: 'samedi', libelle: 'Samedi' },
  { cle: 'dimanche', libelle: 'Dimanche' },
]

const plageVide = () => ({ debut: '', fin: '' })

/** Équipes de travail (contrat `etude_ci_preview.json`, `rythme.equipes`). */
export const EQUIPES = [
  { value: '1x8', label: '1 × 8 h (journée)' },
  { value: '2x8', label: '2 × 8 h' },
  { value: '3x8', label: '3 × 8 h' },
  { value: 'continu', label: 'Continu 24 h / 24' },
]

/** CIQ135 — les colonnes d'un mois de registre MT (état d'écran → clé du corps). */
export const COLONNES_REGISTRE_MT = [
  { cle: 'pointe', corps: 'pointe_kwh', libelle: 'Pointe (kWh)' },
  { cle: 'pleines', corps: 'pleines_kwh', libelle: 'Pleines (kWh)' },
  { cle: 'creuses', corps: 'creuses_kwh', libelle: 'Creuses (kWh)' },
  { cle: 'puissance', corps: 'puissance_atteinte_kw', libelle: 'Puissance atteinte (kW)' },
  { cle: 'kvarh', corps: 'kvarh', libelle: 'Réactif (kvarh)' },
]

const registreVide = () => ({ pointe: '', pleines: '', creuses: '', puissance: '', kvarh: '' })

export const PROFIL_CI_VIDE = Object.freeze({
  // 'mensuel' (12 kWh) | 'annuel' (total kWh) | 'factures' (montants MAD)
  saisieConso: 'mensuel',
  kwhMensuels: Object.freeze(Array(12).fill('')),
  kwhAnnuel: '',
  factures: Object.freeze([]),
  joursOuverts: Object.freeze(Array(7).fill(false)),
  plages: Object.freeze({ ouvre: plageVide(), samedi: plageVide(), dimanche: plageVide() }),
  fermetures: Object.freeze([]),
  talonKw: '',
  talonInconnu: false,
  typePose: '',
  surfaceUtile: '',
  couverture: '',
  tension: '',
  phases: '',
  puissanceSouscrite: '',
  revente: false,
  tailleExplicite: '',
  // CIQ135 — industriel : équipes, registres MT, cos φ connu, courbe mesurée.
  equipes: '',
  debutEquipeH: '',
  registresMt: Object.freeze(Array.from({ length: 12 }, registreVide)),
  cosPhi: '',
  cosPhiProvenance: '',
  // L'objet `courbe_mesuree` du corps ({ contenu, source }) ou null.
  courbe: null,
})

export const profilCiVide = () => JSON.parse(JSON.stringify(PROFIL_CI_VIDE))

/** Pose `valeur` au chemin pointé (`a.b.0.c`), tableaux compris — immuable. */
export function poserProfilCi(profil, chemin, valeur) {
  const cles = String(chemin).split('.')
  const copier = (n) => (Array.isArray(n) ? [...n] : { ...(n || {}) })
  const racine = copier(profil || profilCiVide())
  let noeud = racine
  for (let i = 0; i < cles.length - 1; i += 1) {
    noeud[cles[i]] = copier(noeud[cles[i]])
    noeud = noeud[cles[i]]
  }
  noeud[cles[cles.length - 1]] = valeur
  // La revente n'existe qu'en MT : un site repassé hors MT la perd.
  if (chemin === 'tension' && valeur !== 'mt') racine.revente = false
  return racine
}

const vide = (v) => v === '' || v === null || v === undefined
const texte = (v) => (vide(v) ? '' : String(v))

const registreRempli = (r) => COLONNES_REGISTRE_MT.some(({ cle }) => !vide((r || {})[cle]))

/** CIQ135 — les 12 registres MT du corps, ou `null` tant qu'aucune cellule n'est saisie. */
function registresEtat(p) {
  const registres = Array.isArray(p.registresMt) ? p.registresMt : []
  if (!registres.some(registreRempli)) return null
  return Array.from({ length: 12 }, (_, i) => {
    const r = registres[i] || {}
    const mois = {}
    for (const { cle, corps } of COLONNES_REGISTRE_MT) mois[corps] = r[cle]
    if (!vide(p.cosPhi)) mois.cos_phi = p.cosPhi
    return mois
  })
}

function consommationEtat(p) {
  const registres = registresEtat(p)
  if (p.saisieConso === 'annuel') {
    return { kwh_mensuels: null, kwh_annuel: p.kwhAnnuel, factures_mad: [], registres_mt: registres }
  }
  if (p.saisieConso === 'factures') {
    return {
      kwh_mensuels: null,
      kwh_annuel: null,
      factures_mad: (p.factures || []).map((f) => ({
        mois: f?.mois, montant_ttc: f?.montant_ttc, kwh: f?.kwh,
      })),
      registres_mt: registres,
    }
  }
  return { kwh_mensuels: [...(p.kwhMensuels || [])], kwh_annuel: null, factures_mad: [], registres_mt: registres }
}

function plagesEtat(p) {
  const out = {}
  for (const { cle } of TYPES_JOUR) {
    const pl = (p.plages || {})[cle] || {}
    if (vide(pl.debut) && vide(pl.fin)) continue
    out[cle] = [[pl.debut, pl.fin]]
  }
  return Object.keys(out).length ? out : null
}

/**
 * L'état d'écran → l'état du corps (forme du contrat, nombres en texte).
 * `ctx` : { mode, lead, devis, ville, categorie, reponses }.
 */
export function etatCorpsDepuisProfil(profil, ctx = {}) {
  const p = { ...profilCiVide(), ...(profil || {}) }
  const jours = Array.isArray(p.joursOuverts) && p.joursOuverts.some(Boolean)
    ? p.joursOuverts.map(Boolean) : null
  return {
    mode: ctx.mode,
    lead: ctx.lead ?? null,
    devis: ctx.devis ?? null,
    site: { ville: ctx.ville || null, lat: null, lon: null },
    tension: p.tension || null,
    phases: p.phases || null,
    puissance_souscrite_kva: p.puissanceSouscrite,
    consommation: consommationEtat(p),
    tarif: ctx.tarif ?? null,
    rythme: {
      jours_ouverts: jours,
      plages: plagesEtat(p),
      equipes: p.equipes || null,
      debut_equipe_h: p.debutEquipeH,
      fermetures: (p.fermetures || []).map((f) => ({ du: f?.du, au: f?.au, motif: f?.motif })),
      ramadan: null,
      talon: p.talonInconnu
        ? { kw: null, part_pct: null, inconnu: true }
        : (vide(p.talonKw) ? null : { kw: p.talonKw, part_pct: null, inconnu: false }),
      categorie_commerciale: ctx.categorie || null,
      reponses_categorie: ctx.reponses && Object.keys(ctx.reponses).length ? ctx.reponses : null,
    },
    courbe_mesuree: p.courbe || null,
    toit: {
      type_pose: p.typePose || null,
      surface_utile_m2: p.surfaceUtile,
      surface_type: vide(p.surfaceUtile) ? null : 'declaree',
      pente_deg: null,
      azimut_deg: null,
      couverture: p.couverture || null,
      charge_admissible_kg_m2: null,
      charge_admissible_source: null,
    },
    contraintes: {
      revente_choisie: p.tension === 'mt' ? Boolean(p.revente) : false,
      nb_points_raccordement: null,
      longueur_dc_m: null,
      longueur_ac_m: null,
      besoin_cellule_mt: null,
    },
    tva_recuperable: ctx.tvaRecuperable ?? null,
    options: { batterie_souhaitee: null, om: null },
    taille_explicite_kwc: p.tailleExplicite,
  }
}

/**
 * Le corps de `POST /ventes/etude-ci/preview/`, ou `null` (aucun appel). Un
 * lead peut porter la consommation : avec un lead, le corps part même sans
 * consommation saisie et le serveur la résout (`entrees_resolues`).
 */
export function corpsCiDepuisProfil(profil, ctx = {}) {
  const etat = etatCorpsDepuisProfil(profil, ctx)
  const corps = construireCorpsCi(etat)
  if (corps) return corps
  return ctx.lead && ['commercial', 'industriel'].includes(ctx.mode) ? normaliserCorpsCi(etat) : null
}

//: Les ENTRÉES C&I v2 (propriétaire `ecran`) — `cles_etude_params_ci_v2.entrees`.
export const CLES_ENTREES_CI_V2 = [
  'mode', 'site', 'tension', 'phases', 'puissance_souscrite_kva', 'consommation',
  'rythme', 'courbe_mesuree', 'toit', 'contraintes', 'options', 'taille_explicite_kwc',
]

/** L'état d'écran → les ENTRÉES v2 de `etude_params` (jamais une dérivée). */
export function entreesCiV2(profil, ctx = {}) {
  const corps = normaliserCorpsCi(etatCorpsDepuisProfil(profil, ctx))
  const out = {}
  for (const cle of CLES_ENTREES_CI_V2) out[cle] = corps[cle] ?? null
  return out
}

/** La consommation est-elle exprimée, OU une taille explicite posée ? */
export function profilCiAncre(profil) {
  return corpsCiDepuisProfil(profil, { mode: 'commercial' }) !== null
}

/** Inverse : les entrées v2 stockées → l'état d'écran (`?edit=`). */
export function profilDepuisEtude(e) {
  const p = profilCiVide()
  const etude = e && typeof e === 'object' ? e : {}
  const c = etude.consommation || {}
  if (Array.isArray(c.kwh_mensuels) && c.kwh_mensuels.length === 12) {
    p.saisieConso = 'mensuel'
    p.kwhMensuels = c.kwh_mensuels.map(texte)
  } else if (!vide(c.kwh_annuel)) {
    p.saisieConso = 'annuel'
    p.kwhAnnuel = texte(c.kwh_annuel)
  } else if (Array.isArray(c.factures_mad) && c.factures_mad.length) {
    p.saisieConso = 'factures'
    p.factures = c.factures_mad.map((f) => ({
      mois: texte(f?.mois), montant_ttc: texte(f?.montant_ttc), kwh: texte(f?.kwh),
    }))
  }
  if (Array.isArray(c.registres_mt) && c.registres_mt.length === 12) {
    p.registresMt = c.registres_mt.map((m) => {
      const ligne = registreVide()
      for (const { cle, corps } of COLONNES_REGISTRE_MT) ligne[cle] = texte((m || {})[corps])
      return ligne
    })
    const cos = c.registres_mt.find((m) => !vide((m || {}).cos_phi))
    if (cos) p.cosPhi = texte(cos.cos_phi)
  }
  if (etude.courbe_mesuree && typeof etude.courbe_mesuree === 'object') {
    p.courbe = etude.courbe_mesuree
  }
  const r = etude.rythme || {}
  p.equipes = texte(r.equipes)
  p.debutEquipeH = texte(r.debut_equipe_h)
  if (Array.isArray(r.jours_ouverts) && r.jours_ouverts.length === 7) {
    p.joursOuverts = r.jours_ouverts.map((j) => j === true)
  }
  for (const { cle } of TYPES_JOUR) {
    const pl = r.plages && Array.isArray(r.plages[cle]) ? r.plages[cle][0] : null
    if (Array.isArray(pl)) p.plages[cle] = { debut: texte(pl[0]), fin: texte(pl[1]) }
  }
  p.fermetures = Array.isArray(r.fermetures)
    ? r.fermetures.map((f) => ({ du: texte(f?.du), au: texte(f?.au), motif: texte(f?.motif) })) : []
  if (r.talon && r.talon.inconnu === true) p.talonInconnu = true
  else if (r.talon) p.talonKw = texte(r.talon.kw)
  const t = etude.toit || {}
  p.typePose = texte(t.type_pose)
  p.surfaceUtile = texte(t.surface_utile_m2)
  p.couverture = texte(t.couverture)
  p.tension = texte(etude.tension)
  p.phases = texte(etude.phases)
  p.puissanceSouscrite = texte(etude.puissance_souscrite_kva)
  p.revente = etude.contraintes?.revente_choisie === true
  p.tailleExplicite = texte(etude.taille_explicite_kwc)
  return p
}

// ── CIQ126 — Auto-remplir C&I : les lignes de la COMPOSITION serveur ──
// `composition` = la réponse de l'aperçu (`composition.lignes`, contrat
// `etude_ci_preview.json`) ; `produits` = le catalogue de l'écran (prix de
// vente HT + TVA du produit). Le serveur dit QUOI et COMBIEN : quantités et
// produits tels quels ; l'écran ne fait que poser le prix catalogue du produit
// (TTC, l'écran est 100 % TTC). Un article « prix à renseigner »
// (`produit: null` ou `prix_connu: false`) devient une ligne SANS produit,
// nommée — jamais chiffrée à 0 comme un article gratuit, jamais enregistrée.
export function lignesDepuisCompositionCi(composition, produits) {
  const lignes = composition && Array.isArray(composition.lignes) ? composition.lignes : []
  const rows = []
  for (const it of lignes) {
    const quantite = Number(it?.quantite)
    if (!Number.isFinite(quantite) || quantite <= 0) continue
    const p = (it.produit == null || it.prix_connu === false) ? null
      : (produits || []).find((x) => String(x.id) === String(it.produit)) || null
    rows.push({
      produit: p ? String(p.id) : '',
      designation: p ? p.nom : `${it.designation || 'Article C&I'} — prix à renseigner`,
      quantite,
      prix_unit_ttc: p ? ttcFromHt(p.prix_vente, tauxTvaOf(p)) : 0,
      taux_tva: p ? tauxTvaOf(p) : 20,
    })
  }
  return rows
}

/** Le devis porte-t-il des entrées C&I v2 ? */
export const etudePorteProfilCi = (e) => Boolean(e && typeof e === 'object'
  && ['consommation', 'rythme', 'toit', 'taille_explicite_kwc'].some((k) => e[k] != null))
