// QJR540 — les blocs livrés du modal DevisForm (supprimé) vivent dans
// l'Édition complète : le calepinage qui pilote le devis (CAL40), les pièces
// jointes du devis (ventes.devis), les compteurs de relations et le bandeau
// « En attente de signature client ». L'écran RÉEL est rendu ; identité/droits
// et clé `calepinage` viennent des exemples COMMITTÉS des contrats.
//
// Run : npx vitest run src/pages/ventes/DevisGeneratorEditBlocs.test.jsx
import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor, renderHook, act } from '@testing-library/react'

import { exempleContrat } from '../../test/fixtures/contractSamples'

vi.mock('../../api/crmApi', async () => (await import('../../test/mocksApiDevis.js')).crmApiAvecLead())
vi.mock('../../api/stockApi', () => ({
  default: { getProduits: vi.fn(() => Promise.resolve({ data: [] })) },
}))
vi.mock('../../api/parametresApi', () => ({
  default: { getProfile: vi.fn(() => Promise.resolve({ data: {} })) },
}))
vi.mock('../../api/recordsApi', () => ({
  default: {
    getAttachments: vi.fn(() => Promise.resolve({ data: [] })),
    deleteAttachment: vi.fn(),
  },
}))
vi.mock('../../api/ventesApi', async () => (await import('../../test/mocksApiDevis.js')).ventesApiEdition())

import crmApi from '../../api/crmApi'
import stockApi from '../../api/stockApi'
import ventesApi from '../../api/ventesApi'
import recordsApi from '../../api/recordsApi'
import DevisGenerator from './DevisGenerator'
import { bancEdition, devisResidentielRouvert } from './devisGenerator.testHelpers.jsx'


function devisRouvert(variante, calepinage = 'exemple', extra = {}) {
  return devisResidentielRouvert(variante, {
    id: 12,
    ...exempleContrat('calepinage', 'calepinage_du_devis', calepinage),
    factures_liees: [{ id: 3 }], bon_commande_etat: null, chantier: null,
    layout_stale: null, layout_nb_panneaux: null,
    ...extra,
  })
}

const { renderEdition } = bancEdition({ DevisGenerator, stockApi, crmApi, ventesApi })

describe('QJR540 — blocs repris de DevisForm dans l’Édition complète', () => {
  it('?edit=12 avec calepinage : bloc calepinage, pièces jointes ventes.devis 12, compteurs', async () => {
    ventesApi.getDevisById.mockResolvedValue(devisRouvert('exemple_envoye'))
    renderEdition(12)
    expect(await screen.findByTestId('cal-bloc-calepinage-devis')).toBeTruthy()
    await waitFor(() => expect(recordsApi.getAttachments).toHaveBeenCalledWith('ventes.devis', 12))
    expect(screen.getByText('Pièces jointes')).toBeTruthy()
    expect(screen.getByText(/factures liées/)).toBeTruthy()
    expect(screen.getByTestId('devis-attente-signature').textContent)
      .toMatch(/En attente de signature client/)
  })

  // T4-X4-006 — le serveur renvoie TOUJOURS un objet (`{exists: false, …}`) :
  // le compteur lisait sa seule présence et affichait « 1 bon de commande » sur
  // chaque brouillon. Il compte `exists`.
  it('T4-X4-006 — « 1 bon de commande » seulement si un bon de commande existe', async () => {
    ventesApi.getDevisById.mockResolvedValue(devisRouvert('exemple_envoye', 'exemple', {
      bon_commande_etat: { exists: false, id: null, reference: null, mismatch: false } }))
    renderEdition(12)
    expect(await screen.findByText(/factures liées/)).toBeTruthy()
    expect(screen.queryByText(/bon de commande/)).toBeNull()
  })

  it('T4-X4-006 — un bon de commande existant se compte', async () => {
    ventesApi.getDevisById.mockResolvedValue(devisRouvert('exemple_envoye', 'exemple', {
      bon_commande_etat: { exists: true, id: 5, reference: 'BC-5', mismatch: false } }))
    renderEdition(12)
    expect(await screen.findByText('1 bon de commande')).toBeTruthy()
  })

  it('brouillon sans calepinage : aucun bloc calepinage vide, pas de bandeau de signature', async () => {
    ventesApi.getDevisById.mockResolvedValue(devisRouvert('exemple_brouillon', 'exemple_vide'))
    renderEdition(12)
    await waitFor(() => expect(recordsApi.getAttachments).toHaveBeenCalledWith('ventes.devis', 12))
    expect(screen.queryByTestId('cal-bloc-calepinage-devis')).toBeNull()
    expect(screen.queryByTestId('devis-attente-signature')).toBeNull()
  })
})

