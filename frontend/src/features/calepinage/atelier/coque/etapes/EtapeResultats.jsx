import { useState } from 'react'
import { useParams } from 'react-router-dom'
import calepinageApi from '../../../../../api/calepinageApi'
import useResource from '../../../../../hooks/useResource'
import '../../../../../styles/calepinage/54-etape-resultats.css'
import { estIncomplet } from '../../../production/BandeauProvenanceProduction.helpers'
import { DuSoleilAuReseau } from '../../../production/CartePostesPertes'
import DiagrammePertes from '../../../production/DiagrammePertes'
import { MoisParMois } from '../../../production/GraphiqueMensuel'
import { NoteValeursPubliees } from '../../../production/LigneValeursPubliees'
import { reglagesPublies } from '../../../production/LigneValeursPubliees.helpers'
import PiedResultats from '../../../production/PiedResultats'
import ResultatAvantSimulation from '../../../production/ResultatAvantSimulation'
import ResultatIncomplet from '../../../production/ResultatIncomplet'
import TuilesResultat from '../../../production/TuilesResultat'
import EtatEcranAtelier from '../../EtatEcranAtelier'
import { useModeExpert } from '../../modeExpert'
import PanneauPertes from '../../PanneauPertes'

/* ============================================================================
   L'ÉTAPE « RÉSULTATS » DU PARCOURS GUIDÉ (maquettes Resultats.dc.html et
   ResultatsIncomplet.dc.html) : pleine largeur du centre de l'atelier, sans carte ni
   panneau de droite. UNE lecture de `GET resultat/` nourrit tout l'écran.
     · résultat complet  : quatre tuiles, « Mois par mois » + « Du soleil au réseau »,
                           pied « Année basse… » + bouton de l'étape suivante ;
     · résultat incomplet : carte « au plus » + « Pour un résultat complet » (ACAL700) ;
     · jamais simulé / périmé : ResultatAvantSimulation (carte sombre + bouton de calcul,
                           « Pour un résultat complet », « Ce qui est déjà sûr »).
   Rien n'est calculé ici : chaque figure est servie ou son bloc est omis. L'ancien contenu
   (diagramme de pertes détaillé, édition d'un poste de perte, réglages utilisés, bouton de
   calcul) reste TOUT dans « Détail des pertes et réglages » (ouvert d'office en expert) ;
   les onglets Production, etc. restent dans le rail en expert. `action` = {libelle, onClick}
   de l'étape suivante, relayée par le shell (à défaut, l'URL ouvre l'étape Documents).
   ========================================================================== */

/** ACAL396 — le diagramme ET l'édition d'un poste ; chaque poste enregistré remonte le
    diagramme (nouvelle `key`) qui relit `GET resultat/` : le bandeau « périmée » apparaît. */
function PertesAvance({ calepinageId, lectureSeule, onEnregistre, sourcesOuvertes, onSources }) {
  const [relecture, setRelecture] = useState(0)
  return (
    <div data-testid="cal-pertes-unifie" className="flex flex-col gap-4">
      <DiagrammePertes key={relecture} calepinageId={calepinageId}
        sourcesOuvertes={sourcesOuvertes} onSources={onSources} />
      <PanneauPertes calepinageId={calepinageId} lectureSeule={lectureSeule}
        onEnregistre={() => { setRelecture((n) => n + 1); onEnregistre?.() }} />
    </div>
  )
}

export default function EtapeResultats({
  calepinageId = null, lectureSeule = false, parcours = null, action = null, intervalleMs = 2000,
}) {
  const { id: idRoute } = useParams()
  const id = calepinageId ?? idRoute
  const [expert] = useModeExpert()
  const [avanceOuvert, setAvanceOuvert] = useState(null) // null = suit le mode ; sinon le choix de l'utilisateur
  const [sourcesOuvertes, setSourcesOuvertes] = useState(false)
  const { data, loading, error, refetch } = useResource(
    () => calepinageApi.calepinages.resultat(id), id,
    { select: (r) => r.data, errorMessage: 'Résultats indisponibles.' },
  )
  if (loading || error) {
    return <EtatEcranAtelier id={id} loading={loading} error={error} testIdErreur="cal236-erreur" />
  }
  const perime = data?.simulation_perimee === true
  const simule = data?.simule === true && !perime
  const total = data?.production?.total
  const incomplet = simule && estIncomplet(total)
  const complet = simule && !incomplet && typeof total?.p50_kwh === 'number'
  const ouvert = avanceOuvert ?? expert
  const publiees = reglagesPublies(data?.simulation)
  const voirSources = () => { setSourcesOuvertes(true); setAvanceOuvert(true) }
  const note = publiees.length > 0
    ? <NoteValeursPubliees simulation={data?.simulation} onVoirSources={voirSources} /> : null

  return (
    <div className="cal-res" data-zone="etape-resultats">
      {!simule && (
        <ResultatAvantSimulation calepinageId={id} data={data} parcours={parcours}
          intervalleMs={intervalleMs} onTermine={refetch} />
      )}
      {incomplet && <ResultatIncomplet calepinageId={id} data={data} parcours={parcours} />}
      {complet && (
        <>
          <TuilesResultat data={data} />
          <section className="cal-res-milieu">
            <MoisParMois data={data} />
            <DuSoleilAuReseau cascade={data?.cascade} note={note} />
          </section>
          <PiedResultats production={data?.production} action={action} />
        </>
      )}
      <details open={ouvert} onToggle={(e) => setAvanceOuvert(e.currentTarget.open)}
        className="cal-res-carte" data-zone="avance">
        <summary className="cursor-pointer font-medium">Détail des pertes et réglages</summary>
        {ouvert && (
          <div className="mt-3 flex flex-col gap-4">
            <PertesAvance calepinageId={id} lectureSeule={lectureSeule} onEnregistre={refetch}
              sourcesOuvertes={sourcesOuvertes} onSources={setSourcesOuvertes} />
          </div>
        )}
      </details>
    </div>
  )
}
