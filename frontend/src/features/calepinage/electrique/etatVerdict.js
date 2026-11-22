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
  if (!ETATS[etat]) return null
  const n = nombrePoints(points)
  const libelles = {
    pret: 'Prêt',
    a_completer: `À compléter : ${n} point${n > 1 ? 's' : ''}`,
    bloquant: `Bloquant : ${n}`,
  }
  return { libelle: libelles[etat], ton: ETATS[etat].ton }
}
