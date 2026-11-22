import { Link } from 'react-router-dom'
import { BoutonOr, Icone, Segmente } from './primitives'

/* ============================================================================
   COQUE — LE BANDEAU DU PROJET (maquette Main : 56 px, fond carte, filet bas).
   « ‹ Calepinages » · nom (16 px demi-gras) + ligne 12 px · [espace] · état
   d'enregistrement (BarreEnregistrement, forme barre du haut) · Guidé | Expert ·
   « Générer le devis » doré. Le niveau expert reste porté par la case
   `cal-mode-expert` (contrat des tests et des specs) que le segmenté pilote.
   Rien n'est inventé : le nom et la ligne viennent du contexte servi.
   ========================================================================== */

const MODES = [{ valeur: 'guide', libelle: 'Guidé' }, { valeur: 'expert', libelle: 'Expert' }]

export default function BarreProjet({
  retour, titre, sousTitre = '', enregistrement = null, expert = false, onExpert,
  libelleDevis = 'Générer le devis', onDevis = null, cache = false,
}) {
  return (
    <header className="cal-barre-projet" data-testid="cal-barre-projet" hidden={cache || undefined}>
      {/* « ‹ Calepinages » referme l'atelier comme le geste qui l'a ouvert (`retour.onClick`, qui
          confirme d'abord une conception non enregistrée) ; à défaut, un lien vers la liste. */}
      {retour.onClick ? (
        <button type="button" onClick={retour.onClick} className="cal-retour" data-testid="cal-retour-liste">
          <Icone nom="retour" taille={18} epaisseur={2} />
          {retour.libelle}
        </button>
      ) : (
        <Link to={retour.to} className="cal-retour" data-testid="cal-retour-liste">
          <Icone nom="retour" taille={18} epaisseur={2} />
          {retour.libelle}
        </Link>
      )}
      <h1 className="cal-projet">
        <span className="cal-projet-titre" data-testid="cal-projet-titre">{titre}</span>
        {sousTitre && <span className="cal-projet-sous-titre" data-testid="cal-projet-sous-titre">{sousTitre}</span>}
      </h1>
      <span className="cal-barre-espace" aria-hidden="true" />
      {enregistrement}
      {/* Miroir du segmenté (contrat `cal-mode-expert` des tests) : hors du parcours clavier et sans boîte (le
          segmenté est LE contrôle ; un seul arrêt de tabulation, un seul contrôle compté à l'écran). */}
      <label className="sr-only cal-case-expert" aria-hidden="true">
        <input type="checkbox" data-testid="cal-mode-expert" checked={expert} tabIndex={-1}
          onChange={(e) => onExpert(e.target.checked)} />
        Mode expert
      </label>
      <Segmente libelle="Mode" options={MODES} valeur={expert ? 'expert' : 'guide'}
        onChange={(v) => onExpert(v === 'expert')} />
      {onDevis && (
        <BoutonOr onClick={onDevis} data-testid="cal-generer-devis-haut">{libelleDevis}</BoutonOr>
      )}
    </header>
  )
}
