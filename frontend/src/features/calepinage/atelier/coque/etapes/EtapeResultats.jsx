import { useEffect, useState } from 'react'
import { panneauxDuModule } from '../../cibleAuModule'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import calepinageApi from '../../../../../api/calepinageApi'
import useResource from '../../../../../hooks/useResource'
import { formatDate, formatNumber } from '../../../../../lib/format'
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
import { memeTaille, phraseTailles, tailleDifferente } from '@roofpro/tailleConception' // T4-X9 — LE prédicat de taille de l'atelier
import { messageResultatIndisponible } from '../../../delaiReseau'
import { estAtelierPompage } from '../../contexteAtelier'
import EtatEcranAtelier from '../../EtatEcranAtelier'
import OutilPosePompage from '../../../commun/OutilPosePompage'
import { useModeExpert } from '../../modeExpert'
import { PARAM_ONGLET } from '../../onglets'
import { premierOngletEtape } from '../../parcoursGuide'
import { publierResultat } from '../../simulationFraiche'
import PanneauPertes from '../../PanneauPertes'
import { useLectureServie } from './panneaux/lectures'

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
/** « Réviser le devis » (devis reçu : jamais touché, la révision en fait une V2 — même geste que `BoutonDevis`). */
function useReviser(devis, { surLaConception = false } = {}) {
  const navigate = useNavigate()
  const [enCours, setEnCours] = useState(false)
  const reviser = async () => {
    if (enCours) return
    setEnCours(true)
    let v2 = null
    try {
      await reviserEtOuvrir({
        devis: { id: devis.devis, reference: devis.reference },
        surLaConception,
        onApres: (nouveau) => { v2 = nouveau },
        navigate: () => { if (v2?.id != null) navigate(`/ventes/devis/${v2.id}/design`) },
      })
    } finally {
      setEnCours(false)
    }
  }
  return [enCours, reviser]
}

