import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor, act, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import process from 'node:process'
import { resolve } from 'node:path'
import { creerRepere, metresVersLngLat } from '../repere'
import { ConfirmProvider } from '../../../providers/ConfirmProvider'

/* Écran neuf « Relevé de visite » au téléphone (maquette Telephone) : structure, ordre et
   libellés de la maquette ; replis honnêtes (pastille « Hors ligne » seulement hors ligne ou
   file non vide, « mesurée » seulement depuis le capteur) ; et la PREUVE que « Terminer le
   relevé » envoie le MÊME corps que le panneau de l'atelier (`PanneauReleve`). */

const RELEVE_COURANT = { id: 9, releve_le: '2026-11-20', notes: '', chaines: [], azimut: null, photos: [] }
const ZONE = { id: 'z1', label: 'Pan sud', vertices: [[-7.6, 33.5], [-7.5999, 33.5], [-7.5999, 33.5001]] }

const api = {
  releve: vi.fn(), get: vi.fn(), photos: vi.fn(), layout: vi.fn(),
  enregistrerReleve: vi.fn(), corrigerReleve: vi.fn(), supprimerReleve: vi.fn(),
  enregistrerSectionLayout: vi.fn(), appliquerCoteReleve: vi.fn(),
}
vi.mock('../../../api/calepinageApi', () => ({
  default: { calepinages: new Proxy({}, { get: (_, nom) => (...a) => api[nom](...a) }) },
}))
const file = { compterEnAttente: vi.fn(), deposerOuMettreEnFile: vi.fn(), rejouerFile: vi.fn() }
// Les photos sont simulées ; la file du RELEVÉ (ACAL1810) est la vraie (magasin en mémoire sous jsdom, comme sans IndexedDB).
vi.mock('../fileEnvoiPhotos', async (importOriginal) => ({
  ...(await importOriginal()),
  compterEnAttente: (...a) => file.compterEnAttente(...a),
  deposerOuMettreEnFile: (...a) => file.deposerOuMettreEnFile(...a),
  rejouerFile: (...a) => file.rejouerFile(...a),
}))
const capteurs = { demarrerCapteurs: vi.fn(), lireInclinaison: vi.fn(), lireVisee: vi.fn(), arreter: vi.fn() }
vi.mock('../capteursTelephone', () => ({
  demarrerCapteurs: (...a) => capteurs.demarrerCapteurs(...a),
  lireInclinaison: (...a) => capteurs.lireInclinaison(...a),
  lireVisee: (...a) => capteurs.lireVisee(...a),
  arreter: (...a) => capteurs.arreter(...a),
}))

const { oublierReleveEnFile, releveEnAttente } = await import('../fileEnvoiPhotos')
const { default: ReleveVisite } = await import('./ReleveVisite')
const { default: PanneauReleve } = await import('../atelier/PanneauReleve')

let enLigne = true
const rendre = () => render(
  <MemoryRouter initialEntries={['/calepinage/1/releve']}>
    <Routes><Route path="/calepinage/:id/releve" element={<ReleveVisite />} /></Routes>
  </MemoryRouter>,
)
const taper = (testId, valeur) => fireEvent.change(screen.getByTestId(testId), { target: { value: valeur } })

beforeEach(async () => {
  vi.clearAllMocks()
  await oublierReleveEnFile('1')
  enLigne = true
  Object.defineProperty(window.navigator, 'onLine', { configurable: true, get: () => enLigne })
  api.releve.mockResolvedValue({ data: { releves: [RELEVE_COURANT], releve_courant_id: 9 } })
  api.get.mockResolvedValue({ data: { nom: 'Calepinage 1', client: { nom: 'Villa Bennani', ville: '' }, lead: { nom: 'Bennani', ville: 'Casablanca' } } })
  api.photos.mockResolvedValue({ data: { photos: [{ id: 5, genre: 'drone', url: '/api/x/5/fichier/' }] } })
  api.layout.mockResolvedValue({ data: { roof_layout: { zones: [ZONE] }, empreinte_document: 'emp-1' } })
  api.corrigerReleve.mockResolvedValue({ data: { releve: { ...RELEVE_COURANT } } })
  api.enregistrerSectionLayout.mockResolvedValue({ data: { roof_layout: { zones: [ZONE] }, empreinte_document: 'emp-2' } })
  file.compterEnAttente.mockResolvedValue(0)
  file.rejouerFile.mockResolvedValue({ envoyees: 0, refusees: [], restantes: 0 })
  capteurs.demarrerCapteurs.mockResolvedValue({ indisponible: true, motif: 'Capteurs absents : saisissez l’azimut et la hauteur à la main.' })
})
afterEach(() => { cleanup() })

