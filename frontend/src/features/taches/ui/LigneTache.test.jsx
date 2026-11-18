import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { exempleContrat } from '../../../test/fixtures/contractSamples'
import CaseRonde from './CaseRonde'
import Etoile from './Etoile'
import LigneTache from './LigneTache'

/* TCH44 — la ligne de tâche rend l'`exemple` d'item.json ; Tab → Actions → item ; un échec
   réseau remet la case en arrière ; la 4e étoile est refusée. Les 44 px se mesurent en TCH134. */

const AUJOURDHUI = '2026-11-17'
const item = () => structuredClone(exempleContrat('taches', 'item'))

function trouverActivite(noeud) {
  if (Array.isArray(noeud)) {
    for (const x of noeud) { const r = trouverActivite(x); if (r) return r }
  } else if (noeud && typeof noeud === 'object') {
    if (noeud.type === 'activite') return noeud
    for (const x of Object.values(noeud)) { const r = trouverActivite(x); if (r) return r }
  }
  return null
}

const monter = (props = {}) => render(
  <div role="list"><LigneTache item={item()} aujourdhui={AUJOURDHUI} {...props} /></div>,
)

describe('TCH44 — LigneTache rend l\'ITEM du contrat', () => {
  it('titre, projet, échéance, durée, heure et étoile viennent des données', () => {
    const { container } = monter()
    const ligne = container.querySelector('.ligne')
    expect(within(ligne).getByRole('button', { name: 'Devis Settat' })).toBeInTheDocument()
    expect(ligne.querySelector('.titre')).toHaveTextContent('Devis Settat')
    expect(ligne.querySelector('.meta')).toHaveTextContent('échéance jeu. 19')
    expect(ligne.querySelector('.meta')).toHaveTextContent('1 h')
    expect(ligne.querySelector('.meta [data-p="vert"] .projet-nom')).toHaveTextContent('Ventes')
    expect(ligne.querySelector('.heure')).toHaveTextContent('10:00')
    expect(screen.getByRole('img', { name: 'Essentielle' })).toBeInTheDocument()
    // une liste à plat : aucune bordure ni carte par tâche, une seule ligne d'élément de liste
    expect(screen.getAllByRole('listitem')).toHaveLength(1)
  })

  it('la case a pour nom « Marquer « titre » comme faite » et la ligne faite reste barrée', () => {
    const faite = { ...item(), statut: 'fait' }
    const { container } = render(<LigneTache item={faite} aujourdhui={AUJOURDHUI} />)
    expect(container.querySelector('.ligne')).toHaveClass('faite')
    expect(screen.getByRole('checkbox', { name: 'Marquer « Devis Settat » comme faite' })).toBeChecked()
  })

  it('priorité haute = drapeau (jamais une teinte), échéance du jour = rouge, dépassée = rouge', () => {
    const urgente = { ...item(), priorite: 3, essentielle: false, echeance: AUJOURDHUI }
    const { container } = render(<LigneTache item={urgente} aujourdhui={AUJOURDHUI} />)
    expect(screen.getByRole('img', { name: 'Priorité haute' })).toBeInTheDocument()
    expect(container.querySelector('.meta .alerte')).toHaveTextContent("échéance aujourd'hui")
  })

  it('passe visuelle n° 53 — fin de ligne « heure, ★ ou drapeau » : drapeau avant l\'heure, jamais à côté de ★', () => {
    const { container, unmount } = render(<LigneTache item={{ ...item(), priorite: 3, essentielle: false }} aujourdhui={AUJOURDHUI} />)
    const fin = [...container.querySelector('.ligne-fin').children]
    expect(fin[0]).toHaveClass('drapeau')
    expect(fin[1]).toHaveClass('heure')
    unmount()
    render(<LigneTache item={{ ...item(), priorite: 3, essentielle: true }} aujourdhui={AUJOURDHUI} />)
    expect(screen.getByRole('img', { name: 'Essentielle' })).toBeInTheDocument()
    expect(screen.queryByRole('img', { name: 'Priorité haute' })).toBeNull()
  })

  it('une activité de l\'ERP porte « Activité ERP » et son lien', () => {
    const activite = trouverActivite(exempleContrat('taches', 'aujourdhui'))
    expect(activite).not.toBeNull()
    const { container } = render(<LigneTache item={activite} aujourdhui={AUJOURDHUI} />)
    const meta = container.querySelector('.meta')
    expect(meta).toHaveTextContent('Activité ERP')
    expect(meta).toHaveTextContent(activite.lien.libelle)
    expect(screen.queryByRole('button', { name: /Essentielle/ })).toBeNull()
  })

  it('en vue Projet la méta montre le Quand ; la puce Garder d\'une ligne proposée appelle onGarder', async () => {
    const onGarder = vi.fn()
    render(<LigneTache item={item()} aujourdhui={AUJOURDHUI} contexte="projet" propose onGarder={onGarder} />)
    expect(document.querySelector('.meta .fort')).toHaveTextContent("aujourd'hui")
    await userEvent.setup().click(screen.getByRole('button', { name: 'Garder' }))
    expect(onGarder).toHaveBeenCalledWith(expect.objectContaining({ id: 20 }))
  })

  it('passe visuelle n° 16 — la puce « Garder » est le mot seul, sans « + » (maquettes : `<button class="garder">Garder`)', () => {
    render(<LigneTache item={item()} aujourdhui={AUJOURDHUI} propose onGarder={() => {}} />)
    const garder = screen.getByRole('button', { name: 'Garder' })
    expect(garder.querySelector('svg')).toBeNull()
    expect(garder).toHaveTextContent(/^Garder$/)
  })
})

