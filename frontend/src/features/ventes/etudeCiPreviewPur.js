// CIQ124 — fonctions PURES de l'aperçu C&I serveur (imports relatifs seulement : elles
// tournent sous `node --test`, voir etudeCiPreview.test.mjs).
//
// Contrat partagé : `backend/django_core/apps/ventes/contract_samples/
// etude_ci_preview.json` (CIQ2). L'écran ne CALCULE rien : il construit le
// corps à partir de ce que le vendeur a TAPÉ, l'envoie à
// `POST /ventes/etude-ci/preview/` (CIQ118) et affiche la réponse.
//
// RÈGLES :
//   1. aucune valeur par défaut n'est posée ici — un champ vide part `null`
//      (« un défaut n'est jamais enregistré comme une saisie ») ;
//   2. aucun nombre n'est arrondi ni « corrigé » : la saisie part telle quelle
//      (seule la virgule décimale est lue comme un point) ;
//   3. tant qu'il manque l'essentiel (mode C&I, et une consommation OU une
//      taille explicite), le corps vaut `null` : AUCUN appel réseau ;
//   4. toutes les alertes du serveur sont rendues, aucune n'est filtrée ; les
//      alertes INTERNES sont marquées (jamais imprimées au client) ;
//   5. une réponse qui ne décrit plus la saisie courante n'est jamais montrée.

import {
  nombreOuNull, texteOuNull, creerLibelleProvenance, alertesDuServeur,
} from './etudePreviewCommun.js'

export { nombreOuNull }

const MODES = ['commercial', 'industriel']

const booleenOuNull = (v) => {
  if (v === true || v === false) return v
  if (v === 'true' || v === 'oui') return true
  if (v === 'false' || v === 'non') return false
  return null
}

const objetOuNull = (v) => (v && typeof v === 'object' && !Array.isArray(v)
  ? JSON.parse(JSON.stringify(v)) : null)

/** Réponse de catégorie : booléen, nombre tapé, sinon texte tel quel. */
const reponse = (v) => {
  if (typeof v === 'boolean') return v
  const n = nombreOuNull(v)
  return n !== null ? n : texteOuNull(v)
}

const liste12 = (v) => {
  if (!Array.isArray(v) || v.length !== 12) return null
  const out = v.map(nombreOuNull)
  return out.some((x) => x !== null) ? out : null
}

function construireConsommation(c = {}) {
  const factures = Array.isArray(c.factures_mad) ? c.factures_mad
    .filter((f) => f && texteOuNull(f.mois))
    .map((f) => ({
      mois: texteOuNull(f.mois),
      montant_ttc: nombreOuNull(f.montant_ttc),
      kwh: nombreOuNull(f.kwh),
    })) : []
  const registres = Array.isArray(c.registres_mt) && c.registres_mt.length
    ? c.registres_mt.map((r) => Object.fromEntries(Object.entries(r || {})
      .map(([k, v]) => [k, nombreOuNull(v)])))
    : null
  return {
    kwh_mensuels: liste12(c.kwh_mensuels),
    kwh_annuel: nombreOuNull(c.kwh_annuel),
    factures_mad: factures,
    registres_mt: registres,
  }
}

function construireRythme(r = {}) {
  const plages = r.plages && typeof r.plages === 'object'
    ? Object.fromEntries(Object.entries(r.plages).map(([type, liste]) => [type,
      (Array.isArray(liste) ? liste : []).map((p) => (Array.isArray(p)
        ? p.map(nombreOuNull) : p))]))
    : null
  const talon = r.talon && typeof r.talon === 'object' ? {
    kw: nombreOuNull(r.talon.kw),
    part_pct: nombreOuNull(r.talon.part_pct),
    inconnu: booleenOuNull(r.talon.inconnu),
  } : null
  const reponses = r.reponses_categorie && typeof r.reponses_categorie === 'object'
    ? Object.fromEntries(Object.entries(r.reponses_categorie)
      .map(([k, v]) => [k, reponse(v)]))
    : null
  return {
    jours_ouverts: Array.isArray(r.jours_ouverts) && r.jours_ouverts.length === 7
      ? r.jours_ouverts.map((j) => booleenOuNull(j)) : null,
    plages,
    equipes: texteOuNull(r.equipes),
    debut_equipe_h: nombreOuNull(r.debut_equipe_h),
    fermetures: Array.isArray(r.fermetures) ? r.fermetures
      .filter((f) => f && texteOuNull(f.du) && texteOuNull(f.au))
      .map((f) => ({ du: texteOuNull(f.du), au: texteOuNull(f.au), motif: texteOuNull(f.motif) }))
      : [],
    ramadan: objetOuNull(r.ramadan),
    talon,
    categorie_commerciale: texteOuNull(r.categorie_commerciale),
    reponses_categorie: reponses,
  }
}

