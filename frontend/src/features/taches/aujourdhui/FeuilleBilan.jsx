import { useCallback, useEffect, useState } from 'react'
import { ChevronDown, ChevronUp, Lightbulb, MoreHorizontal, Pencil, Star } from 'lucide-react'
import * as client from '../../../api/tachesApi'
import recordsApi from '../../../api/recordsApi'
import { frenchError } from '../../../lib/frenchError'
import AnneauProgression from '../ui/AnneauProgression'
import CaseRonde from '../ui/CaseRonde'
import { annoncer } from '../lib/gestes'
import { accord, jourLong, jourNomme } from '../lib/textes'
import { useCompteTaches } from '../lib/enLigne'
import { ecrireTexte, lireTexte, viderALaDeconnexion } from '../lib/stockage'

/* ============================================================================
   TCH80 — Feuille « Bilan du soir » (textes.md §2.9, regles.md §4.6), ouverte par la carte
   « Faire le bilan », le menu, ou `?ouvrir=bilan` (notification du soir). Le lendemain jusqu'à
   midi, c'est le « Bilan d'hier ». Contenu lu dans `journee/cloture/` (journee_cloture.json) :
     · « {faites} sur {objectif} » (+ essentiel), les segments (R3-020 : plus de second chiffre « gardées ») ;
     · Faites ; Reste : par tâche Reporter à {jour} · Choisir un jour · Plus tard · Abandonner
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

/** Le brouillon du « mot » d'un bilan : une clé par compte et par jour de bilan (rien sans compte connu), gardé
 *  par `lib/stockage` (stockage indisponible : le mot vit le temps de la feuille) et vidé à la déconnexion. */
const PREFIXE_MOT = 'taches:bilan-mot:'
const cleBrouillonMot = (userId, jourBilan) => (userId != null && jourBilan ? `${PREFIXE_MOT}${userId}:${jourBilan}` : null)
const lireMot = lireTexte
const garderMot = ecrireTexte
viderALaDeconnexion(PREFIXE_MOT)

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

/**
 * R2-030 — UNE action visible par tâche : le choix retenu (« Reporter à ven. 20 » d'emblée), et « ⋯ » qui déplie les
 * autres (Reporter · Choisir un jour · Plus tard · Abandonner) — quatre pilules par tâche en faisaient vingt pour cinq.
 * Une tâche « à revoir » (aucun choix d'emblée) montre « Que faire ? ».
 */
function ChoixReste({ titre, choix, jourReport, onChoisir, minimum }) {
  const [autres, setAutres] = useState(false)
  const [calendrier, setCalendrier] = useState(false)
  const retenu = {
    [REPORTER]: `Reporter à ${jourReport}`,
    jour: choix.jour ? `Le ${jourNomme(choix.jour, minimum)}` : '',
    un_jour: 'Plus tard',
    abandonner: 'Abandonner',
  }[choix.choix] ?? ''
  const prendre = (suite) => { setAutres(false); setCalendrier(false); onChoisir(suite) }
  const options = [
    { cle: REPORTER, libelle: `Reporter à ${jourReport}`, choisir: () => prendre({ choix: REPORTER }) },
    { cle: 'jour', libelle: 'Choisir un jour', choisir: () => setCalendrier((v) => !v) },
    { cle: 'un_jour', libelle: 'Plus tard', choisir: () => prendre({ choix: 'un_jour' }) },
    { cle: 'abandonner', libelle: 'Abandonner', choisir: () => prendre({ choix: 'abandonner' }) },
  ].filter((o) => o.cle === 'jour' || o.cle !== choix.choix)
  return (
    <>
      <div className="reste-choix" role="group" aria-label="Que faire de cette tâche ?">
        {retenu ? (
          <button type="button" className="puce choisi" aria-pressed="true" onClick={() => setAutres((v) => !v)}>{retenu}</button>
        ) : null}
        <button type="button" className={retenu ? 'puce plus' : 'puce'} aria-expanded={autres}
          aria-label={retenu ? `Autres choix pour « ${titre} »` : undefined} onClick={() => setAutres((v) => !v)}>
          {retenu ? <MoreHorizontal className="i i-16" aria-hidden="true" /> : 'Que faire ?'}
        </button>
      </div>
      {autres ? (
        <div className="reste-choix" role="group" aria-label={`Autres choix pour « ${titre} »`}>
          {options.map((o) => (
            <button key={o.cle} type="button" className="puce" aria-expanded={o.cle === 'jour' ? calendrier : undefined} onClick={o.choisir}>
              {o.libelle}
            </button>
          ))}
        </div>
      ) : null}
      {autres && calendrier ? (
        <input type="date" className="champ-date" aria-label="Choisir un jour" min={minimum} value={choix.jour ?? ''}
          onChange={(e) => { if (e.target.value) prendre({ choix: 'jour', jour: e.target.value }) }} />
      ) : null}
    </>
  )
}

/**
 * R2-030 — une tâche du Reste a son ROND à gauche, comme partout (maquette ecran-bilan.html) : cocher la marque faite
 * (`terminer/`, défaite en décochant) ; faite, ses choix disparaissent et le bilan ne la renvoie plus.
 */
