import { formatNumber } from '../../../lib/format'
import { Champ } from './SecoursBatterie'

/* ============================================================================
   ACAL803 — LE GROUPE D'APPOINT D'UN SITE HORS RÉSEAU.
   ----------------------------------------------------------------------------
   Saisie (mode expert, site coché « hors réseau ») : un interrupteur « Il y a
   un groupe sur le site » puis quatre nombres, jamais préremplis, postés sous
   `hors_reseau.groupe` (ACAL800) ; un refus se lit sous son champ
   (`hors_reseau.groupe.<champ>`).
   Lecture (`BlocHorsReseau`) : `hors_reseau.groupe` (ACAL801) et
   `hors_reseau.banque_mois_charge` (ACAL802), TELS QUE SERVIS — aucun calcul,
   aucun litre, aucun prix. Sans groupe servi : rien ; banque du mois chargé
   nulle : « non calculé » et le motif servi.
   ========================================================================== */

const CHAMPS_GROUPE = [
  { cle: 'puissance_kw', libelle: 'Puissance du groupe (kW)' },
  { cle: 'soc_demarrage_pct', libelle: 'Démarre à (% de charge)' },
  { cle: 'soc_arret_pct', libelle: 'S’arrête à (% de charge)' },
  { cle: 'heures_max_par_jour', libelle: 'Heures de marche maximum par jour' },
]

const connu = (v) => v !== null && v !== undefined && Number.isFinite(Number(v))
const kwh = (v) => (connu(v) ? `${formatNumber(v, { decimals: 0 })} kWh` : 'non calculé')
const heures = (v) => (connu(v) ? `${formatNumber(v)} h` : 'non calculé')

export default function GroupeAppoint({ groupe, erreurs = {}, onChange }) {
  return (
    <div className="flex flex-col gap-2" data-testid="acal803-saisie">
      <label className="flex min-h-11 items-center gap-2 text-sm" htmlFor="acal803-actif">
        <input id="acal803-actif" type="checkbox" className="size-5" checked={groupe.actif}
          onChange={(e) => onChange({ ...groupe, actif: e.target.checked })} />
        Il y a un groupe sur le site
      </label>
      {erreurs['hors_reseau.groupe']
        ? <p role="alert" className="text-xs text-destructive" data-testid="acal803-erreur">{erreurs['hors_reseau.groupe']}</p>
        : null}
      {groupe.actif && (
        <div className="grid grid-cols-1 gap-3">
          {CHAMPS_GROUPE.map(({ cle, libelle }) => (
            <Champ key={cle} id={`acal803-${cle}`} libelle={libelle} type="number"
              valeur={groupe[cle]} refus={erreurs[`hors_reseau.groupe.${cle}`]}
              onChange={(v) => onChange({ ...groupe, [cle]: v })} />
          ))}
        </div>
      )}
    </div>
  )
}

/** La lecture du groupe et de la banque du mois chargé, sous le bloc hors réseau
    (`nomMois` : le libellé de mois du panneau, une seule liste des mois). */
export function LectureGroupe({ horsReseau, nomMois }) {
  const g = horsReseau?.groupe
  const b = horsReseau?.banque_mois_charge
  const motifBanque = horsReseau?.motif_banque_mois_charge
  if (!g && !b && !motifBanque) return null
  return (
    <div className="flex flex-col gap-2 text-sm">
      {g && (
        <>
          <p data-testid="acal803-groupe">
            Le groupe a tourné {heures(g.heures_de_marche)} dans l’année ({kwh(g.energie_fournie_kwh)} fournis)
            {g.cause_inactif ? ` — ${g.cause_inactif}` : ''}
          </p>
          {g.par_mois?.length > 0 && (
            <table className="w-full text-sm" data-testid="acal803-groupe-par-mois">
              <thead>
                <tr className="text-left text-xs text-muted-foreground">
                  <th className="py-1 font-normal">Mois</th>
                  <th className="py-1 text-right font-normal">Heures de marche</th>
                  <th className="py-1 text-right font-normal">Énergie fournie</th>
                </tr>
              </thead>
              <tbody>
                {g.par_mois.map((m) => (
                  <tr key={m.mois} className="border-t border-border/60" data-testid="acal803-groupe-mois">
                    <td className="py-1">{nomMois(m.mois)}</td>
                    <td className="py-1 text-right tabular-nums">{heures(m.heures_de_marche)}</td>
                    <td className="py-1 text-right tabular-nums">{kwh(m.energie_fournie_kwh)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {g.mention && <p className="text-xs text-muted-foreground">{g.mention}</p>}
        </>
      )}
      {(b || motifBanque) && (
        <p data-testid="acal803-banque-mois">
          {b
            ? `Pour le mois le plus chargé (${nomMois(b.mois)}) : banque de ${kwh(b.capacite_utile_kwh)} utiles, `
              + `défaillance ${kwh(b.defaillance_kwh)}`
            : `Banque du mois le plus chargé : non calculé : ${motifBanque}`}
        </p>
      )}
    </div>
  )
}
