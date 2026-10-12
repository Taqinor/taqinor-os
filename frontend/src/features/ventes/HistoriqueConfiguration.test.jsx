// QJR553 (D-QJR5-7, contrat QJR513 `devis_historique_configuration.json`) —
// l'historique des versions dans l'Édition complète : diff lisible
// (« Prix unitaire : 100 → 120 »), jamais de prix d'achat ni de marge, et
// « Revenir à cette version » qui recharge l'écran puis passe par
// l'enregistrement NORMAL (replace-lines avec les lignes de l'instantané).
// Les instantanés partent de l'exemple COMMITTÉ du contrat (PACT10).
//
// Run : npx vitest run src/features/ventes/HistoriqueConfiguration.test.jsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { exempleContrat } from '../../test/fixtures/contractSamples'

vi.mock('../../api/crmApi', async () => (await import('../../test/mocksApiDevis.js')).crmApiAvecLead())
vi.mock('../../api/stockApi', async () => (await import('../../test/mocksApiDevis.js')).stockApiMock())
vi.mock('../../api/parametresApi', async () => (await import('../../test/mocksApiDevis.js')).parametresApiMock())
vi.mock('../../api/ventesApi', async () => (await import('../../test/mocksApiDevis.js')).ventesApiEdition({
    getHistoriqueConfigurationDevis: vi.fn(() => Promise.resolve({ data: { snapshots: [] } })),
}))

import crmApi from '../../api/crmApi'
import stockApi from '../../api/stockApi'
import ventesApi from '../../api/ventesApi'
import DevisGenerator from '../../pages/ventes/DevisGenerator'
import { bancEdition } from '../../pages/ventes/devisGenerator.testHelpers.jsx'
import HistoriqueConfiguration from './HistoriqueConfiguration'


const SNAP = exempleContrat('ventes', 'devis_historique_configuration').snapshots[0]
const V1 = {
  ...SNAP, id: 90, date: '2026-09-29T08:00:00+00:00',
  contenu: { ...SNAP.contenu, lignes: SNAP.contenu.lignes.map(l => ({ ...l, prix_unitaire: '100.00', lot: null })) },
}
const V2 = {
  ...SNAP, id: 91,
  contenu: { ...SNAP.contenu, lignes: SNAP.contenu.lignes.map(l => ({ ...l, prix_unitaire: '120.00' })) },
}
const DIFF = {
  ...exempleContrat('ventes', 'devis_historique_configuration', 'exemple_avec_diff').diff,
  modifiees: [{ cle: 'role:panneau', designation: 'Panneau Canadien Solar 710W',
                champs: { prix_unitaire: ['100.00', '120.00'], prix_achat: ['50', '60'] } }],
  parametres: { marge_pct: ['10', '12'] },
}

const { renderEdition, devisRouvert } = bancEdition({ DevisGenerator, stockApi, crmApi, ventesApi })

