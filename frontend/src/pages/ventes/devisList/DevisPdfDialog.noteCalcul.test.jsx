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
// T4-U1-009 — le profil société servi par GET /parametres/ (posé par test ; `null` = la route rend une liste vide).
const profilServi = vi.hoisted(() => ({ courant: null }))
vi.mock('../../../api/axios', () => ({
  default: {
    post: vi.fn((url, corps) => { recus.push({ url, corps }); return Promise.resolve({ status: 202, data: {} }) }),
    get: vi.fn((url) => Promise.resolve(/etat-pdf\/$/.test(url)
      ? { data: { statut: 'en_cours', fichier_pdf: false, erreur: null, date: null } }
      : url === '/parametres/' && profilServi.courant ? { data: profilServi.courant } : { data: [] })),
  },
}))
// Seul `fetchDevis` est neutralisé : le thunk `genererPdfDevis` reste celui du module.
vi.mock('../../../features/ventes/store/ventesSlice', async (importOriginal) =>
  (await import('../../../test/mocksVentesEcrans.js')).ventesSliceSansFetch(await importOriginal()))
vi.mock('../../../api/uxviewsApi', async () =>
  (await import('../../../test/mocksVentesEcrans.js')).uxviewsApiVide({ id: 1, ecran: 'ventes.devis' }))

import DevisList from '../DevisList'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'

afterEach(() => { cleanup(); recus.length = 0; profilServi.courant = null })

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

const ETAT_INITIAL = {
  ventes: { devis: [AGRICOLE, RESIDENTIEL], loading: false, error: null },
  auth: { role: 'admin', role_nom: 'Directeur', permissions: [] },
}

