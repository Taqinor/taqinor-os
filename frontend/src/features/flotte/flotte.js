/* ============================================================================
   FLOTTE — logique métier PURE (sans JSX, testable au node).
   ----------------------------------------------------------------------------
   Miroir front des choix de statut (`models.py`) et du contrôle de permis
   d'affectation (`services.controle_permis`, FLOTTE9). Aucune dépendance React :
   ces helpers alimentent les colonnes / filtres des écrans ET sont vérifiés par
   les tests unitaires. Ne JAMAIS diverger des valeurs backend (les libellés FR
   viennent des `TextChoices`).
   ========================================================================== */

// ── Choix de statut / énergie (valeur → libellé FR, copie fidèle du backend) ──

export const VEHICULE_STATUTS = {
  actif: 'Actif',
  maintenance: 'En maintenance',
  reforme: 'Réformé',
  // XFLT4 — cycle de vie complet (acquisition → cession) ; les 3 statuts
  // historiques ci-dessus restent intacts.
  commande: 'Commandé',
  a_vendre: 'À vendre',
  vendu: 'Vendu',
}

// XFLT4 — checklist de mise en service (gate du passage commande→actif),
// miroir de `Vehicule.CHECKLIST_MISE_EN_SERVICE` (jamais renommer/ajouter
// sans mettre à jour le backend).
export const CHECKLIST_MISE_EN_SERVICE_ITEMS = {
  immatriculation_faite: 'Immatriculation faite',
  plaques: 'Plaques posées',
  assurance_active: 'Assurance active',
  carte_grise_recue: 'Carte grise reçue',
}

export const ENERGIES = {
  diesel: 'Diesel',
  essence: 'Essence',
  electrique: 'Électrique',
  hybride: 'Hybride',
}

export const TYPE_ENGINS = {
  nacelle: 'Nacelle',
  groupe_electrogene: 'Groupe électrogène',
  chariot: 'Chariot',
}

export const RESERVATION_STATUTS = {
  demandee: 'Demandée',
  confirmee: 'Confirmée',
  annulee: 'Annulée',
}

export const DEMANDE_STATUTS = {
  demandee: 'Demandée',
  approuvee: 'Approuvée',
  refusee: 'Refusée',
  annulee: 'Annulée',
}

export const ENTRETIEN_STATUTS = {
  a_faire: 'À faire',
  planifie: 'Planifié',
  fait: 'Fait',
}

export const OR_STATUTS = {
  ouvert: 'Ouvert',
  en_cours: 'En cours',
  cloture: 'Clôturé',
}

export const PNEU_STATUTS = {
  monte: 'Monté',
  depose: 'Déposé',
  use: 'Usé',
}

export const PNEU_POSITIONS = {
  av_g: 'Avant gauche',
  av_d: 'Avant droite',
  ar_g: 'Arrière gauche',
  ar_d: 'Arrière droite',
  secours: 'Roue de secours',
}

export const ECHEANCE_TYPES = {
  visite_technique: 'Visite technique',
  assurance: 'Assurance',
  vignette: 'Vignette / TSAV',
  carte_grise: 'Carte grise',
  taxe_essieu: "Taxe à l'essieu",
  autre: 'Autre',
}

// Statut « réglementaire » commun (échéances / assurances / VT / cartes grises).
export const CONFORMITE_STATUTS = {
  a_jour: 'À jour',
  valide: 'Valide',
  a_renouveler: 'À renouveler',
  expire: 'Expiré',
  expiree: 'Expirée',
}

export const SINISTRE_STATUTS = {
  declare: 'Déclaré',
  en_cours: 'En cours',
  clos: 'Clos',
  indemnise: 'Indemnisé',
}

export const SINISTRE_TYPES = {
  accident_materiel: 'Accident matériel',
  accident_corporel: 'Accident corporel',
  vol: 'Vol',
  bris_de_glace: 'Bris de glace',
  incendie: 'Incendie',
  catastrophe: 'Catastrophe naturelle',
  autre: 'Autre',
}

export const INFRACTION_STATUTS = {
  a_payer: 'À payer',
  payee: 'Payée',
  contestee: 'Contestée',
  classee: 'Classée',
}

export const INFRACTION_TYPES = {
  exces_vitesse: 'Excès de vitesse',
  stationnement: 'Stationnement',
  feu_rouge: 'Feu rouge',
  document: 'Défaut de document',
  autre: 'Autre',
}

