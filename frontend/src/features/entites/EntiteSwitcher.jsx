import { useEffect, useState } from 'react'
import { Network } from 'lucide-react'
import entitesApi from './entitesApi'
import { poserEntiteActive, useEntiteActive } from '../../lib/entiteActive'

/**
 * NTADM26 — Bascule d'ENTITÉ active dans l'en-tête.
 *
 * Confort d'affichage, JAMAIS une frontière de sécurité : choisir une filiale
 * n'ouvre ni ne ferme aucun droit — elle pose seulement le paramètre `?entite=`
 * de NTADM2 sur les listes (intercepteur axios), et le serveur refait son
 * propre scoping à chaque requête (société + périmètre de rôle NTADM3).
 *
 * Ne s'affiche QUE si l'utilisateur a accès à DEUX entités ou plus — mono-
 * entité (et donc toutes les sociétés d'aujourd'hui) ne voit rien : l'en-tête
 * est strictement inchangé.
 *
 * Le changement est instantané et SANS rechargement : `poserEntiteActive`
 * diffuse un événement window, le routeur remonte l'écran courant sur cette
 * clé et les listes se refont avec le nouveau paramètre.
 */
export default function EntiteSwitcher() {
  const [entites, setEntites] = useState([])
  const active = useEntiteActive()

  useEffect(() => {
    let vivant = true
    entitesApi.mesEntites()
      .then((res) => {
        if (vivant) setEntites(Array.isArray(res.data) ? res.data : [])
      })
      // Silencieux : un compte sans accès au référentiel (ou un portail
      // externe) n'a simplement pas de bascule — jamais un toast d'erreur
      // sur chaque chargement de page.
      .catch(() => { if (vivant) setEntites([]) })
    return () => { vivant = false }
  }, [])

  if (entites.length < 2) return null

  // Une entité devenue inaccessible (périmètre modifié) ne doit pas rester
  // sélectionnée en silence : on retombe sur « Toutes les entités ».
  const valeur = entites.some((e) => e.id === active) ? String(active) : ''

  return (
    <label className="header-company-switcher" title="Entité affichée">
      <Network size={15} aria-hidden="true" />
      <select
        aria-label="Changer d'entité affichée"
        data-testid="entite-switcher"
        value={valeur}
        onChange={(e) => poserEntiteActive(e.target.value)}
      >
        <option value="">Toutes les entités</option>
        {entites.map((e) => (
          <option key={e.id} value={e.id}>{e.nom}</option>
        ))}
      </select>
    </label>
  )
}
