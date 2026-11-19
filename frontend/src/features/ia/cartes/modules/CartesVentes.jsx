import { formatDate } from '../../../../lib/format'
import { cheminDeLEcran } from '../ecrans'
import {
  BoutonLien, Geste, Ligne, Rangee, SurTotal, Titre, Vide, libelle, montant, NATURES_FACTURE, STATUTS_FACTURE,
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

const TRANCHES_AGE = Object.freeze([
  ['b0_30', '0 à 30 jours'], ['b31_60', '31 à 60 jours'], ['b61_90', '61 à 90 jours'], ['b90_plus', 'Plus de 90 jours'],
])

// `liste_impayes` — qui doit de l'argent (action `ventes.impayes.lister`). L'ordre est celui du
// serveur (les plus en retard d'abord) ; les tranches d'âge portent sur TOUTES les factures dues.
function CarteImpayes({ carte }) {
  const d = carte.donnees ?? {}
  const lignes = d.lignes ?? []
  if (!lignes.length) return <Vide texte="Aucun impayé en retard pour le moment." />
  return (
    <div className="min-w-0">
      <Titre>Impayés : {montant(d.total_du)} ({d.nb_factures} facture{d.nb_factures > 1 ? 's' : ''})</Titre>
      <dl className="mb-2 space-y-0.5">
        {TRANCHES_AGE.map(([cle, nom]) => <Ligne key={cle} nom={nom} valeur={montant(d.tranches?.[cle])} />)}
      </dl>
      <ul className="space-y-2">
        {lignes.map((l) => (
          <Rangee key={l.facture_id} titre={`${l.client_nom} — ${montant(l.montant_du)}`}
            detail={[l.reference, l.niveau, l.jours_retard > 0 ? `${l.jours_retard} j de retard` : '',
              l.promesse?.date_promise ? `promesse pour le ${formatDate(l.promesse.date_promise)}` : '',
              l.contestee ? 'contestée' : ''].filter(Boolean).join(' · ')}>
            <Geste cle={l.a_faire} />
            <BoutonLien lien={l.lien} texte="Ouvrir la facture" />
          </Rangee>
        ))}
      </ul>
      <SurTotal affiches={lignes.length} total={d.nb_factures} />
      <BoutonLien lien={d.lien} texte="Ouvrir les relances" />
    </div>
  )
}

// `liste_factures` — retrouver une facture (action `ventes.facture.chercher`). Plusieurs
// candidates : on les montre, l'assistant demande laquelle (il ne répartit jamais).
function CarteFactures({ carte }) {
  const d = carte.donnees ?? {}
  const lignes = d.lignes ?? []
  if (!lignes.length) return <Vide texte="Aucune facture ne correspond." />
  return (
    <div className="min-w-0">
      <Titre>Factures trouvées ({d.total ?? lignes.length})</Titre>
      <ul className="space-y-2">
        {lignes.map((l) => (
          <Rangee key={l.facture_id} titre={`${l.reference} — ${l.client_nom}`}
            detail={[libelle(NATURES_FACTURE, l.nature), libelle(STATUTS_FACTURE, l.statut),
              `total ${montant(l.total_ttc)}`,
              l.montant_du && l.montant_du !== '0.00' ? `reste dû ${montant(l.montant_du)}` : '',
              dateOuVide(l.date_emission) && `émise le ${dateOuVide(l.date_emission)}`,
              dateOuVide(l.date_echeance) && `échéance le ${dateOuVide(l.date_echeance)}`,
              l.jours_retard > 0 ? `${l.jours_retard} j de retard` : ''].filter(Boolean).join(' · ')}>
            <Geste cle={l.a_faire} />
            <BoutonLien lien={l.lien} texte="Ouvrir la facture" />
          </Rangee>
        ))}
      </ul>
      <SurTotal affiches={lignes.length} total={d.total} />
    </div>
  )
}

// `facture_brouillon` — la facture que l'assistant a PRÉPARÉE (action `ventes.vente.facturer`,
// décision D-W2-Q2) : un BROUILLON sans numéro légal, l'émission reste un geste d'écran. La carte
// le dit en toutes lettres et ne ressemble jamais à une facture émise. Le serveur ne sert pas de
// `lien` dans cette réponse : le bouton n'apparaît que si la charge utile en porte un.
function CarteFactureBrouillon({ carte }) {
  const d = carte.donnees ?? {}
  const f = d.facture ?? {}
  const v = d.vente ?? {}
  return (
    <div className="min-w-0 border-l-4 border-warning pl-2">
      <p className="text-xs font-semibold uppercase tracking-wide text-warning">
        Brouillon — à vérifier puis émettre à l’écran
      </p>
      <Titre>{libelle(NATURES_FACTURE, f.nature)} : {montant(f.total_ttc)} TTC</Titre>
      <p className="break-words text-xs text-muted-foreground">
        Référence provisoire {f.reference} · aucun numéro de facture légal tant qu’elle n’est pas émise.
      </p>
      <dl className="mt-2 space-y-0.5">
        <Ligne nom="Prix convenu TTC" valeur={montant(v.prix_convenu_ttc)} />
        <Ligne nom="Déjà émis TTC" valeur={montant(v.emis_ttc)} />
        <Ligne nom="Brouillons TTC" valeur={montant(v.brouillons_ttc)} />
        <Ligne nom="Reste à facturer TTC" valeur={montant(v.reste_a_facturer_ttc)} />
        <Ligne nom="Reste à payer TTC" valeur={montant(v.reste_a_payer_ttc)} />
      </dl>
      <BoutonLien lien={d.lien ?? cheminDeLEcran('facture', f.id)} texte="Ouvrir la facture pour l’émettre" />
    </div>
  )
}

const CARTES_VENTES = Object.freeze({
  vente_etat: CarteVenteEtat,
  liste_impayes: CarteImpayes,
  liste_factures: CarteFactures,
  facture_brouillon: CarteFactureBrouillon,
})
export default CARTES_VENTES
