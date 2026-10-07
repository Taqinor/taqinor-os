// VT10 — la revue bureau d'études filtre sur `statut` (champ déjà renvoyé par
// la liste, jamais une invention de paramètre), et le renvoi exige un motif
// (garde UI, en plus de la garde serveur).
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

const { getVisites, getVisite, renvoyerVisite } = vi.hoisted(() => ({
  getVisites: vi.fn(),
  getVisite: vi.fn(),
  renvoyerVisite: vi.fn(),
}))

vi.mock('../../api/visitesApi', () => ({
  default: {
    getVisites: (...a) => getVisites(...a),
    getVisite: (...a) => getVisite(...a),
    validerVisite: vi.fn(),
    renvoyerVisite: (...a) => renvoyerVisite(...a),
  },
}))

import VisiteBureauEtudesPage from './VisiteBureauEtudesPage'
import { documentContrat } from '../../test/fixtures/contractSamples'

beforeEach(() => {
  vi.clearAllMocks()
  getVisites.mockResolvedValue({
    data: [
      { id: 1, lead: 10, lead_nom: 'Lead A', ville: 'Casablanca', statut: 'terminee', date_prevue: null, complet: true, manquants_count: 0 },
      { id: 2, lead: 11, lead_nom: 'Lead B', ville: 'Rabat', statut: 'validee', date_prevue: null, complet: true, manquants_count: 0 },
      { id: 3, lead: 12, lead_nom: 'Lead C', ville: 'Fès', statut: 'en_cours', date_prevue: null, complet: false, manquants_count: 3 },
    ],
  })
  getVisite.mockResolvedValue({
    data: {
      id: 1, lead: 10, statut: 'terminee',
      checklist: [{ categorie: 'toiture', libelle: 'Toiture', slots: [{ code: 's1', libelle: 'Vue', requis: true, etat: 'ok', photos: [] }] }],
      mesures: { toiture: { longueur_m: 12, largeur_m: 8, pente_deg: 15, orientation: 'sud' } },
      client_panel: { lead_nom: 'Lead A' },
    },
  })
})

describe('VisiteBureauEtudesPage — VT10', () => {
  it('ne liste que les visites `terminee` (champ statut déjà fourni par la liste)', async () => {
    render(<MemoryRouter><VisiteBureauEtudesPage /></MemoryRouter>)
    expect(await screen.findByText('Lead A')).toBeInTheDocument()
    expect(screen.queryByText('Lead B')).not.toBeInTheDocument()
    expect(screen.queryByText('Lead C')).not.toBeInTheDocument()
  })

  it('le bouton Renvoyer reste désactivé tant qu’aucun motif n’est saisi', async () => {
    const user = userEvent.setup()
    render(<MemoryRouter><VisiteBureauEtudesPage /></MemoryRouter>)
    await user.click(await screen.findByText('Lead A'))
    await user.click(await screen.findByRole('button', { name: /renvoyer/i }))
    const boutonEnvoyer = await screen.findByRole('button', { name: /^renvoyer$/i })
    expect(boutonEnvoyer).toBeDisabled()
  })

  // VISITE-QUALIF — ligne compacte lecture seule, utile au commercial closer
  // sans rouvrir le wizard terrain.
  it('sans qualification enregistrée : texte de repli, jamais un cadre vide', async () => {
    const user = userEvent.setup()
    render(<MemoryRouter><VisiteBureauEtudesPage /></MemoryRouter>)
    await user.click(await screen.findByText('Lead A'))
    const bloc = await screen.findByTestId('visite-qualification-resume')
    expect(bloc).toHaveTextContent('Qualification non renseignée.')
  })

  it('avec une qualification enregistrée : ligne compacte des libellés choisis', async () => {
    getVisite.mockResolvedValue({
      data: {
        id: 1, lead: 10, statut: 'terminee',
        checklist: [{ categorie: 'toiture', libelle: 'Toiture', slots: [{ code: 's1', libelle: 'Vue', requis: true, etat: 'ok', photos: [] }] }],
        mesures: { toiture: { longueur_m: 12, largeur_m: 8, pente_deg: 15, orientation: 'sud' } },
        client_panel: { lead_nom: 'Lead A' },
        qualification: {
          temperature: 'chaud', devis: 'convient', decideur: 'seul',
          frein: 'prix', declencheur: 'economies', rappel: 'demain_matin',
        },
      },
    })
    const user = userEvent.setup()
    render(<MemoryRouter><VisiteBureauEtudesPage /></MemoryRouter>)
    await user.click(await screen.findByText('Lead A'))
    const bloc = await screen.findByTestId('visite-qualification-resume')
    expect(bloc).toHaveTextContent('Chaud — prêt à signer · Le devis convient · Seul · Prix · Les économies · Demain matin')
  })
})

