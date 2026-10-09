// Doublures partagées des tests de la fiche ticket SAV (TicketDetail) :
// factorisées ici pour ne pas recopier le même bloc de mocks dans chaque test.
// Les `vi.mock(...)` restent dans chaque fichier de test (hissés par vitest) ;
// leurs fabriques importent ce module dynamiquement.
import { vi } from 'vitest'
import { configureStore } from '@reduxjs/toolkit'

const vide = () => vi.fn(() => Promise.resolve({ data: [] }))

// Réponses neutres de savApi pour tout ce que la fiche charge à l'ouverture.
export function savApiMock(surcharges = {}) {
  return {
    default: {
      getTicketHistorique: vide(),
      getTicketPieces: vide(),
      getEquipements: vide(),
      getTicketPiecesUnifiees: vi.fn(() => Promise.resolve({
        data: { lignes: [], sous_totaux: { ajout: 0, retrait: 0, recyclage: 0 } } })),
      getTicketsSimilaires: vi.fn(() => Promise.resolve({ data: { results: [] } })),
      getTriageIa: vi.fn(() => Promise.resolve({ data: { disponible: false } })),
      getPretsEquipement: vide(),
      getReponsesType: vide(),
      getTicketChecklist: vide(),
      getChecklistTemplates: vide(),
      ...surcharges,
    },
  }
}

// ticketsSlice : `updateTicket` devient un thunk factice (sans réseau) dont
// `unwrap()` rend `repondre(args)` (par défaut `{}`).
export function ticketsSliceMock(actual, repondre = () => ({})) {
  return {
    ...actual,
    updateTicket: (args) => {
      const action = { type: 'sav/updateTicket/noop' }
      const valeur = repondre(args)
      action.unwrap = () => Promise.resolve(valeur)
      return action
    },
  }
}

export function axiosMock(get = () => Promise.resolve({ data: [] }), extra = {}) {
  return { default: { get: vi.fn(get), ...extra } }
}

export function installationsApiMock() {
  return { default: { getInterventions: vide() } }
}

export function ticketStore(role, extra = {}) {
  return configureStore({
    reducer: {
      tickets: (state = { items: [] }) => state,
      auth: (state = { role, permissions: [] }) => state,
      ...extra,
    },
  })
}

// Ticket minimal accepté par TicketDetail.
export const TICKET_BASE = {
  id: 1, reference: 'SAV-1', statut: 'en_cours', type: 'correctif',
  priorite: 'normale', sous_garantie: 'non', sous_garantie_effectif: 'non',
  couverture: 'a_determiner', devis_id_ext: null, facture_id_ext: null, instructions: '',
}
