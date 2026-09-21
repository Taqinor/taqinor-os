import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import calepinageApi from '../../api/calepinageApi'
/* CALX27 — le droit d'ÉCRITURE métier du module. Même code que la garde
   serveur de l'action (`PeutGererCalepinage`, `views/verrou.py`) : l'écran ne
   propose pas un geste que l'API refusera. */
import { useHasPermission } from '../../hooks/useHasPermission'
/* CAL17 (moitié écran) — la FICHE de l'agrégat de détail. Le serveur publiait
   vingt et une clés que personne ne lisait. */
import FicheCalepinage from './FicheCalepinage'
// CAL38 — la SORTIE vers le devis (générer / resynchroniser). Elle se pose ici,
// dans l'emplacement enregistré par CAL37 : l'atelier n'est pas rouvert.
import BoutonDevis from './BoutonDevis'
/* CAL101 — les raccourcis clavier de l'atelier et leur aide-mémoire (« ? »).
   Ils se posent ICI, dans l'emplacement enregistré par CAL37 : un composant de
   raccourcis monté nulle part serait exactement l'oubli du 03/08/2026 — et un
   raccourci qui n'est branché sur aucun écran ne rend jamais personne rapide.
   Les gestes concrets (outil tracé, obstacle, zone…) viendront de `builderApi`
   au fur et à mesure que l'atelier les expose : tant qu'un geste n'existe pas,
   son raccourci ne mange PAS la frappe (comportement déclaré du composant). */
import RaccourcisAtelier from './RaccourcisAtelier'
/* CAL79 — le remplissage branché sur la porte moteur CAL22/CAL23, avec son
   RÉGIME DE PREUVE affiché honnêtement. Il se pose ICI plutôt que sur une
   route à lui : un panneau de remplissage sans la géométrie de l'atelier
   n'aurait aucune surface à remplir — ce serait un écran mort. L'entrée du
   moteur et l'application du plan viennent de `builderApi` ; tant que
   l'atelier ne les expose pas, le panneau le DIT (« dessinez d'abord un pan de
   toit ») au lieu de faire semblant. */
import RemplissageProuve from './RemplissageProuve'
/* CAL70 — les allées/passages de maintenance : le moteur sait DÉJÀ chercher
   la plus grande allée à compte constant (`allee_gratuite.py`, AOF50) et la
   publie dans `suggestions[]` de `moteur/calculer` ; ce panneau se pose ICI
   (emplacement CAL37) plutôt que sur une route à lui, pour la même raison
   que CAL79 : sans la géométrie de l'atelier, il n'y aurait rien à analyser. */
import PanneauAllees from './PanneauAllees'
// CAL188 — le badge « calepinage périmé », lu du MÊME champ serveur.
import BadgePerime from './BadgePerime'
/* CALX1 — LE RAIL D'ONGLETS. Treize écrans du module étaient servis par le
   routeur (`module.config.jsx`) sans qu'aucun lien du dépôt n'y mène : livrés
   et introuvables. Ils se parcourent désormais depuis ICI, par `?onglet=<cle>`,
   et leurs routes profondes restent servies comme liens profonds. Ajouter un
   panneau = UNE ligne en fin de `atelier/onglets.js` ; ce fichier-ci n'est plus
   rouvert (décision D-CALX 3 et 13). */
import Rail from './atelier/Rail'

/* ============================================================================
   CAL37 — L'UNIQUE EMPLACEMENT DES PANNEAUX DE L'ATELIER, mode `calepinage`.
   ----------------------------------------------------------------------------
   POURQUOI UN SEUL ENDROIT : `pages/ventes/ToitureDesign.jsx` est l'écran le
   plus chargé du dépôt (quatre modes sur le MÊME builder). Si chaque tâche du
   Groupe CAL y ajoutait son bouton, elles se marcheraient toutes dessus — et
   deux lanes file-disjointes qui rouvrent le même fichier, c'est un conflit de
   fold garanti. Les tâches suivantes (CAL38 « Générer le devis », CAL180
   l'export image) posent donc leur panneau ICI, et n'ont jamais à rouvrir
   l'atelier.

   CE COMPOSANT N'ENREGISTRE RIEN et ne calcule RIEN : il AFFICHE ce que le
   serveur a déjà servi (contrat `calepinage_design_context.json`) et délègue
   toute écriture à l'atelier ou aux boutons qui portent leur propre appel. La
   cible en particulier n'est JAMAIS devinée : `cible` vaut `null` quand le
   calepinage n'a ni devis lié ni facture exploitable, et l'écran écrit alors
   « non renseignée » — jamais une puissance fabriquée (règle fondateur « zéro
   chiffre inventé »).
   ========================================================================== */

