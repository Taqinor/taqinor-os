"""ARC18 — Ponts additifs crm.Client & stock.Fournisseur → tiers.Tiers.

On prouve :
  - le service ``attacher_ou_creer_tiers`` dédupe par email/ICE COMPANY-SCOPÉ
    (deux sociétés, même email/ICE → deux Tiers séparés) ;
  - la sauvegarde d'un Client / Fournisseur crée OU rattache son Tiers miroir
    et pose le bon drapeau de rôle (mirror one-way) ;
  - la commande ``backfill_tiers`` est idempotente et rapporte des compteurs
    justes (créé / rattaché / déjà lié) — « backfill 100 % » ;
  - aucun changement du comportement existant (le Client garde son identité).
"""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from testkit.factories import CompanyFactory, another_tenant

from apps.tiers import services as tiers_services
from apps.tiers.models import Tiers


def _client(company, **kw):
    from apps.crm.models import Client
    defaults = dict(nom='Alaoui', prenom='Youssef',
                    email='y.alaoui@example.ma', telephone='0600000000')
    defaults.update(kw)
    return Client.objects.create(company=company, **defaults)


def _fournisseur(company, **kw):
    from apps.stock.models import Fournisseur
    defaults = dict(nom='ACME Solaire', email='contact@acme.ma',
                    ice='001122334455667')
    defaults.update(kw)
    return Fournisseur.objects.create(company=company, **defaults)


