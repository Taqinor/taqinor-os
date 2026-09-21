import { useMemo, useState } from 'react'
import { Bus, MapPin, Plus, AlertTriangle } from 'lucide-react'

import { Badge, Button, toast } from '../../ui'
import educationApi from '../../api/educationApi'
import flotteApi from '../../api/flotteApi'
import useEducationResource from './useEducationResource'

/* ============================================================================
   PACT80 — TRANSPORT SCOLAIRE (NTEDU23). Trou (a) : le backend existait en
   entier — circuits, arrêts ordonnés, affectations élève→circuit — et le
   client éducation n'avait AUCUNE entrée pour ce sujet.

   TROIS RÈGLES DU CONTRAT, TENUES ICI :
   1. Le véhicule d'un circuit est une FK RÉELLE vers `flotte.Vehicule`. L'écran
      lit le parc par le client de la FLOTTE (`flotteApi.vehicules.list`) —
      jamais une copie locale du parc, jamais une saisie libre d'immatriculation.
      Côté serveur, la disponibilité passe par `apps/flotte/selectors.py` : la
      frontière inter-apps est respectée des deux côtés.
   2. Les arrêts sont ORDONNÉS (champ `ordre`) et affichés dans cet ordre.
   3. L'indisponibilité du véhicule est un AVERTISSEMENT DOUX, JAMAIS BLOQUANT.
      Le serveur renvoie un champ `avertissement` dans la réponse de création ;
      l'affectation EST enregistrée. L'écran affiche l'avertissement et
      rafraîchit la liste — il ne l'utilise jamais comme une erreur. Un
      établissement affecte souvent les élèves avant d'immobiliser un bus.
   ========================================================================== */

const carte = {
  background: 'var(--card, #fff)',
  border: '1px solid var(--border, #e5e7eb)',
  borderRadius: 12,
  padding: 16,
  marginBottom: 18,
}

const champ = {
  padding: '8px 10px',
  borderRadius: 8,
  border: '1px solid var(--border, #d1d5db)',
  fontSize: 14,
  fontFamily: 'inherit',
  minWidth: 150,
}

const ligneForm = {
  display: 'flex', flexWrap: 'wrap', gap: 10, alignItems: 'flex-end',
}

const CIRCUIT_VIDE = { nom: '', vehicule: '' }
const ARRET_VIDE = { circuit: '', nom: '', ordre: '1', heure_passage_estimee: '' }
const AFFECTATION_VIDE = { eleve: '', circuit: '', arret: '', date_debut: '', date_fin: '' }