describe('QJR553 — historique des versions', () => {
  it('diff lisible « Prix unitaire : 100 → 120 », jamais prix d’achat ni marge', async () => {
    ventesApi.getHistoriqueConfigurationDevis.mockImplementation((id, params) => Promise.resolve({
      data: params ? { snapshots: [V1, V2], diff: DIFF } : { snapshots: [V1, V2] },
    }))
    render(<HistoriqueConfiguration devisId={12} peutRevenir onRevenir={vi.fn()} />)
    await userEvent.click(await screen.findByRole('button', { name: /Voir les différences/ }))
    expect(ventesApi.getHistoriqueConfigurationDevis).toHaveBeenLastCalledWith(12, { a: 90, b: 91 })
    const diff = await screen.findByTestId('historique-diff')
    expect(diff.textContent).toMatch(/Prix unitaire : 100 → 120/)
    expect(diff.textContent).toMatch(/Ajoutée : Batterie Dyness 10 kWh/)
    expect(document.body.textContent).not.toMatch(/prix_achat|Prix d.achat|marge/i)
  })

  it('ADEV36 — un échéancier se lit « Acompte 40 % · Solde 60 % → Acompte 30 % · Solde 70 % »', async () => {
    const tr = (a, s) => [
      { libelle: 'Acompte', type: 'acompte', pct_or_montant: a },
      { libelle: 'Solde', type: 'solde', pct_or_montant: s },
    ]
    const diffEch = { ajoutees: [], retirees: [], modifiees: [], parametres: {
      echeancier: [tr(40, 60), tr(30, 70)],
    } }
    ventesApi.getHistoriqueConfigurationDevis.mockImplementation((id, params) => Promise.resolve({
      data: params ? { snapshots: [V1, V2], diff: diffEch } : { snapshots: [V1, V2] },
    }))
    render(<HistoriqueConfiguration devisId={12} peutRevenir onRevenir={vi.fn()} />)
    await userEvent.click(await screen.findByRole('button', { name: /Voir les différences/ }))
    const diff = await screen.findByTestId('historique-diff')
    expect(diff.textContent).toMatch(/Échéancier : Acompte 40 % · Solde 60 % → Acompte 30 % · Solde 70 %/)
    expect(diff.textContent).not.toMatch(/modifié/)
  })

  it('ADEV36 — un échéancier vide s’affiche « — »', async () => {
    const diffVide = { ajoutees: [], retirees: [], modifiees: [], parametres: {
      echeancier: [[], [{ libelle: 'Solde', type: 'solde', pct_or_montant: 100 }]],
    } }
    ventesApi.getHistoriqueConfigurationDevis.mockImplementation((id, params) => Promise.resolve({
      data: params ? { snapshots: [V1, V2], diff: diffVide } : { snapshots: [V1, V2] },
    }))
    render(<HistoriqueConfiguration devisId={12} peutRevenir onRevenir={vi.fn()} />)
    await userEvent.click(await screen.findByRole('button', { name: /Voir les différences/ }))
    const diff = await screen.findByTestId('historique-diff')
    expect(diff.textContent).toMatch(/Échéancier : — → Solde 100 %/)
  })

  it('pas de « Revenir » quand le devis n’est pas modifiable', async () => {
    ventesApi.getHistoriqueConfigurationDevis.mockResolvedValue({ data: { snapshots: [V1, V2] } })
    render(<HistoriqueConfiguration devisId={12} peutRevenir={false} onRevenir={vi.fn()} />)
    await screen.findByTestId('historique-configuration')
    expect(screen.queryByRole('button', { name: /Revenir à cette version/ })).toBeNull()
  })

  it('« Revenir » recharge l’écran puis enregistre par replace-lines les lignes de l’instantané', async () => {
    const rouvert = devisRouvert('exemple_brouillon')
    ventesApi.getDevisById.mockResolvedValue(rouvert)
    ventesApi.getHistoriqueConfigurationDevis.mockResolvedValue({ data: { snapshots: [V1, V2] } })
    renderEdition(rouvert.data.id)
    await waitFor(() => expect(crmApi.getLead).toHaveBeenCalledWith(77))
    const appelsChargeur = ventesApi.getDevisById.mock.calls.length
    // Sans fournisseur de dialogue, la confirmation retombe sur window.confirm.
    const confirmer = vi.spyOn(window, 'confirm').mockReturnValue(true)
    await userEvent.click(await screen.findByRole('button', { name: /Revenir à cette version/ }))
    await waitFor(() => expect(confirmer).toHaveBeenCalled())
    await waitFor(() => expect(ventesApi.replaceLignesDevis).toHaveBeenCalled())
    const [id, lignes, extra] = ventesApi.replaceLignesDevis.mock.calls.at(-1)
    expect(id).toBe(rouvert.data.id)
    expect(lignes).toEqual(V1.contenu.lignes.map(({ lot, ...l }) => (void lot, l)))
    expect(extra.entete.echeancier).toEqual(V1.contenu.echeancier)
    expect(extra.etude_params).toEqual(V1.contenu.etude)
    expect(ventesApi.patchDevis).not.toHaveBeenCalled()
    await waitFor(() => expect(ventesApi.getDevisById.mock.calls.length).toBeGreaterThan(appelsChargeur))
  })
})
