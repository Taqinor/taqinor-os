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
import { bancEdition, devisResidentielRouvert, renderGeneratorPage, makeStoreDirecteur, LEAD, PANNEAU, ONDULEUR } from './devisGenerator.testHelpers.jsx'


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

describe('ACAL1206 — le refus faute de taille nomme les deux gestes possibles', () => {
  it('sans taille ⇒ rien composé ; message nommant la facture hiver/été (lien vers la fiche du lead) ET le nombre de panneaux', async () => {
    const { render } = await import('@testing-library/react')
    const { MemoryRouter } = await import('react-router-dom')
    const { createElement } = await import('react')
    const { etat, composerDevis, ctx, monte } = await bancAutoFill()
    const { result } = monte(ctx({ kwp: 0, selectedLead: { id: 7 } }))
    await act(async () => { await result.current.handleAutoFill() })
    expect(composerDevis).not.toHaveBeenCalled()
    const { container } = render(createElement(MemoryRouter, null, etat.erreurs.autofill))
    expect(container.textContent).toMatch(/Aucune taille : saisissez la facture hiver\/été du lead \(fiche du lead\) ou un nombre de panneaux/)
    expect(container.querySelector('a[href="/crm/leads/7"]')).not.toBeNull()
  })
})

describe('ACAL1212 — ?lead= : aucun Auto-remplir résidentiel avant l\'application du lead', () => {
  it('lead attendu mais pas encore appliqué ⇒ aucune composition, aucun message résidentiel ; lead appliqué ⇒ la branche normale reprend', async () => {
    const { etat, composerDevis, etudeCiPreview, ctx, monte } = await bancAutoFill()
    const { result, rerender } = monte(ctx({ kwp: 0, leadAttendu: '119' }))
    await act(async () => { await result.current.handleAutoFill() })
    expect(composerDevis).not.toHaveBeenCalled()
    expect(etudeCiPreview).not.toHaveBeenCalled()
    expect(String(etat.erreurs.autofill)).toMatch(/lead.*en cours de chargement/i)
    expect(String(etat.erreurs.autofill)).not.toMatch(/nombre de panneaux/)
    await act(async () => { rerender(ctx({ kwp: 0, leadAttendu: '119', selectedLead: { id: 119 } })) })
    await act(async () => { await result.current.handleAutoFill() })
    expect(String(etat.erreurs.autofill)).not.toMatch(/en cours de chargement/)
  })

  // Revue 4 — un lead `?lead=` introuvable (absent de la liste, relu en 404) ne bloque plus Auto-remplir derrière un faux
  // « Lead en cours de chargement » : la recherche terminée sans lead lève l'attente, l'écran dit « Lead introuvable ».
  it('lead introuvable ⇒ l\'attente cesse : Auto-remplir suit sa branche normale (refus faute de taille, nommé)', async () => {
    const { fireEvent } = await import('@testing-library/react')
    crmApi.getLead.mockRejectedValue({ response: { status: 404 } })
    renderGeneratorPage(DevisGenerator, {
      crmApi, stockApi, produits: [PANNEAU, ONDULEUR], store: makeStoreDirecteur(), leads: [LEAD],
      route: '/ventes/devis/nouveau?lead=999',
    })
    expect((await screen.findAllByText(/Lead introuvable \(n° 999\)/)).length).toBeGreaterThan(0)
    fireEvent.click(screen.getAllByTestId('btn-auto-remplir')[0])
    const erreur = await screen.findByTestId('autofill-erreur')
    expect(erreur.textContent).not.toMatch(/en cours de chargement/)
    expect(erreur.textContent).toMatch(/Aucune taille/)
  })
  it('clic pendant l\'attente puis recherche terminée sans lead ⇒ « en cours » est remplacé par « aucun lead appliqué »', async () => {
    const { etat, ctx, monte } = await bancAutoFill()
    const { result, rerender } = monte(ctx({ kwp: 0, leadAttendu: '999' }))
    await act(async () => { await result.current.handleAutoFill() })
    expect(String(etat.erreurs.autofill)).toMatch(/en cours de chargement/)
    await act(async () => { rerender(ctx({ kwp: 0, leadAttendu: null })) })
    await waitFor(() => expect(String(etat.erreurs.autofill)).toMatch(/Aucun lead appliqué/))
  })
})