describe('Relevé de visite — la maquette, dans son ordre', () => {
  it('en-tête, photos, mesures, pente, orientation, pied : libellés mot pour mot et dans l’ordre', async () => {
    rendre()
    expect(await screen.findByTestId('releve-projet')).toHaveTextContent('Villa Bennani — Casablanca')
    expect(await screen.findByTestId('releve-photos-compte')).toHaveTextContent('1 sur 3')
    const texte = screen.getByTestId('cal-releve').textContent
    const attendus = ['Relevé de visite', 'Photos', '1 sur 3', 'Drone', 'Oblique (aérienne)', 'Depuis le sol',
      'Mesures', 'Longueur', 'Largeur', 'Pente du toit', 'Le toit regarde vers', 'Boussole', 'Voir en 3D', 'Terminer le relevé']
    let pos = -1
    for (const a of attendus) {
      const i = texte.indexOf(a, pos + 1)
      expect(i, `« ${a} » absent ou hors ordre`).toBeGreaterThan(pos)
      pos = i
    }
    // Catégorie sans photo = tuile pointillée qui ouvre l'appareil ; celle qui a sa photo, non.
    expect(screen.getByTestId('releve-photo-oblique').querySelector('input[type="file"]')).not.toBeNull()
    expect(screen.getByTestId('releve-photo-drone').querySelector('input[type="file"]')).toBeNull()
    expect(screen.queryByTestId('releve-hors-ligne')).toBeNull()
    expect(screen.queryByTestId('releve-note-hors-ligne')).toBeNull()
  })

  it('la pastille « Hors ligne » et la note portent le compte RÉEL de la file', async () => {
    file.compterEnAttente.mockResolvedValue(2)
    enLigne = false
    rendre()
    expect(await screen.findByTestId('releve-hors-ligne')).toHaveTextContent('Hors ligne')
    await waitFor(() => expect(screen.getByTestId('releve-note-hors-ligne'))
      .toHaveTextContent('2 photos gardées sur ce téléphone. Elles partiront dès le retour du réseau.'))
  })
})

describe('ACAL2002 — « Terminer le relevé » est le bouton doré v2', () => {
  it('lit les jetons du bouton d’étape : fond d’action, rayon 15, 700, ombre dorée', async () => {
    const { readFileSync } = await import('node:fs')
    const { resolve } = await import('node:path')
    const style = document.createElement('style')
    style.textContent = ['49-jetons-v2.css', '58-telephone.css']
      .map((f) => readFileSync(resolve(process.cwd(), `src/styles/calepinage/${f}`), 'utf8')).join('\n')
    document.head.appendChild(style)
    try {
      rendre()
      const bouton = await screen.findByTestId('releve-terminer')
      const cs = getComputedStyle(bouton)
      expect(cs.background).toContain('--cal-action')
      expect(cs.borderRadius).toBe('15px')
      expect(cs.boxShadow).toBe('var(--cal-action-ombre)')
      expect(cs.font).toContain('700')
    } finally { style.remove() }
  })
})

describe('Relevé de visite — « mesurée » seulement depuis le capteur', () => {
  it('une pente tapée à la main (capteur absent) se dit « saisie à la main », jamais « mesurée »', async () => {
    rendre()
    await screen.findByTestId('releve-projet')
    await waitFor(() => expect(screen.getByTestId('releve-pente-bouton')).not.toBeDisabled())
    fireEvent.click(screen.getByTestId('releve-pente-bouton'))
    taper(await screen.findByTestId('releve-pente-main').then(() => 'releve-pente-main'), '30')
    expect(screen.getByTestId('releve-pente-valeur')).toHaveTextContent('30° · saisie à la main')
    expect(screen.getByTestId('releve-pente-valeur').textContent).not.toMatch(/mesurée/)
  })

  it('le capteur donne « 24° · mesurée » et écrit la pente du pan comme SaisiePente (provenance telephone)', async () => {
    capteurs.demarrerCapteurs.mockResolvedValue({ ok: true })
    capteurs.lireInclinaison.mockReturnValue({ betaDeg: 24, gammaDeg: 0 })
    capteurs.lireVisee.mockReturnValue({ azimutDeg: 337.5, hauteurDeg: 0 })
    rendre()
    await waitFor(() => expect(screen.getByTestId('releve-pente-bouton')).not.toBeDisabled())
    fireEvent.click(screen.getByTestId('releve-pente-bouton'))
    await waitFor(() => expect(screen.getByTestId('releve-pente-valeur')).toHaveTextContent('24° mesurée'))
    fireEvent.click(screen.getByTestId('releve-terminer'))
    await waitFor(() => expect(api.corrigerReleve).toHaveBeenCalled())
    const [, corpsPente] = api.enregistrerSectionLayout.mock.calls[0]
    expect(corpsPente).toEqual({
      cle: 'zones', zone_id: 'z1', base_empreinte: 'emp-1',
      champs: { pitchDeg: expect.closeTo(24, 6), pitchSource: { mode: 'degres', degres: expect.closeTo(24, 6), provenance: 'telephone' } },
    })
  })
})

