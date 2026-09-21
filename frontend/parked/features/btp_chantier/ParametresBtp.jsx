import { useEffect, useState } from 'react'
import { Settings2 } from 'lucide-react'
import { Button, toast } from '../../ui'
import btpChantierApi from '../../api/btpChantierApi'
import { frenchError } from '../../lib/frenchError'

/* ============================================================================
   NTCON25 — Réglages BTP de la société (singleton par tenant).
   ----------------------------------------------------------------------------
   Écran ADMIN : le serveur refuse (403) toute écriture non administrateur, et
   la société vient TOUJOURS du jeton, jamais du formulaire. Les deux
   interrupteurs pilotent des guards réels — PPSPS signé avant démarrage
   (NTCON16) et checklist de réception complète (NTCON19) — dont l'effet est
   IMMÉDIAT après enregistrement.

   PÉRIMÈTRE : NTCON25 citait `pages/parametres/ParametresBtpPage.jsx`, hors
   du dossier de ce vertical ; l'écran vit donc dans le module BTP et est
   branché par son propre `module.config.jsx` — aucune écriture hors périmètre.
   ========================================================================== */

const VIDE = {
  delai_reponse_rfi_defaut_jours: 5,
  delai_revue_visa_defaut_jours: 10,
  guard_ppsps_bloquant: true,
  guard_checklist_lot_bloquant: true,
  lots_types_defaut: [],
  taux_penalite_retard_defaut_pmil: '',
}

export default function ParametresBtp() {
  const [reglages, setReglages] = useState(VIDE)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [erreurs, setErreurs] = useState({})

  useEffect(() => {
    let cancelled = false
    btpChantierApi.parametres.get()
      .then((res) => {
        if (cancelled) return
        setReglages({ ...VIDE, ...(res?.data || {}) })
      })
      .catch(() => { if (!cancelled) setReglages(VIDE) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  const maj = (patch) => setReglages((r) => ({ ...r, ...patch }))

  const enregistrer = async (event) => {
    event.preventDefault()
    setSaving(true)
    setErreurs({})
    try {
      const res = await btpChantierApi.parametres.enregistrer({
        delai_reponse_rfi_defaut_jours:
          Number(reglages.delai_reponse_rfi_defaut_jours) || 0,
        delai_revue_visa_defaut_jours:
          Number(reglages.delai_revue_visa_defaut_jours) || 0,
        guard_ppsps_bloquant: Boolean(reglages.guard_ppsps_bloquant),
        guard_checklist_lot_bloquant:
          Boolean(reglages.guard_checklist_lot_bloquant),
        lots_types_defaut: (reglages.lots_types_defaut || []),
        taux_penalite_retard_defaut_pmil:
          reglages.taux_penalite_retard_defaut_pmil === ''
            ? null : reglages.taux_penalite_retard_defaut_pmil,
      })
      setReglages({ ...VIDE, ...(res?.data || {}) })
      toast.success('Réglages BTP enregistrés.')
    } catch (err) {
      const data = err?.response?.data
      if (data && typeof data === 'object' && !Array.isArray(data)) {
        setErreurs(data)
      }
      toast.error(frenchError(err, 'Enregistrement impossible.'))
    } finally {
      setSaving(false)
    }
  }

  const messageErreur = (champ) => {
    const valeur = erreurs?.[champ]
    if (!valeur) return null
    const texte = Array.isArray(valeur) ? valeur.join(' ') : String(valeur)
    return (
      <span role="alert" style={{ color: '#dc2626', fontSize: 12 }}>{texte}</span>
    )
  }

  if (loading) return <p>Chargement…</p>

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        <Settings2 size={20} strokeWidth={1.75} aria-hidden="true" />
        <h1 style={{ fontSize: 18, fontWeight: 600, margin: 0 }}>Réglages BTP</h1>
      </div>

      <form onSubmit={enregistrer} noValidate style={{ display: 'grid', gap: 12, maxWidth: 560 }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <input
            type="checkbox"
            aria-label="Bloquer le démarrage sans PPSPS signé"
            checked={Boolean(reglages.guard_ppsps_bloquant)}
            onChange={(e) => maj({ guard_ppsps_bloquant: e.target.checked })}
          />
          Bloquer le démarrage d&apos;un ordre de sous-traitance sans PPSPS signé
        </label>

        <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <input
            type="checkbox"
            aria-label="Bloquer la réception d'un lot si la checklist est incomplète"
            checked={Boolean(reglages.guard_checklist_lot_bloquant)}
            onChange={(e) => maj({ guard_checklist_lot_bloquant: e.target.checked })}
          />
          Bloquer la réception d&apos;un lot si sa checklist est incomplète
        </label>

        <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          Délai de réponse RFI par défaut (jours ouvrés)
          <input
            type="number"
            step="any"
            aria-label="Délai de réponse RFI par défaut"
            value={reglages.delai_reponse_rfi_defaut_jours}
            onChange={(e) => maj({ delai_reponse_rfi_defaut_jours: e.target.value })}
          />
        </label>
        {messageErreur('delai_reponse_rfi_defaut_jours')}

        <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          Délai de revue de visa par défaut (jours ouvrés)
          <input
            type="number"
            step="any"
            aria-label="Délai de revue de visa par défaut"
            value={reglages.delai_revue_visa_defaut_jours}
            onChange={(e) => maj({ delai_revue_visa_defaut_jours: e.target.value })}
          />
        </label>
        {messageErreur('delai_revue_visa_defaut_jours')}

        <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          Taux de pénalité de retard par défaut (‰/jour)
          <input
            type="number"
            step="any"
            aria-label="Taux de pénalité de retard par défaut"
            value={reglages.taux_penalite_retard_defaut_pmil ?? ''}
            onChange={(e) => maj({ taux_penalite_retard_defaut_pmil: e.target.value })}
          />
        </label>
        {messageErreur('taux_penalite_retard_defaut_pmil')}

        <label style={{ display: 'grid', gap: 4 }}>
          Lots types suggérés par l&apos;assistant (un par ligne)
          <textarea
            rows={5}
            aria-label="Lots types suggérés"
            value={(reglages.lots_types_defaut || []).join('\n')}
            onChange={(e) => maj({
              lots_types_defaut: e.target.value.split('\n'),
            })}
          />
        </label>
        {messageErreur('lots_types_defaut')}

        <div>
          <Button type="submit" disabled={saving}>
            {saving ? 'Enregistrement…' : 'Enregistrer'}
          </Button>
        </div>
      </form>
    </div>
  )
}
