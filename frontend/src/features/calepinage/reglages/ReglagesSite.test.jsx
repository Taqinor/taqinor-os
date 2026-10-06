import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor, within } from '@testing-library/react'
import { exempleContrat } from '../../../test/fixtures/contractSamples'
import { espions } from '../../../test/fixtures/calepinageApiMock'

/* ============================================================================
   ACAL130 — « SITE & IMAGERIE » : pays, fournisseur, attribution, altitude +
   source, fuseau, et le fuseau EFFECTIF avec sa provenance.
   Les réponses viennent de `contract_samples/site_imagerie.json` (jamais une
   charge écrite à la main). Le serveur REMPLACE la section `imagerie` en
   entier (seules `simulation` / `electrique_societe` fusionnent) : le corps
   du PUT porte donc les clés servies, les seules clés modifiées étant
   remplacées ; `site_effectif` (clé dérivée) n'est jamais renvoyée.
   ========================================================================== */

const SERVI = exempleContrat('calepinage', 'site_imagerie').imagerie
const VIDE = exempleContrat('calepinage', 'site_imagerie', 'exemple_vide').imagerie
const SANS_VALEUR = exempleContrat('calepinage', 'site_imagerie', 'exemple_section_declaree_sans_valeur').imagerie

// ACAL345 — la doublure partagée de `calepinageApi.parametres` et de la permission.
const mocks = espions
vi.mock('../../../api/calepinageApi', async () => (await import('../../../test/fixtures/calepinageApiMock')).apiParametres())
vi.mock('../../../hooks/useHasPermission', async () => (await import('../../../test/fixtures/calepinageApiMock')).permissionMock())

const { default: ReglagesSite } = await import('./ReglagesSite')

const champ = (cle) => screen.getByTestId(`acal130-champ-${cle}`).querySelector('input')
const sansDerivee = (section) => {
  const copie = { ...section }
  delete copie.site_effectif
  return copie
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.hasPermission.mockReturnValue(true)
  mocks.getParametres.mockResolvedValue({ data: { imagerie: SERVI } })
  mocks.putParametres.mockResolvedValue({ data: {} })
})
afterEach(() => { cleanup() })