/** La consommation est-elle exprimée (kWh, factures, registres ou courbe) ? */
export function consommationExprimee(etat) {
  const c = (etat && etat.consommation) || {}
  if ((liste12(c.kwh_mensuels) || []).some((v) => v !== null && v > 0)) return true
  if ((nombreOuNull(c.kwh_annuel) || 0) > 0) return true
  if ((c.factures_mad || []).some((f) => (nombreOuNull(f?.kwh) || 0) > 0
    || (nombreOuNull(f?.montant_ttc) || 0) > 0)) return true
  if (Array.isArray(c.registres_mt) && c.registres_mt.length) return true
  return Boolean(etat && etat.courbe_mesuree)
}

/**
 * Le corps du contrat `etude_ci_preview.json`, ou `null` tant qu'il manque
 * l'essentiel (aucun appel). `etat` suit la forme du corps (les nombres
 * peuvent arriver en texte, tels que tapés).
 */
export function construireCorpsCi(etat) {
  if (!etat || !MODES.includes(etat.mode)) return null
  const explicite = nombreOuNull(etat.taille_explicite_kwc)
  if (!consommationExprimee(etat) && !(explicite !== null && explicite > 0)) return null
  return normaliserCorpsCi(etat)
}

/**
 * CIQ125 — la forme du corps SANS la garde « essentiel présent » : c'est
 * aussi la forme des ENTRÉES C&I v2 persistées dans `etude_params`
 * (`cles_etude_params_ci_v2.entrees`), une seule normalisation pour les deux.
 */
export function normaliserCorpsCi(etat) {
  const e = etat || {}
  const explicite = nombreOuNull(e.taille_explicite_kwc)
  const site = e.site || {}
  const toit = e.toit || {}
  const contraintes = e.contraintes || {}
  const options = e.options || {}
  return {
    mode: e.mode,
    lead: nombreOuNull(e.lead),
    devis: nombreOuNull(e.devis),
    site: { ville: texteOuNull(site.ville), lat: nombreOuNull(site.lat), lon: nombreOuNull(site.lon) },
    tension: texteOuNull(e.tension),
    phases: texteOuNull(e.phases),
    puissance_souscrite_kva: nombreOuNull(e.puissance_souscrite_kva),
    consommation: construireConsommation(e.consommation),
    tarif: objetOuNull(e.tarif),
    rythme: construireRythme(e.rythme),
    courbe_mesuree: objetOuNull(e.courbe_mesuree),
    toit: {
      type_pose: texteOuNull(toit.type_pose),
      surface_utile_m2: nombreOuNull(toit.surface_utile_m2),
      surface_type: texteOuNull(toit.surface_type),
      pente_deg: nombreOuNull(toit.pente_deg),
      azimut_deg: nombreOuNull(toit.azimut_deg),
      couverture: texteOuNull(toit.couverture),
      charge_admissible_kg_m2: nombreOuNull(toit.charge_admissible_kg_m2),
      charge_admissible_source: texteOuNull(toit.charge_admissible_source),
    },
    contraintes: {
      revente_choisie: booleenOuNull(contraintes.revente_choisie),
      nb_points_raccordement: nombreOuNull(contraintes.nb_points_raccordement),
      longueur_dc_m: nombreOuNull(contraintes.longueur_dc_m),
      longueur_ac_m: nombreOuNull(contraintes.longueur_ac_m),
      besoin_cellule_mt: booleenOuNull(contraintes.besoin_cellule_mt),
    },
    tva_recuperable: texteOuNull(e.tva_recuperable),
    options: {
      batterie_souhaitee: booleenOuNull(options.batterie_souhaitee),
      om: booleenOuNull(options.om),
    },
    taille_explicite_kwc: explicite,
  }
}

const LIBELLES_ORIGINE = {
  saisie: 'saisi',
  lead: 'fiche lead',
  devis: 'devis',
  reglage_societe: 'réglage société',
  fiche: 'fiche produit',
  pvgis: 'PVGIS',
  calepinage: 'calepinage',
  calculee: 'calculé',
  estimation: 'estimation',
  mesure_visite: 'mesuré en visite',
}
const LIBELLES_DETAIL_LEAD = {
  client: 'déclaré par le client',
  site_web: 'formulaire du site',
  facture: 'lu sur facture',
  mesure_visite: 'mesuré en visite',
  derive: 'déduit',
}

export const libelleProvenance = creerLibelleProvenance(LIBELLES_ORIGINE, LIBELLES_DETAIL_LEAD)

/**
 * TOUTES les alertes du serveur, dans l'ordre, aucune filtrée. Les alertes
 * `interne: true` sont MARQUÉES (affichage vendeur seulement), jamais
 * retirées. Une alerte sans message garde son code pour rester visible.
 */
export const alertesAffichables = (reponse) => alertesDuServeur(
  reponse, 'Alerte du moteur C&I', (a) => ({ niveau: a?.niveau || 'alerte', interne: a?.interne === true }),
)

/**
 * La réponse à afficher pour la saisie COURANTE, ou `null` : une réponse
 * servie pour une autre saisie (arrivée après une nouvelle frappe) n'est
 * jamais montrée.
 */
export function reponseAJour(donnees, corpsServi, corpsCourant) {
  if (!donnees || !corpsCourant) return null
  const cle = typeof corpsCourant === 'string' ? corpsCourant : JSON.stringify(corpsCourant)
  return corpsServi === cle ? donnees : null
}
