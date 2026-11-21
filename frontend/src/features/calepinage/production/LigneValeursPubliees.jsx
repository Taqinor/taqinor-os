import useResource from '../../../hooks/useResource'
import calepinageApi from '../../../api/calepinageApi'
import { useModeExpert } from '../atelier/modeExpert'
import { estProfilDepart } from '../reglages/profilDepart'

/* ACAL698 — « n réglages utilisent des valeurs publiées, non mesurées sur ce
   chantier (…) · Voir les sources ». Le compte est celui des réglages FIGÉS au
   calcul (`simulation.reglages_utilises`) dont la `reference` commence par le
   préfixe du profil de départ (ACAL405) — jamais un compte de toutes les clés.
   Libellés lus dans le registre servi par `GET parametres/` (clé brute si le
   registre manque). Aucun réglage de ce type : la ligne est ABSENTE. Niveau
   expert. « Voir les sources » ouvre « Réglages utilisés » (`onVoirSources`). */

function libellesDuRegistre(donnees) {
  const registre = donnees?.registre
  const table = {}
  if (registre && typeof registre === 'object') {
    for (const liste of Object.values(registre)) {
      if (!Array.isArray(liste)) continue
      for (const ligne of liste) {
        if (ligne?.cle && typeof ligne.libelle === 'string') table[ligne.cle] = ligne.libelle
      }
    }
  }
  return table
}

function LigneAvecRegistre({ publiees, onVoirSources }) {
  const { data } = useResource(
    () => (calepinageApi.parametres?.get
      ? calepinageApi.parametres.get() : Promise.resolve(null)),
    'registre-parametres',
    { select: (r) => r?.data ?? null },
  )
  const libelles = libellesDuRegistre(data)
  const noms = publiees.map((cle) => libelles[cle] || cle).join(', ')
  return (
    <p className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground" data-testid="acal698-ligne">
      <span data-testid="acal698-texte">
        {publiees.length} {publiees.length > 1 ? 'réglages utilisent' : 'réglage utilise'} des
        valeurs publiées, non mesurées sur ce chantier ({noms})
      </span>
      <button
        type="button"
        className="min-h-11 underline"
        onClick={onVoirSources}
        data-testid="acal698-voir-sources"
      >
        Voir les sources
      </button>
    </p>
  )
}

export default function LigneValeursPubliees({ simulation, onVoirSources }) {
  const [expert] = useModeExpert()
  const reglages = simulation?.reglages_utilises
  const publiees = reglages && typeof reglages === 'object'
    ? Object.keys(reglages).filter((cle) => estProfilDepart(reglages[cle]?.reference))
    : []
  if (!expert || publiees.length === 0) return null
  return <LigneAvecRegistre publiees={publiees} onVoirSources={onVoirSources} />
}
