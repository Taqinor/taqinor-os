"""AGR620 — SKU pompage « prix à renseigner » : installation, entretien,
antivol, clôture. Tous à prix 0, jamais auto-chiffrés ; ``ENT-PMP`` récurrent
(XCTR1 crée le contrat à l'acceptation).
"""
import re
from decimal import Decimal
from io import StringIO

from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.stock.management.commands import seed_catalogue as seed_mod
from apps.stock.models import Produit
from apps.stock.selectors import produits_pompage
from authentication.models import Company
from core.events import devis_accepted
from core.product_roles import ROLES_POMPAGE, est_panneau

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')
SKUS = ('INST-PMP', 'ENT-PMP', 'ANTIVOL-PV', 'CLOTURE-PV')


def _seed(company):
    call_command('seed_catalogue', company_slug=company.slug,
                 stdout=StringIO())


class SkuPompageTests(TestCase):
    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='agr620-co', defaults={'nom': 'AGR620 Co'})[0]

    def _p(self, sku):
        return Produit.objects.get(company=self.co, sku=sku)

    def test_seed_deux_fois_quatre_sku_sans_doublon_ni_prix_touche(self):
        _seed(self.co)
        _seed(self.co)
        for sku in SKUS:
            self.assertEqual(
                Produit.objects.filter(company=self.co, sku=sku).count(), 1)
        # un prix saisi par le fondateur survit à un re-seed
        Produit.objects.filter(company=self.co, sku='ANTIVOL-PV').update(
            prix_vente=Decimal('123'))
        _seed(self.co)
        self.assertEqual(self._p('ANTIVOL-PV').prix_vente, Decimal('123'))

    def test_prix_zero_roles_et_baremes_vides(self):
        _seed(self.co)
        roles = {
            'INST-PMP': 'installation_pompage',
            'ENT-PMP': 'entretien_pompage',
            'ANTIVOL-PV': 'antivol', 'CLOTURE-PV': 'cloture'}
        for sku, role in roles.items():
            p = self._p(sku)
            self.assertEqual(p.prix_vente, 0, sku)
            self.assertEqual(p.role_pompage, role)
            self.assertIn(role, ROLES_POMPAGE)
        inst = self._p('INST-PMP')
        self.assertIsNone(inst.prix_fixe_ht)
        self.assertIsNone(inst.prix_par_panneau_ht)
        ent = self._p('ENT-PMP')
        self.assertTrue(ent.est_recurrent)
        self.assertFalse(ent.periodicite_defaut)
        self.assertFalse(self._p('INST-PMP').est_recurrent)

    def test_descriptions_neutres_sans_chiffre_et_noms_jamais_panneau(self):
        _seed(self.co)
        for sku in SKUS:
            p = self._p(sku)
            self.assertFalse(re.search(r'\d', p.description or ''), sku)
            self.assertFalse(est_panneau(p.nom), sku)
            self.assertNotIn('panneau', p.nom.lower())

    def test_aucun_auto_remplissage_d_un_sku_a_prix_zero(self):
        _seed(self.co)
        servis = {e['sku'] for e in produits_pompage(
            self.co, avec_prix=True)}
        for sku in SKUS:
            self.assertNotIn(sku, servis)
        self.assertEqual(
            {r[1] for r in seed_mod.SKU_POMPAGE_PRIX_A_RENSEIGNER},
            set(SKUS))

    def test_devis_accepte_avec_entretien_price_cree_un_contrat(self):
        _seed(self.co)
        Produit.objects.filter(company=self.co, sku='ENT-PMP').update(
            prix_vente=Decimal('1000'))
        ent = self._p('ENT-PMP')
        user = User.objects.create_user(
            username='agr620_admin', password='x', role_legacy='admin',
            company=self.co)
        Client = django_apps.get_model('crm', 'Client')
        Devis = django_apps.get_model('ventes', 'Devis')
        LigneDevis = django_apps.get_model('ventes', 'LigneDevis')
        Contrat = django_apps.get_model('sav', 'ContratMaintenance')
        client = Client.objects.create(
            company=self.co, nom='Client', prenom='AGR620',
            email='agr620-client@example.invalid')
        devis = Devis.objects.create(
            company=self.co, reference=f'DEV-{MONTH}-0620', client=client,
            statut='accepte', taux_tva=Decimal('20'))
        LigneDevis.objects.create(
            devis=devis, produit=ent, designation=ent.nom, quantite=1,
            prix_unitaire=Decimal('1000'), taux_tva=Decimal('20'))
        devis_accepted.send(
            sender=None, devis=devis, user=user, ancien_statut='envoye')
        self.assertEqual(Contrat.objects.filter(client=client).count(), 1)
