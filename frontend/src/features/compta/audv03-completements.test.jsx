import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import { exempleContrat } from '../../test/fixtures/contractSamples'

/* ============================================================================
   AUDV03 — deux compléments trésorerie DEVIENNENT visibles à l'écran.
   ----------------------------------------------------------------------------
   * COMPTA4 (DRAFT165-31) — `sequence_piece_journal` calculait le prochain
     numéro de pièce d'un journal sans aucun appelant : l'écran de saisie ne
     pouvait pas annoncer le numéro qui SERA attribué à une OD laissée sans
     référence.
   * XACC15 (DRAFT165-35) — `poster_dotation_etalement` n'avait aucun appelant :
     l'échéancier de dotations était généré puis JAMAIS étalé, la charge
     restant immobilisée au débit de 3491.

   Les charges utiles viennent des exemples COMMITTÉS (PACT10/PACT13), ceux-là
   mêmes que `apps/compta/tests/test_audv03_completements_tresorerie.py`
   affirme contre la vraie réponse des vues — jamais un objet retapé ici.
   ========================================================================== */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

// `vi.hoisted` : la fabrique de `vi.mock` est remontée au-dessus des imports,
// elle ne peut lire AUCUNE variable de module — y compris un simple helper.
const mocks = vi.hoisted(() => ({
  prochainNumero: vi.fn(),
  journaux: vi.fn(),
  comptes: vi.fn(),
  ecrituresList: vi.fn(),
  chargesList: vi.fn(),
  posterDotation: vi.fn(),
  vide: () => Promise.resolve({ data: [] }),
}))

vi.mock('../../api/comptaApi', () => ({
  default: {
    journaux: { list: mocks.journaux },
    comptes: { list: mocks.comptes },
    ecritures: {
      list: mocks.ecrituresList,
      create: mocks.vide,
      valider: mocks.vide,
      extourner: mocks.vide,
      prochainNumero: mocks.prochainNumero,
    },
    chargesAvance: {
      list: mocks.chargesList,
      create: mocks.vide,
      posterDotation: mocks.posterDotation,
    },
  },
}))

function mount(ui) {
  const store = configureStore({
    reducer: { auth: () => ({ role: 'admin', role_nom: null }) },
  })
  return render(
    <Provider store={store}>
      <MemoryRouter>
        <ThemeProvider>{ui}</ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

describe('AUDV03 — aperçu du numéro de pièce d’une OD (COMPTA4)', () => {
  it('annonce le numéro qui SERA attribué dès qu’un journal est choisi', async () => {
    const apercu = exempleContrat('compta', 'ecriture_prochain_numero')
    mocks.journaux.mockResolvedValue({
      data: [{ id: apercu.journal, code: apercu.journal_code,
        libelle: 'Opérations diverses' }],
    })
    mocks.comptes.mockResolvedValue({ data: [] })
    mocks.ecrituresList.mockResolvedValue({ data: [] })
    mocks.prochainNumero.mockResolvedValue({ data: apercu })

    const { default: EcrituresPage } = await import('./pages/EcrituresPage.jsx')
    mount(<EcrituresPage />)

    fireEvent.click(await screen.findByRole('button', { name: /Nouvelle écriture/ }))

    // Le `<Label required>Journal</Label>` de l'éditeur n'est pas relié au
    // `<select>` (ni `htmlFor`, ni `id`) : il n'y a donc PAS de nom
    // accessible à viser. On passe par l'OPTION, qui porte le libellé réel du
    // journal, puis on remonte à son `<select>` — même patron que les autres
    // tests d'écran de ce module.
    const option = await screen.findByRole(
      'option', { name: `${apercu.journal_code} — Opérations diverses` })
    const journal = option.closest('select')
    fireEvent.change(journal, { target: { value: String(apercu.journal) } })

    await waitFor(() => {
      expect(screen.getByText(`Numéro attribué : ${apercu.reference}`))
        .toBeInTheDocument()
    })
    expect(mocks.prochainNumero).toHaveBeenCalledWith(
      { journal: String(apercu.journal) })
  }, 30000)
})

describe('AUDV03 — postage d’une dotation d’étalement (XACC15)', () => {
  const charge = {
    id: 37,
    reference: 'CCA-2026-0037',
    libelle: 'Assurance annuelle',
    montant_total: '12000.00',
    date_debut: '2026-01-01',
    nb_mois: 12,
    dotations: [
      { id: 511, numero: 3, date_dotation: '2026-08-01', montant: '1000.00',
        posted: true },
      { id: 512, numero: 4, date_dotation: '2026-09-01', montant: '1000.00',
        posted: false },
    ],
  }

  it('poste la dotation NON postée et ne propose rien sur celle déjà postée', async () => {
    mocks.chargesList.mockResolvedValue({ data: [charge] })
    mocks.posterDotation.mockResolvedValue({
      data: exempleContrat('compta', 'dotation_etalement_poster'),
    })

    const { default: ChargesAvancePage } = await import(
      './pages/ChargesAvancePage.jsx')
    mount(<ChargesAvancePage />)

    // `ListShell`/`DataTable` rend DEUX fois la même ligne (table desktop +
    // cartes mobile, toutes deux dans le DOM sous jsdom) : viser la <tr>.
    const libelle = (await screen.findAllByText('Assurance annuelle'))
      .find((el) => el.closest('tr'))
    fireEvent.click(libelle.closest('tr'))

    const dialogue = await screen.findByRole('dialog')
    // Une seule dotation est postable : celle qui ne l'est pas encore.
    const boutons = within(dialogue).getAllByRole('button', { name: 'Poster' })
    expect(boutons).toHaveLength(1)

    fireEvent.click(boutons[0])
    await waitFor(() => {
      expect(mocks.posterDotation).toHaveBeenCalledWith(charge.id, 512)
    })
    // Après postage, plus aucun bouton : la dotation a basculé « postée ».
    await waitFor(() => {
      expect(within(dialogue).queryByRole('button', { name: 'Poster' }))
        .not.toBeInTheDocument()
    })
  }, 30000)
})