function Reste({ item, choix, onChoisir, jourReport, minimum, aTrancher, faite, onTerminer, enLigne, jourBilan }) {
  return (
    <div className={faite ? 'reste faite' : 'reste'} role="listitem" data-ligne={`${item.type}:${item.id}`}>
      <CaseRonde coche={faite} titre={item.titre} desactivee={!enLigne} onBasculer={(suivant) => onTerminer(item, suivant)} />
      <div>
        <div className="titre">{item.titre}</div>
        <div className="meta">
          {aTrancher && !faite ? <span>À revoir : reportée 3 fois</span> : null}
          {/* R3-021 (C-13) — son échéance est ce jour-là : reportée, elle n'en change pas (le dire, jamais la déplacer en silence) */}
          {!faite && item.echeance && item.echeance === jourBilan ? <span className="alerte">échéance aujourd'hui</span> : null}
          {item.moment === 'soir' ? <span>Ce soir</span> : null}
          {item.projet ? <span data-p={item.projet.couleur}><i className="point" /><span className="projet-nom">{item.projet.nom}</span></span> : null}
        </div>
        {faite ? null : <ChoixReste titre={item.titre} choix={choix} jourReport={jourReport} onChoisir={onChoisir} minimum={minimum} />}
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

function Corps({ donnees, choix, enLigne, aujourdhui, fixer, constat, repondreConstat, mot, setMot, motOuvert, setMotOuvert, lecture, faites, terminer }) {
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
      </div>
      {lecture ? <p className="carte-source">Le bilan d&apos;hier n&apos;est plus modifiable après midi.</p> : null}

      {(donnees.faites ?? []).length > 0 ? (
        <div className="bilan-section">
          <p className="fiche-label">Faites <span className="compte chiffres">{donnees.faites.length}</span></p>
          <div role="list" className="bilan-faites">
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
                choix={choix[item.id] ?? { choix: REPORTER }} onChoisir={(c) => fixer(item.id, c)} jourBilan={donnees.jour}
                faite={faites.has(item.id)} onTerminer={terminer} enLigne={enLigne && !lecture} />
            ))}
            {aTrancher.map((item) => (
              <Reste key={`${item.type}:${item.id}`} item={item} aTrancher jourReport={jourReport} minimum={aujourdhui}
                choix={choix[item.id] ?? { choix: null }} onChoisir={(c) => fixer(item.id, c)} jourBilan={donnees.jour}
                faite={faites.has(item.id)} onTerminer={terminer} enLigne={enLigne && !lecture} />
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
  // L4 → L2 — « Un mot sur ta journée » ne se perd jamais : chaque frappe est gardée sur l'appareil (par compte et par
  // jour de bilan) ; fermer la feuille sans valider puis la rouvrir le même soir le retrouve ; « Valider » l'efface
  const { userId } = useCompteTaches()
  const cleMot = cleBrouillonMot(userId, jour || aujourdhui)
  const [mot, setMotEtat] = useState(() => lireMot(cleMot))
  const setMot = (texte) => { setMotEtat(texte); garderMot(cleMot, texte) }
  const [motOuvert, setMotOuvert] = useState(() => Boolean(lireMot(cleMot)))
  const [constatRepondu, setConstatRepondu] = useState(false)
  const [envoi, setEnvoi] = useState(false)
  const [erreurEnvoi, setErreurEnvoi] = useState('')
  const [faites, setFaites] = useState(() => new Set()) // R2-030 : les restes cochés ici (faites)

  const terminer = async (item, suivant) => {
    if (!enLigne) { annoncer('Possible une fois connecté'); throw new Error('hors ligne') }
    const poser = (fait) => setFaites((avant) => {
      const suite = new Set(avant)
      if (fait) suite.add(item.id)
      else suite.delete(item.id)
      return suite
    })
    poser(suivant) // optimiste : le rond se remplit et les choix partent au toucher
    try {
      if (suivant) await client.terminerTache(item.id)
      else await client.rouvrirTache(item.id)
      annoncer(suivant ? `Fait : ${item.titre}` : `Rouverte : ${item.titre}`)
    } catch (err) {
      poser(!suivant)
      annoncer(frenchError(err))
      throw err
    }
  }

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
    const nommes = Object.entries(choix).filter(([id, c]) => c.choix && c.choix !== REPORTER && !faites.has(Number(id)))
    const corps = {
      jour: donnees.jour,
      choix: [
        ...nommes.map(([id, c]) => ({ id: Number(id), choix: c.choix, ...(c.choix === 'jour' ? { jour: c.jour } : {}) })),
        ...(donnees.a_trancher ?? [])
          .filter((item) => !faites.has(item.id))
          .map((item) => [item.id, choix[item.id]])
          .filter(([, c]) => c?.choix === REPORTER)
          .map(([id]) => ({ id, choix: REPORTER })),
      ],
      le_reste: true,
      reflexion: mot.trim(),
    }
    try {
      const { data } = await client.cloturerJournee(corps)
      garderMot(cleMot, '') // enregistré avec le bilan : le brouillon n'a plus lieu d'être
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
        faites={faites} terminer={terminer}
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
