// Onglet « Équipe & rôles » de la page Paramètres : ORGANISATION de l'entreprise
// (décision fondateur 27/10/2026). Direction en haut → départements (chacun
// avec son responsable) → équipes (commerciales, terrain, autres ; chacune avec
// son chef) → personnes. Chaque personne a une FONCTION (poste : porte un
// département et un rôle par défaut) et un RÔLE (permissions). La hiérarchie
// (manager) est calculée par le serveur à partir de cette structure : aucun
// superviseur n'est plus réglé à la main ici. Contrat de lecture :
// `apps/roles/contract_samples/organisation.json`.
import { useEffect, useState } from 'react'
import api from '../../api/axios'
import rolesApi from '../../api/rolesApi'
import crmApi from '../../api/crmApi'
import installationsApi from '../../api/installationsApi'
import { apiErrorMessage } from '../../lib/apiError'
import { Skeleton, EmptyState, CarteContenu, Badge, Button } from '../../ui'
import { ResponsiveDialog, useIsMobile } from '../../ui/ResponsiveDialog'
import toutesLesPages from './toutesLesPages'
import { SectionTitle } from './peComponents'

const selectCls =
  'h-[var(--control-h)] w-full rounded-md border border-input '
  + 'bg-card px-[var(--control-px)] text-sm text-foreground shadow-ui-xs '
  + 'transition-colors focus-visible:border-ring focus-visible:outline-none '
  + 'focus-visible:ring-2 focus-visible:ring-ring'

const TYPES_EQUIPE = {
  commerciale: { label: 'Commerciale', tone: 'info' },
  terrain: { label: 'Terrain', tone: 'success' },
  autre: { label: 'Autre', tone: 'neutral' },
}

const MANQUE_LABEL = { fonction: 'fonction manquante', role: 'rôle manquant' }

// Connecteurs de l'arbre : CSS pur, sans dépendance. Couleur = currentColor
// atténuée, donc valable en clair comme en sombre.
const ARBRE_CSS = `
.org-tree{--org-line:color-mix(in srgb,currentColor 28%,transparent)}
.org-tree .org-stem{display:block;width:2px;height:22px;background:var(--org-line)}
.org-tree .org-row{display:flex;justify-content:center;margin:0;padding:0;list-style:none}
.org-tree .org-row>li{position:relative;padding:22px 8px 0;display:flex;flex-direction:column;align-items:center}
.org-tree .org-row>li::before,.org-tree .org-row>li::after{content:'';position:absolute;top:0;width:50%;height:22px;border-top:2px solid var(--org-line)}
.org-tree .org-row>li::before{right:50%}
.org-tree .org-row>li::after{left:50%;border-left:2px solid var(--org-line)}
.org-tree .org-row>li:first-child::before{border-top:0}
.org-tree .org-row>li:last-child::after{border-top:0}
.org-tree .org-row>li:last-child::before{border-right:2px solid var(--org-line);border-radius:0 6px 0 0}
.org-tree .org-row>li:first-child::after{border-radius:6px 0 0 0}
.org-tree .org-row>li:only-child::before{display:none}
.org-tree .org-row>li:only-child::after{border-top:0;border-radius:0}
.org-tree .org-teams{border-left:2px solid var(--org-line);margin-left:10px;padding-left:12px}
`

const nomUtilisateur = (u) => [u.first_name, u.last_name].filter(Boolean).join(' ') || u.username

function Champ({ label, htmlFor, children, hint }) {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={htmlFor} className="text-xs font-medium text-foreground">{label}</label>
      {children}
      {hint && <p className="text-[11px] text-muted-foreground">{hint}</p>}
    </div>
  )
}

function ErreurForm({ message }) {
  if (!message) return null
  return (
    <p role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-2.5 text-sm text-destructive">
      {message}
    </p>
  )
}

// ── Personne (puce) ─────────────────────────────────────────────────────────
function PersonneChip({ p, onEdit }) {
  if (!p) return null
  const contenu = (
    <>
      <span className="font-medium text-foreground">{p.nom}</span>
      <span className={p.fonction ? 'text-muted-foreground' : 'text-destructive'}>
        {p.fonction || 'sans fonction'}
      </span>
      <span className="text-muted-foreground">{p.role || 'sans rôle'}</span>
    </>
  )
  const cls = 'inline-flex flex-wrap items-center gap-x-1.5 rounded-md border border-border bg-card px-2 py-1 text-xs '
  if (!onEdit) {
    return <span className={cls} data-testid={`org-personne-${p.id}`}>{contenu}</span>
  }
  return (
    <button type="button" className={cls + 'text-left hover:bg-accent'}
            data-testid={`org-personne-${p.id}`} onClick={() => onEdit(p)}
            aria-label={`Modifier ${p.nom}`}>
      {contenu}
    </button>
  )
}

