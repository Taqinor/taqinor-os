// ENF22 — helpers extraits de VerdictElectrique.jsx (react-refresh/only-export-components) : le fichier composant n'exporte plus que des composants.

/**
 * Les statuts publiés par `verdict_publiable`, chacun avec SON apparence.
 *
 * `refuse` dit si le statut empêche de publier — c'est la règle du serveur
 * (`verdict_publiable` : zéro bloquant ET zéro `sans_source`), recopiée ici
 * pour EXPLIQUER le booléen, jamais pour le recalculer.
 */
export const STATUTS = {
  bloquant: { libelle: 'Bloquant', ton: 'danger', refuse: true },
  sans_source: { libelle: 'Sans provenance', ton: 'outline', refuse: true },
  alerte: { libelle: 'À surveiller', ton: 'warning', refuse: false },
  non_verifiable: { libelle: 'Non vérifiable', ton: 'info', refuse: false },
  omis: { libelle: 'Non calculé, motivé', ton: 'neutral', refuse: false },
  ok: { libelle: 'Conforme', ton: 'success', refuse: false },
}

/** Le libellé d'un statut — un statut inconnu est NOMMÉ, jamais tu. */
export function libelleStatut(statut) {
  return STATUTS[statut]?.libelle ?? `statut « ${statut} »`
}

/**
 * Le ton du badge. Un statut INCONNU ne prend jamais le ton de `ok` : une
 * valeur que cet écran ne comprend pas ne peut pas se lire comme un succès.
 */
export function tonStatut(statut) {
  return STATUTS[statut]?.ton ?? 'primary'
}

/** Vrai quand CE statut est l'un des deux que le serveur juge refusants. */
export function statutRefuse(statut) {
  return STATUTS[statut]?.refuse === true
}

/**
 * Les domaines, dans l'ordre de lecture, et l'onglet qui en RÉPOND.
 *
 * Les codes sont ceux que produisent les producteurs du verdict :
 * `core/electrique/chaines.py` (`CH_*`), `services/norme.py`,
 * `services/raccordement.py` (`CODE_*`, en minuscules),
 * `services/troncons.py` (`CODE_VERDICT`), `services/terre.py` et la garde de
 * fiche de `services/electrique.py`. Un code inconnu tombe dans `autre` avec
 * son libellé intact : il est AFFICHÉ, jamais avalé.
 */
export const DOMAINES = [
  {
    cle: 'fiches',
    libelle: 'Fiches équipements',
    onglet: 'fiches',
    codes: ['FICHE_INCOMPLETE'],
    prefixes: [],
  },
  {
    cle: 'chaines',
    libelle: 'Chaînes et entrées MPPT',
    onglet: 'affectation',
    codes: [],
    prefixes: ['CH_'],
  },
  {
    cle: 'norme',
    // Réglage SOCIÉTÉ : l'atelier d'un calepinage n'en répond pas, donc
    // aucun bouton — mieux vaut pas de bouton qu'un bouton qui ment.
    libelle: 'Norme électrique',
    onglet: null,
    codes: ['NORME_NON_APPLICABLE'],
    prefixes: [],
  },
  {
    cle: 'raccordement',
    libelle: 'Raccordement réseau',
    onglet: 'raccordement',
    codes: ['RACCORDEMENT_REFUSE', 'puissance_souscrite', 'regime_phases',
      'tension_nominale', 'elevation_tension', 'desequilibre_phases'],
    prefixes: [],
  },
  {
    cle: 'troncons',
    libelle: 'Cheminement et câbles',
    onglet: 'cheminement-cables',
    codes: ['TRONCON_NON_CALCULABLE', 'chute_cumulee_dc', 'chute_cumulee_ac'],
    prefixes: [],
  },
  {
    cle: 'terre',
    // La terre est le troisième côté des tronçons (`LIBELLES_COTE` de
    // `CheminementCables.jsx`) : c'est là qu'elle se lit.
    libelle: 'Mise à la terre',
    onglet: 'cheminement-cables',
    codes: [],
    prefixes: ['TERRE_'],
  },
]

/** Le fourre-tout NOMMÉ des codes que cet écran ne connaît pas encore. */
export const DOMAINE_AUTRE = {
  cle: 'autre',
  libelle: 'Autres contrôles',
  onglet: null,
  codes: [],
  prefixes: [],
}

/** Le domaine d'un code — `DOMAINE_AUTRE` quand aucun ne le revendique. */
export function domaineDuMotif(code) {
  const nom = String(code ?? '')
  for (const domaine of DOMAINES) {
    if (domaine.codes.includes(nom)) return domaine
    if (domaine.prefixes.some((prefixe) => nom.startsWith(prefixe))) {
      return domaine
    }
  }
  return DOMAINE_AUTRE
}

/**
 * Les motifs rangés par domaine : `[{domaine, motifs}]`, dans l'ordre de
 * `DOMAINES` puis `autre`. Un domaine sans motif n'est pas rendu — une section
 * vide se lirait comme « tout va bien ici », ce que personne n'a dit.
 */
export function grouperMotifs(motifs) {
  const liste = Array.isArray(motifs) ? motifs : []
  const groupes = []
  for (const domaine of [...DOMAINES, DOMAINE_AUTRE]) {
    const siens = liste.filter(
      (motif) => domaineDuMotif(motif?.code).cle === domaine.cle)
    if (siens.length > 0) groupes.push({ domaine, motifs: siens })
  }
  return groupes
}

/** Les motifs qui EMPÊCHENT de publier — bloquants et valeurs sans source. */
export function motifsRefusants(motifs) {
  const liste = Array.isArray(motifs) ? motifs : []
  return liste.filter((motif) => statutRefuse(motif?.statut))
}