describe('Relevé de visite — même porte, même corps que le panneau de l’atelier', () => {
  it('Longueur, Largeur, orientation et précision partent dans le corps EXACT de PanneauReleve', async () => {
    // 1) Le panneau de l'atelier : deux chaînes à une cote, l'azimut et sa précision.
    render(<ConfirmProvider><MemoryRouter><PanneauReleve calepinageId={1} /></MemoryRouter></ConfirmProvider>)
    await waitFor(() => expect(screen.getByTestId('cal-releve-champ-releve_le').querySelector('input').value).toBe('2026-11-20'))
    const champ = (id) => screen.getByTestId(id).querySelector('input')
    fireEvent.change(champ('cal-releve-chaine-0-nom'), { target: { value: 'Longueur' } })
    fireEvent.change(champ('cal-releve-chaine-0-cote-0-nom'), { target: { value: 'Longueur' } })
    fireEvent.change(champ('cal-releve-chaine-0-cote-0-valeur'), { target: { value: '12.4' } })
    fireEvent.click(screen.getByTestId('cal-releve-chaine-0-cote-1-retirer'))
    fireEvent.click(screen.getByTestId('cal-releve-ajouter-chaine'))
    fireEvent.change(champ('cal-releve-chaine-1-nom'), { target: { value: 'Largeur' } })
    fireEvent.change(champ('cal-releve-chaine-1-cote-0-nom'), { target: { value: 'Largeur' } })
    fireEvent.change(champ('cal-releve-chaine-1-cote-0-valeur'), { target: { value: '8.6' } })
    fireEvent.click(screen.getByTestId('cal-releve-chaine-1-cote-1-retirer'))
    fireEvent.change(champ('cal-releve-champ-azimut_boussole_deg'), { target: { value: '157.5' } })
    fireEvent.change(champ('cal-releve-champ-precision_azimut_deg'), { target: { value: '10' } })
    fireEvent.click(screen.getByTestId('cal-releve-envoyer'))
    await waitFor(() => expect(api.corrigerReleve).toHaveBeenCalledTimes(1))
    const [, idPanneau, corpsPanneau] = api.corrigerReleve.mock.calls[0]
    cleanup()

    // 2) L'écran téléphone : les mêmes valeurs, tapées à la française.
    rendre()
    await screen.findByTestId('releve-projet')
    await waitFor(() => expect(api.releve).toHaveBeenCalledTimes(2))
    taper('releve-longueur', '12,4')
    taper('releve-largeur', '8,6')
    capteurs.demarrerCapteurs.mockResolvedValue({ ok: true })
    capteurs.lireInclinaison.mockReturnValue({ betaDeg: 0, gammaDeg: 0 })
    capteurs.lireVisee.mockReturnValue({ azimutDeg: 337.5, hauteurDeg: 0 }) // le pan regarde à l'opposé : 157,5°
    fireEvent.click(screen.getByTestId('releve-orientation-bouton'))
    await waitFor(() => expect(screen.getByTestId('releve-orientation-valeur')).toHaveTextContent('Sud-sud-est'))
    expect(screen.getByTestId('releve-orientation-valeur').textContent).not.toMatch(/saisie à la main/)
    taper('releve-precision', '10')
    fireEvent.click(screen.getByTestId('releve-terminer'))
    await waitFor(() => expect(api.corrigerReleve).toHaveBeenCalledTimes(2))
    const [, idTel, corpsTel] = api.corrigerReleve.mock.calls[1]

    expect(idTel).toBe(idPanneau)
    expect(corpsTel).toEqual(corpsPanneau)
    expect(corpsTel.chaines).toEqual([
      { nom: 'Longueur', total_mesure: null, tolerance_m: null, cotes: [{ nom: 'Longueur', valeur: 12.4 }] },
      { nom: 'Largeur', total_mesure: null, tolerance_m: null, cotes: [{ nom: 'Largeur', valeur: 8.6 }] },
    ])
    expect(await screen.findByTestId('releve-message')).toHaveTextContent('Relevé corrigé.')
    expect(api.enregistrerSectionLayout).not.toHaveBeenCalled()
  })

  it('un azimut de CAPTEUR sans précision est refusé AVANT envoi, l’erreur sous la carte', async () => {
    capteurs.demarrerCapteurs.mockResolvedValue({ ok: true })
    capteurs.lireInclinaison.mockReturnValue({ betaDeg: 0, gammaDeg: 0 })
    capteurs.lireVisee.mockReturnValue({ azimutDeg: 0, hauteurDeg: 0 })
    rendre()
    await screen.findByTestId('releve-projet')
    fireEvent.click(screen.getByTestId('releve-orientation-bouton'))
    await screen.findByTestId('releve-precision')
    fireEvent.click(screen.getByTestId('releve-terminer'))
    expect(await screen.findByTestId('releve-erreur-precision')).toHaveTextContent('précision')
    expect(api.corrigerReleve).not.toHaveBeenCalled()
  })
})

