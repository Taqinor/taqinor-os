// AGEN12 — bandeau « La conception a changé » de l'écran devis. Les réponses
// mockées sont celles du contrat committé `conception_lead.json` (PACT10).
// Nouveau fichier car : composant neuf.
//
// Run : npx vitest run src/pages/ventes/generator/BandeauConception.test.jsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

import { documentContrat, exempleContrat } from '../../../test/fixtures/contractSamples'

vi.mock('../../../api/ventesApi', () => ({
  default: { getConceptionLead: vi.fn(), mettreAJourConception: vi.fn(), reviserDevis: vi.fn() },
}))

import ventesApi from '../../../api/ventesApi'
import BandeauConception from './BandeauConception'
import BandeauxEdition from './BandeauxEdition'

const CONCEPTION = exempleContrat('ventes', 'conception_lead')
const MISE_A_JOUR = documentContrat('ventes', 'conception_lead').mettre_a_jour_conception.reponse
const LISTE = CONCEPTION.brouillons_a_mettre_a_jour[0]
const ECART = CONCEPTION.ecart_devis[0]
const panneaux = (q) => [{ id: 1, designation: 'Panneau Canadian Solar 710W', quantite: String(q), variante: '' }]

function rendre(devis, onMisAJour = vi.fn()) {
  const vue = render(<MemoryRouter><BandeauConception devis={devis} onMisAJour={onMisAJour} /></MemoryRouter>)
  return { ...vue, onMisAJour }
}

beforeEach(() => {
  vi.clearAllMocks()
  ventesApi.getConceptionLead.mockResolvedValue({ data: CONCEPTION })
  ventesApi.mettreAJourConception.mockResolvedValue({ data: MISE_A_JOUR })
})

describe('AGEN12 — bandeau « La conception a changé »', () => {
  it('brouillon retouché : le bandeau, « Mettre à jour », puis ce qui est appliqué et ce qui ne l’est pas', async () => {
    const devis = { id: LISTE.devis, reference: LISTE.reference, statut: 'brouillon', lead: CONCEPTION.lead,
      lignes: panneaux(8) }
    const { onMisAJour } = rendre(devis)
    const bandeau = await screen.findByTestId('bandeau-conception')
    const cible = CONCEPTION.valeurs[CONCEPTION.option_retenue].nb_panneaux.valeur
    expect(bandeau.textContent).toContain(`La conception de ce lead a changé : panneaux 8 → ${cible}`)
    expect(bandeau.textContent).toContain(LISTE.motif)
    await act(async () => { fireEvent.click(screen.getByTestId('bandeau-conception-mettre-a-jour')) })
    expect(ventesApi.mettreAJourConception).toHaveBeenCalledWith(LISTE.devis)
    expect(onMisAJour).toHaveBeenCalled()
    const resultat = await screen.findByTestId('bandeau-conception-resultat')
    expect(resultat.textContent).toContain('Brouillon mis à jour sur la conception du lead.')
    expect(screen.getByTestId('bandeau-conception-non-appliquees').textContent)
      .toContain(MISE_A_JOUR.non_appliquees[0].raison)
  })

  it('brouillon intact (non listé) : aucun bandeau', async () => {
    const { container } = rendre({ id: 999, reference: 'DEV-X', statut: 'brouillon', lead: CONCEPTION.lead,
      lignes: panneaux(8) })
    await waitFor(() => expect(ventesApi.getConceptionLead).toHaveBeenCalledWith(CONCEPTION.lead))
    await act(async () => {})
    expect(container.textContent).toBe('')
  })

  it('devis envoyé dont la conception a bougé : « Réviser le devis », jamais « Mettre à jour »', async () => {
    rendre({ id: 14, reference: ECART.devis_ref, statut: 'envoye', lead: CONCEPTION.lead, lignes: panneaux(14) })
    const bandeau = await screen.findByTestId('bandeau-conception-envoye')
    expect(bandeau.textContent).toContain(`${ECART.valeur} ${ECART.devis} → ${ECART.conception}`)
    expect(screen.getByTestId('bandeau-conception-reviser').textContent).toBe('Réviser le devis')
    expect(screen.queryByTestId('bandeau-conception-mettre-a-jour')).toBeNull()
  })

  it('lead neuf — 200 « aucune » du contrat : aucun bandeau, aucune erreur', async () => {
    ventesApi.getConceptionLead.mockResolvedValue({ data: exempleContrat('ventes', 'conception_lead', 'exemple_aucune') })
    const { container } = rendre({ id: 999, reference: 'DEV-X', statut: 'brouillon', lead: 4, lignes: panneaux(8) })
    await waitFor(() => expect(ventesApi.getConceptionLead).toHaveBeenCalledWith(4))
    await act(async () => {})
    expect(container.textContent).toBe('')
  })

  it('sans lead : rien n’est demandé', () => {
    const { container } = rendre({ id: 5, reference: 'DEV-Y', statut: 'brouillon', lead: null, lignes: [] })
    expect(container.textContent).toBe('')
    expect(ventesApi.getConceptionLead).not.toHaveBeenCalled()
  })
})

