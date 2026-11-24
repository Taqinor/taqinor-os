// T4-B4-010 — la DERNIÈRE lecture de « Prêt à envoyer ? » par calepinage, rangée par étape : le rail des étapes la lit
// pour dire « N à régler » sur la MÊME liste que la colonne (plus de tuile « fait » quand la liste a des points à
// régler dans cette étape). Aucun appel réseau ici : PretAEnvoyer publie ce qu'il a lu ; sans lecture, `null`.
import { useSyncExternalStore } from 'react'
import { groupeDuControle } from './PretAEnvoyer.helpers'

const lectures = new Map() // id → { [etape]: nombre de contrôles à régler ou bloquants }
const abonnes = new Set()

/** Publie une lecture servie : `filtre` null = toutes les étapes ; sinon seule l'étape filtrée est remplacée. */
export function publierLecturePret(calepinageId, filtre, controles) {
  if (calepinageId == null || !Array.isArray(controles)) return
  const cle = String(calepinageId)
  const comptes = {}
  for (const c of controles) {
    const etape = groupeDuControle(c)
    if (filtre && etape !== filtre) continue
    comptes[etape] = (comptes[etape] ?? 0) + (c.etat === 'a_regler' || c.etat === 'bloquant' ? 1 : 0)
  }
  if (filtre) comptes[filtre] = comptes[filtre] ?? 0
  const avant = lectures.get(cle)
  const apres = filtre ? { ...(avant ?? {}), ...comptes } : comptes
  if (avant && JSON.stringify(avant) === JSON.stringify(apres)) return
  lectures.set(cle, apres)
  abonnes.forEach((f) => f())
}

const abonner = (f) => { abonnes.add(f); return () => abonnes.delete(f) }

/** `{ toit: 2, panneaux: 0, … }` (étapes lues seulement) ou `null` tant que la liste n'a pas été lue. */
export function useAReglerPret(calepinageId) {
  const cle = calepinageId == null ? null : String(calepinageId)
  return useSyncExternalStore(abonner, () => (cle ? lectures.get(cle) ?? null : null), () => null)
}
