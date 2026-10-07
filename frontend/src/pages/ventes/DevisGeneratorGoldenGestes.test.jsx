// SPL41 — golden des GESTES du générateur de devis, capturé sur le code ACTUEL
// avant tout déplacement (capture seule).
//
// SPL40 fige le DOM et les enregistrements, mais aucun geste : or les blocs que
// SPL44-SPL55 déplacent s'exécutent à l'ÉVÉNEMENT (handleAutoFill,
// recalculerDimensionnement, setLine, moveLine*, addLine, removeLine,
// add/rename/removeVillaGroup, handleRestoreDraft, revenirAVersion, validate,
// poserOverride/regenererOverride, applyLead/applyClient, contacterSuperieur,
// handleReset, setNote, cancel, onSearchClient, « Nouveau client »). Chaque
// geste est joué sur l'écran RÉEL (seules les API sont mockées : les 4 modules
// métier + le transport axios) ; après chaque pas on note le TEXTE UTILE du
// document (nœuds texte + valeurs des champs) et, à la fin, le JSON des
// mock.calls : le tout est figé dans generator/__golden__/gestes-<nom>.txt.
//
// Un golden ROUGE après un déplacement = un bug du déplacement : ne JAMAIS le
// régénérer pour faire passer (NE PAS FAIRE du groupe SPL). En CI
// (`CI=true vitest run`) vitest n'écrit aucun snapshot.
//
// Run : npx vitest run src/pages/ventes/DevisGeneratorGoldenGestes.test.jsx
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { screen, waitFor, fireEvent, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { exempleContrat, reponseContrat } from '../../test/fixtures/contractSamples'
import {
  CATALOGUE, LEAD, PANNEAU, ONDULEUR, CABLE, monter, normalise, stabiliser,
  preparerEnvironnement, chargerNeuf,
  devisAgricolePompeCourbe, devisMultiVillas, devisAdminRegistre,
  devisResidentielEtudeHoraire, devisIndustrielMt,
} from './DevisGeneratorGoldenHarnais'

vi.mock('../../api/crmApi', () => import('./DevisGeneratorGoldenMocks').then((m) => m.mockApi('crmApi', {
  searchClients: { results: [] }, checkDuplicates: { matches: [] },
})))
vi.mock('../../api/stockApi', () => import('./DevisGeneratorGoldenMocks').then((m) => m.mockApi('stockApi')))
vi.mock('../../api/parametresApi', () => import('./DevisGeneratorGoldenMocks').then((m) => m.mockApi('parametresApi')))
vi.mock('../../api/ventesApi', () => import('./DevisGeneratorGoldenMocks').then((m) => m.mockApi('ventesApi', {
  getPrixApplicable: { source: 'standard' }, getHistoriqueConfigurationDevis: { snapshots: [] },
  composerDevis: { lignes: [] }, contacterSuperieur: {},
})))
vi.mock('../../api/axios', () => import('./DevisGeneratorGoldenMocks').then((m) => m.mockApi('axios')))

const DOSSIER = './generator/__golden__'
// Écran lourd + attente de stabilité après chaque pas : marge large pour un
// poste ou un runner chargé.
const DELAI_GESTE = 180000

globalThis.process.env.TZ = 'Africa/Casablanca'

// ── Lecture du TEXTE UTILE du document (portails compris) ──────────────────
function libelleChamp(el) {
  return el.getAttribute('id') || el.getAttribute('name')
    || el.getAttribute('aria-label') || el.getAttribute('data-role')
    || el.getAttribute('placeholder') || el.getAttribute('type') || el.tagName.toLowerCase()
}

function etatUtile() {
  const lignes = []
  const marcheur = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {
    acceptNode: (n) => {
      const parent = n.parentElement
      if (parent && /^(SCRIPT|STYLE)$/.test(parent.tagName)) return NodeFilter.FILTER_REJECT
      return n.nodeValue.trim() ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT
    },
  })
  while (marcheur.nextNode()) lignes.push(marcheur.currentNode.nodeValue.trim())
  const champs = [...document.body.querySelectorAll('input, select, textarea')].map((el) => {
    const valeur = (el.type === 'checkbox' || el.type === 'radio') ? `checked=${el.checked}` : el.value
    return `[champ] ${libelleChamp(el)} = ${valeur}${el.disabled ? ' (désactivé)' : ''}`
  })
  return `${lignes.join('\n')}\n${champs.join('\n')}`
}

