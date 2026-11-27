import { Champ } from './SecoursBatterie'

/* ============================================================================
   ACAL791 — LES TROIS SEUILS DE PROTECTION DE LA BATTERIE D'UN SITE HORS RÉSEAU
   (mode expert, site coché « hors réseau »). Trois pourcentages de la capacité
   utile, jamais préremplis : sans seuil enregistré la banque se décharge
   jusqu'à vide et le résultat le dit (`hors_reseau.mentions`). Un refus du
   serveur se lit sous le seuil fautif (`hors_reseau.seuils.<seuil>`).
   ========================================================================== */

const SEUILS = [
  { cle: 'veille_pct', libelle: 'Mise en veille (% de la capacité utile)' },
  { cle: 'entretien_pct', libelle: 'Recharge d’entretien (% de la capacité utile)' },
  { cle: 'arret_pct', libelle: 'Arrêt complet (% de la capacité utile)' },
]

export default function SeuilsHorsReseau({ seuils, erreurs = {}, onChange }) {
  return (
    <div className="flex flex-col gap-2" data-testid="acal791-seuils">
      <p className="text-sm font-semibold">Seuils de protection de la batterie</p>
      <p className="text-xs text-muted-foreground">
        Trois niveaux de charge, du plus haut au plus bas : veille, recharge d’entretien, arrêt.
        Sans seuil, la batterie se décharge jusqu’à vide.
      </p>
      {erreurs['hors_reseau.seuils']
        ? <p role="alert" className="text-xs text-destructive" data-testid="acal791-erreur">{erreurs['hors_reseau.seuils']}</p>
        : null}
      <div className="grid grid-cols-1 gap-3">
        {SEUILS.map(({ cle, libelle }) => (
          <Champ
            key={cle}
            id={`acal791-${cle}`}
            libelle={libelle}
            type="number"
            valeur={seuils[cle]}
            refus={erreurs[`hors_reseau.seuils.${cle}`]}
            onChange={(v) => onChange({ ...seuils, [cle]: v })}
          />
        ))}
      </div>
    </div>
  )
}
