import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { exempleContrat } from '../../../test/fixtures/contractSamples'
import { creerJeton, listerJetons, revoquerJeton, testerNotification } from '../../../api/tachesApi'
import { subscribeToPush } from '../../pwa/pushSubscribe'
import MonIphone from './MonIphone'

vi.mock('../../../api/tachesApi', async (importOriginal) => ({
  ...(await importOriginal()),
  listerJetons: vi.fn(),
  creerJeton: vi.fn(),
  revoquerJeton: vi.fn(),
  testerNotification: vi.fn(),
  listerAgendasExternes: vi.fn().mockResolvedValue({ data: { results: [] } }),
}))
vi.mock('../../../api/axios', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn(), delete: vi.fn() },
}))
vi.mock('../../pwa/pushSubscribe', () => ({ pushSupported: vi.fn(() => true), subscribeToPush: vi.fn() }))

const api = (await import('../../../api/axios')).default

/* TCH109 — Mon iPhone : chaque étape change d'état sur SA donnée (jetons.json : jeton `flux` utilisé ;
   reglages.json : titres ; jeton.json : création, rendu UNE fois). Le client est mocké sur les échantillons. */

const contrat = (nom) => structuredClone(exempleContrat('taches', nom))
const jetonFlux = () => contrat('jetons_liste').results[0]
const creation = (usage) => {
  const base = contrat('jeton')
  return usage === 'flux' ? base : { ...base, id: 4, usage, prefixe: 'tqc_Zz99', jeton: `tqc_${'Z'.repeat(40)}`, url: undefined, webcal: undefined }
}
const utilise = (usage, id) => ({ ...jetonFlux(), id, usage, prefixe: `tq_${usage}`.slice(0, 8) })

let presse
function monter(props = {}) {
  const onReglage = vi.fn()
  const rendu = render(<MonIphone reglages={contrat('reglages')} onReglage={onReglage} erreur={{}} {...props} />)
  return { ...rendu, onReglage }
}
const etape = (nom) => screen.findByRole('button', { name: nom })
const ouvrir = async (nom) => {
  const bouton = await etape(nom)
  if (bouton.getAttribute('aria-expanded') !== 'true') await userEvent.click(bouton)
}

beforeEach(() => {
  presse = vi.fn().mockResolvedValue(undefined)
  Object.defineProperty(navigator, 'clipboard', { value: { writeText: presse }, configurable: true })
  window.Notification = { permission: 'default' }
  listerJetons.mockResolvedValue({ data: contrat('jetons_liste') })
})
afterEach(() => { vi.clearAllMocks(); window.localStorage.clear() })

