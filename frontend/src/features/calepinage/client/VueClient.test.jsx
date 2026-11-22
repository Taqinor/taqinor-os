import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, within, fireEvent, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { exempleContrat } from '../../../test/fixtures/contractSamples'

/* « Montrer au client » (maquette TelephoneClient).
   1. Repli 2D (L7 — pas de WebGL, ou le temps du démarrage) : le toit ENREGISTRÉ dessiné (jamais une
      image d'exemple), les tuiles dans l'ordre de la maquette et seulement avec des données servies, le
      partage désactivé AVEC sa raison, aucun montant.
   2. Mode présentation (L8, ACAL1314) : l'ATELIER lui-même (même écran ToitureDesign, constructeur simulé
      du harnais), en lecture seule ; bandeau, rail et panneau masqués ; le soleil renvoyé aux VRAIS
      contrôles du constructeur ; AUCUNE requête d'écriture au chargement ni en bougeant le soleil ;
      aucun chiffre d'argent ni libellé interne dans ce qui est visible. */

vi.mock('../../../hooks/useHasPermission', () => ({ useHasPermission: () => false }))
await import('../../../test/toitureDesignHarnessCalepinage')
const { reinitialiserBoot, apiBuilder } = await import('../../../test/toitureDesignHarness')
const { default: calepinageApi } = await import('../../../api/calepinageApi')
const { default: ventesApi } = await import('../../../api/ventesApi')
const { default: axios } = await import('../../../api/axios')
const { default: VueClient } = await import('./VueClient')
const { oublierLecturesServies } = await import('../atelier/coque/etapes/panneaux/lectures')

const ZONE = {
  id: 'z1', label: 'Pan sud',
  vertices: [[-7.6, 33.5], [-7.5998, 33.5], [-7.5998, 33.5001], [-7.6, 33.5001]],
  geometry: { origin: [-7.5999, 33.50005], panels: [{ cx: -1, cy: 0 }, { cx: 1, cy: 0 }], tiltDeg: 20, azimuthDeg: 180 },
}
const RESULTAT = {
  simule: true, simulation_perimee: false,
  pose: { total_modules: 2, kwc: 1.1 },
  production: { total: { p50_kwh: 11480.4, complete: true } },
  autoconsommation: { taux_couverture: 0.82 },
}
const api = calepinageApi.calepinages
// Le chunk de l'atelier (lazy) se charge sous charge en plus d'1 s (délai par défaut de findBy) : 15 s.
const ATTENTE_ATELIER = { timeout: 15000 }

const rendre = (props = { webgl: false }) => render(
  <MemoryRouter initialEntries={['/calepinage/7/client']}>
    <Routes><Route path="/calepinage/:id/client" element={<VueClient {...props} />} /></Routes>
  </MemoryRouter>,
)

beforeEach(() => {
  vi.clearAllMocks()
  reinitialiserBoot()
  api.layout.mockResolvedValue({ data: { roof_layout: { zones: [ZONE], activeAreaId: 'z1' }, empreinte_document: 'e' } })
  // Le contexte COMMITTÉ (contrat), au titre et à la ville de la maquette.
  const ctx = exempleContrat('calepinage', 'calepinage_design_context')
  api.designContext.mockResolvedValue({
    data: { ...ctx, calepinage: { ...ctx.calepinage, titre: 'Villa Bennani', client_ville: 'Casablanca' } },
  })
  api.resultat.mockResolvedValue({ data: RESULTAT })
})
afterEach(() => { cleanup(); oublierLecturesServies() })

