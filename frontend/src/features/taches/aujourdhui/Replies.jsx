import { useCallback, useState } from 'react'
import { ChevronDown } from 'lucide-react'
import * as client from '../../../api/tachesApi'
import { frenchError } from '../../../lib/frenchError'
import { annoncer, proposerAnnuler } from '../lib/gestes'
import { accord, jourNomme } from '../lib/textes'
import { Ligne } from './Sections'
import { Ailleurs } from './LignesErp'

/* ============================================================================
   TCH81 — Les sections REPLIÉES d'Aujourd'hui (regles.md §4.1, lignes 7 à 10) :
     · « À revoir (n) » : reportées 3 fois, retards de plus de 7 jours, activités ERP en retard ; un lot
       « Tout en réserve » ; par tâche : Aujourd'hui · Choisir un jour · En réserve · Abandonner
       (+ Découper si reportée 3 fois) → `taches/{id}/trancher/` ; jamais bloquant ;
     · « En attente (n) » · « {b} en attente d'une autre tâche » ; « Faites (n) » ;
     · « Ailleurs dans l'ERP », lu à l'ouverture seulement.
   Un en-tête vide est absent. Tout geste est optimiste, grisé hors ligne, défait par « Annuler ».
   Maquettes : ecran-aujourdhui-matin.html (« À revoir 2 », « En attente 1 »), composants-4.html.
   Textes : reference/textes.md §2.2 « En-têtes repliés », « À revoir », « Actions d'une ligne À revoir ».
   ========================================================================== */

const cleDe = (item) => `${item.type}:${item.id}`

/** « tâche » : seules les tâches se tranchent ; une activité ERP en retard se coche ou s'ouvre. */
const estTache = (item) => item.type === 'tache'

/** Les gestes d'« À revoir » : trancher une tâche, tout mettre en réserve. Optimistes, annulables. */
// eslint-disable-next-line react-refresh/only-export-components -- hook des gestes, lu par la page (D-ENF22)
export function useARevoir({ donnees, setDonnees, garde, charger }) {
  const trancher = useCallback(async (item, choix, jour = null) => {
    try { garde() } catch { return }
    try {
      const { data } = await client.trancherTache(item.id, jour ? { choix, jour } : { choix })
      setDonnees((d) => {
        const suite = { ...d, a_decider: (d.a_decider ?? []).filter((it) => cleDe(it) !== cleDe(item)) }
        if (choix === 'aujourdhui') suite.journee = [...(d.journee ?? []), { ...item, jour_prevu: d.jour, motif: null }]
        return suite
      })
      const message = {
        aujourdhui: "Mise à aujourd'hui",
        jour: `Prévue ${jourNomme(jour, donnees.jour)}`,
        un_jour: 'En réserve',
        abandonner: 'Abandonnée',
      }[choix]
      proposerAnnuler({
        message,
        onAnnuler: async () => {
          await client.annulerGeste(data.geste_id)
          setDonnees((d) => ({
            ...d,
            a_decider: [item, ...(d.a_decider ?? [])],
            journee: (d.journee ?? []).filter((it) => cleDe(it) !== cleDe(item)),
          }))
        },
      })
    } catch (err) {
      annoncer(frenchError(err))
    }
  }, [donnees, setDonnees, garde])

  const toutEnReserve = useCallback(async () => {
    try { garde() } catch { return }
    const ids = (donnees.a_decider ?? []).filter(estTache).map((it) => it.id)
    if (ids.length === 0) return
    try {
      const { data } = await client.traiterLot({ ids, action: 'planifier', valeurs: { quelque_jour: true } })
      const rangees = new Set(data.appliquees ?? [])
      setDonnees((d) => ({ ...d, a_decider: (d.a_decider ?? []).filter((it) => !(estTache(it) && rangees.has(it.id))) }))
      proposerAnnuler({
        message: `${rangees.size} en réserve`,
        onAnnuler: async () => { await client.annulerGeste(data.geste_id); await charger() },
      })
    } catch (err) {
      annoncer(frenchError(err))
    }
  }, [donnees, setDonnees, garde, charger])

  return { trancher, toutEnReserve }
}