function Personnes({ liste, h }) {
  if (!liste || liste.length === 0) return null
  return (
    <div className="flex flex-wrap gap-1.5">
      {liste.map((p) => (
        <PersonneChip key={p.id} p={p} onEdit={h.canEdit ? h.editPersonne : undefined} />
      ))}
    </div>
  )
}

// ── Équipe ──────────────────────────────────────────────────────────────────
function EquipeContenu({ eq, h }) {
  const t = TYPES_EQUIPE[eq.type] ?? TYPES_EQUIPE.autre
  return (
    <>
      <div className="mb-2 flex flex-wrap items-center gap-2">
        {h.canEdit ? (
          <button type="button" className="font-semibold text-foreground hover:underline"
                  onClick={() => h.editEquipe(eq)} aria-label={`Modifier l'équipe ${eq.nom}`}>
            {eq.nom}
          </button>
        ) : (
          <span className="font-semibold text-foreground">{eq.nom}</span>
        )}
        <Badge tone={t.tone}>{t.label}</Badge>
        {eq.type === 'commerciale' && eq.recoit_leads && (
          <Badge tone="info">Reçoit les nouveaux leads</Badge>
        )}
      </div>
      <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
        <span className="text-muted-foreground">Chef :</span>
        {eq.chef
          ? <PersonneChip p={eq.chef} onEdit={h.canEdit ? h.editPersonne : undefined} />
          : <span className="text-muted-foreground">non défini</span>}
      </div>
      {eq.membres.length === 0
        ? <p className="text-xs text-muted-foreground">Aucun membre.</p>
        : <Personnes liste={eq.membres} h={h} />}
    </>
  )
}

function EquipeBox({ eq, h }) {
  return (
    <div className="rounded-lg border border-border bg-card/60 p-3"
         data-testid={`org-equipe-${eq.type}-${eq.id}`}>
      <EquipeContenu eq={eq} h={h} />
    </div>
  )
}

// ── Département ─────────────────────────────────────────────────────────────
function DeptTitre({ dep, h }) {
  return h.canEdit ? (
    <button type="button" className="font-semibold text-foreground hover:underline"
            onClick={() => h.editDep(dep)} aria-label={`Modifier le département ${dep.nom}`}>
      {dep.nom}
    </button>
  ) : (
    <span className="font-semibold text-foreground">{dep.nom}</span>
  )
}

function DeptContenu({ dep, h }) {
  return (
    <>
      <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
        <span className="text-muted-foreground">Responsable :</span>
        {dep.responsable
          ? <PersonneChip p={dep.responsable} onEdit={h.canEdit ? h.editPersonne : undefined} />
          : <span className="text-muted-foreground">non défini</span>}
      </div>
      {dep.equipes.length > 0 && (
        <div className="org-teams mb-2 flex flex-col gap-2">
          {dep.equipes.map((eq) => <EquipeBox key={`${eq.type}-${eq.id}`} eq={eq} h={h} />)}
        </div>
      )}
      {dep.sans_equipe.length > 0 && (
        <div data-testid={`org-sans-equipe-${dep.id}`}>
          <p className="mb-1 text-[11px] font-medium text-muted-foreground">Sans équipe</p>
          <Personnes liste={dep.sans_equipe} h={h} />
        </div>
      )}
    </>
  )
}

function DeptBox({ dep, h }) {
  return (
    <div className="w-72 rounded-xl border border-border bg-card p-3 shadow-ui-xs"
         data-testid={`org-dept-${dep.id}`}>
      <div className="mb-2"><DeptTitre dep={dep} h={h} /></div>
      <DeptContenu dep={dep} h={h} />
    </div>
  )
}

function DirectionBox({ direction, h }) {
  return (
    <div className="w-80 max-w-full rounded-xl border-2 border-primary/50 bg-card p-3 shadow-ui-xs"
         data-testid="org-direction">
      <div className="mb-2"><DeptTitre dep={direction} h={h} /></div>
      <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
        <span className="text-muted-foreground">Responsable :</span>
        {direction.responsable
          ? <PersonneChip p={direction.responsable} onEdit={h.canEdit ? h.editPersonne : undefined} />
          : <span className="text-muted-foreground">non défini</span>}
      </div>
      <Personnes liste={direction.membres} h={h} />
    </div>
  )
}

