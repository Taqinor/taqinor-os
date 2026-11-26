/* ACAL935 — LA source unique des mots et du ton de l'état du dossier
   électrique (`etat` ∈ pret | a_completer | bloquant, `points` : le nombre de
   points concernés, servis par `etat_dossier_electrique.py`, ACAL934).

   Le cadre de génération du devis et le résumé de l'affectation des chaînes
   lisent CE module : aucun autre fichier n'écrit « Prêt », « À compléter » ni
   « Bloquant ». Mots alignés sur `maquettes/Electrique.dc.html`. */

const ETATS = {
  pret: { ton: 'success' },
  a_completer: { ton: 'warning' },
  bloquant: { ton: 'danger' },
}

function nombrePoints(points) {
  const n = Number(points)
  return Number.isFinite(n) && n >= 0 ? n : 0
}

/** `{libelle, ton}` d'un état servi, ou `null` quand l'état n'est pas connu
    (jamais un mot deviné). */
export function libelleEtat(etat, points) {
  return libelleDe(etat, points)
}

/** ACAL1535 — l'état à afficher pour une proposition : l'état à chaud du verdict, SAUF quand il dit « prêt » et que
    le dossier enregistré (`publication`, servi par `evaluer-electrique` sans corps) reste « à compléter » : le
    résumé ne contredit alors pas le dossier. `null` quand aucun des deux états n'est lu. */
export function etatAffiche(verdict, publication) {
  if (verdict?.etat === 'pret' && publication?.etat === 'a_completer') {
    return libelleDe(publication.etat, publication.points)
  }
  return libelleDe(verdict?.etat, verdict?.points)
}

function libelleDe(etat, points) {
  if (!ETATS[etat]) return null
  const n = nombrePoints(points)
  const libelles = {
    pret: 'Prêt',
    a_completer: `À compléter : ${n} point${n > 1 ? 's' : ''}`,
    // R6-N3 — un nombre de POINTS DU DOSSIER (motifs de son verdict), à ne pas lire comme un compte de contrôles de la liste.
    bloquant: `Bloquant : ${n} point${n > 1 ? 's' : ''} du dossier`,
  }
  return { libelle: libelles[etat], ton: ETATS[etat].ton }
}