// ACAL1205/1206/1212 — « Auto-remplir » : le hook RÉEL (`useCompositionEcran`), son `setErrors` observé.
async function bancAutoFill() {
  const { useCompositionEcran } = await import('./generator/hooks/useCompositionEcran')
  const { SCENARIO_LES_DEUX } = await import('../../features/ventes/quote/scenarios.js')
  const etat = { erreurs: {} }
  const setErrors = (f) => { etat.erreurs = typeof f === 'function' ? f(etat.erreurs) : f }
  const composerDevis = vi.fn(() => Promise.resolve({ data: { lignes: [] } }))
  const etudeCiPreview = vi.fn(() => Promise.resolve({ data: {} }))
  ventesApi.composerDevis = composerDevis
  ventesApi.etudeCiPreview = etudeCiPreview
  const ctx = (surcharge = {}) => {
    const etudeHoraireDonnees = surcharge.etudeHoraireDonnees ?? null
    return {
      produits: [], setErrors, dispatchSizing: vi.fn(), panelW: '710', scenario: SCENARIO_LES_DEUX,
      modeInstallation: 'residentiel', recalcDimTick: 0, etudeHoraireDonnees, etudeHoraireChargement: false,
      marcheCi: false, apercuCi: {}, avecQuantitesFigees: (f) => f(), sizing: { nbPanneaux: '6', touche: {} },
      lines: [], kwp: 4.26, horsReseau: false, structureType: 'acier', selectedLead: null,
      setOnduleursIncomplets: vi.fn(), setAutoFillLoading: vi.fn(), setCompositionErreur: vi.fn(),
      recomposerLignes: vi.fn(), profilCi: null, ctxProfilCi: {},
      resolveKwcAvec: () => etudeHoraireDonnees?.dimensionnement?.recommandation_avec?.kwc ?? 4.26,
      ...surcharge,
    }
  }
  const monte = (initial) => renderHook((props) => useCompositionEcran(props), { initialProps: initial })
  return { etat, composerDevis, etudeCiPreview, ctx, monte }
}

describe('ACAL1205 — Auto-remplir attend l\'étude horaire (taille « avec batterie »)', () => {
  it('clic pendant le chargement de l\'étude ⇒ rien composé + « en cours » ; après l\'étude ⇒ la composition porte la taille avec batterie', async () => {
    const { etat, composerDevis, ctx, monte } = await bancAutoFill()
    const { result, rerender } = monte(ctx({ etudeHoraireChargement: true }))
    await act(async () => { await result.current.handleAutoFill() })
    expect(composerDevis).not.toHaveBeenCalled()
    expect(etat.erreurs.autofill).toMatch(/Dimensionnement en cours/)
    await act(async () => {
      rerender(ctx({ etudeHoraireDonnees: { dimensionnement: {
        recommandation: { panneaux: 6, kwc: 4.26 }, recommandation_avec: { panneaux: 8, kwc: 5.68 } } } }))
    })
    await act(async () => { await result.current.handleAutoFill() })
    expect(composerDevis).toHaveBeenCalledTimes(1)
    expect(composerDevis.mock.calls[0][0].dimensionnement_avec).toMatchObject({ nb_panneaux: 8, kwc: 5.68 })
  })
})

