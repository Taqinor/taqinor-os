import { useCallback, useEffect, useState } from 'react'
import { ChevronDown, ChevronUp, Lightbulb, Pencil, Star } from 'lucide-react'
import * as client from '../../../api/tachesApi'
import recordsApi from '../../../api/recordsApi'
import { frenchError } from '../../../lib/frenchError'
import AnneauProgression from '../ui/AnneauProgression'
import CaseRonde from '../ui/CaseRonde'
import { annoncer } from '../lib/gestes'
import { accord, jourLong, jourNomme } from '../lib/textes'

/* ============================================================================
   TCH80 — Feuille « Bilan du soir » (textes.md §2.9, regles.md §4.6), ouverte par la carte
   « Faire le bilan », le menu, ou `?ouvrir=bilan` (notification du soir). Le lendemain jusqu'à
   midi, c'est le « Bilan d'hier ». Contenu lu dans `journee/cloture/` (journee_cloture.json) :
     · « {faites} sur {objectif} » (+ essentiel), les segments, « {pt} des {pl} gardées » ;
     · Faites ; Reste : par tâche Reporter à {jour} · Choisir un jour · En réserve · Abandonner
       (Reporter est le choix d'emblée), « Tout reporter à {jour} » les remet toutes sur le prochain
       jour travaillé ; une tâche reportée 3 fois est marquée « À revoir : reportée 3 fois » et,
       sans choix, RESTE à sa place (jamais bloquante) ;
     · « À clore dans l'ERP (n) » : les activités du jour ; UN constat au plus ; « Un mot » (280 car.).
   « Valider » → `journee/cloturer/` (`choix`, `le_reste`, `reflexion`) puis toast « Bilan enregistré ·
   Annuler » ; « Passer » ferme sans rien écrire. Hors ligne : grisé. Après midi le lendemain : lecture seule.
   Maquettes : ecran-bilan.html, ecran-bilan-bas.html, ecran-bilan-rythme.html.
   ========================================================================== */

const REPORTER = 'prochain_jour_ouvre'
const LIMITE_MOT = 280

function useCloture(jour, aujourdhui) {
  const [etat, setEtat] = useState({ chargement: true, erreur: '', donnees: null })
  const charger = useCallback(async () => {
    try {
      const { data } = await client.lireCloture(jour && jour !== aujourdhui ? { jour } : undefined)
      setEtat({ chargement: false, erreur: '', donnees: data })
    } catch (err) {
      setEtat((avant) => ({ ...avant, chargement: false, erreur: frenchError(err) }))
    }
  }, [jour, aujourdhui])
  useEffect(() => {
    charger()
  }, [charger])
  return { ...etat, recharger: charger }
}

function Constat({ constat, onRepondre }) {
  return (
    <div className="constat" role="group" aria-label="Un constat">
      <span className="bandeau-icone"><Lightbulb className="i i-16" aria-hidden="true" /></span>
      <div>
        <p>{constat.texte}</p>
        <div className="carte-actions">
          {constat.boutons.map((b) => (
            <button key={b.reponse} type="button" className="lien-bloc" onClick={() => onRepondre(b.reponse)}>{b.libelle}</button>
          ))}
        </div>
      </div>
    </div>
  )
}

function ChoixReste({ choix, jourReport, onChoisir, minimum }) {
  const [calendrier, setCalendrier] = useState(false)
  const actif = (cle) => choix.choix === cle
  return (
    <>
      <div className="reste-choix" role="group" aria-label="Que faire de cette tâche ?">
        <button type="button" className={actif(REPORTER) ? 'puce choisi' : 'puce'} aria-pressed={actif(REPORTER)}
          onClick={() => { setCalendrier(false); onChoisir({ choix: REPORTER }) }}>
          {`Reporter à ${jourReport}`}
        </button>
        <button type="button" className={actif('jour') ? 'puce choisi' : 'puce'} aria-pressed={actif('jour')}
          onClick={() => setCalendrier((v) => !v)}>
          {actif('jour') ? `Le ${jourNomme(choix.jour, minimum)}` : 'Choisir un jour'}
        </button>
        <button type="button" className={actif('un_jour') ? 'puce choisi' : 'puce'} aria-pressed={actif('un_jour')}
          onClick={() => { setCalendrier(false); onChoisir({ choix: 'un_jour' }) }}>
          En réserve
        </button>
        <button type="button" className={actif('abandonner') ? 'puce choisi' : 'puce'} aria-pressed={actif('abandonner')}
          onClick={() => { setCalendrier(false); onChoisir({ choix: 'abandonner' }) }}>
          Abandonner
        </button>
      </div>
      {calendrier ? (
        <input type="date" className="champ-date" aria-label="Choisir un jour" min={minimum} value={choix.jour ?? ''}
          onChange={(e) => { if (e.target.value) { onChoisir({ choix: 'jour', jour: e.target.value }); setCalendrier(false) } }} />
      ) : null}
    </>
  )
}