describe('ACAL1814 — une orientation TAPÉE reste une saisie à la main', () => {
  it('« 160 » tapé puis « Terminer » : aucun azimut boussole envoyé, le pan écrit en source « saisie », relu « saisie à la main »', async () => {
    rendre()
    await screen.findByTestId('releve-projet')
    await waitFor(() => expect(screen.getByTestId('releve-orientation-bouton')).not.toBeDisabled())
    fireEvent.click(screen.getByTestId('releve-orientation-bouton'))
    taper(await screen.findByTestId('releve-azimut-main').then(() => 'releve-azimut-main'), '160')
    expect(screen.queryByTestId('releve-precision')).toBeNull() // aucune précision de boussole exigée pour une saisie
    expect(screen.getByTestId('releve-orientation-valeur')).toHaveTextContent('Sud-sud-est · saisie à la main')
    fireEvent.click(screen.getByTestId('releve-terminer'))
    await waitFor(() => expect(api.corrigerReleve).toHaveBeenCalledTimes(1))
    const [, , corps] = api.corrigerReleve.mock.calls[0]
    expect(corps.azimut_boussole_deg).toBeNull()
    expect(corps.precision_azimut_deg).toBeNull()
    expect(api.enregistrerSectionLayout).toHaveBeenCalledTimes(1)
    expect(api.enregistrerSectionLayout.mock.calls[0][1]).toEqual({
      cle: 'zones', zone_id: 'z1', base_empreinte: 'emp-1',
      champs: { facingAzimuthDeg: 160, facingManual: true, facingAzimuthSource: 'saisie', facingAzimuthPrecisionDeg: null },
    })
    await waitFor(() => expect(screen.getByTestId('releve-message')).toHaveTextContent('Relevé corrigé.'))
    fireEvent.click(screen.getByTestId('releve-terminer')) // déjà écrite : jamais réécrite
    await waitFor(() => expect(api.corrigerReleve).toHaveBeenCalledTimes(2))
    expect(api.enregistrerSectionLayout).toHaveBeenCalledTimes(1)
  })

  it('relue du pan : l’orientation « saisie » du document se lit « Sud-sud-est · saisie à la main » ; une mesure de capteur reprend la main et exige sa précision', async () => {
    api.layout.mockResolvedValue({ data: {
      roof_layout: { zones: [{ ...ZONE, facingAzimuthDeg: 160, facingAzimuthSource: 'saisie', facingManual: true }] },
      empreinte_document: 'emp-1',
    } })
    rendre()
    await waitFor(() => expect(screen.getByTestId('releve-orientation-valeur')).toHaveTextContent('Sud-sud-est · saisie à la main'))
    capteurs.demarrerCapteurs.mockResolvedValue({ ok: true })
    capteurs.lireInclinaison.mockReturnValue({ betaDeg: 0, gammaDeg: 0 })
    capteurs.lireVisee.mockReturnValue({ azimutDeg: 0, hauteurDeg: 0 })
    fireEvent.click(screen.getByTestId('releve-orientation-bouton'))
    await screen.findByTestId('releve-precision')
    expect(screen.getByTestId('releve-orientation-valeur')).toHaveTextContent('Sud')
    expect(screen.getByTestId('releve-orientation-valeur').textContent).not.toMatch(/saisie à la main/)
  })
})

