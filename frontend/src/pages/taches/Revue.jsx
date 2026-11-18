import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Star, TriangleAlert } from 'lucide-react'
import { deciderRevue, lireRevue, lireVueProjet } from '../../api/tachesApi'
import { frenchError } from '../../lib/frenchError'
import CoquilleTaches from '../../features/taches/coquille/CoquilleTaches'
import { avancementDe, echeanceProjet } from '../../features/taches/projets/LigneProjet'
import { annoncer } from '../../features/taches/lib/gestes'
import { aujourdhuiIso } from '../../features/taches/lib/textes'

/* ============================================================================
   TCH93 — Écran Revue de la semaine (`/taches/revue`). Maquette : docs/taches/maquettes/revue-semaine.html.
   Textes : reference/textes.md §2.7 et §4.6. Contrats : `revue_projets.json` (GET) et `revue_decision.json` (PUT).
   Une carte par projet, UNE à la fois : « Faites cette semaine » (3 titres au plus), « « A » attend « B » »,
   « Prochaine action » [Changer], santé, « Intention de la semaine (facultatif) », case « Projet de la semaine »,
   puis Garder · Pause · Terminer · Suivant. Chaque bouton écrit la décision de la carte (PUT), puis passe à la suivante ;
   un refus (« Déjà « A » cette semaine. ») reste SUR la carte, sous la case. À la fin : « Planifier ma semaine ».
   « Semaine courte » : le bilan est remplacé par « Semaine courte, on reprend lundi. » — aucun chiffre inventé.
   ========================================================================== */

const SEMAINE_COURTE = 'Semaine courte, on reprend lundi.'
export const ROUTE_PLANIFIER_SEMAINE = '/taches/agenda?vue=semaine&placer=1'
const DECISIONS = [['garder', 'Garder'], ['pause', 'Pause'], ['terminer', 'Terminer'], ['passe', 'Suivant']]

function ChoixAction({ projetId, valeur, onChoisir }) {
  const [taches, setTaches] = useState(null)
  const [erreur, setErreur] = useState('')
  useEffect(() => {
    let vivant = true
    lireVueProjet(projetId, { vue: 'liste' })
      .then(({ data }) => {
        if (!vivant) return
        const toutes = [...(data.sections ?? []).flatMap((s) => s.taches ?? []), ...(data.sans_section ?? [])]
        setTaches(toutes.filter((t) => t.statut !== 'fait'))
      })
      .catch((err) => { if (vivant) setErreur(frenchError(err, 'Les tâches du projet n\'ont pas pu être lues. Réessaie.')) })
    return () => { vivant = false }
  }, [projetId])
  return (
    <div className="ep-groupe">
      <label className="ep-etiquette" htmlFor="rv-action">Prochaine action</label>
      <select id="rv-action" className="champ" value={valeur ?? ''} onChange={(e) => onChoisir((taches ?? []).find((t) => String(t.id) === e.target.value) ?? null)}>
        <option value="">Choisir une tâche</option>
        {(taches ?? []).map((t) => <option key={t.id} value={t.id}>{t.titre}</option>)}
      </select>
      {erreur ? <p className="ep-erreur" role="alert">{erreur}</p> : null}
    </div>
  )
}

