/**
 * PACT116 — Inscription d'une nouvelle société (onboarding SaaS).
 *
 * POURQUOI CET ÉCRAN EXISTE. `POST /auth/register-company/`
 * (`authentication/views.py`) crée DÉJÀ tout en une requête publique : la
 * société, son `CompanyProfile`, les rôles système, le compte Directeur et les
 * hooks de démarrage. Mais il n'existait AUCUNE route ni aucun lien pour
 * l'atteindre : pas de `/register` dans le routeur, aucun appel depuis l'écran
 * de connexion, et le bouton « Démarrer gratuitement » de la page d'accueil
 * repointait vers `/login`. La fonctionnalité SaaS d'inscription existait et
 * était inatteignable — le trou (a) dans sa forme la plus nette.
 *
 * RÈGLE TENUE ICI : AUCUNE RÈGLE D'UNICITÉ N'EST DUPLIQUÉE CÔTÉ CLIENT.
 * Le serveur est le SEUL à savoir si un nom d'utilisateur est pris ou si un
 * slug de société entre en collision (il désambiguïse tout seul en suffixant).
 * Un contrôle client « ce nom est déjà pris » serait une DEUXIÈME source de
 * vérité, fatalement désynchronisée — exactement le défaut que gardent
 * `check_api_shapes.py` et `check_choices_declares.py`. Cet écran se contente
 * donc de POSTER, puis d'AFFICHER TELLES QUELLES les erreurs 400 par champ que
 * le serveur renvoie (`{"username": ["Ce nom d'utilisateur est deja
 * utilise."]}`), sans les reformuler ni les deviner.
 */
import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { AlertCircle, Eye, EyeOff } from 'lucide-react'

import api from '../api/axios'
import TaqinorMark from '../ui/TaqinorMark'

const CHAMPS = [
  { nom: 'company_nom', label: 'Nom de la société', type: 'text',
    placeholder: 'Ex. Taqinor Énergies', autoComplete: 'organization' },
  { nom: 'username', label: "Nom d'utilisateur du Directeur", type: 'text',
    placeholder: 'Ex. r.kasri', autoComplete: 'username' },
  { nom: 'email', label: 'Adresse e-mail (facultatif)', type: 'email',
    placeholder: 'vous@societe.ma', autoComplete: 'email' },
  { nom: 'password', label: 'Mot de passe', type: 'password',
    placeholder: '••••••••', autoComplete: 'new-password' },
]

const champVide = { company_nom: '', username: '', email: '', password: '' }

const styleChamp = {
  width: '100%', padding: '11px 13px', borderRadius: 8,
  border: '1px solid #d1d5db', fontSize: 14, fontFamily: 'inherit',
  boxSizing: 'border-box', background: '#fff', color: '#111827',
}

/** Messages du serveur pour UN champ, rendus tels quels (jamais un objet). */
function messagesDuServeur(valeur) {
  if (valeur == null) return []
  if (Array.isArray(valeur)) return valeur.map((m) => String(m))
  return [String(valeur)]
}

