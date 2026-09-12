// NTUX2 — Vues sauvegardées serveur pour un écran donné : combine les vues
// personnelles + partagées d'équipe (apps.uxviews.SavedView, NTUX1) avec une
// préférence personnelle légère en localStorage (le DERNIER choix explicite
// de l'utilisateur sur CET écran). Au chargement, sans préférence
// personnelle, la vue par défaut du RÔLE courant s'applique automatiquement
// — recalculée à chaque changement de rôle (aucune action utilisateur).
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useSelector } from 'react-redux'
import uxviewsApi from '../../api/uxviewsApi'
import rolesApi from '../../api/rolesApi'
// NTUX1 — migration BEST-EFFORT des vues localStorage historiques
// (`hooks/useSavedViews.js`) vers l'API serveur, au premier montage d'un
// écran qui adopte ce hook (jamais bloquant, jamais rejouée après succès).
import { migrateLocalSavedViewsForEcran } from './migrateLocalSavedViews'
// NTUX21 — ordre d'affichage des vues PERSONNELLES (glisser-déposer),
// persisté en localStorage (jamais côté serveur, contrairement aux favoris).
import { applyOrder, readOrder, writeOrder } from './personalViewOrder'

const PREF_PREFIX = 'taqinor.uxviews.pref.'

function prefKey(ecran) {
  return `${PREF_PREFIX}${ecran}`
}

function readPref(ecran) {
  try {
    return localStorage.getItem(prefKey(ecran)) || null
  } catch {
    return null
  }
}

function writePref(ecran, viewId) {
  try {
    if (viewId == null) localStorage.removeItem(prefKey(ecran))
    else localStorage.setItem(prefKey(ecran), String(viewId))
  } catch {
    // localStorage indisponible (SSR/quota) — best-effort, jamais bloquant.
  }
}

/**
 * useServerSavedViews(ecran) — retourne :
 *   views, mine, team, loading, error
 *   defaultRoleView   — vue par défaut du rôle courant (ou null)
 *   activeView        — préférence perso si elle existe encore, sinon defaultRoleView
 *   applyView(view)    — mémorise la préférence perso (view=null → efface, repli sur le défaut de rôle)
 *   refresh()
 *   createView(payload) / renameView(id, nom) / duplicateView(view) / deleteView(id)
 *   setDefaultForMyRole(view) — Directeur/Admin uniquement (403 sinon) : résout l'id du
 *     rôle courant via /roles/ (le frontend ne connaît que `role_nom`, cf. authSlice.js)
 *   reorderMine(orderedIds) — NTUX21 : réordonne « Mes vues » (localStorage, par écran)
 */
