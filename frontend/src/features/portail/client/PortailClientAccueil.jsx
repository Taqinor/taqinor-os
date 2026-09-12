import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useSelector } from 'react-redux'
import { FileText, HardHat, Receipt } from 'lucide-react'
import portailApi from '../../../api/portailApi'
import { Card, EmptyState, Spinner } from '../../../ui'
import { formatDate } from '../../../lib/format'

/* ============================================================================
   NTPRT8/NTPRT9 — Accueil du portail client.
   ----------------------------------------------------------------------------
   Point d'entrée du shell : les 4 cartes chiffrées (devis en attente, factures
   impayées + échéance la plus proche, tickets SAV ouverts, prochain jalon
   chantier) viennent de `portailApi.tableauDeBord()`
   (`GET /portail/client/tableau-de-bord/`), servi par
   `apps.portail.views_client.tableau_de_bord_client` — lui-même une lecture
   pure des selectors `ventes`/`sav`/`installations` scopés au client connecté.
   Aucun chiffre n'est fabriqué côté écran : une carte à zéro reflète un compte
   réellement vide, jamais un défaut inventé.
   ========================================================================== */

const SECTIONS = [
  {
    to: '/portail/client/devis',
    icone: FileText,
    titre: 'Mes devis',
    texte: 'Consulter vos propositions et les accepter en ligne.',
  },
  {
    to: '/portail/client/factures',
    icone: Receipt,
    titre: 'Mes commandes & factures',
    texte: 'Suivre vos factures et leur règlement.',
  },
  {
    to: '/portail/client/chantiers',
    icone: HardHat,
    titre: 'Mes chantiers',
    texte: 'Suivre l’avancement et les photos de votre installation.',
  },
]

function CarteResume({ titre, valeur, detail }) {
  return (
    <Card className="flex flex-col gap-1 p-4">
      <span className="text-sm text-muted-foreground">{titre}</span>
      <span className="font-display text-2xl font-semibold">{valeur}</span>
      {detail && (
        <span className="text-sm text-muted-foreground">{detail}</span>
      )}
    </Card>
  )
}

export default function PortailClientAccueil() {
  const user = useSelector((s) => s.auth.user)
  const [resume, setResume] = useState(null)
  const [loading, setLoading] = useState(true)
  const [erreur, setErreur] = useState(false)

  useEffect(() => {
    let annule = false
    portailApi.tableauDeBord()
      .then((r) => { if (!annule) setResume(r.data) })
      .catch(() => { if (!annule) setErreur(true) })
      .finally(() => { if (!annule) setLoading(false) })
    return () => { annule = true }
  }, [])

  const cartes = resume ? [
    { cle: 'devis_en_attente', titre: 'Devis en attente',
      valeur: resume.devis_en_attente },
    { cle: 'factures_impayees', titre: 'Factures impayées',
      valeur: resume.factures_impayees,
      detail: resume.prochaine_echeance
        ? `Échéance la plus proche : ${formatDate(resume.prochaine_echeance)}`
        : null },
    { cle: 'tickets_ouverts', titre: 'Tickets SAV ouverts',
      valeur: resume.tickets_ouverts },
    { cle: 'prochain_jalon', titre: 'Prochain jalon chantier',
      valeur: resume.prochain_jalon
        ? resume.prochain_jalon.libelle
        : 'Aucun jalon à venir',
      detail: resume.prochain_jalon
        ? resume.prochain_jalon.chantier_reference
        : null },
  ] : []

  return (
    <>
      <h1 className="font-display text-xl font-semibold tracking-tight">
        Bonjour{user?.first_name ? ` ${user.first_name}` : ''}
      </h1>
      <p className="text-sm text-muted-foreground">
        Bienvenue dans votre espace client.
      </p>

      {loading && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Spinner /> Chargement de votre tableau de bord…
        </div>
      )}

      {!loading && erreur && (
        <EmptyState
          title="Tableau de bord indisponible"
          description="Vos données n’ont pas pu être chargées. Réessayez plus tard."
        />
      )}

      {!loading && !erreur && resume && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {cartes.map((c) => (
            <CarteResume key={c.cle} titre={c.titre} valeur={c.valeur}
                         detail={c.detail} />
          ))}
        </div>
      )}

      <div className="grid gap-3 sm:grid-cols-2">
        {SECTIONS.map((section) => {
          const { to, icone: Icone, titre, texte } = section
          return (
          <Card key={to} className="p-4">
            <Link to={to} className="flex items-start gap-3">
              <Icone className="mt-0.5 size-5 text-muted-foreground"
                     aria-hidden="true" />
              <span>
                <span className="block font-medium">{titre}</span>
                <span className="block text-sm text-muted-foreground">
                  {texte}
                </span>
              </span>
            </Link>
          </Card>
          )
        })}
      </div>
    </>
  )
}
