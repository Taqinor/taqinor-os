// SPL41 — GOLDEN DES GESTES DU GÉNÉRATEUR (capture seule, avant tout déplacement).
//
// SPL40 fige le DOM et les enregistrements, mais aucun geste : or les blocs
// que SPL44-SPL55 déplacent s'exécutent à l'ÉVÉNEMENT (Auto-remplir, recalcul,
// lignes, villas, brouillon, version, validation, surcharges, lead/client,
// pied de création). Chaque geste ci-dessous est joué sur l'écran RÉEL
// (seules les API sont mockées — les quatre de SPL40, plus le client HTTP de
// l'aperçu pompage, appelé en direct par `etudePompagePreview.js`) et fige le
// texte utile du DOM + les valeurs des champs + TOUS les appels API dans
// `generator/__golden__/gestes-<nom>.txt`.
//
// Régénérer (après un changement VOULU, jamais pour un déplacement) :
//   npx vitest run src/pages/ventes/DevisGeneratorGoldenGestes.test.jsx -u
import { describe, it, expect, vi } from 'vitest'
import { cycleEcran } from '../../test/cycleEcran'
import { act, waitFor, fireEvent, cleanup, screen } from '@testing-library/react'

import {
  LEAD, CLIENT, DATE_FIGEE, monter, attendreStable, instantaneGeste,
  DEVIS_REGISTRE, DEVIS_MULTI_VILLAS, REGISTRE_NON_VIDE,
} from './DevisGeneratorGoldenHarnais'
import { exempleContrat } from '../../test/fixtures/contractSamples'

