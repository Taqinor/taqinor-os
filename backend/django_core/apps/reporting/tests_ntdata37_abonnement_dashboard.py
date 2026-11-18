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

    def test_proprietaire_desactive_rien_ne_part(self):
        """ADRG156 — propriétaire désactivé : aucun envoi (journal ``echec``
        motivé, ``last_sent_at`` nul) et lien public 404 ; réactivé ⇒ envoi."""
        from apps.reporting.diffusion_views import make_report_token
        rapport = self._rapport(cible_id=self._dashboard().pk)
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])
        envoyer = mock.Mock(return_value=True)
        with frozen(LUNDI_06H), \
                mock.patch.object(scheduled_reports, '_is_email_configured',
                                  return_value=True), \
                mock.patch.object(scheduled_reports, '_send_report_email',
                                  envoyer), \
                mock.patch('core.pdf.render_pdf', return_value=b'%PDF faux'):
            self.assertEqual(scheduled_reports.email_saved_reports(), 0)
            envoyer.assert_not_called()
            envois = EnvoiRapport.objects.filter(saved_report=rapport)
            self.assertEqual(list(envois.values_list('statut', 'erreur')), [(
                'echec', 'Propriétaire du rapport désactivé : envoi suspendu.')])
            rapport.refresh_from_db()
            self.assertIsNone(rapport.last_sent_at)
            resp = self.client.get('/api/django/reporting/rapports-partages/'
                                   f'{make_report_token(rapport)}/')
            self.assertEqual(resp.status_code, 404)
            self.assertEqual(resp.json()['detail'], 'Rapport indisponible.')
            self.user.is_active = True
            self.user.save(update_fields=['is_active'])
            EnvoiRapport.objects.filter(saved_report=rapport).delete()
            self.assertEqual(scheduled_reports.email_saved_reports(), 1)

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

    def test_patch_sans_cible_en_modification_409(self):
        """ERR-ENF11-FUZZ-REPORTING — PATCH : la cible requise se lit sur la
        fiche enregistrée -> 409 (plus 400) ; création sans cible : 400 au
        champ."""
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken

        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        rapport = self._rapport(
            name='Ventes', target_kind=SavedReport.TargetKind.SALES)
        url = f'/api/django/reporting/saved-reports/{rapport.pk}/'
        resp = api.patch(url, {'target_kind': 'dashboard'}, format='json')
        self.assertEqual(resp.status_code, 409, resp.content)
        resp = api.post('/api/django/reporting/saved-reports/', {
            'name': 'X', 'target_kind': 'dashboard'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn('cible_id', resp.data)

    def _api_role(self, nom_role, suffixe=''):
        """Compte au rôle LIVRÉ ``nom_role`` (``init_roles``) + son client API."""
        from django.core.management import call_command
        from rest_framework.test import APIClient

        from apps.roles.models import Role
        call_command('init_roles', verbosity=0)
        role = Role.objects.get(company=self.company, nom=nom_role)
        user = User.objects.create_user(
            username=f'ntdata37_{nom_role.replace(" ", "_").lower()}{suffixe}',
            password='x', company=self.company, role=role)
        api = APIClient()
        api.force_authenticate(user)
        return user, api

    def test_requete_stock_exige_stock_export(self):
        """ADRG123 — programmer l'envoi d'une requête du jeu ``stock_produits``
        exige ``stock_export`` ; le rendu d'un rapport existant aussi (au nom
        de son propriétaire)."""
        url = '/api/django/reporting/saved-reports/'
        resultats = {}
        for nom_role in ('Commercial responsable', 'Directeur'):
            user, api = self._api_role(nom_role)
            requete = SavedQuery.objects.create(
                company=self.company, owner=user, titre='Stock',
                dataset='stock_produits', spec={'select': ['nom']})
            avant = SavedReport.objects.count()
            resp = api.post(url, {
                'name': 'Stock', 'target_kind': 'query', 'cible_id': requete.pk,
                'schedule': 'weekly', 'recipients': 'x@exemple.ma'},
                format='json')
            resultats[nom_role] = (resp, avant, SavedReport.objects.count(), user, requete)
        resp, avant, apres, commercial, requete_c = resultats['Commercial responsable']
        self.assertEqual(resp.status_code, 403, resp.content)
        self.assertEqual(str(resp.data['detail']),
                         'Accès au jeu de données refusé.')
        self.assertEqual(apres, avant)  # compté juste après SON post (le Directeur crée le sien ensuite)
        resp = resultats['Directeur'][0]
        self.assertEqual(resp.status_code, 201, resp.content)

        rapport = self._rapport(
            owner=commercial, name='Stock hebdo',
            target_kind=SavedReport.TargetKind.QUERY, cible_id=requete_c.pk)
        self.assertEqual(scheduled_reports._rendre_saved_query(rapport),
                         (None, None, None, None))

    def test_dashboard_avec_widget_stock_exige_stock_export(self):
        """ADRG146 — programmer un tableau de bord = exporter chaque jeu lu par
        ses widgets : ``stock_export`` pour un widget ``stock_produits`` (403
        sinon, aucun rapport) ; au rendu, au nom du propriétaire, un widget
        refusé n'est pas exécuté et devient un bloc d'erreur."""
        from apps.stock.models import Produit
        Produit.objects.create(company=self.company, nom='Onduleur ADRG146',
                               sku='ADRG146-P', prix_vente=100,
                               quantite_stock=3)
        widget_stock = {'id': 'stock', 'titre': 'Stock', 'dataset': 'stock_produits',
                        'spec': {'select': ['nom']}}
        dashboard = self._dashboard(partage=True, layout={'widgets': [widget_stock]})
        url = '/api/django/reporting/saved-reports/'
        resultats = {}
        for nom_role in ('Commercial responsable', 'Directeur'):
            user, api = self._api_role(nom_role)
            avant = SavedReport.objects.count()
            resp = api.post(url, {
                'name': 'Stock', 'target_kind': 'dashboard', 'cible_id': dashboard.pk,
                'schedule': 'weekly', 'recipients': 'x@exemple.ma'}, format='json')
            resultats[nom_role] = (resp, avant, SavedReport.objects.count(), user, api)
        resp, avant, apres, commercial, api_c = resultats['Commercial responsable']
        self.assertEqual(resp.status_code, 403, resp.content)
        self.assertEqual(str(resp.data['detail']), 'Accès au jeu de données refusé.')
        self.assertEqual(apres, avant)
        self.assertEqual(resultats['Directeur'][0].status_code, 201,
                         resultats['Directeur'][0].content)
        liste = api_c.get(url).json()
        self.assertEqual(len(liste.get('results', liste)), 1)  # le seul envoi du Directeur
        self.assertFalse(SavedReport.objects.filter(owner=commercial).exists())

        # Rendu : widget stock ajouté APRÈS la création du rapport (ORM).
        tableau = self._dashboard(partage=True)
        rapport = self._rapport(owner=commercial, cible_id=tableau.pk)
        tableau.layout = {'widgets': tableau.layout['widgets'] + [widget_stock]}
        tableau.save()
        html = scheduled_reports.rendre_dashboard_html(rapport, tableau)
        self.assertNotIn('Onduleur ADRG146', html)
        self.assertIn('<h2>Stock</h2><p class="erreur">Accès au jeu de données '
                      'refusé.</p>', html)
        self.assertIn('NTDATA37 SA', html)  # l'autre widget reste rendu

    def test_widget_metrique_stock_exige_stock_export(self):
        """ADRG157 — un widget de MÉTRIQUE nommée lit le jeu de sa définition :
        programmer ou rendre le tableau exige son code d'export (403 sinon)."""
        from apps.semantic.models import MetricDefinition
        from apps.stock.models import Produit
        MetricDefinition.objects.create(
            company=self.company, cle='stock_qte', libelle='Stock',
            dataset='stock_produits',
            mesure={'field': 'quantite_stock', 'agg': 'sum'})
        Produit.objects.create(company=self.company, nom='Onduleur ADRG157',
                               sku='ADRG157-P', prix_vente=100,
                               quantite_stock=3)
        dashboard = self._dashboard(partage=True, layout={'widgets': [{
            'id': 'm', 'titre': 'Stock', 'type': 'metrique',
            'metrique': 'stock_qte', 'group_by': ['nom']}]})
        url = '/api/django/reporting/saved-reports/'
        corps = {'name': 'Stock', 'target_kind': 'dashboard',
                 'cible_id': dashboard.pk, 'schedule': 'weekly',
                 'recipients': 'x@exemple.ma'}
        commercial, api_c = self._api_role('Commercial responsable')
        resp = api_c.post(url, corps, format='json')
        self.assertEqual(resp.status_code, 403, resp.content)
        self.assertEqual(str(resp.data['detail']),
                         'Accès au jeu de données refusé.')
        self.assertFalse(SavedReport.objects.filter(owner=commercial).exists())
        _directeur, api_d = self._api_role('Directeur')
        resp = api_d.post(url, corps, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        rapport = self._rapport(owner=commercial, cible_id=dashboard.pk)
        html = scheduled_reports.rendre_dashboard_html(rapport, dashboard)
        self.assertNotIn('Onduleur ADRG157', html)
        self.assertIn('<h2>Stock</h2><p class="erreur">Accès au jeu de '
                      'données refusé.</p>', html)

    def test_rapport_fige_stock_exige_stock_export(self):
        """ADRG158 / D-ADRG-15 — le rapport figé « stock » exige ``stock_export``
        sur toutes ses sorties : programmer, modifier, envoi planifié, lien
        public, export à l'écran ; le JSON reste ouvert."""
        from apps.reporting.diffusion_views import make_report_token
        from apps.stock.models import Produit
        Produit.objects.create(company=self.company, nom='Onduleur ADRG158',
                               sku='ADRG158-P', prix_vente=100,
                               quantite_stock=3)
        commercial, api_c = self._api_role('Commercial responsable')
        _directeur, api_d = self._api_role('Directeur')
        rapport = self._rapport(owner=commercial, name='Stock hebdo',
                                target_kind=SavedReport.TargetKind.STOCK)
        url = '/api/django/reporting/saved-reports/'
        corps = {'name': 'S', 'target_kind': 'stock', 'schedule': 'weekly',
                 'recipients': 'x@exemple.ma'}
        for resp in (api_c.post(url, corps, format='json'),
                     api_c.patch(f'{url}{rapport.pk}/',
                                 {'recipients': 'x@libre.ma'}, format='json')):
            self.assertEqual(resp.status_code, 403, resp.content)
            self.assertEqual(str(resp.data['detail']),
                             'Accès au jeu de données refusé.')
        self.assertEqual(list(SavedReport.objects.filter(owner=commercial)
                              .values_list('pk', 'recipients')),
                         [(rapport.pk, 'direction@taqinor.ma')])
        self.assertEqual(api_d.post(url, corps, format='json').status_code, 201)

        envoyer = mock.Mock(return_value=True)
        with frozen(LUNDI_06H), \
                mock.patch.object(scheduled_reports, '_is_email_configured',
                                  return_value=True), \
                mock.patch.object(scheduled_reports, '_send_report_email',
                                  envoyer):
            # Seul l'envoi du Directeur part ; celui du Commercial responsable, non.
            self.assertEqual(scheduled_reports.email_saved_reports(), 1)
        self.assertNotIn(rapport.pk, [c.args[0].pk for c in envoyer.call_args_list])
        self.assertEqual(
            list(EnvoiRapport.objects.filter(saved_report=rapport)
                 .values_list('statut', 'erreur')),
            [('echec', "Le propriétaire n'a pas le droit d'export du stock : "
                       'envoi suspendu.')])
        lien = self.client.get('/api/django/reporting/rapports-partages/'
                               f'{make_report_token(rapport)}/')
        self.assertEqual(lien.status_code, 404)

        stock = '/api/django/reporting/reports/stock/'
        resp = api_c.get(stock, {'export': 'xlsx'})
        self.assertEqual(resp.status_code, 403, resp.content)
        self.assertEqual(resp.data['code'], 'droit_manquant')
        self.assertIn('stock_export', str(resp.data['detail']))
        self.assertEqual(api_c.get(stock).status_code, 200)
        self.assertEqual(api_d.get(stock, {'export': 'xlsx'}).status_code, 200)

    def test_patch_destinataires_d_une_requete_stock_exige_stock_export(self):
        """ADRG147 — l'export du jeu est exigé à CHAQUE écriture d'un rapport
        ``query``, PATCH partiel compris : réorienter l'envoi stock d'un
        Directeur vers une adresse libre est refusé sans ``stock_export``."""
        directeur, api_d = self._api_role('Directeur')
        _commercial, api_c = self._api_role('Commercial responsable')
        requete = SavedQuery.objects.create(
            company=self.company, owner=directeur, titre='Stock', partage=True,
            dataset='stock_produits', spec={'select': ['nom']})
        rapport = self._rapport(
            owner=directeur, name='Stock hebdo', target_kind=SavedReport.TargetKind.QUERY,
            cible_id=requete.pk, recipients='direction@exemple.ma')
        url = f'/api/django/reporting/saved-reports/{rapport.pk}/'
        resp = api_c.patch(url, {'recipients': 'x@libre.ma'}, format='json')
        self.assertEqual(resp.status_code, 403, resp.content)
        self.assertEqual(str(resp.data['detail']), 'Accès au jeu de données refusé.')
        self.assertEqual(api_d.get(url).json()['recipients'], 'direction@exemple.ma')
        resp = api_d.patch(url, {'recipients': 'x@libre.ma'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(api_d.get(url).json()['recipients'], 'x@libre.ma')

    def test_cible_personnelle_d_un_collegue_refusee(self):
        """ADRG124 — le tableau PERSONNEL d'un collègue n'est pas une cible :
        404 au champ, aucun rapport ; ses propres tableaux et les partagés, si."""
        url = '/api/django/reporting/saved-reports/'
        user_a, api_a = self._api_role('Commercial responsable', '_a')
        _user_b, api_b = self._api_role('Commercial responsable', '_b')
        perso_a = self._dashboard(owner=user_a, partage=False)
        partage_a = self._dashboard(owner=user_a, partage=True, titre='Équipe')

        def poster(api, dashboard):
            return api.post(url, {'name': 'x', 'target_kind': 'dashboard',
                                  'cible_id': dashboard.pk}, format='json')

        avant = SavedReport.objects.count()
        resp = poster(api_b, perso_a)
        self.assertEqual(resp.status_code, 404, resp.content)
        self.assertIn('cible_id', resp.data)
        self.assertEqual(SavedReport.objects.count(), avant)
        self.assertEqual(poster(api_b, partage_a).status_code, 201)
        self.assertEqual(poster(api_a, perso_a).status_code, 201)