/* AGR422 — revue d'un relevé du point d'eau (`exemple_point_eau` du contrat
   partagé `visite_terrain.json`). */
describe('VisiteBureauEtudesPage — AGR422 (gabarit point_eau)', () => {
  const contrat = documentContrat('visites', 'visite_terrain')
  const POINT_EAU = contrat.exemple_point_eau

  it('liste les mesures point_eau, avec libellés, unités et choix lisibles', async () => {
    getVisite.mockResolvedValue({ data: { ...POINT_EAU, statut: 'terminee' } })
    const user = userEvent.setup()
    render(<MemoryRouter><VisiteBureauEtudesPage /></MemoryRouter>)
    await user.click(await screen.findByText('Lead A'))
    expect(await screen.findByRole('heading', { name: 'Visite de relevé du point d’eau' })).toBeInTheDocument()
    const dt = (libelle) => screen.getByText(libelle).nextElementSibling
    expect(dt('Niveau statique (pompe arrêtée)')).toHaveTextContent('32 m')
    expect(dt("Source d'eau")).toHaveTextContent('Forage')
    expect(dt('Méthode de mesure du débit')).toHaveTextContent('Seau chronométré')
    expect(dt('Une pompe est-elle déjà installée ?')).toHaveTextContent('Oui')
    expect(dt("Compteur d'eau sur le forage")).toHaveTextContent('—')
  })

  it('masque le lien de calepinage toiture (atelier 3D) pour ce gabarit, même validée', async () => {
    getVisite.mockResolvedValue({ data: { ...POINT_EAU, statut: 'validee' } })
    const user = userEvent.setup()
    render(<MemoryRouter><VisiteBureauEtudesPage /></MemoryRouter>)
    await user.click(await screen.findByText('Lead A'))
    await screen.findByRole('heading', { name: 'Visite de relevé du point d’eau' })
    expect(screen.queryByRole('button', { name: /atelier 3d/i })).not.toBeInTheDocument()
  })

  it('une visite toiture validée garde son lien « Ouvrir l’atelier 3D »', async () => {
    getVisite.mockResolvedValue({
      data: {
        id: 1, lead: 10, statut: 'validee', gabarit: 'toiture',
        checklist: [{ categorie: 'toiture', libelle: 'Toiture', slots: [{ code: 's1', libelle: 'Vue', requis: true, etat: 'ok', photos: [] }] }],
        mesures: { toiture: { longueur_m: 12, largeur_m: 8, pente_deg: 15, orientation: 'sud' } },
        client_panel: { lead_nom: 'Lead A' },
      },
    })
    const user = userEvent.setup()
    render(<MemoryRouter><VisiteBureauEtudesPage /></MemoryRouter>)
    await user.click(await screen.findByText('Lead A'))
    expect(await screen.findByRole('button', { name: /atelier 3d/i })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Lead A' })).toBeInTheDocument()
  })
})

/* CIQ609 — revue d'une visite de site professionnel : le mock est l'`exemple_ci`
   du contrat partagé `visite_terrain.json`. Le tableau déclaré / constaté /
   écart est SERVI (CIQ606) : l'écran n'en recalcule rien. */
describe('VisiteBureauEtudesPage — CIQ609 (gabarit ci)', () => {
  const contrat = documentContrat('visites', 'visite_terrain')
  const CI = {
    ...contrat.exemple_ci,
    statut: 'terminee',
    // L'exemple ne porte qu'une catégorie de checklist : on dérive les
    // autres du contrat `gabarit_ci`.
    checklist: Object.keys(contrat.gabarit_ci).map((categorie) => ({ categorie, libelle: categorie, slots: [] })),
  }

  const ouvrir = async () => {
    const user = userEvent.setup()
    render(<MemoryRouter><VisiteBureauEtudesPage /></MemoryRouter>)
    await user.click(await screen.findByText('Lead A'))
    return user
  }

  it('titre « Visite technique — site professionnel » et zones de toiture récapitulées', async () => {
    getVisite.mockResolvedValue({ data: CI })
    await ouvrir()
    expect(await screen.findByRole('heading', { name: 'Visite technique — site professionnel' })).toBeInTheDocument()
    const zone = await screen.findByTestId('recap-ligne-zones_toiture-z1')
    expect(zone).toHaveTextContent('Atelier nord')
    expect(zone).toHaveTextContent('Orientation du pan : Sud')
  })

  it('affiche le tableau déclaré / constaté / écart tel que servi', async () => {
    getVisite.mockResolvedValue({ data: CI })
    await ouvrir()
    const toiture = await screen.findByTestId('releve-ci-type_toiture')
    expect(toiture).toHaveTextContent('terrasse_beton')
    expect(toiture).toHaveTextContent('bac_acier')
    expect(toiture).toHaveTextContent('Écart')
    expect(screen.getByTestId('releve-ci-niveau_tension')).toHaveTextContent('Concordant')
    expect(screen.getByTestId('releve-ci-puissance_souscrite_kva')).toHaveTextContent('Non comparable')
    expect(screen.getByTestId('releve-ci-surface_utile')).toHaveTextContent('650 m²')
    expect(screen.getByTestId('releve-ci-surface_utile')).toHaveTextContent('720 m²')
  })

  it('ne recalcule rien : l’écart affiché est celui du serveur, même s’il contredit les valeurs', async () => {
    const releve = {
      ...CI.releve_ci,
      surface_utile: { declare: 100, constate: 100, ecart: true },
      type_toiture: { declare: 'a', constate: 'b', ecart: false },
    }
    getVisite.mockResolvedValue({ data: { ...CI, releve_ci: releve } })
    await ouvrir()
    expect(await screen.findByTestId('releve-ci-surface_utile')).toHaveTextContent('Écart')
    expect(screen.getByTestId('releve-ci-type_toiture')).toHaveTextContent('Concordant')
  })

  it('une mesure non relevée se dit « non vérifié (motif) »', async () => {
    getVisite.mockResolvedValue({ data: CI })
    await ouvrir()
    await screen.findByTestId('visite-releve-ci')
    expect(screen.getAllByText(/Non vérifié \(à faire par un électricien\)/i).length).toBeGreaterThan(0)
  })

  it('une visite toiture ne montre pas le tableau déclaré / constaté', async () => {
    await ouvrir()
    await screen.findByTestId('visite-qualification-resume')
    expect(screen.queryByTestId('visite-releve-ci')).not.toBeInTheDocument()
  })
})

/* Renvoi — le corps suit le contrat serveur (VisiteRenvoiSerializer /
   renvoyer_visite) : `photos` = ids des médias, `mesures` = [{categorie, code}].
   Avant : l'écran envoyait les CODES d'emplacement et `champ` → 400 / mesure
   ignorée. Données : `exemple` du contrat partagé `visite_terrain.json`. */
describe('VisiteBureauEtudesPage — renvoi au contrat serveur', () => {
  const contrat = documentContrat('visites', 'visite_terrain')
  const VISITE = contrat.exemple

  it('envoie les ids des photos de l’emplacement choisi et {categorie, code} des mesures', async () => {
    getVisite.mockResolvedValue({ data: { ...VISITE, statut: 'terminee' } })
    renvoyerVisite.mockResolvedValue({ data: {} })
    const slot = VISITE.checklist[0].slots[0]
    const user = userEvent.setup()
    render(<MemoryRouter><VisiteBureauEtudesPage /></MemoryRouter>)
    await user.click(await screen.findByText('Lead A'))
    await user.click(await screen.findByRole('button', { name: /renvoyer/i }))
    await user.click(await screen.findByRole('checkbox', { name: `${VISITE.checklist[0].libelle} — ${slot.libelle}` }))
    await user.click(screen.getByRole('checkbox', { name: 'Toiture — Longueur de la zone utile' }))
    await user.type(screen.getByLabelText(/Motif/), 'Photo floue')
    await user.click(screen.getByRole('button', { name: /^renvoyer$/i }))
    expect(renvoyerVisite).toHaveBeenCalledWith(VISITE.id, {
      photos: slot.photos.map((p) => p.id),
      mesures: [{ categorie: 'toiture', code: 'longueur_m' }],
      motif: 'Photo floue',
    })
  })
})
