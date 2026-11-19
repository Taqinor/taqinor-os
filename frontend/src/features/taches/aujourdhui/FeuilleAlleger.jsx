import { useState } from 'react'
import CaseRonde from '../ui/CaseRonde'
import { heure } from '../lib/textes'

/* ============================================================================
   TCH79 — Feuille « Alléger ma journée » (textes.md §2.10). Elle liste les tâches de la
   journée qu'on PEUT retourner à leurs projets : Essentiel, Prévu, Ce soir — hors activités
   ERP, obligations et tâches à échéance aujourd'hui ou avant, qui restent de toute façon
   (regles.md §4.5). RIEN n'est coché d'avance : on coche ce qu'on GARDE ; le reste retourne à
   ses projets sans compter de report et Proposé revient demain (`journee/alleger/`).
   Le bouton dit « Garder ces k » — rien coché : « Tout renvoyer aux projets » (R2-026) ; hors ligne, il est
   grisé. Le parent poste, annonce
   « {n} retournées aux projets » et pose le toast Annuler.
   Maquettes : ecran-aujourdhui-15h-menu.html, ecran-aujourdhui-15h-bas.html.
   ========================================================================== */

// R2-026 — l'aide en UNE ligne (les tâches à échéance du jour n'y sont pas listées : elles ne se proposent pas)
export const AIDE_ALLEGER = 'Coche ce que tu gardes ; le reste retourne à ses projets, sans report.'

/** Les tâches qu'Alléger peut renvoyer : celles de la journée dont l'échéance n'est pas atteinte. */
// eslint-disable-next-line react-refresh/only-export-components -- règle pure partagée avec le menu ⋯ (D-ENF22)
export function candidatesAlleger(donnees) {
  const vues = new Set()
  return ['essentiel', 'journee', 'ce_soir']
    .flatMap((cle) => donnees[cle] ?? [])
    .filter((item) => item.type === 'tache' && item.statut !== 'fait' && !(item.echeance && item.echeance <= donnees.jour))
    .filter((item) => (vues.has(item.id) ? false : vues.add(item.id)))
}

export default function FeuilleAlleger({ donnees, enLigne, onGarder }) {
  const [gardees, setGardees] = useState(() => new Set())
  const lignes = candidatesAlleger(donnees)
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
        {/* R2-026 — rien coché : on renvoie TOUT (jamais un « Garder ces 0 » mort) */}
        <button
          type="button"
          className="bouton plein large"
          aria-disabled={!enLigne || undefined}
          onClick={() => { if (enLigne) onGarder([...gardees]) }}
        >
          {k === 0 ? 'Tout renvoyer aux projets' : k === 1 ? 'Garder celle-ci' : `Garder ces ${k}`}
        </button>
      </div>
    </div>
  )
}