describe('Relevé de visite — « Voir en 3D » ouvre la vue client (ACAL1811)', () => {
  it('le lien du pied mène à /calepinage/<id>/client, jamais à l’atelier ; le geste inverse reste « Retour au relevé »', async () => {
    rendre()
    await screen.findByTestId('releve-projet')
    expect(screen.getByTestId('releve-voir-3d').getAttribute('href')).toBe('/calepinage/1/client')
    expect(screen.getByTestId('releve-voir-3d')).toHaveTextContent('Voir en 3D')
  })
})

describe('Relevé de visite — « Terminer » répond EN VUE (ACAL1812)', () => {
  it('un refus ramène le champ fautif (focus) et s’écrit dans une bannière posée AVANT le pied fixe', async () => {
    capteurs.demarrerCapteurs.mockResolvedValue({ ok: true })
    capteurs.lireInclinaison.mockReturnValue({ betaDeg: 0, gammaDeg: 0 })
    capteurs.lireVisee.mockReturnValue({ azimutDeg: 340, hauteurDeg: 0 }) // 160° vers le pan
    rendre()
    await screen.findByTestId('releve-projet')
    fireEvent.click(screen.getByTestId('releve-orientation-bouton'))
    await screen.findByTestId('releve-precision')
    fireEvent.click(screen.getByTestId('releve-terminer'))
    const bandeau = await screen.findByTestId('releve-message')
    expect(bandeau).toHaveAttribute('role', 'alert')
    expect(bandeau).toHaveTextContent('précision')
    expect(document.activeElement).toBe(document.getElementById('releve-precision'))
    // Entre le corps défilant et le pied : ni dans le corps (que la barre fixe recouvre), ni après le pied.
    expect(bandeau.closest('.cal-tel-corps')).toBeNull()
    expect(bandeau.nextElementSibling).toBe(document.querySelector('.cal-tel-pied'))
    expect(api.corrigerReleve).not.toHaveBeenCalled()
  })

  it('le succès est dit dans la même bannière (focus) et la pente tapée reste lue « saisie à la main », écrite UNE fois', async () => {
    rendre()
    await screen.findByTestId('releve-projet')
    await waitFor(() => expect(screen.getByTestId('releve-pente-bouton')).not.toBeDisabled())
    fireEvent.click(screen.getByTestId('releve-pente-bouton'))
    taper(await screen.findByTestId('releve-pente-main').then(() => 'releve-pente-main'), '22')
    fireEvent.click(screen.getByTestId('releve-terminer'))
    const bandeau = await screen.findByTestId('releve-message')
    await waitFor(() => expect(bandeau).toHaveTextContent('Relevé corrigé.'))
    expect(bandeau).toHaveAttribute('role', 'status')
    expect(document.activeElement).toBe(bandeau)
    expect(screen.getByTestId('releve-pente-valeur')).toHaveTextContent('22° · saisie à la main')
    expect(api.enregistrerSectionLayout).toHaveBeenCalledTimes(1)
    fireEvent.click(screen.getByTestId('releve-terminer'))
    await waitFor(() => expect(api.corrigerReleve).toHaveBeenCalledTimes(2))
    expect(api.enregistrerSectionLayout).toHaveBeenCalledTimes(1)
  })

  it('la feuille : la bannière ne rétrécit pas (flex: none) et ne sort pas du flux', async () => {
    const { readFileSync } = await import('node:fs')
    const style = document.createElement('style')
    style.textContent = readFileSync(`${globalThis.process.cwd()}/src/styles/calepinage/58-telephone.css`, 'utf8')
    document.head.appendChild(style)
    try {
      const regle = [...style.sheet.cssRules].find((r) => r.selectorText === '.cal-tel-message')
      expect(regle.style.flex).toMatch(/none|0 0/)
      expect(['', 'static', 'relative']).toContain(regle.style.position)
    } finally { style.remove() }
  })
})

