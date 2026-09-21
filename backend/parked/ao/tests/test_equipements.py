"""AOF118 — ``EquipementAO`` : string-FK catalogue + SNAPSHOT FIGÉ.

Ce qui est prouvé ici :

* le re-seed du catalogue (renommage, changement de prix, archivage) n'a AUCUN
  effet sur un dossier déjà déposé — c'est la raison d'être du snapshot ;
* la FK ``produit`` est une string-FK ``PROTECT`` : un produit engagé ne se
  supprime pas en silence ;
* ``apps.ao.models`` n'importe JAMAIS ``apps.stock.models`` (contrat
  import-linter ``ao-models-decoupled``) — la lecture d'attributs passe par
  ``apps.stock.selectors`` ;
* la quantité de modules s'aligne sur la variante RETENUE ;
* aucun champ de coût (``prix_achat``, marge, bénéfice) n'entre dans le
  snapshot.

Run :
    python manage.py test apps.ao.tests.test_equipements -v2
"""
from decimal import Decimal

from django.db import transaction
from django.db.models import ProtectedError
from django.test import SimpleTestCase, TestCase

from apps.ao import services
from apps.ao.models import (
    AppelOffre, BatimentAO, EquipementAO, ToitureAO, VarianteCalepinage,
)
from apps.stock.models import Produit
from authentication.models import Company


class TestFrontiereCrossApp(SimpleTestCase):
    def test_les_modeles_ao_n_importent_pas_stock_models(self):
        from pathlib import Path

        import apps.ao.models as ao_models

        source = Path(ao_models.__file__).read_text(encoding='utf-8')
        self.assertNotIn('from apps.stock.models', source)
        self.assertNotIn('import apps.stock.models', source)
        # La string-FK, elle, est explicitement AUTORISÉE.
        self.assertIn("'stock.Produit'", source)

    def test_le_produit_est_protege(self):
        champ = EquipementAO._meta.get_field('produit')
        self.assertEqual(champ.remote_field.on_delete.__name__, 'PROTECT')

    def test_aucun_champ_de_cout_sur_l_equipement(self):
        noms = {f.name for f in EquipementAO._meta.get_fields()}
        for interdit in ('prix_achat', 'cout_revient', 'marge', 'benefice',
                         'prix_unitaire'):
            self.assertNotIn(interdit, noms)


class BaseEquipement(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AOF118 Co',
                                              slug='aof118-co')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-118-1', objet='Équipements')
        self.produit = Produit.objects.create(
            company=self.company, nom='Module 625 Wc bifacial',
            marque='ACME', sku='ACM-625', prix_vente=Decimal('2950.00'),
            prix_achat=Decimal('1800.00'), garantie='25 ans production')


