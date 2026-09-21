/* NTCON36 — Capture terrain rapide, mobile-first et tolérante au réseau.
 *
 * DEUX GESTES, DEUX TAPS : poser une réserve (avec photo prise depuis la
 * caméra du téléphone) ou compléter l'entrée du jour du journal de chantier.
 * Le formulaire est MINIMAL : ce qu'on saisit debout sur un chantier, pas la
 * fiche complète des écrans de bureau (`/btp-chantier/reserves`,
 * `/btp-chantier/journal`), qui restent la référence.
 *
 * HORS-LIGNE — AUCUN SECOND MÉCANISME. L'opération structurée part dans la
 * file GÉNÉRIQUE du dépôt (`lib/offlineOutbox.queueIfOffline`, jumelle côté
 * serveur du moteur `apps.offlinesync` NTMOB1, où `apps/btp_chantier/
 * offline_ops.py` enregistre ses deux op_types). Le BROUILLON de saisie, lui,
 * vit en `localStorage` — c'est explicitement ce que demande NTCON36, et c'est
 * autre chose qu'une file : il protège la SAISIE EN COURS (onglet fermé,
 * batterie vide), la file protège l'ENVOI.
 *
 * LA PHOTO NE MENT PAS. Le moteur hors-ligne transporte du JSON, pas du
 * binaire : hors réseau, la photo reste dans le brouillon et l'écran le DIT
 * (« la photo sera à renvoyer au retour du réseau ») au lieu de la faire
 * disparaître en silence. En ligne, elle est téléversée par l'endpoint
 * multipart EXISTANT `records.Attachment`, phase « avant ».
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { Camera, CloudOff, MapPin, NotebookPen } from 'lucide-react'

import btpChantierApi from '../../api/btpChantierApi'
import recordsApi from '../../api/recordsApi'
import { queueIfOffline } from '../../lib/offlineOutbox'
import { Button } from '../../ui'
import { frenchError } from '../../lib/frenchError'
import ChantierSelect from '../../features/btp_chantier/ChantierSelect'

/** Clé unique du brouillon local (un seul brouillon terrain par terminal). */
const CLE_BROUILLON = 'btp.terrain.brouillon.v1'

/** Module de la file hors-ligne : « Chantiers » au catalogue `offlinesync`. */
const MODULE_OFFLINE = 'installations'

const OP_RESERVE = 'btp.reserve.creer'
const OP_JOURNAL = 'btp.journal.entree_du_jour'

const GRAVITES = [
  ['mineure', 'Mineure'],
  ['majeure', 'Majeure'],
  ['bloquante', 'Bloquante'],
]

const BROUILLON_VIDE = {
  onglet: 'reserve',
  chantierId: '',
  lot: '',
  description: '',
  gravite: 'mineure',
  meteo: '',
  evenements: '',
  photoNom: '',
}

function lireBrouillon() {
  try {
    const brut = window.localStorage.getItem(CLE_BROUILLON)
    if (!brut) return { ...BROUILLON_VIDE }
    return { ...BROUILLON_VIDE, ...JSON.parse(brut) }
  } catch {
    // Stockage indisponible (navigation privée, quota) : on démarre à vide
    // plutôt que de casser l'écran.
    return { ...BROUILLON_VIDE }
  }
}

function ecrireBrouillon(valeurs) {
  try {
    window.localStorage.setItem(CLE_BROUILLON, JSON.stringify(valeurs))
  } catch {
    /* quota / mode privé : le brouillon est un confort, jamais un prérequis */
  }
}

function effacerBrouillon() {
  try {
    window.localStorage.removeItem(CLE_BROUILLON)
  } catch {
    /* idem */
  }
}

