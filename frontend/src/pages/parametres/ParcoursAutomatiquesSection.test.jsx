import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider, useDispatch, useSelector } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

/* AMET17 — section « Parcours automatiques ». Charge utile = l'exemple
   COMMITTÉ du contrat AMET16 (`apps/parametres/contract_samples/
   drapeaux_parcours.json`), jamais une liste retapée à la main. */
import { exempleContrat } from '../../test/fixtures/contractSamples'
import parametresReducer from '../../features/parametres/store/parametresSlice'
import parametresApi from '../../api/parametresApi'
import ParcoursAutomatiquesSection from './ParcoursAutomatiquesSection'

vi.mock('../../api/parametresApi', () => ({
  default: { updateProfile: vi.fn() },
}))

const CONTRAT = exempleContrat('parametres', 'drapeaux_parcours')
const DRAPEAUX = CONTRAT.drapeaux_parcours

function Harnais({ lectureSeule = false }) {
  const dispatch = useDispatch()
  const profile = useSelector((s) => s.parametres.profile)
  return (
    <ParcoursAutomatiquesSection
      profile={profile} dispatch={dispatch} lectureSeule={lectureSeule} />
  )
}

function rendre(options) {
  const store = configureStore({
    reducer: { parametres: parametresReducer },
    preloadedState: {
      parametres: {
        profile: { drapeaux_parcours: DRAPEAUX }, loading: false,
        saving: false, uploading: false, error: null, saveSuccess: false,
      },
    },
  })
  return render(<Provider store={store}><Harnais {...options} /></Provider>)
}

describe('AMET17 — ParcoursAutomatiquesSection', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks() })

  it('rend les 8 drapeaux du contrat et envoie le PATCH', async () => {
    const attendu = DRAPEAUX.find((d) => d.cle === 'devis_auto_depuis_tunnel')
    parametresApi.updateProfile.mockResolvedValue({
      data: {
        drapeaux_parcours: DRAPEAUX.map((d) => (
          d.cle === attendu.cle ? { ...d, valeur: !d.valeur } : d)),
      },
    })
    rendre()
    expect(DRAPEAUX).toHaveLength(8)
    for (const d of DRAPEAUX) {
      expect(screen.getByTestId(`drapeau-${d.cle}`)).toHaveTextContent(d.libelle)
      expect(screen.getByTestId(`drapeau-${d.cle}`)).toHaveTextContent(d.effet)
      expect(screen.getByTestId(`drapeau-${d.cle}`)).toHaveTextContent(d.parcours)
    }
    const bascule = screen.getByRole('switch', { name: attendu.libelle })
    expect(bascule).toHaveAttribute('aria-checked', String(attendu.valeur))

    await userEvent.click(bascule)

    await waitFor(() => expect(parametresApi.updateProfile)
      .toHaveBeenCalledWith({ [attendu.cle]: !attendu.valeur }))
    // La valeur affichée est celle RELUE du serveur (réponse du PATCH).
    await waitFor(() => expect(
      screen.getByRole('switch', { name: attendu.libelle }),
    ).toHaveAttribute('aria-checked', String(!attendu.valeur)))
  })

  it('lecture seule : les bascules sont inertes', async () => {
    rendre({ lectureSeule: true })
    for (const d of DRAPEAUX) {
      expect(screen.getByRole('switch', { name: d.libelle })).toBeDisabled()
    }
    expect(screen.getByTestId('parcours-automatiques'))
      .toHaveTextContent(/Lecture seule/)
    expect(parametresApi.updateProfile).not.toHaveBeenCalled()
  })
})