function ASansDepartement({ equipes, h }) {
  if (equipes.length === 0) return null
  return (
    <section aria-label="Équipes sans département" className="mt-6 flex flex-col gap-2">
      <h3 className="text-[13px] font-semibold text-foreground">Équipes sans département</h3>
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {equipes.map((eq) => <EquipeBox key={`${eq.type}-${eq.id}`} eq={eq} h={h} />)}
      </div>
    </section>
  )
}

// ── Arbre (≥ 768 px) ────────────────────────────────────────────────────────
function Arbre({ org, h }) {
  const deps = org.departements ?? []
  return (
    <div className="org-tree" data-testid="org-arbre">
      <style>{ARBRE_CSS}</style>
      <div className="overflow-x-auto pb-2">
        <div className="mx-auto flex w-max min-w-full flex-col items-center">
          {org.direction && <DirectionBox direction={org.direction} h={h} />}
          {deps.length > 0 && org.direction && <span className="org-stem" aria-hidden="true" />}
          {deps.length > 0 && (
            <ul className="org-row" style={org.direction ? undefined : { paddingTop: 0 }}>
              {deps.map((d) => (
                <li key={d.id}><DeptBox dep={d} h={h} /></li>
              ))}
            </ul>
          )}
        </div>
      </div>
      <ASansDepartement equipes={org.equipes_sans_departement ?? []} h={h} />
    </div>
  )
}

// ── Liste imbriquée repliable (< 768 px) ───────────────────────────────────
function ListeMobile({ org, h }) {
  const deps = org.departements ?? []
  return (
    <div className="flex flex-col gap-2" data-testid="org-liste">
      {org.direction && (
        <details open className="rounded-lg border border-border p-2">
          <summary className="cursor-pointer text-sm font-semibold">{org.direction.nom}</summary>
          <div className="mt-2 flex flex-col gap-2">
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <span className="text-muted-foreground">Responsable :</span>
              {org.direction.responsable
                ? <PersonneChip p={org.direction.responsable} onEdit={h.canEdit ? h.editPersonne : undefined} />
                : <span className="text-muted-foreground">non défini</span>}
            </div>
            <Personnes liste={org.direction.membres} h={h} />
          </div>
        </details>
      )}
      {deps.map((d) => (
        <details key={d.id} open className="rounded-lg border border-border p-2" data-testid={`org-dept-${d.id}`}>
          <summary className="cursor-pointer text-sm font-semibold">{d.nom}</summary>
          <div className="mt-2 flex flex-col gap-2">
            {h.canEdit && (
              <Button variant="outline" size="sm" className="self-start" onClick={() => h.editDep(d)}>
                Modifier le département
              </Button>
            )}
            <DeptContenu dep={d} h={h} />
          </div>
        </details>
      ))}
      <ASansDepartement equipes={org.equipes_sans_departement ?? []} h={h} />
    </div>
  )
}

// ── À compléter ────────────────────────────────────────────────────────────
function ACompleter({ liste, h }) {
  if (!liste || liste.length === 0) return null
  return (
    <section aria-label="À compléter" data-testid="org-a-completer"
             className="mb-4 rounded-lg border border-destructive/40 bg-destructive/10 p-3">
      <h3 className="mb-2 text-[13px] font-semibold text-destructive">
        À compléter ({liste.length})
      </h3>
      <ul className="flex flex-col gap-1.5">
        {liste.map((p) => (
          <li key={p.id} className="flex flex-wrap items-center gap-2 text-sm">
            <span className="font-medium text-foreground">{p.nom}</span>
            <span className="text-xs text-destructive">
              {(p.manque ?? []).map((m) => MANQUE_LABEL[m] ?? m).join(' · ')}
            </span>
            {h.canEdit && (
              <Button variant="outline" size="sm" className="ml-auto" onClick={() => h.editPersonne(p)}>
                Compléter
              </Button>
            )}
          </li>
        ))}
      </ul>
    </section>
  )
}

