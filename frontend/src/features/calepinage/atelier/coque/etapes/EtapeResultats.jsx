import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import calepinageApi from '../../../../../api/calepinageApi'
import useResource from '../../../../../hooks/useResource'
import { formatNumber } from '../../../../../lib/format'
import { reviserEtOuvrir } from '../../../../ventes/reviserDevis'
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
import { messageResultatIndisponible } from '../../../delaiReseau'
import EtatEcranAtelier from '../../EtatEcranAtelier'
import { useModeExpert } from '../../modeExpert'
import PanneauPertes from '../../PanneauPertes'

/* ============================================================================
   L'ÉTAPE « RÉSULTATS » DU PARCOURS GUIDÉ (maquettes Resultats.dc.html et
   ResultatsIncomplet.dc.html) : pleine largeur du centre de l'atelier, sans carte ni
   panneau de droite. UNE lecture de `GET resultat/` nourrit tout l'écran.
     · résultat complet  : quatre tuiles, « Mois par mois » + « Du soleil au réseau »,
                           pied « Année basse… » + bouton de l'étape suivante (le bouton, seul, dans
                           les deux autres états — ACAL1958) ;
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

/** ACAL1956 (D-ACAL-90) + ACAL1755 (D-ACAL-86, D-ACAL-96) — la production RETENUE PAR LE DEVIS lié (`production_devis` de
    `GET resultat/` : devis envoyé ou accepté ; à défaut `ecart_devis` : tout devis lié dont le PDF imprime la figure) :
    l'étape n'est jamais vide. UN SEUL chiffre quand la simulation de la pose (la plus réaliste) et le devis portent le même ;
    sinon les DEUX, chacun nommé, et — pour un devis que le client a reçu — « Réviser le devis » (le devis envoyé n'est jamais
    modifié : la révision en crée une V2). Rien n'est recalculé ici. `p50` : la simulation de la pose, seulement quand
    elle est complète (un plafond « au plus » n'est pas un chiffre à comparer). */
function ProductionDuDevis({ bloc, p50, incomplet = false }) {
  const navigate = useNavigate()
  const [enCours, setEnCours] = useState(false)
  if (!bloc) return null
  const kwh = typeof bloc.production_annuelle_kwh === 'number' ? bloc.production_annuelle_kwh : null
  const lien = <Link to={`/ventes/devis?devis=${bloc.devis}`}>{bloc.reference || 'voir le devis'}</Link>
  const simule = typeof p50 === 'number' ? p50 : null
  const dit = (n) => `${formatNumber(n, { decimals: 0 })} kWh par an`
  if (kwh != null && simule != null && Math.round(kwh) === Math.round(simule)) {
    return (
      <section className="cal-res-carte flex flex-col gap-1" data-zone="production-devis" data-chiffre="un-seul">
        <p>
          {`Production : ${dit(simule)} — le devis `}
          {lien}
          {' et la simulation de la pose portent le même chiffre.'}
        </p>
      </section>
    )
  }
  // Un devis que le client a reçu (envoyé ou accepté) : jamais touché ; la révision en fait une V2 (même geste que `BoutonDevis`).
  const reviser = async () => {
    if (enCours) return
    setEnCours(true)
    let v2 = null
    try {
      await reviserEtOuvrir({
        devis: { id: bloc.devis, reference: bloc.reference },
        onApres: (nouveau) => { v2 = nouveau },
        navigate: () => { if (v2?.id != null) navigate(`/ventes/devis/${v2.id}/design`) },
      })
    } finally {
      setEnCours(false)
    }
  }
  return (
    <section className="cal-res-carte flex flex-col gap-1" data-zone="production-devis"
      data-chiffre={simule != null && kwh != null ? 'deux' : undefined}>
      <p>
        {kwh != null
          ? `Production retenue par le devis : ${dit(kwh)}`
          : 'Production retenue par le devis : le devis ne la porte pas'}
        {' — '}
        {lien}
      </p>
      <p>
        {simule != null
          ? `Production simulée de la pose : ${dit(simule)}`
          : (incomplet
            ? 'La simulation de la pose est incomplète : elle ne donne qu’un plafond, pas un chiffre à comparer.'
            : 'Simulez la pose pour la comparer à ce chiffre.')}
      </p>
      {simule != null && kwh != null && bloc.statut && (
        <>
          <p className="cal-res-sourdine">
            Le devis envoyé n’est pas modifié : « Réviser le devis » crée une nouvelle version à ajuster sur la simulation de la pose.
          </p>
          <button type="button" className="cal-res-lien" style={{ alignSelf: 'flex-start' }} disabled={enCours}
            onClick={reviser} data-testid="cal-reviser-devis-ecart">
            {enCours ? 'Révision…' : 'Réviser le devis'}
          </button>
        </>
      )}
    </section>
  )
}

