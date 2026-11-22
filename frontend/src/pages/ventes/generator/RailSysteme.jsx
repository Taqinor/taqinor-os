// R2-21 — le bloc « Système » du rail suit l'OPTION affichée (kWc facturé et
// panneaux de CETTE option), jamais le seul champ « panneaux » de la branche
// sans batterie sous un total « avec batterie ». Sans ligne panneau : repli
// sur la cible tapée (comportement d'avant). Extrait de `DevisGenerator.jsx`
// (garde de forme C20 : fichier-mur) — le rendu est INCHANGÉ.
import { formatNumber } from '../../../lib/format'
import { comptePanneauxOption } from '../../../features/ventes/solar'

const ligneSysteme = ({ kwc, n }) => (
  `${kwc > 0 ? `${formatNumber(kwc, { decimals: 2 })} kWc` : '— kWc'}`
  + `${n > 0 ? ` · ${n} panneaux` : ''}`)

export default function RailSysteme({
  lines, produits, kwp, kwpLignes, kwpAvec, nbPanneaux,
  showSans, showAvec, agricole = false, optionArgent,
}) {
  const systemeOption = (opt) => {
    const n = comptePanneauxOption(lines, opt, produits)
    const k = opt === 'avec' ? kwpAvec : kwpLignes
    return { kwc: k > 0 ? k : kwp, n: n > 0 ? n : (parseInt(nbPanneaux) || 0) }
  }
  const sSans = systemeOption('sans')
  const sAvec = systemeOption('avec')
  const deuxLignes = showSans && showAvec && !agricole
    && (sSans.n !== sAvec.n || Math.abs(sSans.kwc - sAvec.kwc) > 1e-9)
  if (deuxLignes) {
    return (
      <div className="text-sm text-foreground" data-testid="gen-rail-systeme">
        <div>Sans batterie : {ligneSysteme(sSans)}</div>
        <div>Avec batterie : {ligneSysteme(sAvec)}</div>
      </div>
    )
  }
  return (
    <div className="text-sm text-foreground" data-testid="gen-rail-systeme">
      {ligneSysteme(optionArgent === 'avec' ? sAvec : sSans)}
    </div>
  )
}
