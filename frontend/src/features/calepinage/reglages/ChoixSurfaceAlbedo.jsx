import albedoSurfaces from './albedoSurfaces.json'

/* ACAL748 — « Remplir depuis une surface (valeur publiée) » : met la valeur,
   la source « texte » et la référence dans la ligne `albedo_mensuel`. Rien
   n'est envoyé : l'enregistrement reste le bouton existant. Données :
   `albedoSurfaces.json` (ACAL747, valeurs uniques imprimées par PVsyst). */

function referenceSurface(s) {
  return `PVsyst — Albedo usual coefficients — ${s.surface} — ${s.url} — lu le ${s.date_lecture}`
    + ' — valeur publiée, non mesurée'
}

export default function ChoixSurfaceAlbedo({ cle, disabled, onChoisir }) {
  const choisir = (e) => {
    const s = albedoSurfaces.surfaces.find((x) => x.surface === e.target.value)
    if (!s) return
    onChoisir('valeurTexte', String(s.valeur))
    onChoisir('source', 'texte')
    onChoisir('reference', referenceSurface(s))
  }
  return (
    <label className="mt-2 block" data-testid={`acal748-choix-${cle}`}>
      <span className="text-xs text-muted-foreground">Remplir depuis une surface (valeur publiée)</span>
      <select value="" disabled={disabled} onChange={choisir}
        className="mt-1 block min-h-11 w-full rounded-md border border-border bg-background px-2 text-sm">
        <option value="">— choisir une surface —</option>
        {albedoSurfaces.surfaces.map((s) => (
          <option key={s.surface} value={s.surface}>{`${s.surface} (${s.valeur})`}</option>
        ))}
      </select>
    </label>
  )
}