// ── Dialogues ──────────────────────────────────────────────────────────────
function PersonneDialog({ personne, postes, roles, onClose, onSaved }) {
  const posteInit = postes.find((p) => p.intitule === personne.fonction)
  const roleInit = roles.find((r) => r.nom === personne.role)
  const [fonction, setFonction] = useState(posteInit ? String(posteInit.id) : '')
  const [role, setRole] = useState(roleInit ? String(roleInit.id) : '')
  const [erreur, setErreur] = useState(null)
  const [saving, setSaving] = useState(false)

  const poste = postes.find((p) => String(p.id) === fonction)
  const roleDefaut = poste?.role != null ? roles.find((r) => r.id === poste.role) : null

  const changerFonction = (v) => {
    setFonction(v)
    const np = postes.find((p) => String(p.id) === v)
    // La fonction pose le rôle par défaut ; l'admin peut ensuite le changer.
    if (np?.role != null) setRole(String(np.role))
  }

  const submit = async (e) => {
    e.preventDefault()
    setSaving(true)
    setErreur(null)
    try {
      const payload = { fonction: fonction ? Number(fonction) : null }
      if (role) payload.role = Number(role)
      await api.patch(`/users/${personne.id}/`, payload)
      await onSaved()
    } catch (err) {
      setErreur(apiErrorMessage(err, "Impossible d'enregistrer la personne."))
    } finally {
      setSaving(false)
    }
  }

  return (
    <ResponsiveDialog open onOpenChange={(o) => { if (!o) onClose() }}
                      title={`Fonction et rôle — ${personne.nom}`} className="max-w-md">
      <form onSubmit={submit} className="flex flex-col gap-3">
        <Champ label="Fonction" htmlFor="org-p-fonction">
          <select id="org-p-fonction" className={selectCls} value={fonction}
                  onChange={(e) => changerFonction(e.target.value)}>
            <option value="">— Aucune —</option>
            {postes.filter((p) => p.actif !== false || String(p.id) === fonction).map((p) => (
              <option key={p.id} value={p.id}>{p.intitule}</option>
            ))}
          </select>
        </Champ>
        <Champ label="Rôle (permissions)" htmlFor="org-p-role"
               hint={roleDefaut ? `rôle de la fonction : ${roleDefaut.nom}` : undefined}>
          <select id="org-p-role" className={selectCls} value={role}
                  onChange={(e) => setRole(e.target.value)}>
            <option value="">— Aucun —</option>
            {roles.map((r) => <option key={r.id} value={r.id}>{r.nom}</option>)}
          </select>
        </Champ>
        <ErreurForm message={erreur} />
        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
          <Button type="submit" loading={saving}>Enregistrer</Button>
        </div>
      </form>
    </ResponsiveDialog>
  )
}

function DepartementDialog({ dep, users, onClose, onSaved }) {
  const [nom, setNom] = useState(dep.nom ?? '')
  const [responsable, setResponsable] = useState(dep.responsable != null ? String(dep.responsable) : '')
  const [ordre, setOrdre] = useState(dep.ordre != null ? String(dep.ordre) : '0')
  const [estDirection, setEstDirection] = useState(!!dep.est_direction)
  const [erreur, setErreur] = useState(null)
  const [saving, setSaving] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setSaving(true)
    setErreur(null)
    try {
      await rolesApi.saveDepartement(dep.id ?? null, {
        nom,
        responsable: responsable ? Number(responsable) : null,
        ordre: ordre === '' ? 0 : Number(ordre),
        est_direction: estDirection,
      })
      await onSaved()
    } catch (err) {
      setErreur(apiErrorMessage(err, "Impossible d'enregistrer le département."))
    } finally {
      setSaving(false)
    }
  }

  return (
    <ResponsiveDialog open onOpenChange={(o) => { if (!o) onClose() }}
                      title={dep.id ? `Département — ${dep.nom}` : 'Nouveau département'} className="max-w-md">
      <form onSubmit={submit} noValidate className="flex flex-col gap-3">
        <Champ label="Nom" htmlFor="org-d-nom">
          <input id="org-d-nom" className={selectCls} value={nom} onChange={(e) => setNom(e.target.value)} />
        </Champ>
        <Champ label="Responsable" htmlFor="org-d-resp">
          <select id="org-d-resp" className={selectCls} value={responsable}
                  onChange={(e) => setResponsable(e.target.value)}>
            <option value="">— Aucun —</option>
            {users.map((u) => <option key={u.id} value={u.id}>{nomUtilisateur(u)}</option>)}
          </select>
        </Champ>
        <Champ label="Ordre" htmlFor="org-d-ordre">
          <input id="org-d-ordre" type="number" step="any" className={selectCls} value={ordre}
                 onChange={(e) => setOrdre(e.target.value)} />
        </Champ>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={estDirection} onChange={(e) => setEstDirection(e.target.checked)} />
          Département « Direction » (affiché en haut de l'organigramme)
        </label>
        <ErreurForm message={erreur} />
        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
          <Button type="submit" loading={saving}>Enregistrer</Button>
        </div>
      </form>
    </ResponsiveDialog>
  )
}

