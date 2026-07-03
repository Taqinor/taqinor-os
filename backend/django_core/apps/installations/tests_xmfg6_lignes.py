"""
XMFG6 — Composants personnalisables par ordre (kit sur-mesure à la commande).

Couvre :
  * la création d'un ordre copie la BOM du kit en lignes éditables ;
  * modifier les lignes d'un ordre PLANIFIÉ change réservation + consommation
    + coût prévu, SANS toucher le kit maître ;
  * édition verrouillée dès `en_cours` (et après) ;
  * la clôture (XMFG1) consomme depuis les LIGNES, pas la BOM du kit, quand
    des lignes existent.

Run :
    python manage.py test apps.installations.tests_xmfg6_lignes -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import (
    Kit, KitComposant, OrdreAssemblage, OrdreAssemblageLigne,
    ReservationAssemblage,
)

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'xmfg6-co-{n}', defaults={'nom': nom or f'XMFG6 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'xmfg6-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_produit(company, nom='Disjoncteur', stock=100, prix_achat=0):
    from apps.stock.models import Produit
    return Produit.objects.create(
        company=company, nom=nom, prix_vente=200, prix_achat=prix_achat,
        quantite_stock=stock)


class TestLignesPersonnalisables(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.composite = make_produit(self.company, nom='Coffret', stock=0)
        self.comp1 = make_produit(
            self.company, nom='Disjoncteur', stock=100, prix_achat=10)
        self.comp2 = make_produit(
            self.company, nom='Presse-étoupe', stock=100, prix_achat=2)
        self.kit = Kit.objects.create(
            company=self.company, nom='Coffret', produit_compose=self.composite)
        KitComposant.objects.create(kit=self.kit, produit=self.comp1, quantite=2)
        KitComposant.objects.create(kit=self.kit, produit=self.comp2, quantite=4)

    def test_creation_copie_bom_en_lignes(self):
        resp = self.api.post(f'{BASE}/ordres-assemblage/', {
            'kit': self.kit.id, 'quantite': 3,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        ordre = OrdreAssemblage.objects.get(id=resp.data['id'])
        lignes = list(ordre.lignes.all())
        self.assertEqual(len(lignes), 2)
        by_produit = {ligne.produit_id: ligne.quantite for ligne in lignes}
        self.assertEqual(by_produit[self.comp1.id], 2 * 3)
        self.assertEqual(by_produit[self.comp2.id], 4 * 3)
        self.assertTrue(all(
            ligne.origine == OrdreAssemblageLigne.Origine.KIT for ligne in lignes))

    def test_modifier_ligne_ne_touche_pas_kit_maitre(self):
        ordre = OrdreAssemblage.objects.create(
            company=self.company, reference='ASM-L1', kit=self.kit, quantite=1)
        from apps.installations.services import seed_lignes_assemblage
        seed_lignes_assemblage(ordre)
        ligne = ordre.lignes.get(produit=self.comp1)
        resp = self.api.patch(
            f'{BASE}/ordre-assemblage-lignes/{ligne.id}/',
            {'quantite': 5}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        ligne.refresh_from_db()
        self.assertEqual(ligne.quantite, 5)
        # le kit maître (BOM) n'a pas bougé
        kit_composant = self.kit.composants.get(produit=self.comp1)
        self.assertEqual(kit_composant.quantite, 2)

    def test_ajout_ligne_recalcule_cout_prevu(self):
        ordre = OrdreAssemblage.objects.create(
            company=self.company, reference='ASM-L2', kit=self.kit, quantite=1)
        from apps.installations.services import (
            seed_lignes_assemblage, cout_prevu_assemblage,
        )
        seed_lignes_assemblage(ordre)
        cout_avant = cout_prevu_assemblage(ordre)
        self.assertEqual(cout_avant, 2 * 10 + 4 * 2)  # 28

        extra = make_produit(self.company, nom='Vis inox', stock=100, prix_achat=1)
        resp = self.api.post(f'{BASE}/ordre-assemblage-lignes/', {
            'ordre': ordre.id, 'produit': extra.id, 'quantite': 10,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        ligne = OrdreAssemblageLigne.objects.get(id=resp.data['id'])
        self.assertEqual(ligne.origine, OrdreAssemblageLigne.Origine.AJOUT)
        cout_apres = cout_prevu_assemblage(ordre)
        self.assertEqual(cout_apres, cout_avant + 10 * 1)

    def test_edition_verrouillee_des_en_cours(self):
        ordre = OrdreAssemblage.objects.create(
            company=self.company, reference='ASM-L3', kit=self.kit, quantite=1)
        from apps.installations.services import seed_lignes_assemblage
        seed_lignes_assemblage(ordre)
        ligne = ordre.lignes.get(produit=self.comp1)
        self.api.post(
            f'{BASE}/ordres-assemblage/{ordre.id}/demarrer/', {}, format='json')
        resp = self.api.patch(
            f'{BASE}/ordre-assemblage-lignes/{ligne.id}/',
            {'quantite': 99}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
        ligne.refresh_from_db()
        self.assertEqual(ligne.quantite, 2)

    def test_reservation_suit_les_lignes_modifiees(self):
        ordre = OrdreAssemblage.objects.create(
            company=self.company, reference='ASM-L4', kit=self.kit, quantite=1)
        from apps.installations.services import (
            seed_lignes_assemblage, seed_reservations_assemblage,
        )
        seed_lignes_assemblage(ordre)
        ligne = ordre.lignes.get(produit=self.comp1)
        ligne.quantite = 7
        ligne.save(update_fields=['quantite'])
        seed_reservations_assemblage(ordre)
        resa = ReservationAssemblage.objects.get(ordre=ordre, produit=self.comp1)
        self.assertEqual(resa.quantite, 7)

    def test_terminer_consomme_depuis_les_lignes(self):
        ordre = OrdreAssemblage.objects.create(
            company=self.company, reference='ASM-L5', kit=self.kit, quantite=1)
        from apps.installations.services import seed_lignes_assemblage
        seed_lignes_assemblage(ordre)
        ligne = ordre.lignes.get(produit=self.comp1)
        ligne.quantite = 9  # au lieu de 2 (BOM standard)
        ligne.save(update_fields=['quantite'])

        resp = self.api.post(
            f'{BASE}/ordres-assemblage/{ordre.id}/terminer/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.comp1.refresh_from_db()
        # 100 stock initial - 9 (ligne modifiée, pas 2 de la BOM)
        self.assertEqual(self.comp1.quantite_stock, 100 - 9)
