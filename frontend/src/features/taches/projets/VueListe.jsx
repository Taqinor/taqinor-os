import { Plus } from 'lucide-react'
import LigneTache from '../ui/LigneTache'

/* ============================================================================
   TCH89 — La vue Liste d'un projet : les étapes (sections) dans l'ordre du serveur, puis « Sans étape »,
   puis « Faites ({n}) ». Forme lue : `projet_vue.json` (`sections[].taches`, `sans_section`, `faites_nb`).
   Maquette : docs/taches/maquettes/projet-liste.html. Textes : reference/textes.md §2.6.
   Présentation seule : l'écran (`pages/taches/Projet.jsx`) écrit, met à jour sur place et annule ; ce composant
   rappelle `onTerminer`, `onOuvrir`, `onAction`, `onAjouter(sectionId)`.
   Le compte d'une étape n'est PAS servi (le contrat ne donne que les tâches ouvertes) : jamais un chiffre
   recalculé ici ; seul « Faites ({n}) » vient de `faites_nb`.
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

function Etape({ nom, taches, sectionId, aujourdhui, poignees }) {
  return (
    <section className="section ep-etape" aria-label={nom}>
      <h2 className="section-titre"><span>{nom}</span></h2>
      {taches.length > 0 ? (
        <div className="liste" role="list">
          {taches.map((t) => (
            <LigneTache
              key={`${t.type}:${t.id}`}
              item={t}
              contexte="projet"
              aujourdhui={aujourdhui}
              onTerminer={poignees.onTerminer}
              onOuvrir={poignees.onOuvrir}
              onAction={poignees.onAction}
              onAnnonce={poignees.onAnnonce}
            />
          ))}
        </div>
      ) : null}
      <AjouterTache sectionId={sectionId} onAjouter={poignees.onAjouter} />
    </section>
  )
}

export default function VueListe({ vue, aujourdhui, onTerminer, onOuvrir, onAction, onAjouter, onAnnonce }) {
  const poignees = { onTerminer, onOuvrir, onAction, onAjouter, onAnnonce }
  const sections = vue.sections ?? []
  const sansSection = vue.sans_section ?? []
  return (
    <div className="ep-vue-liste">
      {sections.map((s) => (
        <Etape key={s.id} nom={s.nom} taches={s.taches ?? []} sectionId={s.id} aujourdhui={aujourdhui} poignees={poignees} />
      ))}
      {sansSection.length > 0 || sections.length === 0 ? (
        <Etape nom="Sans étape" taches={sansSection} sectionId={null} aujourdhui={aujourdhui} poignees={poignees} />
      ) : null}
      {vue.faites_nb > 0 ? (
        <div className="ep-etape ep-faites"><span className="chiffres">{`Faites (${vue.faites_nb})`}</span></div>
      ) : null}
    </div>
  )
}
