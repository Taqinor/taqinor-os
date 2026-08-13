// NTMOB17 — vignette de galerie respectant le mode « Économie de données ».
// Le composant rend l'UNITÉ CLIQUABLE complète (bouton + image) pour ne jamais
// imbriquer deux éléments interactifs.
// Mode INACTIF : bouton + `<img loading="lazy">` — comportement strictement
// identique à avant pour un utilisateur qui n'a rien activé.
// Mode ACTIF : AUCUN `src` n'est posé tant que l'utilisateur n'a pas tapé la
// vignette, donc le navigateur n'émet aucune requête image (c'est ce que la
// mesure DevTools du critère d'acceptation constate sur un écran chantier à
// 20 photos). Le premier tap CHARGE la vignette, le suivant ouvre la visionneuse.
import { useState } from 'react'
import { ImageOff } from 'lucide-react'
import useDataSaver from '../../hooks/useDataSaver'

export default function DataSaverThumb({ src, alt, className = '', onActivate, title }) {
  const dataSaver = useDataSaver()
  const [revealed, setRevealed] = useState(false)
  const placeholder = dataSaver && !revealed

  return (
    <button
      type="button"
      title={placeholder ? `${title || alt} — appuyez pour charger l'aperçu` : title || alt}
      aria-label={placeholder ? `Charger l'aperçu de ${alt}` : undefined}
      data-datasaver-placeholder={placeholder ? '1' : undefined}
      onClick={() => (placeholder ? setRevealed(true) : onActivate?.())}
    >
      {placeholder ? (
        <span
          className={`flex flex-col items-center justify-center gap-0.5 rounded-md border border-dashed border-border bg-muted text-[10px] leading-tight text-muted-foreground ${className}`}
        >
          <ImageOff className="size-5" aria-hidden="true" />
          <span>Appuyer</span>
        </span>
      ) : (
        <img src={src} alt={alt} loading="lazy" className={className} />
      )}
    </button>
  )
}
