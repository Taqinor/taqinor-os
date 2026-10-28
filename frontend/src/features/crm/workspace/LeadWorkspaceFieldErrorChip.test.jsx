import { describe, it, expect, vi } from 'vitest'
import { renderLeadWorkspace, echecReseauAutosaveVille } from '../../../test/leadWorkspaceHarness'
import { LEAD_A, installerHooksLeadWorkspace } from '../../../test/leadWorkspaceMocks'
import { screen, fireEvent, waitFor } from '@testing-library/react'
import crmApi from '../../../api/crmApi'
import LeadWorkspace from './LeadWorkspace'

/* RÈGLE FONDATEUR 08/09/2026 — « all the errors should point at the field
   creating this error and even say what is exactly the error so it is easy
   to solve ». Incident déclencheur : « Non enregistré — Réessayer » + un
   toast « Assurez-vous qu'il n'y a pas plus de 3 chiffres avant la virgule »
   SANS jamais dire quel champ (equip_clim_kw). Ce fichier reprend le patron
   de mocks/rendu de LeadWorkspace.test.jsx (même LEAD_A, mêmes neutralisations
   des rails) pour prouver que le chip d'échec d'autosauvegarde NOMME
   désormais le champ fautif, et garde une action « Réessayer » distincte et
   visible. */

vi.mock('../../../pages/crm/leads/LeadDevisPanel', () => ({ default: () => null }))
vi.mock('../../../pages/crm/leads/SigneDialog', () => ({ default: () => null }))
vi.mock('./ContextRail', () => ({ default: () => null }))
vi.mock('./IdentityRail', () => ({
  default: () => <div data-testid="identity-rail" />,
}))


vi.mock('../../../api/crmApi', async () => (await import('../../../test/leadWorkspaceMocks')).crmApiSections())

installerHooksLeadWorkspace()

function renderEdit(props = {}) {
  return renderLeadWorkspace({ lead: LEAD_A, ...props })
}

async function settled() {
  await waitFor(() => expect(crmApi.getLead).toHaveBeenCalled())
}

describe('RÈGLE FONDATEUR 08/09/2026 — le chip d’échec d’autosauvegarde NOMME le champ fautif', () => {
  it('un 400 { equip_clim_kw: [...] } fait apparaître « Puissance totale climatisation » dans le chip, avec « Réessayer » toujours visible', async () => {
    crmApi.updateLead.mockRejectedValueOnce({
      response: {
        status: 400,
        data: { equip_clim_kw: ["Assurez-vous qu'il n'y a pas plus de 3 chiffres avant la virgule."] },
      },
    })
    renderEdit()
    await settled()
    fireEvent.change(document.querySelector('#lf-ville'), { target: { value: 'Rabat' } })

    const chip = await waitFor(
      () => screen.getByRole('button', { name: /Puissance totale climatisation/ }),
      { timeout: 3000 },
    )
    expect(chip).toHaveTextContent("Assurez-vous qu'il n'y a pas plus de 3 chiffres avant la virgule.")
    // « Réessayer » reste une action DISTINCTE, jamais absorbée par le clic
    // qui nomme/navigue vers le champ.
    expect(screen.getByRole('button', { name: 'Réessayer' })).toBeInTheDocument()
    // Le brouillon reste intact (même garantie que l'échec réseau générique).
    expect(document.querySelector('#lf-ville').value).toBe('Rabat')
  })

  it('cliquer le chip nommé ne jette pas (jumpToField, cible potentiellement repliée) — Réessayer reste opérant', async () => {
    crmApi.updateLead.mockRejectedValueOnce({
      response: {
        status: 400,
        data: { equip_clim_kw: ['Trop de chiffres.'] },
      },
    })
    renderEdit()
    await settled()
    fireEvent.change(document.querySelector('#lf-ville'), { target: { value: 'Fès' } })
    const chip = await waitFor(
      () => screen.getByRole('button', { name: /Puissance totale climatisation/ }),
      { timeout: 3000 },
    )
    expect(() => fireEvent.click(chip)).not.toThrow()

    // Réessayer relance bien un PATCH (2e appel à updateLead).
    crmApi.updateLead.mockResolvedValueOnce({ data: { id: 1 } })
    fireEvent.click(screen.getByRole('button', { name: 'Réessayer' }))
    await waitFor(() => expect(crmApi.updateLead).toHaveBeenCalledTimes(2))
  })

  it('plusieurs champs en erreur : le message porte la 1re erreur + « (+ N autre(s)) »', async () => {
    crmApi.updateLead.mockRejectedValueOnce({
      response: {
        status: 400,
        data: {
          equip_clim_kw: ["Assurez-vous qu'il n'y a pas plus de 3 chiffres avant la virgule."],
          equip_ve_km_semaine: ['Valeur trop grande.'],
        },
      },
    })
    renderEdit()
    await settled()
    fireEvent.change(document.querySelector('#lf-ville'), { target: { value: 'Agadir' } })
    const chip = await waitFor(
      () => screen.getByRole('button', { name: /Puissance totale climatisation/ }),
      { timeout: 3000 },
    )
    expect(chip).toHaveTextContent('(+ 1 autre)')
  })

  it('un échec SANS champ exploitable (réseau) garde le chip générique historique « Non enregistré — Réessayer »', async () => {
    await echecReseauAutosaveVille(LEAD_A)
    // Un seul bouton (pas de second « Réessayer » séparé) — comportement
    // historique inchangé pour ce cas, zéro régression.
    expect(screen.getAllByRole('button', { name: /Réessayer/ })).toHaveLength(1)
  })
})
