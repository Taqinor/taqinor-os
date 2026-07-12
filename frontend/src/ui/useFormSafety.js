import { useDirtyGuard, confirmLeaveIfDirty } from './useDirtyGuard'
import { isDirty } from './form-utils'
import { useNavigationGuard } from '../hooks/useNavigationGuard'

/**
 * VX170 — useFormSafety(initial, current, onClose, options)
 *
 * LA primitive commune qui rend le mauvais câblage impossible : chaque
 * formulaire du repo réinventait son propre snapshot (`isDirty` maison /
 * `JSON.stringify` diff / `useMemo` custom) et ne branchait qu'1 des 3
 * mécanismes de garde sur 3 — jamais les trois ensemble :
 *   (a) diff générique         — `ui/form-utils.isDirty` (un seul utilitaire).
 *   (b) tab-close               — `useDirtyGuard` (`beforeunload`, + filet
 *                                  WebKit `pagehide`/`visibilitychange` si
 *                                  `persistKey` est fourni — VX170).
 *   (c) fermeture volontaire    — `confirmLeaveIfDirty` déjà enveloppé dans
 *                                  `guardedClose` (✕ / overlay / Annuler).
 *   (d) navigation route-level  — `useNavigationGuard` (VX169, `useBlocker`),
 *                                  actif seulement si `options.routeLevel`.
 *
 * Usage (dialogue) :
 *   const { dirty, guardedClose } = useFormSafety(initial, fields, onClose)
 *   <Dialog onOpenChange={(o) => { if (!o) guardedClose() }}>
 *   <Button onClick={guardedClose}>Annuler</Button>
 *
 * Usage (écran route-level, pas de dialogue à fermer) :
 *   const { dirty } = useFormSafety(initial, form, null, { routeLevel: true })
 *
 * @param {object} initial            — snapshot de référence (pris UNE fois,
 *                                       typiquement via `useRef(initial)`).
 * @param {object} current            — état courant du formulaire.
 * @param {Function|null|undefined} onClose — appelé si l'utilisateur confirme
 *                                       vouloir quitter (fermeture volontaire).
 * @param {object} [options]
 * @param {string} [options.message]  — message de confirmation (FR par défaut).
 * @param {string} [options.persistKey] — clé `localStorage` (via `lib/safeStorage`)
 *                                       pour le brouillon défensif WebKit
 *                                       `pagehide` — omis = pas de persistance.
 * @param {boolean} [options.routeLevel=false] — monte aussi la garde de
 *                                       navigation IN-APP (`useNavigationGuard`).
 * @returns {{ dirty: boolean, guardedClose: () => void, snapshot: object }}
 */
export function useFormSafety(initial, current, onClose, options = {}) {
  const { message, persistKey, routeLevel = false } = options

  const dirty = isDirty(initial, current)

  useDirtyGuard(
    dirty,
    message,
    persistKey ? { key: persistKey, getData: () => current } : undefined,
  )

  // VX169 — garde route-level optionnelle (no-op hors routeur data — cf.
  // hooks/useNavigationGuard.js).
  useNavigationGuard(routeLevel ? dirty : false, message)

  const guardedClose = () => {
    if (confirmLeaveIfDirty(dirty, message)) onClose?.()
  }

  return { dirty, guardedClose, snapshot: current }
}

export default useFormSafety
