import { useEffect, useMemo, useState } from 'react'
import { Coins, Landmark } from 'lucide-react'
import { DetailShell } from '../../ui/module'
import { Badge, Button, DefinitionList, EmptyState, Spinner } from '../../ui'
import { formatMAD, formatDate } from '../../lib/format'
import juridiqueApi from '../../api/juridiqueApi'
import { useHasPermission, useIsAdmin } from '../../hooks/useHasPermission'
import {
  StatutDossierPill, ConfidentialitePill, StatutMandatPill, StatutNotePill,
  StatutAudiencePill, NATURE_MAP, PROCEDURE_MAP, POSITION_MAP, estClos,
} from './juridiqueStatus'
import ProvisionPanel from './ProvisionPanel'
import WizardClotureDossier from './WizardClotureDossier'

/* ============================================================================
   NTJUR22 — Détail d'un dossier juridique (onglets).
   ----------------------------------------------------------------------------
   Résumé · Audiences & délais · Conseils & honoraires · Budget · Historique.

   TOUT est chargé en UN passage au montage (``Promise.all``) : aucun onglet ne
   déclenche un appel en ouvrant, donc aucun onglet ne peut être « vide en
   attendant » ni renvoyer une erreur au clic. Un Directeur ouvrant un dossier
   confidentiel voit donc tous les onglets peuplés, sans appel en erreur.

   PÉRIMÈTRE ASSUMÉ : l'onglet « Pièces (GED) » du plan n'est PAS rendu ici —
   le dossier GED d'un dossier juridique (NTJUR16) et son ACL (NTJUR17) ne sont
   pas encore construits. Un onglet qui appellerait un endpoint inexistant
   contredirait le critère d'acceptation (« sans appel API en erreur ») : il
   arrivera avec NTJUR16/17.

   « Proposer une provision » n'est visible qu'au palier comptable /
   Administrateur — exactement les droits que le serveur exige
   (``compta_saisir`` + ``juridique_gerer_mandats``, NTJUR14/NTJUR39).
   ========================================================================== */

