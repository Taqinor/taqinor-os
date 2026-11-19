import { useState } from 'react'
import { DndContext, KeyboardSensor, PointerSensor, useDraggable, useDroppable, useSensor, useSensors } from '@dnd-kit/core'
import { ChevronDown, ChevronUp, GripVertical, Plus } from 'lucide-react'
import LigneTache from '../ui/LigneTache'
import { compteEtape } from '../lib/projets'
import { cleEtape, coordonneesVerticales, detecterDansEtape } from './ordre'

/* ============================================================================
   TCH89 — La vue Liste d'un projet : les étapes (sections) dans l'ordre du serveur, puis « Sans étape »,
   puis « Faites ({n}) ». Forme lue : `projet_vue.json` (`sections[].taches`, `sans_section`, `faites_nb`).
   Maquette : docs/taches/maquettes/projet-liste.html. Textes : reference/textes.md §2.6.
   Présentation seule : l'écran (`pages/taches/Projet.jsx`) écrit, met à jour sur place et annule ; ce composant
   rappelle `onTerminer`, `onOuvrir`, `onAction`, `onAjouter(sectionId)`.
   Raccord F2 — le compte d'une étape (« {faites} sur {total} ») et la liste des faites ne s'affichent que si le
   serveur les sert (`sections[].compteurs`, `sans_section_compteurs`) ; la liste des faites est lue à la demande. Sinon « Faites ({n}) »
   reste le seul compte, lu de `faites_nb`.
   R2-063 — l'ORDRE des tâches d'une étape (c'est lui qui décide ce qui remonte dans Proposé) se change : une poignée
   à glisser (souris : au survol ; doigt et clavier : sous « Réorganiser » du ⋯), « Monter » / « Descendre » (▲ ▼) sous
   « Réorganiser », Alt+↑/↓ sur une ligne (branché par l'écran). Le composant ne fait que rappeler
   `onReordonner(tache, { sens } | { vers })` : l'écran écrit (`reordonnerTache`), met à jour sur place et annule.
   ========================================================================== */

/** Raccord F2 — « Ajouter une tâche » d'une étape ouvre LA feuille de saisie (analyse, hors ligne, brouillon),
 * avec le projet et l'étape en contexte : `onAjouter(sectionId)`. */
function AjouterTache({ sectionId, onAjouter }) {
  return (
    <button type="button" className="ep-ajouter" onClick={() => onAjouter(sectionId)}>
      <Plus className="i i-16" aria-hidden="true" />Ajouter une tâche
    </button>
  )
}

/** Une tâche d'une étape : glissable par sa poignée, recevant les autres tâches de la même étape ; ▲▼ sous « Réorganiser ». */
function Rang({ item, etape, rang, total, aujourdhui, poignees, reorganiser }) {
  const id = `rang-${item.id}`
  const data = { etape, titre: item.titre }
  const { attributes, listeners, setNodeRef: refGlisse, isDragging } = useDraggable({ id, data })
  const { setNodeRef: refRecoit } = useDroppable({ id, data })
  const ligne = (
    <LigneTache
      item={item}
      contexte="projet"
      aujourdhui={aujourdhui}
      onTerminer={poignees.onTerminer}
      onOuvrir={poignees.onOuvrir}
      onAction={poignees.onAction}
      onAnnonce={poignees.onAnnonce}
    />
  )
  if (total < 2 || item.type !== 'tache') return ligne
  return (
    <div ref={(noeud) => { refGlisse(noeud); refRecoit(noeud) }} role="presentation" className={`ep-rang${reorganiser ? ' reorg' : ''}${isDragging ? ' saisi' : ''}`}>
      <button type="button" className="ep-poignee-ordre" aria-label={`Déplacer « ${item.titre} »`} {...attributes} {...listeners}>
        <GripVertical className="i i-16" aria-hidden="true" />
      </button>
      <div className="ep-rang-ligne">{ligne}</div>
      {reorganiser ? (
        <div className="reorg-controles">
          <button type="button" className="bouton-icone" aria-label={`Monter « ${item.titre} »`} disabled={rang === 0}
            onClick={() => poignees.onReordonner?.(item, { sens: -1 })}>
            <ChevronUp className="i i-16" aria-hidden="true" />
          </button>
          <button type="button" className="bouton-icone" aria-label={`Descendre « ${item.titre} »`} disabled={rang === total - 1}
            onClick={() => poignees.onReordonner?.(item, { sens: 1 })}>
            <ChevronDown className="i i-16" aria-hidden="true" />
          </button>
        </div>
      ) : null}
    </div>
  )
}

function Etape({ nom, taches, sectionId, aujourdhui, poignees, reorganiser, compteurs = null }) {
  const compte = compteEtape(compteurs)
  const etape = cleEtape(sectionId)
  return (
    <section className="section ep-etape" aria-label={nom}>
      <h2 className="section-titre"><span>{nom}</span>{compte ? <span className="compte chiffres">{compte}</span> : null}</h2>
      {taches.length > 0 ? (
        <div className="liste" role="list">
          {taches.map((t, i) => (
            <Rang key={`${t.type}:${t.id}`} item={t} etape={etape} rang={i} total={taches.length} aujourdhui={aujourdhui}
              poignees={poignees} reorganiser={reorganiser} />
          ))}
        </div>
      ) : null}
      <AjouterTache sectionId={sectionId} onAjouter={poignees.onAjouter} />
    </section>
  )
}

