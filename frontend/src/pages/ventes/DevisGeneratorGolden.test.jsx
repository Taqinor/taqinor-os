// SPL40 — golden du générateur de devis : DOM + appels API de 9 scénarios,
// capturés sur le code ACTUEL avant tout déplacement (capture seule).
//
// Chaque scénario monte l'écran RÉEL (seules les API sont mockées : les 4
// modules métier + le transport axios des aperçus/pièces jointes, pour qu'aucun
// appel réseau ne réponde à un instant aléatoire), attend que le DOM se
// stabilise, puis fige `normalise(container.innerHTML)` dans
// generator/__golden__/<scénario>.html. Pour c, d, f, g, le test clique
// « Enregistrer » et fige le JSON des mock.calls des API d'écriture dans
// <scénario>.appels.txt (extension .txt : le parseur de plans tronque .json).
//
// Un golden ROUGE après un déplacement = un bug du déplacement : ne JAMAIS le
// régénérer pour faire passer (NE PAS FAIRE du groupe SPL). En CI
// (`CI=true vitest run`) vitest n'écrit aucun snapshot : un fichier manquant
// ou différent échoue.
//
// Limites connues : Recharts (ResponsiveContainer) ne rend rien sous jsdom,
// donc les props du graphique ne sont pas figées ; un onClick oublié ne change
// pas innerHTML — c'est SPL41 (gestes) qui le couvre.
//
// Run : npx vitest run src/pages/ventes/DevisGeneratorGolden.test.jsx
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { exempleContrat, reponseContrat } from '../../test/fixtures/contractSamples'
import {
  LEAD, monter, normalise, stabiliser, serialiserAppels, preparerEnvironnement, chargerNeuf,
  devisEnvoyeLesDeux, devisIndustrielMt, devisCommercialHotel,
  devisAgricolePompeCourbe, devisMultiVillas, devisAdminRegistre,
  devisResidentielEtudeHoraire,
} from './DevisGeneratorGoldenHarnais'

vi.mock('../../api/crmApi', () => import('./DevisGeneratorGoldenMocks').then((m) => m.mockApi('crmApi')))
vi.mock('../../api/stockApi', () => import('./DevisGeneratorGoldenMocks').then((m) => m.mockApi('stockApi')))
vi.mock('../../api/parametresApi', () => import('./DevisGeneratorGoldenMocks').then((m) => m.mockApi('parametresApi')))
vi.mock('../../api/ventesApi', () => import('./DevisGeneratorGoldenMocks').then((m) => m.mockApi('ventesApi')))
vi.mock('../../api/axios', () => import('./DevisGeneratorGoldenMocks').then((m) => m.mockApi('axios')))

const DOSSIER = './generator/__golden__'
// Écran lourd + attente de stabilité (~1 s de calme) : marge large pour un
// poste ou un runner chargé (le délai global de 20 s a été dépassé sous charge).
const DELAI_SCENARIO = 90000
const APPELS_ECRITURE = [
  'replaceLignesDevis', 'createDevisAtomic', 'patchEtudeParams',
  'poserOverrides', 'regenererOverride',
]

// Les fuseaux du poste et de la CI diffèrent : on fige celui du produit.
globalThis.process.env.TZ = 'Africa/Casablanca'

async function capturerDom(container, nom) {
  const html = await stabiliser(container)
  await expect(normalise(html)).toMatchFileSnapshot(`${DOSSIER}/${nom}.html`)
}

async function enregistrerEtCapturer(ventesApi, nom, attendu) {
  const bouton = await screen.findByRole('button', { name: /Enregistrer les modifications/ })
  await userEvent.click(bouton)
  await waitFor(() => expect(ventesApi[attendu]).toHaveBeenCalled(), { timeout: 5000 })
  await expect(serialiserAppels(ventesApi, APPELS_ECRITURE))
    .toMatchFileSnapshot(`${DOSSIER}/${nom}.appels.txt`)
}

beforeEach(() => preparerEnvironnement())

afterEach(() => {
  vi.useRealTimers()
})

