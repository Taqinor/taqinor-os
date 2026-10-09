// SPL53 — LES BANDEAUX D'ÉDITION DU GÉNÉRATEUR, déplacés tels quels de
// DevisGenerator.jsx : devis envoyé, conflit de verrou (QJR549), attente de
// signature + compteurs (QJR540), reprise de brouillon et continuité EZ4,
// chargement / échec des référentiels, avertissements de vente (ZSAL9).
// `ScrollProgress`, `PageHeader` et l'ouverture du `<form noValidate>` restent
// dans la coquille. Props nommées une par une, jamais de spread.
import { Button, RelationCounters } from '../../../ui'
import { formatDateTime, formatDate } from '../../../lib/format'

export default function BandeauxEdition({
  editDevis, conflitVerrou, setConflitVerrou, clear, setRechargeEdit, forcerSansJetonRef,
  handleSubmit, brouillonProposable, restored, handleRestoreDraft, discard, savedAt, refsLoading,
  loadFailed, saleWarnings,
}) {
  return (
    <>
      {editDevis?.statut === 'envoye' && (
        <div
          data-testid="devis-envoye-banner"
          role="status"
          className="rounded-lg border border-warning/40 bg-warning/10 p-3 text-sm text-warning"
        >
          Devis envoyé{editDevis.date_envoi ? ` le ${formatDate(editDevis.date_envoi)}` : ''} :
          vos corrections seront visibles sur le lien de la proposition ; un PDF déjà envoyé
          par email ou WhatsApp n'est pas mis à jour — renvoyez-le si besoin. Le statut reste Envoyé.
        </div>
      )}
      {/* QJR549 (ex-DevisForm VX243c) — bannière NON bloquante : le devis a
          été enregistré ailleurs pendant cette édition (409 devis_modifie). */}
      {conflitVerrou && (
        <div
          data-testid="devis-verrou-banner"
          role="alert"
          className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-warning/40 bg-warning/10 p-3 text-sm text-warning"
        >
          <span>
            Modifié par {conflitVerrou.par || 'un autre utilisateur'}
            {' '}pendant votre édition — vérifiez avant d'enregistrer.
          </span>
          <span className="flex gap-2">
            <Button
              type="button" size="sm" variant="outline"
              onClick={() => { setConflitVerrou(null); clear(); setRechargeEdit(n => n + 1) }}
            >
              Revoir
            </Button>
            <Button
              type="button" size="sm" variant="outline"
              onClick={() => {
                forcerSansJetonRef.current = true
                setConflitVerrou(null)
                handleSubmit({ preventDefault: () => {} })
              }}
            >
              Enregistrer quand même
            </Button>
          </span>
        </div>
      )}
      {/* QJR540 (ex-DevisForm VX250) — lecture PURE du statut chargé : ne
          change jamais un statut (règle #4). */}
      {editDevis?.statut === 'envoye' && (
        <p
          data-testid="devis-attente-signature"
          role="status"
          className="rounded-lg border border-warning/30 bg-warning/10 px-3 py-2 text-sm text-warning"
        >
          En attente de signature client
        </p>
      )}
      {/* QJR540 (ex-DevisForm VX159/VX250) — compteurs dérivés du devis
          déjà chargé : zéro appel réseau nouveau. */}
      {editDevis?.id && (
        <RelationCounters
          counters={[
            {
              label: 'factures liées',
              count: editDevis.factures_liees?.length ?? 0,
              to: `/ventes/factures?q=${encodeURIComponent(editDevis.client_nom ?? '')}`,
            },
            { label: 'bon de commande', count: editDevis.bon_commande_etat ? 1 : 0 },
            {
              label: 'chantier',
              count: editDevis.chantier ? 1 : 0,
              to: editDevis.chantier ? `/chantiers?id=${editDevis.chantier.id}` : undefined,
            },
          ]}
        />
      )}
      {brouillonProposable && (
        <div
          data-testid="draft-restore-banner"
          className="flex flex-col gap-2 rounded-lg border border-warning/40 bg-warning/10 p-3 text-sm text-warning sm:flex-row sm:items-center sm:justify-between"
        >
          <span>
            Un brouillon non enregistré du{' '}
            {(() => {
              try { return formatDateTime(restored.savedAt) }
              catch { return 'précédent' }
            })()}{' '}
            a été retrouvé.
          </span>
          <div className="flex gap-2">
            <Button type="button" size="sm" variant="outline" onClick={handleRestoreDraft}>
              Reprendre le brouillon
            </Button>
            <Button type="button" size="sm" variant="ghost" onClick={discard}>
              Ignorer
            </Button>
          </div>
        </div>
      )}
      {/* EZ4 — la confiance vient de la CONTINUITÉ VISIBLE (patron
          Docs/Notion) : tant qu'on ne voit rien, on ne sait pas si le travail
          est à l'abri. Discret, jamais bloquant. */}
      {savedAt && (
        <p
          data-testid="draft-saved-indicator"
          className="text-xs text-muted-foreground"
          role="status"
        >
          Brouillon enregistré à{' '}
          {(() => {
            try {
              return new Date(savedAt).toLocaleTimeString('fr-FR', {
                hour: '2-digit', minute: '2-digit',
              })
            } catch { return 'l’instant' }
          })()}
        </p>
      )}
      {refsLoading && (
        <div className="rounded-lg border border-info/30 bg-info/10 p-3 text-sm text-info">
          Chargement des données (leads, clients, produits)…
        </div>
      )}
      {loadFailed.length > 0 && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          Échec du chargement : {loadFailed.join(', ')}. Vérifiez votre connexion puis rechargez la page.
        </div>
      )}
      {/* ZSAL9 — avertissements de vente (client/produits) : bannière non
          intrusive ; un avertissement bloquant est signalé mais n'empêche pas
          la saisie (le blocage réel est côté serveur à l'acceptation). */}
      {saleWarnings.length > 0 && (
        <div
          data-testid="sale-warnings"
          className="flex flex-col gap-1 rounded-lg border border-warning/40 bg-warning/10 p-3 text-sm text-warning"
        >
          {saleWarnings.map(w => (
            <div key={w.key}>
              <span className="font-medium">{w.cible} :</span> {w.message}
              {w.bloquant && (
                <span className="ml-1 font-medium">
                  (bloquant — un responsable devra passer outre)
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </>
  )
}