describe('TCH44 — clavier : Tab → Actions → item (sans balayage ni glisser)', () => {
  it('Tab parcourt case, titre puis Actions ; Entrée ouvre le menu de l\'appui long', async () => {
    const onAction = vi.fn()
    const onReporter = vi.fn()
    const user = userEvent.setup()
    monter({ onAction, onReporter, reporterLibelle: 'lun. 23' })

    await user.tab()
    expect(screen.getByRole('checkbox', { name: /Marquer/ })).toHaveFocus()
    await user.tab()
    expect(screen.getByRole('button', { name: 'Devis Settat' })).toHaveFocus()
    await user.tab()
    const actions = screen.getByRole('button', { name: 'Actions pour « Devis Settat »' })
    expect(actions).toHaveFocus()

    await user.keyboard('{Enter}')
    const menu = await screen.findByRole('menu')
    const libelles = within(menu).getAllByRole('menuitem').map((el) => el.textContent)
    expect(libelles).toEqual([
      'Reporter à lun. 23', 'Choisir un jour', 'En réserve', 'Déplacer…', 'Plus essentielle', 'En attente de…', 'Priorité', 'Supprimer',
    ])
    await user.click(within(menu).getByRole('menuitem', { name: 'Choisir un jour' }))
    expect(onAction).toHaveBeenCalledWith('choisir_jour', expect.objectContaining({ id: 20 }))
  })

  it('« Reporter à lun. 23 » du menu vaut le balayage gauche complet', async () => {
    const onReporter = vi.fn()
    const onAnnonce = vi.fn()
    const user = userEvent.setup()
    monter({ onReporter, onAnnonce, reporterLibelle: 'lun. 23' })
    await user.click(screen.getByRole('button', { name: 'Actions pour « Devis Settat »' }))
    await user.click(await screen.findByRole('menuitem', { name: 'Reporter à lun. 23' }))
    expect(onReporter).toHaveBeenCalledTimes(1)
    expect(onAnnonce).toHaveBeenCalledWith('Reportée à lun. 23')
  })

  it('le clic-droit ouvre le même menu', async () => {
    monter()
    fireEvent.contextMenu(document.querySelector('.ligne'))
    expect(await screen.findByRole('menu')).toBeInTheDocument()
  })
})