export default function DossierDetailPage({ dossierId, onBack, onChanged }) {
  const [dossier, setDossier] = useState(null)
  const [budget, setBudget] = useState(null)
  const [timeline, setTimeline] = useState([])
  const [audiences, setAudiences] = useState([])
  const [delais, setDelais] = useState([])
  const [mandats, setMandats] = useState([])
  const [notes, setNotes] = useState([])
  const [loading, setLoading] = useState(true)
  const [erreur, setErreur] = useState(null)
  // NTJUR32 — le wizard n'écrit RIEN tant qu'il n'est pas confirmé : l'ouvrir
  // puis le refermer laisse le dossier exactement dans son statut précédent.
  const [clotureOuverte, setClotureOuverte] = useState(false)

  const estAdmin = useIsAdmin()
  const peutEngager = useHasPermission('juridique_gerer_mandats')
  // Le serveur exige compta_saisir ET juridique_gerer_mandats, avec repli
  // légacy pour les comptes sans rôle fin (un administrateur passe toujours).
  const peutProvisionner = estAdmin || peutEngager

  const lignes = (data) => (
    Array.isArray(data) ? data : (data?.results ?? []))

  const charger = () => {
    setLoading(true)
    setErreur(null)
    return Promise.all([
      juridiqueApi.get(dossierId),
      juridiqueApi.budget(dossierId),
      juridiqueApi.timeline(dossierId),
      juridiqueApi.audiences({ dossier: dossierId }),
      juridiqueApi.delaisPrescription({ dossier: dossierId }),
      juridiqueApi.mandats({ dossier: dossierId }),
      juridiqueApi.notesHonoraires({ dossier: dossierId }),
    ])
      .then(([d, b, t, a, dl, m, n]) => {
        setDossier(d.data)
        setBudget(b.data)
        setTimeline(lignes(t.data))
        setAudiences(lignes(a.data))
        setDelais(lignes(dl.data))
        setMandats(lignes(m.data))
        setNotes(lignes(n.data))
      })
      .catch(() => setErreur('Impossible de charger ce dossier juridique.'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount
    charger()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dossierId])

  const resume = useMemo(() => {
    if (!dossier) return []
    return [
      { term: 'Référence', description: dossier.reference || '—' },
      {
        term: 'Nature',
        description: NATURE_MAP[dossier.nature] || dossier.nature || '—',
      },
      {
        term: 'Procédure',
        description: PROCEDURE_MAP[dossier.type_procedure]
          || dossier.type_procedure || '—',
      },
      {
        term: 'Juridiction',
        description: [dossier.juridiction_nom, dossier.juridiction_ville]
          .filter(Boolean).join(' · ') || '—',
      },
      { term: 'Partie adverse', description: dossier.partie_adverse_nom || '—' },
      {
        term: 'Notre position',
        description: POSITION_MAP[dossier.notre_position]
          || dossier.notre_position || '—',
      },
      { term: 'Montant en jeu', description: formatMAD(dossier.montant_en_jeu) },
      {
        term: "Date d'ouverture",
        description: dossier.date_ouverture
          ? formatDate(dossier.date_ouverture) : '—',
      },
      {
        term: 'Responsable',
        description: dossier.responsable_interne_nom || '—',
      },
    ]
  }, [dossier])

  if (loading || !dossier) {
    return (
      <div className="page flex items-center gap-2 text-muted-foreground">
        {erreur
          ? <EmptyState title="Dossier indisponible" description={erreur} />
          : <><Spinner className="size-4" /> Chargement…</>}
      </div>
    )
  }

  // ── Onglet Résumé ──
  const ongletResume = (
    <div className="flex flex-col gap-4">
      {dossier.resume_faits && (
        <div className="whitespace-pre-wrap rounded-lg border border-border p-3 text-sm leading-relaxed">
          {dossier.resume_faits}
        </div>
      )}
      <DefinitionList items={resume} />
      {peutProvisionner && (
        <ProvisionPanel
          dossier={dossier}
          onChanged={(maj) => { setDossier(maj); onChanged?.() }}
        />
      )}
    </div>
  )

  // ── Onglet Audiences & délais ──
  const ongletEcheancier = (
    <div className="flex flex-col gap-4">
      <section>
        <h3 className="mb-2 text-sm font-semibold">Audiences</h3>
        {audiences.length ? (
          <ul className="flex flex-col gap-2">
            {audiences.map((a) => (
              <li key={a.id} className="rounded-lg border border-border px-3 py-2 text-sm">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium">{formatDate(a.date_audience)}</span>
                  <StatutAudiencePill status={a.statut} />
                </div>
                <div className="mt-1 text-muted-foreground">
                  {a.type_audience} {a.juridiction_salle ? `· ${a.juridiction_salle}` : ''}
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState
            title="Aucune audience"
            description="Aucune audience n'est programmée sur ce dossier."
          />
        )}
      </section>
      <section>
        <h3 className="mb-2 text-sm font-semibold">Délais de prescription</h3>
        {delais.length ? (
          <ul className="flex flex-col gap-2">
            {delais.map((d) => (
              <li key={d.id} className="rounded-lg border border-border px-3 py-2 text-sm">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium">{d.type_delai}</span>
                  <Badge tone={d.jours_restants != null && d.jours_restants <= 30
                    ? 'danger' : 'neutral'}
                  >
                    {d.jours_restants != null
                      ? `${d.jours_restants} j restant(s)` : '—'}
                  </Badge>
                </div>
                <div className="mt-1 text-muted-foreground">
                  Limite : {formatDate(d.date_limite)}
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState
            title="Aucun délai suivi"
            description="Aucun délai de prescription n'est enregistré."
          />
        )}
      </section>
    </div>
  )

  // ── Onglet Conseils & honoraires ──
  const ongletConseils = (
    <div className="flex flex-col gap-4">
      <section>
        <h3 className="mb-2 text-sm font-semibold">Mandats</h3>
        {mandats.length ? (
          <ul className="flex flex-col gap-2">
            {mandats.map((m) => (
              <li key={m.id} className="rounded-lg border border-border px-3 py-2 text-sm">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium">{m.cabinet_nom || '—'}</span>
                  <StatutMandatPill status={m.statut} />
                </div>
                <div className="mt-1 text-muted-foreground">
                  {m.mode_facturation} · engagé {formatMAD(m.montant_engage)}
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState
            title="Aucun mandat"
            description="Aucun cabinet n'est mandaté sur ce dossier."
          />
        )}
      </section>
      <section>
        <h3 className="mb-2 text-sm font-semibold">Notes d'honoraires</h3>
        {notes.length ? (
          <ul className="flex flex-col gap-2">
            {notes.map((n) => (
              <li key={n.id} className="rounded-lg border border-border px-3 py-2 text-sm">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-xs">{n.reference || '—'}</span>
                  <StatutNotePill status={n.statut} />
                </div>
                <div className="mt-1 text-muted-foreground">
                  {formatDate(n.date_facture)} · {formatMAD(n.montant_ttc)} TTC
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState
            title="Aucune note d'honoraires"
            description="Aucune note reçue pour ce dossier."
          />
        )}
      </section>
    </div>
  )

  // ── Onglet Budget ──
  const ongletBudget = (
    <div className="flex flex-col gap-4">
      <DefinitionList items={[
        {
          term: 'Budget alloué',
          description: budget?.budget_alloue != null
            ? formatMAD(budget.budget_alloue)
            : 'Aucune enveloppe fixée',
        },
        { term: 'Engagé', description: formatMAD(budget?.engage) },
        { term: 'Consommé', description: formatMAD(budget?.consomme) },
        {
          term: 'Consommation',
          // Jamais un « 0 % » inventé : sans enveloppe, le pourcentage n'existe
          // simplement pas côté serveur.
          description: budget?.pourcentage_consomme != null
            ? `${budget.pourcentage_consomme} %`
            : '—',
        },
      ]}
      />
      {budget?.depassement && (
        <div className="rounded-lg border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm">
          <Coins className="mr-1 inline size-4" aria-hidden="true" />
          Le budget alloué de ce dossier est dépassé.
        </div>
      )}
    </div>
  )

  // ── Onglet Historique (timeline unifiée NTJUR20) ──
  const ongletHistorique = timeline.length ? (
    <ul className="flex flex-col gap-2">
      {timeline.map((e) => (
        <li key={`${e.type}-${e.id}`} className="rounded-lg border border-border px-3 py-2 text-sm">
          <div className="flex items-center justify-between gap-2">
            <Badge tone={e.type === 'chatter' ? 'neutral' : 'info'}>{e.type}</Badge>
            <span className="text-xs text-muted-foreground">
              {e.auteur ? `${e.auteur} · ` : ''}{formatDate(e.date)}
            </span>
          </div>
          <div className="mt-1">
            <span className="font-medium">{e.libelle}</span>
            {e.detail ? <span className="text-muted-foreground"> — {e.detail}</span> : null}
          </div>
        </li>
      ))}
    </ul>
  ) : (
    <EmptyState
      title="Aucun événement"
      description="Ce dossier n'a encore aucune activité enregistrée."
    />
  )

  const actions = (
    <>
      <ConfidentialitePill status={dossier.confidentialite} />
      {!estClos(dossier.statut) && (
        <Button
          type="button"
          variant="outline"
          onClick={() => setClotureOuverte(true)}
        >
          <Landmark /> Clôturer le dossier
        </Button>
      )}
    </>
  )

  return (
    <div className="page flex flex-col gap-4">
      <button
        type="button"
        onClick={onBack}
        className="inline-flex w-fit items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        ← Retour au registre
      </button>
      <DetailShell
        title={dossier.titre}
        subtitle={dossier.reference || undefined}
        status={dossier.statut}
        statusPill={StatutDossierPill}
        actions={actions}
        tabs={[
          { value: 'resume', label: 'Résumé', content: ongletResume },
          {
            value: 'echeancier',
            label: 'Audiences & délais',
            count: audiences.length + delais.length,
            content: ongletEcheancier,
          },
          {
            value: 'conseils',
            label: 'Conseils & honoraires',
            count: mandats.length + notes.length,
            content: ongletConseils,
          },
          { value: 'budget', label: 'Budget', content: ongletBudget },
          {
            value: 'historique',
            label: 'Historique',
            count: timeline.length,
            content: ongletHistorique,
          },
        ]}
      />
      {clotureOuverte && (
        <WizardClotureDossier
          dossier={dossier}
          onAnnuler={() => setClotureOuverte(false)}
          onClos={(maj) => {
            setClotureOuverte(false)
            if (maj) setDossier(maj)
            charger()
            onChanged?.()
          }}
        />
      )}
    </div>
  )
}
