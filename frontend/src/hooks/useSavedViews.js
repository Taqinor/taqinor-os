/**
 * FG11 — useSavedViews(key)
 *
 * Hook générique pour les vues enregistrées en localStorage par écran.
 * Extrait et généralise le pattern N79 existant de LeadsPage.jsx.
 *
 * Retourne :
 *   savedViews  — tableau de { name, state } (ordre de création)
 *   saveView    — (name, state) => void  : enregistre l'état courant
 *   deleteView  — (name) => void         : supprime une vue par nom
 *   clearViews  — () => void             : efface toutes les vues
 *
 * @param {string} key  — clé localStorage unique par écran,
 *                        ex. 'taqinor.crm.leads.savedViews'
 */
import { useEffect, useState } from 'react'

function load(key) {
  try {
    const raw = localStorage.getItem(key)
    const parsed = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function persist(key, views) {
  try {
    localStorage.setItem(key, JSON.stringify(views))
  } catch {
    // Quota exceeded ou environnement sans localStorage (SSR/test).
  }
}

export function useSavedViews(key) {
  const [savedViews, setSavedViews] = useState(() => load(key))

  // Synchronise le localStorage dès que les vues changent.
  useEffect(() => {
    persist(key, savedViews)
  }, [key, savedViews])

  // Enregistre (ou remplace) une vue par son nom.
  function saveView(name, state) {
    const trimmed = (name || '').trim()
    if (!trimmed) return
    setSavedViews(prev => {
      const filtered = prev.filter(v => v.name !== trimmed)
      return [...filtered, { name: trimmed, state }]
    })
  }

  // Supprime une vue par son nom.
  function deleteView(name) {
    setSavedViews(prev => prev.filter(v => v.name !== name))
  }

  // Efface toutes les vues sauvegardées.
  function clearViews() {
    setSavedViews([])
  }

  return { savedViews, saveView, deleteView, clearViews }
}