describe('TCH44 — case ronde : optimiste, retour arrière si échec', () => {
  it('cocher annonce « Fait : titre » et garde la case cochée', async () => {
    const onTerminer = vi.fn().mockResolvedValue({})
    const onAnnonce = vi.fn()
    const user = userEvent.setup()
    monter({ onTerminer, onAnnonce })
    const case_ = screen.getByRole('checkbox', { name: /Marquer/ })
    await user.click(case_)
    expect(case_).toBeChecked()
    expect(onTerminer).toHaveBeenCalledWith(expect.objectContaining({ id: 20 }), true)
    await waitFor(() => expect(onAnnonce).toHaveBeenCalledWith('Fait : Devis Settat'))
  })

  it('échec réseau : la case revient, rien n\'est annoncé', async () => {
    const onTerminer = vi.fn().mockRejectedValue(new Error('Network Error'))
    const onAnnonce = vi.fn()
    const user = userEvent.setup()
    monter({ onTerminer, onAnnonce })
    const case_ = screen.getByRole('checkbox', { name: /Marquer/ })
    await user.click(case_)
    await waitFor(() => expect(onTerminer).toHaveBeenCalledTimes(1))
    await waitFor(() => expect(case_).not.toBeChecked())
    expect(onAnnonce).not.toHaveBeenCalled()
  })

  it('l\'optimiste se règle sur la prop dès que le parent change `coche`', async () => {
    const { rerender } = render(<CaseRonde coche={false} titre="T" onBasculer={() => Promise.resolve()} />)
    await userEvent.setup().click(screen.getByRole('checkbox'))
    expect(screen.getByRole('checkbox')).toBeChecked()
    rerender(<CaseRonde coche titre="T" onBasculer={() => Promise.resolve()} />)
    expect(screen.getByRole('checkbox')).toBeChecked()
    rerender(<CaseRonde coche={false} titre="T" onBasculer={() => Promise.resolve()} />)
    expect(screen.getByRole('checkbox')).not.toBeChecked()
  })

  it('sélection : la case se nomme « Sélectionner : titre » et la ligne est aria-selected', async () => {
    const onBasculer = vi.fn()
    const user = userEvent.setup()
    monter({ selection: { actif: true, selectionnee: false, onBasculer } })
    await user.click(screen.getByRole('checkbox', { name: 'Sélectionner : Devis Settat' }))
    expect(onBasculer).toHaveBeenCalledTimes(1)
    expect(screen.getByRole('listitem')).toHaveAttribute('aria-selected', 'false')
  })
})

describe('TCH44 — Étoile : 3 au plus', () => {
  it('la 4e est refusée : onRefus, jamais onBasculer', async () => {
    const onBasculer = vi.fn()
    const onRefus = vi.fn()
    render(<Etoile active={false} nbEssentielles={3} onBasculer={onBasculer} onRefus={onRefus} titre="T" />)
    await userEvent.setup().click(screen.getByRole('checkbox', { name: 'Essentielle : T' }))
    expect(onRefus).toHaveBeenCalledTimes(1)
    expect(onBasculer).not.toHaveBeenCalled()
  })

  it('la 3e passe ; retirer une étoile posée passe toujours', async () => {
    const onBasculer = vi.fn()
    const user = userEvent.setup()
    const { rerender } = render(<Etoile active={false} nbEssentielles={2} onBasculer={onBasculer} titre="T" />)
    await user.click(screen.getByRole('checkbox'))
    expect(onBasculer).toHaveBeenLastCalledWith(true)
    rerender(<Etoile active nbEssentielles={3} onBasculer={onBasculer} titre="T" />)
    await user.click(screen.getByRole('checkbox'))
    expect(onBasculer).toHaveBeenLastCalledWith(false)
  })
})

