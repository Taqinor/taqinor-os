import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { initState } from '../draftCore'
import SectionSite from './SectionSite'
import crmApi from '../../../../api/crmApi'
import { documentContrat } from '../../../../test/fixtures/contractSamples'

/* AGR517 — fiche lead agricole : carte « Références de pompage proches ».
   Les réponses serveur sont IMPORTÉES de l'échantillon de contrat partagé
   `lead_references_proches.json` (check_api_shapes), jamais écrites à la main. */
vi.mock('../../../../api/crmApi', () => ({
  default: { getLeadReferencesProches: vi.fn() },
}))
vi.mock('./TraceToitClient', () => ({ default: () => null }))
vi.mock('../../../stock/StructureSelector', () => ({ default: () => null }))

const contrat = documentContrat('crm', 'lead_references_proches')

afterEach(() => { cleanup(); vi.clearAllMocks() })

const monter = (lead) => render(
  <SectionSite state={initState({ lead, mode: 'edit' })} setField={vi.fn()} errors={{}} />,
)

describe('AGR517 — Références de pompage proches', () => {
  it('liste vide : le message dit de ne jamais citer un toit', async () => {
    crmApi.getLeadReferencesProches.mockResolvedValue({ data: contrat.exemple_vide })
    monter({ id: 1512, type_installation: 'agricole' })
    expect(await screen.findByTestId('references-proches')).toHaveTextContent(
      'Aucune réalisation de pompage saisie : rien à montrer — ne citez jamais un toit à la place.')
    expect(crmApi.getLeadReferencesProches).toHaveBeenCalledWith(1512)
  })

  it('deux références : ordre du serveur conservé, ville/distance/mois/liens', async () => {
    crmApi.getLeadReferencesProches.mockResolvedValue({
      data: {
        ...contrat.exemple,
        references: [
          { ...contrat.exemple.references[0], lien_video: 'https://exemple.ma/v/1' },
          contrat.exemple.references[1],
        ],
      },
    })
    monter({ id: 1512, type_installation: 'agricole' })
    const lignes = await screen.findAllByTestId('reference-proche')
    expect(lignes).toHaveLength(2)
    expect(lignes[0]).toHaveTextContent('Villa à Bouskoura')
    expect(lignes[0]).toHaveTextContent('(8 km)')
    expect(lignes[0]).toHaveTextContent('juillet 2026')
    expect(lignes[0].querySelector('a[href="https://taqinor.ma/realisations/villa-bouskoura/"]'))
      .not.toBeNull()
    expect(lignes[0].querySelector('a[href="https://exemple.ma/v/1"]')).not.toBeNull()
    expect(lignes[1]).toHaveTextContent('Maison à Berrechid')
    // Distance et mois inconnus : rien d'affiché, jamais « null » ni « 0 km ».
    expect(lignes[1]).not.toHaveTextContent('km')
    expect(lignes[1]).not.toHaveTextContent('mise en service')
    expect(lignes[1].querySelector('a[href*="video"]')).toBeNull()
  })

  it('lead résidentiel : bloc absent, aucune requête', async () => {
    crmApi.getLeadReferencesProches.mockResolvedValue({ data: contrat.exemple })
    monter({ id: 1388, type_installation: 'residentiel' })
    await waitFor(() => expect(screen.getByLabelText('Surface (m²)')).toBeInTheDocument())
    expect(screen.queryByTestId('references-proches')).toBeNull()
    expect(crmApi.getLeadReferencesProches).not.toHaveBeenCalled()
  })
})
