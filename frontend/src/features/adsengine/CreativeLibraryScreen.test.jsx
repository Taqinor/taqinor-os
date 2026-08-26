import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* ENG27 — Bibliothèque créative : grille d'assets, flux policy-check humain
   règle par règle (pending → vérifié à l'écran), upload, variantes ENG18. */

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  upload: vi.fn(),
  policyCheck: vi.fn(),
  generateVariants: vi.fn(),
  checklist: vi.fn(),
}))

vi.mock('./adsengineApi', () => ({
  default: {
    creatives: {
      list: mocks.list, upload: mocks.upload,
      policyCheck: mocks.policyCheck, generateVariants: mocks.generateVariants,
      checklist: mocks.checklist,
    },
  },
}))

import CreativeLibraryScreen from './CreativeLibraryScreen'

const renderScreen = () => render(
  <MemoryRouter><CreativeLibraryScreen /></MemoryRouter>)

/* WIR170 — clés RÉELLES de la check-list serveur
   (`apps/adsengine/policy.py DEFAULT_FORBIDDEN`, renvoyées par
   `GET /adsengine/creatifs/checklist/`). Aucune clé inventée ici. */
const SERVER_FORBIDDEN = [
  { key: 'no_fake_sites', label: 'Aucun faux chantier / installation mise en scène' },
  { key: 'no_fake_clients', label: 'Aucun faux client ni acteur présenté comme client' },
  { key: 'no_fake_testimonials', label: 'Aucun faux témoignage' },
  { key: 'no_unverified_numbers', label: 'Aucun chiffre non vérifié (économies, puissance, délais)' },
]

beforeEach(() => {
  vi.clearAllMocks()
  mocks.list.mockResolvedValue({ data: [
    { id: 1, designation: 'Reel toiture', type: 'reel', policy_stamp: { passed: false }, reponses_whatsapp: 3, cout_mad: 250 },
    { id: 2, designation: 'Statique prix', type: 'static', policy_stamp: { passed: true }, reponses_whatsapp: 8, cout_mad: 400 },
  ] })
  mocks.upload.mockResolvedValue({ data: {} })
  mocks.checklist.mockResolvedValue({ data: { forbidden: SERVER_FORBIDDEN, allowed: [] } })
  // Le serveur renvoie l'asset estampillé (`CreativeAssetSerializer`).
  mocks.policyCheck.mockResolvedValue({ data: {
    id: 1, designation: 'Reel toiture', type: 'reel',
    policy_stamp: { passed: true, rules_checked: SERVER_FORBIDDEN.map(r => r.key) },
  } })
  mocks.generateVariants.mockResolvedValue({ data: {} })
})

