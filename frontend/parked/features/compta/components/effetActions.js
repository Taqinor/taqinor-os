/* NTTRE26 — Ce qu'on peut (et ne peut PAS) faire d'un effet, et POURQUOI.
   ----------------------------------------------------------------------------
   L'assistant « Endossement / protêt » présente les deux actions possibles sur
   un effet et grise celle qui est invalide pour son statut courant, EN DISANT
   la raison — plutôt que de laisser l'utilisateur découvrir le refus après
   coup, au retour du serveur.

   Les règles reproduites ici sont EXACTEMENT celles du serveur
   (`apps/compta/services.py` : `endosser_effet` et `constater_protet`) — le
   serveur reste seul juge, l'assistant ne fait que l'annoncer à l'avance. */

/** Statuts depuis lesquels un effet à recevoir peut encore être endossé. */
export const STATUTS_ENDOSSABLES = ['portefeuille', 'remis']

const LIBELLES_STATUT = {
  portefeuille: 'en portefeuille',
  remis: 'remis à l’encaissement',
  encaisse: 'déjà encaissé',
  paye: 'déjà payé',
  impaye: 'impayé',
  escompte: 'remis à l’escompte',
  endosse: 'déjà endossé',
}

function statutLisible(statut) {
  return LIBELLES_STATUT[statut] || statut || 'inconnu'
}

/**
 * Disponibilité des deux actions NTTRE7 pour un effet donné.
 * @param {{sens: string, statut: string, date_protet?: string}} effet
 * @returns {{endosser: {possible: boolean, raison: string},
 *            protet: {possible: boolean, raison: string}}}
 */
export function actionsEffet(effet) {
  const sens = effet?.sens
  const statut = effet?.statut

  let endosser
  if (sens !== 'recevoir') {
    endosser = {
      possible: false,
      raison: 'Seul un effet À RECEVOIR peut être endossé à un tiers.',
    }
  } else if (!STATUTS_ENDOSSABLES.includes(statut)) {
    endosser = {
      possible: false,
      raison: `Cet effet est ${statutLisible(statut)} : l’endossement n’est `
        + 'possible qu’en portefeuille ou remis à l’encaissement.',
    }
  } else {
    endosser = { possible: true, raison: '' }
  }

  let protet
  if (statut !== 'impaye') {
    protet = {
      possible: false,
      raison: `Un protêt ne se constate que sur un effet IMPAYÉ ; celui-ci est `
        + `${statutLisible(statut)}. Constatez d’abord le rejet.`,
    }
  } else if (effet?.date_protet) {
    protet = {
      possible: false,
      raison: 'Un protêt a déjà été constaté sur cet effet.',
    }
  } else {
    protet = { possible: true, raison: '' }
  }

  return { endosser, protet }
}
