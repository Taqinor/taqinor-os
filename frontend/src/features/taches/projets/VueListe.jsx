import { useState } from 'react'
import { ChevronDown, Plus } from 'lucide-react'
import LigneTache from '../ui/LigneTache'
import { compteEtape } from '../lib/projets'

/* ============================================================================
   TCH89 — La vue Liste d'un projet : les étapes (sections) dans l'ordre du serveur, puis « Sans étape »,
   puis « Faites ({n}) ». Forme lue : `projet_vue.json` (`sections[].taches`, `sans_section`, `faites_nb`).
   Maquette : docs/taches/maquettes/projet-liste.html. Textes : reference/textes.md §2.6.
   Présentation seule : l'écran (`pages/taches/Projet.jsx`) écrit, met à jour sur place et annule ; ce composant
   rappelle `onTerminer`, `onOuvrir`, `onAction`, `onAjouter(sectionId)`.
   Raccord F2 — le compte d'une étape (« {faites} sur {total} ») et la liste des faites ne s'affichent que si le
   serveur les sert (`sections[].compteurs`, `sans_section_compteurs`) ; la liste des faites est lue à la demande. Sinon « Faites ({n}) »
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

function Etape({ nom, taches, sectionId, aujourdhui, poignees, compteurs = null }) {
  const compte = compteEtape(compteurs)
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
export default function VueListe({ vue, aujourdhui, onTerminer, onOuvrir, onAction, onAjouter, onAnnonce, chargerFaites = null }) {
  const poignees = { onTerminer, onOuvrir, onAction, onAjouter, onAnnonce }
  const sections = vue.sections ?? []
  const sansSection = vue.sans_section ?? []
  return (
    <div className="ep-vue-liste">
      {sections.map((s) => (
        <Etape key={s.id} nom={s.nom} taches={s.taches ?? []} sectionId={s.id} aujourdhui={aujourdhui} poignees={poignees}
          compteurs={s.compteurs} />
      ))}
      {sansSection.length > 0 || sections.length === 0 ? (
        <Etape nom="Sans étape" taches={sansSection} sectionId={null} aujourdhui={aujourdhui} poignees={poignees}
          compteurs={vue.sans_section_compteurs} />
      ) : null}
      <Faites vue={vue} aujourdhui={aujourdhui} poignees={poignees} chargerFaites={chargerFaites} />
    </div>
  )
}
