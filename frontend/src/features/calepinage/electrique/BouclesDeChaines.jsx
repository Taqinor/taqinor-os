/* ACAL685 — « Boucles de câblage » du verdict électrique : une ligne par chaîne, les nombres et les phrases
   servis par `evaluerElectrique` (`boucles_dc[]`, ACAL677/678). L'écran ne compare ni ne calcule rien : le mot
   « au-dessus » vient de `depasse`, la cause d'un nombre absent de `indetermine`. */
const nombreFr = (v) => new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 1 }).format(Number(v))

function phraseBoucle(b) {
  const causes = Array.isArray(b.indetermine) ? b.indetermine.join(' ; ') : ''
  if (b.surface_m2 == null) return `Chaîne ${b.chaine} : surface non calculable : ${causes}`
  const source = b.limite_source === 'societe' ? ' fixée par la société' : b.limite_source ? ` (source : ${b.limite_source})` : ''
  const limite = b.limite_m2 == null ? 'limite non saisie' : `limite de ${nombreFr(b.limite_m2)} m²${source}`
  const phrase = `Chaîne ${b.chaine} : boucle de ${nombreFr(b.surface_m2)} m², ${limite}`
  const reste = b.limite_m2 == null && causes ? ` — ${causes}` : ''
  return `${phrase}${b.depasse === true ? ' — au-dessus' : ''}${reste}`
}

export default function BouclesDeChaines({ boucles }) {
  if (!Array.isArray(boucles) || boucles.length === 0) return null
  return (
    <details className="flex flex-col gap-2" data-testid="acal685-boucles">
      <summary className="min-h-11 cursor-pointer py-2 text-sm font-semibold">Boucles de câblage</summary>
      <ul className="flex flex-col gap-2 text-sm">
        {boucles.map((b) => (
          <li key={b.chaine} className="min-h-11" data-testid={`acal685-ligne-${b.chaine}`}>{phraseBoucle(b)}</li>
        ))}
      </ul>
    </details>
  )
}
