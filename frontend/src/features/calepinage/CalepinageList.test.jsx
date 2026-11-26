import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

/* ============================================================================
   CAL35 — la liste `/calepinage`, prouvée sur les VRAIS filtres.
   ----------------------------------------------------------------------------
   Deux invariants, exactement ceux du « Done » de la tâche :
     1. CHAQUE filtre déclenche l'appel serveur correspondant — la leçon PV22
        est qu'un filtre ignoré fait ouvrir le mauvais objet ;
     2. une vignette SANS image rend le repli, jamais une balise cassée.

   Les lignes viennent de l'échantillon de contrat committé
   (`apps/calepinage/contract_samples/calepinage_liste.json`, PACT10) et non
   d'un PAYLOAD écrit à la main : un mock maison est une DEUXIÈME source de
   vérité, et c'est elle qui a fait passer l'écran AO Tableau de bord en
   production le 03/08/2026 avec zéro clé sur six concordante.
   ========================================================================== */

import { mocks } from '../../test/calepinageListMocks'

import CalepinageList from './CalepinageList'
import {
  STATUTS_CALEPINAGE, apercuVide, identiteCarte, initiales, modifieDe,
} from './CalepinageList.helpers'
import { documentContrat, exempleContrat } from '../../test/fixtures/contractSamples'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

// L'exemple du contrat = un calepinage AVEC aperçu ; `exemple_vide` = un
// calepinage neuf dont `image.url` vaut `null` (et non `0`, ni clé absente).
// ACAL197 — la forme de la LISTE (`calepinage_liste.json`, D06-T01), jamais
// celle du détail : `client_apercu`, `responsable` + `responsable_nom`.
const LIGNE = (variante) => exempleContrat('calepinage', 'calepinage_liste', variante).results[0]
const AVEC_IMAGE = LIGNE('exemple')
const SANS_IMAGE = LIGNE('exemple_sans_image')
const CLIENT_SEUL = LIGNE('exemple_client_seul')

const rendre = () => render(
  <MemoryRouter><ThemeProvider><CalepinageList /></ThemeProvider></MemoryRouter>,
)

const derniersParams = () => mocks.list.mock.calls.at(-1)?.[0] ?? {}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.list.mockResolvedValue({
    data: { count: 2, next: null, previous: null, results: [AVEC_IMAGE, SANS_IMAGE] },
  })
  mocks.getLeads.mockResolvedValue({ data: [] })
  mocks.searchClients.mockResolvedValue({ data: [] })
})

