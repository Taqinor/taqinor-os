// AGNR16 (C-AGNR-004) — un prix RELU du serveur n'est jamais réécrit sans
// geste : l'effet `[clientId, lines.length]` ne résout le tarif que d'une
// ligne NOUVELLE (ou de toutes les lignes non relues quand le client change) ;
// rouvrir puis enregistrer sans toucher garde 1 200,00 / 9 000,00 HT, même
// quand une liste de prix renvoie 900,00. Un geste (quantité) résout encore
// le tarif de SA ligne, et d'elle seule.
//
// Harnais du golden (seules les quatre API sont mockées) ; assert sur le
// corps `replace-lines` enregistré.
import { describe, it, expect, vi } from 'vitest'
import { cycleEcran } from '../../test/cycleEcran'
import { act, waitFor, fireEvent } from '@testing-library/react'

import { monter, attendreStable, DEVIS_REGISTRE, LEAD } from './DevisGeneratorGoldenHarnais'

vi.mock('../../api/crmApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())
vi.mock('../../api/stockApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())
vi.mock('../../api/parametresApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())
vi.mock('../../api/ventesApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())

// Le devis 42 de la tâche : sans lead, client 9, 1 200,00 @10 % et 9 000,00 @20 %.
const DEVIS_42 = { ...DEVIS_REGISTRE, id: 42, reference: 'DEV-202610-042' }
const DEVIS_42_ENVOYE = {
  ...DEVIS_42, statut: 'envoye', lead: LEAD.id, date_envoi: '2026-09-28T10:00:00Z',
}
const LISTE_900 = {
  produit: 0, quantite: '1', prix: '900.00', unite: 'HT', source: 'liste', liste_nom: 'Revendeur',
  remise_volume: { remise_ligne_pct: '0.00', cascade: [], remise_totale_pct: '0.00' },
}

cycleEcran()

const ligneDe = (container, designation) => [...container.querySelectorAll('tr[data-line-key]')]
  .find((tr) => [...tr.querySelectorAll('input')].some((i) => i.value === designation))

async function rouvrir(devis) {
  const vue = await monter(`/ventes/devis/nouveau?edit=${devis.id}`, {
    devis,
    avant: (apis) => {
      apis.ventesApi.getPrixApplicable.mockImplementation((p) => Promise.resolve({
        data: { ...LISTE_900, produit: Number(p?.produit) },
      }))
    },
  })
  await waitFor(() => expect(ligneDe(vue.container, 'Onduleur réseau 5kW Monophasé')).toBeTruthy(),
    { timeout: 5000 })
  await attendreStable(vue.container, act, { stables: 10 })
  return vue
}

async function enregistrer(vue) {
  const bouton = [...vue.container.querySelectorAll('button')]
    .find((b) => /Enregistrer les modifications/.test(b.textContent))
  await act(async () => { fireEvent.click(bouton) })
  await waitFor(() => expect(vue.ventesApi.replaceLignesDevis).toHaveBeenCalled(), { timeout: 5000 })
  const corps = vue.ventesApi.replaceLignesDevis.mock.calls.at(-1)[1]
  const lignes = Array.isArray(corps) ? corps : corps.lignes
  return (designation) => lignes.find((l) => l.designation === designation)?.prix_unitaire
}

describe('AGNR16 — un prix relu n’est jamais réécrit sans geste', () => {
  it('rouvrir puis enregistrer sans toucher garde 1 200,00 / 9 000,00 HT, aucun appel tarif au chargement', async () => {
    const vue = await rouvrir(DEVIS_42)
    expect(vue.ventesApi.getPrixApplicable).not.toHaveBeenCalled()
    const pu = await enregistrer(vue)
    expect(pu('Panneau Canadien Solar 715W')).toBe('1200.00')
    expect(pu('Onduleur réseau 5kW Monophasé')).toBe('9000.00')
  }, 60000)

  it('un devis ENVOYÉ rouvert garde ses prix (D-ASTK-1)', async () => {
    const vue = await rouvrir(DEVIS_42_ENVOYE)
    expect(vue.ventesApi.getPrixApplicable).not.toHaveBeenCalled()
    const pu = await enregistrer(vue)
    expect(pu('Panneau Canadien Solar 715W')).toBe('1200.00')
    expect(pu('Onduleur réseau 5kW Monophasé')).toBe('9000.00')
  }, 60000)

  it('un geste (quantité) résout le tarif de SA ligne seulement', async () => {
    const vue = await rouvrir(DEVIS_42)
    const onduleur = ligneDe(vue.container, 'Onduleur réseau 5kW Monophasé')
    await act(async () => {
      fireEvent.change(onduleur.querySelector('[data-role="line-qty"]'), { target: { value: '2' } })
    })
    await waitFor(() => expect(vue.ventesApi.getPrixApplicable).toHaveBeenCalledTimes(1))
    expect(String(vue.ventesApi.getPrixApplicable.mock.calls[0][0].produit)).toBe('102')
    await attendreStable(vue.container, act, { stables: 5 })
    const pu = await enregistrer(vue)
    expect(pu('Onduleur réseau 5kW Monophasé')).toBe('900.00')
    expect(pu('Panneau Canadien Solar 715W')).toBe('1200.00')
  }, 60000)
})
