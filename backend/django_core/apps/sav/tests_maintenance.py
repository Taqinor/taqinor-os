"""T16 — contrats de maintenance : prochaine visite / dû calculés à la lecture,
génération idempotente de tickets SAV préventifs (sans planificateur)."""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.sav.models import ContratMaintenance, Ticket
from authentication.models import Company

User = get_user_model()


class TestMaintenance(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='cm-co', defaults={'nom': 'CM Co'})[0]
        self.user = User.objects.create_user(
            username='cm_u', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(company=self.company, nom='C')

    def test_prochaine_visite_and_due(self):
        c = ContratMaintenance.objects.create(
            company=self.company, client=self.client_obj, periodicite='annuel',
            date_debut=date.today() - timedelta(days=400))
        self.assertTrue(c.is_due())  # début il y a >1 an
        future = ContratMaintenance.objects.create(
            company=self.company, client=self.client_obj, periodicite='annuel',
            date_debut=date.today())
        self.assertFalse(future.is_due())

    def test_generer_dus_creates_ticket_once(self):
        ContratMaintenance.objects.create(
            company=self.company, client=self.client_obj, periodicite='mensuel',
            date_debut=date.today() - timedelta(days=40))
        r1 = self.api.post('/api/django/sav/contrats-maintenance/generer-dus/')
        self.assertEqual(r1.status_code, 200, r1.data)
        self.assertEqual(r1.data['tickets_generes'], 1)
        self.assertEqual(Ticket.objects.filter(
            company=self.company, type='preventif').count(), 1)
        # Re-générer juste après n'en recrée pas (visite avancée).
        r2 = self.api.post('/api/django/sav/contrats-maintenance/generer-dus/')
        self.assertEqual(r2.data['tickets_generes'], 0)

    def test_filtre_client_illisible_repond_400(self):
        for brut in ('abc', '0', 'null'):
            resp = self.api.get(
                f'/api/django/sav/contrats-maintenance/?client={brut}')
            self.assertEqual(resp.status_code, 400, (brut, resp.content))
            self.assertIn('client', resp.data)

    def test_rapport_pdf_date_illisible_repond_400(self):
        contrat = ContratMaintenance.objects.create(
            company=self.company, client=self.client_obj, periodicite='annuel',
            date_debut=date.today())
        resp = self.api.get(
            f'/api/django/sav/contrats-maintenance/{contrat.pk}/rapport-pdf/'
            '?date=hier')
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn('date', resp.data)

    def test_due_filter(self):
        ContratMaintenance.objects.create(
            company=self.company, client=self.client_obj, periodicite='annuel',
            date_debut=date.today() - timedelta(days=400))
        ContratMaintenance.objects.create(
            company=self.company, client=self.client_obj, periodicite='annuel',
            date_debut=date.today())
        resp = self.api.get('/api/django/sav/contrats-maintenance/?due=1')
        rows = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        self.assertEqual(len(rows), 1)

    def test_cannot_bind_foreign_client(self):
        # ERR9 — un contrat ne peut pas lier le client d'une AUTRE société.
        other = Company.objects.get_or_create(
            slug='cm-other', defaults={'nom': 'Other'})[0]
        foreign_client = Client.objects.create(company=other, nom='Étranger')
        r = self.api.post('/api/django/sav/contrats-maintenance/', {
            'client': foreign_client.id, 'periodicite': 'annuel',
            'date_debut': date.today().isoformat()}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('client', r.data)
        self.assertFalse(ContratMaintenance.objects.filter(
            client=foreign_client).exists())

    def test_multipart_refuse_415_json_seul(self):
        # api-fuzz #956 : aucun upload ici, le formulaire multipart (où
        # « None » arrive en texte) est refusé ; JSON seul.
        r = self.api.post('/api/django/sav/contrats-maintenance/', {
            'client': self.client_obj.id, 'periodicite': 'annuel',
            'date_debut': date.today().isoformat()}, format='multipart')
        self.assertEqual(r.status_code, 415)

    def test_cannot_bind_foreign_installation(self):
        # ERR9 — ni le chantier d'une autre société.
        from apps.installations.models import Installation
        other = Company.objects.get_or_create(
            slug='cm-other2', defaults={'nom': 'Other2'})[0]
        other_client = Client.objects.create(company=other, nom='B')
        foreign_inst = Installation.objects.create(
            company=other, reference='CHT-X', client=other_client)
        r = self.api.post('/api/django/sav/contrats-maintenance/', {
            'client': self.client_obj.id, 'installation': foreign_inst.id,
            'periodicite': 'annuel', 'date_debut': date.today().isoformat()},
            format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('installation', r.data)

    def _contrat_post(self, **corps):
        return self.api.post('/api/django/sav/contrats-maintenance/', {
            'client': self.client_obj.id, 'periodicite': 'mensuel',
            'date_debut': '2000-01-01', **corps}, format='json')

    def test_duree_mois_hors_borne_400_et_rien_cree(self):
        # CI #997 api-fuzz (3e passe) : duree_mois à 2147483646 faisait déborder
        # l'échéance (an > 9999) -> 500 APRÈS écriture, la ligne restait et
        # cassait ensuite la liste. Le schéma publie maximum 600.
        for brut in (601, 2147483646, -1):
            r = self._contrat_post(duree_mois=brut)
            self.assertEqual(r.status_code, 400, (brut, r.content))
            self.assertIn('duree_mois', r.data)
        self.assertFalse(ContratMaintenance.objects.filter(
            company=self.company).exists())
        r = self._contrat_post(duree_mois=600)
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.data['date_expiration'], '2050-01-01')

    def test_dates_en_fin_de_calendrier_ne_font_pas_de_500(self):
        # Même avec une durée bornée, une date_debut proche de l'an 9999
        # déborde : les échéances sont recadrées sur date.max, jamais un 500.
        r = self._contrat_post(
            date_debut='9999-12-31', duree_mois=600, periodicite='annuel',
            facturation_active=True)
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.data['date_expiration'], '9999-12-31')
        self.assertEqual(r.data['prochaine_visite'], '9999-12-31')
        liste = self.api.get('/api/django/sav/contrats-maintenance/')
        self.assertEqual(liste.status_code, 200, liste.content)
        contrat = ContratMaintenance.objects.get(pk=r.data['id'])
        self.assertEqual(contrat.prochaine_facturation(), date.max)
        from apps.sav.dateutils import add_months
        self.assertEqual(add_months(date(9999, 6, 15), 2147483646), date.max)

    def test_entiers_du_contrat_bornes_400(self):
        for cle, brut in (('pieces_couvertes_pct', 101),
                          ('sla_response_days', 3651),
                          ('sla_resolution_days', 2147483646),
                          ('visites_incluses_an', 1001),
                          ('deplacements_inclus_an', 1001),
                          ('delai_intervention_heures', 8761)):
            r = self._contrat_post(**{cle: brut})
            self.assertEqual(r.status_code, 400, (cle, r.content))
            self.assertIn(cle, r.data)

    def test_filtres_due_et_a_renouveler_enumeres_400(self):
        # CI #997 : due et a_renouveler sont publiés enum ['1', 'true'] ;
        # toute autre valeur (vide comprise) -> 400 nommant le paramètre.
        for nom in ('due', 'a_renouveler'):
            for brut in ('', '0', 'AAA'):
                resp = self.api.get(
                    f'/api/django/sav/contrats-maintenance/?{nom}={brut}')
                self.assertEqual(resp.status_code, 400, (nom, brut))
                self.assertIn(nom, resp.data)
            ok = self.api.get(
                f'/api/django/sav/contrats-maintenance/?{nom}=true')
            self.assertEqual(ok.status_code, 200, ok.content)
