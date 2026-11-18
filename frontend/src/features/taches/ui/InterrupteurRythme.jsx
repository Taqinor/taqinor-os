/* L'interrupteur « Comprendre mon rythme » : le MÊME bouton à Réglages (Vie privée) et à l'écran Rythme. */
export default function InterrupteurRythme({ allume, onBasculer }) {
  return (
    <button
      type="button"
      className="interrupteur"
      role="switch"
      aria-checked={allume}
      aria-label="Comprendre mon rythme"
      onClick={() => onBasculer(!allume)}
    />
  )
}
