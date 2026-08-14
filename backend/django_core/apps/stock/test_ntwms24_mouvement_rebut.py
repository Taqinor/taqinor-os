"""NTWMS24 — casse / freinte / mise au rebut AVEC MOTIF.

Critère d'acceptation testé : la valeur totale de perte par motif et par
période est consultable, et reste DISTINCTE des ajustements d'inventaire
normaux.

Run :
    python manage.py test apps.stock.test_ntwms24_mouvement_rebut -v 2
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import (
    EmplacementStock, MouvementRebut, MouvementStock, Produit,
)
from apps.stock.services import (
    declarer_mouvement_rebut, rapport_pertes_entrepot,
)

User = get_user_model()

DEBUT = datetime.date(2026, 5, 1)
FIN = datetime.date(2026, 5, 31)


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def _dater(rebut, jour):
    """`created_at` est `auto_now_add` : on repositionne l'horodatage par
    UPDATE (aware) pour tester une période sans lire l'horloge."""
    MouvementRebut.objects.filter(id=rebut.id).update(
        created_at=timezone.make_aware(
            datetime.datetime.combine(jour, datetime.time(10, 0)),
            timezone.get_default_timezone()))


class Ntwms24Base(TestCase):
    def setUp(self):
        from apps.installations.models import BinLocation

        self.company = make_company('ntwms24-co', 'NTWMS24 Co')
        self.autre = make_company('ntwms24-autre', 'NTWMS24 Autre')
        self.admin = User.objects.create_user(
            username='ntwms24_admin', password='x', role_legacy='admin',
            company=self.company)
        self.magasinier = User.objects.create_user(
            username='ntwms24_magasinier', password='x', role_legacy='normal',
            company=self.company)
        self.emplacement = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt NTWMS24', is_principal=True)
        self.casier = BinLocation.objects.create(
            company=self.company, emplacement=self.emplacement,
            code='A-02-05', zone='A', allee='02', casier='05', ordre=20)
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau 550W', sku='PAN-NTWMS24',
            prix_achat=Decimal('1000'), prix_vente=Decimal('1400'),
            quantite_stock=50)
        self.api = auth(self.admin)


class TestDeclarationRebut(Ntwms24Base):
    def test_declaration_decremente_le_stock_et_chiffre_la_perte(self):
        rebut = declarer_mouvement_rebut(
            company=self.company, user=self.magasinier, produit=self.produit,
            quantite=3, motif='casse', bin_source=self.casier,
            note='Chute au déchargement')

        self.assertEqual(rebut.valeur_perte, Decimal('3000.00'))
        self.assertEqual(rebut.bin_id, self.casier.id)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 47)
        # Le mouvement posé est un REBUT — jamais un ajustement anonyme.
        self.assertEqual(rebut.mouvement.type_mouvement,
                         MouvementStock.TypeMouvement.REBUT)
        self.assertEqual(rebut.mouvement.motif_rebut, 'casse')

    def test_motif_inconnu_refuse(self):
        with self.assertRaises(ValueError):
            declarer_mouvement_rebut(
                company=self.company, user=self.admin, produit=self.produit,
                quantite=1, motif='parce_que')

    def test_quantite_non_positive_refusee(self):
        with self.assertRaises(ValueError):
            declarer_mouvement_rebut(
                company=self.company, user=self.admin, produit=self.produit,
                quantite=0, motif='vol')

    def test_produit_hors_societe_refuse(self):
        produit_autre = Produit.objects.create(
            company=self.autre, nom='Autre', sku='AUT-NTWMS24',
            prix_achat=Decimal('10'), prix_vente=Decimal('20'))
        with self.assertRaises(ValueError):
            declarer_mouvement_rebut(
                company=self.company, user=self.admin, produit=produit_autre,
                quantite=1, motif='casse')

    def test_erreur_reception_est_tracee_comme_erreur(self):
        rebut = declarer_mouvement_rebut(
            company=self.company, user=self.admin, produit=self.produit,
            quantite=2, motif='erreur_reception')
        self.assertEqual(rebut.mouvement.motif_rebut, 'erreur')


class TestRapportPertes(Ntwms24Base):
    def _rebut(self, motif, quantite, jour):
        rebut = declarer_mouvement_rebut(
            company=self.company, user=self.admin, produit=self.produit,
            quantite=quantite, motif=motif)
        _dater(rebut, jour)
        return rebut

    def test_agrege_par_motif_sur_la_periode(self):
        self._rebut('casse', 2, datetime.date(2026, 5, 4))
        self._rebut('casse', 1, datetime.date(2026, 5, 9))
        self._rebut('vol', 4, datetime.date(2026, 5, 12))

        rapport = rapport_pertes_entrepot(self.company, debut=DEBUT, fin=FIN)

        self.assertEqual(rapport['total_quantite'], 7)
        self.assertEqual(rapport['total_valeur'], Decimal('7000.00'))
        par_motif = {ligne['motif']: ligne for ligne in rapport['par_motif']}
        self.assertEqual(par_motif['casse']['quantite'], 3)
        self.assertEqual(par_motif['casse']['nb_declarations'], 2)
        self.assertEqual(par_motif['vol']['valeur'], Decimal('4000.00'))

    def test_hors_periode_exclu(self):
        self._rebut('casse', 2, datetime.date(2026, 2, 4))
        rapport = rapport_pertes_entrepot(self.company, debut=DEBUT, fin=FIN)
        self.assertEqual(rapport['total_quantite'], 0)

    def test_ajustement_inventaire_jamais_compte_comme_perte(self):
        MouvementStock.objects.create(
            company=self.company, produit=self.produit,
            type_mouvement=MouvementStock.TypeMouvement.AJUSTEMENT,
            quantite=5, quantite_avant=50, quantite_apres=45,
            created_by=self.admin, reference='INV-1')
        rapport = rapport_pertes_entrepot(self.company)
        self.assertEqual(rapport['total_quantite'], 0)
        self.assertEqual(rapport['par_motif'], [])


class TestEndpointsRebut(Ntwms24Base):
    URL = '/api/django/stock/mouvements-rebut/'
    URL_PERTES = '/api/django/stock/entrepot/pertes/'

    def test_magasinier_peut_declarer(self):
        reponse = auth(self.magasinier).post(self.URL, {
            'produit': self.produit.id, 'quantite': 2, 'motif': 'casse',
            'bin': self.casier.id, 'note': 'Casse chariot',
        }, format='json')
        self.assertEqual(reponse.status_code, 201)
        self.assertEqual(reponse.data['valeur_perte'], '2000.00')
        self.assertEqual(reponse.data['motif_libelle'], 'Casse')

    def test_rapport_pertes_reserve_aux_responsables(self):
        self.assertEqual(
            auth(self.magasinier).get(self.URL_PERTES).status_code, 403)
        self.assertEqual(self.api.get(self.URL_PERTES).status_code, 200)

    def test_rapport_pertes_via_api(self):
        declarer_mouvement_rebut(
            company=self.company, user=self.admin, produit=self.produit,
            quantite=3, motif='perime')
        reponse = self.api.get(self.URL_PERTES)
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.data['total_quantite'], 3)
        self.assertEqual(len(reponse.data['par_motif']), 1)

    def test_isolation_multi_societe(self):
        intrus = User.objects.create_user(
            username='ntwms24_intrus', password='x', role_legacy='admin',
            company=self.autre)
        declarer_mouvement_rebut(
            company=self.company, user=self.admin, produit=self.produit,
            quantite=1, motif='vol')
        reponse = auth(intrus).get(self.URL)
        resultats = reponse.data.get('results', reponse.data)
        self.assertEqual(len(resultats), 0)
