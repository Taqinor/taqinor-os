import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* PACT47 — Import en masse des limites de crédit.

   Les charges utiles ci-dessous ne sont PAS inventées : ce sont les deux
   dictionnaires que `apps/credit/services.importer_limites_csv` renvoie
   réellement (mode aperçu / mode écriture), tels que la vue `importer_limites`
   les retourne sans transformation. `scripts/check_api_shapes.py` compare ce
   mock au dictionnaire lu dans le code serveur : si le serveur change de forme,
   ce test rougit. */

vi.mock('../../api/creditApi', () => ({
  default: { importerLimites: vi.fn() },
}))

import creditApi from '../../api/creditApi'
import ImportLimitesCreditPage from './ImportLimitesCreditPage'

const APERCU = {
  apercu: true,
  ecraser: false,
  total_lignes: 3,
  creations: 1,
  maj: 1,
  erreurs: [
    { ligne: 2, motif: "Client introuvable : 'inconnu@example.com'" },
    { ligne: 3, motif: "Montant invalide : 'abc'" },
  ],
  conflits: [
    {
      ligne: 4,
      client_id: 7,
      client: 'Villa Zenith',
      ecrasements: [
        { champ: 'montant_limite', ancienne: '50000.00', nouvelle: '80000.00' },
      ],
      remplissages: ['mode_hold'],
    },
  ],
}

const RAPPORT = {
  crees: 1,
  maj: 1,
  ecraser: true,
  job_id: 12,
  erreurs: [{ ligne: 2, motif: "Client introuvable : 'inconnu@example.com'" }],
  ecrasements: [
    {
      champ: 'montant_limite', ancienne: '50000.00', nouvelle: '80000.00',
      ecrasement: true, ligne: 4, client_id: 7,
    },
  ],
  refuses: [],
}

const fichierCsv = (nom = 'limites.csv') =>
  new File(['client,montant_limite\n7,80000\n'], nom, { type: 'text/csv' })

afterEach(() => { cleanup(); vi.clearAllMocks() })
beforeEach(() => { vi.clearAllMocks() })

describe('ImportLimitesCreditPage (PACT47)', () => {
  it("l'aperçu montre les erreurs ligne à ligne SANS rien écrire en base", async () => {
    const user = userEvent.setup()
    creditApi.importerLimites.mockResolvedValue({ data: APERCU })
    render(<ImportLimitesCreditPage />)

    await user.upload(screen.getByLabelText('Fichier CSV ou XLSX'), fichierCsv())
    await user.click(screen.getByRole('button', { name: /Aperçu/ }))

    // Rapport ligne à ligne visible…
    expect(await screen.findByTestId('credit-import-apercu')).toBeInTheDocument()
    expect(screen.getByText(/Ligne 2/)).toBeInTheDocument()
    expect(screen.getByText(/Client introuvable/)).toBeInTheDocument()
    expect(screen.getByText(/Montant invalide/)).toBeInTheDocument()
    expect(screen.getByText(/50000.00 → 80000.00/)).toBeInTheDocument()

    // …et AUCUNE écriture : un seul appel, en mode aperçu.
    expect(creditApi.importerLimites).toHaveBeenCalledTimes(1)
    expect(creditApi.importerLimites.mock.calls[0][1]).toEqual({
      apercu: true, ecraser: false,
    })
    expect(screen.queryByTestId('credit-import-rapport')).not.toBeInTheDocument()
  })

  it('confirmer applique EXACTEMENT ce qui a été prévisualisé (même fichier, même option)', async () => {
    const user = userEvent.setup()
    creditApi.importerLimites.mockResolvedValueOnce({ data: APERCU })
    render(<ImportLimitesCreditPage />)

    const fichier = fichierCsv()
    await user.upload(screen.getByLabelText('Fichier CSV ou XLSX'), fichier)
    await user.click(screen.getByLabelText(/Remplacer les valeurs déjà renseignées/))
    await user.click(screen.getByRole('button', { name: /Aperçu/ }))
    expect(await screen.findByTestId('credit-import-apercu')).toBeInTheDocument()

    creditApi.importerLimites.mockResolvedValueOnce({ data: RAPPORT })
    await user.click(screen.getByRole('button', { name: /Confirmer/ }))

    expect(await screen.findByTestId('credit-import-rapport')).toBeInTheDocument()
    expect(creditApi.importerLimites).toHaveBeenCalledTimes(2)
    const [fichierEnvoye, options] = creditApi.importerLimites.mock.calls[1]
    expect(fichierEnvoye.name).toBe(fichier.name)
    expect(options).toEqual({ apercu: false, ecraser: true })
    expect(screen.getByText(/Journal d’import n° 12/)).toBeInTheDocument()
  })

  it('changer le fichier après un aperçu retire la confirmation (on ne confirme jamais un aperçu périmé)', async () => {
    const user = userEvent.setup()
    creditApi.importerLimites.mockResolvedValue({ data: APERCU })
    render(<ImportLimitesCreditPage />)

    await user.upload(screen.getByLabelText('Fichier CSV ou XLSX'), fichierCsv())
    await user.click(screen.getByRole('button', { name: /Aperçu/ }))
    expect(await screen.findByRole('button', { name: /Confirmer/ })).toBeInTheDocument()

    await user.upload(screen.getByLabelText('Fichier CSV ou XLSX'), fichierCsv('autre.csv'))
    expect(screen.queryByRole('button', { name: /Confirmer/ })).not.toBeInTheDocument()
    expect(screen.getByText(/Demandez l’aperçu avant de pouvoir confirmer/)).toBeInTheDocument()
  })
})