/** Une grandeur du serveur, ou le tiret — jamais un zéro de remplacement. */
function valeur(brut, suffixe = '') {
  if (brut === null || brut === undefined || brut === '') return '—'
  return `${brut}${suffixe}`
}

/**
 * CALX27 — le refus SERVEUR, mot pour mot. Rien n'est reformulé : le seul
 * texte écrit ici est celui du cas où le serveur n'a RIEN dit (panne réseau),
 * et il le dit au lieu d'inventer un motif.
 */
function messageRefus(erreur) {
  const data = erreur?.response?.data
  if (typeof data === 'string' && data.trim()) return data.trim()
  if (data && typeof data === 'object') {
    if (typeof data.detail === 'string' && data.detail.trim()) return data.detail.trim()
    const premier = Object.values(data).find((v) => v)
    if (premier) return Array.isArray(premier) ? premier.join(' ') : String(premier)
  }
  return 'Le serveur n’a pas répondu. Réessayez dans un instant.'
}

/* ============================================================================
   CALX27 — LE BANDEAU DE LECTURE SEULE, ET SA SORTIE.
   ----------------------------------------------------------------------------
   CONSTAT : `POST deverrouiller/` (CAL207, `views/verrou.py` + le service qui
   déduit le verrou du chatter) était construit et testé, mais n'avait AUCUN
   consommateur — l'atelier disait « lecture seule » sans offrir la moindre
   sortie, et la seule façon de reprendre la main était d'aller écrire dans la
   base. Une capacité sans affordance n'existe pas pour l'utilisateur.

   DEUX GARDES, LES MÊMES QUE LE SERVEUR :
     * le bouton n'apparaît QUE dans l'état lecture seule — déverrouiller une
       conception déjà ouverte n'a aucun sens ;
     * et QUE avec `calepinage_gerer`, le code EXACT de `PeutGererCalepinage` :
       proposer un geste que l'API refusera par 403 est un piège.

   LA CONFIRMATION NOMME LA CONSÉQUENCE. Le verrou vient du devis envoyé :
   rouvrir l'écriture rend ce devis À REJOUER (il faudra le resynchroniser pour
   qu'il redise la même conception). Le statut du devis n'est JAMAIS touché ici
   (règle #4) — c'est bien pour cela qu'il faut l'annoncer.
   ========================================================================== */
function BandeauVerrou({ calepinageId, onDeverrouille }) {
  /* Le droit est lu ICI, dans le composant qui n'existe QU'EN LECTURE SEULE :
     l'atelier ouvert ne consulte donc aucun droit pour un geste qu'il ne
     propose pas — et le rail (CALX1) continue de se rendre sans store. */
  const peutGerer = useHasPermission('calepinage_gerer')
  const [confirme, setConfirme] = useState(false)
  const [enCours, setEnCours] = useState(false)
  const [refus, setRefus] = useState(null)

  const deverrouiller = async () => {
    if (enCours) return
    setRefus(null)
    setEnCours(true)
    let res = null
    try {
      res = await calepinageApi.calepinages.deverrouiller(calepinageId)
    } catch (erreur) {
      setEnCours(false)
      setRefus(messageRefus(erreur))
      return
    }
    setEnCours(false)
    /* On CROIT le serveur, pas le clic : s'il maintient le verrou, l'écran ne
       fait pas semblant d'avoir rouvert l'écriture. */
    if (res?.data?.verrouille === true) {
      setRefus('Le verrou est toujours posé sur cette conception.')
      return
    }
    setConfirme(false)
    await onDeverrouille?.()
  }

  return (
    <div className="mt-4 border border-brass-400/40 p-3" data-testid="cal-bandeau-lecture-seule">
      <p className="tech-label text-brass-300">Conception figée</p>
      <p className="mt-1 text-sm text-lune-soft">
        Cet atelier est en lecture seule : le devis lié est parti chez le client.
        Les gestes d’écriture sont suspendus tant que le verrou est posé.
      </p>

      {peutGerer && !confirme && (
        <button
          type="button"
          onClick={() => setConfirme(true)}
          data-testid="cal-deverrouiller"
          className="mt-3 inline-flex items-center gap-2 border border-brass-400 px-5 py-3 text-base font-bold text-brass-300"
        >
          Déverrouiller
        </button>
      )}

      {peutGerer && confirme && (
        <div className="mt-3" data-testid="cal-deverrouiller-confirmation">
          <p className="text-sm text-alert-300" role="alert">
            Déverrouiller rouvre l’écriture sur cette conception : le devis lié
            devient à rejouer — il faudra le resynchroniser pour qu’il redise la
            même conception. Le geste est tracé au journal du calepinage.
          </p>
          <div className="mt-3 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={deverrouiller}
              disabled={enCours}
              data-testid="cal-deverrouiller-confirmer"
              className="inline-flex items-center gap-2 border border-brass-400 px-5 py-3 text-base font-bold text-brass-300 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {enCours ? 'Déverrouillage…' : 'Confirmer le déverrouillage'}
            </button>
            <button
              type="button"
              onClick={() => { setConfirme(false); setRefus(null) }}
              disabled={enCours}
              data-testid="cal-deverrouiller-annuler"
              className="inline-flex items-center gap-2 px-5 py-3 text-base font-semibold text-lune-faint disabled:cursor-not-allowed disabled:opacity-60"
            >
              Annuler
            </button>
          </div>
        </div>
      )}

      {/* Le refus NOMME le geste qui a échoué, et rend le message du serveur
          tel quel — jamais un « non enregistré » anonyme. */}
      {refus && (
        <div className="mt-3 border border-alert-300/40 p-3" data-testid="cal-deverrouiller-refus">
          <p className="tech-label text-alert-300">Déverrouillage</p>
          <p className="mt-1 text-sm text-alert-300" role="alert">{refus}</p>
        </div>
      )}
    </div>
  )
}