export default function TerrainCapture() {
  const [form, setForm] = useState(lireBrouillon)
  const [photo, setPhoto] = useState(null)
  const [envoi, setEnvoi] = useState(false)
  const [message, setMessage] = useState(null)
  const [erreur, setErreur] = useState(null)

  // Brouillon persisté à CHAQUE frappe : une saisie faite debout sur un
  // chantier ne se perd pas parce que l'écran s'est verrouillé.
  useEffect(() => { ecrireBrouillon(form) }, [form])

  const set = useCallback((cle, valeur) => {
    setForm((prec) => ({ ...prec, [cle]: valeur }))
  }, [])

  const pretReserve = useMemo(
    () => Boolean(form.chantierId && form.description.trim()),
    [form.chantierId, form.description],
  )
  const pretJournal = useMemo(
    () => Boolean(form.chantierId && (form.meteo.trim() || form.evenements.trim())),
    [form.chantierId, form.meteo, form.evenements],
  )

  const reinitialiser = useCallback(() => {
    setForm({ ...BROUILLON_VIDE, chantierId: form.chantierId,
      onglet: form.onglet })
    setPhoto(null)
    effacerBrouillon()
  }, [form.chantierId, form.onglet])

  async function envoyerReserve() {
    const charge = {
      chantier: Number(form.chantierId),
      lot: form.lot.trim(),
      description: form.description.trim(),
      gravite: form.gravite,
      localisation_plan: {},
    }
    const resultat = await queueIfOffline(
      MODULE_OFFLINE,
      () => btpChantierApi.reserves.create(charge),
      OP_RESERVE,
      charge,
      { target: charge.chantier },
    )
    if (resultat.queued) {
      return {
        queued: true,
        avecPhotoEnAttente: Boolean(photo),
      }
    }
    const id = resultat.data?.data?.id
    if (photo && id) {
      // Photo « avant » sur la réserve — endpoint multipart EXISTANT.
      await recordsApi.uploadAttachment(
        'btp_chantier.reservechantier', id, photo, 'avant')
    }
    return { queued: false }
  }

  async function envoyerJournal() {
    const charge = {
      chantier: Number(form.chantierId),
      date: new Date().toISOString().slice(0, 10),
      meteo: form.meteo.trim(),
      evenements: form.evenements.trim(),
    }
    const resultat = await queueIfOffline(
      MODULE_OFFLINE,
      () => btpChantierApi.journal.create(charge),
      OP_JOURNAL,
      charge,
      { target: charge.chantier },
    )
    return { queued: Boolean(resultat.queued), avecPhotoEnAttente: false }
  }

  async function soumettre(event) {
    event.preventDefault()
    setErreur(null)
    setMessage(null)
    setEnvoi(true)
    try {
      const resultat = form.onglet === 'reserve'
        ? await envoyerReserve()
        : await envoyerJournal()
      if (resultat.queued) {
        setMessage(
          resultat.avecPhotoEnAttente
            ? 'Enregistré hors réseau : il partira à la reconnexion. '
              + 'La photo, elle, sera à renvoyer au retour du réseau.'
            : 'Enregistré hors réseau : il partira à la reconnexion.',
        )
        // Le brouillon reste tant que la photo n'a pas pu partir : rien ne
        // disparaît sans que l'utilisateur l'ait vu.
        if (!resultat.avecPhotoEnAttente) reinitialiser()
      } else {
        setMessage('Enregistré.')
        reinitialiser()
      }
    } catch (err) {
      // Erreur APPLICATIVE (4xx) : le serveur a répondu, l'utilisateur doit la
      // voir — `frenchError` NOMME le champ fautif quand le serveur l'a nommé
      // (règle fondateur : jamais un « non enregistré » générique).
      setErreur(frenchError(err) || "L'enregistrement a échoué.")
    } finally {
      setEnvoi(false)
    }
  }

  const pret = form.onglet === 'reserve' ? pretReserve : pretJournal

  return (
    <div
      data-testid="btp-terrain"
      style={{ maxWidth: 520, margin: '0 auto', padding: 12 }}
    >
      <h1 style={{ fontSize: 18, fontWeight: 600, margin: '0 0 12px' }}>
        Capture terrain
      </h1>

      <div role="tablist" aria-label="Type de saisie"
        style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <Button
          type="button"
          role="tab"
          aria-selected={form.onglet === 'reserve'}
          data-testid="btp-terrain-onglet-reserve"
          variant={form.onglet === 'reserve' ? 'default' : 'outline'}
          onClick={() => set('onglet', 'reserve')}
          style={{ flex: 1, minHeight: 48 }}
        >
          <MapPin size={17} strokeWidth={1.75} aria-hidden="true" />
          Réserve
        </Button>
        <Button
          type="button"
          role="tab"
          aria-selected={form.onglet === 'journal'}
          data-testid="btp-terrain-onglet-journal"
          variant={form.onglet === 'journal' ? 'default' : 'outline'}
          onClick={() => set('onglet', 'journal')}
          style={{ flex: 1, minHeight: 48 }}
        >
          <NotebookPen size={17} strokeWidth={1.75} aria-hidden="true" />
          Journal du jour
        </Button>
      </div>

      <form onSubmit={soumettre}
        style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <ChantierSelect
          value={form.chantierId}
          onChange={(valeur) => set('chantierId', valeur)}
        />

        {form.onglet === 'reserve' ? (
          <>
            <input
              placeholder="Lot (facultatif)"
              aria-label="Lot de la réserve"
              value={form.lot}
              onChange={(e) => set('lot', e.target.value)}
              style={{ minHeight: 44 }}
            />
            <textarea
              placeholder="Ce que vous constatez"
              aria-label="Description de la réserve"
              value={form.description}
              onChange={(e) => set('description', e.target.value)}
              rows={3}
            />
            <select
              aria-label="Gravité de la réserve"
              value={form.gravite}
              onChange={(e) => set('gravite', e.target.value)}
              style={{ minHeight: 44 }}
            >
              {GRAVITES.map(([valeur, libelle]) => (
                <option key={valeur} value={valeur}>{libelle}</option>
              ))}
            </select>
            <label
              style={{ display: 'flex', alignItems: 'center', gap: 8,
                minHeight: 44 }}
            >
              <Camera size={17} strokeWidth={1.75} aria-hidden="true" />
              <span>Photo</span>
              <input
                type="file"
                accept="image/*"
                capture="environment"
                aria-label="Photo de la réserve"
                data-testid="btp-terrain-photo"
                onChange={(e) => {
                  const fichier = e.target.files?.[0] || null
                  setPhoto(fichier)
                  set('photoNom', fichier ? fichier.name : '')
                }}
              />
            </label>
          </>
        ) : (
          <>
            <input
              placeholder="Météo"
              aria-label="Météo du jour"
              value={form.meteo}
              onChange={(e) => set('meteo', e.target.value)}
              style={{ minHeight: 44 }}
            />
            <textarea
              placeholder="Événements du jour"
              aria-label="Événements du jour"
              value={form.evenements}
              onChange={(e) => set('evenements', e.target.value)}
              rows={4}
            />
          </>
        )}

        <Button
          type="submit"
          disabled={envoi || !pret}
          data-testid="btp-terrain-enregistrer"
          style={{ minHeight: 48 }}
        >
          {envoi ? 'Enregistrement…' : 'Enregistrer'}
        </Button>
      </form>

      {message && (
        <p
          role="status"
          data-testid="btp-terrain-message"
          style={{ display: 'flex', alignItems: 'center', gap: 6,
            marginTop: 12 }}
        >
          <CloudOff size={14} strokeWidth={1.75} aria-hidden="true" />
          {message}
        </p>
      )}
      {erreur && (
        <p role="alert" data-testid="btp-terrain-erreur"
          style={{ marginTop: 12, color: '#b91c1c' }}>
          {erreur}
        </p>
      )}
    </div>
  )
}
