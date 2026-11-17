import { useState } from 'react'
import { ChevronDown, Plus } from 'lucide-react'
import LigneTache from '../ui/LigneTache'

/* ============================================================================
   TCH89 — La vue Liste d'un projet : les étapes (sections) dans l'ordre du serveur, puis « Sans étape »,
   puis « Faites ({n}) ». Forme lue : `projet_vue.json` (`sections[].taches`, `sans_section`, `faites_nb`).
   Maquette : docs/taches/maquettes/projet-liste.html. Textes : reference/textes.md §2.6.
   Présentation seule : l'écran (`pages/taches/Projet.jsx`) écrit, met à jour sur place et annule ; ce composant
   rappelle `onTerminer`, `onOuvrir`, `onAction`, `onAjouter(sectionId)`.
   Raccord F2 — le compte d'une étape (« {faites} sur {total} ») et la liste des faites ne s'affichent que si le
   serveur les sert (`sections[].avancement`, `faites`) : jamais un chiffre recalculé ici ; sinon « Faites ({n}) »
   reste le seul compte, lu de `faites_nb`.
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

/** « {faites} sur {total} » d'une étape — seulement si le serveur le sert (`sections[].avancement`), jamais recompté ici. */
function compteEtape(avancement) {
  const { faites, total } = avancement ?? {}
  return Number.isInteger(faites) && Number.isInteger(total) && total > 0 ? `${faites} sur ${total}` : ''
}

function Etape({ nom, taches, sectionId, aujourdhui, poignees, avancement = null }) {
  const compte = compteEtape(avancement)
  return (
    <section className="section ep-etape" aria-label={nom}>
      <h2 className="section-titre"><span>{nom}</span>{compte ? <span className="compte chiffres">{compte}</span> : null}</h2>
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

/** « Faites (n) » : dépliable quand le serveur sert la liste (`faites`), sinon le seul compte servi (`faites_nb`). */
function Faites({ vue, aujourdhui, poignees }) {
  const [ouvert, setOuvert] = useState(false)
  if (!(vue.faites_nb > 0)) return null
  const liste = Array.isArray(vue.faites) ? vue.faites : null
  if (!liste) return <div className="ep-etape ep-faites"><span className="chiffres">{`Faites (${vue.faites_nb})`}</span></div>
  return (
    <section className="section ep-etape ep-faites" aria-label="Faites">
      <button type="button" className="replie" aria-expanded={ouvert} onClick={() => setOuvert((v) => !v)}>
        <span>Faites</span><span className="compte chiffres">{vue.faites_nb}</span>
        <ChevronDown className="i i-16" aria-hidden="true" />
      </button>
      {ouvert ? (
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

export default function VueListe({ vue, aujourdhui, onTerminer, onOuvrir, onAction, onAjouter, onAnnonce }) {
  const poignees = { onTerminer, onOuvrir, onAction, onAjouter, onAnnonce }
  const sections = vue.sections ?? []
  const sansSection = vue.sans_section ?? []
  return (
    <div className="ep-vue-liste">
      {sections.map((s) => (
        <Etape key={s.id} nom={s.nom} taches={s.taches ?? []} sectionId={s.id} aujourdhui={aujourdhui} poignees={poignees}
          avancement={s.avancement} />
      ))}
      {sansSection.length > 0 || sections.length === 0 ? (
        <Etape nom="Sans étape" taches={sansSection} sectionId={null} aujourdhui={aujourdhui} poignees={poignees} />
      ) : null}
      <Faites vue={vue} aujourdhui={aujourdhui} poignees={poignees} />
    </div>
  )
}
