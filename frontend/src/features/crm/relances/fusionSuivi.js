/* SUIVI-RELOAD (02/11/2026) — la fusion des touches rendues par le serveur
   dans la liste DÉJÀ affichée du « Suivi des relances ». Module PUR (aucun
   React, aucun appel réseau), même esprit que `refusGeste.js` : la règle est
   écrite UNE fois et se teste sans dérouler un écran.
   ----------------------------------------------------------------------------
   POURQUOI. Incident de production du 02/11/2026 : la commerciale ouvrait
   WhatsApp depuis une touche, revenait cocher « Fait », et recevait un
   « problème de connexion » puis un écran sans aucune suite — elle se
   déconnectait et se reconnectait pour retrouver sa file. Relevé dans les
   journaux du serveur : CHAQUE geste (l'ouverture de WhatsApp comprise)
   relisait la période ENTIÈRE de l'onglet — jusqu'à 62 jours, ~1,5 Mo — et
   cette relecture dépassait le délai d'attente du navigateur (20 s,
   `api/axios.js`) pendant que les ouvriers du serveur redémarraient.

   Désormais l'écran FUSIONNE : la touche vient de la réponse de son propre
   geste, ses sœurs de la relecture du SEUL lead (`?lead=`, quelques Ko), et
   la période n'est relue qu'au changement d'onglet/responsable (ou sur
   « Réessayer »). */

/** « En retard » = à faire ET `overdue` servi (jours ouvrés, absences :
 *  `controle_suivi.etape_en_retard`, ALEA32) — ACVI72 : aucune seconde
 *  définition à l'écran, pour les cases à cocher comme pour les compteurs. */
export function estEnRetard(etape) {
  return etape.statut === 'a_faire' && etape.overdue === true
}

/** Le tri de LECTURE du serveur (`cadence_selectors.relance_etapes_periode` :
 *  `due_date`, puis `due_at` croissant NULLS LAST, puis `ordre`), rejoué à
 *  l'identique : une touche fusionnée se range à SA place dans sa journée, et
 *  jamais en fin de groupe (l'écran groupe par `due_date`). */
export function comparerLignes(a, b) {
  if (a.due_date !== b.due_date) return a.due_date < b.due_date ? -1 : 1
  if (a.due_at !== b.due_at) {
    if (!a.due_at) return 1
    if (!b.due_at) return -1
    return a.due_at < b.due_at ? -1 : 1
  }
  return (a.ordre ?? 0) - (b.ordre ?? 0)
}

/** Les compteurs de `resume` auxquels une ligne appartient. « En retard » est
 *  un SOUS-ENSEMBLE de « à faire » (contrat), jamais un cinquième statut :
 *  une touche ouverte et échue compte dans les deux. */
function seauxResume(etape, today) {
  const seaux = [etape.statut]
  if (estEnRetard(etape, today)) seaux.push('en_retard')
  return seaux
}

/** Fusionne dans la liste déjà servie les lignes que le serveur vient de
 *  rendre, et renvoie les nouvelles `donnees` (jamais mutées).
 *
 *  `idsRemplaces` = les lignes de la liste que ces lignes remplacent : l'id de
 *  la touche pour la réponse d'un geste, tous les ids du lead pour une
 *  relecture de lead (le moteur a pu annuler ses touches sœurs, en faire
 *  naître une, ou les décaler toutes — l'action `reporter` décale les
 *  suivantes du même delta). Une ligne remplacée et non re-servie quitte la
 *  liste.
 *
 *  Les compteurs restent CEUX DU SERVEUR : on leur applique le seul DELTA des
 *  lignes qui changent de seau — jamais un recomptage depuis `results`, qui
 *  est filtré par l'écran (onglet + cases à cocher) et ne porte donc pas la
 *  période entière. `bornes` est la fenêtre SERVEUR de l'onglet courant,
 *  celle-là même que `resume` compte : une touche reportée au-delà quitte la
 *  liste ET les compteurs, exactement comme à la prochaine relecture. */
export function fusionnerLignes(donnees, idsRemplaces, servies, bornes, today) {
  if (!donnees || !Array.isArray(donnees.results)) return donnees
  const dansFenetre = (e) => Boolean(e?.due_date)
    && e.due_date >= bornes.date_debut && e.due_date <= bornes.date_fin
  const ajoutees = (Array.isArray(servies) ? servies : [])
    .filter((e) => e?.id != null && dansFenetre(e))
  // Une ligne re-servie est remplacée même si l'appelant ne l'a pas listée :
  // jamais de doublon d'id dans la liste fusionnée.
  const idsServies = new Set(ajoutees.map((e) => e.id))
  const remplacee = (e) => idsRemplaces.has(e.id) || idsServies.has(e.id)
  const results = [...donnees.results.filter((e) => !remplacee(e)), ...ajoutees]
    .sort(comparerLignes)
  const resume = { ...(donnees.resume || {}) }
  const bouger = (lignes, signe) => lignes.forEach(
    (e) => seauxResume(e, today).forEach((cle) => {
      if (typeof resume[cle] === 'number') {
        resume[cle] = Math.max(0, resume[cle] + signe)
      }
    }))
  bouger(donnees.results.filter((e) => remplacee(e) && dansFenetre(e)), -1)
  bouger(ajoutees, 1)
  return { ...donnees, count: results.length, resume, results }
}
