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
/* ACAL2023 — la conception COURANTE servie par le design-context (`chiffrage`) : la vue client la lit, ne calcule rien. */
const CHIFFRAGE = {
  marche: 'residentiel', regles_calcul: 15,
  kwc: { valeur: 1.1, unite: 'kWc', source: 'conception', etat: 'servi' },
  production_annuelle_kwh: { valeur: 11480.4, unite: 'kWh/an', source: 'calepinage_enregistre', etat: 'servi' },
  economie_annee1_mad: { valeur: 7420, unite: 'MAD', source: 'conception', etat: 'servi', option: 'sans_batterie' },
  autoconsommation_pct: { valeur: 60, unite: '%', source: 'conception', etat: 'servi' },
  couverture_pct: { valeur: 82, unite: '%', source: 'conception', etat: 'servi' },
  omissions: [],
}
const contexteAvec = (chiffrage) => {
  const ctx = exempleContrat('calepinage', 'calepinage_design_context')
  return { data: { ...ctx, calepinage: { ...ctx.calepinage, titre: 'Villa Bennani', client_ville: 'Casablanca' }, chiffrage } }
}
const api = calepinageApi.calepinages
// Le chunk de l'atelier (lazy) se charge sous charge en plus d'1 s (délai par défaut de findBy) : 15 s.
const ATTENTE_ATELIER = { timeout: 15000 }

const rendre = (props = { webgl: false }) => render(
  <MemoryRouter initialEntries={['/calepinage/7/client']}>
    <Routes><Route path="/calepinage/:id/client" element={<VueClient {...props} />} /></Routes>
  </MemoryRouter>,
)

/** Les chiffres de la carte bleu nuit, dans l'ordre du DOM : la production en grand d'abord, puis les autres. */
const chiffres = () => {
  const carte = screen.queryByTestId('client-tuiles')
  return carte ? [...carte.querySelectorAll('[data-testid^="client-tuile-"]')] : []
}

/** Le bureau (grand écran ≥ 1024 px) : `matchMedia` répond « vrai » à sa requête. */
function auBureau() {
  window.matchMedia = vi.fn((requete) => ({
    matches: requete === '(min-width: 1024px)', media: requete,
    addEventListener: () => {}, removeEventListener: () => {},
  }))
}

beforeEach(() => {
  vi.clearAllMocks()
  reinitialiserBoot()
  api.layout.mockResolvedValue({ data: { roof_layout: { zones: [ZONE], activeAreaId: 'z1' }, empreinte_document: 'e' } })
  // Le contexte COMMITTÉ (contrat), au titre et à la ville de la maquette.
  api.designContext.mockResolvedValue(contexteAvec(CHIFFRAGE))
  api.resultat.mockResolvedValue({ data: RESULTAT })
})
afterEach(() => { cleanup(); oublierLecturesServies(); delete window.matchMedia })

