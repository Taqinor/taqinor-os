import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ChevronRight, Star, TriangleAlert } from 'lucide-react'
import { deciderRevue, lireRevue, lireVueProjet } from '../../api/tachesApi'
import { frenchError } from '../../lib/frenchError'
import CoquilleTaches from '../../features/taches/coquille/CoquilleTaches'
import { avancementDe, echeanceProjet } from '../../features/taches/projets/LigneProjet'
import { annoncer } from '../../features/taches/lib/gestes'
import { accord, aujourdhuiIso } from '../../features/taches/lib/textes'

/* ============================================================================
   TCH93 — Écran Revue de la semaine (`/taches/revue`). Maquette : docs/taches/maquettes/revue-semaine.html.
   Textes : reference/textes.md §2.7 et §4.6. Contrats : `revue_projets.json` (GET) et `revue_decision.json` (PUT).
   Une carte par projet, UNE à la fois : « Faites cette semaine » (3 titres au plus), « « A » attend « B » »,
   « Prochaine action » [Changer], santé, « Intention de la semaine (facultatif) », case « Projet de la semaine »,
   puis Continuer · Pause · Terminer · Suivant (R3-090 : « Continuer » dit la décision garder). Chaque bouton écrit la décision de la carte (PUT), puis passe à la suivante ;
   un refus (« Déjà « A » cette semaine. ») reste SUR la carte, sous la case. À la fin : « Planifier ma semaine ».
   « Semaine courte » : le bilan est remplacé par « Semaine courte, on reprend lundi. » — aucun chiffre inventé.
   ========================================================================== */

const SEMAINE_COURTE = 'Semaine courte, on reprend lundi.'
export const ROUTE_PLANIFIER_SEMAINE = '/taches/agenda?vue=semaine&placer=1'

/** R3-099 — « Planifier ma semaine » depuis la Revue : à partir du jeudi (et le week-end), la semaine à planifier est la
 *  SUIVANTE — celle qui finit n'a plus rien à planifier — : l'adresse porte son lundi (`jour`), comme le fait l'Agenda
 *  dès le jeudi 15 h. Du lundi au mercredi, l'adresse ne dit pas de jour : l'Agenda choisit (semaine en cours). */
function routePlanifierDepuisRevue(aujourdhui) {
  const [a, m, j] = aujourdhui.split('-').map(Number)
  const jourSemaine = (new Date(Date.UTC(a, m - 1, j)).getUTCDay() + 6) % 7 // lundi = 0
  if (jourSemaine < 3) return ROUTE_PLANIFIER_SEMAINE
  const lundi = new Date(Date.UTC(a, m - 1, j + 7 - jourSemaine)).toISOString().split('T')[0]
  return `${ROUTE_PLANIFIER_SEMAINE}&jour=${lundi}`
}

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

// R3-090 (M6, C-20) — « Continuer » : la décision `garder` du serveur, dite avec le mot de Reda
const CHOIX = [['garder', 'Continuer'], ['pause', 'Pause'], ['terminer', 'Terminer']]
const DECISION_DITE = { garder: 'Continue', pause: 'En pause', terminer: 'Terminé', passe: 'Passé' }
const INVITE_INTENTION = 'Ce que tu veux finir cette semaine…'

function Carte({ carte, index, total, aujourdhui, intention, focusId, onFocus, onDecider, occupe, erreurs }) {
  const { projet } = carte
  const [action, setAction] = useState(carte.prochaine_action)
  const [change, setChange] = useState(false)
  // Garder d'office ; la décision déjà écrite cette semaine (carte rouverte) est celle qui est cochée
  const [choix, setChoix] = useState(CHOIX.some(([code]) => code === carte.revue?.decision) ? carte.revue.decision : 'garder')
  const [issue, setIssue] = useState('')
  const { texte } = avancementDe(projet)
  const ech = projet.echeance ? echeanceProjet(projet.echeance, aujourdhui) : null
  const faites = (carte.faites_semaine ?? []).slice(0, 3)
  const prevuesAujourdhui = Number.isInteger(carte.prevues_aujourdhui_nb) ? carte.prevues_aujourdhui_nb : 0
  const corps = (decision, lissue = null) => ({
    intention, prochaine_action_id: action?.id ?? null, decision, focus: focusId === projet.id, issue: lissue,
  })

  return (
    <section className="ep-carte-revue" aria-label={projet.nom} data-p={projet.couleur}>
      <header className="ep-carte-tete">
        <h2 className="ep-titre"><i className="point" aria-hidden="true" />{projet.nom}</h2>
        <span className="chiffres ep-rang-revue">{`${index + 1}/${total}`}</span>
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
      <div className="segmente ep-decision" role="radiogroup" aria-label="Décision">
        {CHOIX.map(([code, libelle]) => (
          <button key={code} type="button" role="radio" aria-checked={choix === code} disabled={occupe}
            onClick={() => { setChoix(code); setIssue('') }}>{libelle}</button>
        ))}
      </div>
      {choix === 'pause' && prevuesAujourdhui > 0 ? (
        // C-5 — mettre en pause arrête Proposé, À trier et les jours suivants, jamais ce qui est déjà prévu aujourd'hui.
        // Le nombre est CELUI QUE LE SERVEUR SERT (`prevues_aujourdhui_nb`) : sans lui, rien n'est dit.
        <p className="ep-revue-ligne ep-pause-reste" role="status">
          {`${accord(prevuesAujourdhui, 'tâche prévue', 'tâches prévues')} aujourd'hui ${prevuesAujourdhui >= 2 ? 'restent' : 'reste'} dans ta journée.`}
        </p>
      ) : null}
      {choix === 'terminer' ? (
        <div className="ep-groupe">
          <div className="ep-etiquette" id="rv-issue">Atteint ou abandonné ?</div>
          <div className="puces" role="radiogroup" aria-labelledby="rv-issue">
            <button type="button" className="puce" role="radio" aria-checked={issue === 'atteint'} disabled={occupe}
              onClick={() => setIssue('atteint')}>Atteint</button>
            <button type="button" className="puce" role="radio" aria-checked={issue === 'abandonne'} disabled={occupe}
              onClick={() => setIssue('abandonne')}>Abandonné</button>
          </div>
          {erreurs.issue ? <p className="ep-erreur" role="alert">{erreurs.issue}</p> : null}
        </div>
      ) : null}
      <div className="carte-actions ep-revue-boutons">
        <button type="button" className="bouton discret" disabled={occupe} onClick={() => onDecider(carte, corps('passe'))}>Passer</button>
        <button type="button" className="bouton plein" disabled={occupe || (choix === 'terminer' && !issue)}
          onClick={() => onDecider(carte, corps(choix, choix === 'terminer' ? issue : null))}>Suivant →</button>
      </div>
    </section>
  )
}

