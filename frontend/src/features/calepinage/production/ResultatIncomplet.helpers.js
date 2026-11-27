import { estSansSource } from '../reglages/profilDepart'

/* T4-B4-003 — LA source unique des nombres de l'écran (R3-06 : celui du serveur). Toutes les phrases la lisent :
   - `pertes`        : pertes pas encore comptées = `etapes_a_compter − etapes_comptees` (même ensemble que la mention
                       « borne haute »), jamais moins que les lignes listées ;
   - `lignes`        : la part de ces pertes rattachable à un réglage ICI (la liste) ; `autres` = pertes − lignes ;
   - `reglagesVides` : les lignes qui sont des réglages VIDES de la SOCIÉTÉ (ni une donnée de la fiche du panneau, ni un
                       réglage rempli dont le serveur donne la cause : `motif`) ;
   - `remplissables` : les clés de ces réglages pour lesquelles une valeur publiée existe (`estSansSource` : la liste
                       `sans_source` du profil) — ce que « Remplir » (page Démarrage rapide) remplit, et seulement ça. */
export function compteDuResultat(aRenseigner) {
  const lignes = Array.isArray(aRenseigner?.lignes) ? aRenseigner.lignes : []
  const pertes = Math.max((aRenseigner?.etapes_a_compter ?? 0) - (aRenseigner?.etapes_comptees ?? 0), lignes.length)
  // ACAL1934 — une ligne qui porte le `motif` servi est un réglage REMPLI que l'étape ne sait pas lire : pas un « vide ».
  const societe = lignes.filter((l) => l.nature === 'reglage_societe' && !l.motif)
  return {
    pertes,
    lignes: lignes.length,
    autres: pertes - lignes.length,
    reglagesVides: societe.length,
    remplissables: societe.filter((l) => !estSansSource(l.cle)).map((l) => l.cle),
  }
}