describe('Relevé de visite — terminé hors ligne : gardé sur le téléphone, envoyé seul au retour du réseau (ACAL1810)', () => {
  const remplir = () => { taper('releve-longueur', '12,4'); taper('releve-largeur', '8,6') }

  it('Terminer sans réseau met le relevé en file ; l’événement online l’envoie UNE fois, avec le même corps', async () => {
    rendre()
    await screen.findByTestId('releve-projet')
    await waitFor(() => expect(api.releve).toHaveBeenCalled())
    enLigne = false
    remplir()
    fireEvent.click(screen.getByTestId('releve-terminer'))
    await waitFor(() => expect(screen.getByTestId('releve-message'))
      .toHaveTextContent('Relevé gardé sur ce téléphone : il partira au retour du réseau.'))
    expect(api.corrigerReleve).not.toHaveBeenCalled()
    expect(api.enregistrerReleve).not.toHaveBeenCalled()
    expect(await releveEnAttente('1')).toBe(true)
    expect(screen.getByTestId('releve-note-hors-ligne')).toHaveTextContent('Le relevé terminé est gardé sur ce téléphone')

    enLigne = true
    window.dispatchEvent(new Event('online'))
    window.dispatchEvent(new Event('online')) // deux retours simultanés : UN seul envoi
    await waitFor(() => expect(screen.getByTestId('releve-message')).toHaveTextContent('Relevé envoyé.'))
    expect(api.corrigerReleve).toHaveBeenCalledTimes(1)
    const [calepinage, releveId, corps] = api.corrigerReleve.mock.calls[0]
    expect([calepinage, releveId]).toEqual(['1', 9])
    expect(corps.chaines).toEqual([
      { nom: 'Longueur', total_mesure: null, tolerance_m: null, cotes: [{ nom: 'Longueur', valeur: 12.4 }] },
      { nom: 'Largeur', total_mesure: null, tolerance_m: null, cotes: [{ nom: 'Largeur', valeur: 8.6 }] },
    ])
    expect(await releveEnAttente('1')).toBe(false)
    await act(async () => { window.dispatchEvent(new Event('online')) }) // file vide : rien à renvoyer
    expect(api.corrigerReleve).toHaveBeenCalledTimes(1)
  })

  it('une réponse PASSAGÈRE au retour du réseau (502 pendant un redémarrage) garde le relevé ; le retour suivant l’envoie', async () => {
    rendre()
    await screen.findByTestId('releve-projet')
    await waitFor(() => expect(api.releve).toHaveBeenCalled())
    enLigne = false
    remplir()
    fireEvent.click(screen.getByTestId('releve-terminer'))
    await waitFor(() => expect(screen.getByTestId('releve-message')).toHaveTextContent('Relevé gardé sur ce téléphone'))
    expect(await releveEnAttente('1')).toBe(true)

    api.corrigerReleve.mockRejectedValueOnce({ response: { status: 502, data: {} } })
    enLigne = true
    await act(async () => { window.dispatchEvent(new Event('online')) })
    await waitFor(() => expect(api.corrigerReleve).toHaveBeenCalledTimes(1))
    expect(await releveEnAttente('1')).toBe(true) // ni perdu, ni dit « refusé »

    await act(async () => { window.dispatchEvent(new Event('online')) })
    await waitFor(() => expect(screen.getByTestId('releve-message')).toHaveTextContent('Relevé envoyé.'))
    expect(api.corrigerReleve).toHaveBeenCalledTimes(2)
    expect(await releveEnAttente('1')).toBe(false)
  })

  it('une coupure en route (aucune réponse du serveur) garde aussi le relevé ; au rechargement hors ligne il attend toujours', async () => {
    api.corrigerReleve.mockRejectedValueOnce({ code: 'ERR_NETWORK', message: 'Network Error' })
    rendre()
    await screen.findByTestId('releve-projet')
    await waitFor(() => expect(api.releve).toHaveBeenCalled())
    remplir()
    fireEvent.click(screen.getByTestId('releve-terminer'))
    await waitFor(() => expect(screen.getByTestId('releve-message')).toHaveTextContent('Relevé gardé sur ce téléphone'))
    cleanup()
    enLigne = false
    rendre() // rechargement hors ligne : rien ne part, la file garde le relevé et l’écran le dit
    await waitFor(() => expect(screen.getByTestId('releve-note-hors-ligne')).toHaveTextContent('Le relevé terminé est gardé sur ce téléphone'))
    expect(api.corrigerReleve).toHaveBeenCalledTimes(1)
    expect(await releveEnAttente('1')).toBe(true)
  })

  it('un relevé terminé en ligne n’est jamais renvoyé : la copie gardée est retirée', async () => {
    rendre()
    await screen.findByTestId('releve-projet')
    await waitFor(() => expect(api.releve).toHaveBeenCalled())
    enLigne = false
    remplir()
    fireEvent.click(screen.getByTestId('releve-terminer'))
    await waitFor(() => expect(screen.getByTestId('releve-message')).toHaveTextContent('Relevé gardé'))
    enLigne = true
    fireEvent.click(screen.getByTestId('releve-terminer')) // le réseau est revenu AVANT l'événement : envoi direct
    await waitFor(() => expect(screen.getByTestId('releve-message')).toHaveTextContent('Relevé corrigé.'))
    expect(await releveEnAttente('1')).toBe(false)
    await act(async () => { window.dispatchEvent(new Event('online')) }) // file vide : rien à renvoyer
    expect(api.corrigerReleve).toHaveBeenCalledTimes(1)
  })
})