function EquipeDialog({ equipe, departements, users, onClose, onSaved }) {
  const edition = !!equipe.id
  const [type, setType] = useState(equipe.type ?? 'commerciale')
  const [nom, setNom] = useState(equipe.nom ?? '')
  const [departement, setDepartement] = useState(equipe.departementId != null ? String(equipe.departementId) : '')
  const [chef, setChef] = useState(equipe.chef ? String(equipe.chef.id) : '')
  const [membres, setMembres] = useState(new Set((equipe.membres ?? []).map((m) => m.id)))
  const [recoitLeads, setRecoitLeads] = useState(!!equipe.recoit_leads)
  const [erreur, setErreur] = useState(null)
  const [saving, setSaving] = useState(false)

  const basculer = (id) => setMembres((s) => {
    const n = new Set(s)
    if (n.has(id)) n.delete(id)
    else n.add(id)
    return n
  })

  const submit = async (e) => {
    e.preventDefault()
    setSaving(true)
    setErreur(null)
    const base = {
      nom,
      departement: departement ? Number(departement) : null,
      membres: [...membres],
    }
    const chefId = chef ? Number(chef) : null
    try {
      if (type === 'commerciale') {
        await crmApi.saveEquipe(equipe.id ?? null, { ...base, responsable: chefId, recoit_leads: recoitLeads })
      } else if (type === 'terrain') {
        await installationsApi.saveEquipeTerrain(equipe.id ?? null, { ...base, chef: chefId })
      } else {
        await rolesApi.saveEquipeOrg(equipe.id ?? null, { ...base, chef: chefId })
      }
      await onSaved()
    } catch (err) {
      setErreur(apiErrorMessage(err, "Impossible d'enregistrer l'équipe."))
    } finally {
      setSaving(false)
    }
  }

  return (
    <ResponsiveDialog open onOpenChange={(o) => { if (!o) onClose() }}
                      title={edition ? `Équipe — ${equipe.nom}` : 'Nouvelle équipe'} className="max-w-lg">
      <form onSubmit={submit} noValidate className="flex flex-col gap-3">
        <Champ label="Type d'équipe" htmlFor="org-e-type">
          <select id="org-e-type" className={selectCls} value={type} disabled={edition}
                  onChange={(e) => setType(e.target.value)}>
            {Object.entries(TYPES_EQUIPE).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
          </select>
        </Champ>
        <Champ label="Nom" htmlFor="org-e-nom">
          <input id="org-e-nom" className={selectCls} value={nom} onChange={(e) => setNom(e.target.value)} />
        </Champ>
        <Champ label="Département" htmlFor="org-e-dep">
          <select id="org-e-dep" className={selectCls} value={departement}
                  onChange={(e) => setDepartement(e.target.value)}>
            <option value="">— Aucun —</option>
            {departements.map((d) => <option key={d.id} value={d.id}>{d.nom}</option>)}
          </select>
        </Champ>
        <Champ label="Chef d'équipe" htmlFor="org-e-chef">
          <select id="org-e-chef" className={selectCls} value={chef} onChange={(e) => setChef(e.target.value)}>
            <option value="">— Aucun —</option>
            {users.map((u) => <option key={u.id} value={u.id}>{nomUtilisateur(u)}</option>)}
          </select>
        </Champ>
        {type === 'commerciale' && (
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={recoitLeads} onChange={(e) => setRecoitLeads(e.target.checked)} />
            Reçoit les nouveaux leads
          </label>
        )}
        <fieldset className="flex flex-col gap-1">
          <legend className="mb-1 text-xs font-medium text-foreground">Membres</legend>
          <div className="max-h-48 overflow-y-auto rounded-md border border-border p-2">
            {users.map((u) => (
              <label key={u.id} className="flex items-center gap-2 py-0.5 text-sm">
                <input type="checkbox" checked={membres.has(u.id)} onChange={() => basculer(u.id)} />
                {nomUtilisateur(u)}
              </label>
            ))}
          </div>
        </fieldset>
        <ErreurForm message={erreur} />
        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
          <Button type="submit" loading={saving}>Enregistrer</Button>
        </div>
      </form>
    </ResponsiveDialog>
  )
}

function PosteDialog({ poste, departements, roles, onClose, onSaved }) {
  const [intitule, setIntitule] = useState(poste.intitule ?? '')
  const [departement, setDepartement] = useState(poste.departement != null ? String(poste.departement) : '')
  const [role, setRole] = useState(poste.role != null ? String(poste.role) : '')
  const [actif, setActif] = useState(poste.actif !== false)
  const [erreur, setErreur] = useState(null)
  const [saving, setSaving] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setSaving(true)
    setErreur(null)
    try {
      await rolesApi.savePoste(poste.id ?? null, {
        intitule,
        departement: departement ? Number(departement) : null,
        role: role ? Number(role) : null,
        actif,
      })
      await onSaved()
    } catch (err) {
      setErreur(apiErrorMessage(err, "Impossible d'enregistrer la fonction."))
    } finally {
      setSaving(false)
    }
  }

  return (
    <ResponsiveDialog open onOpenChange={(o) => { if (!o) onClose() }}
                      title={poste.id ? `Fonction — ${poste.intitule}` : 'Nouvelle fonction'} className="max-w-md">
      <form onSubmit={submit} noValidate className="flex flex-col gap-3">
        <Champ label="Intitulé" htmlFor="org-f-intitule">
          <input id="org-f-intitule" className={selectCls} value={intitule}
                 onChange={(e) => setIntitule(e.target.value)} />
        </Champ>
        <Champ label="Département" htmlFor="org-f-dep">
          <select id="org-f-dep" className={selectCls} value={departement}
                  onChange={(e) => setDepartement(e.target.value)}>
            <option value="">— Aucun —</option>
            {departements.map((d) => <option key={d.id} value={d.id}>{d.nom}</option>)}
          </select>
        </Champ>
        <Champ label="Rôle par défaut" htmlFor="org-f-role">
          <select id="org-f-role" className={selectCls} value={role} onChange={(e) => setRole(e.target.value)}>
            <option value="">— Aucun —</option>
            {roles.map((r) => <option key={r.id} value={r.id}>{r.nom}</option>)}
          </select>
        </Champ>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={actif} onChange={(e) => setActif(e.target.checked)} />
          Active
        </label>
        <ErreurForm message={erreur} />
        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
          <Button type="submit" loading={saving}>Enregistrer</Button>
        </div>
      </form>
    </ResponsiveDialog>
  )
}