describe('Montrer au client — repli 2D, avec les seules données servies', () => {
  it('toit enregistré dessiné, puce du projet, trois tuiles dans l’ordre (la médiane marine), pied', async () => {
    rendre()
    const plan = await screen.findByTestId('client-plan')
    expect(plan.querySelectorAll('.cal-client-pan')).toHaveLength(1)
    expect(plan.querySelectorAll('.cal-client-module')).toHaveLength(2)
    expect(await screen.findByTestId('client-projet')).toHaveTextContent('Villa Bennani')
    // J1 — l'orientation lue sur la face SERVIE du pan (azimut 180°), jamais son libellé.
    expect(screen.getByTestId('client-projet')).toHaveTextContent('Casablanca · pan sud')
    await waitFor(() => expect(screen.getByTestId('client-tuiles').children).toHaveLength(3))
    const tuiles = [...screen.getByTestId('client-tuiles').children]
    expect(tuiles.map((t) => t.dataset.testid)).toEqual(['client-tuile-panneaux', 'client-tuile-kwh', 'client-tuile-couverture'])
    expect(tuiles[0]).toHaveTextContent('2panneaux')
    expect(tuiles[1].textContent.replace(/\s/g, ' ')).toMatch(/^11.480kWh par an · estimation$/)
    expect(tuiles[1].className).toContain('cal-client-tuile-marine')
    expect(tuiles[2]).toHaveTextContent('82 %')
    expect(screen.getByText('Estimation pour une année moyenne à Casablanca. Les montants figurent dans le devis.')).toBeInTheDocument()
    expect(screen.getByTestId('client-retour-releve')).toHaveTextContent('Retour au relevé')
    expect(screen.getByTestId('client-retour-releve').getAttribute('href')).toBe('/calepinage/7/releve')
    expect(screen.getByTestId('cal-vue-client').textContent).not.toMatch(/MAD|DH|prix|marge/i)
  })

  it('H2 — résultat publié INCOMPLET (borne haute) : ni production ni couverture devant le client ; restent panneaux et puissance', async () => {
    api.resultat.mockResolvedValue({ data: {
      ...RESULTAT,
      production: { total: { p50_kwh: 52695.1, complete: false, mention: 'borne haute — 17 pertes non renseignées' } },
    } })
    rendre()
    await waitFor(() => expect(screen.getByTestId('client-tuiles').children).toHaveLength(2))
    const tuiles = [...screen.getByTestId('client-tuiles').children]
    expect(tuiles.map((t) => t.dataset.testid)).toEqual(['client-tuile-panneaux', 'client-tuile-kwc'])
    expect(tuiles[1]).toHaveTextContent('1,10kWc de puissance') // la pose servie du document (2 panneaux dessinés)
    expect(tuiles[1].className).toContain('cal-client-tuile-marine')
    const texte = screen.getByTestId('cal-vue-client').textContent
    expect(texte).not.toMatch(/52.695|kWh|estimation|année moyenne|%/)
  })

  it('H2 — les lectures sont partagées : un seul design-context, un seul résultat, un seul document', async () => {
    rendre()
    await waitFor(() => expect(screen.getByTestId('client-tuiles').children).toHaveLength(3))
    expect(api.designContext).toHaveBeenCalledTimes(1)
    expect(api.resultat).toHaveBeenCalledTimes(1)
    expect(api.layout).toHaveBeenCalledTimes(1)
  })

  it('« Envoyer le lien » est désactivé et dit pourquoi, en français', async () => {
    rendre()
    const bouton = await screen.findByTestId('client-envoyer-lien')
    expect(bouton).toHaveTextContent('Envoyer le lien')
    expect(bouton).toBeDisabled()
    expect(bouton.getAttribute('aria-describedby')).toBe('client-lien-raison')
    expect(screen.getByTestId('client-lien-raison')).toHaveTextContent('« Envoyer au client »')
  })

  it('une simulation périmée retire les tuiles servies par elle ; sans toit, rien n’est dessiné', async () => {
    api.resultat.mockResolvedValue({ data: { ...RESULTAT, simulation_perimee: true } })
    api.layout.mockResolvedValue({ data: { roof_layout: {}, empreinte_document: '' } })
    rendre()
    expect(await screen.findByTestId('client-sans-toit')).toHaveTextContent('Aucun toit enregistré pour ce calepinage.')
    await waitFor(() => expect(api.resultat).toHaveBeenCalled())
    expect(screen.queryByTestId('client-tuiles')).toBeNull()
    expect(screen.queryByTestId('client-plan')).toBeNull()
  })
})

/* Les noms des méthodes d'API qui ÉCRIVENT (POST/PUT/PATCH/DELETE) : enregistrer, envoyer, effacer, créer,
   synchroniser, recentrer, réviser, partager… Toute méthode appelée doit être une lecture. */
