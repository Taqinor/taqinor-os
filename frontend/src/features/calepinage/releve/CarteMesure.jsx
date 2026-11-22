/* Maquette Telephone — une carte de mesure : libellé 14 px, valeur 20 px, bouton 44 px à droite
   (« Mesurer encore », « Boussole »). Le détail (saisie à la main, précision, motif) vient dessous. */
export function CarteMesure({ testId, libelle, valeur, bouton, onBouton, desactive = false, children = null }) {
  return (
    <div className="cal-tel-carte" data-testid={testId}>
      <div className="cal-tel-carte-ligne">
        <span className="cal-tel-carte-texte">
          <span className="cal-tel-libelle">{libelle}</span>
          <span className="cal-tel-valeur" data-testid={`${testId}-valeur`}>{valeur}</span>
        </span>
        <button type="button" className="cal-tel-bouton" onClick={onBouton} disabled={desactive}
          data-testid={`${testId}-bouton`}>
          {bouton}
        </button>
      </div>
      {children}
    </div>
  )
}

/** Un champ décimal du relevé (`inputmode="decimal"`, la virgule acceptée), unité à droite. */
export function ChampDecimal({ id, testId, libelle, valeur, onChange, unite = null, compact = false }) {
  return (
    <div className="cal-tel-champ">
      <label htmlFor={id} className="cal-tel-libelle">{libelle}</label>
      <div className={compact ? 'cal-tel-saisie cal-tel-saisie-compacte' : 'cal-tel-saisie'}>
        <input id={id} data-testid={testId} type="text" inputMode="decimal" value={valeur}
          onChange={(e) => onChange(e.target.value)} />
        {unite && <span className="cal-tel-unite">{unite}</span>}
      </div>
    </div>
  )
}
