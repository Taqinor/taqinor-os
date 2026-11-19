import { useCallback, useEffect, useState } from 'react'

import CoquilleTaches from '../../features/taches/coquille/CoquilleTaches'
import { frenchError } from '../../lib/frenchError'
import {
  annulerGeste, classerErreur, listerGestes, listerSupprimees, restaurerProjet, restaurerTache,
} from '../../api/tachesApi'
import { proposerAnnuler } from '../../features/taches/lib/gestes'
import ChargementTardif from '../../features/taches/ui/ChargementTardif'
import { ABR_JOURS, accord, aujourdhuiIso, heure, jourCourt } from '../../features/taches/lib/textes'

/* ============================================================================
   TCH87 — « Supprimées récemment » (`/taches/supprimees`) : « Supprimées depuis moins de 30 jours. »
   Un projet = UNE ligne « « {projet} » et ses {n} tâches » + Restaurer (409 `nom_pris` : « Un projet actif
   porte déjà ce nom. », dit sous la ligne) ; une tâche seule = sa ligne + Restaurer (« Restaurée dans À trier ·
   Annuler » si son projet n'est plus là) ; vide : « Rien de supprimé ». Dessous, « Derniers gestes » (7 jours) :
   le message du geste, le titre de la tâche touchée (R2-125, servi par `gestes/`) + Annuler (« Déjà annulé » quand c'est
   fait ; « Annulé, sauf {n} modifiée(s) depuis. »). Un squelette tient la place pendant la première lecture.
   La liste ne se vide jamais sur une lecture en échec. Maquettes : supprimees.html, supprimees-gestes.html.
   Passe visuelle n° 63 — les lignes sont des lignes de tâche (`.ligne.es-supprimee`, case vide pour l'alignement) :
   méta « Restaurer » · « {projet ou Sans projet} » · jour de suppression (`deleted_at`, servi à l'heure du Maroc) ;
   un geste = heure (le jour même) ou jour · message · « Annuler » en lien.
   ========================================================================== */

const sansCle = (objet, cle) => Object.fromEntries(Object.entries(objet).filter(([k]) => k !== cle))
const PHRASE_NOM_PRIS = 'Un projet actif porte déjà ce nom.'

/** « Faite · Appeler le fournisseur » : le message du geste puis la tâche qu'il a touchée (nulle : le message seul). */
const phraseGeste = (geste) => (geste.titre ? `${geste.message} · ${geste.titre}` : geste.message)

/** Le jour servi d'un instant ISO (« lun. 16/11 », « aujourd'hui ») : jamais l'horloge ni le fuseau du navigateur. */
const jourServi = (instant, aujourdhui) => jourCourt(String(instant ?? '').slice(0, 10), aujourdhui)

/** supprimees-gestes.html : « 14:10 » le jour même, sinon « lun. 23 ». */
function quandGeste(instant, aujourdhui) {
  const iso = String(instant ?? '')
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso)
  if (!m) return ''
  if (iso.slice(0, 10) === aujourdhui) return heure(iso.slice(11, 16))
  return `${ABR_JOURS[new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3]))).getUTCDay()]} ${Number(m[3])}`
}

