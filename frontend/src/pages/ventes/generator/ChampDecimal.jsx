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

export default function ChampDecimal({ value, onValeur, natif = false, className, ...props }) {
  const [texte, setTexte] = useState(() => enTexte(value))
  const [illisible, setIllisible] = useState(false)
  const recu = useRef(value)
  // Une valeur changée HORS de la frappe (rechargement, recomposition) prend
  // la place du texte ; l'écho de la frappe elle-même (même nombre) ne le
  // réécrit jamais.
  useEffect(() => {
    if (recu.current === value) return
    recu.current = value
    setTexte((t) => (memeNombre(t, value) ? t : enTexte(value)))
    setIllisible(false)
  }, [value])

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
