import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, within, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'
import { exempleContrat } from '../../../test/fixtures/contractSamples'

/* ============================================================================
   NTPRT14 — « Mes chantiers » (portail client authentifié).
   ----------------------------------------------------------------------------
   PACT10 — aucune charge utile n'est écrite ici : la liste vient de
   `apps/portail/contract_samples/mes_chantiers_liste.json`, le détail
   (jalons) de `mes_chantiers_detail.json` et les photos de
   `mes_chantiers_photos.json` — les MÊMES fichiers que les tests backend
   (`apps/portail/tests/test_ntprt14_mes_chantiers.py`) affirment contre la
   réponse RÉELLE du serveur.
   ========================================================================== */

vi.mock('../../../api/portailApi', () => ({
  default: { chantiers: { liste: vi.fn(), detail: vi.fn(), photos: vi.fn(), releves: vi.fn(), ajouterReleve: vi.fn() } },
}))

import portailApi from '../../../api/portailApi'
import PortailClientChantiers from './PortailClientChantiers.jsx'

const LISTE = exempleContrat('portail', 'mes_chantiers_liste')
const DETAIL = exempleContrat('portail', 'mes_chantiers_detail')
const PHOTOS = exempleContrat('portail', 'mes_chantiers_photos')
const RELEVES = exempleContrat('portail', 'mes_releves_pompage')
const RELEVES_VIDE = exempleContrat('portail', 'mes_releves_pompage', 'exemple_vide')
const RELEVE_201 = exempleContrat('portail', 'mes_releves_pompage', 'exemple_201')
const CORPS_POST = exempleContrat('portail', 'mes_releves_pompage', 'corps_post')
const RECUL = exempleContrat('portail', 'mes_releves_pompage', 'exemple_400_recul')
const CHANTIER = LISTE.results[0]

function renderPage() {
  return render(
    <MemoryRouter>
      <ThemeProvider><PortailClientChantiers /></ThemeProvider>
    </MemoryRouter>,
  )
}

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('PortailClientChantiers — NTPRT14', () => {
  it('affiche tous les chantiers du contrat committé', async () => {
    portailApi.chantiers.liste.mockResolvedValue({ data: LISTE })
    renderPage()

    for (const c of LISTE.results) {
      expect(await screen.findByText(c.reference)).toBeInTheDocument()
      expect(screen.getByText(c.statut_display)).toBeInTheDocument()
    }
  })

  it('affiche un état vide explicite quand le client n’a aucun chantier', async () => {
    portailApi.chantiers.liste.mockResolvedValue({ data: { results: [] } })
    renderPage()

    expect(await screen.findByText('Aucun chantier')).toBeInTheDocument()
  })

  it('signale l’indisponibilité sans planter si la liste échoue', async () => {
    portailApi.chantiers.liste.mockRejectedValue(new Error('500'))
    renderPage()

    expect(await screen.findByText('Chantiers indisponibles')).toBeInTheDocument()
  })

  it('« Voir le suivi » charge et affiche la timeline + la galerie', async () => {
    portailApi.chantiers.liste.mockResolvedValue({ data: LISTE })
    portailApi.chantiers.detail.mockResolvedValue({ data: DETAIL })
    portailApi.chantiers.photos.mockResolvedValue({ data: PHOTOS })
    const user = userEvent.setup()
    renderPage()

    await screen.findByText(CHANTIER.reference)
    await user.click(screen.getAllByRole('button', { name: /Voir le suivi/i })[0])

    await waitFor(() => expect(portailApi.chantiers.detail)
      .toHaveBeenCalledWith(CHANTIER.id))
    expect(portailApi.chantiers.photos).toHaveBeenCalledWith(CHANTIER.id)

    for (const j of DETAIL.jalons) {
      expect(await screen.findByText(j.libelle)).toBeInTheDocument()
    }
    for (const p of PHOTOS.results) {
      const img = screen.getByAltText(p.filename)
      expect(img).toHaveAttribute('src', p.url)
    }
  })

  it('sans photo, affiche une note plutôt qu’une galerie vide silencieuse', async () => {
    portailApi.chantiers.liste.mockResolvedValue({ data: LISTE })
    portailApi.chantiers.detail.mockResolvedValue({ data: DETAIL })
    portailApi.chantiers.photos.mockResolvedValue({ data: { results: [] } })
    const user = userEvent.setup()
    renderPage()

    await screen.findByText(CHANTIER.reference)
    await user.click(screen.getAllByRole('button', { name: /Voir le suivi/i })[0])

    expect(await screen.findByText(
      /Aucune photo pour ce chantier/i)).toBeInTheDocument()
  })

  it('n’expose jamais un lien vers l’endpoint interne des pièces jointes', async () => {
    portailApi.chantiers.liste.mockResolvedValue({ data: LISTE })
    portailApi.chantiers.detail.mockResolvedValue({ data: DETAIL })
    portailApi.chantiers.photos.mockResolvedValue({ data: PHOTOS })
    const user = userEvent.setup()
    const { container } = renderPage()

    await screen.findByText(CHANTIER.reference)
    await user.click(screen.getAllByRole('button', { name: /Voir le suivi/i })[0])
    await screen.findByAltText(PHOTOS.results[0].filename)

    const sources = [...container.querySelectorAll('img[src]')]
      .map((img) => img.getAttribute('src'))
    expect(sources.some((s) => s.includes('records/attachments'))).toBe(false)
  })
})

