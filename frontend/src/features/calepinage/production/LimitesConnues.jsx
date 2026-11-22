/* ACAL750 — « Limites connues de cette simulation » : l'encadré replié, en bas
   de l'onglet Pertes (niveau expert). D'abord la liste SERVIE
   (`cascade.limites_connues[].texte_fr`), puis les étapes non comptées avec
   leur `motif_omission` servi. Rien n'est écrit ici : sans limites servies,
   seules les étapes omises ; sans aucune des deux, aucun encadré. */

export default function LimitesConnues({ cascade }) {
  const limites = Array.isArray(cascade?.limites_connues) ? cascade.limites_connues : []
  const omises = (Array.isArray(cascade?.etapes) ? cascade.etapes : [])
    .filter((e) => e?.motif_omission)
  if (limites.length === 0 && omises.length === 0) return null
  return (
    <details className="rounded-md border border-border/60 p-3 text-sm" data-testid="acal750-limites">
      <summary className="min-h-11 cursor-pointer font-medium">
        Limites connues de cette simulation
      </summary>
      {limites.length > 0 && (
        <ul className="mt-1 list-disc pl-5" data-testid="acal750-liste">
          {limites.map((l) => <li key={l.code}>{l.texte_fr}</li>)}
        </ul>
      )}
      {omises.length > 0 && (
        <>
          <p className="mt-2 font-medium">Étapes non comptées :</p>
          <ul className="list-disc pl-5" data-testid="acal750-omises">
            {omises.map((e) => (
              <li key={e.etape}>{`${e.libelle || e.etape} — ${e.motif_omission}`}</li>
            ))}
          </ul>
        </>
      )}
    </details>
  )
}