/**
 * « Faites (n) » : le compte vient de `faites_nb` ; déplié, la liste est lue à la demande (`chargerFaites`, toutes
 * les pages de `GET taches/?projet=&statut=fait&tri=fait_le`). Un échec garde le compte et le dit, avec Réessayer.
 */
function Faites({ vue, aujourdhui, poignees, chargerFaites }) {
  const [ouvert, setOuvert] = useState(false)
  const [liste, setListe] = useState(null)
  const [echec, setEchec] = useState(false)
  if (!(vue.faites_nb > 0)) return null
  if (!chargerFaites) return <div className="ep-etape ep-faites"><span className="chiffres">{`Faites (${vue.faites_nb})`}</span></div>
  const lire = () => {
    setEchec(false)
    chargerFaites().then(setListe).catch(() => setEchec(true))
  }
  const basculer = () => {
    if (!ouvert && liste === null) lire()
    setOuvert((v) => !v)
  }
  return (
    <section className="section ep-etape ep-faites" aria-label="Faites">
      <button type="button" className="replie" aria-expanded={ouvert} onClick={basculer}>
        <span>Faites</span><span className="compte chiffres">{vue.faites_nb}</span>
        <ChevronDown className="i i-16" aria-hidden="true" />
      </button>
      {ouvert && echec ? (
        <div className="pas-a-jour" role="status">
          <span>Pas à jour</span>
          <button type="button" className="bouton lien" onClick={lire}>Réessayer</button>
        </div>
      ) : null}
      {ouvert && !echec && liste === null ? <div className="squelette" role="status" aria-label="Chargement" /> : null}
      {ouvert && liste ? (
        <div className="liste" role="list">
          {liste.map((t) => (
            <LigneTache key={`${t.type}:${t.id}`} item={t} contexte="projet" aujourdhui={aujourdhui}
              onTerminer={poignees.onTerminer} onOuvrir={poignees.onOuvrir} onAction={poignees.onAction} onAnnonce={poignees.onAnnonce} />
          ))}
        </div>
      ) : null}
    </section>
  )
}

const ANNONCES = {
  onDragStart: ({ active }) => `Tâche saisie : ${active.data.current?.titre ?? ''}`.trim(),
  onDragOver: () => undefined,
  onDragEnd: () => undefined, // la position est annoncée par l'écran une fois écrite (`annoncer`)
  onDragCancel: () => 'Déplacement annulé.',
}
const INSTRUCTIONS = {
  draggable: 'Pour réordonner une tâche au clavier : Espace ou Entrée la saisit, ↑ et ↓ la déplacent, Espace ou Entrée la dépose, Échap annule.',
}

export default function VueListe({
  vue, aujourdhui, onTerminer, onOuvrir, onAction, onAjouter, onAnnonce, onReordonner = null, reorganiser = false,
  racine = null, chargerFaites = null,
}) {
  const poignees = { onTerminer, onOuvrir, onAction, onAjouter, onAnnonce, onReordonner }
  const sections = vue.sections ?? []
  const sansSection = vue.sans_section ?? []
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: coordonneesVerticales }),
  )
  // glisser une tâche sur une autre de la même étape = la placer à SA position (la liste entière suit, comme `arrayMove`)
  const surFin = ({ active, over }) => {
    if (!over || active.id === over.id) return
    const etape = active.data.current?.etape
    const liste = etape === 'sans' ? sansSection : (sections.find((s) => cleEtape(s.id) === etape)?.taches ?? [])
    const item = liste.find((t) => `rang-${t.id}` === active.id)
    const vers = liste.findIndex((t) => `rang-${t.id}` === over.id)
    if (item && vers >= 0) onReordonner?.(item, { vers })
  }
  return (
    <div className="ep-vue-liste">
      <DndContext sensors={sensors} collisionDetection={detecterDansEtape} onDragEnd={surFin}
        accessibility={{ announcements: ANNONCES, screenReaderInstructions: INSTRUCTIONS }}>
        <div ref={racine}>
          {sections.map((s) => (
            <Etape key={s.id} nom={s.nom} taches={s.taches ?? []} sectionId={s.id} aujourdhui={aujourdhui} poignees={poignees}
              reorganiser={reorganiser} compteurs={s.compteurs} />
          ))}
          {sansSection.length > 0 || sections.length === 0 ? (
            <Etape nom="Sans étape" taches={sansSection} sectionId={null} aujourdhui={aujourdhui} poignees={poignees}
              reorganiser={reorganiser} compteurs={vue.sans_section_compteurs} />
          ) : null}
        </div>
      </DndContext>
      <Faites vue={vue} aujourdhui={aujourdhui} poignees={poignees} chargerFaites={chargerFaites} />
    </div>
  )
}
