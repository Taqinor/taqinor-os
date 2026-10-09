// AGNR31 — `validate()` dit ce que `lignesEnvoyees` ne gardera pas : une
// ligne « prix à renseigner » bloque (nommée) et ne satisfait plus la garde
// « au moins une pompe » ; une ligne produit à quantité 0 est annoncée
// (avertissement non bloquant) au lieu de disparaître.
//
// Run : npx vitest run src/pages/ventes/DevisGenerator.agnrLignesNonEnregistrables.test.jsx
import { describe, it, expect, vi } from 'vitest'
import { cycleEcran } from '../../test/cycleEcran'
import { act, fireEvent, screen, waitFor } from '@testing-library/react'

import { DATE_FIGEE, monter, attendreStable, DEVIS_AGRICOLE_POMPE, DEVIS_REGISTRE, CATALOGUE } from './DevisGeneratorGoldenHarnais'

vi.mock('../../api/crmApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())
vi.mock('../../api/stockApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())
vi.mock('../../api/parametresApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())
vi.mock('../../api/ventesApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())

cycleEcran({ date: DATE_FIGEE })

const taper = async (el, v) => { await act(async () => { fireEvent.change(el, { target: { value: v } }) }) }
const enregistrer = async () => {
  const b = [...document.querySelectorAll('button')]
    .find((x) => /Enregistrer les modifications/.test(x.textContent || ''))
  await act(async () => { fireEvent.click(b) })
}
const SMART = CATALOGUE.find((p) => /Smart Meter/.test(p.nom))

describe('AGNR31 — lignes que l’enregistrement ne gardera pas', () => {
  it('(a) pompage : la seule pompe est « prix à renseigner » ⇒ bloqué, nommée, aucun envoi', async () => {
    // Le devis agricole SANS sa ligne pompe ; la pompe est un placeholder.
    const devis = { ...DEVIS_AGRICOLE_POMPE, lignes: DEVIS_AGRICOLE_POMPE.lignes.filter((l) => !/Pompe/.test(l.designation)) }
    const vue = await monter(`/ventes/devis/nouveau?edit=${devis.id}`, { devis })
    await attendreStable(vue.container, act)
    await act(async () => {
      fireEvent.click([...document.querySelectorAll('button')].find((b) => /Ajouter ligne/.test(b.textContent || '')))
    })
    // La dernière ligne ajoutée : désignation, quantité 1, prix 0.
    const derniere = [...document.querySelectorAll('tr[data-line-key]')].at(-1)
    const champs = [...derniere.querySelectorAll('input')]
    await taper(champs[0], 'Pompe OSP 30-5 — prix à renseigner')
    await taper(derniere.querySelector('[data-role="line-qty"]'), '1')
    await attendreStable(vue.container, act)
    await enregistrer()
    await attendreStable(vue.container, act)
    expect(vue.ventesApi.replaceLignesDevis).not.toHaveBeenCalled()
    expect(screen.getByTestId('erreur-enregistrement').textContent)
      .toBe('1 ligne « prix à renseigner » ne sera pas enregistrée : Pompe OSP 30-5')
  }, 60000)

  it('(b) une ligne produit à prix tapé passée à quantité 0 ⇒ avertie, l’envoi part sans elle', async () => {
    const devis = {
      ...DEVIS_REGISTRE,
      lignes: [...DEVIS_REGISTRE.lignes, {
        id: 3, produit: SMART.id, designation: 'Smart Meter', quantite: '1', prix_unitaire: '1000.00',
        taux_tva: '20.00', remise: '0.00', ordre: 2, type_ligne: 'produit', optionnelle: false,
        variante: '', prix_manuel: true,
      }],
    }
    const vue = await monter(`/ventes/devis/nouveau?edit=${devis.id}`, { devis })
    await attendreStable(vue.container, act)
    const qtes = [...document.querySelectorAll('[data-role="line-qty"]')]
    await taper(qtes[2], '0')
    await attendreStable(vue.container, act)
    // Annoncé AVANT l'envoi.
    expect(screen.getByTestId('avis-quantite-nulle').textContent)
      .toBe('1 ligne à quantité 0 ne sera pas enregistrée : Smart Meter')
    await enregistrer()
    await waitFor(() => expect(vue.ventesApi.replaceLignesDevis).toHaveBeenCalled(), { timeout: 5000 })
    const [, lignes] = vue.ventesApi.replaceLignesDevis.mock.calls.at(-1)
    expect(lignes).toHaveLength(2)
  }, 60000)
})
