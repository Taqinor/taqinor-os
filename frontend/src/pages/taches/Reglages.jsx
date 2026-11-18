import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { lireReglages, modifierReglages } from '../../api/tachesApi'
import { frenchError } from '../../lib/frenchError'
import CoquilleTaches from '../../features/taches/coquille/CoquilleTaches'
import { configurerGestes } from '../../features/taches/lib/gestes'
import ListeRubriques, { Avance, MesDonnees } from '../../features/taches/reglages/Rubriques'
import { naviguerApresFeuille } from '../../features/taches/ui/FeuilleACrans'
import ViePrivee from '../../features/taches/reglages/ViePrivee'

/* ============================================================================
   TCH108 — Écran « Réglages » (routes /taches/reglages et /taches/reglages/:rubrique ; atteignable
   par le menu ⋯ de la coquille). Rubriques construites : `vie-privee`, `donnees`, `avance`.
   Lecture : `GET reglages/` (`contract_samples/reglages.json`) ; chaque interrupteur envoie
   `PATCH reglages/` (liste blanche) et adopte la valeur rendue ; l'erreur du serveur s'affiche
   sous le réglage. Un échec de lecture dit « Pas à jour » et garde l'écran.
   Textes : textes.md §2.14, §6. Maquettes : reglages*.html.
   ========================================================================== */

const messageDe = (err, champ) => {
  const brut = err?.response?.data?.[champ]
  return Array.isArray(brut) && brut.length > 0 ? String(brut[0]) : frenchError(err, 'Réessaie dans un instant.')
}

function Contenu({ rubrique, reglages, erreur, basculer, navigate }) {
  if (rubrique === 'vie-privee') {
    return (
      <ViePrivee
        allume={Boolean(reglages?.comprendre_mon_rythme)}
        onBasculer={(valeur) => basculer('comprendre_mon_rythme', valeur)}
        onMesDonnees={() => navigate('/taches/reglages/donnees')}
        erreur={erreur.comprendre_mon_rythme}
      />
    )
  }
  if (rubrique === 'donnees') return <MesDonnees onEfface={() => naviguerApresFeuille(navigate, '/taches/aujourdhui')} />
  if (rubrique === 'avance') {
    return (
      <Avance
        sansDelai={Boolean(reglages?.messages_sans_delai)}
        onSansDelai={(valeur) => basculer('messages_sans_delai', valeur)}
        erreur={erreur.messages_sans_delai}
      />
    )
  }
  return null
}

export default function Reglages() {
  const { rubrique } = useParams()
  const navigate = useNavigate()
  const [reglages, setReglages] = useState(null)
  const [echec, setEchec] = useState(false)
  const [erreur, setErreur] = useState({})
  const [essai, setEssai] = useState(0)

  useEffect(() => {
    let actif = true
    lireReglages()
      .then((reponse) => {
        if (!actif) return
        setReglages(reponse.data)
        setEchec(false)
        configurerGestes({ sansDelai: Boolean(reponse.data.messages_sans_delai) })
      })
      .catch(() => { if (actif) setEchec(true) })
    return () => { actif = false }
  }, [essai])

  const basculer = async (champ, valeur) => {
    setErreur((anciennes) => ({ ...anciennes, [champ]: '' }))
    try {
      await modifierReglages({ [champ]: valeur })
      setReglages((actuels) => ({ ...actuels, [champ]: valeur }))
      if (champ === 'messages_sans_delai') configurerGestes({ sansDelai: valeur })
    } catch (err) {
      setErreur((anciennes) => ({ ...anciennes, [champ]: messageDe(err, champ) }))
    }
  }

  return (
    <CoquilleTaches ecran="reglages" titre="Réglages">
      {echec ? (
        <div className="bandeau" role="status">
          <span className="bandeau-texte"><span className="bandeau-titre">Pas à jour</span></span>
          <button type="button" className="bouton lien" onClick={() => setEssai((n) => n + 1)}>Réessayer</button>
        </div>
      ) : null}
      <div className="es-reglages-grille">
        <ListeRubriques courante={rubrique} onOuvrir={(cle) => navigate(`/taches/reglages/${cle}`)} />
        <div>
          <Contenu rubrique={rubrique} reglages={reglages} erreur={erreur} basculer={basculer} navigate={navigate} />
        </div>
      </div>
    </CoquilleTaches>
  )
}