export default function Supprimees({ aujourdhui = aujourdhuiIso() }) {
  const [projets, setProjets] = useState([])
  const [taches, setTaches] = useState([])
  const [gestes, setGestes] = useState([])
  const [charge, setCharge] = useState(false)
  const [erreur, setErreur] = useState('')
  const [erreurs, setErreurs] = useState({})

  const lire = useCallback(() => Promise.all([listerSupprimees(), listerGestes()])
    .then(([supprimees, derniers]) => {
      setProjets(supprimees.data?.projets ?? [])
      setTaches(supprimees.data?.taches ?? [])
      setGestes((derniers.data ?? {}).results ?? [])
      setErreur('')
      setCharge(true)
    })
    .catch((err) => setErreur(frenchError(err))), [])

  useEffect(() => { lire() }, [lire])

  const restaurerLeProjet = async (ligne) => {
    const { projet } = ligne
    try {
      await restaurerProjet(projet.id)
      setProjets((liste) => liste.filter((l) => l.projet.id !== projet.id))
      setErreurs((e) => sansCle(e, `p${projet.id}`))
      proposerAnnuler({ message: `« ${projet.nom} » restauré` })
    } catch (err) {
      const classee = classerErreur(err)
      setErreurs((e) => ({ ...e, [`p${projet.id}`]: classee.code === 'nom_pris' ? PHRASE_NOM_PRIS : frenchError(err) }))
    }
  }

  const restaurerLaTache = async (ligne) => {
    const { item } = ligne
    try {
      const { data } = await restaurerTache(item.id)
      setTaches((liste) => liste.filter((l) => l.item.id !== item.id))
      const sansProjet = item.projet && data?.tache?.projet == null
      proposerAnnuler({ message: sansProjet ? 'Restaurée dans À trier' : 'Restaurée' })
    } catch (err) {
      setErreurs((e) => ({ ...e, [`t${item.id}`]: frenchError(err) }))
    }
  }

  const annuler = async (geste) => {
    try {
      const { data } = await annulerGeste(geste.id)
      const conflits = data?.conflits?.length ?? 0
      setGestes((liste) => liste.map((g) => (g.id === geste.id ? { ...g, annulable: false } : g)))
      proposerAnnuler({ message: conflits > 0 ? `Annulé, sauf ${conflits} modifiée${conflits > 1 ? 's' : ''} depuis.` : 'Annulé.' })
      await lire()
    } catch (err) {
      setErreurs((e) => ({ ...e, [`g${geste.id}`]: frenchError(err) }))
    }
  }

  const vide = charge && projets.length === 0 && taches.length === 0

  return (
    <CoquilleTaches ecran="supprimees" titre="Supprimées et derniers gestes">
      <p className="es-sous">Supprimées depuis moins de 30 jours.</p>
      {erreur ? <p className="erreur-champ" role="alert">{erreur}</p> : null}
      <ChargementTardif actif={!charge && !erreur} />

      <section className="section es-supprimees" aria-label="Supprimées récemment">
        <div className="liste" role="list">
          {projets.map((ligne) => (
            <div key={`p${ligne.projet.id}`} className="ligne es-supprimee" role="listitem">
              <span className="case" aria-hidden="true" />
              <div className="ligne-corps">
                <div className="titre">{`« ${ligne.projet.nom} » et ses ${accord(ligne.taches_nb, 'tâche')}`}</div>
                <div className="meta">
                  <button type="button" className="es-action" aria-label={`Restaurer « ${ligne.projet.nom} »`} onClick={() => restaurerLeProjet(ligne)}>Restaurer</button>
                  <span className="chiffres">{jourServi(ligne.deleted_at, aujourdhui)}</span>
                </div>
                {erreurs[`p${ligne.projet.id}`] ? <p className="erreur-champ" role="alert">{erreurs[`p${ligne.projet.id}`]}</p> : null}
              </div>
              <div className="ligne-fin" />
            </div>
          ))}
          {taches.map((ligne) => (
            <div key={`t${ligne.item.id}`} className="ligne es-supprimee" role="listitem">
              <span className="case" aria-hidden="true" />
              <div className="ligne-corps">
                <div className="titre">{ligne.item.titre}</div>
                <div className="meta">
                  <button type="button" className="es-action" aria-label={`Restaurer « ${ligne.item.titre} »`} onClick={() => restaurerLaTache(ligne)}>Restaurer</button>
                  {ligne.item.projet ? (
                    <span data-p={ligne.item.projet.couleur}><i className="point" /><span className="projet-nom">{ligne.item.projet.nom}</span></span>
                  ) : <span>Sans projet</span>}
                  <span className="chiffres">{jourServi(ligne.deleted_at, aujourdhui)}</span>
                </div>
                {erreurs[`t${ligne.item.id}`] ? <p className="erreur-champ" role="alert">{erreurs[`t${ligne.item.id}`]}</p> : null}
              </div>
              <div className="ligne-fin" />
            </div>
          ))}
        </div>
        {vide ? <div className="vide-etat"><p className="vide-phrase">Rien de supprimé</p></div> : null}
      </section>

      {gestes.length > 0 ? (
        <section className="section" aria-label="Derniers gestes">
          <h2 className="section-titre"><span>Derniers gestes</span></h2>
          <ul className="es-gestes">
            {gestes.map((geste) => (
              <li key={geste.id} className="es-geste">
                <time className="chiffres" dateTime={geste.created_at}>{quandGeste(geste.created_at, aujourdhui)}</time>
                <span className="msg">{geste.titre ? <>{geste.message}{' · '}<span className="titre-geste">{geste.titre}</span></> : geste.message}</span>
                {geste.annule_le || !geste.annulable ? (
                  <span className="deja">Déjà annulé</span>
                ) : (
                  <button type="button" className="bouton lien" aria-label={`Annuler : ${phraseGeste(geste)}`} onClick={() => annuler(geste)}>Annuler</button>
                )}
                {erreurs[`g${geste.id}`] ? <p className="erreur-champ" role="alert">{erreurs[`g${geste.id}`]}</p> : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </CoquilleTaches>
  )
}
