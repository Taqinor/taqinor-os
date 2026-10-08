"""ASTK212 (C-ASTK-055, règle ACAL298) — un id d'une AUTRE société reçoit
EXACTEMENT la réponse d'un id absent sur chaque validation de stock : 400
« objet inexistant » de DRF, jamais 403, jamais « hors de votre entreprise ».

Sonde TEN-11 d'origine : mouvement étranger → 403 {"detail":"Produit hors de
votre entreprise."} vs absent → 400 « Clé primaire … non valide » ; facture
étrangère → 400 « Fournisseur hors de votre entreprise. » vs absent → 400
« Clé primaire … ».

Chaque paire compare les deux corps octet par octet après neutralisation de
l'id cité par le message DRF (et du ``request_id`` propre à chaque requête) ;
aucun objet n'est créé. Aucun mock : vues et sérialiseurs réels.

Run :
    python manage.py test apps.stock.test_astk_oracle_existence -v 2
"""
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.stock.models import (
    AvoirFournisseur, BonCommandeFournisseur, EmplacementStock,
    FactureFournisseur, Fournisseur, KitProduit, MouvementStock,
    NomenclatureCodeBarres, PrixFournisseur, Produit, RegleCodeBarres,
)

User = get_user_model()

BASE = '/api/django/stock'
ID_ABSENT = 99999999


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def _neutralise(texte, pk):
    """Corps JSON où l'id cité et le ``request_id`` sont neutralisés."""
    corps = json.loads(texte)
    enveloppe = corps.get('error') if isinstance(corps, dict) else None
    if isinstance(enveloppe, dict) and 'request_id' in enveloppe:
        enveloppe['request_id'] = '<REQUEST_ID>'
    return json.dumps(corps, ensure_ascii=False, sort_keys=True).replace(
        f'« {pk} »', '« <ID> »').replace(
        f'« {pk} »', '« <ID> »').replace(f'"{pk}"', '"<ID>"').replace(
        f'\\"{pk}\\"', '\\"<ID>\\"').replace(f"'{pk}'", "'<ID>'")


