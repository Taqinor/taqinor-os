import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, within, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* PACT144 — Rapport d'activité périodique (NTAI36).

   La charge utile reprend le dictionnaire réel de
   `apps.ai_governance.services.rapport_periode` — {module, periode,
   metriques:[{cle,label,valeur,unite}], narratif, envoye:false, source} — et
   les deux refus réels de `views._unavailable_response` : 400 (narratif citant
   un chiffre absent des métriques) et 503 (aucune clé LLM). Le point vérifié :
   les métriques affichées sont celles du SERVEUR, le narratif est éditable, et
   un refus serveur est VISIBLE avec son motif exact. */

vi.mock('../../api/aiGovernanceApi', () => ({
  default: { rapportPeriode: vi.fn() },
}))

import aiGovernanceApi from '../../api/aiGovernanceApi'
import RapportPeriodePage from './RapportPeriodePage'

const RAPPORT = {
  module: 'commercial',
  periode: '2026-07',
  metriques: [
    { cle: 'nb_leads', label: 'Leads créés', valeur: '48', unite: '' },
    { cle: 'nb_signes', label: 'Leads signés', valeur: '9', unite: '' },
    { cle: 'taux_conversion_pct', label: 'Taux de conversion', valeur: '18.8', unite: '%' },
    { cle: 'ca_signe', label: 'CA signé', valeur: '812000.00', unite: 'MAD' },
  ],
  narratif: 'En juillet 2026, 48 leads ont été créés et 9 signés.',
  envoye: false,
  source: 'groq',
}

const refusServeur = (statut, detail) => Object.assign(new Error('refus'), {
  response: { status: statut, data: { detail } },
})

const remplirEtGenerer = async (user) => {
  fireEvent.change(screen.getByLabelText('Période (mois)'), {
    target: { value: '2026-07' },
  })
  await user.click(screen.getByRole('button', { name: 'Générer le brouillon' }))
}

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('RapportPeriodePage (PACT144)', () => {
  it('affiche les métriques SERVEUR et un narratif éditable', async () => {
    const user = userEvent.setup()
    aiGovernanceApi.rapportPeriode.mockResolvedValue({ data: RAPPORT })
    render(<RapportPeriodePage />)

    await remplirEtGenerer(user)

    const resultat = await screen.findByTestId('rapport-periode-resultat')
    for (const m of RAPPORT.metriques) {
      expect(within(resultat).getByText(m.label)).toBeInTheDocument()
    }
    expect(within(resultat).getByText('18.8 %')).toBeInTheDocument()
    expect(within(resultat).getByText('812000.00 MAD')).toBeInTheDocument()

    // Narratif éditable, et rien n'est diffusé automatiquement.
    const zone = within(resultat).getByLabelText('Narratif')
    expect(zone).toHaveValue(RAPPORT.narratif)
    await user.clear(zone)
    await user.type(zone, 'Version relue.')
    expect(zone).toHaveValue('Version relue.')
    expect(within(resultat).getByText(/rien n’est diffusé automatiquement/))
      .toBeInTheDocument()

    expect(aiGovernanceApi.rapportPeriode).toHaveBeenCalledWith({
      module: 'commercial', periode: '2026-07',
    })
  })

  it('rend VISIBLE le refus serveur (chiffre absent des métriques) sans afficher le narratif', async () => {
    const user = userEvent.setup()
    aiGovernanceApi.rapportPeriode.mockRejectedValue(refusServeur(
      400,
      'Narratif refusé — chiffres absents des métriques calculées : 120, 7.',
    ))
    render(<RapportPeriodePage />)

    await remplirEtGenerer(user)

    const refus = await screen.findByTestId('rapport-periode-refus')
    expect(refus).toHaveTextContent('Narratif refusé par le serveur')
    expect(refus).toHaveTextContent('chiffres absents des métriques calculées : 120, 7.')
    expect(screen.queryByTestId('rapport-periode-resultat')).not.toBeInTheDocument()
  })

  it('dit la clé absente au lieu d’inventer un brouillon local', async () => {
    const user = userEvent.setup()
    aiGovernanceApi.rapportPeriode.mockRejectedValue(refusServeur(
      503,
      "Aucun fournisseur LLM n'est configuré (clé absente) — les métriques "
      + 'restent consultables dans le reporting.',
    ))
    render(<RapportPeriodePage />)

    await remplirEtGenerer(user)

    const refus = await screen.findByTestId('rapport-periode-refus')
    expect(refus).toHaveTextContent('Génération indisponible')
    expect(refus).toHaveTextContent('clé absente')
    expect(screen.queryByTestId('rapport-periode-resultat')).not.toBeInTheDocument()
  })
})