describe('PortailClientChantiers — AGR614 essai de mise en service', () => {
  async function ouvrirSuivi(detail) {
    portailApi.chantiers.liste.mockResolvedValue({ data: LISTE })
    portailApi.chantiers.detail.mockResolvedValue({ data: detail })
    portailApi.chantiers.photos.mockResolvedValue({ data: { results: [] } })
    const user = userEvent.setup()
    renderPage()
    await screen.findByText(CHANTIER.reference)
    await user.click(screen.getAllByRole('button', { name: /Voir le suivi/i })[0])
    await screen.findByText(/Aucune photo pour ce chantier/i)
  }

  it('rend le bloc avec les valeurs de l’exemple du contrat', async () => {
    await ouvrirSuivi(DETAIL)
    const essai = screen.getByTestId('essai-mise-en-service')
    const r = DETAIL.recette_pompage
    expect(essai).toHaveTextContent('Essai de mise en service')
    expect(essai).toHaveTextContent(`${r.hmt_mesuree_m} m`)
    expect(essai).toHaveTextContent(`${r.debit_mesure_m3h} m³/h`)
    expect(essai).toHaveTextContent(`${r.debit_promis_m3h} m³/h`)
    expect(essai).toHaveTextContent(`${r.ecart_debit_pct} %`)
    expect(essai).toHaveTextContent('Conforme')
  })

  it('absent quand recette_pompage est null', async () => {
    await ouvrirSuivi({ ...DETAIL, recette_pompage: null })
    expect(screen.queryByTestId('essai-mise-en-service')).toBeNull()
    expect(screen.queryByText('Essai de mise en service')).toBeNull()
  })

  it('aucun prix rendu dans le bloc', async () => {
    await ouvrirSuivi(DETAIL)
    expect(screen.getByTestId('essai-mise-en-service').textContent)
      .not.toMatch(/MAD|DH|prix|€|\$/i)
  })
})

