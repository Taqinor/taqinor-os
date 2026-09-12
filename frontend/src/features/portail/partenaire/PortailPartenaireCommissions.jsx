import { useCallback, useEffect, useState } from 'react'
import { Coins, Download } from 'lucide-react'
import portailApi from '../../../api/portailApi'
import {
  Badge, Button, Card, EmptyState, FormField, Input, Spinner, toast,
} from '../../../ui'
import { formatMAD, formatDate } from '../../../lib/format'

/* ============================================================================
   NTPRT30 — « Mes commissions » (portail PARTENAIRE).
   ----------------------------------------------------------------------------
   Relevé en LECTURE SEULE : le partenaire consulte, il ne solde jamais sa
   propre commission (`marquer_payee` reste une action interne). Le partenaire
   est déduit du compte connecté côté serveur — aucun identifiant n'est envoyé.

   Les MONTANTS affichés sont ceux que le serveur renvoie, tels quels : le
   total est la somme des lignes rendues, calculée UNE seule fois côté serveur
   (jamais re-sommée ici, sinon écran et PDF pourraient diverger).

   Le PDF est le MÊME relevé, rendu par le service PDF partagé (jamais le
   moteur de devis — règle #4).
   ========================================================================== */

const TON_STATUT = {
  due: 'warning',
  payee: 'success',
  annulee: 'neutral',
}

export default function PortailPartenaireCommissions() {
  const [releve, setReleve] = useState(null)
  const [loading, setLoading] = useState(true)
  const [erreur, setErreur] = useState(false)
  const [debut, setDebut] = useState('')
  const [fin, setFin] = useState('')
  const [erreursBornes, setErreursBornes] = useState({})
  const [pdfEnCours, setPdfEnCours] = useState(false)

  const charger = useCallback((params) => {
    setLoading(true)
    setErreursBornes({})
    portailApi.partenaire.commissions.releve(params)
      .then((r) => {
        setReleve(r.data)
        setErreur(false)
      })
      .catch((err) => {
        const data = err?.response?.data || {}
        if (data.debut || data.fin) {
          setErreursBornes({ debut: data.debut, fin: data.fin })
        } else {
          setErreur(true)
        }
      })
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    // Différé d'un microtask (react-hooks/set-state-in-effect).
    Promise.resolve().then(() => charger({}))
  }, [charger])

  const appliquer = (e) => {
    e.preventDefault()
    const params = {}
    if (debut) params.debut = debut
    if (fin) params.fin = fin
    charger(params)
  }

  const telechargerPdf = async () => {
    setPdfEnCours(true)
    try {
      const params = {}
      if (debut) params.debut = debut
      if (fin) params.fin = fin
      const res = await portailApi.partenaire.commissions.pdf(params)
      const url = window.URL.createObjectURL(new Blob([res.data]))
      const a = document.createElement('a')
      a.href = url
      a.download = 'releve-commissions.pdf'
      a.click()
      window.URL.revokeObjectURL(url)
    } catch {
      toast.error('Le relevé PDF n’a pas pu être téléchargé.')
    } finally {
      setPdfEnCours(false)
    }
  }

  const totaux = releve?.totaux

  return (
    <>
      <div className="flex items-center gap-2">
        <Coins className="size-5 text-muted-foreground" aria-hidden="true" />
        <h1 className="font-display text-xl font-semibold tracking-tight">
          Mes commissions
        </h1>
      </div>

      <Card className="p-4">
        <form onSubmit={appliquer}
              className="flex flex-wrap items-end gap-3">
          <FormField label="Du" error={erreursBornes.debut}>
            <Input type="date" value={debut}
                   onChange={(e) => setDebut(e.target.value)} />
          </FormField>
          <FormField label="Au" error={erreursBornes.fin}>
            <Input type="date" value={fin}
                   onChange={(e) => setFin(e.target.value)} />
          </FormField>
          <Button type="submit" size="sm" variant="outline">
            Appliquer la période
          </Button>
          <Button type="button" size="sm" onClick={telechargerPdf}
                  disabled={pdfEnCours}>
            <Download aria-hidden="true" /> Relevé PDF
          </Button>
        </form>
      </Card>

      {loading ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Spinner /> Chargement de votre relevé…
        </div>
      ) : erreur || !releve ? (
        <EmptyState
          title="Relevé indisponible"
          description="Votre relevé n’a pas pu être chargé. Réessayez plus tard."
        />
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-3">
            <Card className="flex flex-col gap-1 p-4">
              <span className="text-sm text-muted-foreground">Dues</span>
              <span className="font-display text-2xl font-semibold">
                {formatMAD(totaux.due)}
              </span>
            </Card>
            <Card className="flex flex-col gap-1 p-4">
              <span className="text-sm text-muted-foreground">Payées</span>
              <span className="font-display text-2xl font-semibold">
                {formatMAD(totaux.payee)}
              </span>
            </Card>
            <Card className="flex flex-col gap-1 p-4">
              <span className="text-sm text-muted-foreground">
                Total du relevé
              </span>
              <span className="font-display text-2xl font-semibold">
                {formatMAD(totaux.total)}
              </span>
            </Card>
          </div>

          {releve.lignes.length === 0 ? (
            <EmptyState
              title="Aucune commission"
              description="Aucune commission n’a été enregistrée sur cette période."
            />
          ) : (
            <ul className="flex flex-col gap-3">
              {releve.lignes.map((l) => (
                <Card key={l.id} className="flex flex-col gap-1 p-4">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <p className="font-medium">{formatMAD(l.montant)}</p>
                      <p className="text-xs text-muted-foreground">
                        {formatDate(l.date_creation)}
                        {l.devis_id ? ` — devis n° ${l.devis_id}` : ''}
                        {` — ${formatMAD(l.base_ht)} × ${l.taux} %`}
                      </p>
                    </div>
                    <Badge tone={TON_STATUT[l.statut] || 'neutral'}>
                      {l.statut_display}
                    </Badge>
                  </div>
                  {l.paye_le && (
                    <p className="text-sm text-muted-foreground">
                      Payée le {formatDate(l.paye_le)}
                    </p>
                  )}
                </Card>
              ))}
            </ul>
          )}
        </>
      )}
    </>
  )
}