/** Journal d'un geste : un bloc par pas, puis les appels, figé en .txt. */
function journal() {
  const blocs = []
  return {
    async pas(nom) {
      await stabiliser(document.body)
      blocs.push(`### ${nom}\n${normalise(etatUtile())}`)
    },
    appels(apis) {
      const sortie = {}
      for (const [module, noms] of Object.entries(apis.liste)) {
        for (const nom of noms) {
          const fn = apis[module][nom]
          sortie[`${module}.${nom}`] = fn && fn.mock ? fn.mock.calls : null
        }
      }
      // Aperçus temporisés (500 ms) : leur NOMBRE d'appels dépend de la charge
      // du poste ; seul le DERNIER corps (celui de l'état final) est figé.
      for (const [module, noms] of Object.entries(apis.dernier || {})) {
        for (const nom of noms) {
          const fn = apis[module][nom]
          sortie[`${module}.${nom} (dernier appel)`] = fn && fn.mock ? (fn.mock.calls.at(-1) ?? null) : null
        }
      }
      sortie['window.confirm'] = window.confirm.mock ? window.confirm.mock.calls : null
      blocs.push(`### appels\n${JSON.stringify(sortie, null, 2)}`)
    },
    async figer(nom) {
      await expect(`${blocs.join('\n\n')}\n`).toMatchFileSnapshot(`${DOSSIER}/gestes-${nom}.txt`)
    },
  }
}

const ECRITURES = [
  'replaceLignesDevis', 'createDevisAtomic', 'patchEtudeParams', 'poserOverrides',
  'regenererOverride', 'composerDevis', 'getPrixApplicable', 'contacterSuperieur',
]

// Catalogue DÉRIVÉ de la composition serveur committée (devis_composition.json) :
// mêmes ids, désignations et prix HT que l'exemple — aucun prix inventé.
const COMPOSITION = exempleContrat('ventes', 'devis_composition')
const CATALOGUE_COMPOSITION = [
  ...new Map(COMPOSITION.lignes.map((l) => [l.produit, {
    id: l.produit, nom: l.designation, prix_vente: Number(l.prix_unitaire_ht),
    tva: Number(l.taux_tva), is_archived: false,
  }])).values(),
]

const ETUDE_HORAIRE = reponseContrat('ventes', 'etude_horaire')

/** Le bouton de SOUMISSION du formulaire (« Créer le devis » apparaît aussi ailleurs). */
async function boutonSoumettre() {
  await screen.findAllByRole('button', { name: /Créer le devis/ })
  return document.querySelector('form button[type="submit"]')
}

beforeEach(() => preparerEnvironnement({ confirmeAccepte: true }))

afterEach(() => {
  vi.useRealTimers()
})

