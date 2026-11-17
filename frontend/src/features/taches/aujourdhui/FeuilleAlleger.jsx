import { useState } from 'react'
import CaseRonde from '../ui/CaseRonde'
import { heure } from '../lib/textes'

/* ============================================================================
   TCH79 — Feuille « Alléger ma journée » (textes.md §2.10). Elle liste les tâches de la
   journée qu'on PEUT retourner à leurs projets : Essentiel, Prévu, Ce soir — hors activités
   ERP, obligations et tâches à échéance aujourd'hui ou avant, qui restent de toute façon
   (regles.md §4.5). RIEN n'est coché d'avance : on coche ce qu'on GARDE ; le reste retourne à
   ses projets sans compter de report et Proposé revient demain (`journee/alleger/`).
   Le bouton dit « Garder ces k » ; hors ligne, il est grisé. Le parent poste, annonce
   « {n} retournées aux projets » et pose le toast Annuler.
   Maquettes : ecran-aujourdhui-15h-menu.html, ecran-aujourdhui-15h-bas.html.
   ========================================================================== */

export const AIDE_ALLEGER = "Coche ce que tu gardes aujourd'hui. Le reste retourne à ses projets, sans compter de report ; Proposé revient demain. Les tâches à échéance aujourd'hui restent."

/** Les tâches qu'Alléger peut renvoyer : celles de la journée dont l'échéance n'est pas atteinte. */
function candidates(donnees) {
  const vues = new Set()
  return ['essentiel', 'journee', 'ce_soir']
    .flatMap((cle) => donnees[cle] ?? [])
    .filter((item) => item.type === 'tache' && item.statut !== 'fait' && !(item.echeance && item.echeance <= donnees.jour))
    .filter((item) => (vues.has(item.id) ? false : vues.add(item.id)))
}

export default function FeuilleAlleger({ donnees, enLigne, onGarder }) {
  const [gardees, setGardees] = useState(() => new Set())
  const lignes = candidates(donnees)
  const k = gardees.size
  const basculer = (id) => setGardees((avant) => {
    const suite = new Set(avant)
    if (suite.has(id)) suite.delete(id)
    else suite.add(id)
    return suite
  })
  return (
    <div className="alleger">
      <p className="carte-source">{AIDE_ALLEGER}</p>
      <div className="liste" role="list">
        {lignes.map((item) => (
          <div key={item.id} className="ligne-courte" role="listitem">
            <CaseRonde
              selection
              coche={gardees.has(item.id)}
              titre={item.titre}
              desactivee={!enLigne}
              onBasculer={() => basculer(item.id)}
            />
            <span className="texte">{item.titre}</span>
            {item.heure_debut ? <span className="chiffres heure">{heure(item.heure_debut)}</span> : <span />}
          </div>
        ))}
      </div>
      <div className="feuille-pied">
        <button
          type="button"
          className="bouton plein large"
          aria-disabled={!enLigne || k === 0 || undefined}
          onClick={() => { if (enLigne && k > 0) onGarder([...gardees]) }}
        >
          {k === 1 ? 'Garder celle-ci' : `Garder ces ${k}`}
        </button>
      </div>
    </div>
  )
}