function rendrePage() {
  const reducer = Object.fromEntries(
    Object.entries(ETAT_INITIAL).map(([cle, initial]) => [cle, (s = initial) => s]))
  render(
    <Provider store={configureStore({ reducer })}>
      <MemoryRouter initialEntries={['/ventes/devis']}><ThemeProvider><DevisList /></ThemeProvider></MemoryRouter>
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

  it('Devis final : l’indice dépend du marché', async () => {
    const { unmount } = dialogue({ targetIsAgricole: false, targetIsCi: true, targetMode: 'industriel' })
    expect(screen.getByText('(visite faite — retire la mention « Devis préliminaire »)')).toBeInTheDocument()
    unmount()
    const r2 = dialogue({ targetIsAgricole: true, targetMode: 'agricole' })
    expect(screen.getByText('(visite faite — retire « à confirmer par la visite »)')).toBeInTheDocument()
    r2.unmount()
    profilServi.courant = { nom: 'TAQINOR Démo', ice: '001', rib: '007 780 0001234567890123 45', banque: 'Banque X' }
    dialogue({ targetIsAgricole: false, targetMode: 'residentiel' })
    expect(await screen.findByText('(ajoute modalités de paiement + RIB)')).toBeInTheDocument()
  })

  // T4-U1-009 (rejeu du 26/11) — la fenêtre tout juste ouverte, ou une lecture du profil en échec : rien ne
  // promet le RIB (avant, l'intitulé disait « + RIB » tant que la réponse n'était pas arrivée).
  it('T4-U1-009 — profil pas encore lu ou illisible : l’intitulé ne promet pas le RIB', async () => {
    profilServi.courant = { nom: 'TAQINOR Démo', ice: '001', rib: '007 780 0001234567890123 45', banque: 'Banque X' }
    const r = dialogue({ targetIsAgricole: false, targetMode: 'residentiel' })
    expect(screen.getByText('(ajoute modalités de paiement)')).toBeInTheDocument()
    expect(await screen.findByText('(ajoute modalités de paiement + RIB)')).toBeInTheDocument()
    r.unmount()
    profilServi.courant = null // la route rend une liste : pas un profil
    dialogue({ targetIsAgricole: false, targetMode: 'residentiel' })
    await new Promise((fin) => { setTimeout(fin, 0) }) // la réponse est arrivée
    expect(screen.queryByText('(ajoute modalités de paiement + RIB)')).toBeNull()
    expect(screen.getByText('(ajoute modalités de paiement)')).toBeInTheDocument()
  })

  // T4-U1-009 (revue) — la une page n'imprime ni échéancier ni RIB (`legacy_onepage` : « Devis final » n'y retire
  // que « Devis préliminaire » du C&I) ; un lot ne promet que ce qui vaut pour chacun de ses devis.
  it('T4-U1-009 — une page et lot : l’indice ne promet jamais un RIB ou un échéancier non imprimé', async () => {
    const UNE_PAGE = '(le format une page n’imprime ni échéancier ni RIB)'
    profilServi.courant = { nom: 'TAQINOR Démo', ice: '001', rib: '007 780 0001234567890123 45', banque: 'Banque X' }
    for (const props of [{ targetIsAgricole: false, targetMode: 'residentiel' },
      { targetIsAgricole: true, targetMode: 'agricole' }]) {
      const r = dialogue({ ...props, pdfMode: 'onepage' })
      await new Promise((fin) => { setTimeout(fin, 0) }) // le profil (avec RIB) est lu
      expect(screen.getByText(UNE_PAGE)).toBeInTheDocument()
      expect(screen.queryByText(/\+ RIB|modalités de paiement/)).toBeNull()
      r.unmount()
    }
    const ci = dialogue({ targetIsAgricole: false, targetIsCi: true, targetMode: 'commercial', pdfMode: 'onepage' })
    expect(screen.getByText('(visite faite — retire la mention « Devis préliminaire »)')).toBeInTheDocument()
    ci.unmount()
    const lot = { pdfTarget: null, batchPdf: true, selectedIds: [1, 2], targetIsAgricole: false, targetMode: 'residentiel' }
    const r1 = dialogue(lot)
    expect(await screen.findByText('(selon le devis : modalités de paiement, RIB s’il est au profil société)'))
      .toBeInTheDocument()
    expect(screen.queryByText(/\+ RIB/)).toBeNull()
    r1.unmount()
    profilServi.courant = { nom: 'TAQINOR Démo', ice: '001', rib: '', banque: '' }
    const r2 = dialogue(lot)
    expect(await screen.findByText('(selon le devis : modalités de paiement)')).toBeInTheDocument()
    r2.unmount()
    dialogue({ ...lot, pdfMode: 'onepage' })
    expect(screen.getByText(UNE_PAGE)).toBeInTheDocument()
  })

  it('T4-U3-009 — seules les options qui agissent sur le document du marché sont proposées', () => {
    // Agricole : le document de 3 pages n'a ni page calepinage ni page étude.
    const r1 = dialogue({ targetIsAgricole: true, targetMode: 'agricole' })
    expect(screen.queryByTestId('cal184-calepinage')).toBeNull()
    expect(screen.queryByText(/Inclure l.étude/)).toBeNull()
    r1.unmount()
    // Commercial / industriel : étude intégrée (pas de case), calepinage proposé.
    const r2 = dialogue({ targetIsAgricole: false, targetIsCi: true, targetMode: 'commercial' })
    expect(screen.getByTestId('cal184-calepinage')).toBeInTheDocument()
    expect(screen.queryByText(/Inclure l.étude/)).toBeNull()
    r2.unmount()
    // Résidentiel : les deux, et l'étude dit ce qu'elle ajoute (plus « devis industriel »).
    dialogue({ targetIsAgricole: false, targetMode: 'residentiel', targetHasEtude: true })
    expect(screen.getByTestId('cal184-calepinage')).toBeInTheDocument()
    expect(screen.getByText(/Inclure l.étude/).textContent).not.toMatch(/industriel/)
  })

  // T4-V1-004 — « graphique mensuel page 2 » : le graphique est en page 1 du résidentiel ; aucune page promise.
  // T4-V2-017 — « Inclure l'étude » sans étude chiffrée rendait 3 pages, autre mise en page, sans un mot : la
  // condition est dite AVANT de générer.
  it('T4-V1-004 / T4-V2-017 — les légendes disent ce que l’option fait, sans page inventée', () => {
    dialogue({ targetIsAgricole: false, targetMode: 'residentiel', targetHasEtude: true })
    const mensuel = screen.getByText(/Économies mensuelles/).textContent
    expect(mensuel).not.toMatch(/page/)
    expect(mensuel).toMatch(/graphique de la facture mois par mois/)
    expect(screen.getByTestId('pdf-etude-condition')).toHaveTextContent(
      'La page d’étude n’est ajoutée que si le devis porte une étude chiffrée (production, consommation, économies) ; sinon le PDF garde ses 3 pages.')
  })

  // T4-U1-009 — « Devis final (paiement + RIB) » : société identifiée SANS RIB ni banque (identite.ligne_rib rend "")
  // → l'avertissement INTERNE le dit avant de générer ; le PDF, lui, n'est pas touché.
  it('T4-U1-009 — Devis final coché, profil société sans RIB : avertissement interne avec le chemin', async () => {
    profilServi.courant = { nom: 'TAQINOR Démo', ice: '001', rib: '', banque: '' }
    dialogue({ targetIsAgricole: false, targetMode: 'residentiel', devisFinal: true })
    expect(await screen.findByTestId('pdf-rib-manquant')).toHaveTextContent(
      'RIB non renseigné dans le profil de la société : le devis final sortira sans RIB — Paramètres → Société')
  })

  // T4-X7-020 — l'intitulé de la case ne promet pas un RIB que le profil n'a pas, même avant de cocher.
  it('T4-X7-020 — profil sans RIB : l’intitulé ne dit plus « + RIB » ; avec un RIB il le dit', async () => {
    profilServi.courant = { nom: 'TAQINOR Démo', ice: '001', rib: '', banque: '' }
    const r = dialogue({ targetIsAgricole: false, targetMode: 'residentiel' })
    expect(await screen.findByText('(ajoute modalités de paiement)')).toBeInTheDocument()
    r.unmount()
    profilServi.courant = { nom: 'TAQINOR Démo', ice: '001', rib: '007 780 0001234567890123 45', banque: 'Banque X' }
    dialogue({ targetIsAgricole: false, targetMode: 'residentiel' })
    expect(await screen.findByText('(ajoute modalités de paiement + RIB)')).toBeInTheDocument()
  })

  it('T4-U1-009 — RIB renseigné, ou devis final non coché : aucun avertissement', async () => {
    profilServi.courant = { nom: 'TAQINOR Démo', rib: '007 780 0001234567890123 45', banque: 'Banque X' }
    const r = dialogue({ targetIsAgricole: false, targetMode: 'residentiel', devisFinal: true })
    await waitFor(() => expect(screen.queryByTestId('pdf-rib-manquant')).toBeNull())
    r.unmount()
    profilServi.courant = { nom: 'TAQINOR Démo', rib: '', banque: '' }
    dialogue({ targetIsAgricole: false, targetMode: 'residentiel', devisFinal: false })
    expect(screen.queryByTestId('pdf-rib-manquant')).toBeNull()
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
