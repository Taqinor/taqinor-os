import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* CAD43 — drapeau `samedi_ok` PAR TOUCHE dans l'éditeur de cadences.

   Le samedi est fermé par défaut (jours ouvrés lundi-vendredi) : toute touche
   calculée un samedi est repoussée au lundi 08:30, y compris le message
   d'identité J0. Cocher « Samedi » dans Paramètres → Notifications ouvrirait
   le samedi aux SIX appels d'un coup ; ce drapeau ouvre UNE touche.

   Le mock des lignes est IMPORTÉ du contrat partagé
   (`apps/parametres/contract_samples/cadence_relance_v2.json`), jamais écrit à
   la main : c'est ce fichier commun qui manquait le 03/08/2026, quand l'écran
   mockait l'inverse exact de ce que le serveur renvoyait. */

import CONTRAT from
  '../../../../backend/django_core/apps/parametres/contract_samples/cadence_relance_v2.json'

const LIGNES = CONTRAT.exemple_liste

vi.mock('../../api/parametresApi', () => ({
  default: {
    getMessages: vi.fn(async () => ({ data: [] })),
    getCadenceRelance: vi.fn(async () => ({ data: [] })),
    updateCadenceRelanceEtape: vi.fn(async () => ({ data: {} })),
  },
}))

import parametresApi from '../../api/parametresApi'
import { ThemeProvider } from '../../design/ThemeProvider'
import CadenceRelanceEditor from './CadenceRelanceEditor'

beforeEach(() => {
  parametresApi.getCadenceRelance.mockClear()
  parametresApi.updateCadenceRelanceEtape.mockClear()
  parametresApi.getCadenceRelance.mockImplementation(async (cadence) => ({
    data: cadence === 'contact' ? LIGNES : [],
  }))
})
afterEach(() => cleanup())

function rendre() {
  return render(
    <ThemeProvider><CadenceRelanceEditor /></ThemeProvider>)
}

describe('CAD43 — « Samedi » par touche', () => {
  it('le contrat partagé porte bien le champ samedi_ok', () => {
    expect(CONTRAT.exemple).toHaveProperty('samedi_ok')
    expect(LIGNES.length).toBeGreaterThan(1)
    expect(LIGNES.some(l => l.samedi_ok === true)).toBe(true)
    expect(LIGNES.some(l => l.samedi_ok === false)).toBe(true)
  })

  it('chaque touche a son interrupteur Samedi, reflétant le serveur',
    async () => {
      rendre()
      await waitFor(() => {
        expect(screen.getByLabelText(
          `Autorisée le samedi — étape ${LIGNES[0].ordre}`)).toBeInTheDocument()
      })
      for (const ligne of LIGNES) {
        const bascule = screen.getByLabelText(
          `Autorisée le samedi — étape ${ligne.ordre}`)
        expect(bascule).toHaveAttribute(
          'aria-checked', String(!!ligne.samedi_ok))
      }
    })

  it('cocher « Samedi » n’envoie QUE ce champ au serveur', async () => {
    const user = userEvent.setup()
    rendre()
    const eteinte = LIGNES.find(l => !l.samedi_ok)
    const bascule = await screen.findByLabelText(
      `Autorisée le samedi — étape ${eteinte.ordre}`)

    await user.click(bascule)

    await waitFor(() => {
      expect(parametresApi.updateCadenceRelanceEtape).toHaveBeenCalledWith(
        eteinte.id, { samedi_ok: true })
    })
  })

  it('prévient quand le samedi est ouvert à un APPEL', async () => {
    const user = userEvent.setup()
    rendre()
    const appel = LIGNES.find(l => l.canal === 'appel' && !l.samedi_ok)
    expect(appel).toBeTruthy()

    const bascule = await screen.findByLabelText(
      `Autorisée le samedi — étape ${appel.ordre}`)
    expect(screen.queryByTestId(`cre-samedi-appel-${appel.id}`)).toBeNull()

    await user.click(bascule)

    await waitFor(() => {
      expect(screen.getByTestId(`cre-samedi-appel-${appel.id}`))
        .toBeInTheDocument()
    })
  })

  it('un message silencieux ne déclenche aucun avertissement', async () => {
    const user = userEvent.setup()
    rendre()
    const message = LIGNES.find(
      l => l.canal === 'whatsapp' && l.samedi_ok)
    expect(message).toBeTruthy()
    await screen.findByLabelText(
      `Autorisée le samedi — étape ${message.ordre}`)
    expect(screen.queryByTestId(`cre-samedi-appel-${message.id}`)).toBeNull()
    await user.click(screen.getByLabelText(
      `Autorisée le samedi — étape ${message.ordre}`))
    expect(screen.queryByTestId(`cre-samedi-appel-${message.id}`)).toBeNull()
  })
})
