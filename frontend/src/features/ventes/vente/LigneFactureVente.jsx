// VNT74 (Groupe VNT, D-VNT-3) — une facture de la vente : référence, nature,
// pastille « Brouillon » ≠ « Émise » (une facture brouillon n'a aucune valeur
// comptable), total et payé — tels que servis dans `vente.factures[]`.
// VNT76 — les gestes de CETTE facture, ouverts par `facture.peut` SEUL (dit
// par le serveur avec le palier) : Émettre, PDF, Envoyer (WhatsApp / e-mail),
// Encaisser (PaiementDialog, rafraîchi à la fermeture) et, PAR PAIEMENT, Reçu.
// Un refus serveur s'affiche SOUS cette facture (role=alert, avec sa
// référence) — jamais un toast (règle fondateur « erreurs → le champ fautif »).
// VNT77 (D-VNT-1) — Annuler (le dialogue nomme la conséquence : avoir
// automatique, facture tracée ; avec argent, la directive est obligatoire),
// Supprimer (un `BROUILLON-<id>` seulement), Modifier le montant d'un
// brouillon (`montant-tranche`) : visibles selon `peut` (palier serveur), donc
// jamais un 403 évitable — un Commercial n'en voit aucun.
import { useState } from 'react'
import { Button, Input, StatusPill } from '../../../ui'
import { formatMAD, formatDate } from '../../../lib/format'
import PaiementDialog from '../../../pages/ventes/PaiementDialog'
import {
  AnnulationFactureDialog, SuppressionBrouillonDialog,
} from '../../../pages/ventes/factureList/AnnulationFactureDialog'
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

const estProvisoire = (reference) => String(reference || '').startsWith('BROUILLON-')
// Normalisation de saisie (espaces, virgule) — jamais d'arrondi du nombre tapé.
const normaliser = (v) => String(v ?? '').trim().replace(/\s/g, '').replace(',', '.')

export default function LigneFactureVente({
  facture: f, facturesVente = [], onRafraichir, lectureSeule = false,
}) {
  const actions = useActionsVente({ onSucces: onRafraichir })
  const [encaisser, setEncaisser] = useState(false)
  const [lienWa, setLienWa] = useState('')
  const [info, setInfo] = useState('')
  // VNT77 — gestes de correction : annuler (avoir + directive d'argent),
  // supprimer un BROUILLON-<id>, modifier le montant d'un brouillon de tranche.
  const [annulOuvert, setAnnulOuvert] = useState(false)
  const [annulMsg, setAnnulMsg] = useState(null)
  const [directiveRequise, setDirectiveRequise] = useState(false)
  const [suppOuvert, setSuppOuvert] = useState(false)
  const [montant, setMontant] = useState(null) // null = champ fermé
  const p = pastille(f.statut)
  // Version remplacée : lecture seule, aucun geste (VNT74).
  const peut = lectureSeule ? {} : (f.peut || {})
  const occupe = (geste, cle = f.id) => actions.occupe === `${geste}:${cle}`
  const erreur = actions.erreur?.factureId === f.id && actions.erreur.geste !== 'annuler'
    ? actions.erreur : null
  const recus = lectureSeule ? [] : (f.paiements || []).filter((pa) => pa.peut?.recu === true)

  const enregistrerMontant = async (e) => {
    e.preventDefault()
    const r = await actions.modifierMontant(f, normaliser(montant))
    if (r.ok) setMontant(null)
  }
  const confirmerAnnulation = async (directive) => {
    setAnnulMsg(null)
    const r = await actions.annuler(f, directive)
    if (r.ok) { setAnnulOuvert(false); return }
    setAnnulMsg(r.message)
    if (r.code === 'directive_acompte_requise') setDirectiveRequise(true)
  }

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
        {peut.modifier_montant === true && montant === null && (
          <Button type="button" size="sm" variant="outline" onClick={() => setMontant(String(f.total_ttc ?? ''))}>
            Modifier le montant
          </Button>
        )}
        {peut.annuler === true && (
          <Button
            type="button" size="sm" variant="outline"
            onClick={() => { actions.effacerErreur(); setAnnulMsg(null); setDirectiveRequise(false); setAnnulOuvert(true) }}
          >
            Annuler
          </Button>
        )}
        {peut.supprimer === true && estProvisoire(f.reference) && (
          <Button type="button" size="sm" variant="ghost" onClick={() => setSuppOuvert(true)}>
            Supprimer
          </Button>
        )}
      </div>
      {montant !== null && (
        <form className="flex flex-wrap items-end gap-2" onSubmit={enregistrerMontant} noValidate>
          <label className="grid gap-1">
            <span className="text-muted-foreground">Montant TTC de {f.reference}</span>
            <Input
              type="text" inputMode="decimal" value={montant} autoFocus
              onChange={(e) => setMontant(e.target.value)}
            />
          </label>
          <Button type="submit" size="sm" loading={occupe('montant')}>Enregistrer</Button>
          <Button type="button" size="sm" variant="ghost" onClick={() => setMontant(null)}>Retour</Button>
        </form>
      )}
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
      {annulOuvert && (
        <AnnulationFactureDialog
          facture={f}
          factures={facturesVente}
          busy={occupe('annuler')}
          erreur={annulMsg}
          directiveRequise={directiveRequise}
          onClose={() => setAnnulOuvert(false)}
          onConfirm={confirmerAnnulation}
        />
      )}
      {suppOuvert && (
        <SuppressionBrouillonDialog
          facture={f}
          busy={occupe('supprimer')}
          onClose={() => setSuppOuvert(false)}
          onConfirm={async () => { await actions.supprimer(f); setSuppOuvert(false) }}
        />
      )}
    </li>
  )
}
