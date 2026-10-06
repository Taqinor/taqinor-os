import { createElement } from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'
import gedApi from '../../../api/gedApi'
import ApprobationPage from './ApprobationPage.jsx'
import ChecklistPage from './ChecklistPage.jsx'
import CoffresPage from './CoffresPage.jsx'
import CorbeillePage from './CorbeillePage.jsx'
import PlanificationsPage from './PlanificationsPage.jsx'
import ReglesAclPage from './ReglesAclPage.jsx'
import ReglesDossierPage from './ReglesDossierPage.jsx'
import RetentionPage from './RetentionPage.jsx'
import RoutagesPage from './RoutagesPage.jsx'
import TagsPage from './TagsPage.jsx'

/* ADOC31 — chaque écran GED avancé lit TOUTES les pages de sa liste (enveloppe
   DRF réelle {count, next, results}, 50 par page) : jamais la seule page 1.
   L'oracle : la page 2 (page_size 200) est demandée en plus de la page 1. */

const ligne = (i) => ({
  id: i, nom: `Élément ${i}`, libelle: `Élément ${i}`, slug: `e-${i}`,
  description: '', parent: null, source: 'ventes_devis', statut: 'en_attente',
  niveau: 'lecture', actif: true, actions: [], priorite: 0, ordre: 0,
  condition_group: { op: 'and', conditions: [] }, tags_defaut: [],
  document: 1, document_nom: 'D', folder: 1, folder_nom: 'F', echeance: '2026-12-01',
  duree_conservation_jours: 30, action_echeance: 'signaler', criteres: {},
  proprietaire: 2, proprietaire_nom: 'reda', client: null, document_count: 0,
  supprime_le: '2026-06-01T10:00:00Z', supprime_par_nom: 'reda',
  cabinet: 1, cabinet_nom: 'C', cabinet_cible: 1, cabinet_cible_nom: 'C', role: 1, role_nom: 'RH',
  tag: 1, tag_nom: 'T', created_at: '2026-06-01T10:00:00Z', documents: [],
  telechargements: 0, is_accessible: true, approbateurs: [],
})

const paginee = (total = 60) => vi.fn((params = {}) => {
  const page = params.page || 1
  const debut = (page - 1) * 50
  const items = Array.from({ length: total }, (_, k) => ligne(k + 1))
  return Promise.resolve({ data: {
    count: total,
    next: debut + 50 < total ? `?page=${page + 1}` : null,
    results: items.slice(debut, debut + 50),
  } })
})

const vide = () => vi.fn(() => Promise.resolve({ data: [] }))

vi.mock('../../../api/gedApi', () => ({ default: {} }))
vi.mock('../../../api/crmApi', () => ({
  default: { getClients: vi.fn(() => Promise.resolve({ data: [] })) },
}))
vi.mock('../../../api/rolesApi', () => ({
  default: { getRoles: vi.fn(() => Promise.resolve({ data: [] })) },
}))

const LISTES = [
  'getDemandesApprobation', 'getDemandesSignature', 'getModelesDocument',
  'getDocumentsList', 'getRolesSignataire', 'getLotsEnvoi', 'getDossiers',
  'getCabinets', 'getExigences', 'getDemandesDocument', 'getValidationsOcr',
  'getTamponsSociete', 'getCoffres', 'getCorbeille', 'getPlanificationsDocument',
  'getReglesAclMetadonnee', 'getReglesDossier', 'getTags',
  'getPolitiquesRetention', 'getArchivagesLegaux', 'getLegalHolds', 'getPartages',
  'getJournalAcces', 'getDemandesDisposition', 'getRoutagesDocumentaires',
  'getTagAssignments', 'getLiens',
]

beforeEach(() => {
  for (const nom of LISTES) gedApi[nom] = vide()
  gedApi.getUsers = vide()
  gedApi.getDocumentsEchus = vide()
  gedApi.getStampsDisponibles = vi.fn(() => Promise.resolve({ data: [] }))
  gedApi.getAnalytique = vi.fn(() => Promise.resolve({ data: null }))
  gedApi.getTableauBordSignatures = vi.fn(() => Promise.resolve({ data: null }))
  gedApi.getQuotaEtat = vi.fn(() => Promise.resolve({
    data: { usage_octets: 0, quota_octets: 0, restant_octets: 0, depasse: false, illimite: true },
  }))
})

function monter(Ecran) {
  const store = configureStore({ reducer: { auth: () => ({ user: { username: 'reda', role: 'admin' } }) } })
  return render(
    <Provider store={store}>
      <MemoryRouter><ThemeProvider>{createElement(Ecran)}</ThemeProvider></MemoryRouter>
    </Provider>,
  )
}

const CAS = [
  ['ApprobationPage', ApprobationPage, 'getDemandesApprobation'],
  ['ChecklistPage', ChecklistPage, 'getExigences'],
  ['CoffresPage', CoffresPage, 'getCoffres'],
  ['CorbeillePage', CorbeillePage, 'getCorbeille'],
  ['PlanificationsPage', PlanificationsPage, 'getPlanificationsDocument'],
  ['ReglesAclPage', ReglesAclPage, 'getReglesAclMetadonnee'],
  ['ReglesDossierPage', ReglesDossierPage, 'getReglesDossier'],
  ['RetentionPage', RetentionPage, 'getPolitiquesRetention'],
  ['RoutagesPage', RoutagesPage, 'getRoutagesDocumentaires'],
  ['TagsPage', TagsPage, 'getTags'],
]

describe('ADOC31 — écrans GED avancés : toutes les pages', () => {
  it.each(CAS)('%s lit les 60 lignes (deux pages)', async (_nom, Ecran, liste) => {
    gedApi[liste] = paginee(60)
    monter(Ecran)
    await waitFor(() => expect(gedApi[liste]).toHaveBeenCalledWith(
      expect.objectContaining({ page: 2, page_size: 200 })))
    expect(gedApi[liste]).toHaveBeenCalledWith(expect.objectContaining({ page: 1 }))
  })

})
