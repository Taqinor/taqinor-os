"""Garde de `crm.services.delete_leads_for_company` — suppression DURE de
tous les leads d'une société, réservée au bac à sable API (NTAPI27).

La fonction contourne la corbeille/soft-delete : ni trace, ni annulation. Elle
n'est appelée aujourd'hui que par `publicapi.services.reset_sandbox` sur
`tenant.sandbox_company`, mais un `SandboxTenant` mal pointé suffirait à
détruire le pipeline commercial RÉEL. La défense vit donc DANS le service,
pas seulement chez l'appelant : ces tests prouvent qu'elle refuse une société
réelle (y compris la société PROPRIÉTAIRE d'un bac à sable) et qu'elle
fonctionne toujours sur une vraie société-jumelle.
"""
from django.test import TestCase

from authentication.models import Company

from apps.publicapi.models import SandboxTenant
from apps.publicapi.services import get_or_create_sandbox, reset_sandbox

from .models import Lead
from .services import SuppressionLeadsRefusee, delete_leads_for_company


class GardeSuppressionLeadsTests(TestCase):
    def setUp(self):
        self.reelle = Company.objects.create(
            slug='ntapi27-garde-reelle', nom='Société réelle')

    def test_refuse_une_societe_reelle_sans_bac_a_sable(self):
        Lead.objects.create(company=self.reelle, nom='Prospect réel')

        with self.assertRaises(SuppressionLeadsRefusee) as ctx:
            delete_leads_for_company(self.reelle)

        self.assertIn('REFUSÉE', str(ctx.exception))
        self.assertEqual(Lead.objects.filter(company=self.reelle).count(), 1)

    def test_refuse_la_societe_proprietaire_du_bac_a_sable(self):
        """Le cas dangereux : `SandboxTenant.company` est la société RÉELLE ;
        seule `sandbox_company` est jetable."""
        tenant = get_or_create_sandbox(self.reelle)
        Lead.objects.create(company=tenant.company, nom='Prospect réel')

        with self.assertRaises(SuppressionLeadsRefusee):
            delete_leads_for_company(tenant.company)

        self.assertEqual(Lead.objects.filter(company=tenant.company).count(), 1)

    def test_refuse_une_societe_inexistante_ou_none(self):
        with self.assertRaises(SuppressionLeadsRefusee):
            delete_leads_for_company(None)

    def test_accepte_une_vraie_societe_jumelle_sandbox(self):
        tenant = get_or_create_sandbox(self.reelle)
        sandbox = tenant.sandbox_company
        self.assertTrue(
            SandboxTenant.objects.filter(sandbox_company=sandbox).exists())

        Lead.objects.create(company=sandbox, nom='Lead ajouté au bac à sable')
        avant = Lead.objects.filter(company=sandbox).count()
        self.assertGreater(avant, 0)
        Lead.objects.create(company=self.reelle, nom='Prospect réel')

        supprimes = delete_leads_for_company(sandbox)

        self.assertEqual(supprimes, avant)
        self.assertEqual(Lead.objects.filter(company=sandbox).count(), 0)
        # Isolation multi-société : la société réelle n'est jamais touchée.
        self.assertEqual(Lead.objects.filter(company=self.reelle).count(), 1)

    def test_le_reset_du_bac_a_sable_fonctionne_toujours(self):
        """Le seul appelant légitime traverse la garde sans la déclencher."""
        tenant = get_or_create_sandbox(self.reelle)
        Lead.objects.create(company=tenant.sandbox_company, nom='Lead en trop')

        recrees = reset_sandbox(tenant)

        self.assertGreater(recrees, 0)
        self.assertEqual(
            Lead.objects.filter(company=tenant.sandbox_company).count(),
            recrees)