const ECRITURE = /enregistr|envoy|effac|cre(e|r)|sync|recentr|revis|share|maj|suppr|delete|post|put|patch|ecri|ajout|depuis|valid|appliqu|rattach|lier|dupliq|archiv|copier/i

function appelsDEcriture() {
  const appels = []
  for (const [groupe, methodes] of Object.entries(calepinageApi)) {
    if (!methodes || typeof methodes !== 'object') continue
    for (const [nom, fn] of Object.entries(methodes)) {
      if (fn?.mock?.calls?.length && ECRITURE.test(nom)) appels.push(`calepinageApi.${groupe}.${nom}`)
    }
  }
  for (const [nom, fn] of Object.entries(ventesApi)) {
    if (fn?.mock?.calls?.length && !/^get/.test(nom)) appels.push(`ventesApi.${nom}`)
  }
  if (axios.post.mock.calls.length) appels.push('axios.post')
  return appels
}

/** Le texte VISIBLE : tout le DOM moins les sous-arbres `hidden` (ce que la coque masque). */
function texteVisible(racine) {
  const copie = racine.cloneNode(true)
  copie.querySelectorAll('[hidden]').forEach((n) => n.remove())
  return copie.textContent.replace(/\s+/g, ' ')
}

describe('Montrer au client — l’atelier en mode présentation (vraie 3D)', () => {
  it('le même atelier, en lecture seule : bandeau, rail et panneau masqués (montés), l’habillage autour', async () => {
    const appliquerVue = vi.fn()
    reinitialiserBoot({ appliquerVue })
    rendre({ webgl: true })
    const coque = await screen.findByTestId('cal-coque', {}, ATTENTE_ATELIER)
    expect(coque).toHaveAttribute('data-presentation', '1')
    // Montés mais masqués : les contrôles du constructeur restent là (le soleil leur est renvoyé).
    expect(screen.getByTestId('cal-barre-projet').hidden).toBe(true)
    expect(screen.getByTestId('cal-rail-etapes').hidden).toBe(true)
    expect(screen.getByTestId('cal-panneau-etape').hidden).toBe(true)
    expect(document.getElementById('rp9-map')).not.toBeNull()
    expect(document.getElementById('rp9-sun-hour')).not.toBeNull()
    // La 3D de trois-quarts est demandée au constructeur ; la puce du projet est posée sur la scène.
    await waitFor(() => expect(appliquerVue).toHaveBeenCalledWith('trois-quarts'))
    const scene = document.getElementById('rp9-studio-scene')
    expect(await within(scene).findByTestId('client-projet')).toHaveTextContent('Villa Bennani')
    // Les tuiles et le pied de la maquette.
    await waitFor(() => expect(screen.getByTestId('client-tuiles').children).toHaveLength(3))
    expect(screen.getByTestId('client-envoyer-lien')).toBeDisabled()
    // Aucun bouton d'enregistrement : l'atelier est en lecture seule.
    expect(screen.queryByTestId('cal-enregistrer-calepinage')).toBeNull()
  })

  it('le soleil : Été / Hiver et l’heure sont renvoyés aux VRAIS contrôles du constructeur', async () => {
    reinitialiserBoot({ appliquerVue: vi.fn() })
    rendre({ webgl: true })
    const lecteur = await screen.findByTestId('client-soleil', {}, ATTENTE_ATELIER)
    const ete = document.querySelector('[data-sun-season="summer"]')
    const clicEte = vi.fn()
    ete.addEventListener('click', clicEte)
    await userEvent.click(within(lecteur).getByRole('button', { name: 'Été' }))
    expect(clicEte).toHaveBeenCalledTimes(1)
    const heure = document.getElementById('rp9-sun-hour')
    const entree = vi.fn()
    heure.addEventListener('input', entree)
    fireEvent.change(within(lecteur).getByRole('slider', { name: 'Heure du soleil' }), { target: { value: '15' } })
    await waitFor(() => expect(entree).toHaveBeenCalled())
    expect(heure.value).toBe('15')
  })

  it('aucune requête d’écriture au chargement ni en bougeant le soleil', async () => {
    reinitialiserBoot({ appliquerVue: vi.fn() })
    rendre({ webgl: true })
    const lecteur = await screen.findByTestId('client-soleil', {}, ATTENTE_ATELIER)
    await waitFor(() => expect(api.designContext).toHaveBeenCalled())
    await userEvent.click(within(lecteur).getByRole('button', { name: 'Été' }))
    await userEvent.click(within(lecteur).getByRole('button', { name: 'Hiver' }))
    fireEvent.change(within(lecteur).getByRole('slider', { name: 'Heure du soleil' }), { target: { value: '9' } })
    // Laisse passer le sondage « scène modifiée » (1,5 s) et le planificateur de brouillon.
    await new Promise((r) => { setTimeout(r, 2000) })
    expect(appelsDEcriture()).toEqual([])
  })

  it('H6/J1 — la vue de trois quarts TENUE par le constructeur ; la 3D montrée quand elle est prête ; rendu à la sortie', async () => {
    let prete = null
    const modePresentation = vi.fn((actif, vue) => { if (actif) prete = vue.surPrete; return actif })
    reinitialiserBoot({ appliquerVue: vi.fn(), modePresentation, cadrerToit: vi.fn(() => true) })
    const { unmount } = rendre({ webgl: true })
    await screen.findByTestId('client-soleil', {}, ATTENTE_ATELIER)
    await waitFor(() => expect(modePresentation).toHaveBeenCalledWith(true, expect.objectContaining({
      vue: 'trois-quarts', cadrage: { zoomMax: 22, part: 0.62, cielPx: 190 },
    })))
    // Tant que la vue n'est pas posée et le toit cadré : le toit enregistré de dessus, dit en mots de client.
    expect(screen.getByTestId('client-repli-2d')).toBeInTheDocument()
    expect(screen.getByTestId('client-voir-3d')).toHaveTextContent('La vue 3D se prépare…')
    expect(screen.getByTestId('client-voir-3d').closest('a')).toBeNull()
    act(() => prete())
    expect(await screen.findByTestId('client-aide-geste')).toHaveTextContent('Glissez un doigt pour tourner autour')
    expect(screen.queryByTestId('client-repli-2d')).toBeNull()
    unmount()
    expect(modePresentation).toHaveBeenLastCalledWith(false)
  })

  it('J1 — l’atelier sous la vue client est inerte (ni Tab ni lecteur d’écran) ; la vue client reste vivante', async () => {
    reinitialiserBoot({ appliquerVue: vi.fn() })
    rendre({ webgl: true })
    await screen.findByTestId('client-soleil', {}, ATTENTE_ATELIER)
    await waitFor(() => expect(screen.getByTestId('cal-rail-etapes').closest('[inert]')).not.toBeNull())
    for (const t of ['cal-barre-projet', 'cal-panneau-etape']) {
      expect(screen.getByTestId(t).closest('[inert]')?.getAttribute('aria-hidden')).toBe('true')
    }
    for (const t of ['client-soleil', 'client-envoyer-lien', 'client-retour-releve', 'client-projet']) {
      expect(screen.getByTestId(t).closest('[inert]')).toBeNull()
    }
    // Les VRAIS contrôles du soleil restent montés (inertes) : la vue client les pilote toujours.
    expect(document.getElementById('rp9-sun-hour').closest('[inert]')).not.toBeNull()
  })

  it('J1 — ouverture en été à midi quand la scène porte l’instant par défaut du constructeur', async () => {
    api.layout.mockResolvedValue({ data: {
      roof_layout: { zones: [ZONE], activeAreaId: 'z1', scene: { sunDay: 355, sunHour: 12 } }, empreinte_document: 'e',
    } })
    const clicEte = vi.fn()
    document.addEventListener('click', (e) => { if (e.target?.dataset?.sunSeason === 'summer') clicEte() }, true)
    reinitialiserBoot({ appliquerVue: vi.fn() })
    rendre({ webgl: true })
    await screen.findByTestId('client-soleil', {}, ATTENTE_ATELIER)
    await waitFor(() => expect(clicEte).toHaveBeenCalledTimes(1))
  })

  it('J1 — un instant CHOISI par le commercial est gardé (aucun Été posé d’office)', async () => {
    api.layout.mockResolvedValue({ data: {
      roof_layout: { zones: [ZONE], activeAreaId: 'z1', scene: { sunDay: 100, sunHour: 15 } }, empreinte_document: 'e',
    } })
    const clicEte = vi.fn()
    const ecoute = (e) => { if (e.target?.dataset?.sunSeason === 'summer') clicEte() }
    document.addEventListener('click', ecoute, true)
    reinitialiserBoot({ appliquerVue: vi.fn() })
    rendre({ webgl: true })
    await screen.findByTestId('client-soleil', {}, ATTENTE_ATELIER)
    await waitFor(() => expect(screen.getByTestId('client-tuiles').children.length).toBeGreaterThan(0))
    await new Promise((r) => { setTimeout(r, 300) })
    document.removeEventListener('click', ecoute, true)
    expect(clicEte).not.toHaveBeenCalled()
  })

  it('H6 — un constructeur sans mode présentation : aucune aide de geste (un doigt n’y fait pas tourner)', async () => {
    reinitialiserBoot({ appliquerVue: vi.fn() })
    rendre({ webgl: true })
    await screen.findByTestId('client-soleil', {}, ATTENTE_ATELIER)
    await waitFor(() => expect(screen.getByTestId('client-projet')).toBeInTheDocument())
    expect(screen.queryByTestId('client-aide-geste')).toBeNull()
  })

  it('rien d’argent ni de libellé interne dans ce que voit le client', async () => {
    reinitialiserBoot({ appliquerVue: vi.fn(), ...apiBuilder() })
    rendre({ webgl: true })
    await screen.findByTestId('client-soleil', {}, ATTENTE_ATELIER)
    await waitFor(() => expect(screen.getByTestId('client-tuiles').children).toHaveLength(3))
    const visible = texteVisible(screen.getByTestId('cal-coque'))
    expect(visible).not.toMatch(/MAD|DH\b|€|prix|marge|achat|Interne|Expert|Avancé|Enregistrer|Générer le devis/i)
    expect(visible).toContain('Envoyer le lien')
  })
})

