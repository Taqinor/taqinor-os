// NTDMO26 — Assistant first-run « Configurez votre société en 5 minutes »
// (société RÉELLE, jamais une société de démonstration — voir
// `features/admin/DemoWizard.jsx` pour l'équivalent démo, NTDMO25).
//
// Auto-déclenché à la première connexion d'un administrateur (fenêtre de 30
// jours depuis `Company.date_creation`, même patron que NTDMO15) — voir le
// petit effet ajouté dans `components/PremiersPasWidget.jsx`, qui navigue ici
// dès que l'item de catalogue `assistant_demarrage` (NTDMO26, ajouté à
// `apps/onboarding/services.py::DEFAULT_ITEMS`) est présent et non fait.
//
// 4 étapes, JAMAIS bloquant : « Passer, je configurerai plus tard » ferme le
// wizard DÉFINITIVEMENT pour cet utilisateur (masque l'item `assistant_
// demarrage` via l'endpoint générique `POST onboarding/progress/{id}/
// ignorer/`, déjà utilisé par le widget « Premiers pas » — aucun nouvel
// endpoint backend). Chaque étape complétée coche directement l'item de
// checklist pertinent (`POST onboarding/progress/{id}/marquer-fait/`, WIR59)
// pour qu'il apparaisse fait dans le widget « Premiers pas » (NTDMO13).
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../../api/axios'
import parametresApi from '../../api/parametresApi'
import stockApi from '../../api/stockApi'
import rolesApi from '../../api/rolesApi'
import { Button, Card, Input } from '../../ui'
import { toast } from '../../ui/confirm'

const STEPS = ['bienvenue', 'societe', 'produit', 'equipe', 'termine']