describe('CreativeLibraryScreen (ENG27)', () => {
  it('affiche la grille avec statut de conformité et perf par asset', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.list).toHaveBeenCalled())
    expect(screen.getAllByTestId('ae-creative-card')).toHaveLength(2)
    expect(screen.getByTestId('ae-creative-status-1')).toHaveTextContent('À vérifier')
    expect(screen.getByTestId('ae-creative-status-2')).toHaveTextContent('Vérifié')
    expect(screen.getByText(/3 réponses WhatsApp/)).toBeInTheDocument()
  })

  it('ADSDEEP15 — rend un <video> pour un reel avec preview_url et un <img> pour un statique', async () => {
    mocks.list.mockResolvedValue({ data: [
      { id: 10, designation: 'Reel', asset_type: 'reel', is_video: true,
        preview_url: 'https://minio/signed/reel.mp4', policy_stamp: { passed: true } },
      { id: 11, designation: 'Statique', asset_type: 'static', is_video: false,
        preview_url: 'https://minio/signed/img.png', policy_stamp: { passed: true } },
    ] })
    renderScreen()
    await waitFor(() => expect(mocks.list).toHaveBeenCalled())
    const video = await screen.findByTestId('ae-creative-video')
    expect(video.tagName).toBe('VIDEO')
    expect(video).toHaveAttribute('src', 'https://minio/signed/reel.mp4')
    expect(screen.getByTestId('ae-creative-img')).toHaveAttribute('src', 'https://minio/signed/img.png')
  })

  it('policy-check humain : l\'asset passe pending → vérifié une fois toutes les règles confirmées', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.list).toHaveBeenCalled())
    fireEvent.click(screen.getByTestId('ae-creative-check-1'))
    const checklist = await screen.findByTestId('ae-creative-checklist-1')
    // Valider est désactivé tant que TOUTES les règles ne sont pas confirmées.
    const validate = screen.getByTestId('ae-creative-validate-1')
    expect(validate).toBeDisabled()
    // Confirme chaque règle (rule-by-rule).
    const boxes = checklist.querySelectorAll('input[type="checkbox"]')
    expect(boxes.length).toBeGreaterThanOrEqual(3)
    boxes.forEach(b => fireEvent.click(b))
    expect(validate).not.toBeDisabled()
    fireEvent.click(validate)
    await waitFor(() => expect(mocks.policyCheck).toHaveBeenCalled())
    // pending → vérifié à l'écran (sur le tampon RENVOYÉ par le serveur).
    await waitFor(() => expect(screen.getByTestId('ae-creative-status-1')).toHaveTextContent('Vérifié'))
  })

  it('WIR170 — la check-list vient du SERVEUR et la validation poste `confirmed_keys` (clés réelles)', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.checklist).toHaveBeenCalled())
    fireEvent.click(screen.getByTestId('ae-creative-check-1'))
    const checklist = await screen.findByTestId('ae-creative-checklist-1')
    // Les libellés rendus sont ceux du serveur, pas une liste codée à l'écran.
    expect(checklist).toHaveTextContent('Aucun faux témoignage')
    SERVER_FORBIDDEN.forEach(r => {
      fireEvent.click(screen.getByTestId(`ae-creative-rule-1-${r.key}`))
    })
    fireEvent.click(screen.getByTestId('ae-creative-validate-1'))
    await waitFor(() => expect(mocks.policyCheck).toHaveBeenCalled())
    const [id, payload] = mocks.policyCheck.mock.calls[0]
    expect(id).toBe(1)
    // La SEULE clé lue par le serveur (views.py:864).
    expect(Object.keys(payload)).toEqual(['confirmed_keys'])
    expect([...payload.confirmed_keys].sort())
      .toEqual(SERVER_FORBIDDEN.map(r => r.key).sort())
  })

  it('WIR170 — un refus serveur (passed=false) ne marque JAMAIS l\'asset vérifié', async () => {
    mocks.policyCheck.mockResolvedValue({ data: {
      id: 1, designation: 'Reel toiture', type: 'reel',
      policy_stamp: {
        passed: false, consent_block: 'manquant',
        consent_block_label: 'Consentement client manquant (CNDP) : un asset montrant un client réel exige un consentement signé.',
      },
    } })
    renderScreen()
    await waitFor(() => expect(mocks.checklist).toHaveBeenCalled())
    fireEvent.click(screen.getByTestId('ae-creative-check-1'))
    await screen.findByTestId('ae-creative-checklist-1')
    SERVER_FORBIDDEN.forEach(r => {
      fireEvent.click(screen.getByTestId(`ae-creative-rule-1-${r.key}`))
    })
    fireEvent.click(screen.getByTestId('ae-creative-validate-1'))
    await waitFor(() => expect(mocks.policyCheck).toHaveBeenCalled())
    // Aucun affichage optimiste : le statut reste « À vérifier ».
    await waitFor(() => expect(screen.getByTestId('ae-creative-msg'))
      .toHaveTextContent(/Consentement client manquant/))
    expect(screen.getByTestId('ae-creative-status-1')).toHaveTextContent('À vérifier')
  })

  it('WIR170 — check-list serveur indisponible : validation impossible (aucune règle inventée)', async () => {
    mocks.checklist.mockRejectedValue(new Error('boom'))
    renderScreen()
    await waitFor(() => expect(mocks.checklist).toHaveBeenCalled())
    fireEvent.click(screen.getByTestId('ae-creative-check-1'))
    const checklist = await screen.findByTestId('ae-creative-checklist-1')
    expect(checklist).toHaveTextContent('Check-list policy indisponible')
    expect(checklist.querySelectorAll('input[type="checkbox"]')).toHaveLength(0)
    expect(screen.getByTestId('ae-creative-validate-1')).toBeDisabled()
  })

  it('WIR170 — l\'écran est ATTEIGNABLE : route + entrée de nav déclarées', async () => {
    const { default: config } = await import('./module.config.jsx')
    expect(config.routes.map(r => r.path)).toContain('/publicite/creatifs')
    expect(config.nav.items.map(i => i.to)).toContain('/publicite/creatifs')
  })

  it('upload : soumet un FormData avec le fichier choisi', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.list).toHaveBeenCalled())
    fireEvent.change(screen.getByTestId('ae-creative-upload-designation'),
      { target: { value: 'Nouveau reel' } })
    const file = new File(['x'], 'reel.mp4', { type: 'video/mp4' })
    fireEvent.change(screen.getByTestId('ae-creative-upload-file'),
      { target: { files: [file] } })
    fireEvent.click(screen.getByTestId('ae-creative-upload-submit'))
    await waitFor(() => expect(mocks.upload).toHaveBeenCalled())
    const fd = mocks.upload.mock.calls[0][0]
    expect(fd).toBeInstanceOf(FormData)
    expect(fd.get('designation')).toBe('Nouveau reel')
    expect(fd.get('file')).toBeTruthy()
  })

  it('déclenche des variantes (ENG18) sur un asset vérifié', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.list).toHaveBeenCalled())
    fireEvent.click(screen.getByTestId('ae-creative-variants-2'))
    await waitFor(() => expect(mocks.generateVariants).toHaveBeenCalledWith(2))
  })
})
