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
import {
  ligneProduitCatalogue, TVA_STANDARD_DEFAUT, ttcExactFromHt,
  COMMERCIAL_CATEGORIES, COMMERCIAL_CATEGORY_QUESTIONS,
} from '../solar.js'
import { ROLES_CI_PRESTATION, ROUTE_PARAMETRES_PRESTATIONS_CI } from '../../stock/catalogue.js'

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

function plagesEtat(p, stockees) {
  const out = {}
  for (const { cle } of TYPES_JOUR) {
    const pl = (p.plages || {})[cle] || {}
    if (vide(pl.debut) && vide(pl.fin)) continue
    // AGNR7 — l'écran n'édite que la PREMIÈRE plage : inchangée, la liste
    // stockée (plages suivantes comprises) repart telle quelle.
    const liste = stockees && Array.isArray(stockees[cle]) ? stockees[cle] : null
    const premiere = liste && Array.isArray(liste[0]) ? liste[0] : null
    if (premiere && String(premiere[0]) === String(pl.debut) && String(premiere[1]) === String(pl.fin)) {
      out[cle] = liste
      continue
    }
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
  // AGNR7 — les feuilles que l'écran N'ÉDITE PAS repartent avec leur valeur
  // STOCKÉE (relevé de visite, devis auto, API) : `etude_schema.ecrire`
  // fusionne au PREMIER niveau, un `null` posé ici effacerait la donnée.
  const s = p.stocke && typeof p.stocke === 'object' ? p.stocke : {}
  const sSite = s.site || {}
  const sToit = s.toit || {}
  const sContraintes = s.contraintes || {}
  const sOptions = s.options || {}
  const sRythme = s.rythme || {}
  const memeNombre = (a, b) => !vide(a) && !vide(b) && Number(a) === Number(b)
  const jours = Array.isArray(p.joursOuverts) && p.joursOuverts.some(Boolean)
    ? p.joursOuverts.map(Boolean) : null
  const talonStocke = sRythme.talon && typeof sRythme.talon === 'object' ? sRythme.talon : null
  let talon = null
  if (p.talonInconnu) talon = { kw: null, part_pct: null, inconnu: true }
  else if (!vide(p.talonKw)) {
    talon = {
      kw: p.talonKw,
      part_pct: talonStocke && memeNombre(talonStocke.kw, p.talonKw) ? (talonStocke.part_pct ?? null) : null,
      inconnu: false,
    }
  }
  return {
    mode: ctx.mode,
    lead: ctx.lead ?? null,
    devis: ctx.devis ?? null,
    site: { ville: ctx.ville || sSite.ville || null, lat: sSite.lat ?? null, lon: sSite.lon ?? null },
    tension: p.tension || null,
    phases: p.phases || null,
    puissance_souscrite_kva: p.puissanceSouscrite,
    consommation: consommationEtat(p),
    tarif: ctx.tarif ?? null,
    rythme: {
      jours_ouverts: jours,
      plages: plagesEtat(p, sRythme.plages),
      equipes: p.equipes || null,
      debut_equipe_h: p.debutEquipeH,
      fermetures: (p.fermetures || []).map((f) => ({ du: f?.du, au: f?.au, motif: f?.motif })),
      ramadan: sRythme.ramadan ?? null,
      talon,
      categorie_commerciale: ctx.categorie || null,
      reponses_categorie: ctx.reponses && Object.keys(ctx.reponses).length ? ctx.reponses : null,
    },
    courbe_mesuree: p.courbe || null,
    toit: {
      type_pose: p.typePose || null,
      surface_utile_m2: p.surfaceUtile,
      surface_type: vide(p.surfaceUtile) ? null
        : (memeNombre(sToit.surface_utile_m2, p.surfaceUtile) && sToit.surface_type
          ? sToit.surface_type : 'declaree'),
      pente_deg: sToit.pente_deg ?? null,
      azimut_deg: sToit.azimut_deg ?? null,
      couverture: p.couverture || null,
      charge_admissible_kg_m2: sToit.charge_admissible_kg_m2 ?? null,
      charge_admissible_source: sToit.charge_admissible_source ?? null,
    },
    contraintes: {
      revente_choisie: p.tension === 'mt' ? Boolean(p.revente) : false,
      nb_points_raccordement: sContraintes.nb_points_raccordement ?? null,
      longueur_dc_m: sContraintes.longueur_dc_m ?? null,
      longueur_ac_m: sContraintes.longueur_ac_m ?? null,
      besoin_cellule_mt: sContraintes.besoin_cellule_mt ?? null,
    },
    tva_recuperable: ctx.tvaRecuperable ?? null,
    options: { batterie_souhaitee: sOptions.batterie_souhaitee ?? null, om: sOptions.om ?? null },
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
  // AGNR7 — les sous-objets STOCKÉS, gardés tels quels : les feuilles que
  // l'écran n'édite pas en repartent à l'enregistrement.
  p.stocke = JSON.parse(JSON.stringify({
    site: etude.site ?? null,
    toit: etude.toit ?? null,
    contraintes: etude.contraintes ?? null,
    options: etude.options ?? null,
    rythme: etude.rythme ?? null,
  }))
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
export const LIBELLE_A_CHIFFRER_VISITE = 'à chiffrer après visite'

export function lignesDepuisCompositionCi(composition, produits, tvaStandard) {
  const lignes = composition && Array.isArray(composition.lignes) ? composition.lignes : []
  // ADEV84 — le taux des repères est celui de la SOCIÉTÉ (`quoteLogic.tvaStandard`,
  // Paramètres) ; le défaut nommé de solar.js ne sert que tant qu'il est inconnu.
  const tva = Number(tvaStandard) > 0 ? Number(tvaStandard) : TVA_STANDARD_DEFAUT
  const rows = []
  for (const it of lignes) {
    const quantite = Number(it?.quantite)
    const quantiteOk = Number.isFinite(quantite) && quantite > 0
    // ADEV84 — une ligne sans quantité (câble DC/AC) ou marquée par le serveur
    // `a_chiffrer_visite` n'est plus sautée en silence : repère NOMMÉ, jamais
    // enregistré (aucun produit — `usePersistanceDevis` ne garde que les lignes
    // à produit) ; `a_chiffrer_visite: true` est le drapeau de CE module.
    if (it?.a_chiffrer_visite === true || !quantiteOk) {
      rows.push({
        produit: '',
        designation: `${it?.designation || 'Article C&I'} — ${LIBELLE_A_CHIFFRER_VISITE}`,
        quantite: quantiteOk ? quantite : 0,
        prix_unit_ttc: 0,
        taux_tva: tva,
        a_chiffrer_visite: true,
      })
      continue
    }
    const p = (it.produit == null || it.prix_connu === false) ? null
      : (produits || []).find((x) => String(x.id) === String(it.produit)) || null
    // ATOT28 — un produit tarifé : ligne catalogue (HT d'origine porté).
    const row = p ? ligneProduitCatalogue(p, quantite) : {
      produit: '',
      designation: `${it.designation || 'Article C&I'} — prix à renseigner`,
      quantite,
      prix_unit_ttc: 0,
      taux_tva: tva,
    }
    // ADEV92 (rejeu « humain » 23/10/2026) — le serveur sert le prix HT de la
    // ligne (`prix_unitaire_ht` : forfait société de Paramètres pour une
    // prestation, D-ACI-4=a ; prix catalogue pour un article) : l'écran le
    // porte tel quel, comme le devis automatique — un même site ne sort plus
    // à deux totaux selon le chemin (108 100 vs 123 500 MAD mesurés).
    const htServeur = Number(it.prix_unitaire_ht)
    if (p && Number.isFinite(htServeur) && htServeur > 0) {
      row.prix_unit_ttc = ttcExactFromHt(htServeur, row.taux_tva)
      row.prixHtOrigine = htServeur.toFixed(2)
    }
    rows.push(row)
  }
  return rows
}

// ADEV84 — l'avertissement « devis incomplet » de l'Auto-remplir : chaque poste
// « prix à renseigner » avec SON lien (Paramètres pour une prestation C&I, le
// catalogue Stock pour un article — il n'existe aucune route de fiche produit,
// la fiche s'ouvre en volet depuis `/stock`), puis les postes « à chiffrer
// après visite » (hors total : listés par le serveur et/ou repères sans quantité).
export function avertissementsCompositionCi(composition) {
  const lignes = composition && Array.isArray(composition.lignes) ? composition.lignes : []
  const lien = (nom) => {
    const l = lignes.find((x) => x?.designation === nom)
    return ROLES_CI_PRESTATION.includes(l?.role) ? ROUTE_PARAMETRES_PRESTATIONS_CI : '/stock'
  }
  const aRenseigner = (composition?.prix_a_renseigner || []).map((nom) => ({ nom, lien: lien(nom) }))
  const visite = new Set(composition?.a_chiffrer_visite || [])
  for (const l of lignes) {
    const q = Number(l?.quantite)
    if (l?.designation && (l.a_chiffrer_visite === true || !(Number.isFinite(q) && q > 0))) {
      visite.add(l.designation)
    }
  }
  return { aRenseigner, aChiffrerVisite: [...visite] }
}

/** Le devis porte-t-il des entrées C&I v2 ? */
export const etudePorteProfilCi = (e) => Boolean(e && typeof e === 'object'
  && ['consommation', 'rythme', 'toit', 'taille_explicite_kwc'].some((k) => e[k] != null))

// ── ADEV100 — le générateur s'OUVRE PRÉ-REMPLI depuis la fiche lead ──
// (rejeu « humain » R1-07 : catégorie « Non précisée », contrat vide, lead
// « Hôtel » non repris — la commerciale retapait ce que le lead savait déjà).
// `semisCiDepuisLead` calcule, SANS rien écrire, ce que la fiche lead apporte à
// l'écran : des valeurs ÉDITABLES (jamais verrouillées), repérées par un badge
// de provenance (LIBELLE_REPRIS_LEAD). Règles : une valeur absente du lead n'est pas semée ; un
// champ que la commerciale a DÉJÀ rempli n'est jamais écrasé ; la consommation
// du lead n'est reprise que si le lead n'a pas de relevé de factures (le
// serveur le lit mieux). Les champs que l'écran n'édite pas (équipes de travail
// d'un commerce) ne sont pas semés : ils resteraient cachés. Pure, sans React.
export const LIBELLE_REPRIS_LEAD = 'repris du lead'

const CONTRATS_LEAD = ['bt_domestique', 'bt_patente', 'bt_force_motrice', 'mt_general']
//: Réponses de catégorie que l'écran sait afficher en plus des questions.
const REPONSES_HEURES = ['heures', 'heures_cuisson', 'heures_garde', 'fermeture_du', 'fermeture_au']
const PHASES_LEAD = { monophase: 'mono', triphase: 'tri' }

/** Le type de pose que la fiche lead permet d'affirmer (jamais une terrasse béton : lestée ou fixée ?). */
function poseDuLead(lead) {
  if (lead.type_surface === 'ombriere') return 'ombriere'
  if (lead.type_surface === 'terrain') return 'sol'
  if (lead.type_toiture === 'bac_acier') return 'bac_acier'
  if (lead.type_toiture === 'tuiles') return 'toiture_inclinee'
  return ''
}

const nombrePositif = (v) => {
  const x = Number(v)
  return vide(v) || !Number.isFinite(x) || x <= 0 ? null : x
}

/**
 * `lead` : le DÉTAIL du lead (champs pro). `courant` : ce que l'écran porte
 * déjà — `{ profil, categorie, reponses, tarif }`. Rend `null` (rien à semer)
 * ou `{ profil: [[chemin, valeur]…], categorie, reponses, tarif, marques }` ;
 * `marques` = les clés des champs semés (badge « repris du lead »).
 */
export function semisCiDepuisLead(lead, courant = {}) {
  const type = lead && lead.type_installation
  if (type !== 'commercial' && type !== 'industriel') return null
  const p = { ...profilCiVide(), ...(courant.profil || {}) }
  const profil = []
  const marques = []
  const semer = (cle, chemin, valeur) => {
    profil.push([chemin, valeur])
    if (!marques.includes(cle)) marques.push(cle)
  }

  // Consommation : le kWh MENSUEL du lead vaut 12× en annuel.
  const mensuel = nombrePositif(lead.conso_mensuelle_kwh)
  const releve = lead.releve_conso && Array.isArray(lead.releve_conso.mois)
    && lead.releve_conso.mois.length > 0
  const consoVide = (p.kwhMensuels || []).every(vide) && vide(p.kwhAnnuel)
    && !(p.factures || []).length
  if (mensuel && !releve && consoVide) {
    profil.push(['saisieConso', 'annuel'])
    semer('kwhAnnuel', 'kwhAnnuel', String(Math.round(mensuel * 12 * 100) / 100))
  }

  // Raccordement : tension (jamais « je ne sais pas » ni le défaut visible du site web), phase.
  if (['bt', 'mt'].includes(lead.tension_raccordement)
      && lead.tension_source !== 'site_defaut_visible' && vide(p.tension)) {
    semer('tension', 'tension', lead.tension_raccordement)
  }
  const phase = PHASES_LEAD[lead.raccordement]
  if (phase && vide(p.phases)) semer('phases', 'phases', phase)

  // Rythme : jours, heures d'ouverture.
  if (Array.isArray(lead.jours_ouverture) && lead.jours_ouverture.length
      && !(p.joursOuverts || []).some(Boolean)) {
    const jours = new Set(lead.jours_ouverture.map(Number))
    semer('joursOuverts', 'joursOuverts', Array.from({ length: 7 }, (_, i) => jours.has(i + 1)))
  }
  const plage = (p.plages || {}).ouvre || {}
  if (!vide(lead.heure_debut) && !vide(lead.heure_fin) && vide(plage.debut) && vide(plage.fin)) {
    semer('plages', 'plages.ouvre.debut', texte(lead.heure_debut))
    profil.push(['plages.ouvre.fin', texte(lead.heure_fin)])
  }

  // Toit : surface et type de pose.
  const surface = nombrePositif(lead.surface_toiture_m2)
  if (surface && vide(p.surfaceUtile)) semer('surfaceUtile', 'surfaceUtile', String(surface))
  const pose = poseDuLead(lead)
  if (pose && vide(p.typePose)) semer('typePose', 'typePose', pose)

  // Catégorie commerciale et ses réponses (commercial seulement).
  let categorie = null
  let reponses = null
  if (type === 'commercial') {
    const courante = courant.categorie && courant.categorie !== 'non_precisee' ? courant.categorie : null
    if (!courante && COMMERCIAL_CATEGORIES.some((c) => c.value === lead.categorie_commerciale)) {
      categorie = lead.categorie_commerciale
      marques.push('categorie')
    }
    const active = categorie || courante
    const brutes = lead.reponses_categorie && typeof lead.reponses_categorie === 'object'
      ? lead.reponses_categorie : {}
    const deja = courant.reponses || {}
    const acceptees = new Set([
      ...(COMMERCIAL_CATEGORY_QUESTIONS[active] || []).map((q) => q.key), ...REPONSES_HEURES,
    ])
    const posees = {}
    for (const [cle, valeur] of Object.entries(active && active === lead.categorie_commerciale ? brutes : {})) {
      if (!acceptees.has(cle) || vide(valeur) || !vide(deja[cle])) continue
      posees[cle] = valeur
      marques.push(`reponses.${cle}`)
    }
    if (Object.keys(posees).length) reponses = posees
  }

  // Contrat d'électricité (+ option bi-horaire de la force motrice).
  let tarif = null
  const contrat = lead.contrat_electricite
  if (CONTRATS_LEAD.includes(contrat) && vide((courant.tarif || {}).contrat)) {
    tarif = {
      contrat,
      optionBiHoraire: contrat === 'bt_force_motrice' && lead.option_tarifaire_bt === 'bi_horaire',
    }
    marques.push('contrat')
  }

  return marques.length ? { profil, categorie, reponses, tarif, marques } : null
}

/** La clé « repris du lead » qu'une modification du champ `chemin` du profil efface. */
export function cleReprisDuChamp(chemin) {
  const tete = String(chemin).split('.')[0]
  return ['saisieConso', 'kwhMensuels', 'factures'].includes(tete) ? 'kwhAnnuel' : tete
}
