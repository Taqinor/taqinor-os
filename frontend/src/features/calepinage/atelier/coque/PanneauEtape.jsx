/* Coque — le panneau d'étape de droite (maquette Main : 360 px, fond carte, filet gauche).
   En-tête « Étape N sur 5 » (12 px) + titre (20 px) ; corps qui défile seul ; pied collé en
   bas (bouton doré plein largeur). Porte l'id historique `rp9-studio-inspecteur` (specs).
   `refCorps` / `refPied` : les nœuds que la coque ouvre aux portails `<DansPanneau>` / `<PiedEtape>`.
   TIROIR (maquette Tablette, et téléphone) — `tiroir` : le même panneau devient le tiroir du bas
   (56-coque-responsive.css) : une poignée qui l'agrandit ou le réduit, puis UNE rangée « titre ·
   contrôle principal (`refControle`, portail `<EnTeteEtape>`) · bouton d'action », les cartes de
   l'étape dessous. Les mêmes enfants, aux mêmes places de l'arbre : rien n'est remonté au passage. */
export default function PanneauEtape({
  numero = null, total = 5, titre, cache = false, refCorps, refPied, children, pied = null,
  tiroir = false, deplie = false, onDeplier = null, refControle = null,
}) {
  return (
    <aside id="rp9-studio-inspecteur" aria-label={titre || 'Étape'} hidden={cache}
      className="cal-panneau-etape" data-testid="cal-panneau-etape"
      data-tiroir={tiroir ? '1' : undefined} data-deplie={tiroir ? (deplie ? '1' : '0') : undefined}>
      {tiroir && (
        <button type="button" className="cal-tiroir-poignee" aria-expanded={deplie}
          aria-label="Agrandir ou réduire le panneau du bas" onClick={() => onDeplier?.(!deplie)}>
          <span aria-hidden="true" />
        </button>
      )}
      {titre && (
        <div className="cal-panneau-etape-tete">
          {numero && <p className="cal-panneau-etape-rang">{`Étape ${numero} sur ${total}`}</p>}
          <h2 className="cal-panneau-etape-titre" data-testid="cal-panneau-etape-titre">{titre}</h2>
        </div>
      )}
      {tiroir && <div ref={refControle} className="cal-panneau-etape-controle" />}
      <div className="cal-panneau-etape-corps">
        <div ref={refCorps} className="cal-panneau-etape-emplacement" />
        {children}
      </div>
      <div ref={refPied} className="cal-panneau-etape-pied">{pied}</div>
    </aside>
  )
}
