import { useCallback, useMemo, useState } from 'react'
import { Boxes } from 'lucide-react'
import aoApi from '../../../api/aoApi'
import useResource from '../../../hooks/useResource'
import { unwrapList } from '../../../api/resource'
import { Badge, Button, Card, EmptyState, Skeleton, toast } from '../../../ui'
import BasculeAssistant from './BasculeAssistant'
import RapportBascule from './RapportBascule'
import { ROLES, GRAVITE_TONE, GRAVITE_LABEL } from './EquipementsPage.utils'

/* ============================================================================
   AOF180 — Écran « Équipements retenus » (+ bascule + rapport).
   ----------------------------------------------------------------------------
   AOF118 fige un SNAPSHOT du catalogue par équipement (désignation, marque,
   référence constructeur, caractéristiques) : c'est CE snapshot qu'on affiche,
   jamais une relecture du catalogue — sinon un re-seed ferait bouger la
   désignation d'un matériel dans un dossier DÉJÀ DÉPOSÉ. Le repli
   `e.produit_designation` a donc été retiré : il n'existe dans aucun
   sérialiseur, et il aurait rouvert par la fenêtre la relecture catalogue que
   le snapshot ferme par la porte.

   AOF119 ajoute le contrôle d'APPROVISIONNEMENT. Sa forme réelle
   (`fabrique/approvisionnement.py`) est un CONSTAT par équipement :
   `{gravite, motif}` avec `gravite ∈ {info, avertissement, blocage}` — pas un
   `statut`/`libelle`/`delai_jours`, qui n'existent nulle part côté serveur.

   **L'ARGUMENT « aucun approvisionnement nouveau » N'EST PAS RENDU ICI**, et
   c'est délibéré. `argument_aucun_approvisionnement()` est une décision de
   DOSSIER : elle n'est vraie que si AUCUN équipement du dossier ne la
   contredit, et son texte est une CONSTANTE (`PHRASE_ARGUMENT`) que le module
   interdit de reformuler. Une liste PAGINÉE ne peut pas la prouver — un
   `every()` sur la page 1 affirmerait l'argument alors que la batterie
   archivée est en page 2. C'est exactement la phrase « écrite à la main » que
   AOF119 existe pour empêcher ; elle appartient à la génération de la pièce,
   pas à cet écran.

   **AUCUN COÛT.** Ni `prix_achat`, ni marge, ni coût de revient : ni à
   l'écran, ni dans le corps d'une requête (cf. `payloadBascule`).
   ========================================================================== */

const errMsg = (e, fallback) => e?.response?.data?.detail || fallback

function Appro({ appro }) {
  const gravite = appro?.gravite
  if (!gravite) {
    return <span className="text-xs text-muted-foreground">approvisionnement non contrôlé</span>
  }
  return (
    <div className="flex max-w-64 flex-col items-end gap-0.5">
      <Badge tone={GRAVITE_TONE[gravite] ?? 'neutral'}>
        {GRAVITE_LABEL[gravite] ?? gravite}
      </Badge>
      {appro.motif ? (
        <span className="text-right text-xs text-muted-foreground">{appro.motif}</span>
      ) : null}
    </div>
  )
}

function Caracteristiques({ valeurs }) {
  const entrees = Object.entries(valeurs || {})
  if (!entrees.length) return null
  return (
    <dl className="flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-muted-foreground">
      {entrees.map(([k, v]) => (
        <div key={k} className="flex gap-1">
          <dt>{k} :</dt>
          <dd className="text-foreground">{String(v)}</dd>
        </div>
      ))}
    </dl>
  )
}

export default function EquipementsPage({ affaireId }) {
  const [enBascule, setEnBascule] = useState(null)
  const [rapport, setRapport] = useState(null)
  const [motifRapport, setMotifRapport] = useState('')

  // `?appel_offre=` — le nom du CHAMP DU MODÈLE et la convention de toutes les
  // ressources filles du routeur AO. `?projet=` était un filtre inconnu : le
  // ViewSet l'ignore en silence et renvoie TOUTE la société.
  const params = useMemo(
    () => (affaireId ? { appel_offre: affaireId } : undefined), [affaireId],
  )
  const { data: equipements, loading, error, refetch } = useResource(
    (p) => aoApi.equipements.list(p), params,
    { initialData: [], select: unwrapList, errorMessage: 'Impossible de charger les équipements retenus.' },
  )

  const basculer = useCallback(async (equipement, corps) => {
    const res = await aoApi.equipements.bascule(equipement.id, corps)
    setRapport(res?.data?.rapport ?? res?.data ?? null)
    setMotifRapport(corps?.motif ?? '')
    toast.success('Bascule effectuée — vérifiez les emplacements suspects.')
    refetch()
  }, [refetch])

  const parRole = useMemo(() => {
    const carte = new Map()
    for (const e of equipements) {
      const r = e.role || 'autre'
      if (!carte.has(r)) carte.set(r, [])
      carte.get(r).push(e)
    }
    return carte
  }, [equipements])

  if (loading && equipements.length === 0) {
    return <div className="flex flex-col gap-3"><Skeleton className="h-8 w-64" /><Skeleton className="h-40 w-full" /></div>
  }
  if (error) {
    return <EmptyState icon={Boxes} title="Équipements indisponibles" description={error} />
  }
  if (equipements.length === 0) {
    return (
      <EmptyState
        icon={Boxes}
        title="Aucun équipement retenu"
        description="Aucun matériel n’a encore été retenu pour cette affaire."
      />
    )
  }

  const rolesPresents = ROLES.filter(([cle]) => parRole.has(cle))
  const roleInconnus = [...parRole.keys()].filter((c) => !ROLES.some(([r]) => r === c))

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="font-display text-xl font-semibold tracking-tight">Équipements retenus</h1>
        <p className="mt-0.5 text-sm text-muted-foreground">
          Caractéristiques figées au moment du choix (snapshot catalogue) et contrôle
          d’approvisionnement.
        </p>
      </div>

      {[...rolesPresents, ...roleInconnus.map((c) => [c, c])].map(([cle, libelle]) => (
        <Card key={cle} className="flex flex-col gap-2 p-4">
          <h2 className="font-display text-base font-semibold">{libelle}</h2>
          <ul className="flex flex-col gap-2">
            {(parRole.get(cle) ?? []).map((e) => (
              <li key={e.id} className="flex flex-wrap items-start justify-between gap-2 rounded-lg border border-border p-2.5">
                <div className="flex min-w-0 flex-col gap-1">
                  <span className="text-sm font-medium">{e.designation}</span>
                  <span className="text-xs text-muted-foreground">
                    {e.marque || '—'}
                    {e.reference_constructeur ? ` · réf. ${e.reference_constructeur}` : ''}
                    {e.quantite != null ? ` · qté ${e.quantite} ${e.unite || ''}`.trimEnd() : ''}
                  </span>
                  <Caracteristiques valeurs={e.caracteristiques} />
                </div>
                <div className="flex items-start gap-2">
                  <Appro appro={e.approvisionnement} />
                  <Button
                    size="sm" variant="outline"
                    onClick={() => setEnBascule(e)}
                  >
                    Basculer
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        </Card>
      ))}

      {rapport && <RapportBascule rapport={rapport} motif={motifRapport} />}

      {enBascule && (
        <BasculeAssistant
          equipement={enBascule}
          onFermer={() => setEnBascule(null)}
          onBasculer={async (equipement, corps) => {
            try {
              await basculer(equipement, corps)
            } catch (e) {
              toast.error(errMsg(e, 'Bascule refusée.'))
              throw e
            }
          }}
        />
      )}
    </div>
  )
}