describe('ACAL1836 — le relevé sur la maquette v2 : la carte du toit, les cotes reprises, la feuille', () => {
  // Un toit RECTANGLE créé 12,4 × 8,6 m (sommets servis en [lng, lat] autour de Casablanca).
  const rectangle = () => {
    const repere = creerRepere({ origine_lnglat: [-7.6, 33.5], ordre: 'lnglat' })
    return [[0, 0], [12.4, 0], [12.4, 8.6], [0, 8.6]].map(([x, y]) => metresVersLngLat(repere, { x, y }))
  }
  const avecToit = (vertices) => api.layout.mockResolvedValue({
    data: { roof_layout: { zones: [{ ...ZONE, id: 'z1', vertices }] }, empreinte_document: 'emp-1' },
  })

  it('un toit rectangle déjà créé préremplit Longueur et Largeur, DITES « reprises du toit » ; elles partent avec « Terminer »', async () => {
    avecToit(rectangle())
    rendre()
    await waitFor(() => expect(screen.getByTestId('releve-longueur')).toHaveValue('12,4'))
    expect(screen.getByTestId('releve-largeur')).toHaveValue('8,6')
    expect(screen.getByTestId('releve-cotes-reprises')).toHaveTextContent('Reprises du toit')
    // La carte du toit porte le plan servi et les mêmes cotes en pilules.
    expect(within(screen.getByTestId('releve-carte-toit')).getByTestId('client-plan')).toBeInTheDocument()
    expect(screen.getByTestId('releve-cote-longueur')).toHaveTextContent('12,4')
    expect(screen.getByTestId('releve-cote-largeur')).toHaveTextContent('8,6')
    fireEvent.click(screen.getByTestId('releve-terminer'))
    await waitFor(() => expect(api.corrigerReleve).toHaveBeenCalledTimes(1))
    expect(api.corrigerReleve.mock.calls[0][2].chaines).toEqual([
      { nom: 'Longueur', total_mesure: null, tolerance_m: null, cotes: [{ nom: 'Longueur', valeur: 12.4 }] },
      { nom: 'Largeur', total_mesure: null, tolerance_m: null, cotes: [{ nom: 'Largeur', valeur: 8.6 }] },
    ])
  })

  it('une saisie remplace la reprise (et la note disparaît) ; un champ vidé reste vide ; un contour non rectangle ne reprend rien', async () => {
    avecToit(rectangle())
    rendre()
    await waitFor(() => expect(screen.getByTestId('releve-longueur')).toHaveValue('12,4'))
    taper('releve-longueur', '12,6')
    taper('releve-largeur', '')
    expect(screen.queryByTestId('releve-cotes-reprises')).toBeNull()
    fireEvent.click(screen.getByTestId('releve-terminer'))
    await waitFor(() => expect(api.corrigerReleve).toHaveBeenCalledTimes(1))
    expect(api.corrigerReleve.mock.calls[0][2].chaines).toEqual([
      { nom: 'Longueur', total_mesure: null, tolerance_m: null, cotes: [{ nom: 'Longueur', valeur: 12.6 }] },
    ])
    cleanup()
    avecToit([[-7.6, 33.5], [-7.5999, 33.5], [-7.5999, 33.5001]]) // triangle
    rendre()
    await screen.findByTestId('releve-projet')
    await waitFor(() => expect(api.layout).toHaveBeenCalledTimes(2))
    expect(screen.getByTestId('releve-longueur')).toHaveValue('')
    expect(screen.queryByTestId('releve-cotes-reprises')).toBeNull()
  })

  it('une mesure déjà relevée prime sur le toit dessiné', async () => {
    api.releve.mockResolvedValue({ data: { releves: [{ ...RELEVE_COURANT, chaines: [
      { nom: 'Longueur', total_mesure: null, tolerance_m: null, cotes: [{ nom: 'Longueur', valeur: 13.1 }] },
    ] }], releve_courant_id: 9 } })
    avecToit(rectangle())
    rendre()
    await waitFor(() => expect(screen.getByTestId('releve-largeur')).toHaveValue('8,6'))
    expect(screen.getByTestId('releve-longueur')).toHaveValue('13,1')
  })

  it('la poignée réduit puis agrandit la feuille (aria-expanded), sans rien perdre', async () => {
    rendre()
    const poignee = await screen.findByTestId('releve-poignee')
    expect(poignee).toHaveAttribute('aria-expanded', 'true')
    fireEvent.click(poignee)
    expect(poignee).toHaveAttribute('aria-expanded', 'false')
    expect(screen.getByTestId('cal-releve')).toHaveAttribute('data-feuille-reduite', '1')
    expect(screen.getByTestId('releve-terminer')).toBeInTheDocument()
    fireEvent.click(poignee)
    expect(screen.getByTestId('cal-releve')).not.toHaveAttribute('data-feuille-reduite')
  })

  it('« Photos » dit N sur M avec un trait par genre servi (M = 3), pris = or', async () => {
    rendre()
    expect(await screen.findByTestId('releve-photos-compte')).toHaveTextContent('1 sur 3')
    const traits = [...screen.getByRole('progressbar', { name: 'Photos prises' }).querySelectorAll('.cal-tel-barre-trait')]
    expect(traits).toHaveLength(3)
    expect(traits.filter((t) => t.hasAttribute('data-fait'))).toHaveLength(1)
  })

  it('la feuille : arrondie en haut (26 px), l’en-tête flotte, l’action fait 54 px — lus dans la feuille de style', async () => {
    const { readFileSync } = await import('node:fs')
    const style = document.createElement('style')
    style.textContent = ['49-jetons-v2.css', '58-telephone.css']
      .map((f) => readFileSync(resolve(process.cwd(), `src/styles/calepinage/${f}`), 'utf8')).join('\n')
    document.head.appendChild(style)
    try {
      rendre()
      await screen.findByTestId('releve-projet')
      expect(getComputedStyle(document.querySelector('.cal-tel-feuille')).borderRadius).toBe('26px 26px 0 0')
      expect(getComputedStyle(document.querySelector('.cal-tel-entete')).position).toBe('absolute')
      expect(getComputedStyle(screen.getByTestId('releve-terminer')).height).toBe('54px')
    } finally { style.remove() }
  })
})

