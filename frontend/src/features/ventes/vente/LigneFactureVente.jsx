// VNT74 (Groupe VNT, D-VNT-3) — une facture de la vente : référence, nature,
// pastille « Brouillon » ≠ « Émise » (une facture brouillon n'a aucune valeur
// comptable), total et payé — tels que servis dans `vente.factures[]`.
// VNT76 — les gestes de CETTE facture, ouverts par `facture.peut` SEUL (dit
// par le serveur avec le palier) : Émettre, PDF, Envoyer (WhatsApp / e-mail),
// Encaisser (PaiementDialog, rafraîchi à la fermeture) et, PAR PAIEMENT, Reçu.
// Un refus serveur s'affiche SOUS cette facture (role=alert, avec sa
// référence) — jamais un toast (règle fondateur « erreurs → le champ fautif »).
import { useState } from 'react'
import { Button, StatusPill } from '../../../ui'
import { formatMAD, formatDate } from '../../../lib/format'
import PaiementDialog from '../../../pages/ventes/PaiementDialog'
import { useActionsVente } from './useActionsVente'

const NATURES = {
  acompte: 'Acompte',
  intermediaire: 'Tranche intermédiaire',
  solde: 'Solde',
  complete: 'Facture complète',
  bc: 'Facture du bon de commande',
  consolidee: 'Facture consolidée',
}

function pastille(statut) {
  if (statut === 'brouillon') return { label: 'Brouillon', tone: 'neutral' }
  if (statut === 'annulee') return { label: 'Annulée', tone: 'danger' }
  return { label: 'Émise', tone: 'info' }
}

export default function LigneFactureVente({ facture: f, onRafraichir, lectureSeule = false }) {
  const actions = useActionsVente({ onSucces: onRafraichir })
  const [encaisser, setEncaisser] = useState(false)
  const [lienWa, setLienWa] = useState('')
  const [info, setInfo] = useState('')
  const p = pastille(f.statut)
  // Version remplacée : lecture seule, aucun geste (VNT74).
  const peut = lectureSeule ? {} : (f.peut || {})
  const occupe = (geste, cle = f.id) => actions.occupe === `${geste}:${cle}`
  const erreur = actions.erreur?.factureId === f.id ? actions.erreur : null
  const recus = lectureSeule ? [] : (f.paiements || []).filter((pa) => pa.peut?.recu === true)

  const whatsapp = async () => {
    setInfo('')
    const r = await actions.whatsapp(f)
    setLienWa(r.ok ? (r.data?.wa_url || '') : '')
  }
  const email = async () => {
    setLienWa('')
    const r = await actions.envoyerEmail(f)
    setInfo(r.ok ? (r.data?.detail || 'Email envoyé.') : '')
  }

  return (
    <li className="grid gap-1 rounded-md border p-2 text-sm" data-testid={`facture-vente-${f.id}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-medium">{f.reference}</span>
        <StatusPill label={p.label} tone={p.tone} />
      </div>
      <div className="flex flex-wrap justify-between gap-2">
        <span className="text-muted-foreground">{NATURES[f.nature] ?? f.nature}</span>
        <span className="num">{formatMAD(f.total_ttc)}</span>
      </div>
      {Number.parseFloat(f.montant_paye ?? '0') > 0 && (
        <p className="text-muted-foreground">Payé : <span className="num">{formatMAD(f.montant_paye)}</span></p>
      )}
      <div className="flex flex-wrap gap-2">
        {peut.emettre === true && (
          <Button type="button" size="sm" loading={occupe('emettre')} onClick={() => actions.emettre(f)}>
            Émettre
          </Button>
        )}
        {peut.pdf === true && (
          <Button type="button" size="sm" variant="outline" loading={occupe('pdf')} onClick={() => actions.pdf(f)}>
            PDF
          </Button>
        )}
        {peut.envoyer === true && (
          <>
            <Button type="button" size="sm" variant="outline" loading={occupe('envoyer')} onClick={whatsapp}>
              WhatsApp
            </Button>
            <Button type="button" size="sm" variant="outline" disabled={occupe('envoyer')} onClick={email}>
              E-mail
            </Button>
          </>
        )}
        {peut.encaisser === true && (
          <Button type="button" size="sm" variant="outline" onClick={() => setEncaisser(true)}>
            Encaisser
          </Button>
        )}
      </div>
      {recus.length > 0 && (
        <ul className="grid gap-1" aria-label={`Paiements de ${f.reference}`}>
          {recus.map((pa) => (
            <li key={pa.id} className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-muted-foreground">
                {formatDate(pa.date_paiement)} — <span className="num">{formatMAD(pa.montant)}</span>
              </span>
              <Button
                type="button" size="sm" variant="ghost" loading={occupe('recu', pa.id)}
                aria-label={`Reçu du paiement du ${formatDate(pa.date_paiement)}`}
                onClick={() => actions.recu(f, pa)}
              >
                Reçu
              </Button>
            </li>
          ))}
        </ul>
      )}
      {lienWa && (
        <a className="gen-hint" href={lienWa} target="_blank" rel="noopener noreferrer">
          Ouvrir WhatsApp pour {f.reference}
        </a>
      )}
      {info && <p className="gen-hint" role="status">{info}</p>}
      {erreur && <p className="text-destructive" role="alert">{f.reference} : {erreur.message}</p>}
      <PaiementDialog
        facture={encaisser ? f : null}
        onOpenChange={(o) => { if (!o) { setEncaisser(false); onRafraichir?.() } }}
        onSaved={() => onRafraichir?.()}
      />
    </li>
  )
}