describe('CalepinageList (CAL35)', () => {
  it('charge la liste au montage, SANS filtre inventé', async () => {
    rendre()
    await waitFor(() => expect(mocks.list).toHaveBeenCalled())
    expect(derniersParams()).toEqual({})
  })

  it('rend une vignette par calepinage, avec sa référence', async () => {
    rendre()
    expect(await screen.findByTestId(`cal-vignette-${AVEC_IMAGE.id}`)).toBeInTheDocument()
    expect(screen.getByTestId(`cal-vignette-${SANS_IMAGE.id}`)).toBeInTheDocument()
    // La référence et le rattachement vivent dans la même ligne de texte :
    // on interroge la vignette, pas un nœud de texte isolé.
    expect(screen.getByTestId(`cal-vignette-${AVEC_IMAGE.id}`))
      .toHaveTextContent(AVEC_IMAGE.reference)
  })

  it('une vignette SANS image rend le repli — jamais une balise cassée', async () => {
    rendre()
    await screen.findByTestId(`cal-vignette-${SANS_IMAGE.id}`)

    // Le calepinage neuf du contrat a `image.url === null` : aucune `<img>` ne
    // doit être émise pour lui (une `src` vide affiche l'icône cassée).
    expect(SANS_IMAGE.image.url).toBeNull()
    expect(screen.getByTestId('cal-vignette-sans-image')).toBeInTheDocument()
    const images = screen.getAllByTestId('cal-vignette-image')
    expect(images).toHaveLength(1)
    expect(images[0]).toHaveAttribute('src', AVEC_IMAGE.image.url)
    for (const img of document.querySelectorAll('img')) {
      expect(img.getAttribute('src')).toBeTruthy()
    }
  })

  it('rend la vignette, la référence et le client d’un calepinage client seul', async () => {
    mocks.list.mockResolvedValue({
      data: { count: 1, next: null, previous: null, results: [CLIENT_SEUL] },
    })
    rendre()
    const vignette = await screen.findByTestId(`cal-vignette-${CLIENT_SEUL.id}`)
    expect(vignette).toHaveTextContent(CLIENT_SEUL.reference)
    expect(vignette).toHaveTextContent(CLIENT_SEUL.client_apercu.nom)
    expect(vignette).not.toHaveTextContent('Sans rattachement')
    expect(vignette).toHaveTextContent('Modifié 3 octobre')
    expect(screen.getByTestId('cal-vignette-image'))
      .toHaveAttribute('src', CLIENT_SEUL.image.url)
  })

  it('propose les trois statuts même si la page n’en contient qu’un', async () => {
    mocks.list.mockResolvedValue({
      data: { count: 1, next: null, previous: null, results: [CLIENT_SEUL] },
    })
    rendre()
    await screen.findByTestId(`cal-vignette-${CLIENT_SEUL.id}`)
    fireEvent.click(screen.getByRole('combobox', { name: 'Statut' }))
    await screen.findByRole('listbox')
    for (const { libelle } of documentContrat('calepinage', 'calepinage_liste').statuts_publies) {
      expect(screen.getByRole('option', { name: libelle })).toBeInTheDocument()
    }
  })

  it('STATUTS_CALEPINAGE égale statuts_publies du contrat', () => {
    const publies = documentContrat('calepinage', 'calepinage_liste').statuts_publies
    expect(STATUTS_CALEPINAGE).toEqual(publies.map((x) => [x.valeur, x.libelle]))
  })

  it('la vignette mène à l’atelier du calepinage', async () => {
    rendre()
    const vignette = await screen.findByTestId(`cal-vignette-${AVEC_IMAGE.id}`)
    expect(vignette).toHaveAttribute('href', `/calepinage/${AVEC_IMAGE.id}`)
  })

  it('ACAL957 — les filtres sont repliés derrière « Filtres » ; l’appui les déplie', async () => {
    rendre()
    await waitFor(() => expect(mocks.list).toHaveBeenCalled())
    const conteneur = screen.getByTestId('acal957-filtres')
    const bouton = screen.getByTestId('acal957-filtres-basculer')
    expect(conteneur.className).toContain('hidden')
    expect(bouton.getAttribute('aria-expanded')).toBe('false')
    fireEvent.click(bouton)
    expect(bouton.getAttribute('aria-expanded')).toBe('true')
    expect(conteneur.className).not.toContain('hidden')
    expect(screen.getByLabelText('Modifié depuis le')).toBeTruthy()
  })

  it('un filtre avancé actif garde la barre ouverte et compte dans « Filtres · N actif »', async () => {
    rendre()
    await waitFor(() => expect(mocks.list).toHaveBeenCalled())
    fireEvent.change(screen.getByLabelText('Modifié depuis le'), { target: { value: '2026-09-01' } })
    expect(screen.getByTestId('acal957-filtres').className).not.toContain('hidden')
    expect(screen.getByTestId('acal957-filtres-basculer')).toHaveTextContent('Filtres · 1 actif')
  })

  it('la RECHERCHE part en `?q=` — le filtre servi par CAL16', async () => {
    rendre()
    await waitFor(() => expect(mocks.list).toHaveBeenCalled())
    fireEvent.change(screen.getByLabelText('Rechercher un calepinage'), { target: { value: 'toiture' } })
    await waitFor(() => expect(derniersParams()).toEqual({ q: 'toiture' }))
  })

  it('la DATE part en `?depuis=`', async () => {
    rendre()
    await waitFor(() => expect(mocks.list).toHaveBeenCalled())
    fireEvent.change(screen.getByLabelText('Modifié depuis le'), { target: { value: '2026-09-01' } })
    await waitFor(() => expect(derniersParams()).toEqual({ depuis: '2026-09-01' }))
  })

  it('les filtres se CUMULENT dans une seule requête', async () => {
    rendre()
    await waitFor(() => expect(mocks.list).toHaveBeenCalled())
    fireEvent.change(screen.getByLabelText('Rechercher un calepinage'), { target: { value: 'hangar' } })
    fireEvent.change(screen.getByLabelText('Modifié depuis le'), { target: { value: '2026-09-10' } })
    await waitFor(() => expect(derniersParams()).toEqual({ q: 'hangar', depuis: '2026-09-10' }))
  })

  it('un filtre VIDÉ disparaît de la requête (jamais `?q=` vide)', async () => {
    rendre()
    const champ = screen.getByLabelText('Rechercher un calepinage')
    fireEvent.change(champ, { target: { value: 'hangar' } })
    await waitFor(() => expect(derniersParams()).toEqual({ q: 'hangar' }))
    fireEvent.change(champ, { target: { value: '' } })
    await waitFor(() => expect(derniersParams()).toEqual({}))
  })

  it('le filtre LEAD cherche CÔTÉ SERVEUR (bornage société), jamais dans une liste locale', async () => {
    mocks.getLeads.mockResolvedValue({ data: [{ id: 4, nom: 'Lead d’essai', ville: 'Casablanca' }] })
    rendre()
    await waitFor(() => expect(mocks.list).toHaveBeenCalled())
    fireEvent.click(screen.getByRole('combobox', { name: 'Lead' }))
    // Une liste pré-chargée côté écran ne peut pas être bornée société : la
    // recherche DOIT partir au serveur.
    await waitFor(() => expect(mocks.getLeads).toHaveBeenCalled())
    expect(await screen.findByText('Lead d’essai')).toBeInTheDocument()
    fireEvent.click(screen.getByText('Lead d’essai'))
    await waitFor(() => expect(derniersParams()).toEqual({ lead: '4' }))
  })

  it('le filtre CLIENT cherche CÔTÉ SERVEUR et part en `?client=`', async () => {
    mocks.searchClients.mockResolvedValue({ data: [{ id: 9, nom: 'Client d’essai' }] })
    rendre()
    await waitFor(() => expect(mocks.list).toHaveBeenCalled())
    fireEvent.click(screen.getByRole('combobox', { name: 'Client' }))
    await waitFor(() => expect(mocks.searchClients).toHaveBeenCalled())
    fireEvent.click(await screen.findByText('Client d’essai'))
    await waitFor(() => expect(derniersParams()).toEqual({ client: '9' }))
  })

  it('le libellé de statut d’une ligne est celui du SERVEUR', async () => {
    rendre()
    await screen.findByTestId(`cal-vignette-${AVEC_IMAGE.id}`)
    expect(screen.getAllByText(AVEC_IMAGE.statut_libelle).length).toBeGreaterThan(0)
  })

  it('état vide : il EXPLIQUE le geste de création', async () => {
    mocks.list.mockResolvedValue({ data: { count: 0, next: null, previous: null, results: [] } })
    rendre()
    expect(await screen.findByText(/Aucun calepinage pour l’instant/)).toBeInTheDocument()
    expect(screen.getByText(/part d’un lead ou d’un client/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Créer un calepinage/ }))
    expect(mocks.navigate).toHaveBeenCalledWith('/calepinage/nouveau')
  })

  it('état vide SOUS FILTRE : il propose de réinitialiser, pas de créer', async () => {
    rendre()
    await waitFor(() => expect(mocks.list).toHaveBeenCalled())
    mocks.list.mockResolvedValue({ data: { count: 0, next: null, previous: null, results: [] } })
    fireEvent.change(screen.getByLabelText('Rechercher un calepinage'), { target: { value: 'introuvable' } })
    expect(await screen.findByText(/Aucun calepinage ne correspond à ces filtres/)).toBeInTheDocument()
  })

  it('la PAGINATION suit le serveur : « Suivant » n’est actif que s’il y a une page suivante', async () => {
    mocks.list.mockResolvedValue({
      data: { count: 3, next: 'http://x/?page=2', previous: null, results: [AVEC_IMAGE] },
    })
    rendre()
    await screen.findByTestId(`cal-vignette-${AVEC_IMAGE.id}`)
    const suivant = screen.getByRole('button', { name: 'Suivant' })
    expect(suivant).toBeEnabled()
    expect(screen.getByRole('button', { name: 'Précédent' })).toBeDisabled()
    fireEvent.click(suivant)
    await waitFor(() => expect(derniersParams()).toEqual({ page: 2 }))
  })

  it('changer un filtre REVIENT à la page 1 (sinon la page 3 d’une autre liste s’affiche vide)', async () => {
    mocks.list.mockResolvedValue({
      data: { count: 9, next: 'http://x/?page=2', previous: null, results: [AVEC_IMAGE] },
    })
    rendre()
    await screen.findByTestId(`cal-vignette-${AVEC_IMAGE.id}`)
    fireEvent.click(screen.getByRole('button', { name: 'Suivant' }))
    await waitFor(() => expect(derniersParams()).toEqual({ page: 2 }))
    fireEvent.change(screen.getByLabelText('Rechercher un calepinage'), { target: { value: 'toit' } })
    await waitFor(() => expect(derniersParams()).toEqual({ q: 'toit' }))
  })

  it('une erreur serveur s’affiche telle quelle, jamais un texte fabriqué', async () => {
    mocks.list.mockRejectedValue({ response: { data: { detail: 'Accès refusé à ce module.' } } })
    rendre()
    expect(await screen.findByRole('alert')).toHaveTextContent('Accès refusé à ce module.')
  })

  // T4-B4-002 — une lecture restée SANS réponse (délai dépassé : « annulée » au réseau) est relancée par l'écran monté.
  it('une première lecture sans réponse est relancée : la liste s’affiche, aucun message mort', async () => {
    mocks.list.mockRejectedValueOnce({ code: 'ECONNABORTED', message: 'timeout of 20000ms exceeded' })
    rendre()
    expect(await screen.findByText('2 projets')).toBeInTheDocument()
    expect(mocks.list).toHaveBeenCalledTimes(2)
    expect(screen.queryByRole('alert')).toBeNull()
  })

  // T4-B4-013 — « 0 projet » s'affichait pendant la lecture, avant « 40 projets » : jamais un faux zéro.
  it('pendant la lecture : « Chargement… » à la place du compte, jamais « 0 projet »', async () => {
    let servir
    mocks.list.mockReturnValueOnce(new Promise((ok) => { servir = ok }))
    rendre()
    await waitFor(() => expect(mocks.list).toHaveBeenCalled())
    expect(screen.queryByText('0 projet')).toBeNull()
    expect(screen.getByRole('heading', { name: 'Calepinages' }).parentElement).toHaveTextContent('Chargement…')
    servir({ data: { count: 2, next: null, previous: null, results: [AVEC_IMAGE, SANS_IMAGE] } })
    expect(await screen.findByText('2 projets')).toBeInTheDocument()
  })

  // ACAL1747 — le compteur est posé sur le jeton de texte secondaire de l'écran (pas sur le gris pâle du thème).
  it('le compteur « N projets » porte la classe du jeton --cal-texte-2, défini en clair et en sombre', async () => {
    const { readFileSync } = await import('node:fs')
    rendre()
    const compteur = await screen.findByTestId('liste-compteur')
    expect(compteur).toHaveClass('cliste-compteur')
    expect(compteur).not.toHaveClass('text-muted-foreground')
    const racine = `${globalThis.process.cwd()}/src/styles/calepinage`
    expect(readFileSync(`${racine}/57-liste.css`, 'utf8')).toMatch(/\.cliste-compteur\s*\{\s*color:\s*var\(--cal-texte-2\);?\s*\}/)
    const jetons = readFileSync(`${racine}/49-jetons-v2.css`, 'utf8')
    expect(jetons).toMatch(/\.cliste,[^{]*\{[^}]*--cal-texte-2:/)
    expect(jetons).toMatch(/\.dark \.cliste,[^{]*\{[^}]*--cal-texte-2:/)
  })

  // ACAL1825 — la page de la liste est posée sur le papier de la maquette v2 ; cartes et puces lisent les jetons d'ombre
  // posée et d'actif (49-jetons-v2.css), plus l'ombre locale `--cliste-ombre`.
  it('la page de liste porte la classe de fond papier ; ombres et pastille active par les jetons', async () => {
    const { readFileSync } = await import('node:fs')
    const { container } = rendre()
    await screen.findByTestId('liste-compteur')
    expect(container.querySelector('.cliste')).toHaveClass('cliste-page')
    const css = readFileSync(`${globalThis.process.cwd()}/src/styles/calepinage/57-liste.css`, 'utf8')
    expect(css).toMatch(/\.cliste-page\s*\{[^}]*background:\s*var\(--cal-papier\)/)
    expect(css).not.toContain('--cliste-ombre')
    expect(css).toMatch(/\.cliste-carte\s*\{[^}]*box-shadow:\s*var\(--cal-ombre-posee\)/)
    expect(css).toMatch(/\.cliste-puce\[aria-pressed='true'\]\s*\{[^}]*background:\s*var\(--cal-actif\)/)
  })

  // ACAL1819 — au téléphone (≤ 639 px) : titre + « + » 44 × 44 sur une ligne, recherche puis « Filtres », les pastilles
  // d'état derrière « Filtres » : la première carte se lit dans le premier écran. Le DOM garde tout (jsdom n'applique pas le CSS).
  it('ACAL1819 — les pastilles sont repliées derrière « Filtres » (donnée), le libellé du bouton « Nouveau calepinage » reste son nom', async () => {
    const { readFileSync } = await import('node:fs')
    rendre()
    const groupe = await screen.findByTestId('cal-liste-filtres-etat')
    expect(groupe).toHaveClass('cliste-puces')
    expect(groupe).toHaveAttribute('data-replie', 'true')
    fireEvent.click(screen.getByTestId('acal957-filtres-basculer'))
    expect(groupe).toHaveAttribute('data-replie', 'false')
    fireEvent.click(screen.getByTestId('acal957-filtres-basculer'))
    expect(groupe).toHaveAttribute('data-replie', 'true')
    // Un statut choisi garde les pastilles à la vue : un filtre actif ne se cache jamais.
    fireEvent.click(screen.getByRole('button', { name: /^Brouillon/ }))
    expect(groupe).toHaveAttribute('data-replie', 'false')
    const nouveau = screen.getByRole('button', { name: /Nouveau calepinage/ })
    expect(nouveau.querySelector('.cliste-action-texte')).toHaveTextContent('Nouveau calepinage')
    const css = readFileSync(`${globalThis.process.cwd()}/src/styles/calepinage/57-liste.css`, 'utf8')
    const telephone = css.slice(css.indexOf('@media (max-width: 639px)'))
    expect(telephone).toMatch(/\.cliste-puces\[data-replie='true'\]\s*\{\s*display:\s*none/)
    expect(telephone).toMatch(/\.cliste-action\s*\{[^}]*width:\s*44px[^}]*height:\s*44px/)
    expect(telephone).toMatch(/\.cliste-action-texte\s*\{[^}]*clip:/)
  })

  it('un échec qui dure propose « Réessayer », qui relance la lecture', async () => {
    mocks.list.mockRejectedValue({ response: { status: 503, data: { detail: 'Service indisponible.' } } })
    rendre()
    const alerte = await screen.findByRole('alert')
    mocks.list.mockResolvedValue({ data: { count: 2, next: null, previous: null, results: [AVEC_IMAGE, SANS_IMAGE] } })
    fireEvent.click(within(alerte).getByRole('button', { name: 'Réessayer' }))
    expect(await screen.findByText('2 projets')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).toBeNull()
  })

  // CALX32 — le sélecteur de tri, limité aux 4 champs de `ordering_fields`
  // (`views/calepinages.py:173-174`) : created_at, updated_at, statut, titre.
  describe('CALX32 — le tri', () => {
    it('le sélecteur ne propose QUE les 4 champs réellement servis', async () => {
      rendre()
      await waitFor(() => expect(mocks.list).toHaveBeenCalled())
      fireEvent.click(screen.getByRole('combobox', { name: 'Tri' }))
      await screen.findByRole('listbox')
      for (const libelle of ['Date de création', 'Date de modification', 'Statut', 'Titre']) {
        expect(screen.getByRole('option', { name: libelle })).toBeInTheDocument()
      }
      // Rien d'autre n'est inventé : ces 4 + le repli « Tri par défaut ».
      expect(screen.getAllByRole('option')).toHaveLength(5)
    })

    it('changer le tri relance la requête avec `ordering=` et remet la page à 1', async () => {
      mocks.list.mockResolvedValue({
        data: { count: 9, next: 'http://x/?page=2', previous: null, results: [AVEC_IMAGE] },
      })
      rendre()
      await screen.findByTestId(`cal-vignette-${AVEC_IMAGE.id}`)
      fireEvent.click(screen.getByRole('button', { name: 'Suivant' }))
      await waitFor(() => expect(derniersParams()).toEqual({ page: 2 }))

      fireEvent.click(screen.getByRole('combobox', { name: 'Tri' }))
      fireEvent.click(await screen.findByRole('option', { name: 'Titre' }))
      // `ordering=` part, et la page est revenue à 1 (absente des params).
      await waitFor(() => expect(derniersParams()).toEqual({ ordering: 'titre' }))
    })

    it('le sens croissant/décroissant inverse le préfixe `-` de `ordering=`', async () => {
      rendre()
      await waitFor(() => expect(mocks.list).toHaveBeenCalled())
      fireEvent.click(screen.getByRole('combobox', { name: 'Tri' }))
      fireEvent.click(await screen.findByRole('option', { name: 'Statut' }))
      await waitFor(() => expect(derniersParams()).toEqual({ ordering: 'statut' }))

      fireEvent.click(screen.getByRole('combobox', { name: 'Ordre' }))
      fireEvent.click(await screen.findByRole('option', { name: 'Décroissant' }))
      await waitFor(() => expect(derniersParams()).toEqual({ ordering: '-statut' }))
    })
  })
})

/* CALX406 — la colonne « Responsable », lue sur le contrat committé
   `calepinage_liste.json` (`responsable` = identifiant, `responsable_nom`). */
describe('CALX406 — la colonne « Responsable » de la liste', () => {
  const SANS_RESPONSABLE = { ...SANS_IMAGE, id: 90, responsable: null, responsable_nom: null }

  it('chaque vignette dit son responsable, ou qu’il n’y en a pas — jamais un nom deviné', async () => {
    mocks.list.mockResolvedValue({
      data: { count: 2, next: null, previous: null, results: [AVEC_IMAGE, SANS_RESPONSABLE] },
    })
    rendre()
    await screen.findByTestId(`cal-vignette-${AVEC_IMAGE.id}`)
    expect(screen.getByTestId(`cal-responsable-${AVEC_IMAGE.id}`))
      .toHaveTextContent(`Responsable : ${AVEC_IMAGE.responsable_nom}`)
    expect(screen.getByTestId(`cal-responsable-${SANS_RESPONSABLE.id}`))
      .toHaveTextContent('Sans responsable')
  })

  it('la colonne « Responsable » FILTRE la liste : `?responsable=<id>` part au serveur', async () => {
    rendre()
    await screen.findByTestId(`cal-vignette-${AVEC_IMAGE.id}`)
    fireEvent.click(screen.getByRole('combobox', { name: 'Responsable' }))
    fireEvent.click(await screen.findByRole('option', { name: AVEC_IMAGE.responsable_nom }))
    await waitFor(() => expect(derniersParams())
      .toEqual({ responsable: String(AVEC_IMAGE.responsable) }))
  })

  it('« Tous les responsables » retire le filtre de la requête', async () => {
    rendre()
    await screen.findByTestId(`cal-vignette-${AVEC_IMAGE.id}`)
    fireEvent.click(screen.getByRole('combobox', { name: 'Responsable' }))
    fireEvent.click(await screen.findByRole('option', { name: AVEC_IMAGE.responsable_nom }))
    await waitFor(() => expect(derniersParams())
      .toEqual({ responsable: String(AVEC_IMAGE.responsable) }))
    fireEvent.click(screen.getByRole('combobox', { name: 'Responsable' }))
    fireEvent.click(await screen.findByRole('option', { name: 'Tous les responsables' }))
    await waitFor(() => expect(derniersParams()).toEqual({}))
  })

  it('la forme du sérialiseur de liste (identifiant + `responsable_nom`) s’affiche aussi', async () => {
    const ligneListe = { ...SANS_IMAGE, id: 42, responsable: 7, responsable_nom: 'Concepteur d’essai' }
    mocks.list.mockResolvedValue({
      data: { count: 1, next: null, previous: null, results: [ligneListe] },
    })
    rendre()
    expect(await screen.findByTestId('cal-responsable-42'))
      .toHaveTextContent('Responsable : Concepteur d’essai')
  })
})

/* ============================================================================
   ACAL115 — le statut DÉRIVÉ (servi) est affiché et alimente le filtre.
   ========================================================================== */
describe('CalepinageList (ACAL115)', () => {
  it('statut dérivé affiché', async () => {
    mocks.list.mockResolvedValue({
      data: {
        count: 1, next: null, previous: null,
        results: [{ ...AVEC_IMAGE, statut: 'perime', statut_libelle: 'Périmé' }],
      },
    })
    rendre()
    expect(await within(await screen.findByTestId(`cal-vignette-${AVEC_IMAGE.id}`)).findByText('Périmé')).toBeInTheDocument()
  })
})

/* Maquette « Liste » — la carte et les puces d'état : rien que ce que le serveur SERT. */
describe('CalepinageList — maquette Liste', () => {
  const COMPTEURS = { tous: 6, brouillon: 2, valide: 1, perime: 1, refuse: 2 }

  it('titre « Calepinages » + « N projets » + recherche + « Nouveau calepinage »', async () => {
    rendre()
    expect(screen.getByRole('heading', { name: 'Calepinages' })).toBeInTheDocument()
    expect(await screen.findByText('2 projets')).toBeInTheDocument()
    expect(screen.getByLabelText('Rechercher un calepinage')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Nouveau calepinage/ }))
    expect(mocks.navigate).toHaveBeenCalledWith('/calepinage/nouveau')
  })

  it('les puces : Tous + les statuts servis, avec leur effectif quand `compteurs_statut` est servi', async () => {
    mocks.list.mockResolvedValue({
      data: { count: 6, next: null, previous: null, results: [AVEC_IMAGE], compteurs_statut: COMPTEURS },
    })
    rendre()
    const groupe = await screen.findByTestId('cal-liste-filtres-etat')
    const noms = [...groupe.querySelectorAll('button')].map((b) => b.textContent)
    expect(noms).toEqual(['Tous6', 'Brouillon2', 'Validé1', 'Périmé1', 'Refusé2'])
    fireEvent.click(screen.getByRole('button', { name: /^Brouillon/ }))
    await waitFor(() => expect(derniersParams()).toEqual({ statut: 'brouillon' }))
    expect(screen.getByRole('button', { name: /^Brouillon/ })).toHaveAttribute('aria-pressed', 'true')
  })

  it('sans `compteurs_statut`, les puces n’affichent AUCUN nombre', async () => {
    rendre()
    const groupe = await screen.findByTestId('cal-liste-filtres-etat')
    expect([...groupe.querySelectorAll('button')].map((b) => b.textContent))
      .toEqual(['Tous', 'Brouillon', 'Validé', 'Périmé', 'Refusé'])
  })

  it('la ligne « kWc · panneaux · kWh/an » n’affiche que les morceaux servis', async () => {
    const complete = { ...AVEC_IMAGE, id: 301, kwc: 6.96, layout_nb_panneaux: 12, production_kwh_an: 11480 }
    const partielle = { ...SANS_IMAGE, id: 302, kwc: null, layout_nb_panneaux: 8, production_kwh_an: null }
    const nulle = { ...SANS_IMAGE, id: 303, kwc: null, layout_nb_panneaux: null, production_kwh_an: null }
    mocks.list.mockResolvedValue({
      data: { count: 3, next: null, previous: null, results: [complete, partielle, nulle] },
    })
    rendre()
    const c1 = await screen.findByTestId('cal-vignette-301')
    // Le séparateur de milliers français est une espace fine insécable : on compare à l'espace simple.
    // ACAL1310 (langage v2) — le kWc en grand chiffre, panneaux et production à côté.
    expect(c1.textContent.replace(/\s/g, ' ')).toContain('6,96 kWc12 panneaux · 11 480 kWh/an')
    expect(within(c1).getByText('kWc').className).toContain('cliste-unite')
    expect(screen.getByTestId('cal-vignette-302')).toHaveTextContent('8 panneaux')
    expect(screen.getByTestId('cal-vignette-302')).not.toHaveTextContent('kWc')
    expect(screen.getByTestId('cal-vignette-303').textContent).not.toMatch(/panneau|kWc|kWh/)
  })

  it('la grille a TROIS colonnes au plus, comme la maquette (jamais quatre)', async () => {
    const { container } = rendre()
    await screen.findByTestId(`cal-vignette-${AVEC_IMAGE.id}`)
    const grille = container.querySelector('[class*="lg:grid-cols-3"]')
    expect(grille).not.toBeNull()
    expect(grille.className).not.toMatch(/grid-cols-4/)
  })

  it('« points à régler » : seulement quand le serveur le sert et > 0 ; avatar = initiales du responsable', async () => {
    const avec = { ...AVEC_IMAGE, id: 311, points_a_regler: 1, responsable_nom: 'Hamza Bennani' }
    const sans = { ...SANS_IMAGE, id: 312 }
    mocks.list.mockResolvedValue({ data: { count: 2, next: null, previous: null, results: [avec, sans] } })
    rendre()
    const carteAvec = await screen.findByTestId('cal-vignette-311')
    expect(carteAvec).toHaveTextContent('1 point à régler')
    expect(screen.getByTestId('cal-vignette-312')).not.toHaveTextContent('à régler')
    expect(screen.getByTestId('cal-responsable-311')).toHaveTextContent('HB')
    expect(screen.getByTestId('cal-responsable-311')).toHaveTextContent('Responsable : Hamza Bennani')
  })

  it('ACAL1310 — le verdict rangé : « N points à régler », « À relire » si le document a changé, rien sinon ; l’état sur l’aperçu', async () => {
    // Les trois cas du contrat : rangé (1 point), jamais lu (null), périmé (null + « à relire »).
    const range = { ...AVEC_IMAGE, id: 341 }
    const jamais = { ...CLIENT_SEUL, id: 342 }
    const perime = { ...SANS_IMAGE, id: 343 }
    const zero = { ...AVEC_IMAGE, id: 344, points_a_regler: 0 }
    mocks.list.mockResolvedValue({ data: { count: 4, next: null, previous: null, results: [range, jamais, perime, zero] } })
    rendre()
    expect(await screen.findByTestId('cal-signal-341')).toHaveTextContent('1 point à régler')
    expect(screen.queryByTestId('cal-signal-342')).toBeNull()
    expect(screen.getByTestId('cal-signal-343')).toHaveTextContent('À relire')
    expect(screen.getByTestId('cal-signal-343')).toHaveAttribute('data-ton', 'relire')
    expect(screen.queryByTestId('cal-signal-344')).toBeNull()
    const etat = within(screen.getByTestId('cal-vignette-341')).getByText(range.statut_libelle)
    expect(etat.className).toContain('cliste-etat')
    expect(etat.closest('.cliste-apercu')).not.toBeNull()
  })

  it('la ville se lit sur le client rattaché, à défaut sur le lead', async () => {
    const parLead = { ...SANS_IMAGE, id: 321, client_apercu: null, lead: { id: 1, nom: 'L', ville: 'Fès', supprime: false } }
    mocks.list.mockResolvedValue({ data: { count: 1, next: null, previous: null, results: [parLead] } })
    rendre()
    expect(await screen.findByTestId('cal-vignette-321')).toHaveTextContent('Fès')
  })

  it('le titre de la carte est le client (puis la ville), le nom propre passe en petit ; sans rattachement il reste le titre', async () => {
    const lie = { ...SANS_IMAGE, id: 331, nom: 'ACAL987 Toiture x7', client_apercu: { id: 4, nom: 'Villa Bennani' }, lead: { id: 5, nom: 'Villa Bennani', ville: 'Casablanca', supprime: false } }
    const libre = { ...SANS_IMAGE, id: 332, nom: 'Toiture libre', client_apercu: null, lead: null }
    mocks.list.mockResolvedValue({ data: { count: 2, next: null, previous: null, results: [lie, libre] } })
    rendre()
    const carte = await screen.findByTestId('cal-vignette-331')
    expect(within(carte).getByText('Villa Bennani').className).toContain('font-semibold')
    expect(carte).toHaveTextContent('Casablanca')
    expect(within(carte).getByTestId('liste-vignette-nom')).toHaveTextContent('ACAL987 Toiture x7')
    const libreCarte = screen.getByTestId('cal-vignette-332')
    expect(within(libreCarte).getByText('Toiture libre').className).toContain('font-semibold')
    expect(within(libreCarte).queryByTestId('liste-vignette-nom')).toBeNull()
    expect(screen.getByPlaceholderText('Client, ville ou lead')).toBeInTheDocument()
  })

  it('ACAL1336 — sans image, la carte dessine les pans servis ; sans tracé, « Aucun aperçu »', async () => {
    const trace = { ...SANS_IMAGE, id: 351, apercu_toit: AVEC_IMAGE.apercu_toit }
    const rien = { ...SANS_IMAGE, id: 352 }
    mocks.list.mockResolvedValue({ data: { count: 3, next: null, previous: null, results: [trace, rien, AVEC_IMAGE] } })
    rendre()
    const carte = await screen.findByTestId('cal-vignette-351')
    const polygones = carte.querySelectorAll('[data-testid="cal-vignette-toit"] polygon')
    expect(polygones).toHaveLength(AVEC_IMAGE.apercu_toit.contours.length)
    expect(polygones[0].getAttribute('points')).toBe(
      AVEC_IMAGE.apercu_toit.contours[0].map(([x, y]) => `${x},${y}`).join(' '))
    expect(within(carte).queryByText('Aucun aperçu')).toBeNull()
    expect(within(screen.getByTestId('cal-vignette-352')).getByText('Aucun aperçu')).toBeInTheDocument()
    // Une image servie reste l'aperçu (le tracé ne la remplace pas).
    expect(within(screen.getByTestId(`cal-vignette-${AVEC_IMAGE.id}`)).getByTestId('cal-vignette-image')).toBeInTheDocument()
  })

  it('une image qui ne se charge pas retombe sur « Aucun aperçu »', async () => {
    const sansTrace = { ...AVEC_IMAGE, apercu_toit: null }
    mocks.list.mockResolvedValue({ data: { count: 1, next: null, previous: null, results: [sansTrace] } })
    rendre()
    const img = await screen.findByTestId('cal-vignette-image')
    fireEvent.error(img)
    expect(await screen.findByTestId('cal-vignette-sans-image')).toHaveTextContent('Aucun aperçu')
    expect(screen.queryByTestId('cal-vignette-image')).toBeNull()
  })

  it('« Mes calepinages » : absent sans personne connectée', async () => {
    rendre()
    await screen.findByTestId('cal-liste-filtres-etat')
    expect(screen.queryByRole('button', { name: 'Mes calepinages' })).toBeNull()
  })

  it('« Mes calepinages » : filtre `?responsable=<mon id>` puis le retire', async () => {
    const magasin = configureStore({ reducer: { auth: () => ({ user: { id: 3 } }) } })
    render(
      <Provider store={magasin}>
        <MemoryRouter><ThemeProvider><CalepinageList /></ThemeProvider></MemoryRouter>
      </Provider>,
    )
    const puce = await screen.findByRole('button', { name: 'Mes calepinages' })
    fireEvent.click(puce)
    await waitFor(() => expect(derniersParams()).toEqual({ responsable: '3' }))
    expect(puce).toHaveAttribute('aria-pressed', 'true')
    // « mon id » n'est pas un filtre avancé : la barre reste repliée.
    expect(screen.getByTestId('acal957-filtres').className).toContain('hidden')
    fireEvent.click(puce)
    await waitFor(() => expect(derniersParams()).toEqual({}))
  })
})

