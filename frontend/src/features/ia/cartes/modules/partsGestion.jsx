/* eslint-disable react-refresh/only-export-components -- tables de libellés co-localisées avec les briques des cartes (D-ENF22) */
import { ExternalLink } from 'lucide-react'
import { Button } from '../../../../ui'
import { formatMAD } from '../../../../lib/format'
import { cheminAutorise } from '../ecrans'
import { useOuvrirEcran } from '../useCarte'

/* Copilote vague 2 (CRT-B) — briques communes aux cartes « gestion » (ventes,
   stock, après-vente, chiffres). Une carte n'affiche que ce que le serveur a
   envoyé : aucun chiffre recalculé ici, aucun lien fabriqué (le chemin vient du
   champ `lien` de la charge utile, suivi seulement s'il figure dans `ecrans.js`). */

/** Geste suivant dit par le serveur (ensemble fermé `a_faire`) ; « rien » ou une
 *  valeur inconnue : aucune ligne. */
export const GESTES = Object.freeze({
  facturer: 'Facturer la prochaine tranche',
  emettre_brouillon: 'Émettre le brouillon depuis l’écran des factures',
  emettre: 'Émettre la facture depuis l’écran',
  encaisser: 'Enregistrer l’encaissement',
  reviser: 'Ouvrir la dernière version du devis',
  relancer: 'Relancer le client',
  attendre_promesse: 'Attendre la promesse de paiement',
  traiter_contestation: 'Traiter la contestation',
  reapprovisionner: 'Réapprovisionner',
  planifier: 'Planifier l’intervention',
  demarrer: 'Démarrer le ticket',
  resoudre: 'Résoudre le ticket',
  cloturer: 'Clôturer le ticket',
  suivre_ticket: 'Suivre le ticket ouvert',
  voir_impayes: 'Voir les impayés',
})

export const STATUTS_FACTURE = Object.freeze({
  brouillon: 'Brouillon', emise: 'Émise', en_retard: 'En retard', payee: 'Payée', annulee: 'Annulée',
})

export const NATURES_FACTURE = Object.freeze({
  acompte: 'Acompte', intermediaire: 'Intermédiaire', solde: 'Solde', complete: 'Complète',
})

export const libelle = (table, cle) => table[cle] ?? cle ?? ''

export const montant = (v) => formatMAD(v)

export function Titre({ children }) {
  return <p className="mb-2 break-words text-sm font-semibold">{children}</p>
}

export function Vide({ texte }) {
  return <p className="text-sm text-muted-foreground">{texte}</p>
}

export { Rangee } from './partsTerrain'

/** Une ligne « libellé : valeur » ; sans valeur, rien n'est affiché. */
export function Ligne({ nom, valeur }) {
  if (valeur === undefined || valeur === null || valeur === '') return null
  return (
    <div className="flex flex-wrap items-baseline justify-between gap-x-3 text-sm">
      <dt className="text-muted-foreground">{nom}</dt>
      <dd className="font-medium">{valeur}</dd>
    </div>
  )
}

/** Le geste suivant, tel que le serveur le désigne. */
export function Geste({ cle }) {
  const texte = GESTES[cle]
  return texte ? <p className="mt-1 text-xs">À faire : {texte}</p> : null
}

/** Bouton vers un écran de l'ERP : seulement un `lien` du serveur reconnu par `ecrans.js`. */
export function BoutonLien({ lien, texte = 'Ouvrir' }) {
  const ouvrir = useOuvrirEcran()
  if (!cheminAutorise(lien)) return null
  return (
    <Button variant="outline" size="sm" className="mt-1.5 min-h-10 max-w-full" onClick={() => ouvrir(lien)}>
      <ExternalLink className="size-4 shrink-0" aria-hidden="true" />
      <span className="truncate">{texte}</span>
    </Button>
  )
}

/** Mention « n affichés sur total » quand le serveur dit qu'il en existe davantage. */
export function SurTotal({ affiches, total }) {
  if (!(total > affiches)) return null
  return <p className="mt-2 text-xs text-muted-foreground">{affiches} affiché(s) sur {total}.</p>
}

const LIMITE_CITATION = 300

/** Texte venu d'un TIERS (client, terrain) : texte brut, cité, coupé poliment. */
export function Citation({ texte }) {
  if (!texte) return null
  const brut = String(texte)
  const coupe = brut.length > LIMITE_CITATION ? `${brut.slice(0, LIMITE_CITATION).trimEnd()}…` : brut
  return (
    <blockquote className="mt-1 whitespace-pre-line break-words border-l-2 border-border pl-2 text-xs italic text-muted-foreground">
      « {coupe} »
    </blockquote>
  )
}
