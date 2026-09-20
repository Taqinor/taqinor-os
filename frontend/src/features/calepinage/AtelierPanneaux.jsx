import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import calepinageApi from '../../api/calepinageApi'
/* CAL17 (moitié écran) — la FICHE de l'agrégat de détail. Le serveur publiait
   vingt et une clés que personne ne lisait. */
import FicheCalepinage from './FicheCalepinage'
// CAL38 — la SORTIE vers le devis (générer / resynchroniser). Elle se pose ici,
// dans l'emplacement enregistré par CAL37 : l'atelier n'est pas rouvert.
import BoutonDevis from './BoutonDevis'
/* CAL242 — le sens AO → calepinage de l'import de contour (CAL240). Son jumeau
   (« Reprendre le tracé 3D », CAL241) est DÉJÀ monté sur l'écran de toiture
   d'une affaire ; celui-ci restait écrit, testé, et monté NULLE PART — c'est-à-
   dire exactement l'oubli du 03/08/2026 que sa propre docstring dit combattre.
   Sa place est ici : son en-tête déclare « Posé dans l'atelier en mode
   calepinage ».

   CE QU'IL NE PEUT PAS ENCORE FAIRE, et qu'il faut dire : l'endpoint
   `importer-contour-ao` (CAL240) n'est pas encore servi par
   `apps/calepinage/urls.py`. Tant qu'il ne l'est pas, le bouton remonte le
   refus du serveur SOUS lui (c'est son comportement déclaré) au lieu d'importer
   quoi que ce soit ; il devient vivant le jour où CAL240 atterrit, sans qu'une
   ligne d'écran ne change. Ni `affaireId` ni `toitureId` ne lui sont passés :
   l'atelier ne connaît AUCUNE des deux (le contexte de conception ne publie pas
   l'affaire du calepinage) et les INVENTER ferait importer le contour d'un
   autre chantier. Le serveur résout donc la source depuis le calepinage
   lui-même — c'est lui qui tranche. */
import { BoutonReprendreContourAffaire } from './BoutonsContourAO'
/* CAL101 — les raccourcis clavier de l'atelier et leur aide-mémoire (« ? »).
   Ils se posent ICI, dans l'emplacement enregistré par CAL37 : un composant de
   raccourcis monté nulle part serait exactement l'oubli du 03/08/2026 — et un
   raccourci qui n'est branché sur aucun écran ne rend jamais personne rapide.
   Les gestes concrets (outil tracé, obstacle, zone…) viendront de `builderApi`
   au fur et à mesure que l'atelier les expose : tant qu'un geste n'existe pas,
   son raccourci ne mange PAS la frappe (comportement déclaré du composant). */
import RaccourcisAtelier from './RaccourcisAtelier'

/* ============================================================================
   CAL37 — L'UNIQUE EMPLACEMENT DES PANNEAUX DE L'ATELIER, mode `calepinage`.
   ----------------------------------------------------------------------------
   POURQUOI UN SEUL ENDROIT : `pages/ventes/ToitureDesign.jsx` est l'écran le
   plus chargé du dépôt (quatre modes sur le MÊME builder). Si chaque tâche du
   Groupe CAL y ajoutait son bouton, elles se marcheraient toutes dessus — et
   deux lanes file-disjointes qui rouvrent le même fichier, c'est un conflit de
   fold garanti. Les tâches suivantes (CAL38 « Générer le devis », CAL180
   l'export image, CAL242 la reprise du contour d'affaire) posent donc leur
   panneau ICI, et n'ont jamais à rouvrir l'atelier.

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

export default function AtelierPanneaux({
  calepinageId, contexte, builderApi, lectureSeule = false,
  onRecharger, children,
}) {
  const cible = contexte?.cible ?? null
  const calepinage = contexte?.calepinage ?? null

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
        <p className="tech-label rule-brass text-brass-300">Calepinage</p>
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
      </div>

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

      {/* L'EMPLACEMENT des panneaux des tâches suivantes. `builderApi`,
          `onRecharger` et `lectureSeule` leur sont passés par l'atelier, pour
          qu'aucune n'ait à aller les rechercher elle-même. */}
      {/* CAL101 — l'aide-mémoire des raccourcis, à portée de « ? ». */}
      <div className="mt-4">
        <RaccourcisAtelier actions={builderApi?.raccourcis ?? {}} />
      </div>

      <div className="mt-5 flex flex-wrap items-start gap-4" data-testid="cal-atelier-actions">
        <BoutonDevis
          calepinageId={calepinageId}
          detail={detail}
          lectureSeule={lectureSeule}
          onRecharger={onRecharger}
          onRelire={relire}
        />
        {/* Une conception FIGÉE ne reçoit aucun contour : l'import est une
            écriture, il disparaît en lecture seule comme toutes les autres. */}
        {!lectureSeule && (
          <BoutonReprendreContourAffaire
            calepinageId={calepinageId}
            onImporte={onRecharger}
          />
        )}
        {typeof children === 'function'
          ? children({ calepinageId, contexte, builderApi, lectureSeule, onRecharger })
          : children}
      </div>
    </div>
  )
}
