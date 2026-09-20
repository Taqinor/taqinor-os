import { Link } from 'react-router-dom'

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

      {!cible && (
        <p className="mt-2 text-xs text-lune-faint" role="status">
          Aucune cible de puissance connue pour ce calepinage : rattachez un
          devis, ou dessinez librement — rien n'est deviné à votre place.
        </p>
      )}

      {/* L'EMPLACEMENT des panneaux des tâches suivantes. `builderApi`,
          `onRecharger` et `lectureSeule` leur sont passés par l'atelier, pour
          qu'aucune n'ait à aller les rechercher elle-même. */}
      {children ? (
        <div className="mt-5 flex flex-wrap items-start gap-4" data-testid="cal-atelier-actions">
          {typeof children === 'function'
            ? children({ calepinageId, contexte, builderApi, lectureSeule, onRecharger })
            : children}
        </div>
      ) : null}
    </div>
  )
}
