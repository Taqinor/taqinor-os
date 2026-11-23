/* ACAL628 — « Contrôle rapide d'une chaîne ». Les réponses viennent des exemples COMMITTÉS
   `calepinage_controle_chaine.json` et `calepinage_entree_electrique.json` ; seule la façade est mockée. */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { exempleContrat } from '../../../test/fixtures/contractSamples'

vi.mock('../../../api/calepinageApi', () => ({
  default: { calepinages: { entreeElectrique: vi.fn(), controleChaine: vi.fn() } },
}))

import calepinageApi from '../../../api/calepinageApi'
import ControleChaine from './ControleChaine'

const BRUTE = exempleContrat('calepinage', 'calepinage_entree_electrique')
// L'échantillon liste aussi des fiches incomplètes (non sélectionnables) : on les complète pour l'essai.
const ENTREE = {
  ...BRUTE,
  candidats: {
    ...BRUTE.candidats,
    onduleurs: BRUTE.candidats.onduleurs.map((c) => ({ ...c, fiche_complete: true, champs_manquants: [] })),
  },
}
const ROUGE = exempleContrat('calepinage', 'calepinage_controle_chaine', 'exemple_rouge')
const CORPS_ROUGE = exempleContrat('calepinage', 'calepinage_controle_chaine', 'exemple_corps_rouge')

const complet = (liste) => liste.find((c) => c.fiche_complete !== false)

const rendre = async () => {
  calepinageApi.calepinages.entreeElectrique.mockResolvedValue({ data: ENTREE })
  render(<MemoryRouter><ControleChaine calepinageId={3} /></MemoryRouter>)
  await screen.findByTestId('acal628-formulaire')
}

const remplir = async (nombre = '22') => {
  await userEvent.selectOptions(document.getElementById('acal628-module_produit'), String(complet(ENTREE.candidats.modules).id))
  await userEvent.selectOptions(document.getElementById('acal628-onduleur_produit'), String(complet(ENTREE.candidats.onduleurs).id))
  await userEvent.type(document.getElementById('acal628-nombre_modules'), nombre)
  await userEvent.type(document.getElementById('acal628-temperature_min_c'), '-5')
  await userEvent.type(document.getElementById('acal628-temperature_max_c'), '70')
}

beforeEach(() => { vi.clearAllMocks(); window.sessionStorage.clear() })
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('ControleChaine (ACAL628)', () => {
  it('22 modules à −5 °C : le bloc rouge nomme la valeur et la borne servies, avec la fenêtre', async () => {
    await rendre()
    calepinageApi.calepinages.controleChaine.mockResolvedValue({ data: ROUGE })
    await remplir('22')
    await userEvent.click(screen.getByTestId('acal628-controler'))

    const titre = await screen.findByTestId('acal628-titre')
    expect(titre).toHaveTextContent('Trop haut : 1 177 V')
    expect(titre).toHaveTextContent('1 000 V')
    expect(screen.getByTestId('acal628-controle-demarrage')).toHaveTextContent('Conforme')
    expect(screen.getByTestId('acal628-controle-mppt_haut')).toHaveTextContent('À surveiller')
    expect(screen.getByTestId('acal628-fenetre')).toHaveTextContent('de 8 à 18 modules par chaîne')
    const [corps] = calepinageApi.calepinages.controleChaine.mock.calls[0]
    expect(corps.nombre_modules).toBe(CORPS_ROUGE.nombre_modules)
    expect(corps.temperature_min_c).toBe(-5)
    expect(corps.temperature_max_c).toBe(70)
  })

  it('ACAL1546 — N et le froid suffisent ; le verdict rouge n’est écrit qu’une fois', async () => {
    await rendre()
    calepinageApi.calepinages.controleChaine.mockResolvedValue({ data: ROUGE })
    await userEvent.selectOptions(document.getElementById('acal628-module_produit'), String(complet(ENTREE.candidats.modules).id))
    await userEvent.selectOptions(document.getElementById('acal628-onduleur_produit'), String(complet(ENTREE.candidats.onduleurs).id))
    await userEvent.type(document.getElementById('acal628-nombre_modules'), '22')
    await userEvent.type(document.getElementById('acal628-temperature_min_c'), '-5')
    await userEvent.click(screen.getByTestId('acal628-controler'))

    const verdict = await screen.findByTestId('acal628-verdict')
    expect(screen.queryByTestId('acal628-erreur-temperature_max_c')).toBeNull()
    const [corps] = calepinageApi.calepinages.controleChaine.mock.calls[0]
    expect(corps).not.toHaveProperty('temperature_max_c')
    expect(screen.getByTestId('acal628-titre')).toHaveTextContent('Trop haut : 1 177 V')
    // Le refus bloquant n'est pas répété en ligne « Ne convient pas ».
    expect(screen.queryByTestId('acal628-controle-voc_froid')).toBeNull()
    expect(verdict.textContent.match(/1\s177\sV/g)).toHaveLength(1)
    expect(verdict).not.toHaveTextContent('Ne convient pas')
    expect(screen.getByTestId('acal628-controle-demarrage')).toHaveTextContent('Conforme')
  })

  it('un champ vide est désigné sous le champ fautif, rien ne part au serveur', async () => {
    await rendre()
    await userEvent.click(screen.getByTestId('acal628-controler'))

    expect(await screen.findByTestId('acal628-erreur-nombre_modules')).toHaveTextContent('Nombre de modules')
    expect(screen.getByTestId('acal628-erreur-module_produit')).toBeInTheDocument()
    expect(calepinageApi.calepinages.controleChaine).not.toHaveBeenCalled()
  })

  it('un refus serveur nommé s’affiche sous son champ', async () => {
    await rendre()
    calepinageApi.calepinages.controleChaine.mockRejectedValue({
      response: { status: 404, data: { onduleur_produit: 'Produit introuvable.' } },
    })
    await remplir('16')
    await userEvent.click(screen.getByTestId('acal628-controler'))

    expect(await screen.findByTestId('acal628-erreur-onduleur_produit')).toHaveTextContent('Produit introuvable.')
    await waitFor(() => expect(screen.queryByTestId('acal628-verdict')).toBeNull())
  })

  it('le dernier essai est gardé en sessionStorage', async () => {
    await rendre()
    calepinageApi.calepinages.controleChaine.mockResolvedValue({ data: ROUGE })
    await remplir('22')
    await userEvent.click(screen.getByTestId('acal628-controler'))
    await screen.findByTestId('acal628-titre')

    expect(JSON.parse(window.sessionStorage.getItem('cal-controle-chaine-dernier')).nombre_modules).toBe('22')
  })
})