describe('TCH44 — balayage tactile', () => {
  const poser = (cible, type, x) => {
    const e = new Event(type, { bubbles: true })
    Object.assign(e, { clientX: x, clientY: 100, pointerType: 'touch', pointerId: 1 })
    fireEvent(cible, e)
  }

  it('un balayage gauche COMPLET reporte ; un balayage court révèle Reporter et Choisir un jour', () => {
    const onReporter = vi.fn()
    const { container } = monter({ onReporter, reporterLibelle: 'lun. 23' })
    const ligne = container.querySelector('.ligne')
    // court : révèle
    poser(ligne, 'pointerdown', 300)
    poser(ligne, 'pointermove', 220)
    poser(ligne, 'pointerup', 220)
    expect(onReporter).not.toHaveBeenCalled()
    expect(ligne).toHaveClass('glisse-gauche')
    expect(screen.getByRole('button', { name: 'Reporter à lun. 23' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Choisir un jour' })).toBeInTheDocument()
  })

  it('un balayage gauche complet déclenche Reporter et la ligne reste en place', () => {
    const onReporter = vi.fn()
    const { container } = monter({ onReporter, reporterLibelle: 'lun. 23' })
    const ligne = container.querySelector('.ligne')
    poser(ligne, 'pointerdown', 340)
    poser(ligne, 'pointermove', 100)
    poser(ligne, 'pointerup', 100)
    expect(onReporter).toHaveBeenCalledTimes(1)
    expect(ligne).not.toHaveClass('glisse-gauche')
  })
})

describe('Passe visuelle n° 46 — résultats de la Recherche (mot surligné, méta de statut)', () => {
  // le balisage d'une ligne SANS les props de la recherche, figé AVANT leur ajout (ids de Radix et tracés des icônes retirés)
  const balisage = (container) => container.innerHTML.replace(/ (id|aria-controls|d)="[^"]*"/g, '')

  it('une ligne sans ces props rend exactement comme avant (balisage figé)', () => {
    const { container } = monter()
    expect(balisage(container)).toMatchInlineSnapshot(`"<div role="list"><div class="ligne-cadre" role="listitem" data-ligne="tache:20"><div class="ligne"><button type="button" role="checkbox" aria-checked="false" aria-label="Marquer « Devis Settat » comme faite" class="case"><span class="rond"><svg viewBox="0 0 24 24" aria-hidden="true"><path></path></svg></span></button><div class="ligne-corps"><button type="button" class="ligne-corps-bouton"><span class="titre">Devis Settat</span></button><div class="meta"><span class="fort chiffres">échéance jeu. 19</span><span class="chiffres">1 h</span><span data-p="vert"><i class="point"></i><span class="projet-nom">Ventes</span></span></div></div><div class="ligne-fin"><span class="heure chiffres">10:00</span><svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-star i i-16 etoile" aria-label="Essentielle" role="img"><path></path></svg></div><button type="button" class="ligne-actions" aria-label="Actions pour « Devis Settat »" aria-haspopup="menu" aria-expanded="false" data-state="closed"><svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-ellipsis lucide-more-horizontal i" aria-hidden="true"><circle cx="12" cy="12" r="1"></circle><circle cx="19" cy="12" r="1"></circle><circle cx="5" cy="12" r="1"></circle></svg></button></div></div></div>"`)
  })

  it('le mot cherché est surligné dans le titre, sans tenir compte de la casse ni des accents', () => {
    const { container } = monter({ item: { ...item(), titre: 'Préparer le DEVIS accepté' }, surligne: 'devis' })
    const titre = container.querySelector('.titre')
    expect([...titre.querySelectorAll('b.es-trouve')].map((b) => b.textContent)).toEqual(['DEVIS'])
    expect(titre).toHaveTextContent('Préparer le DEVIS accepté')
    const { container: c2 } = monter({ item: { ...item(), titre: "Relancer l'Électricien et l'electricien" }, surligne: 'ELECTRICIEN' })
    expect([...c2.querySelectorAll('.titre b.es-trouve')].map((b) => b.textContent)).toEqual(['Électricien', 'electricien'])
  })

  it('chaque mot de la recherche est surligné ; aucun HTML du titre n\'est jamais interprété', () => {
    const titre = '<img src=x onerror="alert(1)"> devis <b>signé</b>'
    const { container } = monter({ item: { ...item(), titre }, surligne: 'devis signe' })
    const t = container.querySelector('.titre')
    expect(t.querySelector('img')).toBeNull()
    expect(t).toHaveTextContent(titre)
    expect([...t.querySelectorAll('b.es-trouve')].map((b) => b.textContent)).toEqual(['devis', 'signé'])
  })

  it('variante « recherche » : méta de statut lue des données (À trier, En réserve, jour) puis « Suggéré par l\'ERP »', () => {
    const sansRien = { ...item(), jour_prevu: null, quelque_jour: false, projet: null, echeance: null, heure_debut: null }
    const textes = (container) => [...container.querySelector('.meta').children].map((e) => e.textContent)
    const { container: aTrier } = monter({ item: { ...sansRien, source: 'suggestion' }, contexte: 'recherche' })
    expect(textes(aTrier)).toEqual(['À trier', "Suggéré par l'ERP"])
    const reserve = { ...sansRien, quelque_jour: true, projet: { id: 3, nom: 'Salon Solaire Expo', couleur: 'indigo', priorite: 2 } }
    const { container: enReserve } = monter({ item: reserve, contexte: 'recherche' })
    expect(textes(enReserve)).toEqual(['En réserve', 'Salon Solaire Expo'])
    // une tâche qui a un jour le dit (« aujourd'hui », « lun. 16 ») à la place du statut
    const { container: duJour } = monter({ item: { ...sansRien, statut: 'fait', jour_prevu: AUJOURDHUI }, contexte: 'recherche' })
    expect(textes(duJour)).toEqual(["aujourd'hui"])
    // une tâche faite n'est jamais « À trier »
    const { container: faite } = monter({ item: { ...sansRien, statut: 'fait', source: 'suggestion' }, contexte: 'recherche' })
    expect(textes(faite)).toEqual(["Suggéré par l'ERP"])
  })

  it('hors de la recherche, ni statut ni « Suggéré par l\'ERP » ne s\'ajoutent à la méta', () => {
    const sansRien = { ...item(), jour_prevu: null, quelque_jour: false, projet: null, source: 'suggestion' }
    const { container } = monter({ item: sansRien })
    expect(container.querySelector('.meta')).not.toHaveTextContent('À trier')
    expect(container.querySelector('.meta')).not.toHaveTextContent("Suggéré par l'ERP")
  })
})
