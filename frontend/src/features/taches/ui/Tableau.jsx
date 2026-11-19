import { useMemo, useState } from 'react'
import {
  DndContext, KeyboardCode, KeyboardSensor, PointerSensor, pointerWithin, rectIntersection, useDraggable, useDroppable,
  useSensor, useSensors,
} from '@dnd-kit/core'
import { Check, GripVertical, Plus } from 'lucide-react'
import LigneTache from './LigneTache'
import { compteEtape } from '../lib/projets'
import { buildKanbanAnnouncements } from '../../kanban/kanbanA11y'
import { coordonneesVerticales } from '../projets/ordre'

/* ============================================================================
   TCH90 — La vue Tableau d'un projet : une colonne par étape, puis « Sans étape » (maquette
   projet-tableau.html ; textes.md §2.6). Forme lue : `projet_vue.json` (`sections[].taches`, `sans_section`,
   `sections[].compteurs`). Bureau : les colonnes côte à côte ; iPhone : un onglet par étape, UNE colonne à la fois.
   Déplacer une carte d'une étape à l'autre : à la souris (glisser) ou au CLAVIER — la poignée de la carte
   (« Déplacer « … » »), Espace la saisit, ←/→ choisissent la colonne voisine, Espace la dépose, Échap annule —
   avec les annonces françaises PARTAGÉES des kanbans (`features/kanban/kanbanA11y.js`). Le composant ne parle
   jamais au serveur : il appelle `onDeplacer(item, sectionId | null)` ; l'écran écrit, met à jour sur place, annule.
   R2-063 — glisser une carte SUR une autre carte de la MÊME colonne la place à cette position (au clavier : ↑/↓ dans
   la colonne, ←/→ d'une colonne à l'autre) : `onReordonner(item, { vers })`, l'ordre qui décide de ce qui remonte
   dans Proposé. Lâchée sur une carte d'une AUTRE colonne, la carte change d'étape (en bas de la colonne), comme avant.
   ========================================================================== */

const COLONNE = 'etape-'
const CARTE = 'tache-'
const SUR = 'sur-tache-' // la même carte, côté « reçoit » (R2-063)
const cleDe = (sectionId) => (sectionId == null ? 'sans' : String(sectionId))

/** Au clavier, ←/→ sautent à la colonne voisine (la carte se pose en haut de celle-ci) ; ↑/↓ la montent ou la descendent
 *  dans sa colonne (R2-063, `coordonneesVerticales`). */
function coordonneesClavier(event, contexte) {
  const { context: { active, droppableRects, droppableContainers, collisionRect } } = contexte
  if ([KeyboardCode.Up, KeyboardCode.Down].includes(event.code)) return coordonneesVerticales(event, contexte)
  const suivant = event.code === KeyboardCode.Right
  const precedent = event.code === KeyboardCode.Left
  if (!active || !collisionRect || (!suivant && !precedent)) return undefined
  event.preventDefault()
  const colonnes = droppableContainers.getEnabled()
    .filter((c) => String(c.id).startsWith(COLONNE))
    .map((c) => ({ id: c.id, rect: droppableRects.get(c.id) }))
    .filter((c) => c.rect)
    .sort((a, b) => a.rect.left - b.rect.left)
  if (colonnes.length === 0) return undefined
  const milieu = collisionRect.left + collisionRect.width / 2
  let ici = colonnes.findIndex((c) => milieu >= c.rect.left && milieu <= c.rect.left + c.rect.width)
  if (ici < 0) ici = 0
  const cible = colonnes[Math.max(0, Math.min(colonnes.length - 1, ici + (suivant ? 1 : -1)))]
  return { x: cible.rect.left + 8, y: cible.rect.top + 8 }
}

/** Où tombe le glissé : une CARTE sous le pointeur (ou recoupée) l'emporte sur la colonne qui la contient. */
function detecter(args) {
  const pointeur = pointerWithin(args)
  const base = pointeur.length > 0 ? pointeur : rectIntersection(args)
  const cartes = base.filter((c) => String(c.id).startsWith(SUR))
  return cartes.length > 0 ? cartes : base
}

function Carte({ item, cle, aujourdhui, poignees }) {
  const { attributes, listeners, setNodeRef: refGlisse, isDragging } = useDraggable({ id: `${CARTE}${item.id}`, data: { etape: cle } })
  const { setNodeRef: refRecoit } = useDroppable({ id: `${SUR}${item.id}`, data: { etape: cle } })
  return (
    <div ref={(noeud) => { refGlisse(noeud); refRecoit(noeud) }} className={`ep-carte${isDragging ? ' saisie' : ''}`}>
      <div className="liste" role="list">
        <LigneTache item={item} contexte="projet" aujourdhui={aujourdhui} onTerminer={poignees.onTerminer}
          onOuvrir={poignees.onOuvrir} onAction={poignees.onAction} onAnnonce={poignees.onAnnonce} />
      </div>
      <button type="button" className="ep-poignee" aria-label={`Déplacer « ${item.titre} »`} {...attributes} {...listeners}>
        <GripVertical className="i i-16" aria-hidden="true" />
      </button>
    </div>
  )
}