class TestSnapshotFige(BaseEquipement):
    def test_le_snapshot_copie_le_catalogue(self):
        equipement = services.engager_equipement(
            self.ao, role=EquipementAO.Role.MODULE,
            produit_id=self.produit.id, quantite=Decimal('314'))
        self.assertEqual(equipement.designation, 'Module 625 Wc bifacial')
        self.assertEqual(equipement.marque, 'ACME')
        self.assertEqual(equipement.reference_constructeur, 'ACM-625')
        self.assertIsNotNone(equipement.snapshot_le)

    def test_un_reseed_du_catalogue_ne_touche_pas_un_dossier_depose(self):
        """Le cœur d'AOF118 : le catalogue bouge, le dossier ne bouge PAS."""
        equipement = services.engager_equipement(
            self.ao, role=EquipementAO.Role.MODULE,
            produit_id=self.produit.id, quantite=Decimal('314'))
        # Re-seed réel : renommage, nouvelle marque, nouveau prix, archivage.
        self.produit.nom = 'Module 630 Wc TOPCon'
        self.produit.marque = 'AUTRE'
        self.produit.sku = 'AUT-630'
        self.produit.prix_achat = Decimal('1650.00')
        self.produit.is_archived = True
        self.produit.save()

        equipement.refresh_from_db()
        self.assertEqual(equipement.designation, 'Module 625 Wc bifacial')
        self.assertEqual(equipement.marque, 'ACME')
        self.assertEqual(equipement.reference_constructeur, 'ACM-625')

    def test_le_snapshot_ne_porte_aucun_prix(self):
        equipement = services.engager_equipement(
            self.ao, role=EquipementAO.Role.MODULE,
            produit_id=self.produit.id, quantite=Decimal('10'))
        serialise = str(equipement.caracteristiques)
        self.assertNotIn('1800', serialise)
        self.assertNotIn('prix_achat', equipement.caracteristiques)
        self.assertNotIn('prix_vente', equipement.caracteristiques)

    def test_un_equipement_hors_catalogue_reste_possible(self):
        equipement = services.engager_equipement(
            self.ao, role=EquipementAO.Role.CABLE,
            designation='Câble solaire 6 mm²', quantite=Decimal('16000'),
            unite='ml')
        self.assertIsNone(equipement.produit_id)
        self.assertEqual(equipement.designation, 'Câble solaire 6 mm²')

    def test_un_produit_engage_ne_se_supprime_pas(self):
        services.engager_equipement(
            self.ao, role=EquipementAO.Role.MODULE,
            produit_id=self.produit.id, quantite=Decimal('314'))
        with self.assertRaises(ProtectedError), transaction.atomic():
            self.produit.delete()

    def test_la_bascule_trace_son_predecesseur(self):
        ancien = services.engager_equipement(
            self.ao, role=EquipementAO.Role.BATTERIE,
            designation='BOS-G', quantite=Decimal('1'))
        nouveau = services.engager_equipement(
            self.ao, role=EquipementAO.Role.BATTERIE,
            designation='BOS-B Pro-A3', quantite=Decimal('1'),
            remplace=ancien)
        self.assertEqual(nouveau.remplace_id, ancien.id)
        self.assertEqual(list(ancien.remplace_par.all()), [nouveau])


class TestQuantiteAlignee(BaseEquipement):
    def setUp(self):
        super().setUp()
        batiment = BatimentAO.objects.create(
            company=self.company, appel_offre=self.ao, code='C')
        self.toiture = ToitureAO.objects.create(
            company=self.company, batiment=batiment, code_document='05H')

    def test_la_quantite_de_modules_suit_la_variante_retenue(self):
        VarianteCalepinage.objects.create(
            company=self.company, toiture=self.toiture, appel_offre=self.ao,
            nom='Retenue', est_retenue=True,
            resultat={'total_modules': 314, 'kwc': 196.25})
        equipement = services.engager_equipement(
            self.ao, role=EquipementAO.Role.MODULE,
            produit_id=self.produit.id, quantite=Decimal('0'))
        total, touches = services.aligner_quantite_modules(self.ao)
        equipement.refresh_from_db()
        self.assertEqual(total, Decimal('314'))
        self.assertEqual(touches, 1)
        self.assertEqual(equipement.quantite, Decimal('314.000'))

    def test_l_alignement_est_idempotent(self):
        VarianteCalepinage.objects.create(
            company=self.company, toiture=self.toiture, appel_offre=self.ao,
            nom='Retenue', est_retenue=True,
            resultat={'total_modules': 314})
        services.engager_equipement(
            self.ao, role=EquipementAO.Role.MODULE, quantite=Decimal('0'))
        services.aligner_quantite_modules(self.ao)
        _, touches = services.aligner_quantite_modules(self.ao)
        self.assertEqual(touches, 0)

    def test_une_variante_non_retenue_ne_compte_pas(self):
        VarianteCalepinage.objects.create(
            company=self.company, toiture=self.toiture, appel_offre=self.ao,
            nom='Alternative', role=VarianteCalepinage.Role.ALTERNATIVE,
            resultat={'total_modules': 400})
        services.engager_equipement(
            self.ao, role=EquipementAO.Role.MODULE, quantite=Decimal('0'))
        total, _ = services.aligner_quantite_modules(self.ao)
        self.assertEqual(total, Decimal('0'))


class TestIsolationMultiSociete(BaseEquipement):
    def test_le_snapshot_ne_lit_pas_le_catalogue_d_une_autre_societe(self):
        autre = Company.objects.create(nom='AOF118 X', slug='aof118-x')
        produit_autre = Produit.objects.create(
            company=autre, nom='Interdit', prix_vente=Decimal('1.00'))
        instantane = services.snapshot_produit(self.company, produit_autre.id)
        self.assertEqual(instantane, {})
