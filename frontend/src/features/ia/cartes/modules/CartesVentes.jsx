import { formatDate } from '../../../../lib/format'
import {
  BoutonLien, Geste, Ligne, Rangee, Titre, libelle, montant, NATURES_FACTURE, STATUTS_FACTURE,
} from './partsGestion'

/* Copilote vague 2 (CRT-B) — cartes du domaine « ventes » (clé de registry.CARTES
   -> composant). Les montants sont ceux du serveur (texte décimal), passés par
   `lib/format` ; rien n'est recalculé ici. */

const dateOuVide = (iso) => (iso ? formatDate(iso) : '')

// `vente_etat` — où en est une vente après le devis (action `ventes.vente.etat`).
function CarteVenteEtat({ carte }) {
  const d = carte.donnees ?? {}
  return (
    <div className="min-w-0">
      <Titre>Vente {d.reference}{d.client ? ` — ${d.client}` : ''}</Titre>
      <dl className="space-y-0.5">
        <Ligne nom="Prix convenu TTC" valeur={montant(d.prix_convenu_ttc)} />
        <Ligne nom="Émis TTC" valeur={montant(d.emis_ttc)} />
        <Ligne nom="Brouillons TTC" valeur={montant(d.brouillons_ttc)} />
        <Ligne nom="Payé TTC" valeur={montant(d.paye_ttc)} />
        <Ligne nom="Reste à facturer TTC" valeur={montant(d.reste_a_facturer_ttc)} />
        <Ligne nom="Reste à payer TTC" valeur={montant(d.reste_a_payer_ttc)} />
      </dl>
      {d.est_tete === false && (
        <p className="mt-1 text-xs text-warning">Ce devis n’est pas la dernière version de la vente.</p>
      )}
      {d.raison_bloquee && <p className="mt-1 break-words text-xs text-warning">{d.raison_bloquee}</p>}
      {d.prochaines_echeances?.length > 0 && (
        <div className="mt-2">
          <p className="text-xs font-semibold">Prochaines tranches</p>
          <ul className="mt-1 space-y-0.5 text-xs">
            {d.prochaines_echeances.map((e) => (
              <li key={e.cle} className="break-words">{e.libelle} — {montant(e.montant_ttc)}</li>
            ))}
          </ul>
        </div>
      )}
      {d.factures?.length > 0 && (
        <ul className="mt-2 space-y-1.5">
          {d.factures.map((f) => (
            <Rangee key={f.facture_id} titre={`${f.reference} — ${montant(f.total_ttc)}`}
              detail={[libelle(NATURES_FACTURE, f.nature), libelle(STATUTS_FACTURE, f.statut),
                f.montant_du && f.montant_du !== '0.00' ? `reste dû ${montant(f.montant_du)}` : '',
                dateOuVide(f.date_emission) && `émise le ${dateOuVide(f.date_emission)}`]
                .filter(Boolean).join(' · ')} />
          ))}
        </ul>
      )}
      <Geste cle={d.a_faire} />
      <BoutonLien lien={d.lien} texte="Ouvrir le devis" />
    </div>
  )
}

const CARTES_VENTES = Object.freeze({
  vente_etat: CarteVenteEtat,
})
export default CARTES_VENTES
