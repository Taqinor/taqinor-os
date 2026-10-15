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
import { MoreHorizontal } from 'lucide-react'
import {
  Button, Input, StatusPill,
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem,
} from '../../../ui'
import { useIsMobile } from '../../../ui/ResponsiveDialog'
import { formatMAD, formatDate } from '../../../lib/format'
import PaiementDialog from '../../../pages/ventes/PaiementDialog'
import {
  AnnulationFactureDialog, SuppressionBrouillonDialog,
} from '../../../pages/ventes/factureList/AnnulationFactureDialog'
import { useActionsVente } from './useActionsVente'
import { CIBLE_TACTILE } from './venteEtat'

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
  const mobile = useIsMobile()
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

  // VNT81 — les gestes ouverts par le serveur, dans l'ordre d'importance ; au
  // téléphone, 2 boutons visibles au plus, le reste dans « Autres actions ».
  const gestes = [
    peut.emettre === true && { cle: 'emettre', label: 'Émettre', loading: occupe('emettre'), onClick: () => actions.emettre(f) },
    peut.encaisser === true && { cle: 'encaisser', label: 'Encaisser', onClick: () => setEncaisser(true) },
    peut.pdf === true && { cle: 'pdf', label: 'PDF', loading: occupe('pdf'), onClick: () => actions.pdf(f) },
    peut.envoyer === true && { cle: 'whatsapp', label: 'WhatsApp', loading: occupe('envoyer'), onClick: whatsapp },
    peut.envoyer === true && { cle: 'email', label: 'E-mail', disabled: occupe('envoyer'), onClick: email },
    peut.modifier_montant === true && montant === null && {
      cle: 'montant', label: 'Modifier le montant', onClick: () => setMontant(String(f.total_ttc ?? '')),
    },
    peut.annuler === true && {
      cle: 'annuler', label: 'Annuler',
      onClick: () => { actions.effacerErreur(); setAnnulMsg(null); setDirectiveRequise(false); setAnnulOuvert(true) },
    },
    peut.supprimer === true && estProvisoire(f.reference) && {
      cle: 'supprimer', label: 'Supprimer', variant: 'ghost', onClick: () => setSuppOuvert(true),
    },
  ].filter(Boolean)
  const visibles = mobile ? gestes.slice(0, 2) : gestes
  const autres = mobile ? gestes.slice(2) : []

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
      {(visibles.length > 0 || autres.length > 0) && (
        <div className="flex flex-wrap gap-2">
          {visibles.map((g, i) => (
            <Button
              key={g.cle} type="button" size="sm" className={CIBLE_TACTILE}
              variant={g.variant ?? (i === 0 && g.cle === 'emettre' ? 'default' : 'outline')}
              loading={g.loading} disabled={g.disabled} onClick={g.onClick}
            >
              {g.label}
            </Button>
          ))}
          {autres.length > 0 && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  type="button" size="sm" variant="ghost" className={CIBLE_TACTILE}
                  aria-label={`Autres actions — ${f.reference}`}
                >
                  <MoreHorizontal className="size-4" aria-hidden="true" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                {autres.map((g) => (
                  <DropdownMenuItem key={g.cle} disabled={g.disabled || g.loading} onSelect={g.onClick}>
                    {g.label}
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
          )}
        </div>
      )}
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
                type="button" size="sm" variant="ghost" className={CIBLE_TACTILE} loading={occupe('recu', pa.id)}
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