// T4-X6-012 — devis commercial / industriel : la fiche du lead changée dans un AUTRE onglet ;
// le bandeau apparaît quand la fenêtre revient au premier plan (sans recharger la page) et
// après un enregistrement ; un brouillon non retouché qui a suivi le dit et se recharge.
describe('T4-X6-012 — bandeau relu au retour sur l’onglet (devis C&I)', () => {
  const ci = { id: LISTE.devis, reference: LISTE.reference, statut: 'brouillon', lead: CONCEPTION.lead,
    mode_installation: 'commercial', lignes: panneaux(14), updated_at: '2026-11-25T09:00:00Z' }
  const sansListe = { ...CONCEPTION, brouillons_a_mettre_a_jour: [], ecart_devis: [] }
  const revenir = async () => { await act(async () => { window.dispatchEvent(new Event('focus')) }) }

  it('brouillon retouché listé après le changement : bandeau au retour sur l’onglet', async () => {
    ventesApi.getConceptionLead.mockResolvedValueOnce({ data: sansListe })
    rendre(ci)
    await waitFor(() => expect(ventesApi.getConceptionLead).toHaveBeenCalledTimes(1))
    expect(screen.queryByTestId('bandeau-conception')).toBeNull()
    await revenir()
    const bandeau = await screen.findByTestId('bandeau-conception')
    expect(bandeau.textContent).toContain('La conception de ce lead a changé')
    expect(screen.getByTestId('bandeau-conception-mettre-a-jour')).toBeTruthy()
  })

  it('après un enregistrement (jeton avancé) : relu, bandeau', async () => {
    ventesApi.getConceptionLead.mockResolvedValueOnce({ data: sansListe })
    const { rerender } = rendre(ci)
    await waitFor(() => expect(ventesApi.getConceptionLead).toHaveBeenCalledTimes(1))
    rerender(<MemoryRouter><BandeauConception devis={{ ...ci, updated_at: '2026-11-25T09:05:00Z' }}
      onMisAJour={vi.fn()} /></MemoryRouter>)
    expect(await screen.findByTestId('bandeau-conception')).toBeTruthy()
  })

  it('brouillon non retouché : la version avance, il l’a suivie — « Recharger »', async () => {
    ventesApi.getConceptionLead.mockResolvedValueOnce({ data: sansListe })
      .mockResolvedValue({ data: { ...sansListe, version: CONCEPTION.version + 1 } })
    const { onMisAJour } = rendre(ci)
    await waitFor(() => expect(ventesApi.getConceptionLead).toHaveBeenCalledTimes(1))
    await revenir()
    const suivi = await screen.findByTestId('bandeau-conception-suivi')
    expect(suivi.textContent).toContain('il suit la nouvelle conception')
    await act(async () => { fireEvent.click(screen.getByTestId('bandeau-conception-recharger')) })
    expect(onMisAJour).toHaveBeenCalled()
    expect(screen.queryByTestId('bandeau-conception-suivi')).toBeNull()
  })
})

