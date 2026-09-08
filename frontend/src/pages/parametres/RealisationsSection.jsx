// Onglet « Réalisations » de la page Paramètres (ordre fondateur 08/09/2026).
// Catalogue des installations RÉELLES de la société : c'est ici que se remplit
// la preuve envoyée par la touche J4 du suivi après devis (« Voici une
// installation comparable à la vôtre… »). Le serveur y choisit tout seul celle
// de la ville du lead — cet écran ne fait que tenir le catalogue à jour.
//
// Deux règles portées jusque dans le formulaire :
//   * une réalisation = UNE installation réelle (jamais un montage) ;
//   * aucun chiffre par défaut : puissance et mois de mise en service restent
//     VIDES tant qu'ils ne sont pas connus, et la phrase qui les porterait est
//     simplement omise du message.
// Section autonome (comme ReferentielsSection) : elle charge ses données et
// écrit via parametresApi. L'écriture est réservée admin/responsable côté
// serveur (403 sinon).
import { useEffect, useState } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import parametresApi from '../../api/parametresApi'
import { Card, CardContent, Input, Button, IconButton, Switch, Spinner, Badge } from '../../ui'
import { SectionTitle } from './peComponents'
import { toast } from '../../ui/confirm'

// Icône (chemins bruts) de la section — un toit et un rayon.
const REAL_ICON = <><path d="M3 11l9-8 9 8" /><path d="M5 10v10h14V10" /><path d="M10 20v-6h4v6" /></>

const MOIS_FR = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin',
  'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre']

// Extrait la liste d'un retour DRF (liste nue ou { results: [...] }).
const asList = (data) => (Array.isArray(data) ? data : (data?.results ?? []))

// « 2026-07-01 » → « juillet 2026 ». Une date absente ou illisible ne rend
// RIEN : on n'affiche jamais un mois approximatif. Non exporté (règle
// react-refresh : ce fichier n'exporte que son composant).
function moisFrancais(valeur) {
  const m = /^(\d{4})-(\d{2})/.exec(valeur ?? '')
  if (!m) return ''
  const mois = MOIS_FR[Number(m[2]) - 1]
  return mois ? `${mois} ${m[1]}` : ''
}

const BROUILLON_VIDE = {
  titre: '', ville: '', puissance_kwc: '', mois: '', url_page: '', lien_suivi: '',
}

export default function RealisationsSection() {
  const [rows, setRows] = useState(null)
  const [draft, setDraft] = useState(BROUILLON_VIDE)

  const load = () => parametresApi.getRealisations()
    .then(r => setRows(asList(r.data))).catch(() => setRows([]))
  useEffect(() => { load() }, [])

  const set = (champ) => (e) =>
    setDraft(d => ({ ...d, [champ]: e.target.value }))

  const create = async () => {
    if (!draft.titre.trim() || !draft.ville.trim() || !draft.url_page.trim()) return
    // Seuls les champs RENSEIGNÉS partent : un champ vide reste vide côté
    // serveur (null), il ne prend pas une valeur par défaut inventée.
    const payload = {
      titre: draft.titre.trim(),
      ville: draft.ville.trim(),
      url_page: draft.url_page.trim(),
      lien_suivi: draft.lien_suivi.trim(),
    }
    if (draft.puissance_kwc.trim()) payload.puissance_kwc = draft.puissance_kwc.trim()
    if (draft.mois) payload.mise_en_service = `${draft.mois}-01`
    try {
      await parametresApi.createRealisation(payload)
      setDraft(BROUILLON_VIDE)
      load()
    } catch (e) {
      toast.error(e?.response?.data?.detail ?? 'Création impossible.')
    }
  }

  const toggle = async (row) => {
    try { await parametresApi.updateRealisation(row.id, { actif: !row.actif }); load() }
    catch (e) { toast.error(e?.response?.data?.detail ?? 'Modification impossible.') }
  }
  const remove = async (row) => {
    try { await parametresApi.deleteRealisation(row.id); load() }
    catch (e) { toast.error(e?.response?.data?.detail ?? 'Suppression impossible.') }
  }

  return (
    <Card>
      <CardContent className="space-y-3 pt-4">
        <SectionTitle icon={REAL_ICON} label="Réalisations" />
        <p className="text-sm text-muted-foreground">
          Vos installations réelles, une par ligne, avec le lien de leur page
          publique. Le message de suivi « Voici une installation comparable à
          la vôtre » choisit automatiquement celle de la ville du prospect (à
          défaut, la plus proche) et joint ce lien. La puissance et le mois de
          mise en service restent vides tant qu'ils ne sont pas connus : la
          phrase concernée est alors omise, jamais complétée au hasard.
        </p>
        {rows === null ? <Spinner /> : (
          <div className="space-y-2" data-testid="realisations-liste">
            {rows.length === 0 && (
              <p className="text-sm text-muted-foreground">
                Aucune réalisation enregistrée. Tant que ce catalogue est vide,
                le message de suivi n'annonce aucun chantier comparable.
              </p>
            )}
            {rows.map(row => (
              <div key={row.id} className="flex items-center gap-3 border rounded-md px-3 py-2">
                <div className="flex-1 min-w-0">
                  <div className="font-medium flex items-center gap-2">
                    {row.titre}
                    {!row.actif && <Badge>Inactive</Badge>}
                  </div>
                  <div className="text-sm text-muted-foreground truncate">
                    {row.ville}
                    {moisFrancais(row.mise_en_service)
                      ? ` — mise en service ${moisFrancais(row.mise_en_service)}`
                      : ''}
                    {row.puissance_kwc ? ` — ${row.puissance_kwc} kWc` : ''}
                  </div>
                  <div className="text-xs text-muted-foreground truncate">
                    {row.url_page}
                  </div>
                </div>
                <Switch checked={row.actif} onCheckedChange={() => toggle(row)}
                  aria-label="Active" />
                <IconButton title="Supprimer" onClick={() => remove(row)}>
                  <Trash2 size={16} />
                </IconButton>
              </div>
            ))}
          </div>
        )}
        <div className="grid gap-2 sm:grid-cols-2 pt-2" data-testid="realisation-formulaire">
          <Input placeholder="Titre (ex. Villa à Bouskoura)" value={draft.titre}
            onChange={set('titre')} aria-label="Titre" />
          <Input placeholder="Ville" value={draft.ville}
            onChange={set('ville')} aria-label="Ville" />
          <Input placeholder="Puissance en kWc (facultatif)" value={draft.puissance_kwc}
            onChange={set('puissance_kwc')} aria-label="Puissance en kWc" inputMode="decimal" />
          <Input type="month" value={draft.mois}
            onChange={set('mois')} aria-label="Mois de mise en service" />
          <Input placeholder="Lien de la page publique" value={draft.url_page}
            onChange={set('url_page')} aria-label="Lien de la page publique" />
          <Input placeholder="Lien de suivi de production (facultatif)" value={draft.lien_suivi}
            onChange={set('lien_suivi')} aria-label="Lien de suivi de production" />
          <div className="sm:col-span-2">
            <Button onClick={create}><Plus size={16} /> Ajouter la réalisation</Button>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
