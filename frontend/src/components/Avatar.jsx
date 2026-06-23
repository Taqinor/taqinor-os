/* Avatar employé façon Odoo : initiales colorées par défaut, remplacées par
   la photo de profil quand elle existe. La couleur est dérivée du nom (stable
   pour une même personne). Composant autonome (styles en ligne) pour pouvoir
   l'utiliser partout : entête du lead, carte kanban, listes, sélecteur de
   responsable. */

import { useEffect, useState } from 'react'

// Palette douce, lisible en blanc — une teinte stable par personne.
const PALETTE = [
  '#1d4ed8', '#7c3aed', '#db2777', '#dc2626', '#ea580c',
  '#ca8a04', '#16a34a', '#0d9488', '#0369a1', '#4f46e5',
  '#9333ea', '#be123c', '#b45309', '#15803d', '#0e7490',
]

function initialsOf(name) {
  const parts = String(name ?? '').trim().split(/[\s._-]+/).filter(Boolean)
  if (!parts.length) return '?'
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[1][0]).toUpperCase()
}

function colorOf(name) {
  const s = String(name ?? '')
  let h = 0
  for (const c of s) h = (h * 31 + c.charCodeAt(0)) % 99991
  return PALETTE[h % PALETTE.length]
}

/**
 * @param {string} name  Nom affiché (sert aux initiales, à la couleur, au title)
 * @param {string} [src] URL de la photo (présignée) ; si absente → initiales
 * @param {number} [size] Diamètre en px (défaut 28)
 * @param {string} [title] Infobulle (défaut = name)
 */
export default function Avatar({ name, src, size = 28, title }) {
  // Si l'image échoue à charger (URL expirée, objet supprimé…), on retombe
  // proprement sur les initiales au lieu d'un <img> cassé. On réessaie dès que
  // `src` change (nouvelle photo téléversée → aperçu immédiat).
  const [imgFailed, setImgFailed] = useState(false)
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- réinitialiser l'état d'échec quand src change (aperçu immédiat d'une nouvelle photo)
    setImgFailed(false)
  }, [src])

  const dim = `${size}px`
  const base = {
    width: dim,
    height: dim,
    minWidth: dim,
    borderRadius: '50%',
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'hidden',
    flexShrink: 0,
    userSelect: 'none',
    verticalAlign: 'middle',
  }
  const label = title ?? (name || 'Non assigné')

  if (src && !imgFailed) {
    return (
      <span style={base} title={label}>
        <img
          src={src}
          alt={label}
          onError={() => setImgFailed(true)}
          style={{ width: '100%', height: '100%', objectFit: 'cover' }}
        />
      </span>
    )
  }

  return (
    <span
      style={{
        ...base,
        background: name ? colorOf(name) : '#cbd5e1',
        color: '#fff',
        fontWeight: 700,
        fontSize: `${Math.max(9, Math.round(size * 0.4))}px`,
        lineHeight: 1,
      }}
      title={label}
    >
      {initialsOf(name)}
    </span>
  )
}