function Colonne({ colonne, visible, aujourdhui, poignees }) {
  const { setNodeRef, isOver } = useDroppable({ id: `${COLONNE}${colonne.cle}` })
  return (
    <section ref={setNodeRef} aria-label={colonne.nom}
      className={`ep-col${visible ? '' : ' bureau-seul'}${isOver ? ' sur' : ''}`}>
      <div className="ep-col-tete"><b>{colonne.nom}</b>{colonne.compte ? <span className="chiffres">{colonne.compte}</span> : null}</div>
      {colonne.taches.map((t) => <Carte key={`${t.type}:${t.id}`} item={t} cle={colonne.cle} aujourdhui={aujourdhui} poignees={poignees} />)}
      <button type="button" className="ep-col-ajout" onClick={() => poignees.onAjouter(colonne.id)}>
        <Plus className="i i-16" aria-hidden="true" />Ajouter
      </button>
    </section>
  )
}

const INSTRUCTIONS = {
  draggable: 'Pour déplacer une carte au clavier : Espace ou Entrée la saisit, ↑ et ↓ la montent ou la descendent dans sa colonne, '
    + '← et → la passent à la colonne voisine, Espace ou Entrée la dépose, Échap annule.',
}

export default function Tableau({ vue, aujourdhui, onDeplacer, onReordonner, onTerminer, onOuvrir, onAction, onAjouter, onAnnonce }) {
  const colonnes = useMemo(() => {
    const liste = (vue.sections ?? []).map((s) => ({
      cle: cleDe(s.id), id: s.id, nom: s.nom, taches: s.taches ?? [], compteurs: s.compteurs,
    }))
    const sans = vue.sans_section ?? []
    if (sans.length > 0 || liste.length === 0) {
      liste.push({ cle: 'sans', id: null, nom: 'Sans étape', taches: sans, compteurs: vue.sans_section_compteurs })
    }
    return liste.map((c) => ({ ...c, compte: compteEtape(c.compteurs) }))
  }, [vue])
  const [onglet, setOnglet] = useState(null)
  const actif = colonnes.some((c) => c.cle === onglet) ? onglet : colonnes[0]?.cle

  const lieu = useMemo(() => {
    const table = new Map()
    colonnes.forEach((c) => c.taches.forEach((t) => table.set(`${CARTE}${t.id}`, { cle: c.cle, item: t })))
    return table
  }, [colonnes])

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: coordonneesClavier }),
  )
  const annonces = useMemo(() => {
    const nom = (id) => {
      const texte = String(id)
      if (texte.startsWith(SUR)) return lieu.get(`${CARTE}${texte.slice(SUR.length)}`)?.item.titre ?? texte
      if (texte.startsWith(CARTE)) return lieu.get(texte)?.item.titre ?? texte
      return colonnes.find((c) => `${COLONNE}${c.cle}` === texte)?.nom ?? texte
    }
    const base = buildKanbanAnnouncements(nom)
    const surCarte = (over) => Boolean(over) && String(over.id).startsWith(SUR)
    const soiMeme = (e) => String(e.over.id).slice(SUR.length) === String(e.active.id).slice(CARTE.length)
    return {
      ...base,
      onDragOver: (e) => {
        if (!surCarte(e.over)) return base.onDragOver(e)
        return soiMeme(e) ? undefined : `Carte ${nom(e.active.id)} sur ${nom(e.over.id)}.`
      },
      onDragEnd: (e) => {
        if (!surCarte(e.over)) return base.onDragEnd(e)
        return soiMeme(e) ? `Carte ${nom(e.active.id)} reposée à sa place.` : `Carte ${nom(e.active.id)} déposée à la place de ${nom(e.over.id)}.`
      },
    }
  }, [colonnes, lieu])

  const surFin = ({ active, over }) => {
    if (!over) return
    const source = lieu.get(String(active.id))
    if (!source) return
    const cible = String(over.id)
    if (cible.startsWith(SUR)) {
      const visee = lieu.get(`${CARTE}${cible.slice(SUR.length)}`)
      if (!visee) return
      if (visee.cle === source.cle) {
        const colonne = colonnes.find((c) => c.cle === source.cle)
        const vers = colonne ? colonne.taches.findIndex((t) => t.id === visee.item.id) : -1
        if (vers >= 0 && visee.item.id !== source.item.id) onReordonner?.(source.item, { vers })
        return
      }
      const autre = colonnes.find((c) => c.cle === visee.cle)
      if (autre) onDeplacer?.(source.item, autre.id)
      return
    }
    const cle = cible.slice(COLONNE.length)
    if (source.cle === cle) return
    const colonne = colonnes.find((c) => c.cle === cle)
    if (colonne) onDeplacer?.(source.item, colonne.id)
  }

  const poignees = { onTerminer, onOuvrir, onAction, onAjouter, onAnnonce }
  const choisie = colonnes.find((c) => c.cle === actif)
  return (
    <div className="ep-vue-tableau">
      {colonnes.length > 1 ? (
        <div className="ep-onglets-etapes" role="tablist" aria-label="Étapes">
          {colonnes.map((c) => (
            <button key={c.cle} type="button" role="tab" aria-selected={c.cle === actif} onClick={() => setOnglet(c.cle)}>
              {c.nom}
              {c.compteurs && c.compteurs.ouvertes === 0 && c.compteurs.faites > 0
                ? <Check className="i i-14" aria-hidden="true" /> : null}
            </button>
          ))}
          {choisie?.compte ? <span className="ep-onglets-compte chiffres">{choisie.compte}</span> : null}
        </div>
      ) : null}
      <DndContext sensors={sensors} collisionDetection={detecter} onDragEnd={surFin}
        accessibility={{ announcements: annonces, screenReaderInstructions: INSTRUCTIONS }}>
        <div className="ep-tableau">
          {colonnes.map((c) => (
            <Colonne key={c.cle} colonne={c} visible={c.cle === actif} aujourdhui={aujourdhui} poignees={poignees} />
          ))}
        </div>
      </DndContext>
    </div>
  )
}