describe('PortailClientChantiers — AGR618 relevés de ma pompe', () => {
  async function ouvrirSuivi(releves) {
    portailApi.chantiers.liste.mockResolvedValue({ data: LISTE })
    portailApi.chantiers.detail.mockResolvedValue({ data: DETAIL })
    portailApi.chantiers.photos.mockResolvedValue({ data: { results: [] } })
    portailApi.chantiers.releves.mockResolvedValue({ data: releves })
    const user = userEvent.setup()
    const rendu = renderPage()
    await screen.findByText(CHANTIER.reference)
    await user.click(screen.getAllByRole('button', { name: /Voir le suivi/i })[0])
    await screen.findByTestId('releves-pompe')
    return { user, rendu }
  }

  it('liste les relevés du contrat et la moyenne par jour (rien au premier relevé)', async () => {
    await ouvrirSuivi(RELEVES)
    const items = within(screen.getByTestId('releves-liste')).getAllByRole('listitem')
    expect(items).toHaveLength(RELEVES.releves.length)
    expect(items[0]).toHaveTextContent('1838.00 m³')
    expect(items[0]).toHaveTextContent('≈ 19.6 m³/jour')
    // Premier relevé du type : moyenne null → aucune estimation affichée.
    expect(items[2]).not.toHaveTextContent('≈')
  })

  it('compare à l’estimation du devis seulement quand elle est fournie', async () => {
    const { rendu } = await ouvrirSuivi(RELEVES)
    expect(screen.getByTestId('releves-comparaison'))
      .toHaveTextContent(`m³/jour estimé au devis : ${RELEVES.m3_jour_estime_devis}`)
    rendu.unmount()
    cleanup()
    await ouvrirSuivi({ ...RELEVES, m3_jour_estime_devis: null })
    expect(screen.queryByTestId('releves-comparaison')).toBeNull()
    expect(within(screen.getByTestId('releves-pompe')).queryByText(/estimé au devis/)).toBeNull()
  })

  it('aucun relevé : note explicite, formulaire disponible', async () => {
    await ouvrirSuivi(RELEVES_VIDE)
    expect(screen.getByText('Aucun relevé pour le moment.')).toBeInTheDocument()
    expect(screen.queryByTestId('releves-comparaison')).toBeNull()
  })

  it('formulaire noValidate, index en step="any"', async () => {
    await ouvrirSuivi(RELEVES)
    const form = screen.getByTestId('releves-pompe').querySelector('form')
    expect(form).toHaveAttribute('novalidate')
    expect(screen.getByLabelText('Index du compteur')).toHaveAttribute('step', 'any')
  })

  it('envoie le POST avec les valeurs tapées puis recharge la même liste', async () => {
    const { user } = await ouvrirSuivi(RELEVES)
    portailApi.chantiers.ajouterReleve.mockResolvedValue({ data: RELEVE_201 })
    portailApi.chantiers.releves.mockResolvedValue({
      data: { ...RELEVES, releves: [RELEVE_201, ...RELEVES.releves] },
    })

    fireEvent.change(screen.getByLabelText('Index du compteur'),
      { target: { value: CORPS_POST.valeur } })
    fireEvent.change(screen.getByLabelText('Date du relevé'),
      { target: { value: CORPS_POST.date } })
    await user.click(screen.getByRole('button', { name: 'Enregistrer le relevé' }))

    await waitFor(() => expect(portailApi.chantiers.ajouterReleve)
      .toHaveBeenCalledWith(CHANTIER.id, CORPS_POST))
    await waitFor(() => expect(
      within(screen.getByTestId('releves-liste')).getAllByRole('listitem'),
    ).toHaveLength(RELEVES.releves.length + 1))
    expect(screen.getByTestId('releves-liste')).toHaveTextContent('2391.00 m³')
    expect(screen.getByTestId('releves-liste')).toHaveTextContent('≈ 18.4 m³/jour')
    // Rouvrir : la même liste est resservie.
    cleanup()
    await ouvrirSuivi({ ...RELEVES, releves: [RELEVE_201, ...RELEVES.releves] })
    expect(within(screen.getByTestId('releves-liste')).getAllByRole('listitem'))
      .toHaveLength(RELEVES.releves.length + 1)
  })

  it('le 400 « le compteur ne peut pas reculer » s’affiche sous le champ index', async () => {
    const { user } = await ouvrirSuivi(RELEVES)
    portailApi.chantiers.ajouterReleve.mockRejectedValue({
      response: { status: 400, data: RECUL },
    })
    fireEvent.change(screen.getByLabelText('Index du compteur'), { target: { value: '12' } })
    await user.click(screen.getByRole('button', { name: 'Enregistrer le relevé' }))
    const erreur = await screen.findByTestId('releve-erreur-valeur')
    expect(erreur).toHaveTextContent('le compteur ne peut pas reculer')
  })
})

describe('PortailClientChantiers — CIQ649 mise en service d’un chantier pro', () => {
  async function ouvrirSuivi(detail) {
    portailApi.chantiers.liste.mockResolvedValue({ data: LISTE })
    portailApi.chantiers.detail.mockResolvedValue({ data: detail })
    portailApi.chantiers.photos.mockResolvedValue({ data: { results: [] } })
    const user = userEvent.setup()
    renderPage()
    await screen.findByText(CHANTIER.reference)
    await user.click(screen.getAllByRole('button', { name: /Voir le suivi/i })[0])
    await screen.findByText(/Aucune photo pour ce chantier/i)
  }

  it('rend le bloc avec les valeurs de l’exemple du contrat', async () => {
    await ouvrirSuivi(DETAIL)
    const bloc = screen.getByTestId('mise-en-service-ci')
    const r = DETAIL.recette_ci
    expect(bloc).toHaveTextContent('Mise en service')
    expect(bloc).toHaveTextContent('Conforme avec réserves')
    expect(bloc).toHaveTextContent(`${r.pr}`)
    expect(bloc).toHaveTextContent(r.pr_libelle)
    expect(bloc).toHaveTextContent(r.reserves_ouvertes[0].description)
    expect(bloc).toHaveTextContent('Réception provisoire')
    expect(bloc).toHaveTextContent('Réception définitive')
  })

  it('recette_ci: null → rien', async () => {
    await ouvrirSuivi({ ...DETAIL, recette_ci: null })
    expect(screen.queryByTestId('mise-en-service-ci')).toBeNull()
  })

  it('sans réserve ouverte, la liste n’est pas rendue', async () => {
    await ouvrirSuivi({
      ...DETAIL, recette_ci: { ...DETAIL.recette_ci, reserves_ouvertes: [] },
    })
    expect(screen.getByTestId('mise-en-service-ci'))
      .not.toHaveTextContent('Réserves ouvertes')
  })

  it('aucun prix, instrument ni technicien rendu dans le bloc', async () => {
    await ouvrirSuivi(DETAIL)
    expect(screen.getByTestId('mise-en-service-ci').textContent)
      .not.toMatch(/MAD|DH|prix|€|\$|instrument|technicien/i)
  })
})
