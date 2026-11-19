import { jourLong } from '../lib/textes'

/* ============================================================================
   TCH104 — vue Mois de l'Agenda : la grille lun.→dim. des semaines du mois (`du` → `au`,
   42 jours au plus), un point par tâche du jour (trois au plus, puis « +{n} »), un point gris
   par élément de l'ERP ou rendez-vous externe, « Férié », jours non travaillés grisés.
   Toucher un jour le choisit (la page montre sa liste, puis « Jour » au besoin). Au bureau la case dit les TITRES (R2-109).
   Maquette : docs/taches/maquettes/agenda-mois.html. Lit `agenda.json` (`jours[]`) tel quel.
   ========================================================================== */

const ENTETES = ['lun.', 'mar.', 'mer.', 'jeu.', 'ven.', 'sam.', 'dim.']
const POINTS_MAX = 3

function datesEntre(du, au) {
  const [a, m, j] = du.split('-').map(Number)
  const [b, n, k] = au.split('-').map(Number)
  const fin = Date.UTC(b, n - 1, k)
  const dates = []
  for (let t = Date.UTC(a, m - 1, j); t <= fin; t += 86400000) dates.push(new Date(t).toISOString().split('T')[0])
  return dates
}

const jourSemaine = (iso) => (new Date(`${iso}T00:00:00Z`).getUTCDay() + 6) % 7 // lundi = 0

/** R2-109 — les jours de la semaine (0 = lundi) qui sont non travaillés PARTOUT où la lecture les sert : un jour que la
 *  lecture ne sert pas reprend ce que ses pareils servis disent (le week-end est teinté sur toutes les semaines). */
function joursDeRepos(jours) {
  const vus = new Map()
  for (const j of jours ?? []) {
    const rang = jourSemaine(j.jour)
    vus.set(rang, (vus.get(rang) ?? true) && !j.ouvre)
  }
  return new Set([...vus].filter(([, repos]) => repos).map(([rang]) => rang))
}

const tachesDuJour = (jour) => [...(jour?.blocs ?? []), ...(jour?.sans_heure ?? []), ...(jour?.echeances ?? [])]
const erpDuJour = (jour) => [...(jour?.toute_la_journee ?? []), ...(jour?.externes ?? [])]

function Points({ jour }) {
  if (jour?.ferie) return <span className="pts ferie">Férié</span>
  const taches = tachesDuJour(jour)
  const erp = erpDuJour(jour)
  const montrees = taches.slice(0, POINTS_MAX)
  const reste = taches.length - montrees.length
  return (
    <span className="pts" aria-hidden="true">
      {montrees.map((t) => <i key={`t${t.id}`} data-p={t.projet?.couleur || undefined} />)}
      {erp.length ? <i className="erp" /> : null}
      {reste > 0 ? <em>+{reste}</em> : null}
    </span>
  )
}

/** R2-109 — au bureau (≥ 1024 px, agenda.css) la case dit les TITRES (3 au plus, puis « +n ») au lieu de points muets. */
function Titres({ jour }) {
  if (jour?.ferie) return null
  const taches = tachesDuJour(jour)
  if (!taches.length) return null
  const montrees = taches.slice(0, POINTS_MAX)
  const reste = taches.length - montrees.length
  return (
    <span className="ag-mj-titres" aria-hidden="true">
      {montrees.map((t) => (
        <span key={`t${t.id}`} className={t.statut === 'fait' ? 'faite' : undefined}>
          <i className="point" data-p={t.projet?.couleur || undefined} />
          <span className="t">{t.titre}</span>
        </span>
      ))}
      {reste > 0 ? <em className="plus">{`+${reste}`}</em> : null}
    </span>
  )
}

function libelleJour(iso, jour) {
  const n = tachesDuJour(jour).length
  const morceaux = [jourLong(iso)]
  if (jour?.ferie) morceaux.push('Férié')
  else if (jour && !jour.ouvre) morceaux.push('Jour non travaillé')
  morceaux.push(n >= 2 ? `${n} tâches` : `${n} tâche`)
  return morceaux.join(' · ')
}

export default function VueMois({ du, au, mois, jours, aujourdhui, jourChoisi, onChoisir }) {
  const parJour = Object.fromEntries((jours ?? []).map((j) => [j.jour, j]))
  const reposHabituels = joursDeRepos(jours)
  const dates = datesEntre(du, au)
  return (
    <div className="ag-mois chiffres" role="grid" aria-label="Mois">
      <div role="row" className="ag-mois-ligne">
        {ENTETES.map((e) => <span key={e} className="jsem" role="columnheader">{e}</span>)}
      </div>
      {Array.from({ length: Math.ceil(dates.length / 7) }, (_, rang) => (
        <div role="row" className="ag-mois-ligne" key={dates[rang * 7]}>
          {dates.slice(rang * 7, rang * 7 + 7).map((iso) => {
            const jour = parJour[iso]
            const classes = ['ag-mj',
              iso.slice(0, 7) !== mois ? 'hors' : '',
              (jour ? !jour.ouvre : reposHabituels.has(jourSemaine(iso))) ? 'repos' : '',
              iso === aujourdhui ? 'auj' : '',
              iso === jourChoisi ? 'choisi' : ''].filter(Boolean).join(' ')
            return (
              <button
                key={iso}
                type="button"
                role="gridcell"
                className={classes}
                aria-selected={iso === jourChoisi}
                aria-current={iso === aujourdhui ? 'date' : undefined}
                aria-label={libelleJour(iso, jour)}
                onClick={() => onChoisir?.(iso)}
              >
                <b>{Number(iso.slice(8, 10))}</b>
                <Points jour={jour} />
                <Titres jour={jour} />
              </button>
            )
          })}
        </div>
      ))}
    </div>
  )
}