export default function TransportScolaire() {
  const { data: circuits, loading: chargementCircuits, error: erreurCircuits, reload: rechargerCircuits } =
    useEducationResource(educationApi.circuitsTransport.list)
  const { data: arrets, error: erreurArrets, reload: rechargerArrets } =
    useEducationResource(educationApi.arretsTransport.list)
  const { data: affectations, error: erreurAffectations, reload: rechargerAffectations } =
    useEducationResource(educationApi.affectationsTransport.list)
  const { data: eleves, error: erreurEleves } = useEducationResource(educationApi.eleves.list)
  const { data: vehicules, error: erreurVehicules } = useEducationResource(flotteApi.vehicules.list)

  const [formCircuit, setFormCircuit] = useState(CIRCUIT_VIDE)
  const [formArret, setFormArret] = useState(ARRET_VIDE)
  const [formAffectation, setFormAffectation] = useState(AFFECTATION_VIDE)
  const [enregistrement, setEnregistrement] = useState(false)
  // SOFT WARNING du serveur : jamais une erreur, jamais un blocage.
  const [avertissement, setAvertissement] = useState(null)

  const arretsParCircuit = useMemo(() => {
    const parCircuit = new Map()
    arrets.forEach((arret) => {
      const liste = parCircuit.get(arret.circuit) || []
      liste.push(arret)
      parCircuit.set(arret.circuit, liste)
    })
    // Les arrêts se lisent le long du parcours : l'ordre est le contrat.
    parCircuit.forEach((liste) => liste.sort((a, b) => (a.ordre || 0) - (b.ordre || 0)))
    return parCircuit
  }, [arrets])

  const libelleVehicule = (id) => {
    const vehicule = vehicules.find((v) => v.id === Number(id))
    if (!vehicule) return null
    return vehicule.immatriculation || vehicule.nom || `Véhicule #${id}`
  }

  const libelleEleve = (id) => {
    const eleve = eleves.find((e) => e.id === Number(id))
    return eleve ? `${eleve.nom} ${eleve.prenom}` : `Élève #${id}`
  }

  const libelleCircuit = (id) => {
    const circuit = circuits.find((c) => c.id === Number(id))
    return circuit ? circuit.nom : `Circuit #${id}`
  }

  const creerCircuit = async (evenement) => {
    evenement.preventDefault()
    if (!formCircuit.nom.trim()) return
    setEnregistrement(true)
    try {
      await educationApi.circuitsTransport.create({
        nom: formCircuit.nom.trim(),
        vehicule: formCircuit.vehicule ? Number(formCircuit.vehicule) : null,
      })
      toast.success('Circuit créé.')
      setFormCircuit(CIRCUIT_VIDE)
      rechargerCircuits()
    } catch {
      toast.error('Impossible de créer le circuit.')
    } finally {
      setEnregistrement(false)
    }
  }

  const ajouterArret = async (evenement) => {
    evenement.preventDefault()
    if (!formArret.circuit || !formArret.nom.trim()) return
    setEnregistrement(true)
    try {
      await educationApi.arretsTransport.create({
        circuit: Number(formArret.circuit),
        nom: formArret.nom.trim(),
        ordre: Number(formArret.ordre) || 1,
        heure_passage_estimee: formArret.heure_passage_estimee || null,
      })
      toast.success('Arrêt ajouté.')
      setFormArret({ ...ARRET_VIDE, circuit: formArret.circuit })
      rechargerArrets()
    } catch {
      toast.error("Impossible d'ajouter l'arrêt.")
    } finally {
      setEnregistrement(false)
    }
  }

  const affecterEleve = async (evenement) => {
    evenement.preventDefault()
    if (!formAffectation.eleve || !formAffectation.circuit || !formAffectation.date_debut) return
    setEnregistrement(true)
    setAvertissement(null)
    try {
      const reponse = await educationApi.affectationsTransport.create({
        eleve: Number(formAffectation.eleve),
        circuit: Number(formAffectation.circuit),
        arret: formAffectation.arret ? Number(formAffectation.arret) : null,
        date_debut: formAffectation.date_debut,
        date_fin: formAffectation.date_fin || null,
      })
      // L'affectation EST enregistrée : le champ `avertissement` du serveur ne
      // remet jamais cela en cause, il informe.
      toast.success('Élève affecté au circuit.')
      const message = reponse?.data?.avertissement
      if (message) setAvertissement(String(message))
      setFormAffectation(AFFECTATION_VIDE)
      rechargerAffectations()
    } catch {
      toast.error("Impossible d'enregistrer l'affectation.")
    } finally {
      setEnregistrement(false)
    }
  }

  const arretsDuCircuitChoisi = arretsParCircuit.get(Number(formAffectation.circuit)) || []

  // Cinq ressources indépendantes (`useEducationResource`) : un GET en échec
  // (403/500/réseau) ne doit jamais se déguiser en « aucune donnée » — c'est
  // exactement le défaut que ce bandeau referme. Un seul message par texte
  // distinct (les 5 hooks peuvent partager le même message générique).
  const erreursChargement = [...new Set(
    [erreurCircuits, erreurArrets, erreurAffectations, erreurEleves, erreurVehicules].filter(Boolean),
  )]

  return (
    <div style={{ padding: '4px 0 32px' }}>
      {/* ── Échec de chargement : jamais silencieux ── */}
      {erreursChargement.length > 0 && (
        <div
          role="alert"
          style={{
            display: 'flex', flexDirection: 'column', gap: 4, marginBottom: 16,
            padding: '10px 12px', borderRadius: 8, background: '#fef2f2',
            border: '1px solid #fecaca', color: '#991b1b', fontSize: 13,
          }}
        >
          {erreursChargement.map((message) => <span key={message}>{message}</span>)}
        </div>
      )}

      {/* ── Avertissement doux, jamais bloquant ── */}
      {avertissement && (
        <div
          role="status"
          style={{
            display: 'flex', gap: 8, alignItems: 'flex-start', marginBottom: 16,
            padding: '10px 12px', borderRadius: 8, background: '#fffbeb',
            border: '1px solid #fcd34d', color: '#78350f', fontSize: 13,
          }}
        >
          <AlertTriangle size={16} aria-hidden="true" style={{ flexShrink: 0, marginTop: 1 }} />
          <span>
            {avertissement} — l’affectation a bien été enregistrée.
          </span>
        </div>
      )}

      {/* ── Circuits ── */}
      <section style={carte}>
        <h2 style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 16, margin: '0 0 12px' }}>
          <Bus size={18} aria-hidden="true" /> Circuits de ramassage
        </h2>
        <form onSubmit={creerCircuit} style={ligneForm}>
          <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12.5 }}>
            Nom du circuit
            <input
              style={champ}
              value={formCircuit.nom}
              onChange={(e) => setFormCircuit((f) => ({ ...f, nom: e.target.value }))}
              placeholder="Ex. Circuit Nord"
            />
          </label>
          <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12.5 }}>
            Véhicule (parc flotte)
            <select
              style={champ}
              value={formCircuit.vehicule}
              onChange={(e) => setFormCircuit((f) => ({ ...f, vehicule: e.target.value }))}
            >
              <option value="">— Aucun pour l’instant —</option>
              {vehicules.map((vehicule) => (
                <option key={vehicule.id} value={vehicule.id}>
                  {vehicule.immatriculation || vehicule.nom || `Véhicule #${vehicule.id}`}
                </option>
              ))}
            </select>
          </label>
          <Button type="submit" disabled={enregistrement}>
            <Plus size={15} aria-hidden="true" /> Créer le circuit
          </Button>
        </form>

        {chargementCircuits ? (
          <p style={{ fontSize: 13, color: 'var(--muted-foreground, #6b7280)' }}>Chargement…</p>
        ) : circuits.length === 0 ? (
          <p style={{ fontSize: 13, color: 'var(--muted-foreground, #6b7280)' }}>
            Aucun circuit pour l’instant.
          </p>
        ) : (
          <ul style={{ listStyle: 'none', padding: 0, margin: '16px 0 0' }}>
            {circuits.map((circuit) => {
              const etapes = arretsParCircuit.get(circuit.id) || []
              const vehicule = libelleVehicule(circuit.vehicule)
              return (
                <li key={circuit.id} style={{ padding: '10px 0', borderTop: '1px solid var(--border, #e5e7eb)' }}>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                    <strong style={{ fontSize: 14 }}>{circuit.nom}</strong>
                    {vehicule
                      ? <Badge>{vehicule}</Badge>
                      : <Badge tone="outline">Aucun véhicule affecté</Badge>}
                    {!circuit.actif && <Badge tone="outline">Inactif</Badge>}
                  </div>
                  <ol style={{ margin: '8px 0 0', paddingLeft: 20, fontSize: 13 }}>
                    {etapes.map((arret) => (
                      <li key={arret.id}>
                        {arret.nom}
                        {arret.heure_passage_estimee ? ` — ${arret.heure_passage_estimee}` : ''}
                      </li>
                    ))}
                  </ol>
                  {etapes.length === 0 && (
                    <p style={{ margin: '6px 0 0', fontSize: 12.5, color: 'var(--muted-foreground, #6b7280)' }}>
                      Aucun arrêt sur ce circuit.
                    </p>
                  )}
                </li>
              )
            })}
          </ul>
        )}
      </section>

      {/* ── Arrêts ── */}
      <section style={carte}>
        <h2 style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 16, margin: '0 0 12px' }}>
          <MapPin size={18} aria-hidden="true" /> Ajouter un arrêt
        </h2>
        <form onSubmit={ajouterArret} style={ligneForm}>
          <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12.5 }}>
            Circuit de l’arrêt
            <select
              style={champ}
              value={formArret.circuit}
              onChange={(e) => setFormArret((f) => ({ ...f, circuit: e.target.value }))}
            >
              <option value="">— Choisir —</option>
              {circuits.map((circuit) => (
                <option key={circuit.id} value={circuit.id}>{circuit.nom}</option>
              ))}
            </select>
          </label>
          <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12.5 }}>
            Nom de l’arrêt
            <input
              style={champ}
              value={formArret.nom}
              onChange={(e) => setFormArret((f) => ({ ...f, nom: e.target.value }))}
              placeholder="Ex. Place Al Massira"
            />
          </label>
          <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12.5 }}>
            Ordre sur le circuit
            <input
              style={{ ...champ, minWidth: 90 }}
              type="number"
              min="1"
              step="1"
              value={formArret.ordre}
              onChange={(e) => setFormArret((f) => ({ ...f, ordre: e.target.value }))}
            />
          </label>
          <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12.5 }}>
            Heure de passage estimée
            <input
              style={{ ...champ, minWidth: 120 }}
              type="time"
              value={formArret.heure_passage_estimee}
              onChange={(e) => setFormArret((f) => ({ ...f, heure_passage_estimee: e.target.value }))}
            />
          </label>
          <Button type="submit" disabled={enregistrement}>
            <Plus size={15} aria-hidden="true" /> Ajouter l’arrêt
          </Button>
        </form>
      </section>

      {/* ── Affectations ── */}
      <section style={carte}>
        <h2 style={{ fontSize: 16, margin: '0 0 12px' }}>Affecter un élève</h2>
        <form onSubmit={affecterEleve} style={ligneForm}>
          <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12.5 }}>
            Élève
            <select
              style={champ}
              value={formAffectation.eleve}
              onChange={(e) => setFormAffectation((f) => ({ ...f, eleve: e.target.value }))}
            >
              <option value="">— Choisir —</option>
              {eleves.map((eleve) => (
                <option key={eleve.id} value={eleve.id}>{eleve.nom} {eleve.prenom}</option>
              ))}
            </select>
          </label>
          <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12.5 }}>
            Circuit de l’élève
            <select
              style={champ}
              value={formAffectation.circuit}
              onChange={(e) => setFormAffectation((f) => ({ ...f, circuit: e.target.value, arret: '' }))}
            >
              <option value="">— Choisir —</option>
              {circuits.map((circuit) => (
                <option key={circuit.id} value={circuit.id}>{circuit.nom}</option>
              ))}
            </select>
          </label>
          <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12.5 }}>
            Arrêt (facultatif)
            <select
              style={champ}
              value={formAffectation.arret}
              onChange={(e) => setFormAffectation((f) => ({ ...f, arret: e.target.value }))}
            >
              <option value="">— Aucun —</option>
              {arretsDuCircuitChoisi.map((arret) => (
                <option key={arret.id} value={arret.id}>{arret.nom}</option>
              ))}
            </select>
          </label>
          <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12.5 }}>
            Début
            <input
              style={{ ...champ, minWidth: 130 }}
              type="date"
              value={formAffectation.date_debut}
              onChange={(e) => setFormAffectation((f) => ({ ...f, date_debut: e.target.value }))}
            />
          </label>
          <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12.5 }}>
            Fin (facultatif)
            <input
              style={{ ...champ, minWidth: 130 }}
              type="date"
              value={formAffectation.date_fin}
              onChange={(e) => setFormAffectation((f) => ({ ...f, date_fin: e.target.value }))}
            />
          </label>
          <Button type="submit" disabled={enregistrement}>
            <Plus size={15} aria-hidden="true" /> Affecter
          </Button>
        </form>

        {affectations.length > 0 && (
          <ul style={{ listStyle: 'none', padding: 0, margin: '16px 0 0', fontSize: 13 }}>
            {affectations.map((affectation) => (
              <li key={affectation.id} style={{ padding: '7px 0', borderTop: '1px solid var(--border, #e5e7eb)' }}>
                {libelleEleve(affectation.eleve)} — {libelleCircuit(affectation.circuit)}
                {affectation.date_fin
                  ? ` (du ${affectation.date_debut} au ${affectation.date_fin})`
                  : ` (depuis le ${affectation.date_debut})`}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
