import { useState } from 'react'

/* État commun des pages de réglages « un formulaire / un singleton » (Achats,
   Gammes & marques, Réglages UX) : id du singleton, valeurs du formulaire,
   chargement, enregistrement en cours et mise à jour d'un champ. */
export default function useFormulaireReglages(emptyForm) {
  const [id, setId] = useState(null)
  const [form, setForm] = useState(emptyForm)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const setField = (k, v) => setForm((f) => ({ ...f, [k]: v }))
  return { id, setId, form, setForm, loading, setLoading, saving, setSaving, setField }
}