describe('ReglagesSite (ACAL130)', () => {
  it('aller-retour sans geste : section identique', async () => {
    render(<ReglagesSite imagerie={SERVI} />)

    fireEvent.click(screen.getByTestId('acal130-enregistrer'))

    await waitFor(() => expect(mocks.putParametres).toHaveBeenCalledTimes(1))
    // Les huit clés servies reviennent à l'identique ; `site_effectif` n'est
    // jamais renvoyée (clé dérivée).
    expect(mocks.putParametres.mock.calls[0][0]).toEqual({ imagerie: sansDerivee(SERVI) })
    expect('site_effectif' in mocks.putParametres.mock.calls[0][0].imagerie).toBe(false)
  })

  it('PUT ne perd aucune clé : la clé modifiée est remplacée, les autres renvoyées', async () => {
    render(<ReglagesSite imagerie={SERVI} />)

    fireEvent.change(champ('fuseau'), { target: { value: 'Africa/Casablanca' } })
    fireEvent.change(champ('altitude_m'), { target: { value: '150,5' } })
    fireEvent.click(screen.getByTestId('acal130-enregistrer'))

    await waitFor(() => expect(mocks.putParametres).toHaveBeenCalledTimes(1))
    expect(mocks.putParametres.mock.calls[0][0]).toEqual({
      imagerie: { ...sansDerivee(SERVI), fuseau: 'Africa/Casablanca', altitude_m: 150.5 },
    })
  })

  it('société sans réglage : seule la clé saisie part', async () => {
    render(<ReglagesSite imagerie={VIDE} />)

    fireEvent.change(champ('pays'), { target: { value: 'fr' } })
    fireEvent.click(screen.getByTestId('acal130-enregistrer'))

    await waitFor(() => expect(mocks.putParametres).toHaveBeenCalledTimes(1))
    expect(mocks.putParametres.mock.calls[0][0]).toEqual({ imagerie: { pays: 'fr' } })
  })

  it('un champ vidé part à null', async () => {
    render(<ReglagesSite imagerie={SERVI} />)

    fireEvent.change(champ('attribution'), { target: { value: '' } })
    fireEvent.click(screen.getByTestId('acal130-enregistrer'))

    await waitFor(() => expect(mocks.putParametres).toHaveBeenCalledTimes(1))
    expect(mocks.putParametres.mock.calls[0][0].imagerie.attribution).toBeNull()
  })

  it('fuseau effectif et sa source affichés', () => {
    render(<ReglagesSite imagerie={SERVI} />)

    const effectif = screen.getByTestId('acal130-fuseau-effectif')
    expect(effectif).toHaveTextContent('Europe/Paris')
    expect(effectif).toHaveTextContent('réglage imagerie')
  })

  it('fuseau du profil société : provenance et mention servies affichées', () => {
    const profil = {
      ...SERVI,
      fuseau: null,
      site_effectif: { fuseau: 'Africa/Casablanca', source: 'profil_societe', mention: 'Fuseau repris du profil société.' },
    }
    render(<ReglagesSite imagerie={profil} />)

    const effectif = screen.getByTestId('acal130-fuseau-effectif')
    expect(effectif).toHaveTextContent('Africa/Casablanca')
    expect(effectif).toHaveTextContent('profil société')
    expect(effectif).toHaveTextContent('Fuseau repris du profil société.')
  })

  it('aucun fuseau : la mention servie, jamais une heure supposée', () => {
    render(<ReglagesSite imagerie={SANS_VALEUR} />)

    expect(screen.getByTestId('acal130-fuseau-effectif'))
      .toHaveTextContent(SANS_VALEUR.site_effectif.mention)
  })

  it('refus 400 : la clé fautive est nommée sous son champ', async () => {
    mocks.putParametres.mockRejectedValueOnce({
      response: { data: { fuseau: ['Le fuseau horaire « Mars/Olympus » est inconnu de la base IANA.'] } },
    })
    render(<ReglagesSite imagerie={SERVI} />)

    fireEvent.change(champ('fuseau'), { target: { value: 'Mars/Olympus' } })
    fireEvent.click(screen.getByTestId('acal130-enregistrer'))

    const ligne = await screen.findByTestId('acal130-champ-fuseau')
    expect(within(ligne).getByTestId('acal130-erreur-fuseau')).toHaveTextContent('inconnu de la base IANA')
    expect(screen.getByTestId('acal130-bandeau')).toHaveTextContent('fuseau')
  })

  it('après enregistrement, le site effectif est relu du serveur', async () => {
    mocks.getParametres.mockResolvedValue({
      data: { imagerie: { ...SERVI, fuseau: 'Africa/Casablanca', site_effectif: { fuseau: 'Africa/Casablanca', source: 'imagerie', mention: '' } } },
    })
    render(<ReglagesSite imagerie={SERVI} />)

    fireEvent.change(champ('fuseau'), { target: { value: 'Africa/Casablanca' } })
    fireEvent.click(screen.getByTestId('acal130-enregistrer'))

    await screen.findByTestId('acal130-message')
    expect(screen.getByTestId('acal130-fuseau-effectif')).toHaveTextContent('Africa/Casablanca')
    expect(champ('fuseau').value).toBe('Africa/Casablanca')
  })

  it('sans le droit de gérer : saisie désactivée, pas d’enregistrement', () => {
    mocks.hasPermission.mockReturnValue(false)
    render(<ReglagesSite imagerie={SERVI} />)

    expect(champ('fuseau')).toBeDisabled()
    expect(screen.queryByTestId('acal130-enregistrer')).toBeNull()
  })
})