export default function Revue() {
  const navigate = useNavigate()
  const aujourdhui = useMemo(() => aujourdhuiIso(), [])
  const [revue, setRevue] = useState(null)
  // R2-068 — où en est la revue : la décision de chaque projet cette semaine (servie, puis écrite au fil du parcours) ;
  // la carte montrée est la première non décidée (reprise après une interruption) ; UNE intention, en tête
  const [decisions, setDecisions] = useState({})
  const [intention, setIntention] = useState('')
  const [index, setIndex] = useState(0)
  const [focusId, setFocusId] = useState(null)
  const [occupe, setOccupe] = useState(false)
  const [erreurs, setErreurs] = useState({})
  const [erreur, setErreur] = useState('')
  // R3-090 — une carte rouverte depuis le résumé : sa décision écrite, on revient au résumé (pas à la carte suivante)
  const [retouche, setRetouche] = useState(false)

  const lire = useCallback(async () => {
    try {
      const { data } = await lireRevue()
      const cartesLues = data.cartes ?? []
      setRevue(data)
      setFocusId(data.focus_projet_id ?? null)
      setDecisions(Object.fromEntries(cartesLues.map((c) => [c.projet.id, c.revue?.decision ?? ''])))
      setIntention(cartesLues.map((c) => c.revue?.intention).find(Boolean) ?? '')
      const reprise = cartesLues.findIndex((c) => !c.revue?.decision)
      setIndex(reprise < 0 ? cartesLues.length : reprise)
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
      const ecrites = { ...decisions, [carte.projet.id]: corps.decision }
      setDecisions(ecrites)
      // la carte suivante est la prochaine SANS décision (un projet déjà mis en pause cette semaine, servi avec sa
      // décision, n'est pas redemandé) ; une carte rouverte depuis le résumé y ramène
      const liste = revue.cartes ?? []
      const prochaine = retouche ? -1 : liste.findIndex((c, rang) => rang > index && !ecrites[c.projet.id])
      setIndex(prochaine < 0 ? liste.length : prochaine)
      setRetouche(false)
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
        <div className="ep-groupe ep-intention">
          <label className="ep-etiquette" htmlFor="rv-intention">Intention de la semaine (facultatif)</label>
          {/* R3-090 — une invite : le champ vide de 48 pt ne disait pas quoi y écrire */}
          <input id="rv-intention" className="champ" placeholder={INVITE_INTENTION} value={intention} onChange={(e) => setIntention(e.target.value)} />
        </div>
      ) : null}
      {revue && !fini ? (
        <Carte
          key={cartes[index].projet.id}
          carte={cartes[index]}
          index={index}
          total={cartes.length}
          aujourdhui={aujourdhui}
          intention={intention}
          focusId={focusId}
          onFocus={setFocusId}
          onDecider={decider}
          occupe={occupe}
          erreurs={erreurs}
        />
      ) : null}
      {/* R3-090 — le résumé : l'intention en tête, puis TOUTES les décisions servies (un projet mis en pause ou terminé
          garde sa ligne : le serveur sert sa carte tant qu'il a une revue cette semaine) ; une ligne touchée rouvre sa
          carte, et la décision écrite ramène au résumé */}
      {fini && cartes.length > 0 && intention.trim() ? (
        <p className="ep-constat ep-resume-intention"><b>Intention de la semaine</b>{` · ${intention.trim()}`}</p>
      ) : null}
      {fini && cartes.length > 0 ? (
        <ul className="ep-resume-revue" aria-label="Résumé de la revue">
          {cartes.map((c, rang) => (
            <li key={c.projet.id} data-p={c.projet.couleur}>
              <button type="button" className="ep-resume-ligne" onClick={() => { setRetouche(true); setErreurs({}); setIndex(rang) }}>
                <i className="point" aria-hidden="true" /><span className="nom">{c.projet.nom}</span>
                <span className="decision">{DECISION_DITE[decisions[c.projet.id]] ?? ''}</span>
                <ChevronRight className="i i-16" aria-hidden="true" />
              </button>
            </li>
          ))}
        </ul>
      ) : null}
      {fini ? (
        <div className="ep-revue-fin">
          <button type="button" className="bouton plein" onClick={() => navigate(routePlanifierDepuisRevue(aujourdhui))}>Planifier ma semaine</button>
        </div>
      ) : null}
    </CoquilleTaches>
  )
}