describe('Relevé de visite — la pente est celle du PAN, lue comme l’atelier la lit', () => {
  const avecZone = (zone) => api.layout.mockResolvedValue({ data: { roof_layout: { zones: [{ ...ZONE, ...zone }] }, empreinte_document: 'emp-1' } })

  it('un pan « Toit plat » (pitchDeg 22 de panVierge, tables à 10°) se dit « Toit plat », jamais « 22° »', async () => {
    avecZone({ roofType: 'flat', pitchDeg: 22, geometry: { tiltDeg: 10 } })
    rendre()
    await waitFor(() => expect(screen.getByTestId('releve-pente-valeur')).toHaveTextContent('Toit plat'))
    expect(screen.getByTestId('releve-pente-valeur').textContent).not.toMatch(/22|10/)
    expect(screen.getByTestId('releve-pente-bouton')).toHaveTextContent('Mesurer')
  })

  it('un pan en pente sans provenance : « à confirmer » + l’aide « valeur de départ » ; tapée = « saisie à la main »', async () => {
    avecZone({ roofType: 'pitched', pitchDeg: 22 })
    rendre()
    await waitFor(() => expect(screen.getByTestId('releve-pente-valeur')).toHaveTextContent('22° · à confirmer'))
    expect(screen.getByTestId('releve-pente-aide')).toHaveTextContent('Valeur de départ du pan, jamais mesurée.')
    cleanup()
    avecZone({ roofType: 'pitched', pitchDeg: 18, pitchSource: { mode: 'degres', degres: 18 } })
    rendre()
    await waitFor(() => expect(screen.getByTestId('releve-pente-valeur')).toHaveTextContent('18° · saisie à la main'))
    cleanup()
    avecZone({ roofType: 'pitched', pitchDeg: 24, pitchSource: { mode: 'degres', degres: 24, provenance: 'telephone' } })
    rendre()
    await waitFor(() => expect(screen.getByTestId('releve-pente-valeur')).toHaveTextContent('24° mesurée'))
    expect(screen.getByTestId('releve-pente-bouton')).toHaveTextContent('Mesurer encore')
  })

  it('la ligne projet : le client servi — la ville ; sans rattachement, le nom du calepinage', async () => {
    api.get.mockResolvedValue({ data: { nom: 'Calepinage 9', client: null, lead: null } })
    rendre()
    expect(await screen.findByTestId('releve-projet')).toHaveTextContent(/^Calepinage 9$/)
  })
})
