"""NTCRM20 — Registre des apporteurs d'affaires (Deal Registration)."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Apporteur, DealEnregistre, Lead, LeadActivity
from apps.roles.models import Role

User = get_user_model()


class DealEnregistreProtectionTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor NTCRM20', slug='taqinor-ntcrm20')
        self.apporteur1 = Apporteur.objects.create(
            company=self.company, nom='Apporteur A')
        self.apporteur2 = Apporteur.objects.create(
            company=self.company, nom='Apporteur B')

    def test_second_apporteur_refuse_pendant_la_fenetre(self):
        lead1 = Lead.objects.create(
            company=self.company, nom='Prospect', telephone='0612345678')
        DealEnregistre.objects.create(
            company=self.company, apporteur=self.apporteur1, lead=lead1)

        lead2 = Lead.objects.create(
            company=self.company, nom='Prospect (doublon)', telephone='0612345678')
        deal2 = DealEnregistre(
            company=self.company, apporteur=self.apporteur2, lead=lead2)
        with self.assertRaises(Exception):
            deal2.full_clean()

    def test_apporteur_different_client_ok(self):
        lead1 = Lead.objects.create(
            company=self.company, nom='Client 1', telephone='0611111111')
        DealEnregistre.objects.create(
            company=self.company, apporteur=self.apporteur1, lead=lead1)

        lead2 = Lead.objects.create(
            company=self.company, nom='Client 2', telephone='0622222222')
        deal2 = DealEnregistre(
            company=self.company, apporteur=self.apporteur2, lead=lead2)
        deal2.full_clean()  # ne lève pas

    def test_apres_rejet_le_deal_ne_protege_plus(self):
        lead1 = Lead.objects.create(
            company=self.company, nom='Prospect', telephone='0633333333')
        deal1 = DealEnregistre.objects.create(
            company=self.company, apporteur=self.apporteur1, lead=lead1)
        deal1.statut = DealEnregistre.Statut.REJETE
        deal1.save(update_fields=['statut'])

        lead2 = Lead.objects.create(
            company=self.company, nom='Prospect (repris)', telephone='0633333333')
        deal2 = DealEnregistre(
            company=self.company, apporteur=self.apporteur2, lead=lead2)
        deal2.full_clean()  # ne lève pas : la protection est levée


class ApporteurApiTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor NTCRM20b', slug='taqinor-ntcrm20b')
        self.role = Role.objects.create(
            company=self.company, nom='Responsable',
            permissions=['crm_creer', 'crm_modifier'])
        self.user = User.objects.create_user(
            username='resp_ntcrm20', password='x',
            company=self.company, role=self.role)
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def test_crud_apporteur(self):
        resp = self.api.post('/api/django/crm/apporteurs/', {
            'nom': 'Nouvel apporteur', 'type_apporteur': 'courtier',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_enregistrer_puis_refus_second_via_api(self):
        apporteur1 = Apporteur.objects.create(company=self.company, nom='A1')
        apporteur2 = Apporteur.objects.create(company=self.company, nom='A2')
        lead1 = Lead.objects.create(
            company=self.company, nom='Prospect API', telephone='0644444444')
        resp = self.api.post('/api/django/crm/deals-enregistres/', {
            'apporteur': apporteur1.pk, 'lead': lead1.pk,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

        lead2 = Lead.objects.create(
            company=self.company, nom='Prospect API bis', telephone='0644444444')
        resp2 = self.api.post('/api/django/crm/deals-enregistres/', {
            'apporteur': apporteur2.pk, 'lead': lead2.pk,
        }, format='json')
        self.assertEqual(resp2.status_code, 400, resp2.data)

    def test_approuver_rejeter(self):
        apporteur = Apporteur.objects.create(company=self.company, nom='A')
        lead = Lead.objects.create(company=self.company, nom='Prospect approuver')
        deal = DealEnregistre.objects.create(
            company=self.company, apporteur=apporteur, lead=lead)
        resp = self.api.post(f'/api/django/crm/deals-enregistres/{deal.pk}/approuver/')
        self.assertEqual(resp.status_code, 200, resp.data)
        deal.refresh_from_db()
        self.assertEqual(deal.statut, DealEnregistre.Statut.APPROUVE)


# ACRM57 (C-ACRM-019) — ``deals-enregistres/<id>/approuver|rejeter`` passent
# par ``clients_pilotage.approuver_deal`` / ``rejeter_deal`` : table de transitions,
# ``full_clean()`` rejoué à l'approbation, une ligne de chatter (acteur,
# ancien -> nouveau) ; hors table -> 400 nommant ``statut``, rien d'écrit.
#
# Rejoue la sonde V_VA LVIEW2-6 : rejeter un deal ``a_payer`` répondait 200 et
# le sortait de ``a-payer/`` (dette effacée). Source réelle : vues et
# ``DealEnregistre.clean()`` réels, aucun mock. Test-du-test : retirer la table
# (écrire le statut directement) ⇒ les cas hors table repassent à 200 et échouent.
BASE_DEALS = '/api/django/crm/deals-enregistres/'

#: (statut de départ, geste) -> statut attendu (None = 400, inchangé).
CAS = {
    ('en_attente', 'approuver'): 'approuve',
    ('en_attente', 'rejeter'): 'rejete',
    ('approuve', 'approuver'): None,
    ('approuve', 'rejeter'): None,
    ('rejete', 'approuver'): None,
    ('rejete', 'rejeter'): None,
    ('expire', 'approuver'): None,
    ('expire', 'rejeter'): None,
    ('a_payer', 'approuver'): None,
    ('a_payer', 'rejeter'): None,
}


class DealsTransitionsTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='ACRM57 Solaire', slug='acrm57-deals')
        self._activer_apporteurs_si_le_reglage_existe()
        self.admin = User.objects.create_user(
            username='acrm57-admin', password='x', role_legacy='admin',
            company=self.company)
        self.apporteur = Apporteur.objects.create(
            company=self.company, nom='Apporteur A',
            taux_commission_pct=Decimal('5.00'))
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        self._n = 0

    def _activer_apporteurs_si_le_reglage_existe(self):
        """ACRM66 (parcage des apporteurs) peut éteindre ces routes par
        défaut : ce module teste les transitions d'une société qui les a
        ALLUMÉES."""
        from apps.parametres.models import CompanyProfile
        champs = {f.name for f in CompanyProfile._meta.concrete_fields}
        if 'apporteurs_actif' in champs:
            CompanyProfile.objects.update_or_create(
                company=self.company, defaults={'apporteurs_actif': True})

    def _deal(self, statut, *, apporteur=None, telephone=None, **extra):
        self._n += 1
        lead = Lead.objects.create(
            company=self.company, nom=f'Prospect {self._n}',
            telephone=telephone or f'+2126610570{self._n:02d}')
        return DealEnregistre.objects.create(
            company=self.company, apporteur=apporteur or self.apporteur,
            lead=lead, statut=statut, **extra)

    def test_table_des_transitions(self):
        for (depart, geste), attendu in CAS.items():
            with self.subTest(depart=depart, geste=geste):
                deal = self._deal(depart)
                resp = self.api.post(f'{BASE_DEALS}{deal.pk}/{geste}/')
                deal.refresh_from_db()
                if attendu is None:
                    self.assertEqual(resp.status_code, 400, resp.content)
                    self.assertIn('statut', resp.data)
                    self.assertEqual(deal.statut, depart)
                else:
                    self.assertEqual(resp.status_code, 200, resp.content)
                    self.assertEqual(deal.statut, attendu)

    def test_rejeter_un_deal_a_payer_garde_la_dette(self):
        deal = self._deal('a_payer', montant_commission_du=Decimal('1000.00'))
        resp = self.api.post(f'{BASE_DEALS}{deal.pk}/rejeter/')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('statut', resp.data)
        deal.refresh_from_db()
        self.assertEqual(deal.statut, DealEnregistre.Statut.A_PAYER)
        self.assertEqual(deal.montant_commission_du, Decimal('1000.00'))
        a_payer = self.api.get(f'{BASE_DEALS}a-payer/')
        self.assertEqual(a_payer.status_code, 200)
        self.assertIn(deal.pk, [d['id'] for d in a_payer.data])

    def test_approuver_un_deal_rejete_reenregistre_ailleurs_400(self):
        """Le client d'un deal rejeté a depuis été enregistré par un AUTRE
        apporteur : réapprouver est refusé (aucune double protection)."""
        telephone = '+212661057999'
        rejete = self._deal('rejete', telephone=telephone)
        autre = Apporteur.objects.create(company=self.company, nom='Apporteur B')
        self._deal('approuve', apporteur=autre, telephone=telephone)
        resp = self.api.post(f'{BASE_DEALS}{rejete.pk}/approuver/')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('statut', resp.data)
        rejete.refresh_from_db()
        self.assertEqual(rejete.statut, DealEnregistre.Statut.REJETE)

    def test_approbation_rejoue_full_clean(self):
        """En attente, mais le même client est déjà protégé par un autre
        apporteur : ``clean()`` refuse, le statut reste en attente."""
        telephone = '+212661057888'
        autre = Apporteur.objects.create(company=self.company, nom='Apporteur C')
        self._deal('approuve', apporteur=autre, telephone=telephone)
        attente = self._deal('en_attente', telephone=telephone)
        resp = self.api.post(f'{BASE_DEALS}{attente.pk}/approuver/')
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn('statut', resp.data)
        attente.refresh_from_db()
        self.assertEqual(attente.statut, DealEnregistre.Statut.EN_ATTENTE)

    def test_une_transition_laisse_une_ligne_de_chatter(self):
        deal = self._deal('en_attente')
        self.api.post(f'{BASE_DEALS}{deal.pk}/approuver/')
        ligne = LeadActivity.objects.filter(lead=deal.lead).latest('id')
        self.assertEqual(ligne.user, self.admin)
        self.assertIn('En attente', ligne.body)
        self.assertIn('Approuvé', ligne.body)

    def test_un_refus_necrit_rien_au_chatter(self):
        deal = self._deal('a_payer')
        avant = LeadActivity.objects.filter(lead=deal.lead).count()
        self.api.post(f'{BASE_DEALS}{deal.pk}/rejeter/')
        self.assertEqual(
            LeadActivity.objects.filter(lead=deal.lead).count(), avant)
