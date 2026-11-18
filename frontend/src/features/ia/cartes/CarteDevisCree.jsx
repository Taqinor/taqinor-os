import { TriangleAlert } from 'lucide-react'
import { Button } from '../../../ui'
import { formatMAD } from '../../../lib/format'
import { idDevisSur } from './cartes'
import BoutonTelechargerDevis from './BoutonTelechargerDevis'
import { useOuvrirEcran } from './useCarte'

/* COP2-W1 — carte « devis_cree » : ce que l'assistant vient de composer
   (contrat apps/ventes/contract_samples/assistant_devis_cree.json). Colonne de
   ~220 px : chaque ligne s'empile (désignation, puis « qté × prix TTC » et total).
   Le PDF ne passe que par le bouton existant (/proposal, règle #4). Aucun champ
   d'accès au PDF du serveur (jeton, chemin) n'est lu ni affiché ; aucun prix
   d'achat ni marge. Tout champ peut manquer (serveur plus ancien) : on rend ce
   qui est là, sans jamais planter. */

const estObjet = (v) => v != null && typeof v === 'object' && !Array.isArray(v)

const kwcTexte = (kwc) => {
  const n = Number(kwc)
  if (kwc == null || kwc === '' || !Number.isFinite(n) || n <= 0) return ''
  return `${n.toLocaleString('fr-FR', { maximumFractionDigits: 2 })} kWc`
}

const quantiteTexte = (q) => {
  const n = Number(q)
  return Number.isFinite(n) ? n.toLocaleString('fr-FR', { maximumFractionDigits: 2 }) : ''
}

function LigneComposition({ ligne }) {
  const qte = quantiteTexte(ligne.quantite)
  const pu = ligne.prix_unitaire_ttc != null && ligne.prix_unitaire_ttc !== ''
    ? formatMAD(ligne.prix_unitaire_ttc) : ''
  const detail = [qte, pu].filter(Boolean).join(' × ')
  const variante = typeof ligne.variante === 'string' ? ligne.variante.trim() : ''
  return (
    <li className="min-w-0 rounded-md border border-border bg-background/60 p-2" data-testid="devis-cree-ligne">
      <p className="min-w-0 break-words text-sm font-medium">{ligne.designation || 'Ligne du devis'}</p>
      <div className="mt-0.5 flex min-w-0 flex-wrap items-baseline justify-between gap-x-2 text-xs text-muted-foreground">
        <span className="min-w-0 break-words">{detail}{detail ? ' TTC' : ''}</span>
        {ligne.total_ttc != null && ligne.total_ttc !== '' && (
          <span className="font-medium text-foreground">{formatMAD(ligne.total_ttc)}</span>
        )}
      </div>
      {variante && <p className="mt-0.5 min-w-0 break-words text-xs text-muted-foreground">{variante}</p>}
    </li>
  )
}

export default function CarteDevisCree({ carte }) {
  const navigate = useOuvrirEcran()
  const d = estObjet(carte?.donnees) ? carte.donnees : {}
  const id = idDevisSur(d.devis_id ?? d.id)
  const composition = (Array.isArray(d.composition) ? d.composition : []).filter(estObjet)
  const alertes = (Array.isArray(d.alertes) ? d.alertes : [])
    .map((a) => (typeof a === 'string' ? a : a?.message))
    .filter((m) => typeof m === 'string' && m.trim())
  const kwc = kwcTexte(d.kwc)
  const reference = typeof d.reference === 'string' ? d.reference : ''
  const autres = Number.isInteger(d.nb_lignes) ? d.nb_lignes - composition.length : 0
  const aTotal = d.total_ttc != null && d.total_ttc !== ''
  return (
    <div className="min-w-0">
      <p className="min-w-0 break-words text-sm font-semibold">
        Devis créé{reference ? ` — ${reference}` : ''}
      </p>
      {(kwc || d.statut === 'brouillon') && (
        <p className="mt-0.5 text-xs text-muted-foreground">
          {[kwc, d.statut === 'brouillon' ? 'Brouillon' : ''].filter(Boolean).join(' · ')}
        </p>
      )}
      {composition.length > 0 && (
        <ul className="mt-2 space-y-1.5">
          {composition.map((ligne, i) => <LigneComposition key={i} ligne={ligne} />)}
        </ul>
      )}
      {autres > 0 && (
        <p className="mt-1.5 text-xs text-muted-foreground" data-testid="devis-cree-autres">
          + {autres} autre{autres > 1 ? 's' : ''} ligne{autres > 1 ? 's' : ''} dans le devis.
        </p>
      )}
      {aTotal && (
        <p className="mt-2 flex flex-wrap items-baseline justify-between gap-x-2 text-sm font-semibold" data-testid="devis-cree-total">
          <span>Total TTC</span>
          <span>{formatMAD(d.total_ttc)}</span>
        </p>
      )}
      {alertes.length > 0 && (
        <ul className="mt-2 space-y-1" data-testid="devis-cree-alertes">
          {alertes.map((m, i) => (
            <li key={i} className="flex min-w-0 items-start gap-1.5 text-xs text-amber-700 dark:text-amber-400">
              <TriangleAlert className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
              <span className="min-w-0 break-words">{m}</span>
            </li>
          ))}
        </ul>
      )}
      {id && (
        <div className="mt-2.5 flex flex-wrap items-center gap-2">
          <Button size="sm" className="min-h-10" onClick={() => navigate(`/ventes/devis?devis=${id}`)}>
            Ouvrir le devis
          </Button>
          <BoutonTelechargerDevis devisId={id} reference={reference} label="Télécharger le PDF" />
        </div>
      )}
    </div>
  )
}
