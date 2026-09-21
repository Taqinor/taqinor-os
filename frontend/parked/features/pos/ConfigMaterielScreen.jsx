import { useEffect, useState } from 'react'
import posApi from '../../api/posApi'
import { Button, Input, Label, Switch, toast } from '../../ui'

/* XPOS18 — Configuration matériel comptoir (route /pos/config-materiel).
   Imprimante réseau ESC/POS : IP, port (9100 par défaut), activation. Une
   config par société — création si absente, mise à jour sinon. Non renseignée
   = aucun envoi réseau (le backend ne tente rien sans IP + active). */
export default function ConfigMaterielScreen() {
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [configId, setConfigId] = useState(null)
  const [ip, setIp] = useState('')
  const [port, setPort] = useState('9100')
  const [active, setActive] = useState(false)

  useEffect(() => {
    posApi.getConfigMateriel()
      .then((r) => {
        const data = r?.data?.results ?? r?.data ?? []
        const cfg = Array.isArray(data) ? data[0] : data
        if (cfg && cfg.id) {
          setConfigId(cfg.id)
          setIp(cfg.imprimante_ip || '')
          setPort(String(cfg.imprimante_port ?? 9100))
          setActive(!!cfg.imprimante_active)
        }
      })
      .catch(() => { /* pas de config → formulaire vierge */ })
      .finally(() => setLoading(false))
  }, [])

  const handleEnregistrer = async () => {
    setBusy(true)
    const payload = {
      imprimante_ip: ip.trim(),
      imprimante_port: Number(port) || 9100,
      imprimante_active: active,
    }
    try {
      if (configId) {
        await posApi.updateConfigMateriel(configId, payload)
      } else {
        const res = await posApi.createConfigMateriel(payload)
        setConfigId(res.data.id)
      }
      toast.success('Configuration enregistrée.')
    } catch {
      toast.error("L'enregistrement a échoué.")
    } finally {
      setBusy(false)
    }
  }

  if (loading) {
    return (
      <div className="p-4 py-8 text-center text-sm text-muted-foreground sm:p-6">Chargement…</div>
    )
  }

  return (
    <div className="flex flex-col gap-4 p-4 sm:p-6">
      <h1 className="font-display text-xl font-semibold">Matériel de caisse</h1>
      <form
        noValidate
        onSubmit={(e) => { e.preventDefault(); handleEnregistrer() }}
        className="grid max-w-md gap-4 rounded-lg border border-border bg-card p-4"
      >
        <p className="text-sm text-muted-foreground">
          Imprimante à tickets réseau (ESC/POS). Sans IP renseignée et active,
          aucun envoi n'est tenté — le ticket reste disponible en PDF.
        </p>
        <div className="grid gap-1.5">
          <Label htmlFor="cfg-ip">Adresse IP de l'imprimante</Label>
          <Input id="cfg-ip" value={ip} onChange={(e) => setIp(e.target.value)}
                 placeholder="192.168.1.50" />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="cfg-port">Port</Label>
          <Input id="cfg-port" type="number" step="any" value={port}
                 onChange={(e) => setPort(e.target.value)} placeholder="9100" />
        </div>
        <div className="flex items-center justify-between">
          <Label htmlFor="cfg-active">Imprimante active</Label>
          <Switch id="cfg-active" checked={active} onCheckedChange={setActive}
                  aria-label="Activer l'imprimante" />
        </div>
        <div className="flex justify-end">
          <Button type="submit" loading={busy}>Enregistrer</Button>
        </div>
      </form>
    </div>
  )
}
