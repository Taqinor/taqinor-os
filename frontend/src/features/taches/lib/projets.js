/* ============================================================================
   TCH89-TCH90 — Calculs PURS de l'écran « Un projet » (aucun rendu, aucune horloge : le jour est un argument).
   Tout vient de `projet_vue.json` ; rien n'est inventé ici : un compte absent du serveur reste absent.
   ========================================================================== */

/** Les trois vues d'un projet, dans l'ordre du sélecteur (`affichage.vue` : textes.md §2.6 « Vues »). */
export const VUES_PROJET = [['liste', 'Liste'], ['tableau', 'Tableau'], ['chronologie', 'Chronologie']]
export const CODES_VUES = VUES_PROJET.map(([code]) => code)

/** « {faites} sur {total} » d'une étape — seulement si le serveur le sert (`sections[].compteurs`,
 * `sans_section_compteurs` : { ouvertes, faites }, comme `projet.compteurs`), jamais recompté ici. */
export function compteEtape(compteurs) {
  const { faites, ouvertes } = compteurs ?? {}
  const total = Number.isInteger(compteurs?.total) ? compteurs.total : (Number.isInteger(ouvertes) && Number.isInteger(faites) ? ouvertes + faites : null)
  return Number.isInteger(faites) && Number.isInteger(total) && total > 0 ? `${faites} sur ${total}` : ''
}

const iso = (valeur) => (typeof valeur === 'string' && valeur ? valeur.slice(0, 10) : null)

/** Toutes les tâches chargées d'une vue : les étapes, puis « Sans étape ». */
export const toutesLesTaches = (vue) => [...(vue.sections ?? []).flatMap((s) => s.taches ?? []), ...(vue.sans_section ?? [])]

/** « {faites} sur {total} faites » d'une étape entièrement faite, sinon « {faites} sur {total} » ; rien sans compte servi. */
function detailEtape(compteurs) {
  const { faites, ouvertes } = compteurs ?? {}
  if (!Number.isInteger(faites) || !Number.isInteger(ouvertes) || faites + ouvertes === 0) return { texte: '', faite: false }
  const faite = ouvertes === 0
  return { texte: `${faites} sur ${faites + ouvertes}${faite ? ' faites' : ''}`, faite }
}

/**
 * Les éléments de la chronologie : étapes (`etape`), jalons (`jalon`), aujourd'hui (`auj`), échéance du projet
 * (`fin`) — ordonnés par date ; une étape sans date se range au jour même (« Sans date »). `sansDate` : les
 * tâches ouvertes qui n'ont ni jour prévu ni échéance.
 */
export function elementsChronologie(vue, aujourdhui) {
  const elements = []
  for (const s of vue.sections ?? []) {
    const debut = iso(s.date_debut)
    const fin = iso(s.date_fin)
    const { texte, faite } = detailEtape(s.compteurs)
    elements.push({ type: 'etape', id: `e${s.id}`, nom: s.nom, debut, fin, detail: texte, faite, date: debut ?? fin })
  }
  const sansDate = []
  for (const t of toutesLesTaches(vue)) {
    const jour = iso(t.echeance) ?? iso(t.jour_prevu)
    if (t.jalon && jour) elements.push({ type: 'jalon', id: `j${t.id}`, nom: t.titre, date: jour, detail: 'Jalon' })
    if (!iso(t.echeance) && !iso(t.jour_prevu) && !t.jalon) sansDate.push(t)
  }
  elements.push({ type: 'auj', id: 'auj', date: aujourdhui })
  if (iso(vue.projet?.echeance)) elements.push({ type: 'fin', id: 'fin', nom: 'Échéance du projet', date: iso(vue.projet.echeance) })
  const ordre = { etape: 0, jalon: 1, auj: 2, fin: 3 }
  const cle = (e) => e.date ?? aujourdhui
  elements.sort((a, b) => (cle(a) < cle(b) ? -1 : cle(a) > cle(b) ? 1 : ordre[a.type] - ordre[b.type]))
  return { elements, sansDate }
}
