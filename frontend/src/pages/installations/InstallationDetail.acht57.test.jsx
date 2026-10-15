import { describe, it, expect, vi, beforeAll, beforeEach, afterEach } from 'vitest'
import { screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import process from 'node:process'
import { renderInstallationDetail } from '../../test/installationDetailHarness'
import { polyfillResizeObserver } from '../../test/selectNatif'

/* ACHT57 — « Mettre à jour » n'envoie que le DIFF des champs modifiés, le
   formulaire se resynchronise après chaque rafraîchissement, et les champs
   gelés sont grisés quand cloture_verrouillee. Test COMPORTEMENTAL : un faux
   serveur en mémoire applique le corps reçu au chantier (il pose les dates à
   l'avancée et refuse le champ gelé d'un chantier clôturé), puis relecture. */

beforeAll(polyfillResizeObserver)

// ACHT67 — contrat partagé importé (PACT13), jamais un mock de forme écrit à la main.
const CONTRAT_DIVERGENCE = JSON.parse(readFileSync(
  resolve(process.cwd(), '..', 'backend', 'django_core', 'apps', 'installations',
    'contract_samples', 'installation_divergence_devis.json'),
  'utf-8',
))

const db = {}
const fakeServer = vi.hoisted(() => ({ advance: null }))

vi.mock('./ChantierGateTimeline', () => ({
  default: ({ installationId, onAdvanced }) => (
    <button type="button" onClick={async () => {
      fakeServer.advance(installationId)
      await onAdvanced()
    }}>Avancer (stepper)</button>
  ),
}))

vi.mock('./ChantierChecklist', async () => (await import('../../test/selectNatif')).composantNul)
vi.mock('../../features/installations/offline/OfflineSyncIndicator', async () => (await import('../../test/selectNatif')).composantNul)

vi.mock('../../api/installationsApi', async () => ({
  default: {
    ...(await import('../../test/selectNatif')).installationsLecturesVides,
    getInstallation: (id) => Promise.resolve({ data: { ...db[id] } }),
    updateInstallation: (id, body) => {
      const row = db[id]
      if (row.cloture_verrouillee && 'puissance_installee_kwc' in body) {
        return Promise.reject({ response: { data: { puissance_installee_kwc: ['Champ gelé.'] } } })
      }
      Object.assign(row, body)
      return Promise.resolve({ data: { ...row } })
    },
  },
}))
vi.mock('../../api/savApi', async () => (await import('../../test/selectNatif')).savApiMock)
vi.mock('../../api/crmApi', async () => (await import('../../test/selectNatif')).crmApiMock)
vi.mock('../../api/ventesApi', async () => (await import('../../test/selectNatif')).ventesApiMock)

const renderDetail = (row) => renderInstallationDetail({ ...row })

beforeEach(() => {
  db[1] = { id: 1, reference: 'CH-1', statut: 'materiel_commande', annule: false, notes: '' }
  db[2] = { id: 2, reference: 'CH-2', statut: 'en_cours', annule: false, notes: '' }
  db[3] = {
    id: 3, reference: 'CH-3', statut: 'installe', annule: false, notes: '',
    puissance_installee_kwc: 6.5, cloture_verrouillee: true,
  }
  db[4] = { id: 4, reference: 'CH-4', statut: 'installe', annule: false, notes: '' }
  // ACHT67 : bom gelée (10 panneaux) ; divergence servie par le détail.
  db[5] = {
    id: 5, reference: 'CH-5', statut: 'planifie', annule: false, notes: '', devis: 88, client: 12,
    bom: [{ produit_id: 412, designation: 'Panneau monocristallin 550 Wc', quantite: 10 }],
    ...CONTRAT_DIVERGENCE.exemple,
  }
  db[6] = { ...db[5], id: 6, reference: 'CH-6', ...CONTRAT_DIVERGENCE.exemple_concordant }
  // APRF37 : le détail porte les blocs que la LIGNE de liste sert à null.
  db[7] = {
    id: 7, reference: 'CH-7', statut: 'planifie', annule: false, notes: '',
    regime_suggere: { code: 'accord_raccordement', label: 'Accord de raccordement' },
    calepinage: { calepinage_id: 7, kwc: 8.64, nb_modules: 12, planche_url: '/calepinage/7', plan_pose_url: '/ventes/devis/103/3d' },
    dossier_8221_resume: { source: 'saisie_chantier' },
  }
  fakeServer.advance = (id) => {
    if (id === 1) Object.assign(db[1], { statut: 'planifie', date_pose_prevue: '2026-10-20' })
    if (id === 2) Object.assign(db[2], { statut: 'installe', date_pose_reelle: '2026-10-09' })
    if (id === 4) Object.assign(db[4], { date_mise_en_service: '2026-10-10', mes_tension: 400 })
  }
})
afterEach(() => { cleanup() })

describe('InstallationDetail — ACHT57 diff + resynchronisation', () => {
  it.each([
    [1, 'planifie', 'date_pose_prevue', '2026-10-20'],
    [2, 'installe', 'date_pose_reelle', '2026-10-09'],
  ])('chantier %i : avancer au stepper puis modifier Notes ne recule pas le statut', async (id, statut, dateKey, dateVal) => {
    const user = userEvent.setup()
    renderDetail(db[id])
    await user.click(await screen.findByRole('tab', { name: /Jalons/ }))
    await user.click(await screen.findByRole('button', { name: 'Avancer (stepper)' }))
    await user.click(screen.getByRole('tab', { name: /Aperçu/ }))
    await user.type(await screen.findByLabelText('Notes'), 'RAS')
    await user.click(screen.getByRole('button', { name: 'Mettre à jour' }))
    await waitFor(() => expect(db[id].notes).toBe('RAS'))
    expect(db[id].statut).toBe(statut)
    expect(db[id][dateKey]).toBe(dateVal)
  })

  it('chantier clôturé : champ gelé grisé et enregistrement réussi', async () => {
    const user = userEvent.setup()
    renderDetail(db[3])
    expect(await screen.findByLabelText('Puissance installée (kWc)')).toBeDisabled()
    await user.type(screen.getByLabelText('Notes'), 'Clos')
    await user.click(screen.getByRole('button', { name: 'Mettre à jour' }))
    await waitFor(() => expect(db[3].notes).toBe('Clos'))
    expect(db[3].puissance_installee_kwc).toBe(6.5)
    expect(screen.queryByText(/Champ gelé/)).toBeNull()
  })

  // ACHT102 — le formulaire « mise en service » suit le serveur comme `fields`.
  it('le formulaire mes suit le serveur après refresh et garde la saisie en cours', async () => {
    const user = userEvent.setup()
    renderDetail(db[4])
    await user.click(await screen.findByRole('tab', { name: /Jalons/ }))
    await user.type(await screen.findByLabelText('Production test'), '12')
    await user.click(await screen.findByRole('button', { name: 'Avancer (stepper)' }))
    await waitFor(() => expect(screen.getByLabelText('Date de mise en service')).toHaveValue('2026-10-10'))
    expect(screen.getByLabelText('Tension')).toHaveValue(400)
    expect(screen.getByLabelText('Production test')).toHaveValue(12)
  })
})

describe('InstallationDetail — ACHT67 divergence_devis servi par le détail', () => {
  it('aucune bannière quand le serveur dit diverge:false', async () => {
    renderDetail(db[6])
    await screen.findByRole('tab', { name: /Jalons/ })
    expect(screen.queryByText(/Devis modifié/)).toBeNull()
  })

  it('bannière listant les lignes en écart quand diverge:true (rien recalculé côté écran)', async () => {
    renderDetail(db[5])
    expect(await screen.findByText(/Devis modifié/)).toBeInTheDocument()
    expect(screen.getByText(/Panneau monocristallin 550 Wc : 10 gelés \/ 14 au devis/)).toBeInTheDocument()
  })
})

describe('InstallationDetail — APRF37 détail relu à l’ouverture', () => {
  it('une ligne de liste SANS régime ni calepinage affiche « Suggéré » et la carte après lecture du détail', async () => {
    renderDetail({ id: 7, reference: 'CH-7', statut: 'planifie', annule: false, notes: '',
      regime_suggere: null, calepinage: null, dossier_8221_resume: null })
    expect(await screen.findByText('Accord de raccordement')).toBeInTheDocument()
    expect(screen.getByText('Calepinage retenu')).toBeInTheDocument()
  })
})
