import { useEffect, useState } from 'react'
import { Receipt } from 'lucide-react'
import portailApi from '../../../api/portailApi'
import {
  Badge, Button, Card, EmptyState, Spinner, toast,
} from '../../../ui'
import { formatMAD, formatDate } from '../../../lib/format'

/* ============================================================================
   NTPRT11 — « Mes commandes & factures » (portail client authentifié).
   ----------------------------------------------------------------------------
   Liste des factures + statut de règlement + bouton « Payer ». Le paiement en
   ligne est GATÉ (`CMI_ENABLED`, clé marchande) : tant qu'il est OFF, aucun
   appel réseau payant n'est possible — le bouton crée une intention `initie`
   LOCALE côté serveur et l'écran affiche les coordonnées bancaires (RIB du
   `CompanyProfile`) comme repli. Jamais une erreur, jamais une passerelle
   fantôme : le bandeau annonce explicitement que le paiement en ligne arrive.

   Le PDF de facture reste le PDF LEGACY facturation — séparé du moteur devis
   (règle #4, qui ne couvre que le PDF DEVIS client).
   ========================================================================== */

// Statuts de `facturation.Facture` (brouillon exclu côté serveur).
const TON_STATUT = {
  payee: 'success',
  en_retard: 'danger',
  emise: 'info',
  annulee: 'neutral',
}

export default function PortailClientFactures() {
  const [rows, setRows] = useState([])
  const [enLigneActif, setEnLigneActif] = useState(false)
  const [loading, setLoading] = useState(true)
  const [erreur, setErreur] = useState(false)
  const [paiement, setPaiement] = useState(null)
  const [envoi, setEnvoi] = useState(null)

  const charger = () => {
    setLoading(true)
    portailApi.factures.liste()
      .then((r) => {
        setRows(r.data?.results ?? [])
        setEnLigneActif(!!r.data?.paiement_en_ligne_actif)
        setErreur(false)
      })
      .catch(() => setErreur(true))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    charger()
    // eslint-disable-next-line react-hooks/exhaustive-deps -- chargement au montage
  }, [])

  const payer = async (facture) => {
    setEnvoi(facture.id)
    try {
      const r = await portailApi.factures.payer(facture.id)
      setPaiement({ ...r.data, reference_facture: facture.reference })
    } catch (err) {
      toast.error(err?.response?.data?.detail
        || "La demande de paiement n'a pas abouti.")
    } finally {
      setEnvoi(null)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Spinner /> Chargement de vos factures…
      </div>
    )
  }

  if (erreur) {
    return (
      <EmptyState
        title="Factures indisponibles"
        description="Vos factures n’ont pas pu être chargées. Réessayez plus tard."
      />
    )
  }

  return (
    <>
      <div className="flex items-center gap-2">
        <Receipt className="size-5 text-muted-foreground" aria-hidden="true" />
        <h1 className="font-display text-xl font-semibold tracking-tight">
          Mes commandes &amp; factures
        </h1>
      </div>

      {!enLigneActif && (
        <p className="rounded-md border border-border bg-muted/40 px-3 py-2 text-sm text-muted-foreground">
          Le paiement en ligne par carte sera bientôt disponible. En attendant,
          « Payer » vous donne les coordonnées bancaires pour un virement.
        </p>
      )}

      {paiement && (
        <Card className="flex flex-col gap-1 p-4">
          <p className="font-medium">
            Paiement de la facture {paiement.reference_facture}
          </p>
          <p className="text-sm text-muted-foreground">
            Référence de votre intention : {paiement.reference} —{' '}
            {formatMAD(paiement.montant)}
          </p>
          {paiement.virement?.rib ? (
            <p className="text-sm">
              Virement à l’ordre de{' '}
              <span className="font-medium">
                {paiement.virement.beneficiaire}
              </span>
              {paiement.virement.banque ? ` (${paiement.virement.banque})` : ''}
              {' '}— RIB{' '}
              <span className="font-mono">{paiement.virement.rib}</span>
            </p>
          ) : (
            <p className="text-sm text-muted-foreground">
              Contactez-nous pour recevoir les coordonnées bancaires.
            </p>
          )}
        </Card>
      )}

      {rows.length === 0 ? (
        <EmptyState
          title="Aucune facture"
          description="Vous n’avez aucune facture pour le moment."
        />
      ) : (
        <ul className="flex flex-col gap-3">
          {rows.map((f) => (
            <Card key={f.id} className="flex flex-col gap-3 p-4">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="font-medium">{f.reference}</p>
                  <p className="text-xs text-muted-foreground">
                    Émise le {formatDate(f.date_emission)}
                    {f.date_echeance
                      ? ` — échéance ${formatDate(f.date_echeance)}`
                      : ''}
                  </p>
                </div>
                <Badge tone={TON_STATUT[f.statut] || 'neutral'}>
                  {f.statut_display}
                </Badge>
              </div>
              <p className="text-sm">
                <span className="text-muted-foreground">Total TTC : </span>
                <span className="font-medium">{formatMAD(f.montant_ttc)}</span>
                {!f.payee && (
                  <>
                    <span className="text-muted-foreground"> — reste dû : </span>
                    <span className="font-medium">{formatMAD(f.montant_du)}</span>
                  </>
                )}
              </p>
              {!f.payee && (
                <div>
                  <Button size="sm" loading={envoi === f.id}
                          onClick={() => payer(f)}>
                    Payer
                  </Button>
                </div>
              )}
            </Card>
          ))}
        </ul>
      )}
    </>
  )
}
