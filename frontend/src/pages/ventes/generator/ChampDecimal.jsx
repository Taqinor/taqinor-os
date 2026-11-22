// R1-09 / R1-10 (recette 22/11/2026, décision Q1) — LE CHAMP NOMBRE DU
// GÉNÉRATEUR, À LA FRANÇAISE.
// ---------------------------------------------------------------------------
// Un champ natif de type « number » laisse le NAVIGATEUR filtrer la frappe : un Chrome
// dont l'interface est en anglais ou en arabe avale la virgule et l'espace —
// « 12,5 » devenait 125, « 4 800,50 » devenait 480050, sans un mot. Ce champ
// est un texte à clavier décimal (`inputMode="decimal"`) : il AFFICHE ce que le
// vendeur tape, sans jamais le réécrire sous le curseur, et ne transmet au
// calcul que le nombre LU par `lireSaisieDecimale` (virgule ou point décimal,
// espaces et apostrophe de milliers).
//
// RÈGLE FONDATEUR PRÉSERVÉE : `step="any"` (aucun pas, rien n'est « snappé »),
// aucune borne refusée, le formulaire porteur reste `noValidate`. Une saisie
// illisible n'est ni refusée ni changée en un autre nombre : elle est DITE sous
// le champ, et le calcul garde la dernière valeur lue (nommée dans le message).
// Une valeur venue d'ailleurs (devis rouvert, auto-remplissage) s'affiche
// telle que l'état la porte (point décimal, comme avant).
import { useEffect, useRef, useState } from 'react'
import { Input } from '../../../ui'
import { lireSaisieDecimale } from '../../../lib/format'

const enTexte = (v) => (v === null || v === undefined ? '' : String(v))
const memeNombre = (a, b) => {
  const x = lireSaisieDecimale(a)
  const y = lireSaisieDecimale(b)
  return x.etat === y.etat && x.valeur === y.valeur
}

export default function ChampDecimal({ value, onValeur, natif = false, className, onFocus, onBlur, ...props }) {
  const [texte, setTexte] = useState(() => enTexte(value))
  const [illisible, setIllisible] = useState(false)
  const recu = useRef(value)
  const enFrappe = useRef(false)
  // Une valeur changée HORS de la frappe (rechargement, recomposition) prend
  // la place du texte ; l'écho de la frappe elle-même (même nombre) ne le
  // réécrit jamais.
  useEffect(() => {
    if (recu.current === value) return
    recu.current = value
    // V3-02 — un champ VIDÉ pendant la frappe reste vide : une valeur recalculée
    // (cible kWc re-remplie depuis les panneaux) n'est jamais écrite sous le
    // curseur (« 5,5 » tapé ensuite devenait « 3.555,5 ») ; elle s'affiche à la sortie.
    setTexte((t) => (memeNombre(t, value) || (t === '' && enFrappe.current) ? t : enTexte(value)))
    setIllisible(false)
  }, [value])
  const surEntree = (e) => { enFrappe.current = true; onFocus?.(e) }
  const surSortie = (e) => {
    enFrappe.current = false
    setTexte((t) => (t === '' ? enTexte(value) : t))
    onBlur?.(e)
  }

  const surFrappe = (e) => {
    const brut = e.target.value
    setTexte(brut)
    const lu = lireSaisieDecimale(brut)
    setIllisible(lu.etat === 'illisible')
    if (lu.etat === 'illisible') return
    recu.current = lu.texte
    onValeur(lu.texte)
  }

  const Champ = natif ? 'input' : Input
  const retenu = enTexte(value)
  return (
    <>
      <Champ type="text" inputMode="decimal" step="any" autoComplete="off"
             className={className} value={texte} onChange={surFrappe}
             onFocus={surEntree} onBlur={surSortie}
             aria-invalid={illisible ? 'true' : undefined} {...props} />
      {illisible && (
        <span role="alert" className="block text-xs text-destructive" data-champ-illisible="">
          « {texte} » n’est pas un nombre lisible (ex. 4 800,50) : le calcul garde
          {retenu === '' ? ' un champ vide' : ` ${retenu.replace('.', ',')}`}.
        </span>
      )}
    </>
  )
}
