import { useEffect, useState } from 'react'
import { FileText } from 'lucide-react'
import portailApi from '../../../api/portailApi'
import {
  Badge, Button, Card, Checkbox, Dialog, DialogContent, DialogFooter,
  DialogHeader, DialogTitle, EmptyState, Input, Label, Spinner, toast,
} from '../../../ui'
import { formatMAD, formatDate } from '../../../lib/format'

/* ============================================================================
   NTPRT10 — « Mes devis » (portail client authentifié).
   ----------------------------------------------------------------------------
   Liste + PDF + acceptation. Le PDF ouvre l'UNIQUE chemin canonique
   `/api/django/ventes/devis/<id>/proposal/` (CLAUDE.md règle #4) — jamais un
   rendu propre au portail. L'acceptation POSTe sur l'endpoint portail, qui
   appelle le service d'acceptation UNIQUE de `ventes` : la chaîne aval (statut
   accepté → BC/facture → chantier) est donc identique au lien public.

   Le consentement e-signature est EXPLICITE (QX9, loi 43-20) : la case n'est
   jamais pré-cochée et le bouton reste désactivé tant qu'elle ne l'est pas.
   ========================================================================== */

export default function PortailClientDevis() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [erreur, setErreur] = useState(false)
  const [aSigner, setASigner] = useState(null)
  const [nom, setNom] = useState('')
  const [consent, setConsent] = useState(false)
  const [envoi, setEnvoi] = useState(false)

  const charger = () => {
    setLoading(true)
    portailApi.devis.liste()
      .then((r) => { setRows(r.data?.results ?? []); setErreur(false) })
      .catch(() => setErreur(true))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    // Différé d'un microtask : `charger` pose l'état de chargement de façon
    // synchrone, ce qui déclenche un rendu en cascade
    // (react-hooks/set-state-in-effect). Comportement inchangé.
    Promise.resolve().then(charger)
    // eslint-disable-next-line react-hooks/exhaustive-deps -- chargement au montage
  }, [])

  const ouvrirSignature = (devis) => {
    setASigner(devis)
    setNom('')
    setConsent(false)
  }

  const accepter = async () => {
    if (!aSigner || !nom.trim() || !consent) return
    setEnvoi(true)
    try {
      await portailApi.devis.accepter(aSigner.id, {
        nom: nom.trim(),
        consent_esign: true,
      })
      toast.success('Devis accepté. Merci !')
      setASigner(null)
      charger()
    } catch (err) {
      toast.error(err?.response?.data?.detail
        || "L'acceptation n'a pas abouti.")
    } finally {
      setEnvoi(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Spinner /> Chargement de vos devis…
      </div>
    )
  }

  if (erreur) {
    return (
      <EmptyState
        title="Devis indisponibles"
        description="Vos devis n’ont pas pu être chargés. Réessayez plus tard."
      />
    )
  }

  return (
    <>
      <div className="flex items-center gap-2">
        <FileText className="size-5 text-muted-foreground" aria-hidden="true" />
        <h1 className="font-display text-xl font-semibold tracking-tight">
          Mes devis
        </h1>
      </div>

      {rows.length === 0 ? (
        <EmptyState
          title="Aucun devis"
          description="Vous n’avez aucun devis pour le moment."
        />
      ) : (
        <ul className="flex flex-col gap-3">
          {rows.map((d) => (
            <Card key={d.id} className="flex flex-col gap-3 p-4">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="font-medium">{d.reference}</p>
                  <p className="text-xs text-muted-foreground">
                    {formatDate(d.date_creation)}
                    {d.date_validite
                      ? ` — valable jusqu’au ${formatDate(d.date_validite)}`
                      : ''}
                  </p>
                </div>
                <Badge tone={d.accepte ? 'success' : 'neutral'}>
                  {d.statut_display}
                </Badge>
              </div>
              <p className="text-sm">
                <span className="text-muted-foreground">Total TTC : </span>
                <span className="font-medium">{formatMAD(d.total_ttc)}</span>
              </p>
              <div className="flex flex-wrap gap-2">
                <Button asChild variant="outline" size="sm">
                  <a href={portailApi.devis.pdfUrl(d.id)}
                     target="_blank" rel="noreferrer">
                    Voir le devis (PDF)
                  </a>
                </Button>
                {!d.accepte && (
                  <Button size="sm" onClick={() => ouvrirSignature(d)}>
                    Accepter
                  </Button>
                )}
              </div>
            </Card>
          ))}
        </ul>
      )}

      <Dialog open={!!aSigner} onOpenChange={(o) => !o && setASigner(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              Accepter le devis {aSigner?.reference}
            </DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="portail-signataire">Votre nom</Label>
              <Input id="portail-signataire" value={nom}
                     onChange={(e) => setNom(e.target.value)}
                     placeholder="Nom et prénom du signataire" />
            </div>
            <label className="flex items-start gap-2 text-sm">
              <Checkbox checked={consent}
                        onCheckedChange={(v) => setConsent(v === true)} />
              <span>
                J’accepte ce devis et je consens à sa signature électronique.
              </span>
            </label>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setASigner(null)}>
              Annuler
            </Button>
            <Button onClick={accepter}
                    disabled={envoi || !nom.trim() || !consent}>
              {envoi ? 'Envoi…' : 'Confirmer l’acceptation'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
