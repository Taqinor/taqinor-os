import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { exempleContrat } from '../../../test/fixtures/contractSamples'
import ColleListes, { lignesACreer } from '../saisie/ColleListes'

const mocks = vi.hoisted(() => ({ saisieRapide: vi.fn() }))
vi.mock('../../../api/tachesApi', async (importOriginal) => ({ ...(await importOriginal()), saisieRapide: mocks.saisieRapide }))
// par défaut, une relecture ne lit rien (le titre tapé reste) ; R2-005 pose sa réponse
beforeEach(() => { mocks.saisieRapide.mockReset(); mocks.saisieRapide.mockResolvedValue({ data: { lignes: [] } }) })

/* TCH83 — Aperçu d'une liste collée (SCENARIO.md, lun. 2 nov. : « Salon Solaire Expo » et
   « Recrutement technicien », 3 lignes chacune = 6 tâches, 2 nouveaux projets). Le modèle de
   ligne est celui de `saisie_apercu.json` ; ce qui est ajouté (doublon, déjà faite, points en
   retrait) suit les clés du serveur (`apps/taches/saisie/collage.py`). */

const modele = exempleContrat('taches', 'saisie_apercu').lignes[0]

const ligne = (index, collage, titre, plus = {}) => ({
  ...modele,
  index,
  collage,
  titre,
  jetons: [],
  champs: { priorite: 0, nouveau_projet: { nom: collage === 0 ? 'Salon Solaire Expo' : 'Recrutement technicien', priorite: 2 } },
  deja_faite: false,
  doublon_de_ligne: null,
  ...plus,
})

const APERCU = {
  projets_communs: [
    { collage: 0, id: null, nom: 'Salon Solaire Expo', nouveau: true, priorite: 2, source: 'premiere_ligne' },
    { collage: 1, id: null, nom: 'Recrutement technicien', nouveau: true, priorite: 2, source: 'premiere_ligne' },
  ],
  lignes: [
    ligne(0, 0, 'Réserver le stand'),
    ligne(1, 0, 'Imprimer les kakémonos'),
    ligne(2, 0, 'Préparer la démo onduleur hybride'),
    ligne(3, 1, 'Publier l\'annonce'),
    ligne(4, 1, 'Trier les CV reçus'),
    ligne(5, 1, 'Valider le budget du poste'),
  ],
  projets_nouveaux: [
    { nom: 'Salon Solaire Expo', priorite: 2 },
    { nom: 'Recrutement technicien', priorite: 2 },
  ],
}

const monter = (apercu = APERCU, props = {}) => {
  const onCreer = vi.fn()
  const onCollerEncore = vi.fn()
  const onPriorite = vi.fn()
  render(
    <div className="tch">
      <ColleListes apercu={apercu} cid="cid1" onCreer={onCreer} onCollerEncore={onCollerEncore} onPriorite={onPriorite} {...props} />
    </div>,
  )
  return { onCreer, onCollerEncore, onPriorite }
}

