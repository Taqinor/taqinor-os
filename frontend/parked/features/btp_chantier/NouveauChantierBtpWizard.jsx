import { useCallback, useEffect, useState } from 'react'
import { Wand2 } from 'lucide-react'
import { Badge, Button, toast } from '../../ui'
import btpChantierApi from '../../api/btpChantierApi'
import installationsApi from '../../api/installationsApi'
import { frenchError } from '../../lib/frenchError'
import ChantierSelect from './ChantierSelect'
import {
  BROUILLON_CLE, chargerBrouillon, effacerBrouillon, enregistrerBrouillon,
  lotsSuggeres,
} from './nouveauChantierBtp.utils'

/* ============================================================================
   NTCON23 — Assistant guidé « Créer un chantier BTP ».
   ----------------------------------------------------------------------------
   Quatre étapes enchaînées, toutes branchées sur des endpoints DÉJÀ construits
   (aucune nouvelle logique backend) :
     1. chantier cible (`installations.Installation`)
     2. lots (NTCON14) — types TCE pré-remplis, entièrement éditables
     3. affectation par lot : interne (régie) ou sous-traitant (FG304/DC34)
     4. PPSPS initial (NTCON16, OPTIONNEL) + checklist de réception par lot
        (NTCON19, modèle par défaut)

   Brouillon SAUVEGARDÉ à chaque étape (localStorage, par navigateur) : un
   abandon en cours de route se reprend là où il s'est arrêté. Les lectures et
   écritures localStorage sont protégées (navigation privée, site data bloqué).
   ========================================================================== */

const ETAPES = [
  'Chantier', 'Lots', 'Affectation', 'PPSPS et checklist',
]

