/* Coque — le panneau d'étape de droite (maquette Main : 360 px, fond carte, filet gauche).
   En-tête « Étape N sur 5 » (12 px) + titre (20 px) ; corps qui défile seul ; pied collé en
   bas (bouton doré plein largeur). Porte l'id historique `rp9-studio-inspecteur` (specs).
   `refCorps` / `refPied` : les nœuds que la coque ouvre aux portails `<DansPanneau>` / `<PiedEtape>`. */
export default function PanneauEtape({
  numero = null, total = 5, titre, cache = false, refCorps, refPied, children, pied = null,
}) {
  return (
    <aside id="rp9-studio-inspecteur" aria-label={titre || 'Étape'} hidden={cache}
      className="cal-panneau-etape" data-testid="cal-panneau-etape">
      {titre && (
        <div className="cal-panneau-etape-tete">
          {numero && <p className="cal-panneau-etape-rang">{`Étape ${numero} sur ${total}`}</p>}
          <h2 className="cal-panneau-etape-titre" data-testid="cal-panneau-etape-titre">{titre}</h2>
        </div>
      )}
      <div className="cal-panneau-etape-corps">
        <div ref={refCorps} className="cal-panneau-etape-emplacement" />
        {children}
      </div>
      <div ref={refPied} className="cal-panneau-etape-pied">{pied}</div>
    </aside>
  )
}
