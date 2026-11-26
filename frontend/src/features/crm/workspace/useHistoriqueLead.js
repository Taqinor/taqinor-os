import { useCallback, useEffect, useRef, useState } from 'react'
import api from '../../../api/axios'
import useVisibilityAwarePolling from '../../../hooks/useVisibilityAwarePolling'
import { ecouterNotificationsRecues, lienDuLead } from '../../../lib/evenementsNotification'

// Historique du lead (fondateur, prod : « i dont see this ») — l'historique d'une fiche OUVERTE est RELU, il n'est plus figé
// à l'ouverture. Rien ici ne touche au brouillon, au composer, à la liste défilante ni au démontage de l'onglet : seul le
// tableau `historique` est remplacé, et seulement s'il a CHANGÉ. Une lecture en échec ne vide jamais ce qui est à l'écran.
//  • à l'ouverture d'un lead : une lecture fraîche (`chatter_recent` n'est que le premier rendu) ;
//  • au retour au premier plan (fenêtre ou onglet) ;
//  • à intervalle calme, onglet visible — la MÊME cadence et le MÊME mécanisme que le sondage de la cloche (30 s,
//    `useVisibilityAwarePolling`) ;
//  • tout de suite quand une notification NON LUE de CE lead arrive (canal `evenementsNotification`, émis par la cloche).
// Une seule lecture en vol par lead ; une relecture demandée par une action de l'utilisateur pendant ce vol est rejouée
// une fois derrière lui (elle ne peut pas être perdue). Une réponse pour un lead qui n'est plus ouvert est jetée.
export const HISTORIQUE_INTERVALLE_MS = 30 * 1000

export default function useHistoriqueLead(leadId, mode) {
  const [lu, setLu] = useState({ pour: null, entrees: [] })
  const idRef = useRef(leadId)
  const enVol = useRef(new Map())
  const lireRef = useRef(null)
  useEffect(() => { idRef.current = leadId })

  const lire = useCallback((id, rejouable) => {
    if (!id) return
    const vol = enVol.current.get(id)
    if (vol) { if (rejouable) vol.rejouer = true; return }
    const etat = { rejouer: false }
    enVol.current.set(id, etat)
    api.get(`/crm/leads/${id}/historique/`)
      .then((r) => {
        if (idRef.current !== id || !Array.isArray(r?.data)) return
        const signature = JSON.stringify(r.data)
        setLu((prev) => (prev.pour === id && JSON.stringify(prev.entrees) === signature
          ? prev : { pour: id, entrees: r.data }))
      })
      .catch(() => {})
      .finally(() => {
        enVol.current.delete(id)
        if (etat.rejouer && idRef.current === id) lireRef.current?.(id, false)
      })
  }, [])
  useEffect(() => { lireRef.current = lire }, [lire])

  // Après une action de l'utilisateur (note, appel, autosave, épingle) : jamais perdue.
  const refreshHistorique = useCallback(() => lire(idRef.current, true), [lire])
  // Lecture passive (ouverture, retour au premier plan, intervalle, notification) : ignorée si une lecture est en vol.
  const relirePassif = useCallback(() => lire(idRef.current, false), [lire])

  const actif = mode === 'edit' && !!leadId
  useEffect(() => { if (actif) lire(leadId, false) }, [actif, leadId, lire])
  useVisibilityAwarePolling([{ fn: relirePassif, intervalMs: HISTORIQUE_INTERVALLE_MS }], { enabled: actif })
  useEffect(() => {
    if (!actif) return undefined
    const auRetour = () => { if (document.visibilityState !== 'hidden') relirePassif() }
    window.addEventListener('focus', auRetour)
    const retirer = ecouterNotificationsRecues((liens) => {
      if (liens.some((l) => lienDuLead(l, leadId))) lire(leadId, true)
    })
    return () => { window.removeEventListener('focus', auRetour); retirer() }
  }, [actif, leadId, lire, relirePassif])

  return { historique: lu.pour === leadId ? lu.entrees : [], refreshHistorique }
}
