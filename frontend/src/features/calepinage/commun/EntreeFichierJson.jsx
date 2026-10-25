/**
 * ENF19 — l'`<input type="file">` JSON MASQUÉ des écrans d'import du calepinage
 * (projet, document de conception) : un bouton visible appelle
 * `entreeRef.current?.click()`, l'entrée elle-même ne s'affiche jamais. Un seul
 * déclencheur de fichier, pas un second widget d'upload par écran.
 */
export default function EntreeFichierJson({ entreeRef, ariaLabel, testid, onChange }) {
  return (
    <input
      ref={entreeRef}
      type="file"
      accept="application/json"
      className="hidden"
      aria-label={ariaLabel}
      data-testid={testid}
      onChange={onChange}
    />
  )
}
