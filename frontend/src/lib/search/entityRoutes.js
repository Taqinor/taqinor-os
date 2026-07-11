// VX13 — Source UNIQUE pour la recherche transverse d'entités, consommée
// IDENTIQUEMENT par GlobalSearch.jsx (barre du haut) et
// providers/CommandPalette.jsx (⌘K) : avant cette tâche, chacun dupliquait sa
// propre table `ROUTE`/`LIST_ROUTE`/`TYPE_LABEL` (~150 lignes chacun, DÉJÀ
// divergentes — `bon_commande`/`contrat`/`dossier` connus d'un seul côté,
// `produit` de l'autre). Un seul endroit pour ajouter un type d'entité.
//
// `ROUTE`/`LIST_ROUTE`/`TYPE_LABEL` sont l'UNION des deux tables d'origine
// (repli inchangé : un type absent d'une table avant cette fusion reste
// simplement sans route/libellé, comme avant — aucun comportement nouveau).
import { useEffect, useMemo, useState } from 'react'
import reportingApi from '../../api/reportingApi'

// Route d'ouverture par type d'entité (cf. router/index.jsx).
export const ROUTE = {
  lead: (id) => `/crm/leads?lead=${id}`,
  client: () => '/crm',
  devis: () => '/ventes/devis',
  facture: () => '/ventes/factures',
  chantier: () => '/chantiers',
  equipement: () => '/equipements',
  ticket: () => '/sav',
  bon_commande: () => '/ventes/bons-commande',
  contrat: () => '/sav/contrats',
  dossier: () => '/chantiers',
  produit: () => '/stock',
}

// Route de LISTE par type, filtrée par la requête (lien « voir tout »). On reste
// sur la route d'ouverture du type quand aucune liste filtrable n'existe.
export const LIST_ROUTE = {
  lead: (q) => `/crm/leads?q=${encodeURIComponent(q)}`,
  client: (q) => `/crm?q=${encodeURIComponent(q)}`,
  devis: (q) => `/ventes/devis?q=${encodeURIComponent(q)}`,
  facture: (q) => `/ventes/factures?q=${encodeURIComponent(q)}`,
  chantier: (q) => `/chantiers?q=${encodeURIComponent(q)}`,
  equipement: (q) => `/equipements?q=${encodeURIComponent(q)}`,
  ticket: (q) => `/sav?q=${encodeURIComponent(q)}`,
  bon_commande: (q) => `/ventes/bons-commande?q=${encodeURIComponent(q)}`,
  contrat: (q) => `/sav/contrats?q=${encodeURIComponent(q)}`,
}

// Libellé de groupe par type d'entité (utilisé par CommandPalette pour les
// « Récents » — GlobalSearch reçoit déjà `g.label` du serveur).
export const TYPE_LABEL = {
  lead: 'Lead',
  client: 'Client',
  devis: 'Devis',
  facture: 'Facture',
  chantier: 'Chantier',
  equipement: 'Équipement',
  ticket: 'SAV',
  produit: 'Produit',
}

/**
 * useEntitySearch — recherche transverse débouncée (~250 ms), même patron que
 * l'un et l'autre composant AVANT cette tâche : `term.length < 2` = pas de
 * requête (réponse immédiate, groupes vidés) ; sinon débounce 250 ms puis
 * `/reporting/search`. `enabled` (défaut true) permet à CommandPalette de ne
 * chercher QUE quand la palette est ouverte (comportement d'origine préservé).
 *
 * Renvoie `{ groups, loading, failed }` — chaque appelant garde SA propre
 * gestion des états dérivés (activeIndex, open, active…), donc aucun
 * comportement observable ne change (byte-identique aux tests existants).
 */
export function useEntitySearch(term, { enabled = true } = {}) {
  const [groups, setGroups] = useState([])
  const [loading, setLoading] = useState(false)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    if (!enabled) return undefined
    if (term.length < 2) {
      setGroups([])
      setLoading(false)
      setFailed(false)
      return undefined
    }
    setLoading(true)
    setFailed(false)
    const t = setTimeout(() => {
      reportingApi.search(term)
        .then((r) => { setGroups(r.data?.groups ?? []); setFailed(false) })
        .catch(() => { setGroups([]); setFailed(true) })
        .finally(() => setLoading(false))
    }, 250)
    return () => clearTimeout(t)
  }, [term, enabled])

  return useMemo(() => ({ groups, loading, failed }), [groups, loading, failed])
}
