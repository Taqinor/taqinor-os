// TAILLES (fondateur 26/08/2026) — écran vendeur des trois tailles
// Éco / Recommandé / Max (édition complète du devis, DevisGenerator.jsx).
// Contrat : apps/ventes/contract_samples/offres_tailles.json ; endpoints
// backend : apps/ventes/views/devis.py (`offres_tailles`/`offres_tailles_config`/
// `offres_tailles_regenerer`), dérivation dans apps/ventes/offres_tailles.py.
//
// RÈGLE CENTRALE (« zéro chiffre inventé », rep-side final UX — voir le spec
// tiers_design_spec.md § « Rep-side editability ») : ce composant n'ÉDITE que
// la CONFIGURATION d'une taille (nombre de panneaux, banque batterie en
// modules du devis, substitutions catalogue). AUCUN champ dérivé (prix TTC,
// économie, payback, couverture, kWc, production, cumul 25 ans) n'est un
// input — ce sont des valeurs RÉ-ESTAMPILLÉES par le moteur, affichées telles
// que le serveur les renvoie après chaque PATCH/régénération, jamais
// recalculées ni tapées localement. Composant AUTONOME (monté une seule fois
// dans DevisGenerator.jsx) pour ne pas alourdir ce fichier déjà volumineux —
// coordination avec la lane du bouton « Recalculer le dimensionnement »
// (correction #5) : aucune des deux ne touche les mêmes lignes de
// DevisGenerator.jsx au-delà du point de montage.
import { useCallback, useEffect, useState } from 'react'
import { Layers3, Minus, Plus, RefreshCw } from 'lucide-react'
import ventesApi from '../../api/ventesApi'
import {
  Button, IconButton, Card, CardHeader, CardTitle, CardContent,
  Badge, Segmented, Spinner,
} from '../../ui'
import { useConfirmDialog, toast } from '../../ui/confirm'
import { formatMAD, formatNumber } from '../../lib/format'
import { groupProduitsByCategory, PRODUCT_CATEGORIES } from '../../features/ventes/solar'

// Bascule partagée par les trois cartes — même patron que la page client
// (une SEULE bascule au-dessus des cartes, jamais un interrupteur par carte).
const VARIANTES = [
  { value: 'sans', label: 'Sans batterie' },
  { value: 'avec', label: 'Avec batterie' },
]

// { [role]: Produit[] } — catalogue société déjà chargé par DevisGenerator
// (évite un second aller-retour réseau), regroupé par ROLES_AUTO_COMPOSITION
// via le MÊME classement que l'auto-remplissage (`groupProduitsByCategory`).
// Filtré aux produits chiffrés : substituer un produit à 0 MAD ferait
// apparaître une carte gratuite chez le client (même garde que le serveur,
// répétée ici pour ne pas proposer une option qu'il refusera de toute façon).
function produitsParRole(produits) {
  const groups = groupProduitsByCategory(produits || [])
  const parLabel = new Map(groups.map(g => [g.label, g.items]))
  const map = {}
  for (const [role, label] of PRODUCT_CATEGORIES) {
    map[role] = (parLabel.get(label) || []).filter(p => (p.prix_vente || 0) > 0)
  }
  return map
}

// Union des rôles matériel (sans ∪ avec) d'une offre — les seuls rôles pour
// lesquels une substitution a un sens sur CETTE taille.
function rolesDeLOffre(offre) {
  const roles = []
  for (const variante of [offre.sans, offre.avec]) {
    for (const m of (variante && variante.materiel) || []) {
      if (m.role && !roles.includes(m.role)) roles.push(m.role)
    }
  }
  return roles
}

// Aplatit une erreur DRF imbriquée ({config: {equipements: {panneau: [...]}}})
// en liste plate {path: ['config','equipements','panneau'], message}. Les
// messages du serveur sont DÉJÀ en français (OffreTailleConfigSerializer) —
// on les affiche tels quels, jamais un JSON brut (même discipline que
// handleSubmit plus haut dans DevisGenerator.jsx).
function flattenErrors(data, path = []) {
  const out = []
  if (Array.isArray(data)) {
    for (const msg of data) out.push({ path, message: String(msg) })
  } else if (data && typeof data === 'object') {
    for (const [k, v] of Object.entries(data)) out.push(...flattenErrors(v, [...path, k]))
  } else if (data != null) {
    out.push({ path, message: String(data) })
  }
  return out
}

function errorsAt(errors, ...prefix) {
  return errors
    .filter(e => prefix.every((p, i) => e.path[i] === p))
    .map(e => e.message)
}