/** Le bloc « devis » à comparer : `production_devis` (devis reçu : statut servi), à défaut `ecart_devis` (devis lié, sans statut). */
function blocDuDevis(data) {
  if (data?.production_devis) return data.production_devis
  const ecart = data?.ecart_devis
  if (!ecart || ecart.devis == null) return null
  return { devis: ecart.devis, reference: ecart.reference, statut: null, production_annuelle_kwh: ecart.production_devis_kwh }
}

/** ACAL1912 — des panneaux posés mais raccordés à aucun onduleur : la phrase SERVIE en tête de `avertissements` (le même texte
    que l'Expert), et la production rapportée aux panneaux COMPTÉS — jamais « 13 panneaux » à côté d'un productible calculé
    sur 9. Omis quand `production.hors_chaine.modules` n'est pas un nombre > 0. Rien n'est calculé : `posés − hors chaîne`. */
function PanneauxNonRaccordes({ data }) {
  const horsChaine = data?.production?.hors_chaine?.modules
  const phrase = data?.avertissements?.[0]
  if (!(typeof horsChaine === 'number' && horsChaine > 0) || typeof phrase !== 'string' || !phrase) return null
  const poses = data?.pose?.total_modules
  const kwcPose = data?.pose?.kwc
  const kwcCompte = data?.production?.total?.kwc
  const comptes = typeof poses === 'number' ? poses - horsChaine : null
  const kwc = typeof kwcPose === 'number' && typeof kwcCompte === 'number'
    ? ` (${formatNumber(kwcCompte, { decimals: 2 })} kWc sur ${formatNumber(kwcPose, { decimals: 2 })} kWc)` : ''
  return (
    <section className="cal-res-alerte" data-zone="non-raccordes" role="status">
      <p className="cal-res-alerte-titre">{phrase}</p>
      {comptes !== null && comptes >= 0 && (
        <p className="cal-res-alerte-texte">
          {`Production comptée sur ${formatNumber(comptes, { decimals: 0 })} des ${formatNumber(poses, { decimals: 0 })} panneaux posés${kwc}.`}
        </p>
      )}
    </section>
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
    { select: (r) => r.data, errorMessage: messageResultatIndisponible },
  )
  if (loading || error) {
    return (
      <EtatEcranAtelier id={id} loading={loading} error={error} testIdErreur="cal236-erreur" forme="resultats"
        onRetry={refetch} />
    )
  }
  const perime = data?.simulation_perimee === true
  const simule = data?.simule === true && !perime
  const total = data?.production?.total
  const incomplet = simule && estIncomplet(total)
  const complet = simule && !incomplet && typeof total?.p50_kwh === 'number'
  const ouvert = avanceOuvert ?? expert
  const publiees = reglagesPublies(data?.simulation)
  const voirSources = () => { setSourcesOuvertes(true); setAvanceOuvert(true) }
  // « Voir les étapes » (pertes pas encore comptées) : ouvre « Détail des pertes et réglages » et y amène.
  const voirEtapes = () => {
    setAvanceOuvert(true)
    globalThis.document?.querySelector('[data-zone="avance"]')?.scrollIntoView?.({ block: 'start' })
  }
  const note = publiees.length > 0
    ? <NoteValeursPubliees simulation={data?.simulation} onVoirSources={voirSources} /> : null

  return (
    <div className="cal-res" data-zone="etape-resultats">
      <ProductionDuDevis bloc={blocDuDevis(data)} p50={complet ? total?.p50_kwh : null} incomplet={incomplet} />
      {simule && <PanneauxNonRaccordes data={data} />}
      {!simule && (
        <ResultatAvantSimulation calepinageId={id} data={data} parcours={parcours}
          intervalleMs={intervalleMs} onTermine={refetch} />
      )}
      {incomplet && <ResultatIncomplet calepinageId={id} data={data} parcours={parcours} onVoirEtapes={voirEtapes} />}
      {complet && (
        <>
          <TuilesResultat data={data} />
          <section className="cal-res-milieu">
            <MoisParMois data={data} />
            <DuSoleilAuReseau cascade={data?.cascade} note={note} />
          </section>
        </>
      )}
      {/* ACAL1958 — le bouton de l'étape est là dans les TROIS états (avant simulation, incomplet, complet) ;
          la phrase de durée ne lit que les valeurs d'un résultat complet. */}
      <PiedResultats production={complet ? data?.production : null} action={action} />
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