describe('Montrer au client — repli 2D, avec les seules données servies', () => {
  it('toit enregistré dessiné, puce du projet, trois tuiles dans l’ordre (la médiane marine), pied', async () => {
    rendre()
    const plan = await screen.findByTestId('client-plan')
    expect(plan.querySelectorAll('.cal-client-pan')).toHaveLength(1)
    expect(plan.querySelectorAll('.cal-client-module')).toHaveLength(2)
    expect(await screen.findByTestId('client-projet')).toHaveTextContent('Villa Bennani')
    // J1 — l'orientation lue sur la face SERVIE du pan (azimut 180°), jamais son libellé.
    expect(screen.getByTestId('client-projet')).toHaveTextContent('Casablanca · pan sud')
    await waitFor(() => expect(chiffres()).toHaveLength(3))
    // ACAL1837 — UNE carte bleu nuit : la production en grand d'abord, puis les panneaux et la couverture.
    const tuiles = chiffres()
    expect(tuiles.map((t) => t.dataset.testid)).toEqual(['client-tuile-kwh', 'client-tuile-panneaux', 'client-tuile-couverture'])
    expect(screen.getByTestId('client-tuiles').tagName).toBe('SECTION')
    expect(tuiles[0].textContent.replace(/\s/g, ' ')).toMatch(/^11.480Estimation ?kWh par an$/)
    expect(tuiles[0].querySelector('.cal-client-marine-gros')).toHaveTextContent(/^11.480$/)
    expect(tuiles[1]).toHaveTextContent('2panneaux')
    expect(tuiles[2]).toHaveTextContent('82 %')
    expect(screen.getByText('Estimation pour une année moyenne à Casablanca. Les montants figurent dans le devis.')).toBeInTheDocument()
    expect(screen.getByTestId('client-retour-releve')).toHaveTextContent('Retour au relevé')
    expect(screen.getByTestId('client-retour-releve').getAttribute('href')).toBe('/calepinage/7/releve')
    expect(screen.getByTestId('cal-vue-client').textContent).not.toMatch(/MAD|DH|prix|marge/i)
  })

  it('H2 / ACAL2023 — conception non servie (borne haute publiée) : ni production ni couverture devant le client ; restent panneaux et puissance', async () => {
    api.designContext.mockResolvedValue(contexteAvec(null))
    api.resultat.mockResolvedValue({ data: {
      ...RESULTAT,
      production: { total: { p50_kwh: 52695.1, complete: false, mention: 'borne haute — 17 pertes non renseignées' } },
    } })
    rendre()
    await waitFor(() => expect(chiffres()).toHaveLength(2))
    const tuiles = chiffres()
    expect(tuiles.map((t) => t.dataset.testid)).toEqual(['client-tuile-panneaux', 'client-tuile-kwc'])
    expect(tuiles[1]).toHaveTextContent('1,10kWc de puissance') // la pose servie du document (2 panneaux dessinés)
    expect(screen.getByTestId('client-tuiles').querySelector('.cal-client-pilule')).toBeNull() // pas de production : pas de pilule
    const texte = screen.getByTestId('cal-vue-client').textContent
    expect(texte).not.toMatch(/52.695|kWh|estimation|année moyenne|%/)
  })

  it('H2 — les lectures sont partagées : un seul design-context, un seul résultat, un seul document', async () => {
    rendre()
    await waitFor(() => expect(chiffres()).toHaveLength(3))
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
    await waitFor(() => expect(chiffres()).toHaveLength(3))
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

  it('ACAL1906 — le curseur d’heure du client se touche sur 44 px, la carte garde sa hauteur (aucune règle du client ne l’annule)', async () => {
    const { readFileSync } = await import('node:fs')
    const style = document.createElement('style')
    style.textContent = ['49-jetons-v2.css', '50-coque-atelier.css', '52-etape-panneaux.css', '58-telephone.css']
      .map((f) => readFileSync(`${globalThis.process.cwd()}/src/styles/calepinage/${f}`, 'utf8')).join('\n')
    document.head.appendChild(style)
    try {
      reinitialiserBoot({ appliquerVue: vi.fn() })
      rendre({ webgl: true })
      const lecteur = await screen.findByTestId('client-soleil', {}, ATTENTE_ATELIER)
      const c = getComputedStyle(within(lecteur).getByRole('slider', { name: 'Heure du soleil' }))
      expect(parseFloat(c.height)).toBeGreaterThanOrEqual(44)
      expect(parseFloat(c.height) + parseFloat(c.marginTop) + parseFloat(c.marginBottom)).toBe(6)
    } finally {
      style.remove()
    }
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
      vue: 'trois-quarts', cadrage: expect.objectContaining({ zoomMax: 22, part: 0.8, cielPx: 150 }),
    })))
    // ACAL1839 — la zone libre est MESURÉE à chaque cadrage : au téléphone, le corps couvre le bas de la carte.
    const cadrage = modePresentation.mock.calls[0][1].cadrage
    const boite = (top, left, width, height) => ({ top, left, width, height, bottom: top + height, right: left + width, x: left, y: top })
    const carteEl = document.getElementById('rp9-map')
    const corps = screen.getByTestId('cal-vue-client')
    vi.spyOn(carteEl, 'getBoundingClientRect').mockReturnValue(boite(0, 0, 390, 844))
    vi.spyOn(corps, 'getBoundingClientRect').mockReturnValue(boite(385, 0, 390, 459))
    vi.spyOn(screen.getByTestId('client-projet'), 'getBoundingClientRect').mockReturnValue(boite(20, 20, 280, 56))
    expect(cadrage.margesPx).toEqual({ haut: 76, gauche: 0, droite: 0, bas: 459 })
    // Tant que la vue n'est pas posée et le toit cadré : le toit enregistré de dessus, dit en mots de client.
    expect(screen.getByTestId('client-repli-2d')).toBeInTheDocument()
    expect(screen.getByTestId('client-voir-3d')).toHaveTextContent('La vue 3D se prépare…')
    expect(screen.getByTestId('client-voir-3d').closest('a')).toBeNull()
    act(() => prete())
    expect(await screen.findByTestId('client-aide-geste')).toHaveTextContent('Glissez un doigt pour tourner autour')
    expect(screen.queryByTestId('client-repli-2d')).toBeNull()
    expect(screen.getByTestId('client-ciel').style.background).toContain('var(--cal-lien)') // ACAL1839 — le ciel, aux jetons
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

  it('« Glissez pour tourner autour » — la toile de la carte créée APRÈS l’ouverture (MapLibre tardif) redevient vivante ; l’atelier reste inerte', async () => {
    reinitialiserBoot({ appliquerVue: vi.fn() })
    rendre({ webgl: true })
    await screen.findByTestId('client-soleil', {}, ATTENTE_ATELIER)
    const carte = document.getElementById('rp9-map')
    // La carte encore vide à l'ouverture : sa branche est rendue inerte (aucune garde dedans).
    await waitFor(() => expect(carte.closest('[inert]')).not.toBeNull())
    // MapLibre crée sa toile ensuite, DANS la carte : la souris et le doigt doivent pouvoir la tourner.
    const toile = document.createElement('div')
    toile.className = 'maplibregl-canvas-container'
    toile.appendChild(document.createElement('canvas'))
    carte.appendChild(toile)
    await waitFor(() => expect(toile.closest('[inert]')).toBeNull())
    expect(carte.closest('[aria-hidden="true"]')).toBeNull()
    // Rien de ce qui édite ne redevient atteignable.
    for (const t of ['cal-rail-etapes', 'cal-barre-projet', 'cal-panneau-etape']) {
      expect(screen.getByTestId(t).closest('[inert]')).not.toBeNull()
    }
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
    await waitFor(() => expect(chiffres().length).toBeGreaterThan(0))
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
    await waitFor(() => expect(chiffres()).toHaveLength(3))
    const visible = texteVisible(screen.getByTestId('cal-coque'))
    expect(visible).not.toMatch(/MAD|DH\b|€|prix|marge|achat|Interne|Expert|Avancé|Enregistrer|Générer le devis/i)
    expect(visible).toContain('Envoyer le lien')
  })
})

