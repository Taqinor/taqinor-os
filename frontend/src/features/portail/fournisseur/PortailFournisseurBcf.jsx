import { useEffect, useState } from 'react'
import { PackageCheck } from 'lucide-react'
import portailApi from '../../../api/portailApi'
import {
  Badge, Button, Card, EmptyState, Form, FormField, Input, Spinner, toast,
} from '../../../ui'
import { formatDate } from '../../../lib/format'

/* ============================================================================
   NTPRT21 — « Mes bons de commande » (portail FOURNISSEUR authentifié).
   ----------------------------------------------------------------------------
   Porte XPUR22 (lien public tokenisé) sur le COMPTE fournisseur réel : la
   liste et la confirmation de date passent par `/portail/mes-bons-commande/`,
   dont le serveur déduit le fournisseur du compte connecté — le frontend
   n'envoie AUCUN identifiant de fournisseur.

   La confirmation a le MÊME effet que l'ancien lien email : elle pose l'accusé
   (date + numéro) sans jamais écraser la date DEMANDÉE, qui reste affichée à
   côté pour que le fournisseur voie ce qu'on lui avait demandé.

   Aucun montant n'est rendu ici : le serveur n'en envoie pas (le fournisseur
   n'a besoin, à ce stade, que du QUOI et du QUAND).
   ========================================================================== */

const TON_STATUT = {
  envoye: 'info',
  recu: 'success',
}

export default function PortailFournisseurBcf() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [erreur, setErreur] = useState(false)
  const [ouvert, setOuvert] = useState(null)
  const [date, setDate] = useState('')
  const [numero, setNumero] = useState('')
  const [champErreur, setChampErreur] = useState(null)
  const [busy, setBusy] = useState(false)

  const charger = () => {
    setLoading(true)
    portailApi.fournisseur.bonsCommande.liste()
      .then((r) => {
        setRows(r.data?.results ?? [])
        setErreur(false)
      })
      .catch(() => setErreur(true))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    // Différé d'un microtask : `charger` pose l'état de chargement de façon
    // synchrone (react-hooks/set-state-in-effect).
    Promise.resolve().then(charger)
  }, [])

  const ouvrir = (bcf) => {
    setOuvert(bcf.id)
    setDate(bcf.date_confirmee_fournisseur || bcf.date_livraison_prevue || '')
    setNumero(bcf.numero_confirmation_fournisseur || '')
    setChampErreur(null)
  }

  const confirmer = async (e, bcf) => {
    e.preventDefault()
    setChampErreur(null)
    setBusy(true)
    try {
      await portailApi.fournisseur.bonsCommande.confirmer(bcf.id, {
        date_confirmee: date,
        numero_confirmation: numero,
      })
      toast.success('Merci, votre date de livraison a bien été enregistrée.')
      setOuvert(null)
      charger()
    } catch (err) {
      const data = err?.response?.data
      // Le serveur NOMME le champ fautif : on l'affiche sous ce champ-là
      // plutôt qu'un « non enregistré » générique.
      setChampErreur(data?.date_confirmee || data?.detail
        || "La confirmation n'a pas abouti.")
    } finally {
      setBusy(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Spinner /> Chargement de vos commandes…
      </div>
    )
  }

  if (erreur) {
    return (
      <EmptyState
        title="Commandes indisponibles"
        description="Vos commandes n’ont pas pu être chargées. Réessayez plus tard."
      />
    )
  }

  return (
    <>
      <div className="flex items-center gap-2">
        <PackageCheck className="size-5 text-muted-foreground" aria-hidden="true" />
        <h1 className="font-display text-xl font-semibold tracking-tight">
          Mes bons de commande
        </h1>
      </div>

      {rows.length === 0 ? (
        <EmptyState
          title="Aucun bon de commande"
          description="Vous n’avez aucune commande en cours pour le moment."
        />
      ) : (
        <ul className="flex flex-col gap-3">
          {rows.map((bcf) => (
            <Card key={bcf.id} className="flex flex-col gap-3 p-4">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="font-medium">{bcf.reference}</p>
                  <p className="text-xs text-muted-foreground">
                    Commandé le {formatDate(bcf.date_commande)}
                    {bcf.date_livraison_prevue
                      ? ` — livraison demandée le ${formatDate(bcf.date_livraison_prevue)}`
                      : ''}
                  </p>
                </div>
                {bcf.a_confirmer
                  ? <Badge tone="warning">À confirmer</Badge>
                  : (
                    <Badge tone={TON_STATUT[bcf.statut] || 'neutral'}>
                      {bcf.statut_display}
                    </Badge>
                    )}
              </div>

              <ul className="flex flex-col gap-0.5 text-sm text-muted-foreground">
                {(bcf.lignes || []).map((l, i) => (
                  <li key={`${bcf.id}-${i}`}>
                    {l.produit_nom} — {l.quantite}
                    {l.quantite_recue ? ` (reçu : ${l.quantite_recue})` : ''}
                  </li>
                ))}
              </ul>

              {bcf.date_confirmee_fournisseur && (
                <p className="text-sm">
                  <span className="text-muted-foreground">
                    Vous avez confirmé le{' '}
                  </span>
                  <span className="font-medium">
                    {formatDate(bcf.date_confirmee_fournisseur)}
                  </span>
                  {bcf.numero_confirmation_fournisseur
                    ? ` (accusé ${bcf.numero_confirmation_fournisseur})`
                    : ''}
                </p>
              )}

              {ouvert === bcf.id ? (
                <Form onSubmit={(e) => confirmer(e, bcf)}
                      className="flex flex-col gap-3">
                  <FormField label="Date de livraison que vous confirmez">
                    <Input type="date" value={date}
                           onChange={(e) => setDate(e.target.value)} />
                  </FormField>
                  <FormField label="Votre numéro d’accusé (facultatif)">
                    <Input value={numero}
                           onChange={(e) => setNumero(e.target.value)} />
                  </FormField>
                  {champErreur ? (
                    <p className="text-sm text-destructive" role="alert">
                      {champErreur}
                    </p>
                  ) : null}
                  <div className="flex gap-2">
                    <Button type="submit" size="sm" disabled={busy}>
                      Confirmer cette date
                    </Button>
                    <Button type="button" size="sm" variant="ghost"
                            onClick={() => setOuvert(null)}>
                      Annuler
                    </Button>
                  </div>
                </Form>
              ) : (
                <div>
                  <Button size="sm" variant={bcf.a_confirmer ? 'default' : 'outline'}
                          onClick={() => ouvrir(bcf)}>
                    {bcf.date_confirmee_fournisseur
                      ? 'Modifier ma date'
                      : 'Confirmer une date'}
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