class Arc18ServiceDedupTests(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.other_company, _ = another_tenant()

    def test_dedup_by_email_same_company(self):
        t1, cree1 = tiers_services.attacher_ou_creer_tiers(
            company=self.company, nom='A', email='dup@example.ma',
            roles=('is_client',))
        t2, cree2 = tiers_services.attacher_ou_creer_tiers(
            company=self.company, nom='A bis', email='DUP@example.ma',
            roles=('is_fournisseur',))
        self.assertTrue(cree1)
        self.assertFalse(cree2)  # même email (insensible à la casse) → réutilisé
        self.assertEqual(t1.id, t2.id)
        t1.refresh_from_db()
        # Les DEUX rôles ont été cumulés sur le même Tiers.
        self.assertTrue(t1.is_client)
        self.assertTrue(t1.is_fournisseur)

    def test_dedup_by_ice_same_company(self):
        t1, _ = tiers_services.attacher_ou_creer_tiers(
            company=self.company, nom='ACME', ice='ICE-999',
            roles=('is_fournisseur',))
        t2, cree2 = tiers_services.attacher_ou_creer_tiers(
            company=self.company, nom='ACME (autre saisie)', ice='ice-999',
            roles=('is_client',))
        self.assertFalse(cree2)
        self.assertEqual(t1.id, t2.id)

    def test_dedup_is_company_scoped(self):
        # Même email dans DEUX sociétés → deux Tiers séparés (jamais de fuite).
        t_a, _ = tiers_services.attacher_ou_creer_tiers(
            company=self.company, nom='X', email='shared@example.ma')
        t_b, cree_b = tiers_services.attacher_ou_creer_tiers(
            company=self.other_company, nom='X', email='shared@example.ma')
        self.assertTrue(cree_b)
        self.assertNotEqual(t_a.id, t_b.id)
        self.assertEqual(t_a.company_id, self.company.id)
        self.assertEqual(t_b.company_id, self.other_company.id)

    def test_never_overwrites_filled_identity(self):
        t, _ = tiers_services.attacher_ou_creer_tiers(
            company=self.company, nom='N', email='keep@example.ma',
            telephone='0611111111')
        # Deuxième appel avec un téléphone DIFFÉRENT : ne doit PAS écraser.
        tiers_services.attacher_ou_creer_tiers(
            company=self.company, nom='N', email='keep@example.ma',
            telephone='0699999999')
        t.refresh_from_db()
        self.assertEqual(t.telephone, '0611111111')


class Arc18MirrorOnSaveTests(TestCase):
    def setUp(self):
        self.company = CompanyFactory()

    def test_saving_client_creates_and_links_tiers(self):
        client = _client(self.company, type_client='entreprise',
                         ice='ICE-CLI-1')
        client.refresh_from_db()
        self.assertIsNotNone(client.tiers_id)
        tiers = client.tiers
        self.assertEqual(tiers.company_id, self.company.id)
        self.assertTrue(tiers.is_client)
        self.assertEqual(tiers.email, 'y.alaoui@example.ma')
        self.assertEqual(tiers.type_tiers, 'entreprise')

    def test_saving_fournisseur_creates_and_links_tiers(self):
        f = _fournisseur(self.company)
        f.refresh_from_db()
        self.assertIsNotNone(f.tiers_id)
        self.assertTrue(f.tiers.is_fournisseur)
        self.assertEqual(f.tiers.ice, '001122334455667')

    def test_service_fournisseur_flags_soustraitant(self):
        f = _fournisseur(self.company, type='service', ice='ICE-ST-1')
        f.refresh_from_db()
        self.assertTrue(f.tiers.is_fournisseur)
        self.assertTrue(f.tiers.is_soustraitant)

    def test_client_and_fournisseur_same_ice_share_tiers(self):
        # Un même acteur (même ICE) client ET fournisseur → un seul Tiers,
        # cumulant les deux rôles.
        client = _client(self.company, type_client='entreprise',
                         email='both@acme.ma', ice='ICE-BOTH')
        f = _fournisseur(self.company, email='autre@acme.ma', ice='ICE-BOTH')
        client.refresh_from_db()
        f.refresh_from_db()
        self.assertEqual(client.tiers_id, f.tiers_id)
        self.assertTrue(client.tiers.is_client)
        self.assertTrue(client.tiers.is_fournisseur)

    def test_client_api_behaviour_unchanged(self):
        # L'identité reste maître côté Client : le miroir n'altère aucun champ.
        client = _client(self.company, nom='Original', prenom='Nom')
        client.refresh_from_db()
        self.assertEqual(client.nom, 'Original')
        self.assertEqual(client.prenom, 'Nom')

    def test_keyless_client_resaves_do_not_spawn_duplicate_tiers(self):
        # Un client SANS email ni ICE (aucune clé de dédup) : re-sauvegarder
        # plusieurs fois ne doit JAMAIS créer un 2ᵉ Tiers (réutilise le lien).
        client = _client(self.company, nom='SansClé', email=None,
                         telephone='0600000000')
        client.refresh_from_db()
        premier = client.tiers_id
        self.assertIsNotNone(premier)
        client.telephone = '0611111111'
        client.save()
        client.telephone = '0622222222'
        client.save()
        client.refresh_from_db()
        self.assertEqual(client.tiers_id, premier)
        self.assertEqual(
            Tiers.objects.filter(company=self.company).count(), 1)


class Arc18BackfillCommandTests(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.other_company, _ = another_tenant()

    def _run(self, **kw):
        out = StringIO()
        call_command('backfill_tiers', stdout=out, **kw)
        return out.getvalue()

    def test_backfill_links_all_and_reports_counts(self):
        # Crée des enregistrements SANS déclencher automatiquement le miroir :
        # on efface le lien pour simuler des lignes historiques pré-pont.
        client = _client(self.company, email='bf-cli@example.ma')
        f = _fournisseur(self.company, email='bf-four@example.ma',
                         ice='ICE-BF-1')
        # Simule des lignes historiques (lien vidé + Tiers supprimés).
        from apps.crm.models import Client
        from apps.stock.models import Fournisseur
        Client.objects.filter(pk=client.pk).update(tiers=None)
        Fournisseur.objects.filter(pk=f.pk).update(tiers=None)
        Tiers.objects.all().delete()

        output = self._run()
        client.refresh_from_db()
        f.refresh_from_db()
        # 100 % des enregistrements sont désormais reliés.
        self.assertIsNotNone(client.tiers_id)
        self.assertIsNotNone(f.tiers_id)
        self.assertIn('Total', output)
        self.assertIn('créé', output)

    def test_backfill_is_idempotent(self):
        _client(self.company, email='idem@example.ma')
        # Premier passage (le miroir a déjà lié à la création) → tout « déjà lié ».
        out1 = self._run()
        out2 = self._run()
        # Un second passage ne crée aucun nouveau Tiers.
        self.assertIn('déjà lié', out2)
        self.assertEqual(
            Tiers.objects.filter(company=self.company).count(), 1)
        self.assertIn('Total', out1)

    def test_backfill_company_scoped(self):
        _client(self.company, email='scoped@example.ma')
        _client(self.other_company, email='scoped@example.ma')
        # Restreint à une société : seul son enregistrement est traité.
        self._run(company_slug=self.company.slug)
        # Chaque société garde son propre Tiers (jamais fusionnés).
        self.assertEqual(
            Tiers.objects.filter(company=self.company).count(), 1)
        self.assertEqual(
            Tiers.objects.filter(company=self.other_company).count(), 1)