export function useServerSavedViews(ecran) {
  const [views, setViews] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [prefId, setPrefId] = useState(() => readPref(ecran))
  // NTUX21 — ordre d'affichage perso (glisser-déposer), localStorage.
  const [ordrePerso, setOrdrePerso] = useState(() => readOrder(ecran))

  const userId = useSelector((s) => s.auth.user?.id)
  const roleNom = useSelector((s) => s.auth.role_nom)

  const refresh = useCallback(() => {
    if (!ecran) return undefined
    setLoading(true)
    setError(null)
    return uxviewsApi.listSavedViews(ecran)
      .then((res) => setViews(Array.isArray(res.data?.results) ? res.data.results : (res.data || [])))
      .catch(() => setError('Impossible de charger les vues.'))
      .finally(() => setLoading(false))
  }, [ecran])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage / au changement de params
  useEffect(() => { refresh() }, [refresh])
  // eslint-disable-next-line react-hooks/set-state-in-effect -- lecture préférence locale au montage / changement d'écran
  useEffect(() => { setPrefId(readPref(ecran)) }, [ecran])
  // eslint-disable-next-line react-hooks/set-state-in-effect -- lecture ordre local au montage / changement d'écran
  useEffect(() => { setOrdrePerso(readOrder(ecran)) }, [ecran])

  // NTUX1 — migration best-effort des vues localStorage historiques de CET
  // écran, une seule fois (drapeau posé par le module) : si des vues ont
  // réellement été migrées, on recharge la liste serveur pour les révéler
  // immédiatement (jamais un rechargement quand il n'y avait rien à migrer).
  useEffect(() => {
    if (!ecran) return
    migrateLocalSavedViewsForEcran(ecran, { create: uxviewsApi.createSavedView })
      .then((res) => { if (res?.migrated) refresh() })
      .catch(() => { /* best-effort — ne bloque jamais l'écran */ })
  }, [ecran, refresh])

  const mineBrutes = useMemo(
    () => views.filter((v) => String(v.owner) === String(userId)), [views, userId])
  // NTUX21 — ordre perso appliqué UNIQUEMENT à « Mes vues » (jamais aux vues
  // d'équipe, dont l'ordre reste celui du serveur — `SavedView.Meta.ordering`).
  const mine = useMemo(
    () => applyOrder(mineBrutes, ordrePerso), [mineBrutes, ordrePerso])
  const team = useMemo(() => views.filter((v) => String(v.owner) !== String(userId)), [views, userId])

  // NTUX21 — glisser-déposer : `orderedIds` = les ids de `mine` dans leur
  // NOUVEL ordre. Persisté en localStorage (jamais côté serveur) et adopté
  // immédiatement (jamais besoin d'un aller-retour réseau).
  const reorderMine = useCallback((orderedIds) => {
    writeOrder(ecran, orderedIds)
    setOrdrePerso(orderedIds)
  }, [ecran])

  // Vue par défaut du RÔLE courant — recalculée à chaque changement de
  // `roleNom` (ex. un changement de rôle réassigné par un admin) : aucune
  // préférence perso ne masque durablement un changement de rôle, sauf si
  // l'utilisateur a lui-même choisi une autre vue (`prefId`).
  const defaultRoleView = useMemo(
    () => views.find((v) => v.est_defaut_role && v.role_nom === roleNom) || null,
    [views, roleNom],
  )

  const activeView = useMemo(() => {
    if (prefId) {
      const found = views.find((v) => String(v.id) === String(prefId))
      if (found) return found
    }
    return defaultRoleView
  }, [prefId, views, defaultRoleView])

  const applyView = useCallback((view) => {
    writePref(ecran, view?.id ?? null)
    setPrefId(view?.id ?? null)
  }, [ecran])

  const createView = useCallback(
    (payload) => uxviewsApi.createSavedView({ ecran, ...payload }).then((res) => { refresh(); return res.data }),
    [ecran, refresh],
  )

  const renameView = useCallback(
    (id, nom) => uxviewsApi.updateSavedView(id, { nom }).then((res) => { refresh(); return res.data }),
    [refresh],
  )

  const duplicateView = useCallback((view) => createView({
    nom: `${view.nom} (copie)`,
    configuration: view.configuration,
    visibilite: 'PERSONNELLE',
  }), [createView])

  const deleteView = useCallback((id) => uxviewsApi.deleteSavedView(id).then(() => {
    if (String(prefId) === String(id)) applyView(null)
    refresh()
  }), [prefId, applyView, refresh])

  const setDefaultForMyRole = useCallback((view) => rolesApi.getRoles().then((res) => {
    const list = Array.isArray(res.data?.results) ? res.data.results : (res.data || [])
    const match = list.find((r) => r.nom === roleNom)
    if (!match) throw new Error('Rôle introuvable.')
    return uxviewsApi.definirParDefautRole(view.id, match.id).then((r) => { refresh(); return r.data })
  }), [roleNom, refresh])

  return {
    views, mine, team, loading, error,
    defaultRoleView, activeView,
    applyView, refresh,
    createView, renameView, duplicateView, deleteView, setDefaultForMyRole,
    reorderMine,
  }
}

export default useServerSavedViews