describe('ACAL1205 —Auto-remplir attend l\'étude horaire (taille « avec batterie »)', () => {
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

  // Revue 4 — `chargement` repasse à vrai à CHAQUE changement des lignes (clé de l'aperçu = leur TTC) alors que
  // l'étude est déjà là : Auto-remplir, « Appliquer cette taille » et « Recalculer » (compteur de composition) composent.
  const etude = { dimensionnement: {
    recommandation: { panneaux: 6, kwc: 4.26 }, recommandation_avec: { panneaux: 8, kwc: 5.68 } } }
  it('étude présente + rechargement en cours ⇒ les trois gestes composent avec la taille avec batterie', async () => {
    const { composerDevis, ctx, monte } = await bancAutoFill()
    const { result, rerender } = monte(ctx({ etudeHoraireDonnees: etude, etudeHoraireChargement: true }))
    await act(async () => { await result.current.handleAutoFill() })
    expect(composerDevis).toHaveBeenCalledTimes(1)
    for (const tick of [1, 2]) {
      await act(async () => { rerender(ctx({ etudeHoraireDonnees: etude, etudeHoraireChargement: true, recalcDimTick: tick })) })
      await waitFor(() => expect(composerDevis).toHaveBeenCalledTimes(1 + tick))
    }
    for (const appel of composerDevis.mock.calls) {
      expect(appel[0].dimensionnement_avec).toMatchObject({ nb_panneaux: 8, kwc: 5.68 })
    }
  })
  it('étude vraiment absente ⇒ Auto-remplir attend ; son arrivée remplace « en cours » par « prêt — réessayez »', async () => {
    const { etat, composerDevis, ctx, monte } = await bancAutoFill()
    const { result, rerender } = monte(ctx({ etudeHoraireChargement: true }))
    await act(async () => { await result.current.handleAutoFill() })
    expect(composerDevis).not.toHaveBeenCalled()
    expect(etat.erreurs.autofill).toMatch(/Dimensionnement en cours/)
    await act(async () => { rerender(ctx({ etudeHoraireDonnees: etude, etudeHoraireChargement: false })) })
    await waitFor(() => expect(etat.erreurs.autofill).toMatch(/Dimensionnement prêt/))
  })
})


describe('ACAL1208 — le numéro du devis ouvert en édition est sa référence', () => {
  it('édition ⇒ « DEV-202611-0072 » ; création ⇒ « Généré automatiquement »', async () => {
    ventesApi.getDevisById.mockResolvedValue(devisRouvert('exemple_brouillon', 'exemple_vide', { reference: 'DEV-202611-0072' }))
    const { unmount } = renderEdition(12)
    await waitFor(() => expect(document.getElementById('gen-num').value).toBe('DEV-202611-0072'))
    unmount()
    renderGeneratorPage(DevisGenerator, { crmApi, stockApi, produits: [PANNEAU, ONDULEUR], store: makeStoreDirecteur() })
    await waitFor(() => expect(document.getElementById('gen-num')).not.toBeNull())
    expect(document.getElementById('gen-num').value).toBe('Généré automatiquement')
  })
})

describe('ACAL1209 — le distributeur du lead est repris tant que le commercial n\'a pas choisi', () => {
  const ouvrirDepuisLead = async (distributeur) => {
    crmApi.getLead.mockResolvedValue({ data: { ...LEAD, distributeur } })
    renderGeneratorPage(DevisGenerator, {
      crmApi, stockApi, produits: [PANNEAU, ONDULEUR], store: makeStoreDirecteur(), leads: [{ ...LEAD, distributeur }],
      route: `/ventes/devis/nouveau?lead=${LEAD.id}`,
    })
    await waitFor(() => expect(document.getElementById('gen-hiver')?.value).toBe('3000'))
  }
  const libelle = () => document.getElementById('gen-distributeur')?.textContent
  it('lead « lydec » ⇒ le choix Distributeur montre Lydec', async () => {
    await ouvrirDepuisLead('lydec')
    await waitFor(() => expect(libelle()).toMatch(/Lydec/))
  })
  it('valeur SRM inconnue du sélecteur ⇒ ONEE inchangé', async () => {
    await ouvrirDepuisLead('srm_beni_mellal')
    expect(libelle()).toMatch(/ONEE/)
  })
})
