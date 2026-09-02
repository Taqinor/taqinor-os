"""AUD221 — le cross-dock ventile la réception entre les vagues en attente.

Défaut d'origine : `affecter_reception_cross_dock` affectait TOUTE la quantité
reçue à ``proposition['vagues'][0]``, sans plafonner au reste à prélever de
cette vague ni regarder les suivantes. Une réception de 20 pour une vague qui
n'en attendait que 5 servait 5 unités utiles, gonflait le colis de 15 unités
que personne n'avait demandées, et laissait la vague suivante BLOQUÉE alors
que la marchandise était sur le quai.

Run :
    python manage.py test apps.stock.test_aud221_cross_dock_ventilation -v 2
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.stock.models import (
    AffectationCrossDock, BonCommandeFournisseur, EmplacementStock,
    Fournisseur, LigneBonCommandeFournisseur, LigneReceptionFournisseur,
    Produit, ReceptionFournisseur, UniteLogistique,
)
from apps.stock.services import (
    affecter_reception_cross_dock, creer_vague_depuis_besoins, lancer_vague,
)

User = get_user_model()

DATE_REF = datetime.date(2026, 4, 9)


def make_company(slug='aud221-co', nom='AUD221 Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class Aud221Base(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='aud221_admin', password='x', role_legacy='admin',
            company=self.company)
        self.emplacement = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt AUD221', is_principal=True)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur AUD221')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur AUD221', sku='AUD221-1',
            prix_achat=Decimal('7000'), prix_vente=Decimal('9000'),
            quantite_stock=0)
        self.bcf = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-AUD221-1',
            fournisseur=self.fournisseur, date_commande=DATE_REF,
            emplacement_destination=self.emplacement)

    def _reception(self, quantite):
        reception = ReceptionFournisseur.objects.create(
            company=self.company, reference=f'REC-AUD221-{quantite}',
            bon_commande=self.bcf, date_reception=DATE_REF)
        ligne_bcf = LigneBonCommandeFournisseur.objects.create(
            bon_commande=self.bcf, produit=self.produit, quantite=quantite,
            prix_achat_unitaire=self.produit.prix_achat)
        LigneReceptionFournisseur.objects.create(
            reception=reception, ligne_commande=ligne_bcf,
            produit=self.produit, quantite=quantite)
        return reception

    def _vague(self, quantite):
        vague = creer_vague_depuis_besoins(
            company=self.company, user=self.admin,
            besoins=[{'produit_id': self.produit.id, 'quantite': quantite}])
        lancer_vague(vague)
        return vague


class TestVentilationCrossDock(Aud221Base):
    def test_le_surplus_va_a_la_vague_suivante(self):
        vague_a = self._vague(5)
        vague_b = self._vague(5)
        reception = self._reception(20)

        resultat = affecter_reception_cross_dock(
            reception=reception, user=self.admin)

        # Un colis par vague servie. Avant AUD221 : un seul colis de 20
        # unités sur la vague A, la vague B restant bloquée.
        self.assertEqual(len(resultat['unites_logistiques']), 2)
        quantites = {}
        for unite_id in resultat['unites_logistiques']:
            unite = UniteLogistique.objects.get(id=unite_id)
            quantites[unite.vague_id] = sum(
                li.quantite for li in unite.lignes.all())
        self.assertEqual(quantites.get(vague_a.id), 5)
        self.assertEqual(quantites.get(vague_b.id), 5)

    def test_le_reliquat_non_attendu_repart_au_rangement(self):
        self._vague(5)
        self._vague(5)
        reception = self._reception(20)

        resultat = affecter_reception_cross_dock(
            reception=reception, user=self.admin)

        ligne_id = reception.lignes.first().id
        self.assertEqual(resultat['reliquats'],
                         [{'ligne_id': ligne_id, 'quantite': 10}])
        # La trace porte la quantité RÉELLEMENT cross-dockée, pas les 20 reçus.
        affectation = AffectationCrossDock.objects.get(
            company=self.company, ligne_reception_id=ligne_id)
        self.assertEqual(affectation.quantite, 10)

    def test_quantite_exactement_attendue_sans_reliquat(self):
        vague = self._vague(4)
        reception = self._reception(4)

        resultat = affecter_reception_cross_dock(
            reception=reception, user=self.admin)

        self.assertEqual(resultat['reliquats'], [])
        self.assertEqual(len(resultat['unites_logistiques']), 1)
        unite = UniteLogistique.objects.get(id=resultat['unite_logistique'])
        self.assertEqual(unite.vague_id, vague.id)
        self.assertEqual(unite.lignes.first().quantite, 4)

    def test_reception_plus_petite_que_le_besoin(self):
        self._vague(10)
        reception = self._reception(3)

        resultat = affecter_reception_cross_dock(
            reception=reception, user=self.admin)

        self.assertEqual(resultat['reliquats'], [])
        unite = UniteLogistique.objects.get(id=resultat['unite_logistique'])
        self.assertEqual(unite.lignes.first().quantite, 3)

    def test_colis_impose_recoit_tout_le_cross_dock(self):
        """Quand l'appelant impose une unité, elle reste l'unique colis."""
        from apps.stock.services import creer_unite_logistique

        vague_a = self._vague(5)
        self._vague(5)
        reception = self._reception(20)
        colis = creer_unite_logistique(
            company=self.company, type_unite='colis', vague=vague_a)

        resultat = affecter_reception_cross_dock(
            reception=reception, user=self.admin, unite=colis)

        self.assertEqual(resultat['unites_logistiques'], [colis.id])
        colis.refresh_from_db()
        # 5 + 5 attendus par les deux vagues, cumulés dans le colis imposé ;
        # les 10 unités que personne n'attendait restent un reliquat.
        self.assertEqual(sum(li.quantite for li in colis.lignes.all()), 10)
        self.assertEqual(resultat['reliquats'][0]['quantite'], 10)
