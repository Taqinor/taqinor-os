import { useState } from 'react'
import { useSelector } from 'react-redux'
import { Building2 } from 'lucide-react'
import api from '../../api/axios'

/**
 * XPLT19 — Sélecteur de société active (accès multi-sociétés).
 *
 * Ne s'affiche QUE si l'utilisateur peut opérer PLUSIEURS sociétés
 * (`societes_operables` de /auth/me/ contient 2+ entrées) : un compte
 * mono-société ne voit rien — comportement inchangé. Le changement appelle
 * POST /auth/switch-company/ (autorisé membre uniquement, journalisé côté
 * serveur) qui pose de nouveaux cookies JWT portant la société active, puis
 * recharge l'application pour re-scoper toutes les données proprement.
 */
export default function CompanySwitcher() {
  const user = useSelector((state) => state.auth.user)
  const [busy, setBusy] = useState(false)

  const societes = user?.societes_operables || []
  if (societes.length < 2) return null

  const activeId = user?.active_company_id

  const handleChange = async (e) => {
    const companyId = Number(e.target.value)
    if (!companyId || companyId === activeId || busy) return
    setBusy(true)
    try {
      await api.post('/auth/switch-company/', { company_id: companyId })
      // Les nouveaux cookies (claim société active) sont posés : on recharge
      // pour que TOUTES les données affichées soient celles de la nouvelle
      // entité — jamais un mélange de deux sociétés à l'écran.
      window.location.reload()
    } catch {
      setBusy(false)
    }
  }

  return (
    <label className="header-company-switcher" title="Société active">
      <Building2 size={15} aria-hidden="true" />
      <select
        aria-label="Changer de société active"
        value={activeId ?? ''}
        onChange={handleChange}
        disabled={busy}
      >
        {societes.map((s) => (
          <option key={s.id} value={s.id}>{s.nom}</option>
        ))}
      </select>
    </label>
  )
}