export const TELEMATIQUE_SOURCES = {
  manuel: 'Saisie manuelle',
  telematique: 'Fournisseur télématique',
}

// Options {value,label} pour un <Select> à partir d'un map de choix.
export function optionsFrom(map) {
  return Object.entries(map).map(([value, label]) => ({ value, label }))
}

// ── FLOTTE9 — Contrôle de permis à l'affectation (miroir services.controle_permis) ──

/** Normalise une catégorie de permis pour comparaison : majuscules, sans
    espaces. `" ce "` → `"CE"` ; vide/null → chaîne vide. */
export function normaliserCategoriePermis(categorie) {
  if (!categorie) return ''
  return String(categorie).replace(/\s+/g, '').toUpperCase()
}

/**
 * Contrôle « permis valide / catégorie » avant une affectation conducteur↔véhicule.
 *
 * Piloté par l'EXIGENCE du véhicule : ne se déclenche que si
 * `vehicule.categorie_permis_requise` est non vide. Sinon → toujours conforme
 * (aucune contrainte, comportement historique préservé).
 *
 * Renvoie `{ ok, code, message }` — `ok=true` + `code=''` quand tout est
 * conforme. Codes d'échec : `permis_manquant`, `permis_expire`,
 * `categorie_inadaptee`. Lecture seule, aucune exception. `today` injectable
 * (défaut : aujourd'hui) pour la testabilité.
 */
export function controlePermis(conducteur, vehicule, today = new Date()) {
  const requise = normaliserCategoriePermis(vehicule?.categorie_permis_requise)
  if (!requise) {
    // Le véhicule n'impose aucune catégorie → rien à contrôler.
    return { ok: true, code: '', message: '' }
  }

  const numero = (conducteur?.numero_permis || '').trim()
  const categorieCond = normaliserCategoriePermis(conducteur?.categorie_permis)

  if (!numero || !categorieCond) {
    return {
      ok: false,
      code: 'permis_manquant',
      message:
        'Le conducteur ne porte pas de permis valide '
        + `(catégorie ${requise} requise par le véhicule).`,
    }
  }

  const expiration = conducteur?.date_expiration
    ? new Date(conducteur.date_expiration)
    : null
  if (expiration && !Number.isNaN(expiration.getTime())) {
    // Comparaison sur jours calendaires (minuit) — un permis expire « à la fin »
    // de sa date, comme le backend (< today).
    const expDay = Date.UTC(
      expiration.getFullYear(), expiration.getMonth(), expiration.getDate())
    const base = today instanceof Date ? today : new Date(today)
    const todayDay = Date.UTC(
      base.getFullYear(), base.getMonth(), base.getDate())
    if (expDay < todayDay) {
      return {
        ok: false,
        code: 'permis_expire',
        message:
          'Le permis du conducteur est expiré '
          + `(expiré le ${conducteur.date_expiration}).`,
      }
    }
  }

  // Catégories portées par le conducteur (« B, CE » → {'B','CE'}).
  const portees = new Set(
    String(conducteur.categorie_permis)
      .replace(/;/g, ',')
      .split(',')
      .map(normaliserCategoriePermis)
      .filter(Boolean),
  )
  if (!portees.has(requise)) {
    return {
      ok: false,
      code: 'categorie_inadaptee',
      message:
        `La catégorie du permis (${categorieCond}) ne couvre pas la `
        + `catégorie requise par le véhicule (${requise}).`,
    }
  }

  return { ok: true, code: '', message: '' }
}

// ── FLOTTE24 — Adaptation des alertes réglementaires au centre d'échéances ──

/**
 * Transforme la liste plate `alertes` (endpoint FLOTTE24) en `items` pour
 * l'`EcheanceCenter` (id/label/date/daysLeft/meta/to). Chaque alerte porte
 * `libelle`, `date_echeance`, `jours_restants`, `actif_label`, `source`, `type`.
 */
export function alertesToEcheanceItems(alertes = []) {
  return alertes.map((a, i) => ({
    id: `${a.source ?? 'x'}-${a.objet_id ?? i}`,
    label: a.libelle || a.type || 'Échéance',
    date: a.date_echeance,
    daysLeft: a.jours_restants,
    meta: a.actif_label || undefined,
  }))
}
