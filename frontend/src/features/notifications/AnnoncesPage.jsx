import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Megaphone, CheckCircle2, Pin } from 'lucide-react'
import { Card, Badge, Button, Spinner, EmptyState, toast } from '../../ui'
import { formatDateTime } from '../../lib/format'
import notificationsApi from '../../api/notificationsApi'

/**
 * WIR177 — Annonces internes (XKB5 publication + XKB6 accusé de lecture
 * obligatoire).
 *
 * Jusqu'ici les liens de notification pointaient vers `/annonces/<pk>`
 * (inexistant) et « J'ai lu et compris » n'était appelable par aucun écran.
 * Cet écran liste les annonces (`getAnnonces`), permet d'accuser lecture
 * (`accuserLectureAnnonce`, idempotent côté serveur) et supporte `?annonce=`
 * pour ouvrir/mettre en avant une annonce précise (lien de notification ou
 * de relance).
 */
export default function AnnoncesPage() {
  const [searchParams] = useSearchParams()
  const cibleId = searchParams.get('annonce')

  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  // WIR177 — le serveur ne renvoie pas de flag « déjà lu par moi » sur la
  // liste ; l'accusé étant idempotent, on suit juste localement les clics de
  // CETTE session pour désactiver le bouton après confirmation.
  const [luesLocalement, setLuesLocalement] = useState(() => new Set())
  const [busyId, setBusyId] = useState(null)

  const load = () => {
    setLoading(true)
    notificationsApi.getAnnonces({ active: 1 })
      .then((res) => {
        const data = res.data
        setRows(Array.isArray(data) ? data : (data?.results ?? []))
        setError(null)
      })
      .catch(() => setError('Chargement des annonces impossible.'))
      .finally(() => setLoading(false))
  }
  // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount
  useEffect(() => { load() }, [])

  const accuser = async (annonce) => {
    setBusyId(annonce.id)
    try {
      await notificationsApi.accuserLectureAnnonce(annonce.id)
      setLuesLocalement((prev) => new Set(prev).add(annonce.id))
      toast.success('Lecture confirmée.')
    } catch {
      toast.error('Confirmation impossible.')
    } finally {
      setBusyId(null)
    }
  }

  // Annonces épinglées en tête, puis les plus récentes.
  const triees = useMemo(() => (
    [...rows].sort((a, b) => {
      if (a.epinglee !== b.epinglee) return a.epinglee ? -1 : 1
      return (b.date_publication_effective || '').localeCompare(
        a.date_publication_effective || '')
    })
  ), [rows])

  if (loading) {
    return (
      <div className="flex items-center gap-2 p-8 text-muted-foreground">
        <Spinner className="size-4" /> Chargement des annonces…
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4 p-4 sm:p-6">
      <div>
        <h1 className="font-display text-xl font-semibold tracking-tight">
          Annonces
        </h1>
        <p className="mt-0.5 text-sm text-muted-foreground">
          Communications internes ciblées — certaines exigent un accusé de lecture.
        </p>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {triees.length === 0 ? (
        <EmptyState icon={Megaphone} title="Aucune annonce active" />
      ) : (
        <div className="flex flex-col gap-3">
          {triees.map((a) => {
            const estCible = cibleId != null && String(a.id) === String(cibleId)
            const lue = luesLocalement.has(a.id)
            return (
              <Card
                key={a.id}
                id={`annonce-${a.id}`}
                className={`flex flex-col gap-2 p-4 sm:p-5 ${estCible ? 'ring-2 ring-primary' : ''}`}
              >
                <div className="flex flex-wrap items-center gap-2">
                  {a.epinglee && (
                    <Pin size={14} aria-hidden="true" className="text-primary" />
                  )}
                  <h3 className="font-display font-semibold">{a.titre}</h3>
                  {a.lecture_obligatoire && (
                    <Badge tone="warning">Lecture obligatoire</Badge>
                  )}
                </div>
                {a.corps && (
                  <p className="whitespace-pre-wrap text-sm text-muted-foreground">
                    {a.corps}
                  </p>
                )}
                <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
                  <span className="text-xs text-muted-foreground">
                    {a.auteur_username ? `${a.auteur_username} — ` : ''}
                    {formatDateTime(a.date_publication_effective)}
                  </span>
                  {a.lecture_obligatoire && (
                    <Button
                      size="sm"
                      variant={lue ? 'outline' : 'default'}
                      disabled={lue || busyId === a.id}
                      onClick={() => accuser(a)}
                    >
                      <CheckCircle2 size={15} aria-hidden="true" />
                      {lue ? 'Lu et compris' : "J'ai lu et compris"}
                    </Button>
                  )}
                </div>
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}