// E7d (revue lot 4, M4) — « Mettre à jour » ne perd JAMAIS une saisie non enregistrée :
// avec des modifications à l'écran (`dirty`), il demande d'abord (enregistrer puis mettre à
// jour, ou annuler) ; il n'efface rien en silence. Les deux branches, sur le vrai bandeau
// d'édition (`BandeauxEdition`), puis sans modification : aucune question.
describe('M4 — « Mettre à jour » avec des modifications non enregistrées', () => {
  const devis = { id: LISTE.devis, reference: LISTE.reference, statut: 'brouillon', lead: CONCEPTION.lead,
    lignes: panneaux(8) }
  function rendreEdition({ dirty, choix, enregistre = true }) {
    const props = {
      clear: vi.fn(), setRechargeEdit: vi.fn(), confirm: vi.fn(() => Promise.resolve(choix)),
      enregistrer: vi.fn(() => Promise.resolve(enregistre)),
    }
    render(<MemoryRouter><BandeauxEdition editDevis={devis} dirty={dirty} conflitVerrou={null}
      setConflitVerrou={vi.fn()} forcerSansJetonRef={{ current: false }} handleSubmit={vi.fn()}
      brouillonProposable={false} restored={null} handleRestoreDraft={vi.fn()} discard={vi.fn()} savedAt={null}
      refsLoading={false} loadFailed={[]} saleWarnings={[]} {...props} /></MemoryRouter>)
    return props
  }
  const cliquer = async () => {
    await screen.findByTestId('bandeau-conception')
    await act(async () => { fireEvent.click(screen.getByTestId('bandeau-conception-mettre-a-jour')) })
  }

  it('modifications à l’écran + « Annuler » : rien n’est effacé, rien n’est mis à jour', async () => {
    const p = rendreEdition({ dirty: true, choix: false })
    await cliquer()
    expect(p.confirm).toHaveBeenCalledTimes(1)
    expect(p.confirm.mock.calls[0][0].confirmLabel).toBe('Enregistrer puis mettre à jour')
    expect(p.enregistrer).not.toHaveBeenCalled()
    expect(ventesApi.mettreAJourConception).not.toHaveBeenCalled()
    expect(p.clear).not.toHaveBeenCalled()
    expect(screen.getByTestId('bandeau-conception')).toBeTruthy()
  })

  it('modifications à l’écran + « Enregistrer puis mettre à jour » : enregistré AVANT la mise à jour', async () => {
    const p = rendreEdition({ dirty: true, choix: true })
    await cliquer()
    await waitFor(() => expect(ventesApi.mettreAJourConception).toHaveBeenCalledWith(LISTE.devis))
    expect(p.enregistrer.mock.invocationCallOrder[0])
      .toBeLessThan(ventesApi.mettreAJourConception.mock.invocationCallOrder[0])
    expect(p.clear).toHaveBeenCalled()
    expect(p.setRechargeEdit).toHaveBeenCalled()
  })

  it('enregistrement refusé (validation) : la mise à jour n’a pas lieu', async () => {
    const p = rendreEdition({ dirty: true, choix: true, enregistre: false })
    await cliquer()
    await waitFor(() => expect(p.enregistrer).toHaveBeenCalled())
    expect(ventesApi.mettreAJourConception).not.toHaveBeenCalled()
    expect(p.clear).not.toHaveBeenCalled()
  })

  it('aucune modification : mise à jour directe, aucune question', async () => {
    const p = rendreEdition({ dirty: false, choix: false })
    await cliquer()
    await waitFor(() => expect(ventesApi.mettreAJourConception).toHaveBeenCalledWith(LISTE.devis))
    expect(p.confirm).not.toHaveBeenCalled()
  })
})