describe('SPL40 — golden du générateur (DOM + appels)', () => {
  it('(a) résidentiel, création vierge', async () => {
    const { DevisGenerator } = await chargerNeuf()
    const { container } = monter(DevisGenerator, '/ventes/devis/nouveau')
    await screen.findByRole('radio', { name: /Résidentiel/ })
    await capturerDom(container, 'a-residentiel-creation')
  }, DELAI_SCENARIO)

  it('(b) création depuis ?lead=', async () => {
    const { crmApi, DevisGenerator } = await chargerNeuf()
    crmApi.getLeads.mockResolvedValue({ data: [LEAD] })
    crmApi.getLead.mockResolvedValue({ data: LEAD })
    const { container } = monter(DevisGenerator, `/ventes/devis/nouveau?lead=${LEAD.id}`)
    // Le lead (résidentiel) est appliqué depuis la liste dès qu'elle et le
    // catalogue sont arrivés : son nom apparaît dans l'écran.
    await waitFor(() => expect(container.textContent).toContain(LEAD.prenom))
    await capturerDom(container, 'b-creation-depuis-lead')
  }, DELAI_SCENARIO)

  it('(c) ?edit= d’un devis envoyé « Les deux », reco « Sans batterie » + enregistrer', async () => {
    const { crmApi, ventesApi, DevisGenerator } = await chargerNeuf()
    const devis = devisEnvoyeLesDeux()
    crmApi.getLead.mockResolvedValue({ data: LEAD })
    ventesApi.getDevisById.mockResolvedValue({ data: devis })
    const { container } = monter(DevisGenerator, `/ventes/devis/nouveau?edit=${devis.id}`)
    await waitFor(() => expect(crmApi.getLead).toHaveBeenCalledWith(LEAD.id))
    await capturerDom(container, 'c-edition-envoye-les-deux')
    await enregistrerEtCapturer(ventesApi, 'c-edition-envoye-les-deux', 'replaceLignesDevis')
  }, DELAI_SCENARIO)

  it('(d) industriel MT + enregistrer', async () => {
    const { ventesApi, DevisGenerator } = await chargerNeuf()
    const devis = devisIndustrielMt()
    ventesApi.getDevisById.mockResolvedValue({ data: devis })
    ventesApi.etudeCiPreview.mockResolvedValue(reponseContrat('ventes', 'etude_ci_preview'))
    ventesApi.economieCiPreview.mockResolvedValue(reponseContrat('ventes', 'economie_ci'))
    const { container } = monter(DevisGenerator, `/ventes/devis/nouveau?edit=${devis.id}`)
    await waitFor(() =>
      expect(screen.getByRole('radio', { name: /Industriel/ })).toHaveAttribute('aria-checked', 'true'))
    await capturerDom(container, 'd-industriel-mt')
    await enregistrerEtCapturer(ventesApi, 'd-industriel-mt', 'replaceLignesDevis')
  }, DELAI_SCENARIO)

  it('(e) commercial hôtel', async () => {
    const { ventesApi, DevisGenerator } = await chargerNeuf()
    const devis = devisCommercialHotel()
    ventesApi.getDevisById.mockResolvedValue({ data: devis })
    ventesApi.etudeCiPreview.mockResolvedValue(reponseContrat('ventes', 'etude_ci_preview'))
    ventesApi.economieCiPreview.mockResolvedValue(reponseContrat('ventes', 'economie_ci'))
    const { container } = monter(DevisGenerator, `/ventes/devis/nouveau?edit=${devis.id}`)
    await waitFor(() =>
      expect(screen.getByRole('radio', { name: /Commercial/ })).toHaveAttribute('aria-checked', 'true'))
    await capturerDom(container, 'e-commercial-hotel')
  }, DELAI_SCENARIO)

  it('(f) agricole, pompe à courbe + enregistrer', async () => {
    const { ventesApi, api, DevisGenerator } = await chargerNeuf()
    const devis = devisAgricolePompeCourbe()
    ventesApi.getDevisById.mockResolvedValue({ data: devis })
    const pompage = exempleContrat('ventes', 'etude_pompage_preview')
    api.post.mockImplementation((url) => Promise.resolve(
      { data: String(url).includes('etude-pompage') ? pompage : null }))
    const { container } = monter(DevisGenerator, `/ventes/devis/nouveau?edit=${devis.id}`)
    await waitFor(() =>
      expect(screen.getByRole('radio', { name: /Agricole/ })).toHaveAttribute('aria-checked', 'true'))
    await capturerDom(container, 'f-agricole-pompe-courbe')
    await enregistrerEtCapturer(ventesApi, 'f-agricole-pompe-courbe', 'replaceLignesDevis')
  }, DELAI_SCENARIO)

  it('(g) multi-villas + enregistrer', async () => {
    const { ventesApi, DevisGenerator } = await chargerNeuf()
    const devis = devisMultiVillas()
    ventesApi.getDevisById.mockResolvedValue({ data: devis })
    const { container } = monter(DevisGenerator, `/ventes/devis/nouveau?edit=${devis.id}`)
    await screen.findByRole('columnheader', { name: 'Villa' })
    await capturerDom(container, 'g-multi-villas')
    await enregistrerEtCapturer(ventesApi, 'g-multi-villas', 'replaceLignesDevis')
  }, DELAI_SCENARIO)

  it('(h) admin, registre de surcharges non vide', async () => {
    const { ventesApi, DevisGenerator } = await chargerNeuf()
    const devis = devisAdminRegistre()
    ventesApi.getDevisById.mockResolvedValue({ data: devis })
    ventesApi.lireOverrides.mockResolvedValue(reponseContrat('ventes', 'devis_overrides'))
    const { container } = monter(DevisGenerator, `/ventes/devis/nouveau?edit=${devis.id}`,
      { role: 'admin' })
    await screen.findByTestId('overrides-panel')
    await capturerDom(container, 'h-admin-registre')
  }, DELAI_SCENARIO)

  it('(i) résidentiel, aperçu d’étude horaire serveur', async () => {
    const { ventesApi, DevisGenerator } = await chargerNeuf()
    const devis = devisResidentielEtudeHoraire()
    ventesApi.getDevisById.mockResolvedValue({ data: devis })
    ventesApi.postEtudeHorairePreview.mockResolvedValue(reponseContrat('ventes', 'etude_horaire'))
    const { container } = monter(DevisGenerator, `/ventes/devis/nouveau?edit=${devis.id}`)
    await waitFor(() => expect(ventesApi.postEtudeHorairePreview).toHaveBeenCalled(),
      { timeout: 5000 })
    await capturerDom(container, 'i-residentiel-etude-horaire')
  }, DELAI_SCENARIO)
})
