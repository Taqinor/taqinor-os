"""ARC19 — Ponts Tiers : compta.Partenaire et rh.DossierEmploye.

On prouve :
  - la sauvegarde d'un Partenaire crée/rattache son Tiers miroir + pose
    ``is_partenaire`` ;
  - la sauvegarde d'un DossierEmploye (partie INTERNE) crée/rattache son Tiers
    SANS poser de rôle commercial et SANS miroiter le RIB (ARC25) ;
  - le backfill couvre désormais les 4 sources et reste company-scopé ;
  - la dédup reste bornée à la société.
"""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from testkit.factories import CompanyFactory, another_tenant

from apps.tiers.models import Tiers


def _partenaire(company, **kw):
    from apps.compta.models import Partenaire
    import secrets
    defaults = dict(nom='Apporteur SARL', email='p@example.ma',
                    token_acces=secrets.token_urlsafe(16))
    defaults.update(kw)
    return Partenaire.objects.create(company=company, **defaults)


def _dossier(company, **kw):
    from apps.rh.models import DossierEmploye
    defaults = dict(matricule='M-001', nom='Bennani', prenom='Sara',
                    cin='AB123456', email='s.bennani@example.ma',
                    rib='RIB-INTERNE-999')
    defaults.update(kw)
    return DossierEmploye.objects.create(company=company, **defaults)


class Arc19PartenaireBridgeTests(TestCase):
    def setUp(self):
        self.company = CompanyFactory()

    def test_saving_partenaire_creates_and_links_tiers(self):
        p = _partenaire(self.company)
        p.refresh_from_db()
        self.assertIsNotNone(p.tiers_id)
        self.assertTrue(p.tiers.is_partenaire)
        self.assertEqual(p.tiers.email, 'p@example.ma')
        self.assertEqual(p.tiers.company_id, self.company.id)


class Arc19DossierBridgeTests(TestCase):
    def setUp(self):
        self.company = CompanyFactory()

    def test_saving_dossier_creates_internal_tiers_no_commercial_role(self):
        d = _dossier(self.company)
        d.refresh_from_db()
        self.assertIsNotNone(d.tiers_id)
        t = d.tiers
        # Partie INTERNE : aucun rôle commercial n'est posé.
        self.assertFalse(t.is_client)
        self.assertFalse(t.is_fournisseur)
        self.assertFalse(t.is_partenaire)
        self.assertFalse(t.is_soustraitant)
        # Identité de contact miroité…
        self.assertEqual(t.cin, 'AB123456')
        self.assertEqual(t.prenom, 'Sara')

    def test_rib_is_never_mirrored(self):
        # ARC25 gère la fusion RIB — le pont ARC19 ne miroite JAMAIS le RIB.
        d = _dossier(self.company)
        d.refresh_from_db()
        self.assertEqual(d.tiers.rib, '')


class Arc19BackfillTests(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.other_company, _ = another_tenant()

    def test_backfill_covers_partenaire_and_dossier(self):
        out = StringIO()
        _partenaire(self.company, email='bf-part@example.ma')
        _dossier(self.company, matricule='M-BF', email='bf-emp@example.ma')
        call_command('backfill_tiers', stdout=out)
        text = out.getvalue()
        # ODX13 a rapatrié Partenaire de compta vers crm (state-only, même
        # modèle historique) — le rapport de backfill suit le nouveau label.
        self.assertIn('crm.Partenaire', text)
        self.assertIn('rh.DossierEmploye', text)

    def test_backfill_dossier_company_scoped(self):
        _dossier(self.company, matricule='A', email='dup@example.ma')
        _dossier(self.other_company, matricule='B', email='dup@example.ma')
        call_command('backfill_tiers', stdout=StringIO(),
                     company_slug=self.company.slug)
        # Chaque société garde son propre Tiers (jamais fusionnés cross-tenant).
        self.assertEqual(
            Tiers.objects.filter(company=self.company).count(), 1)
        self.assertEqual(
            Tiers.objects.filter(company=self.other_company).count(), 1)