function Carte({ carte, index, total, aujourdhui, focusId, onFocus, onDecider, occupe, erreurs }) {
  const { projet } = carte
  const [intention, setIntention] = useState(carte.revue?.intention ?? '')
  const [action, setAction] = useState(carte.prochaine_action)
  const [change, setChange] = useState(false)
  const [terminer, setTerminer] = useState(false)
  const { texte } = avancementDe(projet)
  const ech = projet.echeance ? echeanceProjet(projet.echeance, aujourdhui) : null
  const faites = (carte.faites_semaine ?? []).slice(0, 3)
  const corps = (decision, issue = null) => ({
    intention, prochaine_action_id: action?.id ?? null, decision, focus: focusId === projet.id, issue,
  })

  return (
    <section className="ep-carte-revue" aria-label={projet.nom} data-p={projet.couleur}>
      <header className="ep-carte-tete">
        <h2 className="ep-titre"><i className="point" aria-hidden="true" />{projet.nom}</h2>
        <span className="chiffres ep-rang">{`${index + 1}/${total}`}</span>
      </header>
      <div className="meta">
        <span className="chiffres">{texte}</span>
        {ech ? <span className="chiffres">{ech.texte}</span> : null}
        {(projet.sante ?? []).length > 0 ? (
          <span className="ep-sante surveiller"><TriangleAlert className="i i-14" aria-hidden="true" />à surveiller</span>
        ) : null}
        {projet.a_planifier ? <span className="ep-aplanifier">À planifier</span> : null}
      </div>
      {(projet.sante ?? []).map((s) => <p key={s.code} className="ep-sante-ligne surveiller">{s.phrase}</p>)}
      {faites.length > 0 ? (
        <p className="ep-revue-ligne">{`Faites cette semaine : ${faites.map((t) => t.titre).join(', ')}`}</p>
      ) : null}
      {(carte.bloquees ?? []).map((b) => (
        <p key={b.id} className="ep-revue-ligne">{`« ${b.titre} » attend « ${b.attend.titre} »`}</p>
      ))}
      {action && !change ? (
        <p className="ep-revue-ligne">
          {`Prochaine action : ${action.titre}`}
          <button type="button" className="bouton discret" onClick={() => setChange(true)}>Changer</button>
        </p>
      ) : (
        <ChoixAction
          projetId={projet.id}
          valeur={action?.id}
          onChoisir={(tache) => { setAction(tache); setChange(false) }}
        />
      )}
      <div className="ep-groupe">
        <label className="ep-etiquette" htmlFor={`rv-intention-${projet.id}`}>Intention de la semaine (facultatif)</label>
        <input id={`rv-intention-${projet.id}`} className="champ" value={intention} onChange={(e) => setIntention(e.target.value)} />
      </div>
      <div className="ep-groupe">
        {/* Passe visuelle n° 45 — « Projet de la semaine » : l'étoile de revue-semaine.html (`.ep-focus`), plus une case
            carrée ; la case native reste dessous (clavier, lecteur d'écran, `aria-invalid`). */}
        <label className="ep-case ep-focus">
          <input
            type="checkbox"
            checked={focusId === projet.id}
            onChange={(e) => onFocus(e.target.checked ? projet.id : null)}
            aria-invalid={erreurs.focus ? 'true' : undefined}
            aria-describedby={erreurs.focus ? 'rv-focus-err' : undefined}
          />
          <Star className="i i-16" aria-hidden="true" />
          Projet de la semaine
        </label>
        {erreurs.focus ? <p id="rv-focus-err" className="ep-erreur" role="alert">{erreurs.focus}</p> : null}
        {erreurs.general ? <p className="ep-erreur" role="alert">{erreurs.general}</p> : null}
      </div>
      {terminer ? (
        <div className="ep-groupe">
          <div className="ep-etiquette" id="rv-issue">Atteint ou abandonné ?</div>
          <div className="puces" role="radiogroup" aria-labelledby="rv-issue">
            <button type="button" className="puce" role="radio" aria-checked="false" disabled={occupe}
              onClick={() => onDecider(carte, corps('terminer', 'atteint'))}>Atteint</button>
            <button type="button" className="puce" role="radio" aria-checked="false" disabled={occupe}
              onClick={() => onDecider(carte, corps('terminer', 'abandonne'))}>Abandonné</button>
          </div>
          {erreurs.issue ? <p className="ep-erreur" role="alert">{erreurs.issue}</p> : null}
        </div>
      ) : null}
      <div className="carte-actions ep-revue-boutons">
        {DECISIONS.map(([code, libelle]) => (
          <button
            key={code}
            type="button"
            className={`bouton ${code === 'garder' ? 'plein' : 'second'}`}
            disabled={occupe}
            onClick={() => (code === 'terminer' ? setTerminer(true) : onDecider(carte, corps(code)))}
          >
            {libelle}
          </button>
        ))}
      </div>
    </section>
  )
}

export default function Revue() {
  const navigate = useNavigate()
  const aujourdhui = useMemo(() => aujourdhuiIso(), [])
  const [revue, setRevue] = useState(null)
  const [index, setIndex] = useState(0)
  const [focusId, setFocusId] = useState(null)
  const [occupe, setOccupe] = useState(false)
  const [erreurs, setErreurs] = useState({})
  const [erreur, setErreur] = useState('')

  const lire = useCallback(async () => {
    try {
      const { data } = await lireRevue()
      setRevue(data)
      setFocusId(data.focus_projet_id ?? null)
      setErreur('')
    } catch (err) {
      setErreur(frenchError(err, 'La revue n\'a pas pu être lue. Réessaie.'))
    }
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement à l'ouverture de l'écran (D-ENF22)
  useEffect(() => { lire() }, [lire])

  const decider = async (carte, corps) => {
    setOccupe(true)
    setErreurs({})
    try {
      await deciderRevue(carte.projet.id, { semaine: revue.semaine, ...corps })
      annoncer(`« ${carte.projet.nom} » : décision enregistrée`)
      setIndex((i) => i + 1)
    } catch (err) {
      const champs = err?.response?.status === 400 ? err.response.data : null
      if (champs && typeof champs === 'object') {
        setErreurs(Object.fromEntries(Object.entries(champs).map(([k, v]) => [k, Array.isArray(v) ? v[0] : String(v)])))
      } else {
        setErreurs({ general: frenchError(err, 'La décision n\'a pas été enregistrée. Réessaie.') })
      }
    } finally {
      setOccupe(false)
    }
  }

  const cartes = revue?.cartes ?? []
  const fini = revue && index >= cartes.length
  return (
    <CoquilleTaches ecran="revue" titre="Revue de la semaine">
      {erreur ? <p className="ep-alerte-ligne" role="alert">{erreur}</p> : null}
      {revue ? (
        <p className="ep-constat chiffres">{revue.semaine_courte ? SEMAINE_COURTE : (revue.bilan_semaine?.texte ?? '')}</p>
      ) : null}
      {revue && cartes.length === 0 ? <p className="ep-constat">Aucun projet actif</p> : null}
      {revue && !fini ? (
        <Carte
          key={cartes[index].projet.id}
          carte={cartes[index]}
          index={index}
          total={cartes.length}
          aujourdhui={aujourdhui}
          focusId={focusId}
          onFocus={setFocusId}
          onDecider={decider}
          occupe={occupe}
          erreurs={erreurs}
        />
      ) : null}
      {fini ? (
        <div className="ep-revue-fin">
          <button type="button" className="bouton plein" onClick={() => navigate(ROUTE_PLANIFIER_SEMAINE)}>Planifier ma semaine</button>
        </div>
      ) : null}
    </CoquilleTaches>
  )
}
