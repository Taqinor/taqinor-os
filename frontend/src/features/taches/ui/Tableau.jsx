import { useMemo, useState } from 'react'
import {
  DndContext, KeyboardCode, KeyboardSensor, PointerSensor, useDraggable, useDroppable, useSensor, useSensors,
} from '@dnd-kit/core'
import { Check, GripVertical, Plus } from 'lucide-react'
import LigneTache from './LigneTache'
import { compteEtape } from '../lib/projets'
import { buildKanbanAnnouncements, kanbanScreenReaderInstructions } from '../../kanban/kanbanA11y'

/* ============================================================================
   TCH90 — La vue Tableau d'un projet : une colonne par étape, puis « Sans étape » (maquette
   projet-tableau.html ; textes.md §2.6). Forme lue : `projet_vue.json` (`sections[].taches`, `sans_section`,
   `sections[].compteurs`). Bureau : les colonnes côte à côte ; iPhone : un onglet par étape, UNE colonne à la fois.
   Déplacer une carte d'une étape à l'autre : à la souris (glisser) ou au CLAVIER — la poignée de la carte
   (« Déplacer « … » »), Espace la saisit, ←/→ choisissent la colonne voisine, Espace la dépose, Échap annule —
   avec les annonces françaises PARTAGÉES des kanbans (`features/kanban/kanbanA11y.js`). Le composant ne parle
   jamais au serveur : il appelle `onDeplacer(item, sectionId | null)` ; l'écran écrit, met à jour sur place, annule.
   ========================================================================== */

const COLONNE = 'etape-'
const CARTE = 'tache-'
const cleDe = (sectionId) => (sectionId == null ? 'sans' : String(sectionId))

/** Au clavier, ←/→ (et ↑/↓) sautent à la colonne voisine : la carte se pose en haut de celle-ci. */
function coordonneesClavier(event, { context: { active, droppableRects, droppableContainers, collisionRect } }) {
  const suivant = [KeyboardCode.Right, KeyboardCode.Down].includes(event.code)
  const precedent = [KeyboardCode.Left, KeyboardCode.Up].includes(event.code)
  if (!active || !collisionRect || (!suivant && !precedent)) return undefined
  event.preventDefault()
  const colonnes = droppableContainers.getEnabled()
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

function Carte({ item, aujourdhui, poignees }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({ id: `${CARTE}${item.id}` })
  return (
    <div ref={setNodeRef} className={`ep-carte${isDragging ? ' saisie' : ''}`}>
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
      {colonne.taches.map((t) => <Carte key={`${t.type}:${t.id}`} item={t} aujourdhui={aujourdhui} poignees={poignees} />)}
      <button type="button" className="ep-col-ajout" onClick={() => poignees.onAjouter(colonne.id)}>
        <Plus className="i i-16" aria-hidden="true" />Ajouter
      </button>
    </section>
  )
}

export default function Tableau({ vue, aujourdhui, onDeplacer, onTerminer, onOuvrir, onAction, onAjouter, onAnnonce }) {
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
  const annonces = useMemo(() => buildKanbanAnnouncements((id) => {
    const texte = String(id)
    if (texte.startsWith(CARTE)) return lieu.get(texte)?.item.titre ?? texte
    return colonnes.find((c) => `${COLONNE}${c.cle}` === texte)?.nom ?? texte
  }), [colonnes, lieu])

  const surFin = ({ active, over }) => {
    if (!over) return
    const source = lieu.get(String(active.id))
    const cle = String(over.id).slice(COLONNE.length)
    if (!source || source.cle === cle) return
    const cible = colonnes.find((c) => c.cle === cle)
    if (cible) onDeplacer?.(source.item, cible.id)
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
      <DndContext sensors={sensors} onDragEnd={surFin}
        accessibility={{ announcements: annonces, screenReaderInstructions: kanbanScreenReaderInstructions }}>
        <div className="ep-tableau">
          {colonnes.map((c) => (
            <Colonne key={c.cle} colonne={c} visible={c.cle === actif} aujourdhui={aujourdhui} poignees={poignees} />
          ))}
        </div>
      </DndContext>
    </div>
  )
}
