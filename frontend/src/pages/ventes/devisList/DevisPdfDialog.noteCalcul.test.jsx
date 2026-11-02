// AMOT68 (C-AMOT-058) — la note de calcul FDA (AGR319) se demande depuis le
// dialogue PDF d'un devis agricole : case « Joindre la note de calcul », et
// le corps envoyé à `generer-pdf` porte `include_note_calcul`.
// APDF114 — prouvé par le VRAI envoi : la page DevisList pilote la case
// jusqu'au POST reçu par un faux serveur en mémoire (le client `api/axios`
// remplacé), thunk `genererPdfDevis` et `ventesApi.genererPdfDevis` réels.
// Test-du-test : retirer `includeNoteCalcul` de l'objet de `buildPdfOptions`
// (useDevisPdf) ⇒ le faux serveur reçoit `false` et le parcours échoue.
import { describe, it, expect, vi, afterEach } from 'vitest'
import {
  render, screen, within, cleanup, fireEvent, waitFor,
} from '@testing-library/react'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'
import DevisPdfDialog from './DevisPdfDialog.jsx'
import { optionsPdfDepuisModale } from './useDevisPdf.js'

// Faux serveur : `post` enregistre {url, corps} et répond 202 ; `get` répond
// « en_cours » à …/etat-pdf/ et une liste vide ailleurs.
const recus = vi.hoisted(() => [])
vi.mock('../../../api/axios', () => ({
  default: {
    post: vi.fn((url, corps) => { recus.push({ url, corps }); return Promise.resolve({ status: 202, data: {} }) }),
    get: vi.fn((url) => Promise.resolve(/etat-pdf\/$/.test(url)
      ? { data: { statut: 'en_cours', fichier_pdf: false, erreur: null, date: null } }
      : { data: [] })),
  },
}))
// Seul `fetchDevis` est neutralisé : le thunk `genererPdfDevis` reste celui du module.
vi.mock('../../../features/ventes/store/ventesSlice', async (importOriginal) => ({
  ...(await importOriginal()), fetchDevis: vi.fn(() => ({ type: 'ventes/fetchDevis/noop' })),
}))
vi.mock('../../../api/uxviewsApi', async () =>
  (await import('../../../test/mocksVentesEcrans.js')).uxviewsApiVide({ id: 1, ecran: 'ventes.devis' }))

import DevisList from '../DevisList'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'

afterEach(() => { cleanup(); recus.length = 0 })

const AGRICOLE = {
  id: 41, reference: 'DEV-AGR-41', client_nom: 'Ferme', statut: 'brouillon',
  date_creation: '2026-11-01', total_ttc: 60000, nb_options: 1, version: 1,
  mode_installation: 'agricole', lignes: [],
}
const RESIDENTIEL = {
  id: 42, reference: 'DEV-RES-42', client_nom: 'Villa', statut: 'brouillon',
  date_creation: '2026-11-01', total_ttc: 90000, nb_options: 1, version: 1,
  mode_installation: 'residentiel',
  lignes: [{ id: 1, designation: 'Onduleur hybride 5kW', quantite: '1', prix_unitaire: '24000' }],
}

function rendrePage() {
  const store = configureStore({
    reducer: {
      ventes: (state = { devis: [AGRICOLE, RESIDENTIEL], loading: false, error: null }) => state,
      auth: (state = { role: 'admin', role_nom: 'Directeur', permissions: [] }) => state,
    },
  })
  render(
    <Provider store={store}>
      <MemoryRouter initialEntries={['/ventes/devis']}>
        <ThemeProvider><DevisList /></ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

async function ouvrir(reference) {
  const ligne = screen.getByText(reference).closest('tr')
  fireEvent.click(within(ligne).getByTitle('Générer le PDF (choix du format)'))
  return screen.findByRole('dialog')
}

async function generer(dialog, n) {
  fireEvent.click(within(dialog).getByRole('button', { name: /Générer/ }))
  await waitFor(() => expect(recus).toHaveLength(n))
}

function dialogue(props) {
  return render(
    <DevisPdfDialog
      pdfTarget={{ id: 1, reference: 'DEV-AGR-1', mode_installation: 'agricole' }}
      batchPdf={false} selectedIds={[]}
      pdfMode="full" setPdfMode={vi.fn()} pdfModeAutoOnepage={false}
      targetIsAgricole showMonthly setShowMonthly={vi.fn()}
      targetHasEtude={false} targetIsCi={false} targetMode="agricole"
      includeEtude={false} setIncludeEtude={vi.fn()}
      includeCalepinage="auto" setIncludeCalepinage={vi.fn()}
      includeNoteCalcul={false} setIncludeNoteCalcul={vi.fn()}
      devisFinal={false} setDevisFinal={vi.fn()}
      paymentMode="standard" setPaymentMode={vi.fn()}
      customAcompte="" setCustomAcompte={vi.fn()}
      onClose={vi.fn()} onGenererLot={vi.fn()} onGenererUn={vi.fn()}
      {...props}
    />,
  )
}

describe('AMOT68 — note de calcul FDA demandable', () => {
  it('cocher la note de calcul puis Générer : le faux serveur reçoit include_note_calcul=true', async () => {
    rendrePage()
    let dialog = await ouvrir('DEV-AGR-41')
    fireEvent.click(within(dialog).getByRole('checkbox', { name: /note de calcul/i }))
    await generer(dialog, 1)

    // Réouverture : case décochée (option non mémorisée).
    dialog = await ouvrir('DEV-AGR-41')
    expect(within(dialog).getByRole('checkbox', { name: /note de calcul/i })).not.toBeChecked()
    await generer(dialog, 2)

    // Résidentiel : aucune case, aucune clé.
    dialog = await ouvrir('DEV-RES-42')
    expect(within(dialog).queryByRole('checkbox', { name: /note de calcul/i })).toBeNull()
    await generer(dialog, 3)

    expect(recus.map((r) => r.url)).toEqual([
      '/ventes/devis/41/generer-pdf/', '/ventes/devis/41/generer-pdf/', '/ventes/devis/42/generer-pdf/'])
    expect(recus[0].corps.include_note_calcul).toBe(true)
    expect(recus[1].corps.include_note_calcul).toBe(false)
    expect(recus[2].corps).not.toHaveProperty('include_note_calcul')
  })

  it('aucune case hors agricole', () => {
    dialogue({ targetIsAgricole: false, targetMode: 'residentiel' })
    expect(screen.queryByRole('checkbox', { name: /note de calcul/i })).toBeNull()
  })

  it('hors agricole, le corps reste celui d’avant (aucune clé ajoutée)', () => {
    const corps = optionsPdfDepuisModale({
      pdfMode: 'full', showMonthly: true, devisFinal: false, includeEtude: false,
      includeCalepinage: 'auto', includeNoteCalcul: true,
    }, { mode_installation: 'residentiel' })
    expect(corps).not.toHaveProperty('include_note_calcul')
    expect(Object.keys(corps).sort()).toEqual(
      ['devis_final', 'include_calepinage', 'include_etude', 'pdf_mode', 'show_monthly'])
  })
})