function ProductionDuDevis({ bloc, p50, incomplet = false }) {
  const [enCours, reviser] = useReviser(bloc)
  if (!bloc) return null
  const kwh = typeof bloc.production_annuelle_kwh === 'number' ? bloc.production_annuelle_kwh : null
  const lien = <Link to={`/ventes/devis?devis=${bloc.devis}`} className="cal-res-lien-devis">{bloc.reference || 'voir le devis'}</Link>
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

/** Relecture E5 M2 — l'option qu'un devis a retenue, en mots du vendeur. */
const LIBELLE_OPTION = { sans: 'option sans batterie', avec: 'option avec batterie' }
/** Relecture E5 M1 — tant que la conception est servie, la production de la POSE (simulée) porte son nom exact :
    jamais deux productions à l'écran sans que chacune soit nommée. */
const NOM_PRODUCTION_POSE = 'Production simulée de la pose'
/** T4-X7-006 — « Réviser le devis » de la conception : ce que le serveur fait réellement. */
const PHRASE_REVISER_SUR_LA_CONCEPTION = 'Le devis envoyé n’est pas modifié : « Réviser le devis » en crée une '
  + 'nouvelle version, copie de ce devis remise sur la conception du lead si elle a changé depuis. Votre pose n’y entre '
  + 'qu’en resynchronisant cette nouvelle version (étape Documents).'

/** ACAL2015 (C4-E5, D-ACAL-96) — LA conception (`conception` de `GET resultat/`) : UN chiffre de production, celui que le
    moteur unique a rangé ; un devis ENVOYÉ dont l'écart servi (`devis_envoye.ecart_devis`, lignes de ventes) porte la
    production est NOMMÉ (référence, date d'envoi) avec « Réviser le devis » quand ventes le permet. Rien n'est recalculé. */
/** T4-X5-001 — LA taille de la conception : `chiffrage.kwc` servi du design-context (le lecteur de la bande Panneaux et de
    la vue client) ; le nombre de panneaux est celui de `cible` quand il décrit cette même taille, sinon il est tu. */
/** T4-X7-013 — la taille servie AVEC la production, sur le bloc `conception` de `GET resultat/` (même option, même version,
    `puissance_kwc` / `nb_panneaux`), prime : la production et sa taille vont ensemble, jamais une production fraîche à côté
    de la taille d'une lecture plus ancienne. Sans elle (serveur d'avant), le design-context comme avant. */
function tailleDeLaConception(contexte, bloc = null) {
  const propre = typeof bloc?.puissance_kwc === 'number' ? bloc.puissance_kwc : null
  const kwc = contexte?.chiffrage?.kwc
  const valeur = propre ?? (kwc?.etat === 'servi' && typeof kwc.valeur === 'number' ? kwc.valeur : null)
  if (valeur == null) return null
  const cible = contexte?.cible
  const cibleDeCetteTaille = typeof cible?.panneaux === 'number' && memeTaille(cible?.kwc, valeur)
  const servis = propre != null && typeof bloc?.nb_panneaux === 'number' ? bloc.nb_panneaux : null
  const panneaux = servis ?? (cibleDeCetteTaille ? cible.panneaux : null)
  // T4-X3-009 — le compte de la conception nomme SON panneau (« 8 panneaux de 550 W ») quand la cible décrit ce même compte.
  const watt = panneaux != null && cibleDeCetteTaille && cible.panneaux === panneaux ? cible?.panel_watt ?? null : null
  return { kwc: valeur, panneaux, watt }
}

/** T4-X9-008 — la part de la consommation servie pour un calepinage de lead est celle de la CONCEPTION
    (`services/etapes/autoconsommation.py::_publier`) : à une autre taille que la pose, la phrase des deux tailles (prédicat
    et formateur uniques de l'atelier) remplace le chiffre ; `null` sinon (même taille, ou taille inconnue). */
function phraseCouvertureConception(data, contexte) {
  // T4-X7-002 — le serveur a trouvé un écart réel et publié les taux de la POSE simulée (`autre_installation`) : le chiffre
  // est celui de cette pose, de ses énergies ; aucune phrase ne le remplace. `'pose'` (aucun taux de conception) : comme avant.
  if (data?.autoconsommation?.taux_source === 'autre_installation') return null
  const taille = data?.conception
    ? tailleDeLaConception(contexte?.etat === 'ok' ? contexte.donnees : null, data.conception) : null
  return taille && tailleDifferente(taille.kwc, data?.pose?.kwc)
    ? phraseTailles('Part de la consommation', taille.kwc, data.pose.kwc) : null
}

/** Le motif de l'atelier (`affichageErp.ts::raisonSansValeur`) : « X kWc », le nombre de panneaux en plus s'il est servi. */
const ditTaille = ({ panneaux, kwc, watt = null }) => `${formatNumber(kwc, { decimals: 2 })} kWc${
  typeof panneaux === 'number' ? ` (${panneauxDuModule(panneaux, watt)})` : ''}`

function ProductionDeLaConception({ bloc, taille = null, pose = null, simulee = false }) {
  const kwh = typeof bloc.production_annuelle_kwh === 'number' ? bloc.production_annuelle_kwh : null
  const dit = (n) => `${formatNumber(n, { decimals: 0 })} kWh par an`
  // T4-X5-001 — une pose d'une AUTRE taille que la conception : le chiffre de la conception dit sa taille, la pose est
  // renvoyée à sa propre simulation (jamais deux productions de deux tailles sans le dire). Même taille : une ligne.
  const autreTaille = kwh != null && tailleDifferente(taille?.kwc, pose?.kwc)
  const envoye = bloc.devis_envoye
  const lie = bloc.devis_lie ?? null
  const ecarts = envoye?.ecart_devis ?? []
  // Relecture E5 M2 — la production QUE LE DEVIS ENVOYÉ A RANGÉE (`devis_envoye.production_annuelle_kwh`, servie par
  // le serveur), comparée au chiffre AFFICHÉ ici : jamais déduite de l'absence d'une ligne d'écart.
  const duDevis = typeof envoye?.production_annuelle_kwh === 'number' ? envoye.production_annuelle_kwh : null
  const different = duDevis != null && (kwh == null || Math.round(duDevis) !== Math.round(kwh))
  const reviserPossible = ecarts.length === 0 || ecarts.some((e) => e?.reviser_possible)
  const option = different && envoye?.option && envoye.option !== bloc.option ? ` (${LIBELLE_OPTION[envoye.option] ?? envoye.option})` : ''
  const [enCours, reviser] = useReviser(envoye, { surLaConception: true })  // T4-X5-011 : V2 sur la conception
  const lien = envoye ? <Link to={`/ventes/devis?devis=${envoye.devis}`} className="cal-res-lien-devis">{envoye.reference || 'voir le devis'}</Link> : null
  return (
    <section className="cal-res-carte flex flex-col gap-1" data-zone="production-conception"
      data-chiffre={different ? 'deux' : 'un-seul'}>
      {autreTaille ? (
        <>
          <p>
            {`Production de la conception : ${dit(kwh)}, calculée pour la conception du lead : ${ditTaille(taille)} — `
              + `votre pose en compte ${ditTaille({ panneaux: pose.total_modules, kwc: pose.kwc })}.`}
          </p>
          <p className="cal-res-sourdine">
            {simulee ? 'La production simulée de votre pose est ci-dessous.'
              : 'La production de votre pose sera celle de sa simulation.'}
          </p>
        </>
      ) : (
        <p>{kwh != null ? `Production de la conception : ${dit(kwh)}` : 'Production de la conception : non calculée'}</p>
      )}
      {/* D-ACAL-109 / D-ACAL-110 — le matériel désigné à la main : quelle option il sert, l'arrondi au module désigné
          (phrases SERVIES par ventes, `conception.designations`, affichées telles quelles). */}
      {(bloc.designations ?? []).map((phrase) => (
        <p key={phrase} className="cal-res-sourdine" data-zone="designation-conception">{phrase}</p>
      ))}
      {envoye && duDevis == null && (
        <p className="cal-res-sourdine">{'Le devis envoyé '}{lien}{' ne porte pas de production enregistrée.'}</p>
      )}
      {envoye && duDevis != null && !different && (
        <p className="cal-res-sourdine">{'Le devis envoyé '}{lien}{' porte le même chiffre.'}</p>
      )}
      {different && (
        <>
          <p>
            {'Devis '}{lien}{` envoyé${envoye.envoye_le ? ` le ${formatDate(envoye.envoye_le)}` : ''}${option} : ${dit(duDevis)}`}
          </p>
          {/* T4-X7-006 — ce que la révision fait VRAIMENT (`reviser_sur_la_conception`) : une copie du devis, remise sur
              la conception du lead seulement si elle a changé depuis ce devis ; la pose n'y entre qu'en resynchronisant. */}
          <p className="cal-res-sourdine" data-zone="reviser-explique">
            {PHRASE_REVISER_SUR_LA_CONCEPTION}
          </p>
          {reviserPossible && (
            <button type="button" className="cal-res-lien" style={{ alignSelf: 'flex-start' }} disabled={enCours}
              onClick={reviser} data-testid="cal-reviser-devis-ecart">
              {enCours ? 'Révision…' : 'Réviser le devis'}
            </button>
          )}
        </>
      )}
      {/* T4-X7-006 — le devis LIÉ (la V2 brouillon après une révision) qui ne porte pas la pose enregistrée : l'écart
          reste NOMMÉ (servi `conception.devis_lie.a_jour`, prédicat des empreintes), avec le geste qui le comble. */}
      {lie && lie.a_jour === false && lie.devis !== envoye?.devis && (
        <p className="cal-res-sourdine" data-zone="devis-lie-pose">
          {'Le devis lié '}
          <Link to={`/ventes/devis?devis=${lie.devis}`} className="cal-res-lien-devis">{lie.reference || 'voir le devis'}</Link>
          {' ne porte pas votre pose : « Resynchroniser le devis » (étape Documents) le met sur la pose.'}
        </p>
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

/** ACAL1912 — des panneaux posés mais raccordés à aucun onduleur : la phrase SERVIE sur sa clé `panneaux_non_raccordes`
    (revue lot 6, ACAL1623 : jamais un rang de `avertissements`, où la « borne haute » la précède), et la production rapportée
    aux panneaux COMPTÉS — jamais « 13 panneaux » à côté d'un productible calculé sur 9. Omis sans la clé ou quand
    `production.hors_chaine.modules` n'est pas un nombre > 0. Rien n'est calculé : `posés − hors chaîne`. */
function PanneauxNonRaccordes({ data }) {
  const horsChaine = data?.production?.hors_chaine?.modules
  const phrase = data?.panneaux_non_raccordes?.phrase
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

/** T4-X7-005 — la simulation complète donne 0 kWh : l'étape le DIT, avec la cause servie (la `raison` des contrôles
    électriques non conformes de `electrique.verdicts`, phrases du serveur telles quelles) et le geste — l'étape Électrique,
    où se corrigent la longueur des chaînes et l'onduleur. Rien n'est calculé ; sans cause servie, la phrase le dit. */
function ProductionNulle({ data }) {
  const [parametres, setParametres] = useSearchParams()
  const [expert] = useModeExpert()
  const p50 = data?.production?.total?.p50_kwh
  if (!(typeof p50 === 'number' && p50 <= 0)) return null
  const raisons = [...new Set((data?.electrique?.verdicts ?? [])
    .filter((v) => v?.conforme === false && typeof v.raison === 'string' && v.raison)
    .map((v) => v.raison))]
  const onglet = premierOngletEtape('electrique', expert)
  const allerElectrique = () => {
    const suivants = new URLSearchParams(parametres)
    suivants.set(PARAM_ONGLET, onglet)
    setParametres(suivants, { state: { etapeChoisie: true } })
  }
  return (
    <section className="cal-res-alerte" data-zone="production-nulle" role="alert">
      <p className="cal-res-alerte-titre">La simulation de la pose donne 0 kWh par an.</p>
      {raisons.length > 0 ? raisons.map((r) => (
        <p key={r} className="cal-res-alerte-texte">{`Cause : ${r.charAt(0).toUpperCase()}${r.slice(1)}.`}</p>
      )) : (
        <p className="cal-res-alerte-texte">Le calcul ne nomme pas de cause : vérifiez le raccordement des panneaux à l’onduleur.</p>
      )}
      <p className="cal-res-alerte-texte">
        Corrigez la longueur des chaînes ou l’onduleur à l’étape Électrique, puis relancez la simulation.
      </p>
      {onglet && (
        <button type="button" className="cal-res-lien" style={{ alignSelf: 'flex-start' }} onClick={allerElectrique}>
          Aller à l’étape Électrique
        </button>
      )}
    </section>
  )
}

/** T4-U4-012 — la simulation donne un chiffre PLAUSIBLE en apparence (4 panneaux sur un onduleur 5 kW : 1 004 kWh) alors que les
    chaînes, trop courtes, passent sous la plage de travail de l'onduleur quand les panneaux chauffent : le raccordement tel
    que dessiné perd l'essentiel de la production, et seul Documents le disait, parmi d'autres points. Quand le résultat servi
    porte ce verdict non conforme (`vmp_hot_over_mppt_min`, sa `raison` servie), l'étape le DIT en une phrase et renvoie à
    l'étape Électrique. Aucun chiffre calculé ici ; le 0 kWh garde sa propre alerte (`ProductionNulle`).
    Le verdict se juge à la chaleur extrême (70 °C) : seule la perte SERVIE de l'étape « Fenêtre MPPT » de la cascade
    (`cascade.etapes[etape='mppt'].perte_pct`, part de l'énergie qui lui arrive) dit si c'est l'essentiel ou quelques
    heures. ≥ 50 % : « l'essentiel » ; en dessous : « la production des heures les plus chaudes » ; aucun chiffre servi :
    la seule phrase du serveur (`CAUSE_TENSION_CHAUD`), jamais « l'essentiel ». */
function CablagePerdLaProduction({ data }) {
  const [parametres, setParametres] = useSearchParams()
  const [expert] = useModeExpert()
  const p50 = data?.production?.total?.p50_kwh
  if (typeof p50 === 'number' && p50 <= 0) return null
  const verdict = (data?.electrique?.verdicts ?? [])
    .find((v) => v?.code === 'vmp_hot_over_mppt_min' && v.conforme === false && typeof v.raison === 'string' && v.raison)
  if (!verdict) return null
  const onglet = premierOngletEtape('electrique', expert)
  const allerElectrique = () => {
    const suivants = new URLSearchParams(parametres)
    suivants.set(PARAM_ONGLET, onglet)
    setParametres(suivants, { state: { etapeChoisie: true } })
  }
  const perte = (data?.cascade?.etapes ?? []).find((e) => e?.etape === 'mppt')?.perte_pct
  const chiffre = typeof perte === 'number' && perte > 0 ? formatNumber(perte, { decimals: 1 }) : null
  let titre = 'Avec ce raccordement, la production des heures où les panneaux chauffent est perdue.'
  if (chiffre !== null) {
    titre = perte >= 50
      ? `Le raccordement tel qu’il est dessiné fait perdre l’essentiel de la production : ${chiffre} % de l’énergie est retirée par la plage de tension de l’onduleur.`
      : `Le raccordement tel qu’il est dessiné fait perdre la production des heures les plus chaudes : ${chiffre} % de l’énergie est retirée par la plage de tension de l’onduleur.`
  }
  return (
    <section className="cal-res-alerte" data-zone="cablage-perd-la-production" role="alert">
      <p className="cal-res-alerte-titre">{titre}</p>
      <p className="cal-res-alerte-texte">{`Cause : ${verdict.raison.charAt(0).toUpperCase()}${verdict.raison.slice(1)}.`}</p>
      {onglet && (
        <button type="button" className="cal-res-lien" style={{ alignSelf: 'flex-start' }} onClick={allerElectrique}>
          Aller à l’étape Électrique
        </button>
      )}
    </section>
  )
}

/** ACAL1987 (D-ACAL-90 renversée : « Simulation must start by itself ») — la simulation PARTIE SEULE à l'enregistrement
    d'une pose complète (`simulation_automatique` de `GET resultat/`). En file ou en cours : « Simulation en cours… », sans
    bouton ; `GET resultat/` est relu en silence toutes les `intervalleMs` jusqu'à la fin, puis `onTermine` relit l'écran
    (le résultat s'affiche sans clic). La relecture d'attente ne passe pas par l'état de chargement de l'écran. */
function SimulationEnCours({ calepinageId, intervalleMs, onTermine }) {
  useEffect(() => {
    let fini = false
    const minuteur = setInterval(() => {
      calepinageApi.calepinages.resultat(calepinageId)
        .then((r) => {
          if (fini || r?.data?.simulation_automatique?.en_cours === true) return
          fini = true
          clearInterval(minuteur)
          onTermine?.()
        })
        .catch(() => { fini = true; clearInterval(minuteur); onTermine?.() })
    }, intervalleMs)
    return () => { fini = true; clearInterval(minuteur) }
  }, [calepinageId, intervalleMs, onTermine])
  return (
    <section className="cal-res-carte flex flex-col gap-1" data-zone="simulation-en-cours" role="status">
      <h2 className="cal-res-titre">Simulation en cours…</h2>
      <p className="cal-res-sourdine m-0">
        La pose enregistrée est complète : la simulation est partie d’elle-même. Le résultat s’affichera ici.
      </p>
    </section>
  )
}

/** ACAL1987 — la dernière pose enregistrée était INCOMPLÈTE : la simulation n'est pas partie, et l'écran dit ce qui
    manque (phrases servies `simulation_automatique.manquants[].motif`, jamais réécrites). Omis sans liste servie. */
function SimulationEnAttente({ manquants }) {
  const motifs = (manquants ?? []).map((m) => m?.motif).filter((m) => typeof m === 'string' && m)
  if (motifs.length === 0) return null
  return (
    <section className="cal-res-carte flex flex-col gap-1" data-zone="simulation-manque" role="status">
      <p className="m-0">Il manque {motifs.length > 1 ? 'ceci' : 'une chose'} pour que la simulation parte seule :</p>
      <ul className="m-0">
        {motifs.map((motif) => <li key={motif}>{motif}</li>)}
      </ul>
    </section>
  )
}

export default function EtapeResultats({
  calepinageId = null, lectureSeule = false, parcours = null, action = null, intervalleMs = 2000, contexte: contexteAtelier = null,
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
  // T4-X8-013 — le résultat lu ici est celui que reprennent le résumé de la feuille « Avancé » et le Total du constructeur.
  useEffect(() => { if (data) publierResultat(id, data) }, [id, data])
  // T4-X5-001 — la taille de la conception (lecture partagée du design-context, jamais un second appel en vol).
  const contexte = useLectureServie('contexte', id, { actif: data?.conception != null })
  if (loading || error) {
    return (
      <EtatEcranAtelier id={id} loading={loading} error={error} testIdErreur="cal236-erreur" forme="resultats"
        onRetry={refetch} />
    )
  }
  // ACAL1268 (D-ACAL-66 = outil_pose) — un lead de pompage n'a ni production de réseau, ni couverture, ni économies, ni
  // onduleur : l'étape dit la taille de la pose servie et renvoie au devis agricole ; le pied et son bouton restent.
  if (estAtelierPompage(contexteAtelier)) {
    const pose = data?.pose
    const taille = typeof pose?.total_modules === 'number' && pose.total_modules > 0
      ? ` Pose : ${formatNumber(pose.total_modules, { decimals: 0 })} panneaux${typeof pose.kwc === 'number' ? ` · ${formatNumber(pose.kwc, { decimals: 2 })} kWc` : ''}.` : ''
    return (
      <div className="cal-res" data-zone="etape-resultats">
        <OutilPosePompage contexte={contexteAtelier}
          phrase={`Lead de pompage : l’atelier pose les panneaux, sans économies ni énergie du réseau.${taille}`} />
        <PiedResultats production={null} action={action} />
      </div>
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
  const auto = data?.simulation_automatique
  const enCours = !simule && auto?.en_cours === true

  return (
    <div className="cal-res" data-zone="etape-resultats">
      {data?.conception
        ? <ProductionDeLaConception bloc={data.conception} pose={data?.pose} simulee={complet}
          taille={tailleDeLaConception(contexte.etat === 'ok' ? contexte.donnees : null, data.conception)} />
        : <ProductionDuDevis bloc={blocDuDevis(data)} p50={complet ? total?.p50_kwh : null} incomplet={incomplet} />}
      {simule && <PanneauxNonRaccordes data={data} />}
      {complet && <ProductionNulle data={data} />}
      {complet && <CablagePerdLaProduction data={data} />}
      {enCours && <SimulationEnCours calepinageId={id} intervalleMs={intervalleMs} onTermine={refetch} />}
      {!simule && !enCours && <SimulationEnAttente manquants={auto?.manquants} />}
      {!simule && !enCours && (
        <ResultatAvantSimulation calepinageId={id} data={data} parcours={parcours}
          intervalleMs={intervalleMs} onTermine={refetch} />
      )}
      {incomplet && (
        <ResultatIncomplet calepinageId={id} data={data} parcours={parcours} onVoirEtapes={voirEtapes}
          nomProduction={data?.conception ? NOM_PRODUCTION_POSE : null} />
      )}
      {complet && (
        <>
          <TuilesResultat data={data} nomProduction={data?.conception ? NOM_PRODUCTION_POSE : null}
            phraseCouverture={phraseCouvertureConception(data, contexte)} />
          <section className="cal-res-milieu">
            <MoisParMois data={data} nomProduction={data?.conception ? NOM_PRODUCTION_POSE : null} />
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