describe('J1 — tuiles tenues hors de l’atelier, orientation certaine', () => {
  it('une lecture du résultat en échec est relue seule : la tuile de puissance arrive sans recharger la page', async () => {
    api.designContext.mockResolvedValue(contexteAvec(null)) // conception non servie : seuls les faits du document et du résultat
    api.resultat.mockRejectedValueOnce(Object.assign(new Error('timeout'), { code: 'ECONNABORTED' }))
    api.resultat.mockResolvedValue({ data: { ...RESULTAT, production: { total: { p50_kwh: 1, complete: false } } } })
    rendre()
    await waitFor(() => expect(chiffres()).toHaveLength(1))
    await waitFor(() => expect(chiffres()).toHaveLength(2), { timeout: 9000 })
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

/* ACAL2023 (D-ACAL-97 : un seul moteur ; T4-X2-007) — « Montrer au client » montre la conception COURANTE du lead : sa production et sa
   part « de votre consommation » sont celles du bloc `chiffrage` servi (les mêmes que l'atelier), pertes par défaut dites ; aucune
   estimation propre à la vue, ni lue sur l'atelier, ni calculée ; conception en cours : « calcul en cours », sans chiffre. */
describe('ACAL2023 — la vue client lit la conception courante servie', () => {
  const INCOMPLET = { ...RESULTAT, production: { total: { p50_kwh: 52695.1, complete: false } }, autoconsommation: { taux_couverture: 0.35 } }
  const sans = (cle) => Object.fromEntries(Object.entries(CHIFFRAGE).filter(([k]) => k !== cle))

  it('tuilesClient : production et part de la conception servie, JAMAIS celles du résultat publié (35 % ≠ 82 %) ni une estimation', async () => {
    const { tuilesClient } = await import('./vueClient.helpers')
    const document = { zones: [ZONE] }
    const tuiles = tuilesClient(document, RESULTAT, CHIFFRAGE)
    expect(tuiles.map((t) => t.cle)).toEqual(['panneaux', 'kwh', 'couverture'])
    expect(tuiles[1].valeur.replace(/\s/g, ' ')).toBe('11 480')
    expect(tuiles[1].libelle).toBe('kWh par an · estimation')
    expect(tuiles[1].nature).toBeUndefined() // pose réelle : pas de pertes par défaut à dire
    expect(tuiles[2].valeur).toBe('82 %') // la part SERVIE — le résultat publié disait 35 %
    expect(tuilesClient(document, INCOMPLET, CHIFFRAGE).find((t) => t.cle === 'couverture').valeur).toBe('82 %')
    // pertes par défaut (production de la ville, pas de la pose) : DITES
    const ville = { ...CHIFFRAGE, production_annuelle_kwh: { ...CHIFFRAGE.production_annuelle_kwh, source: 'standard_ville' } }
    expect(tuilesClient(document, RESULTAT, ville).find((t) => t.cle === 'kwh').nature).toBe('pertes')
    // sans part servie : aucune couverture (jamais celle du résultat publié)
    expect(tuilesClient(document, RESULTAT, sans('couverture_pct')).map((t) => t.cle)).toEqual(['panneaux', 'kwh'])
    // sans conception servie : les faits du document seulement ; en cours de calcul : « calcul en cours », sans chiffre
    expect(tuilesClient(document, RESULTAT, null).map((t) => t.cle)).toEqual(['panneaux', 'kwc'])
    const enCours = { ...CHIFFRAGE, production_annuelle_kwh: { valeur: null, unite: 'kWh/an', source: null, etat: 'omis' },
      omissions: [{ grandeur: 'production_annuelle_kwh', motif: 'premier calcul de la conception en cours' }] }
    const attente = tuilesClient(document, RESULTAT, enCours)
    expect(attente.map((t) => t.cle)).toEqual(['panneaux', 'calcul', 'kwc'])
    expect(attente.find((t) => t.cle === 'calcul').valeur).toBe('calcul en cours')
    expect(attente.find((t) => t.cle === 'kwh')).toBeUndefined()
  })

  it('B1 — conception d’une AUTRE taille que la pose : aucun nombre de production ni de couverture, une phrase vraie ; même taille : les nombres', async () => {
    const { tuilesClient } = await import('./vueClient.helpers')
    const document = { zones: [ZONE] } // 2 panneaux posés, pose de 1,1 kWc
    const autre = { ...CHIFFRAGE, kwc: { ...CHIFFRAGE.kwc, valeur: 21.6 } } // conception de 48 panneaux
    const tuiles = tuilesClient(document, RESULTAT, autre)
    expect(tuiles.find((t) => t.cle === 'kwh')).toBeUndefined()
    expect(tuiles.find((t) => t.cle === 'couverture')).toBeUndefined()
    expect(tuiles.map((t) => t.valeur).join(' ')).not.toMatch(/11.480|82/)
    expect(tuiles.find((t) => t.cle === 'miseajour').libelle).toBe('Production : calculée à la mise à jour de la conception.')
    expect(tuiles.find((t) => t.cle === 'panneaux').valeur).toBe('2')
    // taille de la conception non servie : rien ne prouve la même taille ⇒ aucun nombre non plus
    expect(tuilesClient(document, RESULTAT, sans('kwc')).find((t) => t.cle === 'kwh')).toBeUndefined()
    // même taille (écart < 0,005) : les nombres de la conception
    const egale = { ...CHIFFRAGE, kwc: { ...CHIFFRAGE.kwc, valeur: 1.1004 } }
    expect(tuilesClient(document, RESULTAT, egale).map((t) => t.cle)).toEqual(['panneaux', 'kwh', 'couverture'])
    // aucune conception : comme avant
    expect(tuilesClient(document, RESULTAT, null).map((t) => t.cle)).toEqual(['panneaux', 'kwc'])
  })

  it('B1 — à l’écran : la phrase remplace la production et la part ; pas un chiffre de l’autre taille', async () => {
    api.designContext.mockResolvedValue(contexteAvec({ ...CHIFFRAGE, kwc: { ...CHIFFRAGE.kwc, valeur: 21.6 } }))
    rendre()
    await waitFor(() => expect(screen.getByTestId('client-mention-miseajour')).toHaveTextContent('Production : calculée à la mise à jour de la conception.'))
    expect(screen.queryByTestId('client-tuile-kwh')).toBeNull()
    expect(screen.queryByTestId('client-tuile-couverture')).toBeNull()
    expect(screen.getByTestId('cal-vue-client').textContent).not.toMatch(/11.480|82 %|kWh par an/)
  })

  it('3D : la production est celle de la conception, jamais l’estimation du constructeur ; les pertes par défaut sont dites', async () => {
    api.designContext.mockResolvedValue(contexteAvec({
      ...CHIFFRAGE, production_annuelle_kwh: { ...CHIFFRAGE.production_annuelle_kwh, source: 'standard_ville' },
    }))
    api.resultat.mockResolvedValue({ data: INCOMPLET })
    reinitialiserBoot({ appliquerVue: vi.fn(), ...apiBuilder() })
    rendre({ webgl: true })
    await screen.findByTestId('client-soleil', {}, ATTENTE_ATELIER)
    // Le constructeur de l'atelier publie son estimation dans « Recommandation » (`#rp9-reco-prod`) : la vue client ne la lit plus.
    let prod = document.getElementById('rp9-reco-prod')
    if (!prod) { prod = document.createElement('p'); prod.id = 'rp9-reco-prod'; document.body.appendChild(prod) }
    prod.textContent = '5 571 kWh/an'
    await waitFor(() => expect(screen.getByTestId('client-tuile-kwh')).toBeInTheDocument(), { timeout: 5000 })
    const tuile = screen.getByTestId('client-tuile-kwh')
    expect(tuile.textContent.replace(/\s/g, ' ')).toMatch(/^11 480Estimation ?kWh par an$/)
    expect(screen.getAllByTestId('client-tuile-kwh')).toHaveLength(1)
    expect(screen.getByTestId('client-mention-pertes')).toHaveTextContent('Estimation : pertes par défaut')
    expect(screen.getByTestId('client-tuile-couverture')).toHaveTextContent('82 %')
    expect(texteVisible(screen.getByTestId('cal-coque'))).not.toMatch(/5.571|52.695|au plus|borne haute/)
    prod.textContent = '—'
  })

  it('conception en cours de calcul : « calcul en cours », aucun chiffre de production ni de couverture (repli 2D)', async () => {
    api.designContext.mockResolvedValue(contexteAvec({
      ...CHIFFRAGE, production_annuelle_kwh: { valeur: null, unite: 'kWh/an', source: null, etat: 'omis' },
      couverture_pct: { valeur: null, unite: '%', source: null, etat: 'omis' },
      omissions: [{ grandeur: 'production_annuelle_kwh', motif: 'premier calcul de la conception en cours' }],
    }))
    rendre()
    await waitFor(() => expect(screen.getByTestId('client-tuile-calcul')).toHaveTextContent('calcul en cours'))
    expect(screen.queryByTestId('client-tuile-kwh')).toBeNull()
    expect(screen.queryByTestId('client-tuile-couverture')).toBeNull()
    expect(screen.getByTestId('cal-vue-client').textContent).not.toMatch(/\d\s?%|kWh par an/)
  })
})

/* ACAL1837 — « Montrer au client » au téléphone sur sa maquette v2 : l'attente présentable, la carte bleu nuit,
   le pied (chevron, partage). Aucun chiffre ni prix de plus : seules les données servies. */
describe('ACAL1837 — le téléphone sur sa maquette v2', () => {
  it('en attente de la 3D : un ciel et une silhouette, aucun plan technique ; le plan dessus revient à l’échec', async () => {
    const modePresentation = vi.fn(() => true) // jamais « prête » : la vue de trois quarts n'est pas posée
    reinitialiserBoot({ appliquerVue: vi.fn(), modePresentation, cadrerToit: vi.fn(() => true) })
    rendre({ webgl: true })
    await screen.findByTestId('client-soleil', {}, ATTENTE_ATELIER)
    expect(screen.getByTestId('client-repli-2d')).toBeInTheDocument()
    expect(within(screen.getByTestId('client-repli-2d')).getByTestId('client-attente')).toBeInTheDocument()
    expect(screen.queryByTestId('client-plan')).toBeNull()
    expect(screen.getByTestId('client-voir-3d')).toHaveTextContent('La vue 3D se prépare…')
  })

  it('sans WebGL (aucune 3D à attendre) : le plan dessus du toit enregistré, pas la silhouette', async () => {
    rendre({ webgl: false })
    expect(await screen.findByTestId('client-plan')).toBeInTheDocument()
    expect(screen.queryByTestId('client-attente')).toBeNull()
  })

  it('la carte bleu nuit groupe les chiffres : production en grand + pilule « Estimation », panneaux, couverture ; la mention est SOUS la carte', async () => {
    rendre()
    await waitFor(() => expect(chiffres()).toHaveLength(3))
    const carte = screen.getByTestId('client-tuiles')
    expect(carte).toHaveAttribute('aria-label', 'Votre installation en trois chiffres')
    expect(carte.querySelector('.cal-client-pilule')).toHaveTextContent('Estimation')
    expect(carte.querySelector('.cal-client-marine-unite')).toHaveTextContent(/^kWh par an$/)
    expect(carte.querySelectorAll('.cal-client-marine-grille [data-testid^="client-tuile-"]')).toHaveLength(2)
    expect(carte.querySelector('.cal-client-marine-sur')).toBeNull() // le sur-titre est celui du bureau
    const mention = screen.getByText('Estimation pour une année moyenne à Casablanca. Les montants figurent dans le devis.')
    expect(carte.contains(mention)).toBe(false)
  })

  it('la puce porte le pictogramme maison ; le pied : chevron « Retour au relevé » + « Envoyer le lien » dit pourquoi il est grisé, en entier', async () => {
    rendre()
    expect(await screen.findByTestId('client-projet')).toHaveTextContent('Villa Bennani')
    expect(screen.getByTestId('client-projet').querySelector('.cal-client-puce-icone svg')).not.toBeNull()
    expect(screen.getByTestId('client-retour-releve').querySelector('svg')).not.toBeNull()
    expect(screen.getByTestId('client-envoyer-lien').querySelector('svg')).not.toBeNull()
    expect(screen.getByTestId('client-lien-raison').textContent).toMatch(/Envoyer au client.*sections du devis s’y choisissent\.$/)
  })

  it('la feuille : rayon 26, carte nuit 22, conseil de geste 32 px, boutons du pied 54 px de rayon 15 — lus dans la feuille de style', async () => {
    const { readFileSync } = await import('node:fs')
    const style = document.createElement('style')
    style.textContent = ['49-jetons-v2.css', '50-coque-atelier.css', '58-telephone.css']
      .map((f) => readFileSync(`${globalThis.process.cwd()}/src/styles/calepinage/${f}`, 'utf8')).join('\n')
    document.head.appendChild(style)
    try {
      rendre()
      await waitFor(() => expect(chiffres()).toHaveLength(3))
      expect(getComputedStyle(document.querySelector('.cal-client-corps')).borderRadius).toBe('26px 26px 0 0')
      expect(getComputedStyle(screen.getByTestId('client-tuiles')).borderRadius).toBe('var(--cal-rayon-carte)')
      expect(getComputedStyle(screen.getByTestId('client-envoyer-lien')).height).toBe('54px')
      expect(getComputedStyle(screen.getByTestId('client-envoyer-lien')).borderRadius).toBe('15px')
      expect(getComputedStyle(screen.getByTestId('client-retour-releve')).height).toBe('54px')
    } finally {
      style.remove()
    }
  })
})

/* ACAL1838 — « Montrer au client » au BUREAU (≥ 1024 px, maquette Presentation) : mêmes pièces, autre disposition ; le pied
   mène à l'atelier ; la carte héros porte son sur-titre et la mention ; la barre du soleil a ses repères ; aucun prix. */
describe('ACAL1838 — le grand écran sur sa maquette v2', () => {
  it('au bureau, le pied mène à l’atelier (« Retour à l’atelier »), jamais au relevé ; « Envoyer le lien » reste grisé et dit pourquoi', async () => {
    auBureau()
    rendre()
    const retour = await screen.findByTestId('client-retour-atelier')
    expect(retour).toHaveTextContent('Retour à l’atelier')
    expect(retour.getAttribute('href')).toBe('/calepinage/7')
    expect(screen.queryByTestId('client-retour-releve')).toBeNull()
    expect(screen.getByTestId('cal-vue-client').textContent).not.toMatch(/Retour au relevé/)
    expect(screen.getByTestId('client-envoyer-lien')).toBeDisabled()
    expect(screen.getByTestId('client-lien-raison')).toBeInTheDocument()
  })

  it('la carte héros : « Votre toit produirait », la production, les chiffres servis et la mention DANS la carte ; aucun prix', async () => {
    auBureau()
    rendre()
    await waitFor(() => expect(chiffres()).toHaveLength(3))
    const carte = screen.getByTestId('client-tuiles')
    expect(carte.querySelector('.cal-client-marine-sur')).toHaveTextContent('Votre toit produirait')
    expect(carte.querySelector('.cal-client-marine-gros')).toHaveTextContent(/^11.480$/)
    expect(carte).toHaveTextContent('Estimation pour une année moyenne à Casablanca. Les montants figurent dans le devis.')
    expect(carte.textContent).not.toMatch(/MAD|DH\b|€|prix|marge|achat/i)
    expect(screen.getByTestId('cal-vue-client').textContent).not.toMatch(/MAD|DH\b|€|prix|marge|achat/i)
  })

  it('la barre du soleil : « Soleil », l’heure, des repères de la borne basse à la borne haute SERVIES, Hiver | Été ; le conseil dit « Glissez pour tourner autour »', async () => {
    auBureau()
    let prete = null
    const modePresentation = vi.fn((actif, vue) => { if (actif) prete = vue.surPrete; return actif })
    reinitialiserBoot({ appliquerVue: vi.fn(), modePresentation, cadrerToit: vi.fn(() => true) })
    rendre({ webgl: true })
    const lecteur = await screen.findByTestId('client-soleil', {}, ATTENTE_ATELIER)
    expect(within(lecteur).getByText('Soleil')).toBeInTheDocument()
    const reperes = [...lecteur.querySelectorAll('.cal-client-soleil-reperes span')].map((s) => s.textContent)
    expect(reperes).toEqual(['6 h', '9 h', '12 h', '15 h', '18 h'])
    expect(within(lecteur).getByRole('button', { name: 'Hiver' })).toBeInTheDocument()
    act(() => prete())
    expect(await screen.findByTestId('client-aide-geste')).toHaveTextContent(/^Glissez pour tourner autour$/)
    expect(await screen.findByTestId('client-retour-atelier')).toBeInTheDocument()
  })
})