/** Les quatre actions d'une ligne d'« À revoir » (+ Découper si reportée 3 fois). */
function ActionsARevoir({ item, geste, revoir, minimum }) {
  const [calendrier, setCalendrier] = useState(false)
  return (
    <div className="reste-choix revoir-actions" role="group" aria-label={`Que faire de « ${item.titre} » ?`} data-necessite-reseau="">
      <button type="button" className="puce" onClick={() => revoir.trancher(item, 'aujourdhui')}>Aujourd&apos;hui</button>
      <button type="button" className="puce" aria-expanded={calendrier} onClick={() => setCalendrier((v) => !v)}>Choisir un jour</button>
      <button type="button" className="puce" onClick={() => revoir.trancher(item, 'un_jour')}>En réserve</button>
      <button type="button" className="puce" onClick={() => revoir.trancher(item, 'abandonner')}>Abandonner</button>
      {item.motif === 'reportee_3_fois' ? (
        <button type="button" className="puce" onClick={() => geste.ouvrir(item)}>Découper</button>
      ) : null}
      {calendrier ? (
        <input type="date" className="champ-date" aria-label={`Jour pour « ${item.titre} »`} min={minimum}
          onChange={(e) => { if (e.target.value) { setCalendrier(false); revoir.trancher(item, 'jour', e.target.value) } }} />
      ) : null}
    </div>
  )
}

/** Un en-tête replié (« À revoir 2 ») : un bouton qui déplie ses lignes. */
function Replie({ titre, compte = null, indice = '', onOuvrir = null, children }) {
  const [ouvert, setOuvert] = useState(false)
  const basculer = () => {
    if (!ouvert && onOuvrir) onOuvrir()
    setOuvert((v) => !v)
  }
  return (
    <>
      <button type="button" className="replie" aria-expanded={ouvert} onClick={basculer}>
        <span>{titre}</span>
        {compte === null ? null : <span className="compte chiffres">{compte}</span>}
        {indice ? <span className="indice">{indice}</span> : null}
        <ChevronDown className="i i-16" aria-hidden="true" />
      </button>
      {ouvert ? children : null}
    </>
  )
}

export default function Replies({ donnees, contexte, geste, revoir, enLigne }) {
  const aDecider = donnees.a_decider ?? []
  const enAttente = donnees.en_attente ?? []
  const faites = donnees.faites ?? []
  const bloquees = donnees.a_trier?.bloquees ?? 0
  const lignes = (items, avecActions = false) => (
    <div className="liste" role="list">
      {items.map((item) => (
        <div key={cleDe(item)}>
          <Ligne item={item} contexte={contexte} geste={geste} />
          {avecActions && estTache(item) ? (
            <ActionsARevoir item={item} geste={geste} revoir={revoir} minimum={donnees.jour} />
          ) : null}
        </div>
      ))}
    </div>
  )
  return (
    <div className="replies">
      {aDecider.length > 0 ? (
        <Replie titre="À revoir" compte={aDecider.length}>
          {aDecider.some(estTache) ? (
            <div className="propose-actions">
              <button type="button" className="bouton second" data-necessite-reseau="" aria-disabled={!enLigne || undefined} onClick={revoir.toutEnReserve}>
                Tout en réserve
              </button>
              <button type="button" className="bouton lien" data-necessite-reseau="" aria-disabled={!enLigne || undefined}
                onClick={() => geste.copilote('Aide-moi à prioriser')}>
                Revoir avec le Copilote
              </button>
            </div>
          ) : null}
          {lignes(aDecider, true)}
        </Replie>
      ) : null}
      {enAttente.length > 0 ? (
        <Replie
          titre="En attente"
          compte={enAttente.length}
          indice={bloquees > 0 ? `· ${accord(bloquees, 'en attente', 'en attente')} d'une autre tâche` : ''}
        >
          {lignes(enAttente)}
        </Replie>
      ) : null}
      {faites.length > 0 ? <Replie titre="Faites" compte={faites.length}>{lignes(faites)}</Replie> : null}
      <Replie titre="Ailleurs dans l'ERP"><Ailleurs /></Replie>
    </div>
  )
}