export default function DemarrageWizard() {
  const navigate = useNavigate()
  const [stepIndex, setStepIndex] = useState(0)
  // Clé (key) de checklist -> id d'``OnboardingProgress`` résolu au chargement
  // (nécessaire pour appeler ignorer/marquer-fait, qui prennent un ID).
  const [itemIds, setItemIds] = useState({})
  const [busy, setBusy] = useState(false)

  const [societe, setSociete] = useState({ nom: '', adresse: '', email: '', telephone: '' })
  const [produit, setProduit] = useState({ nom: '', prix_vente: '' })
  const [roles, setRoles] = useState([])
  const [equipe, setEquipe] = useState({ username: '', email: '', password: '', role: '' })

  useEffect(() => {
    api.get('/onboarding/progress/')
      .then((r) => {
        const map = {}
        for (const it of r.data?.items ?? []) map[it.key] = it.id
        setItemIds(map)
      })
      .catch(() => {})
    parametresApi.getProfile()
      .then((r) => setSociete({
        nom: r.data?.nom ?? '', adresse: r.data?.adresse ?? '',
        email: r.data?.email ?? '', telephone: r.data?.telephone ?? '',
      }))
      .catch(() => {})
    rolesApi.getRoles()
      .then((r) => {
        const list = r.data?.results ?? r.data ?? []
        setRoles(list)
        const defaut = list.find((rr) => rr.nom === 'Utilisateur') ?? list[0]
        if (defaut) setEquipe((e) => ({ ...e, role: defaut.id }))
      })
      .catch(() => {})
  }, [])

  const marquerFait = async (key) => {
    const id = itemIds[key]
    if (!id) return
    try { await api.post(`/onboarding/progress/${id}/marquer-fait/`) } catch { /* non bloquant */ }
  }

  const step = STEPS[stepIndex]
  const goNext = () => setStepIndex((i) => Math.min(i + 1, STEPS.length - 1))

  // « Passer, je configurerai plus tard » — à TOUT moment, ferme le wizard
  // DÉFINITIVEMENT pour cet utilisateur (jamais de réapparition automatique).
  const passer = async () => {
    const id = itemIds.assistant_demarrage
    if (id) {
      try { await api.post(`/onboarding/progress/${id}/ignorer/`) } catch { /* non bloquant */ }
    }
    navigate('/dashboard')
  }

  const terminer = async () => {
    await marquerFait('assistant_demarrage')
    navigate('/dashboard')
  }

  const saveSociete = async () => {
    setBusy(true)
    try {
      await parametresApi.updateProfile(societe)
      await marquerFait('configurer_societe')
      toast.success('Société mise à jour.')
      goNext()
    } catch {
      toast.error('Impossible d\'enregistrer les coordonnées.')
    } finally {
      setBusy(false)
    }
  }

  const saveProduit = async () => {
    if (!produit.nom.trim() || !produit.prix_vente) {
      goNext()
      return
    }
    setBusy(true)
    try {
      await stockApi.createProduit({
        nom: produit.nom.trim(), prix_vente: produit.prix_vente,
      })
      await marquerFait('premier_produit')
      toast.success('Produit ajouté au catalogue.')
      goNext()
    } catch {
      toast.error("Impossible d'ajouter ce produit.")
    } finally {
      setBusy(false)
    }
  }

  const saveEquipe = async () => {
    if (!equipe.username.trim() || !equipe.password) {
      goNext()
      return
    }
    setBusy(true)
    try {
      await api.post('/users/', equipe)
      await marquerFait('inviter_coequipier')
      toast.success('Coéquipier invité.')
      goNext()
    } catch {
      toast.error("Impossible d'inviter ce coéquipier.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="ui-root mx-auto max-w-xl p-4 sm:p-6">
      <Card className="space-y-4 p-6" data-testid="demarrage-wizard">
        <div className="flex items-center justify-between">
          <h1 className="text-lg font-semibold">Configurez votre société en 5 minutes</h1>
          {step !== 'termine' && (
            <button
              type="button"
              onClick={passer}
              className="shrink-0 text-xs font-medium text-muted-foreground hover:text-foreground"
            >
              Passer, je configurerai plus tard
            </button>
          )}
        </div>

        {step === 'bienvenue' && (
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">
              Quatre étapes rapides pour préparer votre espace : coordonnées de
              votre société, premier produit du catalogue, et invitation d'un
              premier coéquipier. Chaque étape est facultative — vous pouvez
              tout configurer plus tard depuis Paramètres.
            </p>
            <Button onClick={goNext}>Commencer</Button>
          </div>
        )}

        {step === 'societe' && (
          <div className="space-y-3">
            <p className="font-medium">1. Coordonnées de la société</p>
            <Input placeholder="Nom de la société" value={societe.nom}
                   onChange={(e) => setSociete((s) => ({ ...s, nom: e.target.value }))} />
            <Input placeholder="Adresse" value={societe.adresse}
                   onChange={(e) => setSociete((s) => ({ ...s, adresse: e.target.value }))} />
            <Input placeholder="Email" value={societe.email}
                   onChange={(e) => setSociete((s) => ({ ...s, email: e.target.value }))} />
            <Input placeholder="Téléphone" value={societe.telephone}
                   onChange={(e) => setSociete((s) => ({ ...s, telephone: e.target.value }))} />
            <div className="flex gap-2">
              <Button variant="ghost" onClick={goNext} disabled={busy}>Passer cette étape</Button>
              <Button onClick={saveSociete} disabled={busy}>Enregistrer et continuer</Button>
            </div>
          </div>
        )}

        {step === 'produit' && (
          <div className="space-y-3">
            <p className="font-medium">2. Premier produit du catalogue</p>
            <Input placeholder="Nom du produit" value={produit.nom}
                   onChange={(e) => setProduit((p) => ({ ...p, nom: e.target.value }))} />
            <Input type="number" step="any" placeholder="Prix de vente (TTC)" value={produit.prix_vente}
                   onChange={(e) => setProduit((p) => ({ ...p, prix_vente: e.target.value }))} />
            <div className="flex gap-2">
              <Button variant="ghost" onClick={goNext} disabled={busy}>Passer cette étape</Button>
              <Button onClick={saveProduit} disabled={busy}>Enregistrer et continuer</Button>
            </div>
          </div>
        )}

        {step === 'equipe' && (
          <div className="space-y-3">
            <p className="font-medium">3. Inviter un premier coéquipier</p>
            <Input placeholder="Nom d'utilisateur" value={equipe.username}
                   onChange={(e) => setEquipe((eq) => ({ ...eq, username: e.target.value }))} />
            <Input placeholder="Email" value={equipe.email}
                   onChange={(e) => setEquipe((eq) => ({ ...eq, email: e.target.value }))} />
            <Input type="password" placeholder="Mot de passe temporaire" value={equipe.password}
                   onChange={(e) => setEquipe((eq) => ({ ...eq, password: e.target.value }))} />
            <select
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={equipe.role}
              onChange={(e) => setEquipe((eq) => ({ ...eq, role: e.target.value }))}
            >
              {roles.map((r) => (
                <option key={r.id} value={r.id}>{r.nom}</option>
              ))}
            </select>
            <div className="flex gap-2">
              <Button variant="ghost" onClick={goNext} disabled={busy}>Passer cette étape</Button>
              <Button onClick={saveEquipe} disabled={busy}>Enregistrer et continuer</Button>
            </div>
          </div>
        )}

        {step === 'termine' && (
          <div className="space-y-3">
            <p className="font-medium">Configuration terminée</p>
            <p className="text-sm text-muted-foreground">
              Vous pouvez à tout moment revenir sur ces réglages depuis
              Paramètres, le catalogue ou la gestion des utilisateurs.
            </p>
            <Button onClick={terminer}>Aller au tableau de bord</Button>
          </div>
        )}
      </Card>
    </div>
  )
}
