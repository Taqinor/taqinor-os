/* ACAL1952 — le matériel électrique que le devis lié a RETENU (`devis_retenu`, servi par `entree-electrique/`) : ce qui
   sert le calcul quand rien n'est saisi, et les écarts d'une saisie contraire — des informations, la saisie reste
   permise. Une seule composition pour l'onglet Matériel (`acal149-devis-retenu`) ET le panneau de l'étape Électrique
   du parcours guidé (`cal-elec-devis-retenu`) : même phrase, même devis. */
export default function DevisRetenu({ retenu, testId = 'acal149-devis-retenu', className = 'flex flex-col gap-1 text-xs text-muted-foreground', classeEcart = 'text-info' }) {
  const option = retenu.option === 'avec' ? 'avec batterie' : 'sans batterie'
  const morceaux = [
    retenu.onduleur?.designation,
    retenu.nombre_onduleurs ? `${retenu.nombre_onduleurs} onduleur${retenu.nombre_onduleurs > 1 ? 's' : ''}` : null,
    retenu.longueur_chaine ? `chaînes de ${retenu.longueur_chaine} modules` : null,
  ].filter(Boolean)
  return (
    <div className={className} data-testid={testId}>
      <p>{`Repris du devis ${retenu.reference} (option ${option})${morceaux.length ? ` : ${morceaux.join(' · ')}` : ''}.`}</p>
      {(retenu.ecarts ?? []).map((ecart) => (
        <p key={ecart} className={classeEcart}>{`Écart avec le devis — ${ecart}`}</p>
      ))}
    </div>
  )
}