function Reste({ item, choix, onChoisir, jourReport, minimum, aTrancher }) {
  return (
    <div className="reste" role="listitem" data-ligne={`${item.type}:${item.id}`}>
      <span className="case vide" />
      <div>
        <div className="titre">{item.titre}</div>
        <div className="meta">
          {aTrancher ? <span>À revoir : reportée 3 fois</span> : null}
          {item.moment === 'soir' ? <span>Ce soir</span> : null}
          {item.projet ? <span data-p={item.projet.couleur}><i className="point" /><span className="projet-nom">{item.projet.nom}</span></span> : null}
        </div>
        <ChoixReste choix={choix} jourReport={jourReport} onChoisir={onChoisir} minimum={minimum} />
      </div>
    </div>
  )
}

function ActiviteAClore({ item, enLigne }) {
  const [faite, setFaite] = useState(false)
  const basculer = async () => {
    if (!enLigne || faite) throw new Error('hors-ligne')
    await recordsApi.markActivityDone(item.id)
    setFaite(true)
  }
  return (
    <div className="ligne-courte" role="listitem">
      <CaseRonde coche={faite} titre={item.titre} desactivee={!enLigne} onBasculer={basculer} />
      <span className="texte">{item.titre}</span>
      {item.lien?.libelle ? <span className="chiffres">{item.lien.libelle}</span> : <span />}
    </div>
  )
}

