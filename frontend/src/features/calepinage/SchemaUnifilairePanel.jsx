import { useParams } from 'react-router-dom'
import { AlertCircle } from 'lucide-react'
import calepinageApi from '../../api/calepinageApi'
import useResource from '../../hooks/useResource'
import { renderTrustedSvg } from '../../lib/trustedSvg'
import { Card, Spinner } from '../../ui'

/* ============================================================================
   CAL195 — LE SCHÉMA UNIFILAIRE, DANS LE MODULE.
   ----------------------------------------------------------------------------
   Le schéma existait déjà — mais seulement à l'intérieur du PDF de devis. Un
   calepinage sans devis n'en avait aucun, et personne ne pouvait le regarder
   avant d'avoir chiffré.

   CE PANNEAU NE DESSINE RIEN. Le SVG est composé PAR LE SERVEUR (le MÊME
   moteur `core.electrique` que le devis, à travers la porte
   `apps.ventes.selectors.schema_unifilaire_svg`) : deux surfaces ne peuvent
   donc pas montrer deux schémas qui se contredisent. L'écran l'insère tel
   quel et n'ajoute pas un trait.

   FICHE INCOMPLÈTE ⇒ PAS DE SCHÉMA, et on le DIT. `svg: null` n'est jamais
   affiché comme un cadre vide : les libellés français du serveur
   (`manquantes`, `bloquants`) sont rendus TELS QUELS — l'écran ne reformule
   aucun motif et n'en invente aucun. Même discipline que PVFCH-ANNEXE côté
   devis : un schéma d'aspect officiel bâti sur des caractéristiques devinées
   est un défaut invisible.
   ========================================================================== */

const LISTES = [
  { cle: 'manquantes', titre: 'Fiche technique incomplète' },
  { cle: 'bloquants', titre: 'Conception non conforme' },
]

function Motifs({ donnees }) {
  const blocs = LISTES
    .map(({ cle, titre }) => ({ titre, cle, lignes: donnees?.[cle] || [] }))
    .filter((bloc) => bloc.lignes.length > 0)
  if (!blocs.length) {
    return (
      <p className="text-sm text-muted-foreground" data-testid="cal195-sans-motif">
        Aucun schéma pour cette conception.
      </p>
    )
  }
  return blocs.map((bloc) => (
    <div key={bloc.cle} className="flex flex-col gap-1" data-testid={`cal195-${bloc.cle}`}>
      <div className="flex items-center gap-2 text-sm font-medium">
        <AlertCircle size={15} aria-hidden="true" />
        {bloc.titre}
      </div>
      <ul className="list-disc pl-5 text-sm text-muted-foreground">
        {bloc.lignes.map((ligne) => <li key={ligne}>{ligne}</li>)}
      </ul>
    </div>
  ))
}

export default function SchemaUnifilairePanel({ calepinageId }) {
  const { id: idRoute } = useParams()
  const id = calepinageId ?? idRoute

  const { data, loading, error } = useResource(
    () => calepinageApi.calepinages.schemaUnifilaire(id), id,
    { select: (r) => r.data, errorMessage: 'Schéma unifilaire indisponible.' },
  )

  const balisage = renderTrustedSvg(data?.svg)

  if (loading) return <Spinner />
  if (error) {
    return (
      <p className="text-sm text-destructive" data-testid="cal195-erreur">{error}</p>
    )
  }

  return (
    <Card className="flex flex-col gap-3 p-4" data-testid="cal195-panneau">
      <h2 className="text-base font-semibold">Schéma unifilaire</h2>
      {balisage
        ? (
          <div
            data-testid="cal195-svg"
            /* Le SVG vient du serveur, jamais d'une saisie. Il passe malgré
               tout par `renderTrustedSvg` (VX120, défense en profondeur) :
               un balisage capable d'exécuter du code n'est PAS inséré — on
               montre alors les motifs plutôt qu'un cadre piégé. */
            dangerouslySetInnerHTML={balisage}
          />
        )
        : <Motifs donnees={data} />}
    </Card>
  )
}
