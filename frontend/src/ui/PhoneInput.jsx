import { useState } from 'react'
import { Input } from './Input'
import {
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from './Select'
import { normalizePhoneE164 } from '../lib/format'

/* ============================================================================
   NTI18N24 — Champ téléphone international, au-delà du format marocain.
   ----------------------------------------------------------------------------
   Jusqu'ici chaque écran formatait un téléphone en MAROCAIN UNIQUEMENT
   (`format.js formatPhoneMA`/`normalizeMaPhone`). Ce composant accepte un
   indicatif pays sélectionnable (drapeau + code) : quand la société n'est
   PAS marocaine (`packPays` ≠ 'MA'), OU quand un indicatif est explicitement
   TAPÉ dans le champ (« +33… »), le numéro n'est jamais rejeté ni tronqué
   comme un numéro marocain — critère d'acceptation littéral de la tâche.

   Le champ texte reste un PASSE-PLAT DIRECT `value`/`onChange` en TOUTE
   circonstance (jamais de frappe interceptée, découpée ou tronquée) — c'est
   ce qui garantit qu'un numéro étranger n'est jamais rejeté : le sélecteur
   de pays est un accessoire de LECTURE (il DÉTECTE l'indicatif déjà présent
   dans la valeur pour l'afficher, drapeau + code) et un raccourci d'écriture
   (le choisir PRÉFIXE l'indicatif une fois pour un champ encore vide/local,
   jamais une réécriture forcée d'une valeur déjà internationale).

   Comportement marocain par défaut INCHANGÉ : sans indicatif tapé/choisi, le
   blur ne reformate RIEN (aucun nouveau comportement introduit pour ce cas —
   `formatPhoneMA` reste, comme avant, un formatage d'AFFICHAGE ailleurs dans
   l'app, jamais appliqué ici). Le formatage E.164 (délégué à
   `normalizePhoneE164`, déjà porté du backend — WJ64/DIASPORA) n'intervient
   qu'À L'ENREGISTREMENT (`onBlur`) sur un numéro portant un indicatif
   explicite, jamais en direct pendant la frappe.
   ========================================================================== */

// Liste volontairement courte (marchés effectivement adressés) — extensible
// sans casser l'existant : ajouter une entrée suffit, jamais de nouveau prop.
const PAYS = [
  { code: 'MA', dial: '212', drapeau: '🇲🇦', label: 'Maroc' },
  { code: 'FR', dial: '33', drapeau: '🇫🇷', label: 'France' },
  { code: 'ES', dial: '34', drapeau: '🇪🇸', label: 'Espagne' },
  { code: 'SN', dial: '221', drapeau: '🇸🇳', label: 'Sénégal' },
  { code: 'CI', dial: '225', drapeau: '🇨🇮', label: "Côte d'Ivoire" },
]

// Le plus LONG indicatif correspondant gagne (ex. 225 avant un éventuel 22).
function detecterPays(value) {
  const brut = String(value || '').trim()
  if (!brut.startsWith('+')) return null
  const digits = brut.replace(/\D/g, '')
  return [...PAYS]
    .filter((p) => p.code !== 'MA')
    .sort((a, b) => b.dial.length - a.dial.length)
    .find((p) => digits.startsWith(p.dial)) || null
}

function paysParDefaut(packPays) {
  return PAYS.find((p) => p.code === packPays) || PAYS[0]
}

export default function PhoneInput({
  value, onChange, packPays = 'MA', id, placeholder, disabled, className, ...props
}) {
  const brut = String(value ?? '')

  // Un indicatif explicitement TAPÉ prime toujours (jamais besoin d'attendre
  // que `packPays` change côté société) ; sinon un choix manuel du sélecteur
  // (état local, jamais resynchronisé par effet — pas de useEffect ici) ;
  // sinon `packPays`.
  const [paysChoisi, setPaysChoisi] = useState(null)
  const paysDetecte = detecterPays(brut)
  const pays = paysDetecte || paysChoisi || paysParDefaut(packPays)
  const international = pays.code !== 'MA'

  const handlePaysChange = (code) => {
    const suivant = PAYS.find((p) => p.code === code) || PAYS[0]
    setPaysChoisi(suivant)
    // Un indicatif DÉJÀ présent dans la valeur n'est jamais réécrit — le
    // sélecteur ne fait que préfixer un champ encore local/vide.
    if (suivant.code === 'MA' || brut.trim().startsWith('+')) return
    const chiffres = brut.replace(/\D/g, '')
    onChange?.(chiffres ? `+${suivant.dial}${chiffres}` : `+${suivant.dial}`)
  }

  // TOUJOURS un passe-plat direct — aucune frappe interceptée/tronquée,
  // c'est ce qui garantit qu'un numéro étranger n'est jamais rejeté.
  const handleChange = (e) => onChange?.(e.target.value)

  const handleBlur = (e) => {
    props.onBlur?.(e)
    // Comportement marocain historique : AUCUN reformatage forcé ici.
    if (!brut.trim().startsWith('+')) return
    const e164 = normalizePhoneE164(brut)
    if (e164) onChange?.(`+${e164}`)
  }

  return (
    <div className={`flex gap-2 ${className || ''}`}>
      <Select value={pays.code} onValueChange={handlePaysChange} disabled={disabled}>
        <SelectTrigger className="w-[104px] shrink-0" aria-label="Indicatif pays">
          <SelectValue>{`${pays.drapeau} +${pays.dial}`}</SelectValue>
        </SelectTrigger>
        <SelectContent>
          {PAYS.map((p) => (
            <SelectItem key={p.code} value={p.code}>
              {p.drapeau} {p.label} (+{p.dial})
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <Input
        {...props}
        id={id}
        type="tel"
        inputMode="tel"
        disabled={disabled}
        placeholder={placeholder || (international ? `+${pays.dial} 6 12 34 56 78` : '06 12 34 56 78')}
        value={brut}
        onChange={handleChange}
        onBlur={handleBlur}
        className="flex-1"
      />
    </div>
  )
}