describe('J1 — tuiles tenues hors de l’atelier, orientation certaine', () => {
  it('une lecture du résultat en échec est relue seule : la tuile de puissance arrive sans recharger la page', async () => {
    api.resultat.mockRejectedValueOnce(Object.assign(new Error('timeout'), { code: 'ECONNABORTED' }))
    api.resultat.mockResolvedValue({ data: { ...RESULTAT, production: { total: { p50_kwh: 1, complete: false } } } })
    rendre()
    await waitFor(() => expect(screen.getByTestId('client-tuiles').children).toHaveLength(1))
    await waitFor(() => expect(screen.getByTestId('client-tuiles').children).toHaveLength(2), { timeout: 9000 })
    expect(api.resultat).toHaveBeenCalledTimes(2)
    expect(api.layout).toHaveBeenCalledTimes(1) // la lecture réussie n'est pas refaite
  })

  it('deux pans de faces différentes : aucune orientation dite ; deux pans au sud : « orienté sud »', async () => {
    const ouest = { ...ZONE, id: 'z2', geometry: { ...ZONE.geometry, azimuthDeg: 270 } }
    api.layout.mockResolvedValue({ data: { roof_layout: { zones: [ZONE, ouest] }, empreinte_document: 'e' } })
    rendre()
    await waitFor(() => expect(screen.getByTestId('client-projet')).toHaveTextContent('Casablanca'))
    await waitFor(() => expect(screen.getByTestId('client-plan')).toBeInTheDocument())
    expect(screen.getByTestId('client-projet').textContent).not.toMatch(/pan|orienté/)
    cleanup()
    oublierLecturesServies()
    api.layout.mockResolvedValue({ data: { roof_layout: { zones: [ZONE, { ...ZONE, id: 'z3' }] }, empreinte_document: 'e' } })
    rendre()
    await waitFor(() => expect(screen.getByTestId('client-projet')).toHaveTextContent('Casablanca · orienté sud'))
  })
})
