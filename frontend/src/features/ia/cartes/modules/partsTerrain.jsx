import { ExternalLink } from 'lucide-react'
import { Badge, Button } from '../../../../ui'
import { cheminAutorise } from '../ecrans'
import { useOuvrirEcran } from '../useCarte'

/* Copilote vague 2 (CRT-A) — pièces communes des cartes « terrain » : calepinage,
   visites, chantiers. Une carte rend ce que le serveur a envoyé (rien n'est
   recalculé) ; un lien ne vient que d'un champ `lien`, validé par `ecrans.js`. */

// Ensembles FERMÉS `a_faire` des trois domaines (contrats `assistant_*`).
const A_FAIRE = Object.freeze({
  creer: 'Créer le calepinage',
  reprendre_visite: 'Reprendre la visite',
  dessiner: 'Dessiner le calepinage',
  simuler: 'Lancer la simulation',
  corriger_electrique: 'Corriger le verdict électrique',
  retenir: 'Retenir une variante',
  faire_approuver: 'Faire approuver',
  publier: 'Publier au devis',
  preparer_calepinage: 'Préparer un calepinage',
  assigner: 'Assigner un technicien',
  completer: 'Compléter la visite',
  valider: 'Valider la visite',
  refaire: 'Refaire la visite',
  assigner_visites: 'Assigner les visites sans technicien',
  commander_materiel: 'Commander le matériel',
  encaisser_acompte: 'Encaisser l’acompte',
  planifier_pose: 'Planifier la pose',
  assigner_technicien: 'Assigner un technicien',
  poser: 'Poser',
})

/** Libellé de l'action suivante ; `rien` et l'inconnu ne disent rien. */
const libelleAFaire = (cle) => A_FAIRE[cle] ?? ''

export function Rangee({ titre, detail, children }) {
  return (
    <li className="min-w-0 rounded-md border border-border bg-background/60 p-2">
      <p className="break-words text-sm font-medium">{titre}</p>
      {detail && <p className="break-words text-xs text-muted-foreground">{detail}</p>}
      {children}
    </li>
  )
}

/** « Étiquette : valeur » sur une ligne qui passe à la ligne sans déborder. */
export function Ligne({ etiquette, children }) {
  return (
    <p className="mt-1 break-words text-xs">
      <span className="text-muted-foreground">{etiquette} : </span>{children}
    </p>
  )
}

export function Vide({ texte }) {
  return <p className="text-sm text-muted-foreground">{texte}</p>
}

export function Titre({ children }) {
  return <p className="mb-2 break-words text-sm font-semibold">{children}</p>
}

/** « À faire : … » — l'action suivante telle que le serveur la nomme. */
export function AFaire({ cle }) {
  const texte = libelleAFaire(cle)
  if (!texte) return null
  return (
    <p className="mt-1.5">
      <Badge tone="info" className="max-w-full whitespace-normal break-words">À faire : {texte}</Badge>
    </p>
  )
}

/** Bouton d'ouverture d'un écran — `chemin` doit être un chemin de la table `ecrans.js`. */
export function BoutonEcran({ chemin, libelle = 'Ouvrir' }) {
  const ouvrir = useOuvrirEcran()
  if (!cheminAutorise(chemin)) return null
  return (
    <Button variant="outline" size="sm" className="mt-2 min-h-10 max-w-full" onClick={() => ouvrir(chemin)}>
      <ExternalLink className="size-4 shrink-0" aria-hidden="true" />
      <span className="truncate">{libelle}</span>
    </Button>
  )
}

/** Texte saisi par un tiers (terrain, client) : texte brut, marqué comme cité. */
export function Citation({ titre, texte }) {
  if (!texte) return null
  return (
    <blockquote className="mt-2 min-w-0 border-l-2 border-border pl-2">
      {titre && <p className="text-xs font-medium text-muted-foreground">{titre}</p>}
      <p className="whitespace-pre-line break-words text-xs italic">{texte}</p>
    </blockquote>
  )
}

/** Plus de lignes côté serveur que celles envoyées : on le dit, sans rien recalculer. */
export function SuiteListe({ total, affiche }) {
  if (!(total > affiche)) return null
  return (
    <p className="mt-1.5 text-xs text-muted-foreground">
      {affiche} affichés sur {total} : le reste se lit dans l’écran.
    </p>
  )
}
