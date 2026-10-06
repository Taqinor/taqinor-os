import { useEffect, useState } from 'react'
import { FileSignature } from 'lucide-react'
import portailApi from '../../../api/portailApi'
import {
  Badge, Button, Card, EmptyState, Spinner, Textarea,
} from '../../../ui'
import { formatDate, formatMAD } from '../../../lib/format'

/* ============================================================================
   ADOC139 (D-ADOC-1) — « Mes contrats » (maintenance) du portail client.
   ----------------------------------------------------------------------------
   Contrat `mes_contrats_maintenance.json` : les clés servies sont affichées
   TELLES QUELLES (aucun recalcul de montant). La demande de renouvellement ou
   de résiliation part en POST `/mes-contrats-maintenance/<id>/demander/`
   `{type_demande, message}` ; elle reste une DEMANDE traitée en interne (elle
   ne touche jamais `actif` ni une date). Le message du serveur — succès ou
   refus lecture seule — est affiché tel quel.
   ========================================================================== */

const TYPES = [
  { value: 'renouvellement', label: 'Demander le renouvellement' },
  { value: 'resiliation', label: 'Demander la résiliation' },
]

function messageErreur(err) {
  const d = err?.response?.data
  return d?.detail
    || (d && typeof d === 'object' && Object.values(d).flat().join(' '))
    || "La demande n'a pas abouti."
}

export default function PortailClientContrats() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [erreur, setErreur] = useState(false)
  const [messages, setMessages] = useState({})
  const [retours, setRetours] = useState({})
  const [envoi, setEnvoi] = useState(null)

  useEffect(() => {
    portailApi.contrats.liste()
      .then((r) => { setRows(r.data?.results ?? []); setErreur(false) })
      .catch(() => setErreur(true))
      .finally(() => setLoading(false))
  }, [])

  const demander = async (contrat, type) => {
    setEnvoi(contrat.id)
    setRetours((r) => ({ ...r, [contrat.id]: null }))
    try {
      const res = await portailApi.contrats.demander(contrat.id, {
        type_demande: type,
        message: (messages[contrat.id] || '').trim(),
      })
      setRetours((r) => ({ ...r, [contrat.id]: { ok: res.data?.detail } }))
    } catch (err) {
      setRetours((r) => ({ ...r, [contrat.id]: { erreur: messageErreur(err) } }))
    } finally {
      setEnvoi(null)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Spinner /> Chargement de vos contrats…
      </div>
    )
  }

  if (erreur) {
    return (
      <EmptyState
        title="Contrats indisponibles"
        description="Vos contrats n’ont pas pu être chargés. Réessayez plus tard."
      />
    )
  }

  return (
    <>
      <div className="flex items-center gap-2">
        <FileSignature className="size-5 text-muted-foreground" aria-hidden="true" />
        <h1 className="font-display text-xl font-semibold tracking-tight">
          Mes contrats
        </h1>
      </div>

      {rows.length === 0 ? (
        <EmptyState
          title="Aucun contrat"
          description="Vous n’avez aucun contrat de maintenance pour le moment."
        />
      ) : (
        <ul className="flex flex-col gap-3">
          {rows.map((c) => {
            const retour = retours[c.id]
            return (
              <Card key={c.id} className="flex flex-col gap-3 p-4">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <p className="font-medium">{c.chantier}</p>
                    <p className="text-xs text-muted-foreground">
                      {c.periodicite_display} — depuis le {formatDate(c.date_debut)}
                      {c.date_renouvellement
                        ? ` — renouvellement le ${formatDate(c.date_renouvellement)}`
                        : ''}
                    </p>
                  </div>
                  <Badge tone={c.actif ? 'success' : 'neutral'}>
                    {c.actif ? 'Actif' : 'Inactif'}
                  </Badge>
                </div>
                <p className="text-sm">
                  <span className="text-muted-foreground">Prix : </span>
                  <span className="font-medium">{formatMAD(c.prix)}</span>
                </p>
                <p className="text-xs text-muted-foreground">
                  Inclus par an : {c.visites_incluses_an} visite(s),{' '}
                  {c.deplacements_inclus_an} déplacement(s) — pièces couvertes à{' '}
                  {c.pieces_couvertes_pct} %
                </p>
                <Textarea aria-label="Message (facultatif)"
                          placeholder="Message (facultatif)"
                          value={messages[c.id] || ''}
                          onChange={(e) => setMessages((m) => ({ ...m, [c.id]: e.target.value }))} />
                <div className="flex flex-wrap gap-2">
                  {TYPES.map((t) => (
                    <Button key={t.value} variant="outline" size="sm"
                            disabled={envoi === c.id}
                            onClick={() => demander(c, t.value)}>
                      {t.label}
                    </Button>
                  ))}
                </div>
                {retour?.ok ? (
                  <p className="text-sm text-emerald-600" role="status">{retour.ok}</p>
                ) : null}
                {retour?.erreur ? (
                  <p className="text-sm text-destructive" role="alert">{retour.erreur}</p>
                ) : null}
              </Card>
            )
          })}
        </ul>
      )}
    </>
  )
}
