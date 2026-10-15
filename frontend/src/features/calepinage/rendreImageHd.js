/* Rendu haute résolution hors écran PARTAGÉ (export PNG, carte de chaleur) :
   `builderApi.renderImageHd(scale)` du builder, jamais d'exception — soit
   `{ rendu }`, soit `{ echec: { ok: false, motif } }` que l'écran affiche tel
   quel. `motifEchec` dit l'échec du rendu ; `motifVide` celui d'une scène non
   rendable (3D indisponible). */
export async function rendreImageHd(builderApi, scale, { motifEchec, motifVide }) {
  const api = builderApi?.current ?? builderApi
  if (!api || typeof api.renderImageHd !== 'function') {
    return { echec: { ok: false, motif: 'Outil non prêt — ouvrez la conception puis réessayez.' } }
  }
  let rendu = null
  try {
    rendu = await api.renderImageHd(scale)
  } catch {
    return { echec: { ok: false, motif: motifEchec } }
  }
  if (!rendu || !rendu.blob) {
    return { echec: { ok: false, motif: motifVide } }
  }
  return { rendu }
}