function StatChamp({ label, value }) {
  if (value == null) return null
  return (
    <div className="flex items-baseline justify-between gap-2 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className="num font-medium tabular-nums">{value}</span>
    </div>
  )
}

function Stepper({ label, value, onChange, min, disabled, testId }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="text-sm text-muted-foreground">{label}</span>
      <div className="flex items-center gap-1" data-testid={testId}>
        <IconButton label={`${label} : moins`} size="icon" variant="outline"
                    disabled={disabled || value <= min}
                    onClick={() => onChange(Math.max(min, value - 1))}>
          <Minus className="size-3.5" />
        </IconButton>
        {/* `w-8` (2 rem) coupait un compte à trois chiffres — un champ de 120
            panneaux est une taille « Max » parfaitement ordinaire. Largeur
            MINIMALE, pas fixe : la valeur pousse, elle n'est plus rognée. */}
        <span className="num min-w-10 px-0.5 text-center text-sm font-semibold tabular-nums">{value}</span>
        <IconButton label={`${label} : plus`} size="icon" variant="outline"
                    disabled={disabled}
                    onClick={() => onChange(value + 1)}>
          <Plus className="size-3.5" />
        </IconButton>
      </div>
    </div>
  )
}

function TierCard({
  offre, varianteAffichee, avecServable, roleOptions, pending,
  onNbPanneaux, onBatterieModules, onEquipement, onAppliquer, onRegenerer,
  saving, erreurs,
}) {
  const donneesVariante = varianteAffichee === 'avec' ? offre.avec : offre.sans
  // Aucune donnée pour la variante affichée (ex. « avec » indisponible sur
  // cette taille précise) : la carte reste visible (comparaison des 3 tailles
  // = la valeur), pauvre plutôt que masquée — même discipline que le contrat.
  const roles = rolesDeLOffre(offre)
  const nbPanneaux = pending.nb_panneaux ?? offre.config?.nb_panneaux ?? 0
  // Le sentinel serveur `config.batterie_nb_modules = 0` signifie « aucun
  // réglage manuel » (0 est un module REFUSÉ à l'écriture — la variante
  // « sans » exprime déjà l'absence de batterie) : la valeur de départ du
  // stepper est donc le compte réellement dérivé par le moteur pour « avec »
  // quand aucun override n'est enregistré.
  const batterieDepart = (offre.config?.batterie_nb_modules > 0)
    ? offre.config.batterie_nb_modules
    : (offre.avec?.batterie?.nb_modules ?? 1)
  const batterieModules = pending.batterie_nb_modules ?? batterieDepart
  const aDesModifications = Boolean(
    pending.nb_panneaux != null
    || pending.batterie_nb_modules != null
    || (pending.equipements && Object.keys(pending.equipements).length),
  )
  const remplissageKo = varianteAffichee === 'avec' && donneesVariante?.batterie
    && donneesVariante.batterie.remplissage_ok === false
  // Tout ce qui n'est PAS déjà affiché près d'un rôle catalogue précis
  // (`erreursRole` ci-dessous, sous chaque select) : `cle`, `nb_panneaux`,
  // `batterie_nb_modules`, le repli générique {path:[]} des catch() —
  // jamais un message affiché DEUX fois.
  const roleErrorKeys = new Set(roles.map(r => `config.equipements.${r}`))
  const erreursGenerales = Array.from(new Set(
    erreurs
      .filter(e => !roleErrorKeys.has(e.path.join('.')))
      .map(e => e.message),
  ))

  return (
    <Card data-testid={`offre-taille-${offre.cle}`} className={offre.recommande ? 'border-primary/50' : undefined}>
      <CardContent className="flex flex-col gap-3 pt-4 sm:pt-5">
        <div className="flex flex-wrap items-center gap-1.5">
          <h4 className="font-display text-sm font-semibold">{offre.titre}</h4>
          {offre.recommande && <Badge tone="primary">Recommandé</Badge>}
          {offre.est_le_devis && <Badge tone="success">Devis officiel</Badge>}
          {offre.ajuste && (
            <Badge tone="warning" data-testid={`offre-taille-${offre.cle}-ajuste`}>Ajusté</Badge>
          )}
        </div>
        <p className="text-xs text-muted-foreground">
          {donneesVariante?.nb_panneaux ?? nbPanneaux} panneaux
          {donneesVariante?.puissance_kwc != null && (
            <> · {formatNumber(donneesVariante.puissance_kwc, { decimals: 2 })} kWc</>
          )}
        </p>

        {/* ── Configuration éditable — résolue par le moteur, jamais un prix tapé ── */}
        <div className="flex flex-col gap-2 rounded-lg border border-border/60 bg-muted/20 p-2.5">
          <Stepper label="Panneaux" value={nbPanneaux} min={1} disabled={saving}
                   onChange={onNbPanneaux} testId={`offre-taille-${offre.cle}-stepper-panneaux`} />
          {avecServable && (
            <Stepper label="Modules batterie" value={batterieModules} min={1} disabled={saving}
                     onChange={onBatterieModules}
                     testId={`offre-taille-${offre.cle}-stepper-batterie`} />
          )}
          {roles.map(role => {
            const options = roleOptions[role] || []
            if (!options.length) return null
            const materielActuel = (donneesVariante?.materiel || []).find(m => m.role === role)
            const erreursRole = errorsAt(erreurs, 'config', 'equipements', role)
            return (
              <div key={role} className="flex flex-col gap-0.5">
                <label className="text-xs text-muted-foreground" htmlFor={`ot-${offre.cle}-${role}`}>
                  {materielActuel
                    ? `${materielActuel.marque ? materielActuel.marque + ' — ' : ''}${materielActuel.modele || ''}`
                    : 'Substituer'}
                </label>
                <select
                  id={`ot-${offre.cle}-${role}`}
                  data-testid={`offre-taille-${offre.cle}-equip-${role}`}
                  className="h-[var(--control-h-sm)] rounded-md border border-input bg-card px-2 text-xs text-foreground"
                  disabled={saving}
                  value={pending.equipements?.[role] ?? ''}
                  onChange={(e) => onEquipement(role, e.target.value ? parseInt(e.target.value, 10) : undefined)}
                >
                  <option value="">— conserver le produit actuel —</option>
                  {options.map(p => (
                    <option key={p.id} value={p.id}>
                      {p.marque ? `${p.marque} — ${p.nom}` : p.nom}
                    </option>
                  ))}
                </select>
                {erreursRole.map((m, i) => (
                  <span key={i} className="text-xs text-destructive">{m}</span>
                ))}
              </div>
            )
          })}
        </div>

        {/* ── Chiffres dérivés — LECTURE SEULE, réestampillés par le moteur ── */}
        <div className="flex flex-col gap-1 border-t border-border/60 pt-2">
          <div className="flex items-baseline justify-between gap-2">
            <span className="text-xs uppercase tracking-wide text-muted-foreground">Prix TTC</span>
            <span className="num text-lg font-semibold tabular-nums">
              {donneesVariante?.prix_ttc != null ? formatMAD(donneesVariante.prix_ttc, { decimals: 0 }) : '—'}
            </span>
          </div>
          <StatChamp label="Économie annuelle"
                     value={donneesVariante?.economie_annuelle_mad != null
                       ? formatMAD(donneesVariante.economie_annuelle_mad, { decimals: 0 }) : null} />
          <StatChamp label="Retour sur investissement"
                     value={donneesVariante?.payback_annees != null
                       ? `${formatNumber(donneesVariante.payback_annees, { decimals: 1 })} ans` : null} />
          <StatChamp label="Taux de couverture"
                     value={donneesVariante?.couverture_pct != null
                       ? `${formatNumber(donneesVariante.couverture_pct, { decimals: 0 })} %` : null} />
          <StatChamp label="Production annuelle"
                     value={donneesVariante?.production_annuelle_kwh != null
                       ? `${formatNumber(donneesVariante.production_annuelle_kwh, { decimals: 0 })} kWh` : null} />
          {varianteAffichee === 'avec' && donneesVariante?.batterie && (
            <StatChamp label="Banque batterie"
                       value={`${donneesVariante.batterie.nb_modules} × ${formatNumber(donneesVariante.batterie.module_kwh, { decimals: 1 })} kWh`
                         + (donneesVariante.batterie.capacite_utile_kwh != null
                           ? ` (${formatNumber(donneesVariante.batterie.capacite_utile_kwh, { decimals: 1 })} kWh utiles)`
                           : '')} />
          )}
        </div>

        {remplissageKo && (
          <p className="text-xs text-warning" data-testid={`offre-taille-${offre.cle}-remplissage-ko`}>
            Cette banque ne se remplit pas tous les jours à cette taille —
            surdimensionnée pour ce profil de consommation.
          </p>
        )}
        {donneesVariante?.toit_ok === false && (
          <p className="text-xs text-destructive">
            Cette configuration dépasse le plafond du toit de ce devis.
          </p>
        )}
        {!donneesVariante && (
          <p className="text-xs text-muted-foreground">
            Variante non servie sur cette taille.
          </p>
        )}

        {erreursGenerales.map((m, i) => (
          <p key={i} className="text-xs text-destructive" data-testid={`offre-taille-${offre.cle}-erreur`}>{m}</p>
        ))}

        <div className="mt-1 flex flex-wrap items-center gap-2">
          <Button type="button" size="sm" disabled={!aDesModifications} loading={saving}
                  data-testid={`offre-taille-${offre.cle}-appliquer`}
                  onClick={onAppliquer}>
            Appliquer
          </Button>
          <Button type="button" size="sm" variant="outline" loading={saving}
                  data-testid={`offre-taille-${offre.cle}-regenerer`}
                  onClick={onRegenerer}>
            <RefreshCw className="size-3.5" /> Régénérer depuis le moteur
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

/**
 * DevisOffresTailles — les trois tailles Éco / Recommandé / Max éditables
 * depuis l'écran d'édition complète du devis.
 *
 * @param {number|string} devisId          `editId` — absent/`null` sur un
 *                                          devis non encore enregistré :
 *                                          l'API a besoin d'un pk réel.
 * @param {string}        modeInstallation Marché du devis — section réservée
 *                                          au résidentiel (agricole = pompage,
 *                                          industriel/commercial ne dérivent
 *                                          pas ces tailles).
 * @param {Array}         produits         Catalogue déjà chargé par
 *                                          DevisGenerator (évite un second
 *                                          aller-retour réseau).
 */
export default function DevisOffresTailles({ devisId, modeInstallation, produits }) {
  const { confirm } = useConfirmDialog()
  const actif = Boolean(devisId) && modeInstallation === 'residentiel'

  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState(null)
  const [block, setBlock] = useState(null)
  const [variante, setVariante] = useState('sans')
  const [pending, setPending] = useState({})
  const [erreursParTaille, setErreursParTaille] = useState({})
  const [tailleEnCours, setTailleEnCours] = useState(null)

  const charger = useCallback(() => {
    if (!actif) return
    setLoading(true)
    setLoadError(null)
    ventesApi.getOffresTaillesDevis(devisId)
      .then(({ data }) => setBlock(data))
      .catch(() => setLoadError(
        'Impossible de charger les tailles Éco / Recommandé / Max de ce devis.'))
      .finally(() => setLoading(false))
  }, [devisId, actif])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage / changement de devis, même patron que DevisForm.jsx ApprobationPanel
  useEffect(() => { charger() }, [charger])

  const avecServable = block?.offres_tailles?.avec_servable === true
  // Devis sans option batterie servable (ou passé de servable à non-servable
  // entre deux chargements) : jamais de bascule affichée sur « avec » vide.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- retombée sur 'sans' quand 'avec' devient indisponible
    if (!avecServable && variante === 'avec') setVariante('sans')
  }, [avecServable, variante])

  if (!actif) return null

  const roleOptions = produitsParRole(produits)

  const setPendingField = (cle, field, value) => {
    setPending(p => ({ ...p, [cle]: { ...p[cle], [field]: value } }))
  }
  const setPendingEquipement = (cle, role, produitId) => {
    setPending(p => {
      const equipements = { ...(p[cle]?.equipements || {}) }
      if (produitId == null) delete equipements[role]
      else equipements[role] = produitId
      return { ...p, [cle]: { ...p[cle], equipements } }
    })
  }

  const appliquer = async (offre) => {
    const cle = offre.cle
    const edits = pending[cle] || {}
    // C3 — `enregistrer_config` REMPLACE toute la config stockée de la taille
    // (apps/ventes/offres_tailles.py) : envoyer SEULEMENT les champs touchés
    // depuis le dernier Applique effacerait silencieusement un override
    // enregistré lors d'un Applique précédent (ex. « 4 modules batterie »
    // posé sur Max, puis « 36 panneaux » appliqué plus tard aurait fait
    // retomber la batterie au défaut moteur). On envoie donc la config
    // EFFECTIVE complète = la config connue du serveur (`offre.config`, la
    // même que la réponse GET) fusionnée avec les éditions en attente — les
    // éditions gagnent quand les deux existent.
    const configServeur = offre.config || {}
    const config = {}
    const nbPanneaux = edits.nb_panneaux != null
      ? edits.nb_panneaux
      : (configServeur.nb_panneaux > 0 ? configServeur.nb_panneaux : undefined)
    if (nbPanneaux != null) config.nb_panneaux = nbPanneaux
    // `batterie_nb_modules = 0` est le sentinel serveur « aucun override » —
    // le reprendre littéralement serait REFUSÉ en 400 par le serializer
    // (« zéro module n'exprime pas sans batterie ») : on ne le propage que
    // s'il exprime un vrai override (> 0).
    const batterieNbModules = edits.batterie_nb_modules != null
      ? edits.batterie_nb_modules
      : (configServeur.batterie_nb_modules > 0 ? configServeur.batterie_nb_modules : undefined)
    if (batterieNbModules != null) config.batterie_nb_modules = batterieNbModules
    if (edits.equipements && Object.keys(edits.equipements).length) config.equipements = edits.equipements
    if (Object.keys(config).length === 0) return
    setTailleEnCours(cle)
    setErreursParTaille(e => ({ ...e, [cle]: [] }))
    try {
      const { data } = await ventesApi.patchOffreTailleConfig(devisId, cle, config)
      setBlock(data)
      setPending(p => ({ ...p, [cle]: {} }))
      toast.success(`Taille « ${offre.titre} » mise à jour.`)
    } catch (err) {
      const raw = err?.response?.data
      const flat = raw && typeof raw === 'object' ? flattenErrors(raw) : []
      setErreursParTaille(e => ({
        ...e,
        [cle]: flat.length ? flat : [{ path: [], message: 'L\'enregistrement a échoué — vérifiez la configuration.' }],
      }))
    } finally {
      setTailleEnCours(null)
    }
  }

  const regenerer = async (offre) => {
    const ok = await confirm({
      title: `Régénérer la taille « ${offre.titre} » ?`,
      description: 'La configuration ajustée à la main pour cette taille sera '
        + 'remplacée par la dérivation du moteur. Les deux autres tailles ne '
        + 'sont pas touchées.',
      confirmLabel: 'Régénérer',
    })
    if (!ok) return
    setTailleEnCours(offre.cle)
    setErreursParTaille(e => ({ ...e, [offre.cle]: [] }))
    try {
      const { data } = await ventesApi.regenererOffreTaille(devisId, offre.cle)
      setBlock(data)
      setPending(p => ({ ...p, [offre.cle]: {} }))
      toast.success(`Taille « ${offre.titre} » régénérée depuis le moteur.`)
    } catch {
      setErreursParTaille(e => ({
        ...e, [offre.cle]: [{ path: [], message: 'La régénération a échoué.' }],
      }))
    } finally {
      setTailleEnCours(null)
    }
  }

  return (
    <Card data-testid="offres-tailles-section">
      <CardHeader className="flex-row items-center justify-between gap-2 space-y-0">
        <CardTitle className="flex items-center gap-2">
          <Layers3 className="size-4 text-muted-foreground" aria-hidden="true" />
          Tailles Éco / Recommandé / Max
        </CardTitle>
        {avecServable && (
          <Segmented options={VARIANTES} value={variante} onChange={setVariante} size="sm"
                     data-testid="offres-tailles-variante-switch" />
        )}
      </CardHeader>
      <CardContent className="pt-0">
        {loading && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Spinner /> Chargement des tailles…
          </div>
        )}
        {!loading && loadError && (
          <div className="flex flex-wrap items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
            {loadError}
            <Button type="button" size="sm" variant="outline" onClick={charger}>Réessayer</Button>
          </div>
        )}
        {!loading && !loadError && block && block.editable === false && (
          <p className="text-sm text-muted-foreground" data-testid="offres-tailles-non-editable">
            {block.raison_non_editable
              || 'Les tailles ne sont pas encore disponibles pour ce devis.'}
          </p>
        )}
        {!loading && !loadError && block?.editable && block.offres_tailles?.offres?.length > 0 && (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3" data-testid="offres-tailles-cartes">
            {block.offres_tailles.offres.map(offre => (
              <TierCard
                key={offre.cle}
                offre={offre}
                varianteAffichee={avecServable ? variante : 'sans'}
                avecServable={avecServable}
                roleOptions={roleOptions}
                pending={pending[offre.cle] || {}}
                onNbPanneaux={(v) => setPendingField(offre.cle, 'nb_panneaux', v)}
                onBatterieModules={(v) => setPendingField(offre.cle, 'batterie_nb_modules', v)}
                onEquipement={(role, id) => setPendingEquipement(offre.cle, role, id)}
                onAppliquer={() => appliquer(offre)}
                onRegenerer={() => regenerer(offre)}
                saving={tailleEnCours === offre.cle}
                erreurs={erreursParTaille[offre.cle] || []}
              />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
