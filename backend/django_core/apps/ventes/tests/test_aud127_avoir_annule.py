"""AUD127 — annuler un avoir contre-passe enfin son effet.

L'action `annuler` posait `statut='annulee'` et rendait la réponse : AUCUN
événement émis, alors que la CRÉATION envoie `avoir_cree` auquel compta
abonne l'écriture d'avoir (YLEDG1). Il n'existait aucun `avoir_annule` dans
`core/events.py`. L'effet ERP était immédiat : `Facture.avoirs_total`
(`facturation/models.py`) exclut les avoirs annulés, donc `montant_du`
remonte — pendant que le grand livre, lui, garde l'avoir. Une créance de
20 000 réapparaissait côté ERP alors que la comptabilité la considérait
toujours comme créditée. Et si l'avoir était de type contre-passation, la
facture d'origine avait été forcée à ANNULEE et rien ne la restaurait.

Trois cas ROUGES : l'événement + l'extourne, la restauration de la facture
contre-passée, et l'idempotence de la double annulation.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Avoir, Facture, FactureActivity, LigneFacture

User = get_user_model()


def make_company(slug='aud127-co', nom='AUD127 Co'):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


class _Listener:
    """Compte les émissions d'`avoir_annule` et retient les avoirs vus."""

    def __init__(self):
        self.calls = []

    def __call__(self, sender, instance, company, **kwargs):
        self.calls.append((instance.id, getattr(company, 'id', None)))


class TestAUD127AvoirAnnule(TestCase):
    def setUp(self):
        from apps.roles.models import ALL_PERMISSIONS, Role
        from core.events import avoir_annule

        self.company = make_company()
        admin_role = Role.objects.create(
            company=self.company, nom='Administrateur',
            permissions=ALL_PERMISSIONS, est_systeme=True)
        self.admin = User.objects.create_user(
            username='aud127_admin', password='x', role=admin_role,
            role_legacy='admin', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        self.cl = Client.objects.create(
            company=self.company, nom='Client', prenom='AUD127',
            telephone='+212600000127')
        self.panneau = Produit.objects.create(
            company=self.company, nom='Panneau PV', sku='PV-AUD127',
            prix_vente=Decimal('1000'), quantite_stock=100,
            tva=Decimal('20.00'))
        # 20 × 1 000 HT à 20 % = 20 000 HT + 4 000 TVA = 24 000 TTC.
        self.facture = Facture.objects.create(
            company=self.company, reference='FAC-AUD127-0001',
            client=self.cl, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'))
        LigneFacture.objects.create(
            facture=self.facture, produit=self.panneau,
            designation='Panneau PV', quantite=Decimal('20'),
            prix_unitaire=Decimal('1000'), taux_tva=Decimal('20.00'))

        self.listener = _Listener()
        avoir_annule.connect(self.listener, dispatch_uid='test_aud127')
        self.addCleanup(avoir_annule.disconnect, dispatch_uid='test_aud127')

    def _creer_avoir(self, body):
        r = self.api.post(
            f'/api/django/ventes/factures/{self.facture.id}/creer-avoir/',
            body, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        return Avoir.objects.get(id=r.data['id'])

    def _annuler(self, avoir):
        return self.api.post(
            f'/api/django/ventes/avoirs/{avoir.id}/annuler/')

    def test_annulation_emet_avoir_annule_exactement_une_fois(self):
        avoir = self._creer_avoir(
            {'motif': 'Retour partiel',
             'lignes': [{'produit': self.panneau.id,
                         'designation': 'Panneau PV', 'quantite': '10',
                         'prix_unitaire': '1000', 'taux_tva': '20'}]})
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.avoirs_total, Decimal('12000.00'))

        r = self._annuler(avoir)
        self.assertEqual(r.status_code, 200, r.data)
        avoir.refresh_from_db()
        self.assertEqual(avoir.statut, Avoir.Statut.ANNULEE)
        # L'événement documentaire existe et porte l'avoir + la société :
        # c'est lui qui déclenche l'extourne côté compta (YLEDG4).
        self.assertEqual(len(self.listener.calls), 1)
        self.assertEqual(self.listener.calls[0],
                         (avoir.id, self.company.id))
        # Et l'ERP rend bien la créance (avoirs_total exclut les annulés).
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.avoirs_total, Decimal('0'))
        self.assertEqual(self.facture.montant_du, Decimal('24000.00'))

    def test_extourne_comptable_branchee_sur_l_evenement(self):
        """Le receiver compta est abonné à `avoir_annule` : l'écriture
        d'avoir est EXTOURNÉE, jamais supprimée (COMPTA11)."""
        from apps.compta import receivers as compta_receivers
        from core.events import avoir_annule

        self.assertTrue(
            hasattr(compta_receivers, '_extourne_avoir_annule'),
            "compta n'abonne rien à avoir_annule")
        # `Signal.receivers` : chaque entrée commence par sa lookup_key, dont
        # le premier élément est le `dispatch_uid` quand il est fourni.
        uids = [entree[0][0] for entree in avoir_annule.receivers]
        self.assertIn('compta_extourne_avoir_annule', uids)

    def test_annulation_d_une_contre_passation_restaure_la_facture(self):
        avoir = self._creer_avoir(
            {'mode': 'contre_passation', 'motif': 'Erreur de facturation'})
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.statut, Facture.Statut.ANNULEE)

        r = self._annuler(avoir)
        self.assertEqual(r.status_code, 200, r.data)
        self.facture.refresh_from_db()
        # La facture reprend son statut ANTÉRIEUR, pas un statut deviné.
        self.assertEqual(self.facture.statut, Facture.Statut.EMISE)
        # La restauration est tracée dans le chatter.
        trace = FactureActivity.objects.filter(
            facture=self.facture, field='statut',
            new_value=Facture.Statut.EMISE).first()
        self.assertIsNotNone(trace)
        self.assertIn(avoir.reference, trace.body)

    def test_contre_passation_sans_statut_anterieur_refusee(self):
        """Si la trace ZFAC5 ne porte pas de statut antérieur exploitable,
        l'annulation est REFUSÉE plutôt que de laisser la facture morte."""
        avoir = self._creer_avoir(
            {'mode': 'contre_passation', 'motif': 'Erreur'})
        FactureActivity.objects.filter(
            facture=self.facture, field='statut',
            new_value=Facture.Statut.ANNULEE).update(old_value='')

        r = self._annuler(avoir)
        self.assertEqual(r.status_code, 400, r.data)
        avoir.refresh_from_db()
        self.assertEqual(avoir.statut, Avoir.Statut.EMISE)
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.statut, Facture.Statut.ANNULEE)
        self.assertEqual(len(self.listener.calls), 0)

    def test_double_annulation_est_un_no_op(self):
        avoir = self._creer_avoir(
            {'motif': 'Retour partiel',
             'lignes': [{'produit': self.panneau.id,
                         'designation': 'Panneau PV', 'quantite': '5',
                         'prix_unitaire': '1000', 'taux_tva': '20'}]})
        r1 = self._annuler(avoir)
        self.assertEqual(r1.status_code, 200, r1.data)
        r2 = self._annuler(avoir)
        self.assertEqual(r2.status_code, 200, r2.data)
        avoir.refresh_from_db()
        self.assertEqual(avoir.statut, Avoir.Statut.ANNULEE)
        # UNE seule émission : une seconde extourne doublerait le grand livre.
        self.assertEqual(len(self.listener.calls), 1)
