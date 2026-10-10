// AGNR30 — `conditions`, `echeancierSaisie`, `tarifSaisie` et `ecoCi` entrent
// dans l'instantané du brouillon : les modifier arme la garde de sortie et
// crée un brouillon local ; restaurer le brouillon remet la valeur.
// Harnais : celui de DevisGeneratorBrouillonEdition.test.jsx (écran réel).
//
// Run : npx vitest run src/pages/ventes/DevisGenerator.agnrBrouillonConditions.test.jsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor, fireEvent } from '@testing-library/react'

import { reinitialiserEdition } from '../../test/shimsEcran'
import { PANNEAU, ONDULEUR, devisBrouillonLead7, renderGenerateurPage } from '../../test/generateurEmbarque'

// Fabriques partagées : src/test/mocksApiDevis.js.
vi.mock('../../api/crmApi', async () => (await import('../../test/mocksApiDevis.js')).crmApiMock())
vi.mock('../../api/stockApi', async () => (await import('../../test/mocksApiDevis.js')).stockApiMock())
vi.mock('../../api/parametresApi', async () => (await import('../../test/mocksApiDevis.js')).parametresApiMock())
vi.mock('../../api/ventesApi', async () => (await import('../../test/mocksApiDevis.js')).ventesApiMock())

import crmApi from '../../api/crmApi'
import stockApi from '../../api/stockApi'
import ventesApi from '../../api/ventesApi'

const CLE = 'taqinor:draft:devis:edit:42'
const UPDATED_AT = '2026-09-30T10:00:00Z'
const LEAD = { id: 7, nom: 'Karim', prenom: 'Brouillon', facture_hiver: '2000', ete_differente: false }

const devis42 = devisBrouillonLead7

const renderEdition = () => renderGenerateurPage()

const quitterBloque = () => {
  const ev = new Event('beforeunload', { cancelable: true })
  window.dispatchEvent(ev)
  return ev.defaultPrevented
}

beforeEach(() => {
  reinitialiserEdition(ventesApi)
  stockApi.getProduits.mockResolvedValue({ data: [PANNEAU, ONDULEUR] })
  crmApi.getLead.mockResolvedValue({ data: LEAD })
  ventesApi.getDevisById.mockResolvedValue(devis42())
})

describe('AGNR30 — conditions, échéancier, tarif et éco C&I dans le brouillon', () => {
  it('ne changer QUE la référence de commande arme la garde et écrit un brouillon', async () => {
    renderEdition()
    await screen.findByRole('button', { name: /Enregistrer les modifications/ })
    await waitFor(() => expect(crmApi.getLead).toHaveBeenCalledWith(7))
    await new Promise(r => setTimeout(r, 1700))
    const ref = await screen.findByLabelText(/Référence de commande du client/)
    fireEvent.change(ref, { target: { value: 'BC-1' } })
    await waitFor(() => expect(quitterBloque()).toBe(true))
    await waitFor(() => expect(window.localStorage.getItem(CLE)).not.toBeNull(), { timeout: 3000 })
    const brouillon = JSON.parse(window.localStorage.getItem(CLE))
    expect(brouillon.data.conditions.referenceCommande).toBe('BC-1')
  }, 15000)

  it('contrôle positif : la note arme la garde comme avant', async () => {
    renderEdition()
    await screen.findByRole('button', { name: /Enregistrer les modifications/ })
    await waitFor(() => expect(crmApi.getLead).toHaveBeenCalledWith(7))
    await new Promise(r => setTimeout(r, 1700))
    fireEvent.change(screen.getByPlaceholderText(/Conditions particulières/), { target: { value: 'Note' } })
    await waitFor(() => expect(quitterBloque()).toBe(true))
  }, 15000)

  it('restaurer le brouillon remet conditions, tarif, éco C&I et échéancier', async () => {
    window.localStorage.setItem(CLE, JSON.stringify({
      savedAt: '2026-09-30T11:00:00Z', version: UPDATED_AT,
      data: {
        conditions: { referenceCommande: 'BC-9' },
        tarifSaisie: { mode: 'grille' },
        ecoCi: { revente_demandee: false },
        echeancierSaisie: [{ libelle: 'Acompte', pourcentage: '40' }, { libelle: 'Solde', pourcentage: '60' }],
      },
    }))
    renderEdition()
    fireEvent.click(await screen.findByRole('button', { name: /Reprendre le brouillon/ }))
    await waitFor(() => expect(screen.getByLabelText(/Référence de commande du client/).value).toBe('BC-9'))
    // Le brouillon réécrit (autosave) porte les quatre clés restaurées.
    await waitFor(() => {
      const d = JSON.parse(window.localStorage.getItem(CLE) || 'null')?.data
      expect(d?.conditions?.referenceCommande).toBe('BC-9')
      expect(d?.tarifSaisie).toEqual(expect.objectContaining({ mode: 'grille' }))
      expect(d?.ecoCi).toEqual(expect.objectContaining({ revente_demandee: false }))
      expect(d?.echeancierSaisie?.[0]?.libelle).toBe('Acompte')
    }, { timeout: 4000 })
  }, 15000)
})
