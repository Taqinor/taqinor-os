/* Maquette Telephone v2 — UNE carte blanche porte les mesures lues (pente, orientation), une ligne chacune :
   libellé 13 px, valeur 20 px / 700, sa provenance (« ✓ mesurée » en vert, sinon « · saisie à la main » en gris),
   bouton 44 px à droite (« Mesurer encore », « Boussole » + son pictogramme). Le détail (saisie à la main, précision,
   motif) vient dessous, dans la même ligne. Les cartes se suivent : la feuille les rassemble (`.cal-tel-cartes`). */

function Coche() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M20 6L9 17l-5-5" /></svg>
  )
}

/** Le pictogramme de la boussole (aiguille rouille au nord, grise au sud). */
export function PictoBoussole() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeWidth="1.6" />
      <path d="M12 5.5l2.6 6.5h-5.2z" className="cal-tel-boussole-nord" />
      <path d="M12 18.5l-2.6-6.5h5.2z" className="cal-tel-boussole-sud" />
    </svg>
  )
}

export function CarteMesure({
  testId, libelle, valeur, provenance = null, provenanceOk = false, bouton, onBouton, icone = null,
  desactive = false, children = null,
}) {
  return (
    <div className="cal-tel-carte" data-testid={testId}>
      <div className="cal-tel-carte-ligne">
        <span className="cal-tel-carte-texte">
          <span className="cal-tel-libelle">{libelle}</span>
          <span className="cal-tel-valeur" data-testid={`${testId}-valeur`}>
            {valeur}
            {provenance && (provenanceOk ? (
              <>{' '}<span className="cal-tel-provenance" data-ok=""><Coche />{provenance}</span></>
            ) : <span className="cal-tel-provenance">{` · ${provenance}`}</span>)}
          </span>
        </span>
        <button type="button" className="cal-tel-bouton" onClick={onBouton} disabled={desactive}
          data-testid={`${testId}-bouton`}>
          {icone}
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
