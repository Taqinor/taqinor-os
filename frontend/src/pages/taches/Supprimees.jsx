import { useCallback, useEffect, useState } from 'react'

import CoquilleTaches from '../../features/taches/coquille/CoquilleTaches'
import { frenchError } from '../../lib/frenchError'
import {
  annulerGeste, classerErreur, listerGestes, listerSupprimees, restaurerProjet, restaurerTache,
} from '../../api/tachesApi'
import { proposerAnnuler } from '../../features/taches/lib/gestes'
import { accord } from '../../features/taches/lib/textes'

/* ============================================================================
   TCH87 — « Supprimées récemment » (`/taches/supprimees`) : « Supprimées depuis moins de 30 jours. »
   Un projet = UNE ligne « « {projet} » et ses {n} tâches » + Restaurer (409 `nom_pris` : « Un projet actif
   porte déjà ce nom. », dit sous la ligne) ; une tâche seule = sa ligne + Restaurer (« Restaurée dans À trier ·
   Annuler » si son projet n'est plus là) ; vide : « Rien de supprimé ». Dessous, « Derniers gestes » (7 jours) :
   le message du geste + Annuler (« Déjà annulé » quand c'est fait ; « Annulé, sauf {n} modifiée(s) depuis. »).
   La liste ne se vide jamais sur une lecture en échec. Maquettes : supprimees.html, supprimees-gestes.html.
   ========================================================================== */

const sansCle = (objet, cle) => Object.fromEntries(Object.entries(objet).filter(([k]) => k !== cle))
const PHRASE_NOM_PRIS = 'Un projet actif porte déjà ce nom.'

export default function Supprimees() {
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
      setGestes(derniers.data?.results ?? [])
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
    <CoquilleTaches ecran="supprimees" titre="Supprimées récemment">
      <p className="apercu-source">Supprimées depuis moins de 30 jours.</p>
      {erreur ? <p className="erreur-champ" role="alert">{erreur}</p> : null}

      <section className="section" aria-label="Supprimées récemment">
        <div className="liste" role="list">
          {projets.map((ligne) => (
            <div key={`p${ligne.projet.id}`} className="atrier-ligne" role="listitem" data-p={ligne.projet.couleur}>
              <div className="atrier-titre">
                <span className="titre">{`« ${ligne.projet.nom} » et ses ${accord(ligne.taches_nb, 'tâche')}`}</span>
              </div>
              <div className="puces">
                <button type="button" className="puce" aria-label={`Restaurer « ${ligne.projet.nom} »`} onClick={() => restaurerLeProjet(ligne)}>Restaurer</button>
              </div>
              {erreurs[`p${ligne.projet.id}`] ? <p className="erreur-champ" role="alert">{erreurs[`p${ligne.projet.id}`]}</p> : null}
            </div>
          ))}
          {taches.map((ligne) => (
            <div key={`t${ligne.item.id}`} className="atrier-ligne" role="listitem">
              <div className="atrier-titre"><span className="titre">{ligne.item.titre}</span></div>
              <div className="puces">
                <button type="button" className="puce" aria-label={`Restaurer « ${ligne.item.titre} »`} onClick={() => restaurerLaTache(ligne)}>Restaurer</button>
              </div>
              {erreurs[`t${ligne.item.id}`] ? <p className="erreur-champ" role="alert">{erreurs[`t${ligne.item.id}`]}</p> : null}
            </div>
          ))}
        </div>
        {vide ? <div className="vide-etat"><p className="vide-phrase">Rien de supprimé</p></div> : null}
      </section>

      {gestes.length > 0 ? (
        <section className="section" aria-label="Derniers gestes">
          <h2 className="section-titre"><span>Derniers gestes</span></h2>
          <div className="liste" role="list">
            {gestes.map((geste) => (
              <div key={geste.id} className="atrier-ligne" role="listitem">
                <div className="atrier-titre"><span className="titre">{geste.message}</span></div>
                <div className="puces">
                  {geste.annule_le || !geste.annulable ? (
                    <span className="atrier-repere">Déjà annulé</span>
                  ) : (
                    <button type="button" className="puce" aria-label={`Annuler : ${geste.message}`} onClick={() => annuler(geste)}>Annuler</button>
                  )}
                </div>
                {erreurs[`g${geste.id}`] ? <p className="erreur-champ" role="alert">{erreurs[`g${geste.id}`]}</p> : null}
              </div>
            ))}
          </div>
        </section>
      ) : null}
    </CoquilleTaches>
  )
}
