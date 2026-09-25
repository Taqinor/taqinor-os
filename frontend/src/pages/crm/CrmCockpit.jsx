import { useEffect, useMemo, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { useNavigate } from 'react-router-dom'
import { Users, UserPlus, Map as MapIcon } from 'lucide-react'
import { ModuleHero } from '../../ui/module'
import { Badge, Button } from '../../ui'
// NTI18N1 — rollout i18n : premier écran CRM migré (sous-titre du cockpit).
import { useT } from '../../i18n'
import { fetchClients, fetchLeads } from '../../features/crm/store/crmSlice'
import { formatDate, formatNumber } from '../../lib/format'
import { useIsAdminOrResponsable } from '../../hooks/useHasPermission'
import crmApi from '../../api/crmApi'
import CrmInsightsPanel from './leads/CrmInsightsPanel'
import DormantAccountsWidget from './DormantAccountsWidget'
import PortfolioWidget from './dashboard/PortfolioWidget'
import RelancesDuJourWidget from './RelancesDuJourWidget'
import MesStatsRelanceTiles from './MesStatsRelanceTiles'
import AdherenceRelancesPanel from './AdherenceRelancesPanel'
import KpiRelancesPanel from './KpiRelancesPanel'
import PlacementAnciensLeadsCard from './PlacementAnciensLeadsCard'

/* ============================================================================
   ODY15 — Cockpit CRM : porte d'entrée de l'app (ModuleHero VX15 + actions
   rapides + KPI), premier item de `nav.items` (`/crm/cockpit`) — la même
   convention que `nav.items[0].to` déjà lue ailleurs comme « cockpit du
   module » (VX9 AppLauncher, VX10 PinnedApps, VX46 préférence d'atterrissage,
   cf. `pages/preferences/prefs.js:resolveLandingPath`).
   ----------------------------------------------------------------------------
   Aucune écriture, aucun appel réseau dupliqué : les compteurs viennent des
   slices REDUX déjà chargées par les écrans CRM (clients/leads — même patron
   que `Dashboard.jsx`) et le détail KPI réutilise TEL QUEL le panneau
   d'insights existant (VX219/WR9, `leads/CrmInsightsPanel.jsx` — objectifs,
   ROI par source, SLA premier contact). Zéro deuxième implémentation, zéro
   registre d'apps local (ODY1 reste l'unique source « mes apps »).
   ========================================================================== */
// PARAM-CADENCE (décision fondateur 25/09/2026 — « regarde aussi le
// cockpit, que tout soit bien fait maintenant que la cadence est bien
// faite ») — les trois compteurs intermédiaires de la chaîne
// appel → visite → devis → suivi de proposition, absents du cockpit jusqu'ici.
// PERSONNELS (même portée que la file du jour, transparence CKP5 : le
// manager voit les mêmes chiffres). Forme `chaine_commerciale` (contrat
// committé `apps/crm/contract_samples/chaine_commerciale.json`, PACT10) :
// aucun chiffre calculé ici, le serveur sert les comptes et les dates.
const TUILES_CHAINE = [
  { cle: 'joints_sans_devis', titre: 'Joints sans devis', dateChamp: 'joint_le' },
  { cle: 'visites_a_venir', titre: 'Visites à venir', dateChamp: 'visite_prevue_le' },
  { cle: 'devis_a_preparer', titre: 'Devis à préparer', dateChamp: 'prochaine_le' },
]

/** Une ligne « dossier » d'une tuile de la chaîne : nom, date utile de CETTE
 *  tuile, badges d'état servis tels quels par le serveur, lien vers la fiche
 *  lead (même route que les tuiles Clients/Leads actifs ci-dessus). */
function LigneChaineDossier({ lead, dateChamp, navigate }) {
  const date = lead[dateChamp]
  const nom = [lead.prenom, lead.nom].filter(Boolean).join(' ') || `Lead ${lead.id}`
  return (
    <li className="flex flex-wrap items-center gap-1.5 text-sm">
      <a
        href={`/crm/leads?lead=${lead.id}`}
        className="font-medium text-primary underline"
        onClick={(e) => {
          e.preventDefault()
          navigate(`/crm/leads?lead=${lead.id}`)
        }}
      >
        {nom}
      </a>
      {date && <span className="text-muted-foreground">{formatDate(date)}</span>}
      {lead.en_retard && <Badge tone="danger">en retard</Badge>}
      {lead.sans_devis && <Badge tone="warning">sans devis</Badge>}
      {lead.apres_visite && <Badge tone="outline">après visite</Badge>}
    </li>
  )
}

/** Une tuile (« Joints sans devis », « Visites à venir », « Devis à
 *  préparer ») : le total, puis les dossiers servis, puis « et N autres »
 *  si le serveur en a plus que ce qu'il a envoyé — `N` et `limite` viennent
 *  TOUJOURS de la réponse, jamais devinés côté écran. */
function TuileChaine({ cle, titre, data, dateChamp, limite, navigate }) {
  const total = data?.total ?? 0
  const leads = data?.leads ?? []
  const reste = total - leads.length
  return (
    <div className="rounded-lg border border-border bg-card p-3" data-testid={`chaine-tuile-${cle}`}>
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          {titre}
        </span>
        <span
          className="font-display text-lg font-semibold tabular-nums"
          data-testid={`chaine-total-${cle}`}
        >
          {formatNumber(total)}
        </span>
      </div>
      {leads.length === 0 ? (
        <p className="mt-1.5 text-xs text-muted-foreground">Aucun dossier.</p>
      ) : (
        <ul className="mt-1.5 space-y-1">
          {leads.map((lead) => (
            <LigneChaineDossier
              key={lead.id} lead={lead} dateChamp={dateChamp} navigate={navigate}
            />
          ))}
        </ul>
      )}
      {reste > 0 && (
        <p className="mt-1 text-xs text-muted-foreground">
          et {reste} autre{reste > 1 ? 's' : ''} (au-delà des {limite} affichés ici)
        </p>
      )}
    </div>
  )
}

/** « Où en est la chaîne » — au-dessus de la file du jour. Erreur réseau : le
 *  panneau se TAIT (`null`), jamais un cockpit cassé par un widget en plus. */
function ChaineCommercialePanel({ navigate }) {
  const [donnees, setDonnees] = useState(null)
  const [erreur, setErreur] = useState(false)

  useEffect(() => {
    let active = true
    crmApi.getChaineCommerciale()
      .then((r) => { if (active) setDonnees(r.data) })
      .catch(() => { if (active) setErreur(true) })
    return () => { active = false }
  }, [])

  if (erreur || !donnees) return null

  return (
    <div data-testid="chaine-commerciale-panel">
      <h2 className="mb-2 text-sm font-semibold text-foreground">Où en est la chaîne</h2>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {TUILES_CHAINE.map((t) => (
          <TuileChaine
            key={t.cle} cle={t.cle} titre={t.titre} dateChamp={t.dateChamp}
            data={donnees[t.cle]} limite={donnees.limite} navigate={navigate}
          />
        ))}
      </div>
    </div>
  )
}

export default function CrmCockpit() {
  const t = useT()
  const dispatch = useDispatch()
  const navigate = useNavigate()
  const { clients, leads } = useSelector((s) => s.crm)
  // CKP5 (fondateur 2026-09-10) — sert UNIQUEMENT à ordonner les blocs (la
  // vue adhérence est mise en avant admin/responsable), JAMAIS à en cacher
  // un : transparence totale, les deux voient les mêmes chiffres.
  const isResponsableOuAdmin = useIsAdminOrResponsable()

  // VX55 — annule les requêtes en vol au démontage (même patron que
  // ClientList/LeadsPage) : une réponse tardive ne doit jamais écraser
  // l'état d'un autre écran après navigation.
  useEffect(() => {
    const tc = dispatch(fetchClients())
    const tl = dispatch(fetchLeads())
    return () => { tc?.abort?.(); tl?.abort?.() }
  }, [dispatch])

  // Compteurs légers, dérivés des mêmes champs que Dashboard.jsx
  // (`leadsChauds`) : is_archived/perdu, jamais un statut de pipeline
  // STAGES.py (règle #2) — aucune clé de stage n'est lue ici.
  const stats = useMemo(() => {
    const leadsActifs = (leads ?? []).filter((l) => l && !l.is_archived && !l.perdu).length
    return [
      { label: 'Clients', value: formatNumber((clients ?? []).length), to: '/crm' },
      { label: 'Leads actifs', value: formatNumber(leadsActifs), to: '/crm/leads' },
    ]
  }, [clients, leads])

  return (
    <div className="page">
      <ModuleHero
        title="CRM"
        subtitle={t('crm.cockpit.subtitle', null, 'Pistes, clients, activités et carte commerciale')}
        accent="var(--module-accent-azur)"
        actions={(
          <>
            <Button variant="outline" onClick={() => navigate('/crm/leads?new=1')}>
              <UserPlus /> Nouveau lead
            </Button>
            <Button variant="outline" onClick={() => navigate('/crm?new=1')}>
              <Users /> Nouveau client
            </Button>
            <Button variant="outline" onClick={() => navigate('/carte')}>
              <MapIcon /> Carte
            </Button>
          </>
        )}
        kpiSlot={(
          <div className="mt-2 grid grid-cols-2 gap-3 sm:grid-cols-3" data-testid="crm-cockpit-stats">
            {stats.map((s) => (
              <button
                key={s.label}
                type="button"
                onClick={() => navigate(s.to)}
                className="rounded-lg border border-border bg-card p-3 text-left transition-colors hover:bg-muted"
              >
                <span className="block text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  {s.label}
                </span>
                <span className="font-display text-xl font-semibold tabular-nums">{s.value}</span>
              </button>
            ))}
          </div>
        )}
      />

      <div className="mt-2">
        <CrmInsightsPanel />
      </div>

      {/* CKP4 — tuiles PERSO (jamais comparatives) : à faire maintenant / mon
          à-l'heure 7 j / série sans retard. Visibles à TOUS les rôles. */}
      <div className="mt-4">
        <MesStatsRelanceTiles />
      </div>

      {/* PARAM-CADENCE (décision fondateur 25/09/2026) — les trois
          compteurs de la chaîne AU-DESSUS de la file du jour : avant même
          d'ouvrir la file, savoir où en est chaque dossier de la chaîne
          appel → visite → devis. */}
      <div className="mt-4">
        <ChaineCommercialePanel navigate={navigate} />
      </div>

      {/* CKP4 — LA FILE d'abord, EN TÊTE et pleine largeur, pour TOUS les
          rôles (« moi et Meryem on voit la même chose ») : c'est l'écran
          opérationnel du jour, jamais relégué à une colonne parmi d'autres. */}
      <div className="mt-4">
        <RelancesDuJourWidget />
      </div>

      {/* CKP5 — vue ADHÉRENCE (stratégique) : visible par TOUS les rôles
          (décision transparence, jamais cachée) ; mise en avant PLEINE
          LARGEUR juste après la file pour admin/responsable — un rôle normal
          la retrouve plus bas, dans la grille, jamais masquée. */}
      {isResponsableOuAdmin && (
        <div className="mt-4">
          <AdherenceRelancesPanel />
        </div>
      )}

      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <KpiRelancesPanel />
        {/* MRY33 — la carte se gate elle-même aux rôles responsable/admin
            (`useIsAdminOrResponsable`, `null` sinon) — même esprit que le
            badge « vient de la pub » de `IdentityRail.jsx`. */}
        <PlacementAnciensLeadsCard />
        <DormantAccountsWidget />
        <PortfolioWidget />
        {!isResponsableOuAdmin && <AdherenceRelancesPanel />}
      </div>
    </div>
  )
}
