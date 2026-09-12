"""NTDATA37 — un abonnement peut viser un Dashboard (PDF) ou une SavedQuery (XLSX).

Couvre :
  * le critère d'acceptation : un abonnement HEBDO à un dashboard « Direction »
    envoie son PDF le lundi ;
  * la rétro-compatibilité TOTALE des 3 rapports figés (rendu .xlsx inchangé,
    `render_report_xlsx` garde son contrat à deux valeurs) ;
  * une requête sauvegardée part en .xlsx, sous le nom de la requête ;
  * un widget en ERREUR est rendu AVEC son message (jamais tu) ;
  * une cible d'une AUTRE société n'est jamais résolue ;
  * une cible supprimée n'explose pas : l'envoi est journalisé en échec ;
  * la validation refuse `dashboard`/`query` sans `cible_id`, au CHAMP fautif.

L'horloge est FIGÉE (lundi) : la cadence hebdomadaire dépend du jour réel.
Le rendu PDF est remplacé par un double (WeasyPrint est une dépendance lourde
qui n'a rien à faire dans un test de planification) ; le HTML qui l'alimente,
lui, est vérifié tel quel.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.reporting import scheduled_reports
from apps.reporting.models import EnvoiRapport, SavedReport
from authentication.models import Company
from core import data_explorer
from core.models import Dashboard, SavedQuery
from testkit.time import frozen

User = get_user_model()

#: Lundi 13 avril 2026, 06 h 00 — le créneau d'envoi hebdomadaire.
LUNDI_06H = '2026-04-13 06:00:00'


def _companies_dataset(company, user):
    return Company.objects.filter(pk=company.pk)


class AbonnementDashboardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTDATA37 SA',
                                             slug='ntdata37-sa')
        cls.autre = Company.objects.create(nom='NTDATA37 Autre',
                                           slug='ntdata37-autre')
        cls.user = User.objects.create_user(
            username='ntdata37_u', password='x', company=cls.company,
            role_legacy='admin')

    def setUp(self):
        data_explorer.register_dataset(
            'societes_ntdata37', 'Sociétés', ['id', 'nom'],
            _companies_dataset)

    def _dashboard(self, company=None, **kw):
        params = dict(
            company=company or self.company, titre='Direction',
            layout={'widgets': [{
                'id': 'societes', 'titre': 'Sociétés',
                'dataset': 'societes_ntdata37',
                'spec': {'select': ['nom']},
            }]})
        params.update(kw)
        return Dashboard.objects.create(**params)

    def _rapport(self, **kw):
        params = dict(company=self.company, owner=self.user,
                      name='Direction hebdo',
                      target_kind=SavedReport.TargetKind.DASHBOARD,
                      schedule=SavedReport.Schedule.WEEKLY,
                      recipients='direction@taqinor.ma')
        params.update(kw)
        return SavedReport.objects.create(**params)

    # ── Critère d'acceptation ──────────────────────────────────────────────
    def test_abonnement_hebdo_a_un_dashboard_envoie_son_pdf_le_lundi(self):
        dashboard = self._dashboard()
        rapport = self._rapport(cible_id=dashboard.pk)

        envois = []

        def _envoyer(report, content, title, filename=None,
                     content_type=None):
            envois.append((report.pk, title, filename, content_type,
                           content))
            return True

        with frozen(LUNDI_06H), \
                mock.patch.object(scheduled_reports, '_is_email_configured',
                                  return_value=True), \
                mock.patch.object(scheduled_reports, '_send_report_email',
                                  _envoyer), \
                mock.patch('core.pdf.render_pdf',
                           return_value=b'%PDF-1.4 faux'):
            envoyes = scheduled_reports.email_saved_reports()

        self.assertEqual(envoyes, 1)
        self.assertEqual(len(envois), 1)
        _pk, titre, nom, mime, contenu = envois[0]
        self.assertEqual(titre, 'Direction')
        self.assertEqual(nom, 'Direction.pdf')
        self.assertEqual(mime, scheduled_reports.MIME_PDF)
        self.assertEqual(contenu, b'%PDF-1.4 faux')

        rapport.refresh_from_db()
        self.assertIsNotNone(rapport.last_sent_at)
        self.assertEqual(
            EnvoiRapport.objects.filter(saved_report=rapport,
                                        statut='envoye').count(), 1)

    def test_pas_envoye_un_autre_jour(self):
        dashboard = self._dashboard()
        self._rapport(cible_id=dashboard.pk)
        with frozen('2026-04-14 06:00:00'), \
                mock.patch.object(scheduled_reports, '_is_email_configured',
                                  return_value=True):
            self.assertEqual(scheduled_reports.email_saved_reports(), 0)

    # ── Rendus ─────────────────────────────────────────────────────────────
    def test_html_du_dashboard_contient_les_lignes(self):
        dashboard = self._dashboard()
        rapport = self._rapport(cible_id=dashboard.pk)
        html = scheduled_reports.rendre_dashboard_html(rapport, dashboard)
        self.assertIn('Direction', html)
        self.assertIn('Sociétés', html)
        self.assertIn('NTDATA37 SA', html)

    def test_widget_en_erreur_est_rendu_avec_son_message(self):
        """Un tableau de bord qui tait un widget cassé ment par omission."""
        dashboard = self._dashboard(layout={'widgets': [{
            'id': 'casse', 'titre': 'Casse', 'dataset': 'inexistant',
            'spec': {},
        }]})
        rapport = self._rapport(cible_id=dashboard.pk)
        html = scheduled_reports.rendre_dashboard_html(rapport, dashboard)
        self.assertIn('erreur', html)
        self.assertIn('inexistant', html)

    def test_requete_sauvegardee_part_en_xlsx(self):
        requete = SavedQuery.objects.create(
            company=self.company, owner=self.user, titre='Mes societes',
            dataset='societes_ntdata37', spec={'select': ['nom']})
        rapport = self._rapport(
            name='Requête hebdo',
            target_kind=SavedReport.TargetKind.QUERY, cible_id=requete.pk)
        contenu, titre, nom, mime = scheduled_reports.rendre_rapport(rapport)
        self.assertIsNotNone(contenu)
        self.assertEqual(titre, 'Mes societes')
        self.assertEqual(nom, 'Messocietes.xlsx')
        self.assertEqual(mime, scheduled_reports.MIME_XLSX)

    def test_retro_compatibilite_des_trois_rapports_figes(self):
        rapport = self._rapport(
            name='Ventes', target_kind=SavedReport.TargetKind.SALES,
            cible_id=None)
        contenu, titre, nom, mime = scheduled_reports.rendre_rapport(rapport)
        self.assertIsNotNone(contenu)
        self.assertEqual(nom, 'sales.xlsx')
        self.assertEqual(mime, scheduled_reports.MIME_XLSX)
        # Le contrat HISTORIQUE à deux valeurs est conservé tel quel.
        contenu_legacy, titre_legacy = scheduled_reports.render_report_xlsx(
            rapport)
        self.assertIsNotNone(contenu_legacy)
        self.assertEqual(titre_legacy, titre)

    # ── Garde-fous ─────────────────────────────────────────────────────────
    def test_cible_d_une_autre_societe_jamais_resolue(self):
        etranger = self._dashboard(company=self.autre)
        rapport = self._rapport(cible_id=etranger.pk)
        self.assertIsNone(rapport.resoudre_cible())
        self.assertEqual(scheduled_reports.rendre_rapport(rapport),
                         (None, None, None, None))

    def test_cible_supprimee_journalisee_en_echec(self):
        dashboard = self._dashboard()
        rapport = self._rapport(cible_id=dashboard.pk)
        dashboard.delete()
        with frozen(LUNDI_06H), \
                mock.patch.object(scheduled_reports, '_is_email_configured',
                                  return_value=True):
            self.assertEqual(scheduled_reports.email_saved_reports(), 0)
        envoi = EnvoiRapport.objects.get(saved_report=rapport)
        self.assertEqual(envoi.statut, 'echec')
        self.assertIn('cible', envoi.erreur.lower())

    def test_dashboard_sans_cible_refuse_au_champ_fautif(self):
        rapport = SavedReport(
            company=self.company, name='Sans cible',
            target_kind=SavedReport.TargetKind.DASHBOARD)
        with self.assertRaises(ValidationError) as leve:
            rapport.clean()
        self.assertIn('cible_id', leve.exception.message_dict)

    def test_rapport_fige_sans_cible_reste_valide(self):
        rapport = SavedReport(company=self.company, name='Ventes',
                              target_kind=SavedReport.TargetKind.SALES)
        rapport.clean()  # ne lève pas
