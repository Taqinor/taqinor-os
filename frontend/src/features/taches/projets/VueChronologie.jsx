import { useMemo } from 'react'
import { Diamond } from 'lucide-react'
import { elementsChronologie } from '../lib/projets'
import { ecartJours, jourNomme } from '../lib/textes'

/* ============================================================================
   TCH90 — La vue Chronologie d'un projet, et son burn-up « Avancement par semaine ».
   Maquette : docs/taches/maquettes/projet-chronologie.html. Forme lue : `projet_vue.json` — les étapes
   (`sections[].date_debut/date_fin/compteurs`), les tâches (`jalon`, `jour_prevu`, `echeance`), l'échéance du
   projet (`projet.echeance`), `burnup` et `burnup_legende`. AUCUN chiffre n'est écrit ici : chaque date, chaque
   compte et chaque point du burn-up est calculé de ce que le serveur sert, ou omis.
   Deux dessins d'UNE même donnée (CSS seul choisit) : iPhone, une frise verticale par date ; bureau, UNE piste
   (les étapes bout à bout, le jalon au-dessus, « aujourd'hui » et « échéance » en traits — pas un Gantt).
   Textes : reference/textes.md §2.6 (« Sans date », « {faites} sur {total} faites », « Échéance du projet »,
   « Jalon », burn-up : « reconstruit depuis les dates actuelles »).
   ========================================================================== */

function EtiquetteDate({ element, aujourdhui }) {
  if (element.type === 'auj') return `Aujourd'hui · ${jourNomme(aujourdhui, aujourdhui)}`
  if (element.type === 'etape') {
    if (!element.debut && !element.fin) return 'Sans date'
    if (element.debut && element.fin) return `${jourNomme(element.debut, aujourdhui)} → ${jourNomme(element.fin, aujourdhui)}`
    return jourNomme(element.debut ?? element.fin, aujourdhui)
  }
  return jourNomme(element.date, aujourdhui)
}

function FriseVerticale({ elements, aujourdhui }) {
  return (
    <div className="ep-frise" role="list" aria-label="Chronologie du projet jusqu'à l'échéance">
      {elements.map((e) => (
        <div key={e.id} className={`ep-f-item ${e.type}${e.faite ? ' faite' : ''}`} role="listitem">
          {e.type === 'jalon' ? <Diamond className="i ep-f-glyphe" aria-hidden="true" /> : null}
          <div className="ep-f-date"><EtiquetteDate element={e} aujourdhui={aujourdhui} /></div>
          {e.nom ? <div className="ep-f-titre">{e.nom}</div> : null}
          {e.detail ? <div className="ep-f-detail">{e.detail}</div> : null}
        </div>
      ))}
    </div>
  )
}

function FriseHorizontale({ elements, aujourdhui }) {
  const dates = elements.filter((e) => e.type !== 'auj').flatMap((e) => (e.type === 'etape' ? [e.debut, e.fin] : [e.date])).filter(Boolean)
  const toutes = [...dates, aujourdhui].sort()
  const debut = toutes[0]
  const fin = toutes[toutes.length - 1]
  const etendue = Math.max(1, ecartJours(fin, debut) ?? 1)
  const pct = (jour) => Math.min(100, Math.max(0, ((ecartJours(jour, debut) ?? 0) / etendue) * 100))
  const style = (gauche, largeur) => ({ left: `${gauche.toFixed(2)}%`, ...(largeur === undefined ? {} : { width: `${largeur.toFixed(2)}%` }) })
  const etapes = elements.filter((e) => e.type === 'etape' && (e.debut || e.fin))
  const jalons = elements.filter((e) => e.type === 'jalon')
  const echeance = elements.find((e) => e.type === 'fin')
  return (
    <div className="ep-frise-h" role="group" aria-label="Chronologie : étapes et jalons jusqu'à l'échéance">
      <div className="ep-fh-axe chiffres" aria-hidden="true">
        <span style={style(0)}>{jourNomme(debut, aujourdhui)}</span>
        <span style={style(100)}>{jourNomme(fin, aujourdhui)}</span>
      </div>
      <div className="ep-fh-zone">
        <div className="ep-fh-jalons">
          {jalons.map((j) => (
            <span key={j.id}>
              <Diamond className="i ep-fh-losange" style={style(pct(j.date))} aria-hidden="true" />
              <span className="ep-fh-etiquette" style={style(pct(j.date))}>{`${j.nom} · ${jourNomme(j.date, aujourdhui)}`}</span>
            </span>
          ))}
        </div>
        {etapes.map((e) => {
          const de = e.debut ?? e.fin
          const a = e.fin ?? e.debut
          return (
            <div key={e.id}>
              <div className="ep-fh-rang">
                <div className={`ep-fh-barre${e.faite ? ' faite' : ''}`} style={style(pct(de), Math.max(4, pct(a) - pct(de)))}>{e.nom}</div>
              </div>
              {e.detail ? <div className="ep-fh-sous-rang"><span className="ep-fh-sous chiffres" style={style(pct(de))}>{e.detail}</span></div> : null}
            </div>
          )
        })}
        <div className="ep-fh-trait auj" style={style(pct(aujourdhui))}><span>{`Aujourd'hui · ${jourNomme(aujourdhui, aujourdhui)}`}</span></div>
        {echeance ? (
          <div className="ep-fh-trait fin" style={style(pct(echeance.date))}><span>{`Échéance · ${jourNomme(echeance.date, aujourdhui)}`}</span></div>
        ) : null}
      </div>
    </div>
  )
}

export default function VueChronologie({ vue, aujourdhui }) {
  const { elements, sansDate } = useMemo(() => elementsChronologie(vue, aujourdhui), [vue, aujourdhui])
  return (
    <div className="ep-vue-chronologie">
      <FriseVerticale elements={elements} aujourdhui={aujourdhui} />
      <FriseHorizontale elements={elements} aujourdhui={aujourdhui} />
      {sansDate.length > 0 ? (
        <div className="ep-sans-dates"><b>Sans date :</b>{` ${sansDate.map((t) => t.titre).join(', ')}`}</div>
      ) : null}
    </div>
  )
}

/** « Avancement par semaine » : le burn-up SERVI (`burnup`, un point par semaine close) en courbes et en lignes. */
export function Burnup({ vue, aujourdhui }) {
  const points = vue.burnup ?? []
  if (points.length === 0) return <p className="ep-burnup-legende">Aucune semaine terminée.</p>
  const haut = Math.max(1, ...points.map((p) => p.total))
  const x = (i) => (points.length === 1 ? 150 : 10 + (i / (points.length - 1)) * 280)
  const y = (valeur) => 110 - (valeur / haut) * 100
  const courbe = (champ) => points.map((p, i) => `${x(i).toFixed(1)},${y(p[champ]).toFixed(1)}`).join(' ')
  return (
    <div className="ep-burnup">
      <svg viewBox="0 0 300 120" role="img" aria-label="Avancement par semaine : tâches faites et tâches du projet">
        <polyline className="courbe-total" points={courbe('total')} />
        <polyline className="courbe-faites" points={courbe('faites')} />
      </svg>
      <ul className="ep-burnup-liste" aria-label="Avancement par semaine">
        {points.map((p) => (
          <li key={p.semaine}><span>{jourNomme(p.semaine, aujourdhui)}</span><span className="chiffres">{`${p.faites} sur ${p.total}`}</span></li>
        ))}
      </ul>
      {vue.burnup_legende ? <p className="ep-burnup-legende">{vue.burnup_legende}</p> : null}
    </div>
  )
}