export default function AtelierPanneaux({
  calepinageId, contexte, builderApi, lectureSeule = false,
  onRecharger, children,
}) {
  const cible = contexte?.cible ?? null
  const calepinage = contexte?.calepinage ?? null

  /* CALX27 — le déverrouillage REND la main tout de suite : les panneaux d'écriture
     réapparaissent sans rechargement complet de l'atelier. L'état du serveur
     est quand même relu derrière (`relire`, `onRecharger`) — ce drapeau n'est
     qu'un raccourci d'affichage, jamais une seconde vérité. */
  const [deverrouille, setDeverrouille] = useState(false)
  const enLectureSeule = lectureSeule && !deverrouille

  /* UNE SEULE LECTURE DE L'AGRÉGAT (CAL17), partagée. La fiche et le bouton
     devis parlent de la MÊME vérité : deux lectures, ce serait deux états le
     jour où l'un des deux serait périmé. `relecture` est incrémentée par les
     gestes qui changent cet état (resynchronisation, import de contour) —
     jamais un `setState` posé dans le corps de l'effet (react-hooks v7). */
  const [detail, setDetail] = useState(null)
  const [relecture, setRelecture] = useState(0)
  useEffect(() => {
    if (!calepinageId) return undefined
    let annule = false
    // `Promise.resolve` : un client qui ne rendrait pas de promesse ne doit pas
    // faire exploser l'effet — l'écran n'affiche alors simplement pas la fiche.
    Promise.resolve(calepinageApi.calepinages.get(calepinageId))
      .then((res) => { if (!annule) setDetail(res?.data ?? null) })
      .catch(() => { if (!annule) setDetail(null) })
    return () => { annule = true }
  }, [calepinageId, relecture])
  const relire = () => setRelecture((n) => n + 1)

  return (
    <div className="cine-card mt-6 p-6" data-testid="cal-atelier-panneaux">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-2">
        <span className="flex items-baseline gap-2">
          <p className="tech-label rule-brass text-brass-300">Calepinage</p>
          {/* CAL188 — l'en-tête de l'atelier, lu du MÊME champ serveur que la
              fiche devis et la liste (CAL189), jamais recalculé ici. */}
          <BadgePerime layoutStale={detail?.layout_stale}
            layoutNbPanneaux={detail?.layout_nb_panneaux} />
        </span>
        {/* Le comparatif des variantes est CONTEXTUEL à ce calepinage : il
            s'ouvre depuis son atelier, jamais depuis une entrée de menu
            permanente qui n'aurait aucun calepinage à désigner. */}
        <Link
          to={`/calepinage/${calepinageId}/variantes`}
          data-testid="cal-lien-variantes"
          className="text-sm font-semibold text-brass-300 underline"
        >
          Comparer les variantes
        </Link>
        {/* CAL53 — la photo de site (CAL52) se cale depuis ici : un item de
            menu permanent n'aurait aucun calepinage à désigner. */}
        <Link
          to={`/calepinage/${calepinageId}/photos`}
          data-testid="cal-lien-photos-calage"
          className="text-sm font-semibold text-brass-300 underline"
        >
          Photos du site
        </Link>
      </div>

      {/* CALX27 — LE BANDEAU DE LECTURE SEULE ET SA SORTIE. Il ne s'affiche
          que dans cet état ; le bouton qu'il porte n'existe qu'avec le droit
          de gérer. Après déverrouillage, le bandeau disparaît et les panneaux
          d'écriture reviennent — sans rechargement complet. */}
      {enLectureSeule && (
        <BandeauVerrou
          calepinageId={calepinageId}
          onDeverrouille={async () => {
            setDeverrouille(true)
            relire()
            await onRecharger?.()
          }}
        />
      )}

      {/* LA CIBLE, TELLE QUE LE SERVEUR LA SERT. `source` dit d'où elle vient
          (devis lié, factures du lead) : sans elle, personne ne peut savoir si
          le chiffre affiché engage un devis ou n'est qu'une estimation. */}
      <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-4">
        <div>
          <dd className="fig text-lg text-white" data-testid="cal-cible-panneaux">
            {cible ? valeur(cible.panneaux) : 'non renseignée'}
          </dd>
          <dt className="tech-label mt-0.5 text-lune-faint">Cible — panneaux</dt>
        </div>
        <div>
          <dd className="fig text-lg text-white">{cible ? valeur(cible.kwc, ' kWc') : '—'}</dd>
          <dt className="tech-label mt-0.5 text-lune-faint">Cible — puissance</dt>
        </div>
        <div>
          <dd className="fig text-lg text-white">{valeur(cible?.source)}</dd>
          <dt className="tech-label mt-0.5 text-lune-faint">Source de la cible</dt>
        </div>
        <div>
          <dd className="fig text-lg text-white">{valeur(calepinage?.statut)}</dd>
          <dt className="tech-label mt-0.5 text-lune-faint">Statut</dt>
        </div>
      </dl>

      {/* CAL17 — TOUT ce que le serveur publie sur ce calepinage, lu et rendu.
          Silencieuse tant que l'agrégat n'est pas arrivé : jamais une fiche de
          tirets qui aurait l'air de dire « rien à afficher ». */}
      <FicheCalepinage detail={detail} />

      {!cible && (
        <p className="mt-2 text-xs text-lune-faint" role="status">
          Aucune cible de puissance connue pour ce calepinage : rattachez un
          devis, ou dessinez librement — rien n'est deviné à votre place.
        </p>
      )}

      {/* CALX1 — LE RAIL D'ONGLETS, sous la fiche : les treize panneaux
          contextuels de ce calepinage, à un clic. Sans `?onglet=` aucun
          panneau n'est ouvert — l'atelier rend ce qu'il rendait hier. */}
      <Rail calepinageId={calepinageId} />

      {/* L'EMPLACEMENT des panneaux des tâches suivantes. `builderApi`,
          `onRecharger` et `lectureSeule` leur sont passés par l'atelier, pour
          qu'aucune n'ait à aller les rechercher elle-même. */}
      {/* CAL79 — le remplissage prouvé, et son régime annoncé sans flatterie. */}
      <RemplissageProuve
        entree={builderApi?.entreeMoteur ?? null}
        onAppliquer={builderApi?.appliquerPlan ?? null}
        lectureSeule={enLectureSeule}
      />

      {/* CAL70 — les allées de maintenance et le plateau gratuit du moteur. */}
      <PanneauAllees entree={builderApi?.entreeMoteur ?? null} lectureSeule={enLectureSeule} />

      {/* CAL101 — l'aide-mémoire des raccourcis, à portée de « ? ». */}
      <div className="mt-4">
        <RaccourcisAtelier actions={builderApi?.raccourcis ?? {}} />
      </div>

      <div className="mt-5 flex flex-wrap items-start gap-4" data-testid="cal-atelier-actions">
        <BoutonDevis
          calepinageId={calepinageId}
          detail={detail}
          lectureSeule={enLectureSeule}
          onRecharger={onRecharger}
          onRelire={relire}
        />
        {/* SOLMVP15 — le bouton « Reprendre le contour de l'affaire » (CAL242)
            était posé ici. Son endpoint est parti avec l'app d'appels d'offres,
            qui sort du produit : il n'y a plus d'affaire dont reprendre le
            contour. Le contour de l'atelier n'a pas changé d'un champ
            (`roof_layout.outline`, v2) et le tracé sur carte reste la voie de
            le poser. */}
        {typeof children === 'function'
          ? children({ calepinageId, contexte, builderApi, lectureSeule: enLectureSeule, onRecharger })
          : children}
      </div>
    </div>
  )
}
