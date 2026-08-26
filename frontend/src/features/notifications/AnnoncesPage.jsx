import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Megaphone, CheckCircle2, Pin } from 'lucide-react'
import {
  Badge, Button, Card, CardContent, EmptyState, Spinner, toast,
} from '../../ui'
import { PageHeader } from '../../ui/PageHeader'
import useDocumentTitle from '../../hooks/useDocumentTitle'
import notificationsApi from '../../api/notificationsApi'

/* WIR177 — Écran DESTINATAIRE des annonces internes (XKB5/XKB6).

   Le backend savait publier une annonce ciblée, relancer les retardataires et
   enregistrer un accusé de lecture… mais AUCUN écran ne les recevait : les
   deux notifications pointaient sur `/annonces/<pk>`, une route qui n'a jamais
   existé (404 garanti), et `accuserLectureAnnonce` n'était appelable de nulle
   part — donc le rapport de conformité XKB6 restait vide pour toujours.

   Cet écran :
     - liste les annonces ACTIVES de la société (`getAnnonces({ active: 1 })`,
       publiées et non expirées — le queryset serveur fait le filtrage, cf.
       `AnnonceViewSet.get_queryset`) ;
     - accepte `?annonce=<pk>` (le motif que les deux `link=` de
       `apps/notifications/services.py` posent désormais) : l'annonce visée est
       remontée en tête et mise en évidence ;
     - expose « J'ai lu et compris » sur les annonces à lecture obligatoire.
       Le POST est IDEMPOTENT côté serveur (`acknowledge_annonce`) : un second
       clic ne crée pas de doublon — l'UI le reflète en gardant simplement la
       confirmation affichée.

   Épinglées d'abord, puis les plus récentes. Aucun droit d'écriture ici :
   créer/publier/consulter la conformité restent dans Paramètres (admin). */

function dateFr(value) {
  if (!value) return ''
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleDateString('fr-FR', {
    day: '2-digit', month: 'long', year: 'numeric',
  })
}

// Épinglées d'abord ; à égalité, la plus récemment publiée d'abord. L'annonce
// ciblée par `?annonce=` passe avant tout le reste.
function trier(annonces, cibleId) {
  const rang = (a) => {
    if (cibleId != null && String(a.id) === String(cibleId)) return 0
    return a.epinglee ? 1 : 2
  }
  return [...annonces].sort((a, b) => {
    const dr = rang(a) - rang(b)
    if (dr !== 0) return dr
    const da = new Date(a.date_publication_effective || a.created_at || 0)
    const db = new Date(b.date_publication_effective || b.created_at || 0)
    return db - da
  })
}

export default function AnnoncesPage() {
  useDocumentTitle('Annonces')
  const [searchParams] = useSearchParams()
  const cibleId = searchParams.get('annonce')

  const [annonces, setAnnonces] = useState([])
  const [loading, setLoading] = useState(true)
  // Accusés posés pendant CETTE session (le serializer de liste n'expose pas
  // « est-ce que MOI j'ai lu » — la vérité vit dans le rapport de conformité,
  // réservé à l'admin). Un accusé déjà enregistré côté serveur est idempotent.
  const [lus, setLus] = useState([])
  const [enCours, setEnCours] = useState(null)
  const cibleRef = useRef(null)

  const charger = useCallback(() => {
    setLoading(true)
    return notificationsApi.getAnnonces({ active: 1 })
      .then((r) => {
        const rows = Array.isArray(r.data) ? r.data : (r.data?.results ?? [])
        setAnnonces(rows)
      })
      .catch(() => toast.error('Chargement des annonces impossible.'))
      .finally(() => setLoading(false))
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- fetch-on-mount via le helper de rafraîchissement partagé
  useEffect(() => { charger() }, [charger])

  // `?annonce=<pk>` : l'annonce visée est déjà remontée en tête par `trier` ;
  // on l'amène en plus dans le champ de vision (best-effort — `scrollIntoView`
  // n'existe pas en environnement de test headless).
  useEffect(() => {
    if (!cibleId || loading) return
    cibleRef.current?.scrollIntoView?.({ block: 'center' })
  }, [cibleId, loading, annonces])

  const triees = useMemo(() => trier(annonces, cibleId), [annonces, cibleId])

  const accuser = async (annonce) => {
    setEnCours(annonce.id)
    try {
      await notificationsApi.accuserLectureAnnonce(annonce.id)
      // Idempotent : un second clic laisse la confirmation en place.
      setLus((ids) => (ids.includes(annonce.id) ? ids : [...ids, annonce.id]))
      toast.success('Lecture confirmée.')
    } catch {
      toast.error('Confirmation impossible.')
    } finally {
      setEnCours(null)
    }
  }

  return (
    <div className="p-4" data-testid="annonces-page">
      <PageHeader
        title="Annonces"
        subtitle="Les communications internes qui vous sont adressées."
        icon={Megaphone}
      />

      {loading && (
        <div className="flex justify-center py-10"><Spinner /></div>
      )}

      {!loading && triees.length === 0 && (
        <EmptyState
          icon={Megaphone}
          title="Aucune annonce"
          description="Aucune annonce active ne vous est adressée pour le moment."
        />
      )}

      {!loading && triees.length > 0 && (
        <ul className="flex flex-col gap-3" role="list">
          {triees.map((a) => {
            const cible = cibleId != null && String(a.id) === String(cibleId)
            const lu = lus.includes(a.id)
            return (
              <li key={a.id} ref={cible ? cibleRef : undefined}>
                <Card
                  data-testid={`annonce-${a.id}`}
                  className={cible ? 'border-primary' : undefined}
                >
                  <CardContent className="pt-4">
                    <div className="mb-1 flex flex-wrap items-center gap-2">
                      {a.epinglee && (
                        <Pin size={14} aria-label="Épinglée"
                             className="shrink-0 text-muted-foreground" />
                      )}
                      <h3 className="font-medium text-foreground">{a.titre}</h3>
                      {a.lecture_obligatoire && (
                        <Badge tone="primary">Lecture obligatoire</Badge>
                      )}
                    </div>
                    <p className="mb-2 whitespace-pre-line text-sm text-muted-foreground">
                      {a.corps}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {a.auteur_username && <>Par {a.auteur_username} · </>}
                      {dateFr(a.date_publication_effective || a.created_at)}
                    </p>

                    {a.lecture_obligatoire && (
                      <div className="mt-3">
                        {lu ? (
                          <span
                            className="flex items-center gap-1.5 text-sm font-medium text-foreground"
                            data-testid={`annonce-lue-${a.id}`}
                          >
                            <CheckCircle2 size={16} aria-hidden="true" />
                            Lecture confirmée
                          </span>
                        ) : (
                          <Button
                            type="button"
                            onClick={() => accuser(a)}
                            loading={enCours === a.id}
                          >
                            J’ai lu et compris
                          </Button>
                        )}
                      </div>
                    )}
                  </CardContent>
                </Card>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