describe('TCH109 — Mon iPhone', () => {
  it('compte les étapes faites sur leurs données : seul le jeton flux utilisé est fait', async () => {
    monter()
    expect(await screen.findByText('1 sur 6')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: '1 étapes sur 6 faites' })).toBeInTheDocument()
    const calendrier = await etape(/Voir tes tâches dans le Calendrier/)
    expect(calendrier).toHaveTextContent('Fait')
    expect(calendrier).toHaveAttribute('aria-expanded', 'false')
    expect(await etape(/Recevoir les notifications/)).toHaveAttribute('aria-expanded', 'true')
    expect(await etape(/Dicter à Siri/)).toHaveTextContent('À faire')
  })

  it('étape demandée par l\'adresse (?etape=calendrier) : « Mes agendas » et son champ sont visibles sans geste de plus', async () => {
    monter({ etapeDemandee: 1 })
    const calendrier = await etape(/Voir tes tâches dans le Calendrier/)
    expect(calendrier).toHaveAttribute('aria-expanded', 'true')
    expect(await screen.findByRole('heading', { name: 'Mes agendas' })).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: /^Adresse de l'agenda/ })).toBeInTheDocument()
    expect(await etape(/Recevoir les notifications/)).toHaveAttribute('aria-expanded', 'true')
  })

  it('deux jetons de plus utilisés et la permission accordée : « 4 sur 6 », les étapes faites se replient', async () => {
    window.Notification = { permission: 'granted' }
    listerJetons.mockResolvedValue({ data: { results: [jetonFlux(), utilise('capture', 5), utilise('tuile', 6)] } })
    monter()
    expect(await screen.findByText('4 sur 6')).toBeInTheDocument()
    expect(await etape(/Recevoir les notifications/)).toHaveTextContent('Fait')
    expect(await etape(/Ouvrir Aujourd'hui depuis l'icône/)).toHaveAttribute('aria-expanded', 'true')
  })

  it('le dernier usage du jeton est dit avec son heure ; un jeton jamais utilisé le dit aussi', async () => {
    listerJetons.mockResolvedValue({ data: { results: [jetonFlux(), { ...utilise('capture', 5), dernier_usage_le: null }] } })
    monter()
    await ouvrir(/Voir tes tâches dans le Calendrier/)
    expect(await screen.findByText(/Dernier usage : .* 09:41 · tqf_Ab12…/)).toBeInTheDocument()
    await ouvrir(/Dicter à Siri/)
    expect(await screen.findByText(/Jamais utilisé · tq_captu…/)).toBeInTheDocument()
  })

  it('créer un jeton : rendu UNE fois, copié, puis il disparaît et ne laisse aucune trace locale', async () => {
    listerJetons.mockResolvedValue({ data: { results: [] } })
    creerJeton.mockResolvedValue({ data: creation('capture') })
    monter()
    await ouvrir(/Dicter à Siri/)
    await userEvent.click(await screen.findByRole('button', { name: 'Créer le jeton' }))
    expect(creerJeton).toHaveBeenCalledWith({ usage: 'capture', libelle: '' })
    const secret = creation('capture').jeton
    expect(await screen.findByText(secret)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Copier mon jeton' }))
    expect(presse).toHaveBeenCalledWith(secret)
    expect(await screen.findByText('Copié. Il ne sera plus affiché : colle-le maintenant.')).toBeInTheDocument()
    expect(screen.queryByText(secret)).toBeNull()
    expect(screen.queryByRole('button', { name: 'Copier mon jeton' })).toBeNull()
    expect(screen.getByText(/Perdu \? Régénère-le\./)).toBeInTheDocument()
    expect(JSON.stringify({ ...window.localStorage })).not.toContain(secret)
    expect(window.location.href).not.toContain(secret)
  })

  it('régénérer demande confirmation puis crée le nouveau ; révoquer retire le jeton et dit comment', async () => {
    creerJeton.mockResolvedValue({ data: creation('flux') })
    revoquerJeton.mockResolvedValue({ data: {} })
    monter()
    await ouvrir(/Voir tes tâches dans le Calendrier/)
    expect(await screen.findByText(/Pour couper l'accès : « Révoquer »/)).toBeInTheDocument()
    await userEvent.click(await screen.findByRole('button', { name: 'Régénérer' }))
    const dialogue = screen.getByRole('alertdialog', { name: 'Régénérer ?' })
    expect(within(dialogue).getByText("Régénérer ? L'ancien cesse de marcher tout de suite.")).toBeInTheDocument()
    expect(creerJeton).not.toHaveBeenCalled()
    await userEvent.click(within(dialogue).getByRole('button', { name: 'Régénérer' }))
    expect(creerJeton).toHaveBeenCalledWith({ usage: 'flux', libelle: '' })
    expect(await screen.findByRole('link', { name: "S'abonner" })).toHaveAttribute('href', creation('flux').webcal)
    await userEvent.click(screen.getByRole('button', { name: 'Copier le lien' }))
    expect(presse).toHaveBeenCalledWith(creation('flux').url)
    await userEvent.click(screen.getByRole('button', { name: 'Révoquer' }))
    expect(revoquerJeton).toHaveBeenCalledWith(3)
    expect(await screen.findByRole('button', { name: 'Créer le lien du calendrier' })).toBeInTheDocument()
  })

  it('un refus du serveur à la création se lit sous le jeton', async () => {
    listerJetons.mockResolvedValue({ data: { results: [] } })
    creerJeton.mockRejectedValue(Object.assign(new Error('400'), { response: { status: 400, data: { error: 'x', usage: ['Jeton refusé.'] } } }))
    monter()
    await ouvrir(/Installer la grande tuile/)
    await userEvent.click(await screen.findByRole('button', { name: 'Créer le jeton de la tuile' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Jeton refusé.')
  })

  it('tuile : « Copier le script » copie le script de l\'ERP, sans aucun jeton', async () => {
    monter()
    await ouvrir(/Installer la grande tuile/)
    await userEvent.click(await screen.findByRole('button', { name: 'Copier le script' }))
    expect(presse).toHaveBeenCalledTimes(1)
    const copie = presse.mock.calls[0][0]
    expect(copie).toContain(`const BASE = "${window.location.origin}";`)
    expect(copie).not.toContain('__BASE__')
    expect(copie).not.toMatch(/tq[cft]_[A-Za-z0-9]{8}/)
    expect(await screen.findByText('Script copié. Il ne contient pas ton jeton.')).toBeInTheDocument()
  })

  it('notifications : l\'autorisation fait passer l\'étape à « Actives », un test part, la clé absente est dite', async () => {
    subscribeToPush.mockResolvedValueOnce({ ok: false, reason: 'unconfigured' })
    subscribeToPush.mockResolvedValueOnce({ ok: true })
    testerNotification.mockResolvedValue({ data: {} })
    monter()
    expect(await screen.findByText('Pas encore autorisées.')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Autoriser les notifications' }))
    expect(await screen.findByText("Pas configurées sur ce serveur : demande à l'administrateur.")).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Autoriser les notifications' }))
    expect(await screen.findByText('Actives sur cet appareil.')).toBeInTheDocument()
    expect(await etape(/Recevoir les notifications/)).toHaveTextContent('Fait')
    await userEvent.click(screen.getByRole('button', { name: 'Envoyer un test' }))
    expect(testerNotification).toHaveBeenCalledTimes(1)
  })

  it('notifications refusées : le chemin des Réglages de l\'iPhone est dit', async () => {
    window.Notification = { permission: 'denied' }
    monter()
    expect(await screen.findByText("Refusées : Réglages de l'iPhone → Notifications → Taqinor → Autoriser.")).toBeInTheDocument()
  })

  it('« Montrer le titre sur l\'écran verrouillé ? » : Oui / Non écrivent le réglage', async () => {
    const { onReglage } = monter()
    await userEvent.click(await screen.findByRole('button', { name: 'Oui' }))
    expect(onReglage).toHaveBeenCalledWith('titres_notifications', true)
    expect(screen.getByRole('button', { name: 'Oui' })).toHaveAttribute('aria-pressed', 'true')
    await userEvent.click(screen.getByRole('button', { name: 'Non' }))
    expect(onReglage).toHaveBeenLastCalledWith('titres_notifications', false)
  })

  // Passe visuelle (mineur, contenu de Mon iPhone) — les marches de chaque étape sont NUMÉROTÉES (textes.md §7 :
  // « 1. Ouvre l'ERP… 2. Touche… ») : la remise à zéro des listes de l'ERP effaçait les numéros, et les marches se
  // lisaient d'un bloc.
  it('passe visuelle — les marches des étapes 1 à 4 sont des listes numérotées', async () => {
    monter({ reglages: { ...contrat('reglages'), raccourci_siri_url: null } })
    const marches = [
      [/Recevoir les notifications/, /^Ouvre l'ERP depuis son icône/],
      [/Voir tes tâches dans le Calendrier/, /^Touche « Créer le lien du calendrier »/],
      [/Dicter à Siri/, /^Ouvre l'app Raccourcis/],
      [/Installer la grande tuile/, /^App Store → Scriptable/],
    ]
    for (const [nom, premiere] of marches) {
      await ouvrir(nom)
      const liste = (await screen.findByText(premiere)).closest('ol')
      expect(liste, `liste de « ${nom} »`).toHaveClass('list-decimal')
      expect(liste.closest('ol.ep-etapes')).not.toBe(liste)
    }
  })

  it('Siri : « Installer le raccourci » n\'existe que si l\'adresse est posée, sans elle la recette est directe', async () => {
    const { unmount } = monter({ reglages: { ...contrat('reglages'), raccourci_siri_url: 'https://www.icloud.com/shortcuts/abc' } })
    await ouvrir(/Dicter à Siri/)
    expect(await screen.findByRole('link', { name: 'Installer le raccourci' })).toHaveAttribute('href', 'https://www.icloud.com/shortcuts/abc')
    expect(screen.queryByText(/Ouvre l'app Raccourcis/)).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: 'Le faire à la main' }))
    expect(screen.getByText(/Ouvre l'app Raccourcis/)).toBeInTheDocument()
    unmount()
    monter({ reglages: { ...contrat('reglages'), raccourci_siri_url: null } })
    await ouvrir(/Dicter à Siri/)
    expect(screen.queryByRole('link', { name: 'Installer le raccourci' })).toBeNull()
    expect(await screen.findByText(/Ouvre l'app Raccourcis/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: "Copier l'adresse" }))
    expect(presse).toHaveBeenCalledWith(`${window.location.origin}/api/django/taches/capture/?reponse=texte`)
  })

  it('« En faire mon accueil » mémorise la route et fait passer l\'étape 5 à « Fait »', async () => {
    api.post.mockResolvedValue({ data: {} })
    monter()
    await ouvrir(/Ouvrir Aujourd'hui depuis l'icône/)
    await userEvent.click(await screen.findByRole('button', { name: 'En faire mon accueil' }))
    expect(api.post).toHaveBeenCalledWith('/auth/mobile-home-route/', { route: '/taches/aujourdhui' })
    await waitFor(() => expect(screen.getByRole('button', { name: /Ouvrir Aujourd'hui depuis l'icône/ })).toHaveTextContent('Fait'))
  })

  it('« Ce qui est visible » reflète reglages.json et écrit au toucher', async () => {
    const { onReglage } = monter()
    expect(await screen.findByRole('switch', { name: 'Titres dans le calendrier' })).toBeChecked()
    expect(screen.getByRole('switch', { name: 'Titres sur la tuile' })).toBeChecked()
    expect(screen.getByRole('switch', { name: "Titres sur l'écran verrouillé" })).not.toBeChecked()
    await userEvent.click(screen.getByRole('switch', { name: 'Titres sur la tuile' }))
    expect(onReglage).toHaveBeenCalledWith('titres_tuile', false)
    expect(screen.getByText("Une tâche confidentielle n'y apparaît jamais par son titre.")).toBeInTheDocument()
  })

  it('R2-126 — « Mettre Tâches sur l\'écran d\'accueil » est la première chose de l\'écran, nommée, avec ses marches', async () => {
    const { container } = monter()
    const bloc = await screen.findByRole('region', { name: "Mettre Tâches sur l'écran d'accueil" })
    expect(within(bloc).getByRole('heading', { name: /Mettre Tâches sur l'écran d'accueil/ })).toHaveTextContent('À faire')
    const marches = within(bloc).getAllByRole('listitem').map((li) => li.textContent)
    expect(marches[0]).toMatch(/^Dans Safari, touche le bouton Partager/)
    expect(marches[1]).toMatch(/«\sSur l'écran d'accueil\s»/)
    // il précède les cinq étapes (qui restent cinq) dans l'écran
    expect(bloc.compareDocumentPosition(container.querySelector('ol.ep-etapes')) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(container.querySelectorAll('ol.ep-etapes > li')).toHaveLength(5)
  })

  it('R2-126 — ouvert depuis son icône (mode autonome), l\'étape est « Fait » et ses marches disparaissent', async () => {
    window.matchMedia = vi.fn().mockReturnValue({ matches: true })
    monter()
    const bloc = await screen.findByRole('region', { name: "Mettre Tâches sur l'écran d'accueil" })
    expect(within(bloc).getByRole('heading')).toHaveTextContent('Fait')
    expect(within(bloc).queryByRole('listitem')).toBeNull()
    // R3-098 — elle compte : « 2 sur 6 » (le jeton flux utilisé + l'icône)
    expect(await screen.findByText('2 sur 6')).toBeInTheDocument()
    delete window.matchMedia
  })

  it('R3-098 — « Mettre Tâches sur l\'écran d\'accueil » est l\'étape 1, numérotée, puis 2 à 6 ; « Six étapes »', async () => {
    const { container } = monter()
    const bloc = await screen.findByRole('region', { name: "Mettre Tâches sur l'écran d'accueil" })
    expect(bloc.querySelector('.num').textContent).toBe('1')
    expect(screen.getByText('Six étapes, à faire une fois. Chacune se replie quand elle est faite.')).toBeInTheDocument()
    await screen.findByText('1 sur 6')
    const numeros = [...container.querySelectorAll('ol.ep-etapes > li .num')].map((n) => n.textContent)
    // l'étape « calendrier » (3) est faite : sa coche remplace son numéro
    expect(numeros).toEqual(['2', '', '4', '5', '6'])
  })

  it('R2-130 — « Oui / Non » répond à une question écrite juste au-dessus ; les guillemets ne se séparent plus de leur mot', async () => {
    monter()
    const question = await screen.findByText('Montrer le titre sur l\'écran verrouillé ?', { selector: 'p' })
    const groupe = screen.getByRole('group', { name: 'Montrer le titre sur l\'écran verrouillé ?' })
    expect(question.nextElementSibling).toBe(groupe)
    expect(within(groupe).getAllByRole('button').map((b) => b.textContent)).toEqual(['Oui', 'Non'])
    // « Autoriser les notifications » n'est plus dans la même rangée que Oui / Non
    expect(within(groupe).queryByRole('button', { name: 'Autoriser les notifications' })).toBeNull()
    const marche = (await screen.findAllByRole('listitem')).find((li) => li.textContent.includes('Autoriser les notifications')).textContent
    expect(marche).toContain('« Autoriser les notifications »')
    expect(marche).not.toMatch(/« | »/)
  })

  it('un échec de lecture des jetons dit « Pas à jour » et garde l\'écran', async () => {
    listerJetons.mockRejectedValue(new Error('Network Error'))
    monter()
    expect(await screen.findByText('Pas à jour')).toBeInTheDocument()
    expect(screen.getByText('0 sur 6')).toBeInTheDocument()
  })
})