function PosteLigne({ p, dep, rol, canEdit, onEdit, onToggle }) {
  return (
    <tr className="border-b border-border/60" data-testid={`poste-${p.id}`}>
      <td className="py-1.5 pr-3 font-medium text-foreground">{p.intitule}</td>
      <td className="py-1.5 pr-3">{dep(p.departement)}</td>
      <td className="py-1.5 pr-3">{rol(p.role)}</td>
      <td className="py-1.5 pr-3">
        <Badge tone={p.actif === false ? 'neutral' : 'success'}>{p.actif === false ? 'Archivée' : 'Active'}</Badge>
      </td>
      {canEdit && (
        <td className="py-1.5">
          <div className="flex gap-1.5">
            <Button variant="outline" size="sm" onClick={() => onEdit(p)} aria-label={`Modifier ${p.intitule}`}>Modifier</Button>
            <Button variant="ghost" size="sm" onClick={() => onToggle(p)}>
              {p.actif === false ? 'Réactiver' : 'Archiver'}
            </Button>
          </div>
        </td>
      )}
    </tr>
  )
}

// ── Onglets Fonctions / Départements ───────────────────────────────────────
function FonctionsTab({ postes, departements, roles, canEdit, onEdit, onToggle }) {
  const dep = (id) => departements.find((d) => d.id === id)?.nom ?? '—'
  const rol = (id) => roles.find((r) => r.id === id)?.nom ?? '—'
  return (
    <div className="flex flex-col gap-3">
      {canEdit && (
        <Button size="sm" className="self-start" onClick={() => onEdit({})}>+ Fonction</Button>
      )}
      {postes.length === 0 ? (
        <EmptyState title="Aucune fonction" description="Créez les fonctions de l'entreprise (Directeur, Chargée de clientèle…)." />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm" aria-label="Fonctions">
            <thead>
              <tr className="border-b border-border text-left text-xs text-muted-foreground">
                <th className="py-1.5 pr-3 font-medium">Intitulé</th>
                <th className="py-1.5 pr-3 font-medium">Département</th>
                <th className="py-1.5 pr-3 font-medium">Rôle par défaut</th>
                <th className="py-1.5 pr-3 font-medium">Actif</th>
                {canEdit && <th className="py-1.5 font-medium"><span className="sr-only">Actions</span></th>}
              </tr>
            </thead>
            <tbody>
              {postes.map((p) => (
                <PosteLigne key={p.id} p={p} dep={dep} rol={rol} canEdit={canEdit} onEdit={onEdit} onToggle={onToggle} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function DepartementsTab({ departements, users, canEdit, onEdit }) {
  const resp = (id) => {
    const u = users.find((x) => x.id === id)
    return u ? nomUtilisateur(u) : '—'
  }
  return (
    <div className="flex flex-col gap-3">
      {canEdit && (
        <Button size="sm" className="self-start" onClick={() => onEdit({})}>+ Département</Button>
      )}
      {departements.length === 0 ? (
        <EmptyState title="Aucun département" description="Créez Direction, Commercial, Technique, Marketing…" />
      ) : (
        <ul className="divide-y divide-border/60 rounded-lg border border-border px-3" aria-label="Départements">
          {departements.map((d) => (
            <li key={d.id} className="flex flex-wrap items-center gap-2 py-2 text-sm" data-testid={`departement-${d.id}`}>
              <span className="font-medium text-foreground">{d.nom}</span>
              {d.est_direction && <Badge tone="primary">Direction</Badge>}
              {d.actif === false && <Badge tone="neutral">Archivé</Badge>}
              <span className="text-xs text-muted-foreground">Responsable : {resp(d.responsable)}</span>
              <span className="text-xs text-muted-foreground">Ordre {d.ordre}</span>
              {canEdit && (
                <Button variant="outline" size="sm" className="ml-auto" onClick={() => onEdit(d)}
                        aria-label={`Modifier ${d.nom}`}>Modifier</Button>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

// ── Section ────────────────────────────────────────────────────────────────
export default function EquipeSection({ canManageSensitive = false }) {
  const canEdit = !!canManageSensitive
  const mobile = useIsMobile()
  const [org, setOrg] = useState(null)
  const [postes, setPostes] = useState([])
  const [departements, setDepartements] = useState([])
  const [roles, setRoles] = useState([])
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [onglet, setOnglet] = useState('organigramme')
  const [dialogue, setDialogue] = useState(null) // {kind, data}

  const load = async () => {
    try {
      const lectures = [
        rolesApi.getOrganisation().then((r) => r.data),
        toutesLesPages((p) => rolesApi.getPostes(p)),
        toutesLesPages((p) => rolesApi.getDepartements(p)),
      ]
      if (canEdit) {
        lectures.push(
          toutesLesPages((p) => rolesApi.getRoles(p)),
          toutesLesPages((p) => api.get('/users/', { params: { ...p, page_size: 200 } })),
        )
      }
      const [o, po, de, ro, us] = await Promise.all(lectures)
      setOrg(o)
      setPostes(po)
      setDepartements(de)
      setRoles(ro ?? [])
      setUsers((us ?? []).filter((u) => u.is_active !== false))
      setError(null)
    } catch (err) {
      setError(apiErrorMessage(err, "Impossible de charger l'organisation."))
    } finally {
      setLoading(false)
    }
  }

  // Chargement initial — le setState a lieu dans le callback async.
  // eslint-disable-next-line react-hooks/set-state-in-effect, react-hooks/exhaustive-deps -- chargement initial : setState dans le callback async, jamais synchrone (D-ENF22)
  useEffect(() => { load() }, [])

  const fermerEtRecharger = async () => {
    setDialogue(null)
    await load()
  }

  const basculerPoste = async (p) => {
    try {
      await rolesApi.savePoste(p.id, { actif: p.actif === false })
      await load()
    } catch (err) {
      setError(apiErrorMessage(err, "Impossible de modifier la fonction."))
    }
  }

  // Département complet (liste serveur) pour l'édition depuis l'organigramme.
  const editDep = (d) => {
    const complet = departements.find((x) => x.id === d.id)
    setDialogue({
      kind: 'departement',
      data: complet ?? { id: d.id, nom: d.nom, ordre: d.ordre, responsable: d.responsable?.id ?? null },
    })
  }

  const h = {
    canEdit,
    editPersonne: (p) => setDialogue({ kind: 'personne', data: p }),
    editDep,
    editEquipe: (eq) => setDialogue({ kind: 'equipe', data: eq }),
  }

  // L'équipe porte le département qui la contient (le contrat ne le répète pas).
  const orgEnrichi = org && {
    ...org,
    departements: (org.departements ?? []).map((d) => ({
      ...d,
      equipes: (d.equipes ?? []).map((e) => ({ ...e, departementId: d.id })),
      sans_equipe: d.sans_equipe ?? [],
    })),
    equipes_sans_departement: (org.equipes_sans_departement ?? []).map((e) => ({ ...e, departementId: null })),
  }

  const tabCls = (active) =>
    'rounded-md px-3 py-1 text-xs font-medium transition-colors '
    + (active
      ? 'bg-primary text-primary-foreground'
      : 'bg-muted/60 text-muted-foreground hover:bg-muted')

  const vide = orgEnrichi && !orgEnrichi.direction
    && orgEnrichi.departements.length === 0
    && orgEnrichi.equipes_sans_departement.length === 0

  return (
    <div className="flex flex-col gap-4">
      <CarteContenu contenu="pt-4 sm:pt-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <SectionTitle label="Organisation" icon={<><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></>}/>
          <div className="flex shrink-0 gap-1" role="tablist" aria-label="Organisation">
            <button type="button" role="tab" aria-selected={onglet === 'organigramme'} className={tabCls(onglet === 'organigramme')} onClick={() => setOnglet('organigramme')}>Organigramme</button>
            <button type="button" role="tab" aria-selected={onglet === 'fonctions'} className={tabCls(onglet === 'fonctions')} onClick={() => setOnglet('fonctions')}>Fonctions</button>
            <button type="button" role="tab" aria-selected={onglet === 'departements'} className={tabCls(onglet === 'departements')} onClick={() => setOnglet('departements')}>Départements</button>
          </div>
        </div>
        <p className="mb-3.5 text-[12.5px] leading-relaxed text-muted-foreground">
          Direction, départements, équipes et personnes. Chaque personne a une
          <strong> fonction</strong> (qui porte son département et son rôle par
          défaut) et un <strong>rôle</strong> (ses permissions). Le manager de
          chacun est calculé automatiquement à partir de cette structure.
        </p>

        {error && (
          <p role="alert" className="mb-3 rounded-lg border border-destructive/30 bg-destructive/10 p-2.5 text-sm text-destructive">
            {error}
          </p>
        )}

        {loading ? (
          <div className="space-y-2.5">
            <Skeleton className="h-9 w-full" />
            <Skeleton className="h-9 w-full" />
            <Skeleton className="h-9 w-full" />
          </div>
        ) : onglet === 'fonctions' ? (
          <FonctionsTab postes={postes} departements={departements} roles={roles} canEdit={canEdit}
                        onEdit={(p) => setDialogue({ kind: 'poste', data: p })} onToggle={basculerPoste} />
        ) : onglet === 'departements' ? (
          <DepartementsTab departements={departements} users={users} canEdit={canEdit}
                           onEdit={(d) => setDialogue({ kind: 'departement', data: d })} />
        ) : !orgEnrichi ? null : (
          <>
            <ACompleter liste={orgEnrichi.a_completer} h={h} />
            {canEdit && (
              <div className="mb-3 flex flex-wrap gap-2">
                <Button size="sm" variant="outline" onClick={() => setDialogue({ kind: 'departement', data: {} })}>+ Département</Button>
                <Button size="sm" variant="outline" onClick={() => setDialogue({ kind: 'equipe', data: {} })}>+ Équipe</Button>
              </div>
            )}
            {vide ? (
              <EmptyState title="Organisation vide" description="Créez d'abord un département « Direction » puis vos autres départements." />
            ) : mobile ? (
              <ListeMobile org={orgEnrichi} h={h} />
            ) : (
              <Arbre org={orgEnrichi} h={h} />
            )}
          </>
        )}
      </CarteContenu>

      <CarteContenu contenu="pt-4 sm:pt-5">
        <p className="text-[12.5px] leading-relaxed text-muted-foreground">
          La gestion des employés se fait dans
          <strong> Administration → Utilisateurs</strong> (menu latéral), et
          les rôles & permissions dans <strong>Administration → Rôles</strong>.
        </p>
      </CarteContenu>

      {dialogue?.kind === 'personne' && (
        <PersonneDialog personne={dialogue.data} postes={postes} roles={roles}
                        onClose={() => setDialogue(null)} onSaved={fermerEtRecharger} />
      )}
      {dialogue?.kind === 'departement' && (
        <DepartementDialog dep={dialogue.data} users={users}
                           onClose={() => setDialogue(null)} onSaved={fermerEtRecharger} />
      )}
      {dialogue?.kind === 'equipe' && (
        <EquipeDialog equipe={dialogue.data} departements={departements} users={users}
                      onClose={() => setDialogue(null)} onSaved={fermerEtRecharger} />
      )}
      {dialogue?.kind === 'poste' && (
        <PosteDialog poste={dialogue.data} departements={departements} roles={roles}
                     onClose={() => setDialogue(null)} onSaved={fermerEtRecharger} />
      )}
    </div>
  )
}