vi.mock('../../api/crmApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())
vi.mock('../../api/stockApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())
vi.mock('../../api/parametresApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())
vi.mock('../../api/ventesApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())
// L'aperçu pompage (AGR127) appelle le client HTTP en direct.
vi.mock('../../api/axios', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock(() => new Promise(() => {})))

const DOSSIER = './generator/__golden__'

const stable = (vue) => attendreStable(vue.container, act)

async function figerGeste(vue, nom) {
  await stable(vue)
  await expect(instantaneGeste(vue.container, vue)).toMatchFileSnapshot(`${DOSSIER}/gestes-${nom}.txt`)
}

const bouton = (texte) => {
  const b = [...document.querySelectorAll('button')].find((x) => texte.test(x.textContent || '')
    || texte.test(x.getAttribute('aria-label') || ''))
  expect(b, `bouton ${texte}`).toBeTruthy()
  return b
}
const cliquer = async (el) => { await act(async () => { fireEvent.click(el) }) }
const taper = async (el, valeur) => { await act(async () => { fireEvent.change(el, { target: { value: valeur } }) }) }

// Le <select> natif caché du Select Radix porte `onValueChange` (CI #752).
const selectNatifDe = (id) => document.getElementById(id)?.parentElement?.querySelector('select')

const LEAD_KWH_INCOHERENT = {
  ...LEAD, id: 78, nom: 'Bennani', prenom: 'Kwh', facture_hiver: '300',
  conso_mensuelle_kwh: '5000',
}

const LEAD_NU = { ...LEAD, id: 79, nom: 'Sans', prenom: 'Facture', facture_hiver: null }

cycleEcran({ date: DATE_FIGEE, pointerCapture: true, restaurer: true })

describe('SPL41 — golden des gestes du générateur', () => {
  it('Auto-remplir résidentiel (composition serveur)', async () => {
    const vue = await monter(`/ventes/devis/nouveau?lead=${LEAD.id}`, {
      avant: ({ ventesApi }) => {
        ventesApi.composerDevis.mockResolvedValue({ data: exempleContrat('ventes', 'devis_composition', 'exemple') })
      },
    })
    await stable(vue)
    await taper(screen.getByLabelText(/Nombre de panneaux/), '8')
    await cliquer(screen.getByTestId('btn-auto-remplir'))
    await waitFor(() => expect(vue.ventesApi.composerDevis).toHaveBeenCalled())
    await figerGeste(vue, 'autofill-residentiel')
  }, 60000)

  it('Auto-remplir agricole (pompe à courbe, aperçu pompage serveur)', async () => {
    const vue = await monter('/ventes/devis/nouveau', {
      avant: (apis) => {
        void apis
      },
    })
    const axios = (await import('../../api/axios')).default
    axios.post.mockImplementation((url) => (String(url).includes('etude-pompage/preview')
      ? Promise.resolve({ data: exempleContrat('ventes', 'etude_pompage_preview', 'exemple') })
      : new Promise(() => {})))
    await stable(vue)
    await cliquer(await screen.findByRole('radio', { name: /Agricole/ }))
    await cliquer(bouton(/^Pompe neuve$/))
    await cliquer(bouton(/^Volume déclaré$/))
    await taper(document.getElementById('gen-besoin-volume'), '120')
    await taper(document.getElementById('gen-hmt'), '60')
    await stable(vue)
    await cliquer(screen.getByTestId('btn-auto-remplir'))
    vue.axios = axios
    await figerGeste(vue, 'autofill-agricole')
  }, 60000)

  it('Recalculer le dimensionnement', async () => {
    const vue = await monter(`/ventes/devis/nouveau?lead=${LEAD.id}`, {
      avant: ({ ventesApi }) => {
        ventesApi.composerDevis.mockResolvedValue({ data: exempleContrat('ventes', 'devis_composition', 'exemple') })
      },
    })
    await stable(vue)
    await taper(screen.getByLabelText(/Nombre de panneaux/), '8')
    await cliquer(screen.getByTestId('btn-auto-remplir'))
    await stable(vue)
    await taper(screen.getByLabelText(/Nombre de panneaux/), '12')
    await cliquer(bouton(/Recalculer le dimensionnement/))
    await figerGeste(vue, 'recalcul-dimensionnement')
  }, 60000)

  it('lignes : produit, quantité, monter/descendre, supprimer, ajouter (produit + section)', async () => {
    const vue = await monter(`/ventes/devis/nouveau?edit=${DEVIS_REGISTRE.id}`, {
      devis: DEVIS_REGISTRE,
      avant: ({ ventesApi }) => {
        ventesApi.getPrixApplicable.mockResolvedValue({ data: { prix: '1100.00', source: 'liste', liste_nom: 'Revendeur' } })
      },
    })
    await stable(vue)
    const qtes = () => [...document.querySelectorAll('[data-role="line-qty"]')]
    await taper(qtes()[0], '10')
    await cliquer(document.querySelectorAll('button[aria-label="Descendre la ligne"]')[0])
    await cliquer(document.querySelectorAll('button[aria-label="Monter la ligne"]')[1])
    await cliquer(bouton(/Ajouter ligne/))
    await cliquer(bouton(/^\+ Section$|Section/))
    // Changer le produit de la ligne ajoutée (Combobox) → tarif applicable.
    const declencheurs = [...document.querySelectorAll('tr[data-line-key] [role="combobox"]')]
    if (declencheurs.length) {
      await cliquer(declencheurs[declencheurs.length - 1])
      const option = [...document.querySelectorAll('[role="option"]')]
        .find((o) => /Smart Meter/.test(o.textContent || ''))
      if (option) await cliquer(option)
    }
    await stable(vue)
    const supprimer = document.querySelectorAll('button[aria-label="Supprimer la ligne"]')
    await cliquer(supprimer[supprimer.length - 1])
    await figerGeste(vue, 'lignes')
  }, 60000)

  it('villas : ajouter, renommer, retirer un groupe', async () => {
    const vue = await monter(`/ventes/devis/nouveau?edit=${DEVIS_MULTI_VILLAS.id}`, { devis: DEVIS_MULTI_VILLAS })
    await stable(vue)
    await cliquer(bouton(/Ajouter une villa/))
    const noms = [...document.querySelectorAll('input[aria-label^="Nom du groupe"]')]
    await taper(noms[noms.length - 1], 'Villa C')
    await taper(noms[1], 'Villa A bis')
    const retirer = document.querySelectorAll('button[aria-label="Supprimer la villa"]')
    await cliquer(retirer[retirer.length - 1])
    await figerGeste(vue, 'villas')
  }, 60000)

  it('brouillon local : saisie, puis restauration à la réouverture', async () => {
    // Création sans lead : clé `devis:new` (la clé d'un lead n'est connue
    // qu'après son chargement, la lecture du brouillon se fait au montage).
    let vue = await monter('/ventes/devis/nouveau')
    await stable(vue)
    await taper(document.querySelector('textarea[placeholder^="Conditions particulières"]'), 'Pose sous quinzaine.')
    await stable(vue)
    cleanup()
    vue = await monter('/ventes/devis/nouveau')
    await stable(vue)
    await cliquer(bouton(/Reprendre le brouillon/))
    await figerGeste(vue, 'brouillon-restauration')
  }, 60000)

  it('revenir à une version (instantané → replace-lines)', async () => {
    const snap = exempleContrat('ventes', 'devis_historique_configuration').snapshots[0]
    const v1 = {
      ...snap, id: 90, date: '2026-09-29T08:00:00+00:00',
      contenu: { ...snap.contenu, lignes: snap.contenu.lignes.map((l) => ({ ...l, prix_unitaire: '100.00', lot: null })) },
    }
    const v2 = { ...snap, id: 91 }
    const vue = await monter(`/ventes/devis/nouveau?edit=${DEVIS_REGISTRE.id}`, {
      devis: DEVIS_REGISTRE, historique: { snapshots: [v1, v2] },
    })
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    await stable(vue)
    await cliquer(await screen.findByRole('button', { name: /Revenir à cette version/ }))
    await waitFor(() => expect(vue.ventesApi.replaceLignesDevis).toHaveBeenCalled())
    await figerGeste(vue, 'version-restauree')
  }, 60000)

  it('refus de validation : messages exacts', async () => {
    const messages = []
    const lireRefus = () => [...document.querySelectorAll('[data-testid="erreur-enregistrement"], .text-destructive, [role="alert"]')]
      .map((e) => (e.textContent || '').trim()).filter(Boolean)
    // (1) création vierge : ni lead ni client.
    let vue = await monter('/ventes/devis/nouveau')
    await stable(vue)
    await cliquer(bouton(/Créer le devis/))
    await stable(vue)
    messages.push('== client absent ==', ...lireRefus())
    cleanup()
    // (2) industriel sans consommation.
    vue = await monter(`/ventes/devis/nouveau?lead=${LEAD_NU.id}`, { leads: [LEAD, LEAD_NU] })
    await stable(vue)
    await cliquer(await screen.findByRole('radio', { name: /Industriel/ }))
    await stable(vue)
    await cliquer(bouton(/Créer le devis/))
    await stable(vue)
    messages.push('== industriel sans consommation ==', ...lireRefus())
    cleanup()
    // (3) kWh déclaré contredit par les factures du lead.
    vue = await monter(`/ventes/devis/nouveau?lead=${LEAD_KWH_INCOHERENT.id}`, { leads: [LEAD, LEAD_KWH_INCOHERENT] })
    await stable(vue)
    await cliquer(bouton(/Créer le devis/))
    await stable(vue)
    messages.push('== kWh déclaré incohérent ==', ...lireRefus())
    cleanup()
    // (4) aucune ligne exploitable (devis rouvert, toutes lignes retirées).
    vue = await monter(`/ventes/devis/nouveau?edit=${DEVIS_REGISTRE.id}`, { devis: DEVIS_REGISTRE })
    await stable(vue)
    for (;;) {
      const s = document.querySelectorAll('button[aria-label="Supprimer la ligne"]')
      if (!s.length) break
      await cliquer(s[0])
    }
    await cliquer(bouton(/Enregistrer les modifications/))
    await stable(vue)
    messages.push('== aucune ligne exploitable ==', ...lireRefus())
    await expect(`${messages.join('\n')}\n\n${instantaneGeste(vue.container, vue)}`)
      .toMatchFileSnapshot(`${DOSSIER}/gestes-validation-refus.txt`)
  }, 120000)

  it('admin : poser une surcharge puis régénérer', async () => {
    const vue = await monter(`/ventes/devis/nouveau?edit=${DEVIS_REGISTRE.id}`, {
      devis: DEVIS_REGISTRE, registre: REGISTRE_NON_VIDE, role: 'admin',
    })
    await stable(vue)
    await taper(screen.getByTestId('overrides-chemin'), 'scenario')
    await taper(screen.getByTestId('overrides-valeur'), '"Avec batterie"')
    await cliquer(screen.getByTestId('overrides-poser'))
    await waitFor(() => expect(vue.ventesApi.poserOverrides).toHaveBeenCalled())
    await stable(vue)
    const ligne = screen.getByTestId('overrides-effectif-row-scenario')
    const regen = ligne.querySelector('button')
    if (regen) await cliquer(regen)
    await figerGeste(vue, 'surcharge-registre')
  }, 60000)

  it('lead/client : chercher et choisir un client, nouveau client, puis choisir un lead', async () => {
    const vue = await monter('/ventes/devis/nouveau', {
      avant: ({ crmApi }) => {
        crmApi.searchClients.mockResolvedValue({ data: [CLIENT] })
      },
    })
    await stable(vue)
    // Combobox client : ouvrir, chercher (onSearchClient), choisir.
    await cliquer(document.getElementById('gen-client'))
    const recherche = document.querySelector('input[placeholder="Nom ou ICE…"]')
    if (recherche) await taper(recherche, 'Golden')
    await stable(vue)
    const option = [...document.querySelectorAll('[role="option"]')]
      .find((o) => /Client Golden/.test(o.textContent || ''))
    if (option) await cliquer(option)
    await stable(vue)
    // « Nouveau client » (QG3) ouvre la création rapide puis on la ferme.
    const nouveau = [...document.querySelectorAll('button')].find((b) => /Nouveau client/.test(b.textContent || ''))
    if (nouveau) {
      await cliquer(nouveau)
      await stable(vue)
      fireEvent.keyDown(document.activeElement || document.body, { key: 'Escape' })
    }
    // Lead choisi par le sélecteur (Radix → select natif caché).
    const natif = selectNatifDe('gen-lead')
    if (natif) await taper(natif, String(LEAD.id))
    await figerGeste(vue, 'lead-client')
  }, 60000)

  it('pied de création : note client, contacter le supérieur, réinitialiser (refusé), annuler', async () => {
    const vue = await monter(`/ventes/devis/nouveau?edit=${DEVIS_REGISTRE.id}`, {
      devis: DEVIS_REGISTRE,
      avant: ({ ventesApi }) => { ventesApi.contacterSuperieur.mockResolvedValue({ data: {} }) },
    })
    vi.spyOn(window, 'confirm').mockReturnValue(false)
    await stable(vue)
    await taper(document.querySelector('textarea[placeholder^="Conditions particulières"]'), 'Garantie 10 ans.')
    await cliquer(bouton(/Contacter mon supérieur/))
    await waitFor(() => expect(vue.ventesApi.contacterSuperieur).toHaveBeenCalled())
    await cliquer(bouton(/Réinitialiser/))
    await stable(vue)
    const dialogue = [...document.querySelectorAll('[role="alertdialog"] button, [role="dialog"] button')]
      .find((b) => /Annuler/.test(b.textContent || ''))
    if (dialogue) await cliquer(dialogue)
    await stable(vue)
    const avant = instantaneGeste(vue.container, vue)
    await cliquer([...document.querySelectorAll('button')].filter((b) => /^Annuler$/.test((b.textContent || '').trim())).at(-1))
    await stable(vue)
    await expect(`${avant}== APRÈS « Annuler » ==\n${document.body.textContent.includes('APRES-ENREGISTREMENT') ? 'navigation vers la liste des devis' : 'aucune navigation'}\n`)
      .toMatchFileSnapshot(`${DOSSIER}/gestes-pied-creation.txt`)
  }, 60000)
})
