"""XPOS9 — Capture des n° de série à la vente → garantie SAV automatique.

Couvre :
  * `sav.services.creer_equipement_depuis_vente_pos` crée un `Equipement`
    SAV garanti (sans chantier, `client_vente` posé), garantie calculée
    depuis `date_vente` + `Produit.garantie_mois` ;
  * un n° de série en doublon (déjà au parc de la société) est refusé
    (`SerieDejaEnregistreeError`) ;
  * l'intégration `pos.services.valider_vente` : `suivi_serie=False` (défaut)
    → rien ne change (aucun équipement créé) ; `suivi_serie=True` avec des
    n° de série saisis sur la ligne → équipement(s) créé(s), lié(s) au
    client de la vente ; produit non sérialisé (`numeros_serie` vide)
    inchangé.

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_xpos9 -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Client
from apps.sav.models import Equipement
from apps.sav.services import (
    SerieDejaEnregistreeError, creer_equipement_depuis_vente_pos,
)
from apps.stock.models import Categorie, Produit

User = get_user_model()


def make_company(slug='sav-xpos9', nom='Sav Co XPOS9'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class XPOS9ServiceTest(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='xpos9_admin', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Test',
            email='xpos9-client@example.invalid')
        categorie = Categorie.objects.create(
            company=self.company, nom='Onduleurs XPOS9')
        self.onduleur = Produit.objects.create(
            company=self.company, nom='Onduleur Sérialisé', sku='OND-XPOS9',
            prix_achat=3000, prix_vente=6000, quantite_stock=5,
            categorie=categorie, suivi_serie=True, garantie_mois=24)

    def test_cree_equipement_garanti_sans_chantier(self):
        from datetime import date
        equip = creer_equipement_depuis_vente_pos(
            company=self.company, produit=self.onduleur,
            client=self.client_obj, numero_serie='SN-XPOS9-1',
            date_vente=date(2026, 1, 10), created_by=self.admin)
        self.assertIsNone(equip.installation_id)
        self.assertEqual(equip.client_vente_id, self.client_obj.id)
        self.assertEqual(equip.numero_serie, 'SN-XPOS9-1')
        self.assertEqual(equip.date_fin_garantie, date(2028, 1, 10))

    def test_doublon_serie_refuse(self):
        from datetime import date
        Equipement.objects.create(
            company=self.company, produit=self.onduleur,
            numero_serie='SN-XPOS9-DUP', client_vente=self.client_obj,
            created_by=self.admin)
        with self.assertRaises(SerieDejaEnregistreeError):
            creer_equipement_depuis_vente_pos(
                company=self.company, produit=self.onduleur,
                client=self.client_obj, numero_serie='SN-XPOS9-DUP',
                date_vente=date(2026, 1, 10), created_by=self.admin)

    def test_serie_vide_leve_valueerror(self):
        from datetime import date
        with self.assertRaises(ValueError):
            creer_equipement_depuis_vente_pos(
                company=self.company, produit=self.onduleur,
                client=self.client_obj, numero_serie='',
                date_vente=date(2026, 1, 10), created_by=self.admin)


class XPOS9ValiderVenteIntegrationTest(TestCase):
    """Intégration côté pos.services.valider_vente — le flag suivi_serie
    gate la création automatique, sans jamais bloquer la vente elle-même."""

    def setUp(self):
        self.company = make_company('sav-xpos9-int', 'Sav Co XPOS9 Int')
        self.admin = User.objects.create_user(
            username='xpos9_int_admin', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Int',
            email='xpos9-int-client@example.invalid')
        categorie = Categorie.objects.create(
            company=self.company, nom='Onduleurs XPOS9 Int')
        self.onduleur = Produit.objects.create(
            company=self.company, nom='Onduleur Sérialisé Int',
            sku='OND-XPOS9-INT', prix_achat=3000, prix_vente=6000,
            quantite_stock=5, categorie=categorie, suivi_serie=True,
            garantie_mois=12)
        self.cable = Produit.objects.create(
            company=self.company, nom='Câble', sku='CABLE-XPOS9-INT',
            prix_achat=10, prix_vente=30, quantite_stock=50,
            categorie=categorie)

    def _vente_with_lines(self, lignes_data):
        from apps.pos.models import LigneVenteComptoir, VenteComptoir
        vente = VenteComptoir.objects.create(
            company=self.company, reference='VC-XPOS9-1',
            client=self.client_obj, created_by=self.admin)
        for data in lignes_data:
            LigneVenteComptoir.objects.create(
                vente=vente, produit=data['produit'],
                designation=data['produit'].nom, quantite=1,
                prix_unitaire_ttc=Decimal('1200'),
                numeros_serie=data.get('numeros_serie') or [])
        return vente

    def test_produit_serialise_avec_serie_cree_equipement(self):
        from apps.pos import services as pos_services
        vente = self._vente_with_lines([
            {'produit': self.onduleur, 'numeros_serie': ['SN-INT-1']},
        ])
        pos_services.valider_vente(
            vente=vente, paiements=[{'mode': 'carte', 'montant': '1200'}],
            user=self.admin)
        equip = Equipement.objects.get(
            company=self.company, numero_serie='SN-INT-1')
        self.assertEqual(equip.client_vente_id, self.client_obj.id)
        self.assertIsNone(equip.installation_id)
        self.assertIsNotNone(equip.date_fin_garantie)

    def test_produit_non_serialise_inchange(self):
        from apps.pos import services as pos_services
        vente = self._vente_with_lines([{'produit': self.cable}])
        pos_services.valider_vente(
            vente=vente, paiements=[{'mode': 'carte', 'montant': '1200'}],
            user=self.admin)
        self.assertFalse(
            Equipement.objects.filter(company=self.company).exists())

    def test_suivi_serie_off_ne_cree_rien_meme_avec_serie_saisie(self):
        """Si le produit n'a pas `suivi_serie` actif, une série saisie par
        erreur sur la ligne ne crée rien (comportement additif, gated)."""
        from apps.pos import services as pos_services
        self.onduleur.suivi_serie = False
        self.onduleur.save(update_fields=['suivi_serie'])
        vente = self._vente_with_lines([
            {'produit': self.onduleur, 'numeros_serie': ['SN-INT-OFF']},
        ])
        pos_services.valider_vente(
            vente=vente, paiements=[{'mode': 'carte', 'montant': '1200'}],
            user=self.admin)
        self.assertFalse(
            Equipement.objects.filter(company=self.company).exists())

    def test_doublon_serie_ne_bloque_pas_la_vente(self):
        from apps.pos import services as pos_services
        Equipement.objects.create(
            company=self.company, produit=self.onduleur,
            numero_serie='SN-INT-DUP', client_vente=self.client_obj,
            created_by=self.admin)
        vente = self._vente_with_lines([
            {'produit': self.onduleur, 'numeros_serie': ['SN-INT-DUP']},
        ])
        # Ne doit lever aucune exception : la vente se valide normalement.
        pos_services.valider_vente(
            vente=vente, paiements=[{'mode': 'carte', 'montant': '1200'}],
            user=self.admin)
        vente.refresh_from_db()
        from apps.pos.models import VenteComptoir
        self.assertEqual(vente.statut, VenteComptoir.Statut.VALIDEE)
        self.assertEqual(
            Equipement.objects.filter(
                company=self.company, numero_serie='SN-INT-DUP').count(), 1)