describe('SPL41 — golden des gestes du générateur', () => {
  it('Auto-remplir résidentiel (composition serveur) puis échec serveur', async () => {
    const apis = await chargerNeuf(CATALOGUE_COMPOSITION)
    const { ventesApi, DevisGenerator } = apis
    ventesApi.postEtudeHorairePreview.mockResolvedValue(ETUDE_HORAIRE)
    ventesApi.composerDevis.mockResolvedValue({ data: COMPOSITION })
    monter(DevisGenerator, '/ventes/devis/nouveau')
    const j = journal()
    await screen.findByRole('radio', { name: /Résidentiel/ })
    fireEvent.change(screen.getByLabelText(/Facture Hiver/), { target: { value: '1200' } })
    await waitFor(() => expect(parseFloat(screen.getByLabelText(/Nombre de panneaux/).value) || 0)
      .toBeGreaterThan(0), { timeout: 10000 })
    await j.pas('facture hiver 1200 → taille du moteur')
    fireEvent.click(screen.getByTestId('btn-auto-remplir'))
    await waitFor(() => expect(ventesApi.composerDevis).toHaveBeenCalled(), { timeout: 10000 })
    await j.pas('Auto-remplir → lignes de la composition serveur')
    ventesApi.composerDevis.mockRejectedValue({ response: { data: { detail: 'Catalogue incomplet : aucun onduleur réseau actif.' } } })
    fireEvent.click(screen.getByTestId('btn-auto-remplir'))
    await screen.findByTestId('composition-erreur')
    await j.pas('Auto-remplir refusé par le serveur → erreur rendue, lignes inchangées')
    j.appels({ ...apis, liste: { ventesApi: ECRITURES }, dernier: { ventesApi: ['postEtudeHorairePreview'] } })
    await j.figer('autofill-residentiel')
  }, DELAI_GESTE)

  it('Auto-remplir agricole (kit serveur, pompe à courbe)', async () => {
    const apis = await chargerNeuf()
    const { ventesApi, api, DevisGenerator } = apis
    const devis = devisAgricolePompeCourbe()
    ventesApi.getDevisById.mockResolvedValue({ data: devis })
    const pompage = exempleContrat('ventes', 'etude_pompage_preview')
    api.post.mockImplementation((url) => Promise.resolve(
      { data: String(url).includes('etude-pompage') ? pompage : null }))
    monter(DevisGenerator, `/ventes/devis/nouveau?edit=${devis.id}`)
    const j = journal()
    await screen.findByTestId('resultat-pompage', {}, { timeout: 10000 })
    await j.pas('devis agricole rouvert, aperçu de pompage servi')
    fireEvent.click(screen.getByTestId('btn-auto-remplir'))
    await screen.findByTestId('pompage-auto-rempli')
    await j.pas('Auto-remplir → lignes du kit serveur')
    j.appels({ ...apis, liste: { ventesApi: ECRITURES }, dernier: { api: ['post'] } })
    await j.figer('autofill-agricole')
  }, DELAI_GESTE)

  it('Recalculer le dimensionnement', async () => {
    const apis = await chargerNeuf(CATALOGUE_COMPOSITION)
    const { ventesApi, DevisGenerator } = apis
    ventesApi.postEtudeHorairePreview.mockResolvedValue(ETUDE_HORAIRE)
    ventesApi.composerDevis.mockResolvedValue({ data: COMPOSITION })
    monter(DevisGenerator, '/ventes/devis/nouveau')
    const j = journal()
    await screen.findByRole('radio', { name: /Résidentiel/ })
    fireEvent.change(screen.getByLabelText(/Facture Hiver/), { target: { value: '1200' } })
    await waitFor(() => expect(parseFloat(screen.getByLabelText(/Nombre de panneaux/).value) || 0)
      .toBeGreaterThan(0), { timeout: 10000 })
    fireEvent.change(screen.getByLabelText(/Nombre de panneaux/), { target: { value: '3' } })
    // Le pas attend ~1 s de calme : l'aperçu horaire du corps courant est
    // servi, donc UN clic suffit (pas de « réessayez dans un instant »).
    await j.pas('taille saisie à la main : 3 panneaux')
    fireEvent.click(screen.getByTestId('btn-recalculer-dimensionnement'))
    await waitFor(() => expect(ventesApi.composerDevis).toHaveBeenCalled(), { timeout: 10000 })
    await j.pas('Recalculer → taille du moteur + composition')
    j.appels({ ...apis, liste: { ventesApi: ECRITURES }, dernier: { ventesApi: ['postEtudeHorairePreview'] } })
    await j.figer('recalcul-dimensionnement')
  }, DELAI_GESTE)

  it('lignes : produit, quantité, monter/descendre, supprimer, ajouter', async () => {
    const apis = await chargerNeuf()
    const { ventesApi, DevisGenerator } = apis
    const devis = devisResidentielEtudeHoraire()
    devis.lignes.push({
      id: 3, produit: CABLE.id, designation: CABLE.nom, quantite: '40',
      prix_unitaire: '20.00', taux_tva: '20.00', ordre: 2, type_ligne: 'produit', optionnelle: false,
    })
    ventesApi.getDevisById.mockResolvedValue({ data: devis })
    ventesApi.getPrixApplicable.mockImplementation(({ produit }) => Promise.resolve({
      data: String(produit) === String(ONDULEUR.id)
        ? { source: 'liste', liste_nom: 'Revendeur', prix: 9900 } : { source: 'standard' },
    }))
    monter(DevisGenerator, `/ventes/devis/nouveau?edit=${devis.id}`)
    const j = journal()
    await screen.findByDisplayValue(CABLE.nom)
    await j.pas('trois lignes rouvertes')
    // Changer le produit de la ligne câble → onduleur (getPrixApplicable).
    const ligneCable = screen.getByDisplayValue(CABLE.nom).closest('tr')
    await userEvent.click(within(ligneCable).getByRole('button', { name: new RegExp(CABLE.nom) }))
    await userEvent.type(await screen.findByPlaceholderText(/Chercher un produit/), 'Onduleur')
    await userEvent.click(await screen.findByRole('option', { name: new RegExp(ONDULEUR.nom) }))
    await waitFor(() => expect(ventesApi.getPrixApplicable).toHaveBeenCalled())
    await j.pas('ligne 3 : produit câble → onduleur (prix de liste)')
    const quantites = () => document.querySelectorAll('[data-role="line-qty"]')
    fireEvent.change(quantites()[0], { target: { value: '10' } })
    await j.pas('ligne 1 : quantité 10')
    fireEvent.click(screen.getAllByRole('button', { name: 'Descendre la ligne' })[0])
    await j.pas('ligne 1 descendue')
    fireEvent.click(screen.getAllByRole('button', { name: 'Monter la ligne' }).at(-1))
    await j.pas('dernière ligne montée')
    fireEvent.click(screen.getAllByRole('button', { name: 'Supprimer la ligne' }).at(-1))
    await j.pas('dernière ligne supprimée')
    fireEvent.click(screen.getByRole('button', { name: /Ajouter ligne/ }))
    await j.pas('ligne ajoutée')
    fireEvent.click(screen.getByTitle('Ajouter un intertitre de section (sans prix)'))
    await j.pas('intertitre de section ajouté')
    j.appels({ ...apis, liste: { ventesApi: ECRITURES } })
    await j.figer('lignes')
  }, DELAI_GESTE)

  it('villas : ajouter, renommer, retirer un groupe', async () => {
    const apis = await chargerNeuf()
    const { ventesApi, DevisGenerator } = apis
    const devis = devisMultiVillas()
    ventesApi.getDevisById.mockResolvedValue({ data: devis })
    monter(DevisGenerator, `/ventes/devis/nouveau?edit=${devis.id}`)
    const j = journal()
    await screen.findByRole('columnheader', { name: 'Villa' })
    await j.pas('devis multi-villas rouvert')
    fireEvent.click(screen.getByRole('button', { name: /Ajouter une villa/ }))
    await j.pas('villa ajoutée')
    fireEvent.change(screen.getByLabelText('Nom du groupe 1'), { target: { value: 'Villa Atlas' } })
    await j.pas('groupe 1 renommé « Villa Atlas »')
    const champ2 = screen.getByLabelText('Nom du groupe 2')
    const retirer = within(champ2.parentElement).getAllByRole('button').at(-1)
    fireEvent.click(retirer)
    await j.pas('groupe 2 retiré')
    j.appels({ ...apis, liste: { ventesApi: ECRITURES } })
    await j.figer('villas')
  }, DELAI_GESTE)

  it('restauration d’un brouillon local', async () => {
    const apis = await chargerNeuf()
    const { DevisGenerator } = apis
    window.localStorage.setItem('taqinor:draft:devis:new', JSON.stringify({
      savedAt: '2026-10-05T09:30:00Z',
      data: {
        note: 'Brouillon golden', fHiver: '900', nbPanneaux: '6', scenario: 'Sans batterie',
        lines: [
          { produit: String(PANNEAU.id), designation: PANNEAU.nom, quantite: '6',
            prix_unit_ttc: '1320', taux_tva: 10, typeLigne: 'produit' },
          { produit: String(ONDULEUR.id), designation: ONDULEUR.nom, quantite: '1',
            prix_unit_ttc: '10800', taux_tva: 20, typeLigne: 'produit' },
        ],
      },
    }))
    monter(DevisGenerator, '/ventes/devis/nouveau')
    const j = journal()
    const bandeau = await screen.findByTestId('draft-restore-banner')
    await j.pas('bandeau « Reprendre le brouillon » proposé')
    fireEvent.click(within(bandeau).getAllByRole('button')[0])
    await waitFor(() => expect(screen.queryByTestId('draft-restore-banner')).toBeNull())
    await j.pas('brouillon restauré')
    j.appels({ ...apis, liste: { ventesApi: ECRITURES } })
    await j.figer('brouillon-restauration')
  }, DELAI_GESTE)

  it('revenir à une version (historique de configuration)', async () => {
    const apis = await chargerNeuf()
    const { ventesApi, DevisGenerator } = apis
    const devis = devisResidentielEtudeHoraire()
    ventesApi.getDevisById.mockResolvedValue({ data: devis })
    // Deux versions : l'ancienne = l'exemple committé, la récente = sa copie
    // datée d'après (« Revenir » n'est offert que sur une version antérieure).
    const ancienne = exempleContrat('ventes', 'devis_historique_configuration').snapshots[0]
    const recente = { ...ancienne, id: ancienne.id + 1, date: '2026-10-01T09:00:00+00:00' }
    ventesApi.getHistoriqueConfigurationDevis.mockResolvedValue(
      { data: { snapshots: [ancienne, recente] } })
    monter(DevisGenerator, `/ventes/devis/nouveau?edit=${devis.id}`)
    const j = journal()
    await screen.findByTestId('historique-configuration')
    const revenir = await screen.findByRole('button', { name: /Revenir à cette version/ })
    await j.pas('historique affiché')
    fireEvent.click(revenir)
    await waitFor(() => expect(ventesApi.replaceLignesDevis).toHaveBeenCalled(), { timeout: 10000 })
    await j.pas('version restaurée et enregistrée')
    j.appels({ ...apis, liste: { ventesApi: [...ECRITURES, 'getHistoriqueConfigurationDevis'] } })
    await j.figer('version-restauree')
  }, DELAI_GESTE)

  it('refus de validation : client absent, industriel sans conso, kWh incohérent, aucune ligne', async () => {
    const j = journal()
    let apis = await chargerNeuf()
    let rendu = monter(apis.DevisGenerator, '/ventes/devis/nouveau')
    fireEvent.click(await boutonSoumettre())
    await j.pas('création sans lead ni client')
    rendu.unmount()
    window.localStorage.clear()

    apis = await chargerNeuf()
    const industriel = devisIndustrielMt()
    delete industriel.etude_params.consommation
    apis.ventesApi.getDevisById.mockResolvedValue({ data: industriel })
    rendu = monter(apis.DevisGenerator, `/ventes/devis/nouveau?edit=${industriel.id}`)
    fireEvent.click(await screen.findByRole('button', { name: /Enregistrer les modifications/ }))
    await screen.findByTestId('erreur-enregistrement')
    await j.pas('industriel sans consommation')
    rendu.unmount()
    window.localStorage.clear()

    apis = await chargerNeuf()
    // ERR-QAC-KWH-SAISI-INCOHERENT-FACTURES : 5 000 kWh/mois déclarés pour une
    // facture de 300 MAD — contradiction > 2×.
    const leadIncoherent = { ...LEAD, facture_hiver: '300', conso_mensuelle_kwh: 5000 }
    apis.crmApi.getLeads.mockResolvedValue({ data: [leadIncoherent] })
    apis.crmApi.getLead.mockResolvedValue({ data: leadIncoherent })
    rendu = monter(apis.DevisGenerator, `/ventes/devis/nouveau?lead=${LEAD.id}`)
    await waitFor(() => expect(document.body.textContent).toContain(LEAD.prenom))
    fireEvent.click(await boutonSoumettre())
    await j.pas('kWh déclaré contredit par les factures')
    rendu.unmount()
    window.localStorage.clear()

    apis = await chargerNeuf()
    const vide = { ...devisResidentielEtudeHoraire(), lignes: [] }
    apis.ventesApi.getDevisById.mockResolvedValue({ data: vide })
    rendu = monter(apis.DevisGenerator, `/ventes/devis/nouveau?edit=${vide.id}`)
    const bouton = await screen.findByRole('button', { name: /Enregistrer les modifications/ })
    await stabiliser(document.body)
    for (const b of screen.queryAllByRole('button', { name: 'Supprimer la ligne' })) fireEvent.click(b)
    fireEvent.click(bouton)
    await j.pas('aucune ligne exploitable')
    j.appels({ ...apis, liste: { ventesApi: ECRITURES } })
    await j.figer('validation-refus')
  }, DELAI_GESTE)

  it('admin : poser une surcharge puis régénérer', async () => {
    const apis = await chargerNeuf()
    const { ventesApi, DevisGenerator } = apis
    const devis = devisAdminRegistre()
    const registre = reponseContrat('ventes', 'devis_overrides')
    ventesApi.getDevisById.mockResolvedValue({ data: devis })
    ventesApi.lireOverrides.mockResolvedValue(registre)
    ventesApi.poserOverrides.mockResolvedValue(registre)
    ventesApi.regenererOverride.mockResolvedValue(reponseContrat('ventes', 'devis_overrides', 'exemple_vide'))
    monter(DevisGenerator, `/ventes/devis/nouveau?edit=${devis.id}`, { role: 'admin' })
    const j = journal()
    await screen.findByTestId('overrides-panel')
    await j.pas('registre affiché')
    fireEvent.change(screen.getByTestId('overrides-chemin'), { target: { value: 'taille.nb_panneaux' } })
    fireEvent.change(screen.getByTestId('overrides-valeur'), { target: { value: '16' } })
    fireEvent.click(screen.getByTestId('overrides-poser'))
    await waitFor(() => expect(ventesApi.poserOverrides).toHaveBeenCalled())
    await j.pas('surcharge taille.nb_panneaux = 16 posée')
    fireEvent.click(screen.getByTestId('overrides-regenerer-taille.nb_panneaux'))
    await waitFor(() => expect(ventesApi.regenererOverride).toHaveBeenCalled())
    await j.pas('surcharge régénérée')
    j.appels({ ...apis, liste: { ventesApi: [...ECRITURES, 'lireOverrides'] } })
    await j.figer('surcharge-registre')
  }, DELAI_GESTE)

  it('lead/client : chercher et choisir un client, « Nouveau client », puis choisir un lead', async () => {
    const apis = await chargerNeuf()
    const { crmApi, DevisGenerator } = apis
    const CLIENT = { id: 12, nom: 'Société Golden', prenom: '', adresse: 'Rue des Tests, Casablanca', telephone: '0600000000' }
    crmApi.getLeads.mockResolvedValue({ data: [LEAD] })
    crmApi.getLead.mockResolvedValue({ data: LEAD })
    crmApi.searchClients.mockResolvedValue({ data: { results: [{ source: 'client', ...CLIENT }] } })
    monter(DevisGenerator, '/ventes/devis/nouveau')
    const j = journal()
    await screen.findByText('— Sélectionner un client —')
    await j.pas('création, aucun lead ni client')
    await userEvent.click(screen.getByText('— Sélectionner un client —'))
    await userEvent.type(await screen.findByPlaceholderText('Nom ou ICE…'), 'Golden')
    await waitFor(() => expect(crmApi.searchClients).toHaveBeenCalled())
    await userEvent.click(await screen.findByRole('option', { name: /Société Golden/ }))
    await j.pas('client cherché puis choisi')
    await userEvent.click(screen.getByRole('button', { name: /Nouveau client/ }))
    await screen.findByRole('dialog')
    await j.pas('« Nouveau client » ouvert')
    await userEvent.keyboard('{Escape}')
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    await userEvent.click(document.getElementById('gen-lead'))
    await userEvent.click(await screen.findByRole('option', { name: /Khalid/ }))
    await waitFor(() => expect(document.body.textContent).toContain('Client du devis'))
    await j.pas('lead choisi')
    j.appels({ ...apis, liste: { ventesApi: ECRITURES, crmApi: ['searchClients', 'getLead'] } })
    await j.figer('lead-client')
  }, DELAI_GESTE)

  it('pied d’édition : note client, contacter mon supérieur, réinitialiser, annuler', async () => {
    const apis = await chargerNeuf()
    const { ventesApi, DevisGenerator } = apis
    const devis = devisResidentielEtudeHoraire()
    ventesApi.getDevisById.mockResolvedValue({ data: devis })
    monter(DevisGenerator, `/ventes/devis/nouveau?edit=${devis.id}`)
    const j = journal()
    await screen.findByRole('button', { name: /Enregistrer les modifications/ })
    fireEvent.change(screen.getByPlaceholderText(/Conditions particulières/),
      { target: { value: 'Acompte 30 % à la commande.' } })
    await j.pas('note client saisie')
    fireEvent.click(screen.getByRole('button', { name: /Contacter mon supérieur/ }))
    await screen.findByText('Votre supérieur a été notifié.')
    await j.pas('supérieur notifié')
    // Réinitialiser : confirmation REFUSÉE (accepter recharge la page, ce que
    // jsdom ne sait pas faire) — on fige la question posée.
    window.confirm.mockReturnValue(false)
    fireEvent.click(screen.getByRole('button', { name: /Réinitialiser/ }))
    await waitFor(() => expect(window.confirm).toHaveBeenCalled())
    await j.pas('réinitialiser : confirmation refusée, rien ne change')
    fireEvent.click(within(document.querySelector('.gen-actions-sticky'))
      .getByRole('button', { name: 'Annuler' }))
    await screen.findByText('APRES-ENREGISTREMENT')
    await j.pas('annuler → retour à la liste')
    j.appels({ ...apis, liste: { ventesApi: ECRITURES } })
    await j.figer('pied-edition')
  }, DELAI_GESTE)

  it('Paramètres Techniques : refus du moteur (U3-900) et lignes ≠ cible', async () => {
    const apis = await chargerNeuf()
    const { ventesApi, DevisGenerator } = apis
    ventesApi.postEtudeHorairePreview.mockResolvedValue({
      data: { dimensionnement: { motivation: 'Ville du site inconnue : le moteur ne peut pas chiffrer la production.' } },
    })
    monter(DevisGenerator, '/ventes/devis/nouveau')
    const j = journal()
    await screen.findByRole('radio', { name: /Résidentiel/ })
    fireEvent.change(screen.getByLabelText(/Facture Hiver/), { target: { value: '1200' } })
    await screen.findByTestId('sizing-serveur-refus', {}, { timeout: 10000 })
    await j.pas('refus du moteur horaire rendu verbatim')
    fireEvent.change(screen.getByLabelText(/Nombre de panneaux/), { target: { value: '8' } })
    const panneau = screen.getAllByDisplayValue(/Panneau/)[0]?.closest('tr')
    const qte = panneau?.querySelector('[data-role="line-qty"]')
    if (qte) fireEvent.change(qte, { target: { value: '5' } })
    await j.pas('cible 8 panneaux, ligne panneau à 5')
    j.appels({ ...apis, liste: { ventesApi: ECRITURES }, dernier: { ventesApi: ['postEtudeHorairePreview'] } })
    await j.figer('parametres-techniques')
  }, DELAI_GESTE)
})
