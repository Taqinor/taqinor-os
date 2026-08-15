import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import rhApi from '../../api/rhApi'
import Hse from './Hse.jsx'

/* UX27 — HSE RH (registres). WIR36 — les boutons « Déclarer un accident » /
   « Signaler un presqu'accident » / « Nouvelle causerie » câblent les
   wrappers d'écriture ajoutés à `rhApi.js` (ViewSets full CRUD jusqu'ici
   sans appelant côté écriture). */

vi.mock('../../api/qhseApi', () => ({
  default: { causerieSecuritePdf: vi.fn() },
}))

vi.mock('../../api/rhApi', () => {
  const empty = () => Promise.resolve({ data: [] })
  return {
    default: {
      getAccidentsTravail: vi.fn(empty),
      getPresquAccidents: vi.fn(empty),
      getCauseriesSecurite: vi.fn(empty),
      getAnalysesRisques: vi.fn(empty),
      getEmployes: vi.fn(() => Promise.resolve({ data: [{ id: 9, nom: 'Bennani', prenom: 'Youssef' }] })),
      validerAnalyseRisques: vi.fn(),
      createAccidentTravail: vi.fn(),
      createPresquAccident: vi.fn(),
      createCauserieSecurite: vi.fn(),
      // WIR239 — émargement d'une causerie + export CNSS des accidents.
      emargerCauserie: vi.fn(),
      exportCnssAccidents: vi.fn(),
    },
  }
})

function renderHse() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <Hse />
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('Hse — déclarations manuelles (WIR36)', () => {
  beforeEach(() => vi.clearAllMocks())

  it('rend le module HSE', async () => {
    renderHse()
    expect(await screen.findByText('HSE — Hygiène, sécurité & environnement')).toBeInTheDocument()
  })

  it('déclare un accident via rhApi.createAccidentTravail', async () => {
    rhApi.createAccidentTravail.mockResolvedValueOnce({ data: { id: 1 } })
    renderHse()
    await screen.findByText('HSE — Hygiène, sécurité & environnement')

    fireEvent.click(await screen.findByRole('button', { name: /Déclarer un accident/ }))
    fireEvent.change(screen.getByLabelText('Employé blessé'), { target: { value: '9' } })
    fireEvent.change(screen.getByLabelText('Date de l’accident'), { target: { value: '2026-08-01' } })
    fireEvent.click(screen.getByRole('button', { name: 'Déclarer l’accident' }))

    await waitFor(() => expect(rhApi.createAccidentTravail).toHaveBeenCalledWith(
      expect.objectContaining({ employe: '9', date_accident: '2026-08-01' }),
    ))
  })

  it('signale un presqu’accident via rhApi.createPresquAccident', async () => {
    rhApi.createPresquAccident.mockResolvedValueOnce({ data: { id: 1 } })
    renderHse()
    await screen.findByText('HSE — Hygiène, sécurité & environnement')
    fireEvent.click(screen.getByRole('radio', { name: 'Presqu’accidents' }))

    fireEvent.click(await screen.findByRole('button', { name: /Signaler un presqu’accident/ }))
    fireEvent.change(screen.getByLabelText('Date du constat'), { target: { value: '2026-08-01' } })
    fireEvent.click(screen.getByRole('button', { name: 'Signaler' }))

    await waitFor(() => expect(rhApi.createPresquAccident).toHaveBeenCalledWith(
      expect.objectContaining({ date_constat: '2026-08-01' }),
    ))
  })

  it('crée une causerie via rhApi.createCauserieSecurite', async () => {
    rhApi.createCauserieSecurite.mockResolvedValueOnce({ data: { id: 1 } })
    renderHse()
    await screen.findByText('HSE — Hygiène, sécurité & environnement')
    fireEvent.click(screen.getByRole('radio', { name: 'Causeries' }))

    fireEvent.click(await screen.findByRole('button', { name: /Nouvelle causerie/ }))
    fireEvent.change(screen.getByLabelText('Thème'), { target: { value: 'Port des EPI' } })
    fireEvent.change(screen.getByLabelText('Date'), { target: { value: '2026-08-01' } })
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))

    await waitFor(() => expect(rhApi.createCauserieSecurite).toHaveBeenCalledWith(
      expect.objectContaining({ theme: 'Port des EPI', date_causerie: '2026-08-01' }),
    ))
  })
})

/* WIR239 — deux @actions serveur sans consommateur : l'émargement d'une
   causerie (la feuille de présence restait vierge) et l'export CSV de
   déclaration CNSS des accidents du travail (le document exigé après un
   accident du travail). */
describe('Hse — WIR239 : émargement causerie & export CNSS', () => {
  beforeEach(() => vi.clearAllMocks())

  it('émarge un participant via rhApi.emargerCauserie', async () => {
    rhApi.getCauseriesSecurite.mockResolvedValue({
      data: [{
        id: 12, theme: 'Port des EPI', date_causerie: '2026-08-01',
        animateur: 9, animateur_nom: 'Bennani Youssef', lieu: 'Atelier',
        participants: [{
          id: 1, participant: 9, participant_nom: 'Bennani Youssef',
          present: true, emarge: false,
        }],
      }],
    })
    rhApi.emargerCauserie.mockResolvedValueOnce({ data: { id: 1, emarge: true } })
    renderHse()
    await screen.findByText('HSE — Hygiène, sécurité & environnement')
    fireEvent.click(screen.getByRole('radio', { name: 'Causeries' }))

    // Action de ligne « Émarger » → dialogue listant les participants.
    fireEvent.click((await screen.findAllByRole('button', { name: 'Émarger' }))[0])
    const boutons = await screen.findAllByRole('button', { name: 'Émarger' })
    fireEvent.click(boutons[boutons.length - 1])

    await waitFor(() => expect(rhApi.emargerCauserie).toHaveBeenCalledWith(
      12, { participant: 9 },
    ))
    expect((await screen.findAllByText('Émargé'))[0]).toBeInTheDocument()
  })

  it('télécharge l’export CNSS via rhApi.exportCnssAccidents', async () => {
    globalThis.URL.createObjectURL = vi.fn(() => 'blob:cnss')
    globalThis.URL.revokeObjectURL = vi.fn()
    rhApi.exportCnssAccidents.mockResolvedValueOnce({ data: new Blob(['x']) })
    renderHse()
    await screen.findByText('HSE — Hygiène, sécurité & environnement')

    fireEvent.click((await screen.findAllByRole('button', { name: /Export CNSS/ }))[0])
    await waitFor(() => expect(rhApi.exportCnssAccidents).toHaveBeenCalled())
  })
})