class OracleExistenceTests(TestCase):
    def setUp(self):
        self.co_a = Company.objects.create(nom='astk212-a', slug='astk212-a')
        self.co_b = Company.objects.create(nom='astk212-b', slug='astk212-b')
        self.resp_a = User.objects.create_user(
            username='astk212-admin-a', password='x', company=self.co_a,
            role_legacy='admin')
        self.api = _api(self.resp_a)
        self.fa = Fournisseur.objects.create(company=self.co_a, nom='FA')
        self.fb = Fournisseur.objects.create(
            company=self.co_b, nom='FOURNISSEUR-B-SECRET')
        self.pa = Produit.objects.create(
            company=self.co_a, nom='Produit A', sku='ASTK212-PA',
            prix_vente=Decimal('30'), prix_achat=Decimal('10'),
            quantite_stock=50)
        self.pb = Produit.objects.create(
            company=self.co_b, nom='PRODUIT-B-SECRET', sku='ASTK212-PB',
            prix_vente=Decimal('30'), prix_achat=Decimal('10'))
        self.bc_b = BonCommandeFournisseur.objects.create(
            company=self.co_b, reference='BCFB-SECRET', fournisseur=self.fb,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        self.facture_b = FactureFournisseur.objects.create(
            company=self.co_b, reference='FFB-SECRET', fournisseur=self.fb,
            montant_ht=Decimal('100'), montant_tva=Decimal('20'),
            montant_ttc=Decimal('120'))
        self.emp_b = EmplacementStock.objects.create(
            company=self.co_b, nom='EMP-B-SECRET')
        self.nomenclature_b = NomenclatureCodeBarres.objects.create(
            company=self.co_b, nom='NOMENCLATURE-B-SECRET')

    def assertPaire(self, url, corps, champ, pk_etranger, modele):
        """POST ``corps(pk)`` avec l'id étranger puis l'id absent : deux
        400 octet-identiques (id neutralisé), erreur sur ``champ``, aucun
        objet créé, aucun libellé de B divulgué."""
        avant = modele.objects.count()
        r_etranger = self.api.post(url, corps(pk_etranger), format='json')
        r_absent = self.api.post(url, corps(ID_ABSENT), format='json')
        self.assertEqual(r_etranger.status_code, 400, r_etranger.content)
        self.assertEqual(r_absent.status_code, 400, r_absent.content)
        texte = r_etranger.content.decode('utf-8')
        self.assertNotIn('hors de votre entreprise', texte)
        self.assertNotIn('SECRET', texte)
        self.assertIn(champ, texte)
        self.assertEqual(
            _neutralise(texte, pk_etranger),
            _neutralise(r_absent.content.decode('utf-8'), ID_ABSENT))
        self.assertEqual(modele.objects.count(), avant)

    def test_mouvement_produit(self):
        self.assertPaire(
            f'{BASE}/mouvements/',
            lambda pk: {'produit': pk, 'type_mouvement': 'entree',
                        'quantite': 1},
            'produit', self.pb.id, MouvementStock)

    def test_regle_code_barres_nomenclature(self):
        self.assertPaire(
            f'{BASE}/regles-code-barres/',
            lambda pk: {'nomenclature': pk, 'motif': '21', 'encode': 'produit',
                        'priorite': 1},
            'nomenclature', self.nomenclature_b.id, RegleCodeBarres)

    def test_prix_fournisseur_produit(self):
        self.assertPaire(
            f'{BASE}/prix-fournisseurs/',
            lambda pk: {'produit': pk, 'fournisseur': self.fa.id,
                        'prix_achat': '10.00'},
            'produit', self.pb.id, PrixFournisseur)

    def test_prix_fournisseur_fournisseur(self):
        self.assertPaire(
            f'{BASE}/prix-fournisseurs/',
            lambda pk: {'produit': self.pa.id, 'fournisseur': pk,
                        'prix_achat': '10.00'},
            'fournisseur', self.fb.id, PrixFournisseur)

    def _facture(self, **champs):
        corps = {'fournisseur': self.fa.id, 'reference_fournisseur': 'F-1',
                 'montant_ht': '100.00', 'montant_tva': '20.00',
                 'montant_ttc': '120.00'}
        corps.update(champs)
        return corps

    def test_facture_fournisseur(self):
        self.assertPaire(
            f'{BASE}/factures-fournisseur/',
            lambda pk: self._facture(fournisseur=pk),
            'fournisseur', self.fb.id, FactureFournisseur)

    def test_facture_bon_commande(self):
        self.assertPaire(
            f'{BASE}/factures-fournisseur/',
            lambda pk: self._facture(bon_commande=pk),
            'bon_commande', self.bc_b.id, FactureFournisseur)

    def _avoir(self, **champs):
        corps = {'fournisseur': self.fa.id, 'montant_ht': '10.00',
                 'montant_tva': '2.00', 'montant_ttc': '12.00'}
        corps.update(champs)
        return corps

    def test_avoir_fournisseur(self):
        self.assertPaire(
            f'{BASE}/avoirs-fournisseur/',
            lambda pk: self._avoir(fournisseur=pk),
            'fournisseur', self.fb.id, AvoirFournisseur)

    def test_avoir_facture_origine(self):
        self.assertPaire(
            f'{BASE}/avoirs-fournisseur/',
            lambda pk: self._avoir(facture_origine=pk),
            'facture_origine', self.facture_b.id, AvoirFournisseur)

    def _bcf(self, **champs):
        corps = {'fournisseur': self.fa.id, 'lignes': [
            {'produit': self.pa.id, 'quantite': 1,
             'prix_achat_unitaire': '10.00'}]}
        corps.update(champs)
        return corps

    def test_bcf_fournisseur(self):
        self.assertPaire(
            f'{BASE}/bons-commande-fournisseur/',
            lambda pk: self._bcf(fournisseur=pk),
            'fournisseur', self.fb.id, BonCommandeFournisseur)

    def test_bcf_emplacement_destination(self):
        self.assertPaire(
            f'{BASE}/bons-commande-fournisseur/',
            lambda pk: self._bcf(emplacement_destination=pk),
            'emplacement_destination', self.emp_b.id, BonCommandeFournisseur)

    def test_bcf_lignes_produit(self):
        self.assertPaire(
            f'{BASE}/bons-commande-fournisseur/',
            lambda pk: self._bcf(lignes=[{
                'produit': pk, 'quantite': 1,
                'prix_achat_unitaire': '10.00'}]),
            'produit', self.pb.id, BonCommandeFournisseur)

    def test_kit_composants_produit(self):
        self.assertPaire(
            f'{BASE}/kits/',
            lambda pk: {'nom': 'Kit A', 'composants': [
                {'produit': pk, 'quantite': 1}]},
            'produit', self.pb.id, KitProduit)

    def test_onboarding_fournisseur(self):
        from apps.stock.models import DossierOnboardingFournisseur
        self.assertPaire(
            f'{BASE}/dossiers-onboarding-fournisseur/',
            lambda pk: {'fournisseur': pk},
            'fournisseur', self.fb.id, DossierOnboardingFournisseur)

    def test_aucun_message_hors_entreprise_dans_le_code(self):
        """Aucun message propre « … hors de votre entreprise » ne subsiste
        dans les validations de stock (vues + sérialiseurs)."""
        racine = Path(__file__).resolve().parent
        fautifs = []
        for chemin in [racine / 'serializers.py', *racine.glob('views/*.py')]:
            if 'hors de votre entreprise' in chemin.read_text(
                    encoding='utf-8'):
                fautifs.append(chemin.name)
        self.assertEqual(fautifs, [])