export default function NouveauChantierBtpWizard() {
  const [etape, setEtape] = useState(0)
  const [brouillon, setBrouillon] = useState(() => chargerBrouillon())
  const [sousTraitants, setSousTraitants] = useState([])
  const [enCours, setEnCours] = useState(false)
  const [resultat, setResultat] = useState(null)

  useEffect(() => {
    let cancelled = false
    installationsApi.getSousTraitants()
      .then((res) => {
        if (cancelled) return
        const payload = res?.data
        setSousTraitants(
          Array.isArray(payload) ? payload
            : Array.isArray(payload?.results) ? payload.results : [])
      })
      .catch(() => { if (!cancelled) setSousTraitants([]) })
    return () => { cancelled = true }
  }, [])

  const majBrouillon = useCallback((patch) => {
    setBrouillon((precedent) => {
      const suivant = { ...precedent, ...patch }
      enregistrerBrouillon(suivant)
      return suivant
    })
  }, [])

  const majLot = (index, patch) => {
    const lots = brouillon.lots.map(
      (lot, i) => (i === index ? { ...lot, ...patch } : lot))
    majBrouillon({ lots })
  }

  const retirerLot = (index) => {
    majBrouillon({ lots: brouillon.lots.filter((_, i) => i !== index) })
  }

  const ajouterLot = () => {
    majBrouillon({
      lots: [...brouillon.lots, {
        nom: '', interne: true, sous_traitant: '',
        date_debut_prevue: '', date_fin_prevue: '',
      }],
    })
  }

  const prefRemplirLotsTypes = () => {
    majBrouillon({ lots: lotsSuggeres() })
  }

  const peutAvancer = () => {
    if (etape === 0) return Boolean(brouillon.chantier)
    if (etape === 1) {
      return brouillon.lots.length > 0
        && brouillon.lots.every((lot) => lot.nom.trim())
    }
    if (etape === 2) {
      return brouillon.lots.every(
        (lot) => lot.interne || lot.sous_traitant)
    }
    return true
  }

  const creer = async () => {
    setEnCours(true)
    try {
      const lotsCrees = []
      for (const [index, lot] of brouillon.lots.entries()) {
        const res = await btpChantierApi.lots.create({
          chantier: brouillon.chantier,
          nom: lot.nom.trim(),
          ordre: index + 1,
          interne: Boolean(lot.interne),
          sous_traitant: lot.interne ? null : Number(lot.sous_traitant),
          date_debut_prevue: lot.date_debut_prevue || null,
          date_fin_prevue: lot.date_fin_prevue || null,
        })
        lotsCrees.push(res?.data?.id)
      }

      if (brouillon.checklistParDefaut) {
        for (const lotId of lotsCrees) {
          await btpChantierApi.lots.definirChecklist(lotId, [])
        }
      }

      let ppspsCree = null
      if (brouillon.ppspsTitre || brouillon.ppspsDocumentGedId) {
        const res = await btpChantierApi.ppsps.create({
          chantier: brouillon.chantier,
          titre: brouillon.ppspsTitre || '',
          document_ged_id: brouillon.ppspsDocumentGedId
            ? Number(brouillon.ppspsDocumentGedId) : null,
          lots_couverts: lotsCrees,
        })
        ppspsCree = res?.data?.id || null
      }

      setResultat({ lots: lotsCrees.length, ppsps: ppspsCree })
      effacerBrouillon()
      toast.success('Chantier BTP initialisé.')
    } catch (err) {
      toast.error(frenchError(err, "Impossible de terminer l'assistant."))
    } finally {
      setEnCours(false)
    }
  }

  const recommencer = () => {
    effacerBrouillon()
    setBrouillon(chargerBrouillon())
    setResultat(null)
    setEtape(0)
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        <Wand2 size={20} strokeWidth={1.75} aria-hidden="true" />
        <h1 style={{ fontSize: 18, fontWeight: 600, margin: 0 }}>
          Créer un chantier BTP
        </h1>
      </div>

      <ol
        aria-label="Étapes de l'assistant"
        style={{ display: 'flex', gap: 12, listStyle: 'none', padding: 0, flexWrap: 'wrap' }}
      >
        {ETAPES.map((libelle, index) => (
          <li key={libelle}>
            <Badge tone={index === etape ? 'info' : 'neutral'}>
              {index + 1}. {libelle}
            </Badge>
          </li>
        ))}
      </ol>

      {resultat && (
        <div data-testid="btp-wizard-resultat" style={{ marginTop: 16 }}>
          <p>
            {resultat.lots} lot(s) créé(s)
            {resultat.ppsps ? ' · PPSPS initial déposé' : ''}
            {brouillon.checklistParDefaut
              ? ' · checklist de réception posée par lot' : ''}.
          </p>
          <Button type="button" onClick={recommencer}>Nouvel assistant</Button>
        </div>
      )}

      {!resultat && (
        <div style={{ marginTop: 16 }}>
          {etape === 0 && (
            <div>
              <p>Sur quel chantier (projet/installation) travaillons-nous ?</p>
              <ChantierSelect
                value={brouillon.chantier}
                onChange={(v) => majBrouillon({ chantier: v })}
                label="Chantier cible"
                required
              />
            </div>
          )}

          {etape === 1 && (
            <div>
              <p>
                Définissez les lots du chantier — les corps d&apos;état
                classiques sont proposés, tout est éditable.
              </p>
              <Button type="button" variant="outline" onClick={prefRemplirLotsTypes}>
                Proposer les lots types
              </Button>
              <ul style={{ listStyle: 'none', padding: 0, marginTop: 12 }}>
                {brouillon.lots.map((lot, index) => (
                  <li
                    key={`lot-${index}`}
                    style={{ display: 'flex', gap: 8, marginBottom: 8, flexWrap: 'wrap' }}
                  >
                    <input
                      aria-label={`Nom du lot ${index + 1}`}
                      value={lot.nom}
                      onChange={(e) => majLot(index, { nom: e.target.value })}
                    />
                    <input
                      type="date"
                      aria-label={`Début prévu du lot ${index + 1}`}
                      value={lot.date_debut_prevue || ''}
                      onChange={(e) => majLot(index, { date_debut_prevue: e.target.value })}
                    />
                    <input
                      type="date"
                      aria-label={`Fin prévue du lot ${index + 1}`}
                      value={lot.date_fin_prevue || ''}
                      onChange={(e) => majLot(index, { date_fin_prevue: e.target.value })}
                    />
                    <Button
                      type="button"
                      variant="ghost"
                      onClick={() => retirerLot(index)}
                    >
                      Retirer
                    </Button>
                  </li>
                ))}
              </ul>
              <Button type="button" variant="outline" onClick={ajouterLot}>
                Ajouter un lot
              </Button>
            </div>
          )}

          {etape === 2 && (
            <div>
              <p>Qui exécute chaque lot ?</p>
              <ul style={{ listStyle: 'none', padding: 0 }}>
                {brouillon.lots.map((lot, index) => (
                  <li
                    key={`aff-${index}`}
                    style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 8, flexWrap: 'wrap' }}
                  >
                    <strong style={{ minWidth: 120 }}>{lot.nom || `Lot ${index + 1}`}</strong>
                    <label style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      <input
                        type="checkbox"
                        aria-label={`Lot ${lot.nom || index + 1} exécuté en interne`}
                        checked={Boolean(lot.interne)}
                        onChange={(e) => majLot(index, {
                          interne: e.target.checked,
                          sous_traitant: e.target.checked ? '' : lot.sous_traitant,
                        })}
                      />
                      Interne (régie)
                    </label>
                    {!lot.interne && (
                      <select
                        aria-label={`Sous-traitant du lot ${lot.nom || index + 1}`}
                        value={lot.sous_traitant || ''}
                        onChange={(e) => majLot(index, { sous_traitant: e.target.value })}
                      >
                        <option value="">Sous-traitant…</option>
                        {sousTraitants.map((st) => (
                          <option key={st.id} value={st.id}>{st.nom}</option>
                        ))}
                      </select>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {etape === 3 && (
            <div>
              <p>
                PPSPS initial (facultatif à cette étape) et checklist de
                réception par lot.
              </p>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
                <input
                  aria-label="Titre du PPSPS"
                  placeholder="Titre du PPSPS"
                  value={brouillon.ppspsTitre || ''}
                  onChange={(e) => majBrouillon({ ppspsTitre: e.target.value })}
                />
                <input
                  aria-label="Identifiant du document GED du PPSPS"
                  placeholder="Document GED (id)"
                  value={brouillon.ppspsDocumentGedId || ''}
                  onChange={(e) => majBrouillon({ ppspsDocumentGedId: e.target.value })}
                />
              </div>
              <label style={{ display: 'flex', alignItems: 'center', gap: 4, marginTop: 8 }}>
                <input
                  type="checkbox"
                  aria-label="Poser la checklist de réception par défaut sur chaque lot"
                  checked={Boolean(brouillon.checklistParDefaut)}
                  onChange={(e) => majBrouillon({ checklistParDefaut: e.target.checked })}
                />
                Poser la checklist de réception par défaut sur chaque lot
              </label>
            </div>
          )}

          <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
            <Button
              type="button"
              variant="outline"
              onClick={() => setEtape((e) => Math.max(e - 1, 0))}
              disabled={etape === 0}
            >
              Précédent
            </Button>
            {etape < ETAPES.length - 1 && (
              <Button
                type="button"
                onClick={() => setEtape((e) => e + 1)}
                disabled={!peutAvancer()}
              >
                Suivant
              </Button>
            )}
            {etape === ETAPES.length - 1 && (
              <Button type="button" onClick={creer} disabled={enCours}>
                {enCours ? 'Création…' : 'Créer le chantier BTP'}
              </Button>
            )}
          </div>

          <p style={{ marginTop: 12, fontSize: 12, color: '#64748b' }}>
            Brouillon enregistré automatiquement ({BROUILLON_CLE}) — vous
            pourrez reprendre là où vous en êtes.
          </p>
        </div>
      )}
    </div>
  )
}
