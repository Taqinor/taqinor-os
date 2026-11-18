"""FG26 — outillage RGPD : export d'accès du sujet + anonymisation client."""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.roles.permissions_registre import (
    ADMIN_PERMISSIONS,
    COMMERCIAL_PERMISSIONS,
)
from apps.crm.models import Client

User = get_user_model()


def _company(slug='fg26-co', nom='FG26 Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class FG26GdprTest(TestCase):
    def setUp(self):
        self.company = _company()
        self.admin_role = Role.objects.create(
            company=self.company, nom='Administrateur',
            permissions=list(ADMIN_PERMISSIONS), est_systeme=True)
        self.comm_role = Role.objects.create(
            company=self.company, nom='Commercial',
            permissions=list(COMMERCIAL_PERMISSIONS))
        self.admin = User.objects.create_user(
            username='fg26_admin', password='pw', role_legacy='admin',
            role=self.admin_role, company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Jean Soleil',
            email='jean@example.com', telephone='0612345678',
            adresse='1 rue X', cin='AB12345')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')

    def test_data_export_returns_subject_bundle(self):
        r = self.api.get(
            f'/api/django/crm/clients/{self.client_obj.id}/data-export/')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data['identite']['email'], 'jean@example.com')
        self.assertIn('documents', r.data)

    def test_anonymize_scrubs_pii(self):
        r = self.api.post(
            f'/api/django/crm/clients/{self.client_obj.id}/anonymize/')
        self.assertEqual(r.status_code, 200, r.content)
        self.client_obj.refresh_from_db()
        self.assertTrue(self.client_obj.is_anonymized)
        self.assertIsNone(self.client_obj.email)
        self.assertIsNone(self.client_obj.telephone)
        self.assertIsNone(self.client_obj.cin)
        self.assertNotEqual(self.client_obj.nom, 'Jean Soleil')
        self.assertIsNotNone(self.client_obj.anonymized_at)

    def test_anonymize_efface_aussi_les_leads_du_client(self):
        """ASUP12 (C-ASUP-008) — « Anonymiser » passe par le chemin commun
        d'effacement : ses 2 leads (dont 1 archivé), l'e-mail journalisé et le
        calepinage sont effacés ; le lead d'une autre société est intact."""
        from apps.calepinage.models import Calepinage
        from apps.crm.models import Lead
        from apps.ventes.models import EmailLog
        lead = Lead.objects.create(company=self.company, nom='Jean',
                                   client=self.client_obj, telephone='0612345678')
        archive = Lead.objects.create(
            company=self.company, nom='Jean (archivé)', client=self.client_obj,
            email='jean.archive@example.com', is_archived=True)
        mail = EmailLog.objects.create(
            company=self.company, client=self.client_obj, direction='sortant',
            statut='envoye', to_email='jean@example.com', corps='Bonjour Jean')
        calepinage = Calepinage.objects.create(
            company=self.company, client_id=self.client_obj.pk, titre='1 rue X')
        ailleurs = Lead.objects.create(company=_company('fg26-autre', 'Autre'),
                                       nom='Ailleurs', telephone='0612345678')
        r = self.api.post(
            f'/api/django/crm/clients/{self.client_obj.id}/anonymize/')
        self.assertEqual(r.status_code, 200, r.content)
        for fiche in (lead, archive):
            fiche.refresh_from_db()
            with self.subTest(lead=fiche.pk):
                self.assertEqual(fiche.nom, 'Anonymisé')
                self.assertIsNone(fiche.telephone)
                self.assertIsNone(fiche.email)
        mail.refresh_from_db()
        self.assertEqual((mail.to_email, mail.corps), ('', ''))
        calepinage.refresh_from_db()
        self.assertEqual(calepinage.titre, '')
        ailleurs.refresh_from_db()
        self.assertEqual(ailleurs.nom, 'Ailleurs')
        self.assertTrue(ailleurs.telephone)

    def test_anonymize_efface_aussi_les_leads_en_corbeille_du_client(self):
        """ASUP62 — un lead du client en corbeille, à e-mail/téléphone
        différents de ceux du client, est anonymisé et reste en corbeille."""
        from apps.crm.models import Lead
        lead = Lead.objects.create(
            company=self.company, nom='Corbeille', client=self.client_obj,
            email='autre.corbeille@example.com', telephone='0699887766')
        lead.soft_delete()
        r = self.api.post(
            f'/api/django/crm/clients/{self.client_obj.id}/anonymize/')
        self.assertEqual(r.status_code, 200, r.content)
        lead = Lead.all_objects.get(pk=lead.pk)
        self.assertEqual(lead.nom, 'Anonymisé')
        self.assertFalse(lead.email)
        self.assertFalse(lead.telephone)
        self.assertTrue(lead.is_deleted)

    def test_anonymize_idempotent_guard(self):
        self.api.post(
            f'/api/django/crm/clients/{self.client_obj.id}/anonymize/')
        r = self.api.post(
            f'/api/django/crm/clients/{self.client_obj.id}/anonymize/')
        # ERR-ENF11-FUZZ-CRM : refus d'état = 409 (plus 400).
        self.assertEqual(r.status_code, 409, r.content)

    def test_anonymize_requires_admin(self):
        comm = User.objects.create_user(
            username='fg26_comm', password='pw', role_legacy='responsable',
            role=self.comm_role, company=self.company)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(comm)}')
        r = api.post(
            f'/api/django/crm/clients/{self.client_obj.id}/anonymize/')
        self.assertEqual(r.status_code, 403)

    def test_anonymisation_refusee_tant_qu_une_creance_est_ouverte(self):
        """ASUP70 (D-ASUP-8) — « Anonymiser (RGPD) » (client avec ou sans
        e-mail/téléphone) et l'effacement d'une demande de droit sur l'e-mail
        de Jean rendent 409 tant que 1 080,00 MAD restent dus sur une facture
        émise de 1 200,00 MAD TTC ; rien n'est effacé ; le reste encaissé, les
        mêmes gestes rendent 200. Mutants : retirer le contrôle par client
        (le client sans identifiant passe) ou ne pas enregistrer la garde
        ``creance_ouverte`` (la demande est traitée) ⇒ échec."""
        from decimal import Decimal
        from django.core.management import call_command
        from django.utils import timezone
        from apps.crm.models import Lead
        from apps.stock.models import Produit
        from apps.ventes.domain.instantanes_facture import identite_acheteur_courante
        from apps.ventes.models import Facture, LigneFacture, Paiement
        from core.models import DataSubjectRequest
        sans_contact = Client.objects.create(
            company=self.company, nom='Sans Contact', cin='CD67890')
        lead = Lead.objects.create(company=self.company, nom='Jean',
                                   client=self.client_obj, email='jean@example.com')
        produit = Produit.objects.create(company=self.company, nom='Kit', sku='FG26-A70',
                                         prix_vente=Decimal('1000'))
        factures = {}
        for cl in (self.client_obj, sans_contact):
            fac = Facture.objects.create(company=self.company, reference=f'FAC-A70-{cl.pk}',
                                         client=cl, statut='emise', taux_tva=Decimal('20'))
            LigneFacture.objects.create(
                facture=fac, produit=produit, designation='Centrale', quantite=Decimal('1'),
                prix_unitaire=Decimal('1000'), taux_tva=Decimal('20'))
            Facture.objects.filter(pk=fac.pk).update(identite_acheteur=identite_acheteur_courante(fac))
            Paiement.objects.create(company=self.company, facture=fac, montant=Decimal('120'),
                                    date_paiement=timezone.now().date(), mode='virement')
            factures[cl.pk] = fac
        motif = ('Anonymisation refusée : ce client doit encore 1 080,00 MAD sur ses '
                 'factures émises. Encaissez le solde, ou soldez-le par un avoir ou un '
                 'abandon de créance, puis recommencez.')
        demande = DataSubjectRequest.objects.create(
            company=self.company, subject_identifier='jean@example.com',
            kind=DataSubjectRequest.KIND_ERASURE)
        call_command('init_roles', verbosity=0)
        directeur = User.objects.create_user(
            username='fg26_directeur', password='pw', company=self.company,
            role=Role.objects.get(company=self.company, nom='Directeur'))
        api_dir = APIClient()
        api_dir.force_authenticate(directeur)
        url_dsr = f'/api/django/core/dsr-requests/{demande.pk}/traiter/'
        for cl in (self.client_obj, sans_contact):
            with self.subTest(client=cl.nom):
                r = self.api.post(f'/api/django/crm/clients/{cl.id}/anonymize/')
                self.assertEqual((r.status_code, r.data.get('detail')), (409, motif))
        r = api_dir.post(url_dsr)
        self.assertEqual((r.status_code, r.data.get('detail')), (409, motif))
        for cl, nom, email, cin in ((self.client_obj, 'Jean Soleil', 'jean@example.com', 'AB12345'),
                                    (sans_contact, 'Sans Contact', None, 'CD67890')):
            cl.refresh_from_db()
            self.assertEqual((cl.nom, cl.email, cl.cin, cl.is_anonymized),
                             (nom, email, cin, False))
        lead.refresh_from_db()
        self.assertEqual((lead.nom, lead.email), ('Jean', 'jean@example.com'))
        demande.refresh_from_db()
        self.assertEqual(demande.statut, DataSubjectRequest.STATUT_RECUE)
        for fac in factures.values():
            Paiement.objects.create(company=self.company, facture=fac, montant=Decimal('1080'),
                                    date_paiement=timezone.now().date(), mode='virement')
        r = self.api.post(f'/api/django/crm/clients/{sans_contact.id}/anonymize/')
        self.assertEqual(r.status_code, 200, r.content)
        r = api_dir.post(url_dsr)
        self.assertEqual(r.status_code, 200, r.content)
        for cl in (self.client_obj, sans_contact):
            cl.refresh_from_db()
            self.assertTrue(cl.is_anonymized)