function Corps({ donnees, choix, enLigne, aujourdhui, fixer, constat, repondreConstat, mot, setMot, motOuvert, setMotOuvert, lecture }) {
  const { bilan } = donnees
  const [compte, ...detail] = String(bilan.texte).split(' · ')
  const restes = donnees.restes ?? []
  const aTrancher = donnees.a_trancher ?? []
  const activites = donnees.activites_a_clore ?? []
  const jourReport = jourNomme(donnees.prochain_jour_ouvre, donnees.jour)
  const toutFait = restes.length + aTrancher.length + activites.length === 0
  return (
    <>
      <div className="entete-date">{jourLong(donnees.jour)}</div>
      <div className="bilan-tete">
        <div className="bilan-compte chiffres">
          {compte}
          {detail.length > 0 ? <span className="bilan-essentiel">{` · ${detail.join(' · ')}`}</span> : null}
        </div>
        <AnneauProgression grand faites={bilan.faites} objectif={bilan.objectif} />
        {bilan.texte_gardees ? <div className="bilan-second chiffres">{bilan.texte_gardees}</div> : null}
      </div>
      {lecture ? <p className="carte-source">Le bilan d&apos;hier n&apos;est plus modifiable après midi.</p> : null}

      {(donnees.faites ?? []).length > 0 ? (
        <div className="bilan-section">
          <p className="fiche-label">Faites <span className="compte chiffres">{donnees.faites.length}</span></p>
          <div role="list">
            {donnees.faites.map((item) => (
              <div key={`${item.type}:${item.id}`} className="ligne-courte" role="listitem">
                <CaseRonde coche titre={item.titre} desactivee onBasculer={() => {}} />
                <span className="texte">{item.titre}</span>
                {item.essentielle ? <Star className="i i-16 etoile" role="img" aria-label="Essentielle" /> : <span />}
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {restes.length + aTrancher.length > 0 ? (
        <div className="bilan-section">
          <div className="restes-tete">
            <p className="fiche-label">Reste</p>
            <button type="button" className="bouton second petit" aria-disabled={lecture || undefined}
              onClick={() => { if (!lecture) fixer(null, { choix: REPORTER }) }}>
              {`Tout reporter à ${jourReport}`}
            </button>
          </div>
          <div role="list">
            {restes.map((item) => (
              <Reste key={`${item.type}:${item.id}`} item={item} jourReport={jourReport} minimum={aujourdhui}
                choix={choix[item.id] ?? { choix: REPORTER }} onChoisir={(c) => fixer(item.id, c)} />
            ))}
            {aTrancher.map((item) => (
              <Reste key={`${item.type}:${item.id}`} item={item} aTrancher jourReport={jourReport} minimum={aujourdhui}
                choix={choix[item.id] ?? { choix: null }} onChoisir={(c) => fixer(item.id, c)} />
            ))}
          </div>
          {aTrancher.length > 0 ? <p className="carte-source">Sans choix, elle reste à sa place.</p> : null}
        </div>
      ) : null}

      {activites.length > 0 ? (
        <div className="bilan-section">
          <p className="fiche-label">{`À clore dans l'ERP (${activites.length})`}</p>
          <div role="list">
            {activites.map((item) => <ActiviteAClore key={item.id} item={item} enLigne={enLigne} />)}
          </div>
        </div>
      ) : null}

      {toutFait ? <p className="vide-phrase">Tout est fait</p> : null}
      {constat ? <Constat constat={constat} onRepondre={repondreConstat} /> : null}

      <button type="button" className="un-mot" aria-expanded={motOuvert} onClick={() => setMotOuvert((v) => !v)}>
        <Pencil className="i i-16" aria-hidden="true" />
        Un mot sur ta journée (facultatif)
        {motOuvert ? <ChevronUp className="i i-16" aria-hidden="true" /> : <ChevronDown className="i i-16" aria-hidden="true" />}
      </button>
      {motOuvert ? (
        <textarea
          className="champ-mot"
          aria-label="Un mot sur ta journée"
          maxLength={LIMITE_MOT}
          rows={3}
          value={mot}
          onChange={(e) => setMot(e.target.value)}
        />
      ) : null}
    </>
  )
}

export default function FeuilleBilan({ jour = null, aujourdhui, maintenant = '', enLigne = true, onValide, onPasser }) {
  const { chargement, erreur, donnees, recharger } = useCloture(jour, aujourdhui)
  const [choix, setChoix] = useState({})
  const [mot, setMot] = useState('')
  const [motOuvert, setMotOuvert] = useState(false)
  const [constatRepondu, setConstatRepondu] = useState(false)
  const [envoi, setEnvoi] = useState(false)
  const [erreurEnvoi, setErreurEnvoi] = useState('')

  const fixer = (id, c) => {
    if (id === null) setChoix({})
    else setChoix((avant) => ({ ...avant, [id]: c }))
  }

  const repondreConstat = async (reponse) => {
    try {
      await client.repondreProposition(donnees.constat.id, { reponse })
      setConstatRepondu(true)
    } catch (err) {
      annoncer(frenchError(err))
    }
  }

  const valider = async () => {
    if (!enLigne) { annoncer('Possible une fois connecté'); return }
    setEnvoi(true)
    setErreurEnvoi('')
    const nommes = Object.entries(choix).filter(([, c]) => c.choix && c.choix !== REPORTER)
    const corps = {
      jour: donnees.jour,
      choix: [
        ...nommes.map(([id, c]) => ({ id: Number(id), choix: c.choix, ...(c.choix === 'jour' ? { jour: c.jour } : {}) })),
        ...(donnees.a_trancher ?? [])
          .map((item) => [item.id, choix[item.id]])
          .filter(([, c]) => c?.choix === REPORTER)
          .map(([id]) => ({ id, choix: REPORTER })),
      ],
      le_reste: true,
      reflexion: mot.trim(),
    }
    try {
      const { data } = await client.cloturerJournee(corps)
      onValide(data)
    } catch (err) {
      setErreurEnvoi(frenchError(err))
      setEnvoi(false)
    }
  }

  const titreHier = jour && jour !== aujourdhui
  const lecture = Boolean(donnees?.possible_jusqua && maintenant && maintenant > donnees.possible_jusqua)
  if (chargement) return <div className="squelette" role="status" aria-label="Chargement" />
  if (!donnees) {
    return (
      <div className="pas-a-jour" role="status">
        <span>{erreur || 'Le bilan ne se charge pas.'}</span>
        <button type="button" className="bouton lien" onClick={recharger}>Réessayer</button>
      </div>
    )
  }
  return (
    <div className="bilan" data-bilan={titreHier ? 'hier' : 'soir'}>
      <Corps
        donnees={donnees} choix={choix} enLigne={enLigne} aujourdhui={aujourdhui} fixer={fixer}
        constat={constatRepondu ? null : donnees.constat} repondreConstat={repondreConstat}
        mot={mot} setMot={setMot} motOuvert={motOuvert} setMotOuvert={setMotOuvert} lecture={lecture}
      />
      {erreurEnvoi ? <p className="erreur-champ" role="alert">{erreurEnvoi}</p> : null}
      <div className="feuille-pied">
        <button type="button" className="bouton discret" onClick={onPasser}>Passer</button>
        <button
          type="button"
          className="bouton plein large"
          aria-disabled={!enLigne || envoi || lecture || undefined}
          onClick={() => { if (!envoi && !lecture) valider() }}
        >
          Valider
        </button>
      </div>
      <span className="sr" aria-live="polite">{accord(donnees.restes?.length ?? 0, 'reste', 'restes')}</span>
    </div>
  )
}
