import { useEffect, useState } from 'react'
import { Link, useMatch } from 'react-router-dom'
import useDroitMetier from '../../../sav/useDroitMetier'
import { BoutonMarine, Icone, Segmente } from './primitives'

/* ============================================================================
   COQUE — LE BANDEAU DU PROJET (maquette v2 Main : 56 px ; au bureau il flotte sur la carte).
   « ‹ Calepinages » · nom (16 px demi-gras) + ligne 12 px · [espace] · état
   d'enregistrement (BarreEnregistrement, forme barre du haut) · Guidé | Expert ·
   « Générer le devis » BLEU NUIT (ACAL1802 : l'or est réservé au bouton d'étape). Le niveau expert reste porté par la case
   `cal-mode-expert` (contrat des tests et des specs) que le segmenté pilote.
   Rien n'est inventé : le nom et la ligne viennent du contexte servi.
   ========================================================================== */

const MODES = [{ valeur: 'guide', libelle: 'Guidé' }, { valeur: 'expert', libelle: 'Expert' }]

/** Vrai au doigt (`pointer: coarse`) : l'entrée du bandeau est alors « Relevé », sinon « Montrer au client ». */
function useAuDoigt() {
  const lire = () => typeof window !== 'undefined' && typeof window.matchMedia === 'function'
    && !!window.matchMedia('(pointer: coarse)')?.matches
  const [doigt, setDoigt] = useState(lire)
  useEffect(() => {
    const mq = typeof window.matchMedia === 'function' ? window.matchMedia('(pointer: coarse)') : null
    if (!mq?.addEventListener) return undefined
    const suivre = () => setDoigt(!!mq.matches)
    mq.addEventListener('change', suivre)
    return () => mq.removeEventListener('change', suivre)
  }, [])
  return doigt
}

/** ACAL1809 — l'écran de visite (au doigt) ou de présentation (à la souris) d'UN toucher depuis le bandeau : les deux
    liens n'étaient qu'au fond d'« Avancé ». Seulement sur `/calepinage/:id` (jamais en mode devis ou lead). */
function EntreeVisite({ id }) {
  const doigt = useAuDoigt()
  const pose = doigt
    ? { vers: 'releve', testid: 'cal-barre-releve', libelle: 'Relevé', titre: 'Relevé de visite',
      picto: <><path d="M9 4h6a1 1 0 011 1v1H8V5a1 1 0 011-1z" /><path d="M8 6H6a1 1 0 00-1 1v13a1 1 0 001 1h12a1 1 0 001-1V7a1 1 0 00-1-1h-2" /><path d="M9 12h6M9 16h4" /></> }
    : { vers: 'client', testid: 'cal-barre-montrer-client', libelle: 'Montrer au client', titre: 'Montrer au client',
      picto: <><rect x="3" y="4" width="18" height="12" rx="1.5" /><path d="M8 20h8M12 16v4" /></> }
  return (
    <Link to={`/calepinage/${id}/${pose.vers}`} className="cal-barre-entree" data-testid={pose.testid} title={pose.titre}>
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
        strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{pose.picto}</svg>
      <span className="cal-barre-entree-texte">{pose.libelle}</span>
    </Link>
  )
}

export default function BarreProjet({
  retour, titre, sousTitre = '', enregistrement = null, expert = false, onExpert,
  libelleDevis = 'Générer le devis', onDevis = null, cache = false,
}) {
  const calepinageId = useMatch('/calepinage/:id')?.params.id ?? null
  // D-ACAL-106 — le Technicien relève et ne chiffre pas : sans `ventes_creer`, « Générer le devis » n'est pas proposé (le serveur reste l'autorité).
  const peutDevis = useDroitMetier('ventes_creer')
  return (
    <header className="cal-barre-projet" data-testid="cal-barre-projet" hidden={cache || undefined}>
      {/* « ‹ Calepinages » referme l'atelier comme le geste qui l'a ouvert (`retour.onClick`, qui
          confirme d'abord une conception non enregistrée) ; à défaut, un lien vers la liste. */}
      {retour.onClick ? (
        <button type="button" onClick={retour.onClick} className="cal-retour" data-testid="cal-retour-liste">
          <Icone nom="retour" taille={18} epaisseur={2} />
          <span className="cal-retour-texte">{retour.libelle}</span>
        </button>
      ) : (
        <Link to={retour.to} className="cal-retour" data-testid="cal-retour-liste">
          <Icone nom="retour" taille={18} epaisseur={2} />
          <span className="cal-retour-texte">{retour.libelle}</span>
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
      {calepinageId && <EntreeVisite id={calepinageId} />}
      {onDevis && peutDevis && (
        <BoutonMarine onClick={onDevis} className="cal-bouton-devis" data-testid="cal-generer-devis-haut">
          {libelleDevis}
        </BoutonMarine>
      )}
    </header>
  )
}
