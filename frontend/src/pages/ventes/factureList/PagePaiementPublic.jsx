/**
 * AFAC26 — Page PUBLIQUE « Payer » (aucun login, aucun layout ERP).
 *
 * Route /payer/:token : destination de l'URL absolue du lien « Payer en ligne »
 * (AFAC21), identique à l'e-mail de pré-échéance et au QR du PDF facture. Le
 * jeton identifie un PaymentLink ; la forme servie est celle du contrat
 * `paiement_public.json` (`GET /api/django/public/pay/<token>/`). Montant =
 * reste exigible à l'instant T servi par le serveur, jamais recalculé ici.
 * Jamais de prix d'achat ni de donnée interne.
 */
import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import api from '../../../api/axios'
import { formatMAD } from '../../../lib/format'
import NoIndex from '../../../components/NoIndex'

export default function PagePaiementPublic() {
  const { token } = useParams()
  const [etat, setEtat] = useState('chargement') // chargement | ok | introuvable
  const [data, setData] = useState(null)

  useEffect(() => {
    let alive = true
    api.get(`/public/pay/${token}/`)
      .then((res) => {
        if (!alive) return
        setData(res.data)
        setEtat('ok')
      })
      .catch(() => { if (alive) setEtat('introuvable') })
    return () => { alive = false }
  }, [token])

  let corps
  if (etat === 'chargement') {
    corps = <p>Chargement…</p>
  } else if (etat === 'introuvable' || !data) {
    corps = <p role="alert">Ce lien de paiement est introuvable ou a expiré.</p>
  } else if (data.statut === 'annule') {
    corps = <p className="text-lg font-semibold">Facture annulée</p>
  } else if (data.paye || data.statut === 'paye') {
    corps = <p className="text-lg font-semibold">Facture réglée</p>
  } else if (data.expire || data.statut === 'expire') {
    corps = <p className="text-lg font-semibold">Lien expiré</p>
  } else {
    corps = (
      <>
        <p className="text-2xl font-bold" data-testid="montant-a-regler">
          {formatMAD(data.montant)} à régler
        </p>
        {data.rib ? (
          <div className="mt-4 text-sm">
            <p className="font-medium">Virement bancaire</p>
            <p data-testid="rib" className="tabular-nums">{data.rib}</p>
            <p className="text-muted-foreground">
              Indiquez la référence {data.reference} dans le libellé du virement.
            </p>
          </div>
        ) : null}
      </>
    )
  }

  return (
    <main className="mx-auto max-w-md px-4 py-10">
      <NoIndex />
      <h1 className="mb-1 text-xl font-semibold">Payer ma facture</h1>
      {etat === 'ok' && data ? (
        <p className="mb-6 text-sm text-muted-foreground">
          {data.reference}{data.client_name ? ` — ${data.client_name}` : ''}
        </p>
      ) : null}
      {corps}
    </main>
  )
}
