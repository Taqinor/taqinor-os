// LB3 — sentinelle d'interception « Signé » (blueprint I3, bug recon2-03 #2).
//
// Passer un lead à l'étape SIGNED n'est jamais un simple PATCH : ça ouvre
// SigneDialog (choix du devis accepté + option). `onInlineSave(lead, 'stage',
// SIGNED)` (LeadsPage.jsx) ouvre le dialogue puis REJETTE avec cette
// sentinelle au lieu de résoudre — avant ce fix, un faux `Promise.resolve()`
// laissait `useOptimisticSave` croire le commit réussi (étape optimiste
// 'SIGNED' + libellé « Enregistré » figés) alors que rien n'était enregistré
// tant que le dialogue n'était pas confirmé.
//
// Le rejet est le signal HONNÊTE : useOptimisticSave/InlineEdit font leur
// rollback normal (l'affichage revient à l'étape réelle) — le SEUL cas
// spécial vit dans l'`onError` de StageMover (KanbanView.jsx), qui avale la
// sentinelle sans toaster (les vraies erreurs réseau toastent toujours).
export const SIGNE_INTERCEPT = Symbol('SIGNE_INTERCEPT')

export function isSigneIntercept(err) {
  return err === SIGNE_INTERCEPT
}

export default SIGNE_INTERCEPT
