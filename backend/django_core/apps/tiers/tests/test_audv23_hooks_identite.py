"""AUDV23 (ARC21) — les hooks d'écriture identité sont CÂBLÉS.

``crm.services.ecrire_identite_client`` et
``stock.services.ecrire_identite_fournisseur`` existaient depuis ARC21 mais
n'avaient AUCUN appelant hors tests : activer ``TIERS_SOURCE_ECRITURE`` aurait
donc été un NOUVEAU CHANTIER, pas un simple flip de flag. Ils sont désormais
branchés sur le MÊME point que le miroir ARC18 (le récepteur ``post_save``) —
donc TOUTE sauvegarde les traverse : API, admin, service, import.

LE FLAG RESTE OFF EN PROD : aucun changement de comportement visible tant que
le fondateur ne l'active pas. Ces tests prouvent les DEUX modes.
"""
from django.test import TestCase, override_settings

from apps.crm.models import Client
from apps.stock.models import Fournisseur
from testkit.factories import CompanyFactory


class HooksCablesFlagOff(TestCase):
    """Défaut de production : NO-OP strict, rien ne bouge."""

    def setUp(self):
        self.company = CompanyFactory()

    def test_sauvegarde_client_ne_touche_pas_le_tiers(self):
        client = Client.objects.create(
            company=self.company, nom='Avant', email='audv23@example.ma')
        client.refresh_from_db()
        self.assertIsNotNone(client.tiers_id, 'le miroir ARC18 doit exister')
        # Le miroir a posé le nom à la création ; on le modifie DIRECTEMENT sur
        # le Tiers puis on re-sauvegarde le client : flag OFF, le hook
        # d'écriture ne doit rien pousser.
        tiers = client.tiers
        tiers.prenom = 'PoséÀLaMain'
        tiers.save(update_fields=['prenom'])

        client.prenom = 'Nouveau'
        client.save()
        tiers.refresh_from_db()
        self.assertEqual(tiers.prenom, 'PoséÀLaMain')

    def test_sauvegarde_fournisseur_ne_touche_pas_le_tiers(self):
        fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Grossiste', email='f@example.ma')
        fournisseur.refresh_from_db()
        self.assertIsNotNone(fournisseur.tiers_id)
        tiers = fournisseur.tiers
        tiers.telephone = '+212600000000'
        tiers.save(update_fields=['telephone'])

        fournisseur.telephone = '+212611111111'
        fournisseur.save()
        tiers.refresh_from_db()
        self.assertEqual(tiers.telephone, '+212600000000')


@override_settings(TIERS_SOURCE_ECRITURE=True)
class HooksCablesFlagOn(TestCase):
    """Flag forcé ON : la sauvegarde écrit bien le Tiers miroir.

    ROUGE avant AUDV23 : les services existaient, personne ne les appelait —
    activer le flag n'aurait RIEN changé au comportement de sauvegarde.
    """

    def setUp(self):
        self.company = CompanyFactory()

    def test_la_sauvegarde_d_un_client_ecrit_son_tiers(self):
        client = Client.objects.create(
            company=self.company, nom='Alaoui', prenom='Karim',
            email='audv23on@example.ma')
        client.refresh_from_db()
        self.assertIsNotNone(client.tiers_id)

        client.prenom = 'Karima'
        client.telephone = '+212622222222'
        client.save()
        tiers = client.tiers
        tiers.refresh_from_db()
        self.assertEqual(tiers.prenom, 'Karima')
        self.assertEqual(tiers.telephone, '+212622222222')

    def test_la_sauvegarde_d_un_fournisseur_ecrit_son_tiers(self):
        fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Grossiste', email='fon@example.ma')
        fournisseur.refresh_from_db()
        self.assertIsNotNone(fournisseur.tiers_id)

        fournisseur.telephone = '+212633333333'
        fournisseur.adresse = 'Zone industrielle, Casablanca'
        fournisseur.save()
        tiers = fournisseur.tiers
        tiers.refresh_from_db()
        self.assertEqual(tiers.telephone, '+212633333333')
        self.assertEqual(tiers.adresse, 'Zone industrielle, Casablanca')

    def test_aucun_prix_d_achat_ne_traverse_le_pont(self):
        """Garde permanente : le pont ne pousse QUE de l'identité."""
        from apps.stock.services import ecrire_identite_fournisseur
        import inspect
        source = inspect.getsource(ecrire_identite_fournisseur)
        self.assertNotIn('prix_achat', source)
        self.assertNotIn('marge', source)
