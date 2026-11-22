/* ============================================================================
   COQUE — LES ATOMES PARTAGÉS DES ÉCRANS DE L'ATELIER (maquettes 22/11).
   ----------------------------------------------------------------------------
   UN SEUL endroit pour les pièces répétées des maquettes (pas de copie de 6 lignes
   d'un écran à l'autre). Couleurs : jetons uniquement, via les classes `cal-*` de
   `styles/calepinage/50-coque-atelier.css` (thème sombre par les jetons seuls).
   Pictogrammes : tracés des maquettes, `currentColor`, `aria-hidden`.
   ========================================================================== */

const TRACES = {
  toit: <><path d="M3 11l9-7 9 7" /><path d="M5 10v9h14v-9" /></>,
  panneaux: <><rect x="3" y="4" width="18" height="16" rx="1.5" /><path d="M3 12h18M9 4v16M15 4v16" /></>,
  electrique: <path d="M13 2L4 14h7l-1 8 9-12h-7z" />,
  resultats: <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" />,
  documents: <><path d="M14 3H6a1 1 0 00-1 1v16a1 1 0 001 1h12a1 1 0 001-1V8z" /><path d="M14 3v5h5M9 13h6M9 17h6" /></>,
  avance: <><path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12" /><circle cx="16" cy="6" r="2" /><circle cx="10" cy="12" r="2" /><circle cx="18" cy="18" r="2" /></>,
  retour: <path d="M15 18l-6-6 6-6" />,
  coche: <path d="M20 6L9 17l-5-5" />,
  suivant: <path d="M5 12h14M13 6l6 6-6 6" />,
  plus: <path d="M12 5v14M5 12h14" />,
  moins: <path d="M5 12h14" />,
  lecture: <path d="M7 4l13 8-13 8z" fill="currentColor" stroke="none" />,
  chevron: <path d="M6 9l6 6 6-6" />,
  info: <><circle cx="12" cy="12" r="9" /><path d="M12 8v5M12 16.5v.5" /></>,
  // Barre d'outils de la carte et pile de zoom (maquette Main).
  selection: <path d="M5 3l14 8-6 2-2 6z" />,
  trace: <><path d="M4 18l5-12 6 9 5-7" /><circle cx="4" cy="18" r="1.6" /><circle cx="9" cy="6" r="1.6" /><circle cx="15" cy="15" r="1.6" /><circle cx="20" cy="8" r="1.6" /></>,
  obstacle: <><rect x="5" y="5" width="14" height="14" rx="2" /><path d="M5 19L19 5" /></>,
  mesure: <><path d="M3 17L17 3l4 4L7 21z" /><path d="M8 12l2 2M11 9l2 2M14 6l2 2" /></>,
  annuler: <><path d="M9 14L4 9l5-5" /><path d="M4 9h10a6 6 0 010 12h-3" /></>,
  retablir: <><path d="M15 14l5-5-5-5" /><path d="M20 9H10a6 6 0 000 12h3" /></>,
  pleinEcran: <path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5" />,
  partager: <><circle cx="18" cy="5" r="3" /><circle cx="6" cy="12" r="3" /><circle cx="18" cy="19" r="3" /><path d="M8.6 13.5l6.8 4M15.4 6.5l-6.8 4" /></>,
}

/** Un pictogramme des maquettes (`nom` ∈ clés de TRACES), à la couleur du texte. */
export function Icone({ nom, taille = 24, epaisseur = 1.8, className = '' }) {
  return (
    <svg width={taille} height={taille} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={epaisseur} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"
      className={className || undefined}>
      {TRACES[nom] ?? null}
    </svg>
  )
}

/** Le bouton doré des maquettes (« Générer le devis », « Poser les panneaux → »).
    `plein` : pleine largeur, 48 px, 16 px (pied d'étape) ; sinon 44 px, 14 px. */
export function BoutonOr({ children, plein = false, fleche = false, className = '', ...props }) {
  return (
    <button type="button" className={`cal-bouton-or${plein ? ' cal-bouton-or-plein' : ''} ${className}`} {...props}>
      {children}
      {fleche && <Icone nom="suivant" taille={18} epaisseur={2.2} />}
    </button>
  )
}

/** Le bouton marine (« Confirmer », « Régler »). */
export function BoutonMarine({ children, className = '', ...props }) {
  return <button type="button" className={`cal-bouton-marine ${className}`} {...props}>{children}</button>
}

/** Le contrôle segmenté (Guidé | Expert, Plan | 3D, Portrait | Paysage | Au mieux).
    `options` = [{ valeur, libelle }] ; `aria-pressed` porte l'état choisi. */
export function Segmente({ libelle, options, valeur, onChange, grand = false, className = '' }) {
  return (
    <div role="group" aria-label={libelle} className={`cal-segmente${grand ? ' cal-segmente-grand' : ''} ${className}`}>
      {options.map((o) => (
        <button key={o.valeur} type="button" aria-pressed={o.valeur === valeur}
          onClick={() => onChange?.(o.valeur)}>
          {o.libelle}
        </button>
      ))}
    </div>
  )
}

/** La carte blanche posée sur la carte (puce « Surface du toit | Pans | Besoin… »,
    barre d'outils flottante). Positionnée par la classe passée (`cal-sur-carte-haut`, …). */
export function CarteFlottante({ children, className = '', ...props }) {
  return <div className={`cal-carte-flottante ${className}`} {...props}>{children}</div>
}

/** Un indicateur de la puce de carte : libellé 12 px au-dessus, valeur 20 px. */
export function Indicateur({ libelle, valeur }) {
  return (
    <div className="cal-indicateur">
      <span className="cal-indicateur-libelle">{libelle}</span>
      <span className="cal-indicateur-valeur">{valeur}</span>
    </div>
  )
}

/** Une section de panneau d'étape : intitulé 14 px demi-gras, contenu en colonne (gap 8). */
export function SectionEtape({ titre, action = null, children, className = '' }) {
  return (
    <section className={`cal-section-etape ${className}`}>
      <div className="cal-section-etape-tete">
        <h2>{titre}</h2>
        {action}
      </div>
      {children}
    </section>
  )
}

/** La tuile choisie / non choisie (formes du toit, options de pose) : bord or + fond pâle si choisie. */
export function Tuile({ choisie = false, pointillee = false, children, className = '', ...props }) {
  return (
    <button type="button" aria-pressed={choisie}
      className={`cal-tuile${pointillee ? ' cal-tuile-pointillee' : ''} ${className}`} {...props}>
      {children}
    </button>
  )
}