describe('TCH83 — aperçu d\'une liste collée', () => {
  it('un projet par collage, priorité Moyenne par défaut, « Créer 6 tâches »', () => {
    monter()
    expect(screen.getByText('Aperçu de ta liste')).toBeInTheDocument()
    expect(screen.getByText('Nouveau projet : Salon Solaire Expo')).toBeInTheDocument()
    expect(screen.getByText('Nouveau projet : Recrutement technicien')).toBeInTheDocument()
    // passe visuelle n° 33 — la priorité est UNE puce « Moyenne ⌄ » dans l'en-tête du projet (premier-usage-1-apercu.html)
    for (const nom of ['Salon Solaire Expo', 'Recrutement technicien']) {
      const puce = screen.getByRole('button', { name: `Priorité du projet ${nom} : moyenne` })
      expect(puce).toHaveClass('puce', 'prio')
      expect(puce).toHaveTextContent('Moyenne')
      expect(puce.closest('.apercu-projet')).toHaveTextContent(`Nouveau projet : ${nom}`)
    }
    expect(screen.queryByRole('radiogroup')).toBeNull()
    expect(screen.getByText('6 tâches · 2 projets')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Créer 6 tâches' })).toBeInTheDocument()
    expect(screen.getAllByRole('checkbox')).toHaveLength(6)
  })

  it('décocher une ligne la retire de l\'envoi ; « Créer 1 tâche » au singulier ; titre modifiable', async () => {
    const user = userEvent.setup()
    const { onCreer } = monter()
    for (const titre of ['Imprimer les kakémonos', 'Préparer la démo onduleur hybride', 'Publier l\'annonce', 'Trier les CV reçus', 'Valider le budget du poste']) {
      await user.click(screen.getByRole('checkbox', { name: `Garder : ${titre}` }))
    }
    expect(screen.getByRole('button', { name: 'Créer 1 tâche' })).toBeInTheDocument()
    const champ = screen.getByRole('textbox', { name: 'Titre : Réserver le stand' })
    await user.clear(champ)
    await user.type(champ, 'Réserver le stand B12')
    await user.click(screen.getByRole('button', { name: 'Créer 1 tâche' }))
    expect(onCreer).toHaveBeenCalledTimes(1)
    const [lignes] = onCreer.mock.calls[0]
    expect(lignes).toHaveLength(1)
    expect(lignes[0]).toMatchObject({ titre: 'Réserver le stand B12', client_id: 'cid1:0', collage: 0 })
  })

  it('la priorité d\'un nouveau projet part avec ses lignes', async () => {
    const user = userEvent.setup()
    const { onPriorite } = monter(APERCU, { priorites: { 'Salon Solaire Expo': 3 } })
    expect(screen.getByRole('button', { name: 'Priorité du projet Salon Solaire Expo : haute' })).toHaveTextContent('Haute')
    await user.click(screen.getByRole('button', { name: 'Priorité du projet Recrutement technicien : moyenne' }))
    expect(await screen.findByRole('menuitemradio', { name: 'Moyenne' })).toHaveAttribute('aria-checked', 'true')
    await user.click(screen.getByRole('menuitemradio', { name: 'Basse' }))
    expect(onPriorite).toHaveBeenCalledWith('Recrutement technicien', 1)
    const lignes = lignesACreer(APERCU, { cochees: {}, titres: {}, enTache: {}, sousTaches: {} }, { cid: 'c', priorites: { 'Salon Solaire Expo': 3 } })
    expect(lignes[0].nouveau_projet).toEqual({ nom: 'Salon Solaire Expo', priorite: 3 })
    expect(lignes[3].nouveau_projet).toEqual({ nom: 'Recrutement technicien', priorite: 2 })
  })

  it('doublons et lignes déjà faites : décochés d\'office, avec leur raison', () => {
    monter({
      ...APERCU,
      lignes: [
        ligne(0, 0, 'Réserver le stand'),
        ligne(1, 0, 'Réserver le stand', { cochee: false, doublon_de_ligne: 0 }),
        ligne(2, 0, 'Appeler Karim', { cochee: false, deja_faite: true }),
        ligne(3, 0, 'Envoyer le devis', { cochee: false, doublon_de: 41 }),
        ligne(4, 0, 'Relancer Settat', { cochee: false, doublon_de: 42, doublon_projet: 'Ventes' }),
      ],
    })
    expect(screen.getByText('En double dans cette liste')).toBeInTheDocument()
    expect(screen.getByText('Déjà faite')).toBeInTheDocument()
    expect(screen.getByText('Déjà dans tes tâches')).toBeInTheDocument()
    // Raccord F2 — le projet du doublon, quand le serveur le sert
    expect(screen.getByText('Déjà dans « Ventes »')).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: 'Créer : Réserver le stand', checked: false })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Créer 1 tâche' })).toBeInTheDocument()
  })

  it('« En faire une tâche » : le projet de tête devient une tâche, ses lignes n\'y sont plus rattachées', async () => {
    const user = userEvent.setup()
    const { onCreer } = monter()
    await user.click(screen.getByRole('button', { name: 'En faire une tâche : Salon Solaire Expo' }))
    expect(screen.getByRole('button', { name: 'Créer 7 tâches' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Créer 7 tâches' }))
    const [lignes] = onCreer.mock.calls[0]
    expect(lignes[0]).toMatchObject({ titre: 'Salon Solaire Expo', collage: 0 })
    expect(lignes[0].nouveau_projet).toBeUndefined()
    expect(lignes[1].nouveau_projet).toBeUndefined()
    expect(lignes.find((l) => l.titre === 'Trier les CV reçus').nouveau_projet.nom).toBe('Recrutement technicien')
  })

  it('points en retrait = check-list de leur tâche ; « En faire des sous-tâches » les rend à part', async () => {
    const user = userEvent.setup()
    const avecPoints = {
      ...APERCU,
      lignes: [ligne(0, 0, 'Préparer la démo'), ligne(1, 0, 'Onduleur', { etape_de: 0 }), ligne(2, 0, 'Câbles', { etape_de: 0 })],
    }
    const { onCreer } = monter(avecPoints)
    expect(screen.getByRole('button', { name: 'Créer 1 tâche' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Créer 1 tâche' }))
    expect(onCreer.mock.calls[0][0][0].checklist).toEqual(['Onduleur', 'Câbles'])

    await user.click(screen.getByRole('button', { name: 'En faire des sous-tâches' }))
    expect(screen.getByRole('button', { name: 'Créer 3 tâches' })).toBeInTheDocument()
  })

  it('« Coller encore » rend la main ; rien d\'écrit avant « Créer » ; liste vide dite en une phrase', async () => {
    const user = userEvent.setup()
    const { onCreer, onCollerEncore } = monter()
    await user.click(screen.getByRole('button', { name: 'Coller encore' }))
    expect(onCollerEncore).toHaveBeenCalledTimes(1)
    expect(onCreer).not.toHaveBeenCalled()
  })

  describe('R2-004 — une liste « comme dans Notes » : un en-tête par titre de groupe', () => {
    const groupe = (index, titre, champs, plus = {}) => ({ ...ligne(index, 0, titre), champs: { priorite: 0, ...champs }, ...plus })
    const villa = { nouveau_projet: { nom: 'Villa Benjelloun', priorite: 2 } }
    const hotel = { nouveau_projet: { nom: 'Hôtel Atlas', priorite: 2 } }
    const NOTES = {
      projets_communs: [],
      lignes: [
        groupe(0, 'envoyer le devis', villa),
        groupe(1, 'appeler l\'architecte', villa),
        groupe(2, 'relancer le directeur', hotel),
        groupe(3, 'visite technique', hotel),
        groupe(4, 'devis variateur', { projet_id: 7 }),
        groupe(5, 'stand', { nouveau_projet: { nom: 'Salon', priorite: 2 } }, {
          jetons: [{ type: 'projet', source: '#Salon', debut: 6, fin: 12, libelle: 'Nouveau projet : Salon', valeur: { nouveau: true, nom: 'Salon' } }],
        }),
      ],
      projets_nouveaux: [{ nom: 'Villa Benjelloun', priorite: 2 }, { nom: 'Hôtel Atlas', priorite: 2 }, { nom: 'Salon', priorite: 2 }],
    }
    const PROJETS = [{ id: 7, nom: 'Pompage Berrechid', couleur: 'terre', statut: 'actif' }]

    it('chaque groupe est nommé AVANT « Créer » ; la puce d\'un projet nouveau se voit sur sa ligne', () => {
      monter(NOTES, { projets: PROJETS })
      const entetes = [...document.querySelectorAll('.apercu-projet .nom-projet')].map((e) => e.textContent)
      expect(entetes).toEqual(['Nouveau projet : Villa Benjelloun', 'Nouveau projet : Hôtel Atlas', 'Projet : Pompage Berrechid'])
      expect(screen.getByRole('group', { name: 'Hôtel Atlas' })).toHaveTextContent('2 tâches')
      const pompage = within(screen.getByRole('group', { name: 'Pompage Berrechid' }))
      expect(pompage.getByRole('textbox', { name: 'Titre : devis variateur' })).toBeInTheDocument()
      // la ligne qui nomme son propre projet reste dans le groupe où elle est écrite, avec sa puce
      expect(pompage.getByRole('textbox', { name: 'Titre : stand' })).toBeInTheDocument()
      expect(pompage.getByText('Nouveau projet : Salon').closest('.puce')).not.toBeNull()
      expect(screen.getByRole('button', { name: 'Priorité du projet Villa Benjelloun : moyenne' })).toBeInTheDocument()
      expect(screen.getByText('6 tâches · 4 projets')).toBeInTheDocument()
    })

    it('« En faire une tâche » sur un groupe : son titre devient une tâche, ses lignes n\'ont plus ce projet', async () => {
      const user = userEvent.setup()
      const { onCreer } = monter(NOTES, { projets: PROJETS })
      await user.click(screen.getByRole('button', { name: 'En faire une tâche : Hôtel Atlas' }))
      expect(screen.getByText('7 tâches · 3 projets')).toBeInTheDocument()
      await user.click(screen.getByRole('button', { name: 'Créer 7 tâches' }))
      const [lignes] = onCreer.mock.calls[0]
      expect(lignes.map((l) => l.titre)).toEqual([
        'envoyer le devis', 'appeler l\'architecte', 'Hôtel Atlas', 'relancer le directeur', 'visite technique', 'devis variateur', 'stand'])
      expect(lignes[2]).toMatchObject({ client_id: 'cid1:g2', collage: 0 })
      expect(lignes[2].nouveau_projet).toBeUndefined()
      expect(lignes[3].nouveau_projet).toBeUndefined()
      expect(lignes[0].nouveau_projet.nom).toBe('Villa Benjelloun')
      expect(lignes[5].projet_id).toBe(7)
      expect(lignes[6].nouveau_projet.nom).toBe('Salon')
    })
  })

  describe('R2-005 — un titre corrigé est relu ; chaque puce se retire', () => {
    const jour = { type: 'jour', source: 'mardi', debut: 9, fin: 14, libelle: 'mar. 24 nov.', valeur: '2026-11-24' }
    const relue = (titre, jetons, champs) => ({ data: { projets_communs: [], projets_nouveaux: [], lignes: [{ ...modele, index: 0, collage: 0, titre, jetons, alertes: [], champs }] } })

    it('à la sortie du champ, la ligne est relue : « … mardi » devient la puce « mar. 24 nov. », le projet du groupe reste', async () => {
      mocks.saisieRapide.mockResolvedValue(relue('Relancer', [jour], { priorite: 0, jour_prevu: '2026-11-24' }))
      const user = userEvent.setup()
      const { onCreer } = monter()
      const champ = screen.getByRole('textbox', { name: 'Titre : Réserver le stand' })
      await user.clear(champ)
      await user.type(champ, 'Relancer mardi')
      await user.tab()
      expect(mocks.saisieRapide).toHaveBeenCalledWith({ texte: 'Relancer mardi', ignorer: [], apercu: true }, { cle: null, erreurSousLeChamp: true })
      expect(await screen.findByText('mar. 24 nov.')).toBeInTheDocument()
      expect(screen.getByRole('textbox', { name: 'Titre : Relancer' })).toHaveValue('Relancer')
      await user.click(screen.getByRole('button', { name: 'Créer 6 tâches' }))
      expect(onCreer.mock.calls[0][0][0]).toMatchObject({
        titre: 'Relancer', jour_prevu: '2026-11-24', nouveau_projet: { nom: 'Salon Solaire Expo', priorite: 2 },
      })
    })

    it('le × d\'une puce relit la ligne SANS elle : le mot revient dans le titre, le jour part', async () => {
      const user = userEvent.setup()
      const { onCreer } = monter({ ...APERCU, lignes: [{ ...ligne(0, 0, 'Relancer'), jetons: [jour], champs: { ...ligne(0, 0, '').champs, jour_prevu: '2026-11-24' } }] })
      mocks.saisieRapide.mockResolvedValue(relue('Relancer mardi', [], { priorite: 0 }))
      await user.click(screen.getByRole('button', { name: 'Retirer mar. 24 nov.' }))
      expect(mocks.saisieRapide).toHaveBeenCalledWith(
        { texte: 'Relancer mardi', ignorer: [{ type: 'jour', source: 'mardi' }], apercu: true }, { cle: null, erreurSousLeChamp: true })
      expect(await screen.findByRole('textbox', { name: 'Titre : Relancer mardi' })).toBeInTheDocument()
      expect(screen.queryByText('mar. 24 nov.')).toBeNull()
      await user.click(screen.getByRole('button', { name: 'Créer 1 tâche' }))
      expect(onCreer.mock.calls[0][0][0].jour_prevu).toBeUndefined()
      expect(onCreer.mock.calls[0][0][0].nouveau_projet.nom).toBe('Salon Solaire Expo')
    })
  })

  it('aperçu sans ligne lisible : « Aucune ligne lisible. », rien à créer', async () => {
    const user = userEvent.setup()
    const { onCreer } = monter({ projets_communs: [], lignes: [], projets_nouveaux: [] })
    expect(screen.getByText('Aucune ligne lisible.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Créer 0 tâche' }))
    expect(onCreer).not.toHaveBeenCalled()
  })
})