export default function RegisterCompany() {
  const navigate = useNavigate()
  const [valeurs, setValeurs] = useState(champVide)
  // Erreurs PAR CHAMP telles que le serveur les renvoie ; jamais fabriquées.
  const [erreursChamp, setErreursChamp] = useState({})
  const [erreurGlobale, setErreurGlobale] = useState(null)
  const [envoi, setEnvoi] = useState(false)
  const [motDePasseVisible, setMotDePasseVisible] = useState(false)

  const majChamp = (nom) => (evenement) => {
    setValeurs((precedent) => ({ ...precedent, [nom]: evenement.target.value }))
  }

  const soumettre = async (evenement) => {
    evenement.preventDefault()
    setErreursChamp({})
    setErreurGlobale(null)
    setEnvoi(true)
    try {
      await api.post('/auth/register-company/', {
        company_nom: valeurs.company_nom,
        username: valeurs.username,
        email: valeurs.email,
        password: valeurs.password,
      })
      // La société existe : on renvoie vers la connexion avec l'identifiant
      // pré-rempli côté écran de login (paramètre lisible, aucune donnée
      // sensible dans l'URL).
      navigate('/login?inscription=ok', { replace: true })
    } catch (err) {
      const donnees = err?.response?.data
      if (donnees && typeof donnees === 'object' && !Array.isArray(donnees)) {
        const parChamp = {}
        let global = null
        Object.entries(donnees).forEach(([champ, valeur]) => {
          const messages = messagesDuServeur(valeur)
          if (!messages.length) return
          if (champ === 'detail' || champ === 'non_field_errors') {
            global = messages.join(' ')
          } else {
            parChamp[champ] = messages
          }
        })
        setErreursChamp(parChamp)
        if (global) setErreurGlobale(global)
        else if (!Object.keys(parChamp).length) {
          setErreurGlobale("La création de la société a échoué. Réessayez.")
        }
      } else {
        setErreurGlobale(
          'Impossible de contacter le serveur. Vérifiez votre connexion.')
      }
    } finally {
      setEnvoi(false)
    }
  }

  return (
    <div
      style={{
        minHeight: '100vh', display: 'flex', alignItems: 'center',
        justifyContent: 'center', padding: 24, background: '#f3f4f6',
      }}
    >
      <div
        style={{
          width: '100%', maxWidth: 460, background: '#fff', borderRadius: 16,
          padding: 32, boxShadow: '0 10px 40px rgba(15, 23, 42, 0.12)',
        }}
      >
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <TaqinorMark size={32} />
          <h1 style={{ fontSize: 21, fontWeight: 700, margin: '18px 0 6px', color: '#111827' }}>
            Créer votre société
          </h1>
          <p style={{ fontSize: 13, color: '#6b7280', margin: 0 }}>
            Vous serez le Directeur de cette société : accès complet, et vous
            invitez ensuite votre équipe.
          </p>
        </div>

        {erreurGlobale && (
          <div
            role="alert"
            style={{
              display: 'flex', gap: 8, alignItems: 'flex-start', marginBottom: 18,
              padding: '10px 12px', borderRadius: 8, background: '#fef2f2',
              border: '1px solid #fecaca', color: '#991b1b', fontSize: 13,
            }}
          >
            <AlertCircle size={16} style={{ flexShrink: 0, marginTop: 1 }} />
            <span>{erreurGlobale}</span>
          </div>
        )}

        <form
          onSubmit={soumettre}
          noValidate
          style={{ display: 'flex', flexDirection: 'column', gap: 16 }}
        >
          {CHAMPS.map(({ nom, label, type, placeholder, autoComplete }) => {
            const messages = erreursChamp[nom] || []
            const estMotDePasse = nom === 'password'
            return (
              <div key={nom}>
                <label
                  htmlFor={`inscription-${nom}`}
                  style={{
                    display: 'block', fontSize: 13, fontWeight: 600,
                    color: '#374151', marginBottom: 6,
                  }}
                >
                  {label}
                </label>
                <div style={{ position: 'relative' }}>
                  <input
                    id={`inscription-${nom}`}
                    name={nom}
                    type={estMotDePasse && motDePasseVisible ? 'text' : type}
                    value={valeurs[nom]}
                    onChange={majChamp(nom)}
                    placeholder={placeholder}
                    autoComplete={autoComplete}
                    aria-invalid={messages.length > 0 || undefined}
                    style={{
                      ...styleChamp,
                      paddingRight: estMotDePasse ? 46 : 13,
                      borderColor: messages.length ? '#dc2626' : '#d1d5db',
                    }}
                  />
                  {estMotDePasse && (
                    <button
                      type="button"
                      onClick={() => setMotDePasseVisible((v) => !v)}
                      aria-label={motDePasseVisible
                        ? 'Masquer le mot de passe'
                        : 'Afficher le mot de passe'}
                      style={{
                        position: 'absolute', right: 10, top: '50%',
                        transform: 'translateY(-50%)', background: 'none',
                        border: 'none', cursor: 'pointer', color: '#6b7280',
                        display: 'flex', padding: 4,
                      }}
                    >
                      {motDePasseVisible ? <EyeOff size={17} /> : <Eye size={17} />}
                    </button>
                  )}
                </div>
                {messages.map((message) => (
                  <p
                    key={message}
                    style={{ margin: '6px 0 0', fontSize: 12.5, color: '#b91c1c' }}
                  >
                    {message}
                  </p>
                ))}
              </div>
            )
          })}

          <button
            type="submit"
            disabled={envoi}
            style={{
              marginTop: 4, padding: '12px 16px', borderRadius: 9, border: 'none',
              background: '#1863DC', color: '#fff', fontSize: 15, fontWeight: 600,
              cursor: envoi ? 'not-allowed' : 'pointer', fontFamily: 'inherit',
              opacity: envoi ? 0.75 : 1,
            }}
          >
            {envoi ? 'Création en cours…' : 'Créer la société →'}
          </button>
        </form>

        <p style={{ textAlign: 'center', marginTop: 24, fontSize: 13, color: '#6b7280' }}>
          Vous avez déjà un compte ?{' '}
          <Link to="/login" style={{ color: '#1863DC', textDecoration: 'none', fontWeight: 600 }}>
            Se connecter
          </Link>
        </p>
      </div>
    </div>
  )
}
