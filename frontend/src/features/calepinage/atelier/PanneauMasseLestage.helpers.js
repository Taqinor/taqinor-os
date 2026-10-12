// ENF22 — helpers extraits de PanneauMasseLestage.jsx (react-refresh/only-export-components) : le fichier composant n'exporte plus que des composants.

/** La clé du paramètre société qui porterait le nombre de points de fixation.
    Elle n'est servie par AUCUN réglage à ce jour : c'est précisément ce que la
    ligne correspondante dit, en la nommant. */
export const CLE_POINTS_FIXATION = 'points_fixation_par_module'

/** Le code de la ligne de feuille dont la charge par point est déduite. */
const CODE_EFFORT = 'effort_soulevement_module'

/** Les entrées qui viennent du CALEPINAGE (jamais des réglages société) :
    libellé français et provenance, telles que `services/lestage.py` les lit
    (fiche produit, CAL164). Aucun chiffre ici — seulement d'où il vient. */
const ENTREES_DU_CALEPINAGE = {
  surface_module_m2: {
    libelle: 'Surface d’un module posé',
    provenance: 'fiche produit (cotes de pose)',
  },
  masse_module_kg: {
    libelle: 'Masse d’un module posé',
    provenance: 'fiche produit (poids)',
  },
  masse_resistante_kg: {
    libelle: 'Masse résistante (module + structure)',
    provenance: 'fiche produit (poids) + masse de structure saisie',
  },
}

/**
 * CALX17 — la PROVENANCE d'une entrée de ligne : la source SAISIE quand le
 * serveur la publie, la fiche produit quand l'entrée vient du calepinage, et
 * « non saisi » sinon. Jamais une provenance devinée.
 */
export function provenanceEntree(cle, parametres) {
  const saisi = (Array.isArray(parametres) ? parametres : [])
    .find((parametre) => parametre?.cle === cle)
  if (saisi) {
    return {
      libelle: saisi.libelle || cle,
      valeur: saisi.valeur,
      unite: saisi.unite || '',
      provenance: saisi.source,
    }
  }
  const connue = ENTREES_DU_CALEPINAGE[cle]
  if (connue) {
    return { libelle: connue.libelle, valeur: null, unite: '', provenance: connue.provenance }
  }
  return { libelle: cle, valeur: null, unite: '', provenance: null }
}

/**
 * CALX17 — la CHARGE PAR POINT DE FIXATION : l'effort de soulèvement d'un
 * module divisé par le nombre de points qui le tiennent.
 *
 * Elle n'est publiée que si les DEUX nombres sont servis. Le nombre de points
 * par module n'appartient à aucun réglage servi aujourd'hui : la ligne est
 * donc omise, en NOMMANT le champ attendu (`points_fixation_par_module`).
 * Une valeur par défaut (« 4 points, comme d'habitude ») produirait une charge
 * de fixation fausse sur une toiture réelle.
 */
export function chargeParPointDeFixation(donnees) {
  const lestage = donnees?.lestage ?? {}
  const parametres = Array.isArray(lestage.parametres) ? lestage.parametres : []
  const lignes = Array.isArray(lestage.lignes) ? lestage.lignes : []

  const points = parametres.find((parametre) => parametre?.cle === CLE_POINTS_FIXATION)
  const nombreDePoints = Number(points?.valeur)
  const effort = lignes.find((ligne) => ligne?.code === CODE_EFFORT)
  const effortValeur = effort?.valeur

  const manquants = []
  if (!points || !Number.isFinite(nombreDePoints) || nombreDePoints <= 0) {
    manquants.push(CLE_POINTS_FIXATION)
  }
  if (effortValeur === null || effortValeur === undefined) manquants.push(CODE_EFFORT)

  const commun = {
    libelle: 'Charge par point de fixation',
    unite: 'N',
    formule: 'F_point = F_soulèvement ÷ n_points',
    entrees: [CODE_EFFORT, CLE_POINTS_FIXATION],
  }
  if (manquants.length) {
    const noms = manquants.includes(CLE_POINTS_FIXATION)
      ? `« ${CLE_POINTS_FIXATION} » (nombre de points de fixation par module, non servi par les réglages de lestage)`
      : `« ${CODE_EFFORT} » (l’effort de soulèvement n’est pas calculé)`
    return {
      ...commun,
      valeur: null,
      manquants,
      mention: `Charge par point de fixation non publiée — champ manquant : ${noms}.`,
    }
  }
  return {
    ...commun,
    valeur: Number(effortValeur) / nombreDePoints,
    manquants: [],
    mention: '',
    provenance: points.source,
  }
}