describe('CalepinageList.helpers — modifieDe / initiales', () => {
  const MAINTENANT = new Date(2026, 10, 22, 16, 0)

  it('modifieDe : aujourd’hui, hier, puis la date', () => {
    expect(modifieDe(new Date(2026, 10, 22, 14, 41).toISOString(), MAINTENANT)).toBe("Modifié aujourd'hui à 14:41")
    expect(modifieDe(new Date(2026, 10, 21, 17, 20).toISOString(), MAINTENANT)).toBe('Modifié hier à 17:20')
    expect(modifieDe(new Date(2026, 9, 18, 9, 0).toISOString(), MAINTENANT)).toBe('Modifié 18 octobre')
    expect(modifieDe(new Date(2025, 10, 18, 9, 0).toISOString(), MAINTENANT)).toBe('Modifié 18 novembre 2025')
    expect(modifieDe(null, MAINTENANT)).toBeNull()
  })

  it('initiales : deux lettres au plus, null sans nom', () => {
    expect(initiales('Hamza Bennani')).toBe('HB')
    expect(initiales('demo_admin')).toBe('D')
    expect(initiales('')).toBeNull()
  })
})

describe('CalepinageList.helpers — identiteCarte / apercuVide', () => {
  it('identiteCarte : client, sinon lead, sinon nom propre', () => {
    expect(identiteCarte({ nom: 'N', client_apercu: { nom: 'C' }, lead: { nom: 'L', ville: 'Fès' } }))
      .toEqual({ titre: 'C', ville: 'Fès', propre: 'N' })
    expect(identiteCarte({ nom: 'N', lead: { nom: 'L', ville: 'Rabat' } }))
      .toEqual({ titre: 'L', ville: 'Rabat', propre: 'N' })
    expect(identiteCarte({ nom: 'N' })).toEqual({ titre: 'N', ville: null, propre: null })
    expect(identiteCarte({ nom: 'Pareil', client_apercu: { nom: 'Pareil' } }).propre).toBeNull()
  })

  it('apercuVide : tout blanc ou transparent = vide ; un pixel sombre = non', () => {
    expect(apercuVide(new Uint8ClampedArray([255, 255, 255, 255, 0, 0, 0, 0]))).toBe(true)
    expect(apercuVide(new Uint8ClampedArray([255, 255, 255, 255, 20, 30, 40, 255]))).toBe(false)
    expect(apercuVide(new Uint8ClampedArray([]))).toBe(false)
  })
})
