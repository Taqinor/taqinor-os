import { describe, it, expect, vi, beforeAll, afterEach } from 'vitest'
import { screen, cleanup } from '@testing-library/react'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import process from 'node:process'
import { renderInstallationDetail } from '../../test/installationDetailHarness'
import { polyfillResizeObserver } from '../../test/selectNatif'

/* ACHT67 — la bannière « Devis modifié » lit `divergence_devis` SERVI par le
   serveur (ACHT66) ; l'écran ne recalcule plus rien. Le test IMPORTE le contrat
   partagé installation_divergence_devis.json (PACT13) — jamais un mock de forme
   écrit à la main. */

beforeAll(polyfillResizeObserver)
afterEach(() => { cleanup(); vi.clearAllMocks() })

const CONTRAT = JSON.parse(readFileSync(
  resolve(process.cwd(), '..', 'backend', 'django_core', 'apps', 'installations',
    'contract_samples', 'installation_divergence_devis.json'),
  'utf-8',
))

vi.mock('../../api/installationsApi', async () => ({
  default: { ...(await import('../../test/selectNatif')).installationsLecturesVides },
}))
vi.mock('../../api/savApi', async () => (await import('../../test/selectNatif')).savApiMock)
vi.mock('../../api/crmApi', async () => (await import('../../test/selectNatif')).crmApiMock)
vi.mock('../../api/ventesApi', async () => ({
  default: {
    ...(await import('../../test/selectNatif')).ventesApiMock.default,
    getReglementaire: () => Promise.resolve({ data: { results: [] } }),
  },
}))

const BASE = {
  id: 702, reference: 'CHT-202609-0001', statut: 'planifie', client: 12, client_nom: 'Client ACHT67',
  devis: 88, devis_reference: 'DEV-0088',
  bom: [{ produit_id: 412, designation: 'Panneau monocristallin 550 Wc', quantite: 10 }],
}

describe('InstallationDetail — ACHT67 divergence_devis servi', () => {
  it('aucune bannière quand le serveur dit diverge:false (chantier concordant)', async () => {
    renderInstallationDetail({ ...BASE, ...CONTRAT.exemple_concordant })
    await screen.findByRole('button', { name: /Voir le devis/ })
    expect(screen.queryByText(/Devis modifié/)).toBeNull()
  })

  it('bannière listant les lignes en écart quand diverge:true', async () => {
    renderInstallationDetail({ ...BASE, ...CONTRAT.exemple })
    await screen.findByRole('button', { name: /Voir le devis/ })
    expect(screen.getByText(/Devis modifié/)).toBeInTheDocument()
    expect(screen.getByText(/Panneau monocristallin 550 Wc : 10 gelés \/ 14 au devis/)).toBeInTheDocument()
  })
})
