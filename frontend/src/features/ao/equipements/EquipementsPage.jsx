import { useCallback, useMemo, useState } from 'react'
import { Boxes, CheckCircle2 } from 'lucide-react'
import aoApi from '../../../api/aoApi'
import useResource from '../../../hooks/useResource'
import { unwrapList } from '../../../api/resource'
import { Badge, Button, Card, EmptyState, Skeleton, toast } from '../../../ui'
import BasculeAssistant from './BasculeAssistant'
import RapportBascule from './RapportBascule'
import { ROLES } from './EquipementsPage.utils'

/* ============================================================================
   AOF180 — Écran « Équipements retenus » (+ bascule + rapport).
   ----------------------------------------------------------------------------
   AOF118 fige un SNAPSHOT du catalogue par équipement (désignation, marque,
   référence constructeur, caractéristiques) : c'est CE snapshot qu'on affiche,
   jamais une relecture du catalogue — sinon un re-seed ferait bouger la
   désignation d'un matériel dans un dossier DÉJÀ DÉPOSÉ.

   AOF119 ajoute le statut d'APPROVISIONNEMENT (lu via `stock.selectors` côté
   serveur) : un produit archivé ou sans prix retenu dans un dossier remonte en
   avertissement, et **l'argument « aucun approvisionnement nouveau » n'est
   affiché QUE si le serveur le confirme** — sur la planche réelle, cette phrase
   était affirmée à la main.

   **AUCUN COÛT.** Ni `prix_achat`, ni marge, ni coût de revient : ni à
   l'écran, ni dans le corps d'une requête (cf. `payloadBascule`).
   ========================================================================== */

const errMsg = (e, fallback) => e?.response?.data?.detail || fallback

const APPRO_TONE = {
  disponible: 'success',
  a_commander: 'info',
  archive: 'warning',
  sans_prix: 'warning',
  rupture: 'danger',
}

function Appro({ appro }) {
  if (!appro) return <span className="text-xs text-muted-foreground">approvisionnement inconnu</span>
  return (
    <Badge tone={APPRO_TONE[appro.statut] ?? 'neutral'}>
      {appro.libelle || appro.statut}
      {appro.delai_jours != null ? ` — ${appro.delai_jours} j` : ''}
    </Badge>
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

export default function EquipementsPage({ projetId }) {
  const [enBascule, setEnBascule] = useState(null)
  const [rapport, setRapport] = useState(null)

  const params = useMemo(() => (projetId ? { projet: projetId } : undefined), [projetId])
  const { data: equipements, loading, error, refetch } = useResource(
    (p) => aoApi.equipements.list(p), params,
    { initialData: [], select: unwrapList, errorMessage: 'Impossible de charger les équipements retenus.' },
  )

  const basculer = useCallback(async (equipement, corps) => {
    const res = await aoApi.equipements.bascule(equipement.id, corps)
    setRapport(res?.data?.rapport ?? res?.data ?? null)
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

  // L'argument commercial n'est disponible que si le SERVEUR l'a confirmé.
  const argumentAppro = equipements.length > 0
    && equipements.every((e) => e.approvisionnement?.aucun_appro_nouveau === true)

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
          Caractéristiques figées au moment du choix (snapshot catalogue) et statut d’approvisionnement.
        </p>
      </div>

      {argumentAppro && (
        <Card className="flex items-start gap-2 border-success/40 bg-success/5 p-3">
          <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-success" aria-hidden="true" />
          <p className="text-sm">
            <span className="font-medium text-success">Aucun approvisionnement nouveau</span>
            {' '}— confirmé par le contrôle d’approvisionnement pour tous les matériels retenus.
          </p>
        </Card>
      )}

      {[...rolesPresents, ...roleInconnus.map((c) => [c, c])].map(([cle, libelle]) => (
        <Card key={cle} className="flex flex-col gap-2 p-4">
          <h2 className="font-display text-base font-semibold">{libelle}</h2>
          <ul className="flex flex-col gap-2">
            {(parRole.get(cle) ?? []).map((e) => (
              <li key={e.id} className="flex flex-wrap items-start justify-between gap-2 rounded-lg border border-border p-2.5">
                <div className="flex min-w-0 flex-col gap-1">
                  <span className="text-sm font-medium">
                    {e.designation || e.produit_designation}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {e.marque || '—'}
                    {e.reference_constructeur ? ` · réf. ${e.reference_constructeur}` : ''}
                    {e.quantite != null ? ` · qté ${e.quantite}` : ''}
                  </span>
                  <Caracteristiques valeurs={e.caracteristiques} />
                </div>
                <div className="flex items-center gap-2">
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

      {rapport && <RapportBascule rapport={rapport} />}

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
