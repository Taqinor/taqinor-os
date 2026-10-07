import axios from 'axios'
import { originFrom } from '../../api/origin'

/* ASTK219 / ASTK223 / ASTK228 — client PUBLIC du module Stock (pages sans
   session : kiosque de quai, solde du dépositaire, portail fournisseur par
   lien). Instance axios DÉDIÉE, sans cookie (`withCredentials: false`) : un
   visiteur public ne porte jamais la session ERP, et aucun refresh 401 / toast
   global de l'instance interne ne s'applique ici.

   Les routes appelées sont les routes PUBLIQUES `/api/django/public/stock/…`
   (public_urls.py), jamais les doublons authentifiés `/stock/public/…`. */

const publicClient = axios.create({
  baseURL: originFrom(import.meta.env.VITE_API_URL),
  withCredentials: false,
  timeout: 20000,
})

const BASE = '/api/django/public/stock'

const publicStockApi = {
  // ASTK219 — check-in chauffeur (code d'arrivée à 8 caractères, NTWMS8).
  quaiCheckin: (societe, code) =>
    publicClient.post(`${BASE}/quai-checkin/`, { societe, code }),
  // ASTK223 — solde du SEUL dépositaire porteur du jeton (sans prix).
  tiersSolde: (token) => publicClient.get(`${BASE}/tiers/${encodeURIComponent(token)}/solde/`),
  // ASTK228 — portail fournisseur par lien : documents, confirmation d'un BCF,
  // créneaux proposés et réservation.
  portailFournisseur: (token) =>
    publicClient.get(`${BASE}/portail-fournisseur/${encodeURIComponent(token)}/`),
  confirmerBcf: (token, bcfId, corps) =>
    publicClient.post(
      `${BASE}/portail-fournisseur/${encodeURIComponent(token)}/bcf/${bcfId}/confirmer/`, corps),
  creneauxDisponibles: (token, params) =>
    publicClient.get(
      `${BASE}/portail-fournisseur/${encodeURIComponent(token)}/creneaux-disponibles/`, { params }),
  reserverCreneau: (token, corps) =>
    publicClient.post(
      `${BASE}/portail-fournisseur/${encodeURIComponent(token)}/reserver-creneau/`, corps),
}

export default publicStockApi
