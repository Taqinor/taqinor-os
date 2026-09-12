import { useCallback, useEffect, useState } from 'react'
import { ClipboardCheck } from 'lucide-react'
import { Badge, Button, toast } from '../../ui'
import btpChantierApi from '../../api/btpChantierApi'
import { frenchError } from '../../lib/frenchError'
import ChantierSelect from './ChantierSelect'

/* ============================================================================
   NTCON24 — Assistant guidé « Clôture de chantier » (DGD + export dossier).
   ----------------------------------------------------------------------------
   Trois étapes, une seule action enchaînée côté serveur :
     1. PRÉ-REQUIS — réserves bloquantes levées (NTCON1/2), visas décidés et
        approuvés (NTCON5), PPSPS signé par tous les sous-traitants actifs
        (NTCON16). Le serveur renvoie la LISTE PRÉCISE de ce qui bloque ;
        l'écran l'affiche telle quelle, jamais un « non conforme » générique.
     2. DGD — montant du marché initial (NTCON9).
     3. CLÔTURE — un POST enchaîne vérification → DGD → notification, puis le
        dossier consolidé (NTCON20) se télécharge d'un clic.
   ========================================================================== */

const ETAPES = ['Pré-requis', 'Décompte général', 'Clôture']

export default function ClotureChantierBtpWizard() {
  const [chantierId, setChantierId] = useState('')
  const [etape, setEtape] = useState(0)
  const [prerequis, setPrerequis] = useState(null)
  const [montant, setMontant] = useState('')
  const [resultat, setResultat] = useState(null)
  const [enCours, setEnCours] = useState(false)

  const verifier = useCallback(() => {
    if (!chantierId) { setPrerequis(null); return undefined }
    let cancelled = false
    btpChantierApi.cloture.prerequis(chantierId)
      .then((res) => { if (!cancelled) setPrerequis(res?.data || null) })
      .catch(() => { if (!cancelled) setPrerequis(null) })
    return () => { cancelled = true }
  }, [chantierId])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement
  useEffect(() => verifier(), [verifier])

  const cloturer = async () => {
    setEnCours(true)
    try {
      const res = await btpChantierApi.cloture.cloturer(chantierId, {
        montant_marche_initial_ht: montant || 0,
      })
      setResultat(res?.data || null)
      toast.success('Chantier clôturé — décompte général notifié.')
    } catch (err) {
      const blocages = err?.response?.data?.blocages
      if (Array.isArray(blocages) && blocages.length) {
        setPrerequis({ pret: false, blocages })
        setEtape(0)
      }
      toast.error(frenchError(err, 'Clôture impossible.'))
    } finally {
      setEnCours(false)
    }
  }

  const telechargerDossier = async () => {
    try {
      const res = await btpChantierApi.exportDossierBtp(chantierId)
      const url = window.URL.createObjectURL(new Blob([res.data]))
      const a = document.createElement('a')
      a.href = url
      a.download = `dossier-chantier-${chantierId}.zip`
      a.click()
      window.URL.revokeObjectURL(url)
    } catch (err) {
      toast.error(frenchError(err, 'Export du dossier impossible.'))
    }
  }

  const pret = Boolean(prerequis?.pret)

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        <ClipboardCheck size={20} strokeWidth={1.75} aria-hidden="true" />
        <h1 style={{ fontSize: 18, fontWeight: 600, margin: 0 }}>
          Clôture de chantier BTP
        </h1>
      </div>

      <ol
        aria-label="Étapes de la clôture"
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

      <div style={{ display: 'flex', gap: 8, margin: '16px 0', flexWrap: 'wrap' }}>
        <ChantierSelect
          value={chantierId}
          onChange={(v) => { setChantierId(v); setEtape(0); setResultat(null) }}
          label="Chantier à clôturer"
        />
      </div>

      {!chantierId && <p>Choisissez le chantier à clôturer.</p>}

      {chantierId && etape === 0 && (
        <div data-testid="btp-cloture-prerequis">
          {prerequis === null && <p>Vérification…</p>}
          {pret && <p>Tous les pré-requis sont satisfaits.</p>}
          {prerequis && !pret && (
            <>
              <p>La clôture est bloquée par :</p>
              <ul>
                {prerequis.blocages.map((blocage) => (
                  <li key={blocage}>{blocage}</li>
                ))}
              </ul>
            </>
          )}
          <div style={{ display: 'flex', gap: 8 }}>
            <Button type="button" variant="outline" onClick={verifier}>
              Revérifier
            </Button>
            <Button type="button" onClick={() => setEtape(1)} disabled={!pret}>
              Suivant
            </Button>
          </div>
        </div>
      )}

      {chantierId && etape === 1 && (
        <div>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            Montant du marché initial HT
            <input
              type="number"
              step="any"
              aria-label="Montant du marché initial HT"
              value={montant}
              onChange={(e) => setMontant(e.target.value)}
            />
          </label>
          <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
            <Button type="button" variant="outline" onClick={() => setEtape(0)}>
              Précédent
            </Button>
            <Button type="button" onClick={() => setEtape(2)}>Suivant</Button>
          </div>
        </div>
      )}

      {chantierId && etape === 2 && (
        <div>
          {!resultat && (
            <>
              <p>
                La clôture génère le décompte général, le notifie, puis met le
                dossier consolidé à disposition.
              </p>
              <div style={{ display: 'flex', gap: 8 }}>
                <Button type="button" variant="outline" onClick={() => setEtape(1)}>
                  Précédent
                </Button>
                <Button type="button" onClick={cloturer} disabled={enCours}>
                  {enCours ? 'Clôture…' : 'Clôturer le chantier'}
                </Button>
              </div>
            </>
          )}
          {resultat && (
            <div data-testid="btp-cloture-resultat">
              <p>
                Décompte général {resultat.dgd?.reference} notifié
                ({resultat.dgd?.statut}).
              </p>
              <Button type="button" onClick={telechargerDossier}>
                Télécharger le dossier de chantier
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
