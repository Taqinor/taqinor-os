"""ASAV6 — un contrat de maintenance né d'un devis accepté porte le chantier.

Le chantier d'un devis se lit par ``installations.selectors.
installation_for_devis`` (related_name ``installations`` côté chantier) —
l'ancien ``getattr(devis, 'installation', None)`` lisait un attribut qui
n'existe pas et rendait toujours None. Les visites préventives générées
ensuite portent le même chantier ; un devis sans chantier garde
``installation=None``.

Run :
    python manage.py test apps.sav.tests_asav6_contrat_chantier_devis -v2
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.sav.maintenance import generer_visites_dues
from apps.sav.models import ContratMaintenance, Ticket
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis
from core.events import devis_accepted

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


class ContratChantierDevisTests(TestCase):

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='asav6-co', defaults={'nom': 'ASAV6 Co'})
        self.user = User.objects.create_user(
            username='asav6_admin', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='ASAV6',
            email='asav6-client@example.invalid')
        self.produit = Produit.objects.create(
            company=self.company, nom='Maintenance annuelle', sku='MNT-ASAV6',
            prix_achat=0, prix_vente=1200, est_recurrent=True,
            periodicite_defaut=Produit.PeriodiciteDefaut.TRIMESTRIEL)

    def _devis_accepte(self, num, avec_chantier):
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-{num:04d}',
            client=self.client_obj, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20'))
        LigneDevis.objects.create(
            devis=devis, produit=self.produit,
            designation='Maintenance annuelle', quantite=1,
            prix_unitaire=Decimal('1200'), taux_tva=Decimal('20'))
        chantier = None
        if avec_chantier:
            chantier = Installation.objects.create(
                company=self.company, reference=f'CHT-ASAV6-{num}',
                client=self.client_obj, devis=devis)
        devis_accepted.send(
            sender=None, devis=devis, user=self.user, ancien_statut='envoye')
        contrat = ContratMaintenance.objects.get(
            company=self.company, notes__contains=f'[devis:{devis.pk}]')
        return contrat, chantier

    def test_contrat_porte_chantier(self):
        contrat, chantier = self._devis_accepte(1, avec_chantier=True)
        contrat.refresh_from_db()
        self.assertEqual(contrat.installation_id, chantier.id)

    def test_visites_sur_chantier(self):
        contrat, chantier = self._devis_accepte(2, avec_chantier=True)
        ContratMaintenance.objects.filter(pk=contrat.pk).update(
            date_debut=timezone.localdate() - timedelta(days=200))
        genere = generer_visites_dues(self.company, self.user)
        self.assertGreaterEqual(genere, 1)
        visites = Ticket.objects.filter(
            company=self.company, type=Ticket.Type.PREVENTIF,
            description__contains=f'contrat #{contrat.pk}')
        self.assertTrue(visites.exists())
        self.assertEqual(
            set(visites.values_list('installation_id', flat=True)),
            {chantier.id})

    def test_sans_chantier_prealable_rattache_au_chantier_ne(self):
        # Pas de chantier AVANT l'acceptation : ``installations`` crée le
        # chantier de l'affaire sur ``devis_accepted`` (receveur abonné avant
        # celui de sav) — le contrat porte CE chantier, jamais un autre.
        contrat, _ = self._devis_accepte(3, avec_chantier=False)
        contrat.refresh_from_db()
        chantier_ne = Installation.objects.get(
            company=self.company, client=self.client_obj)
        self.assertEqual(contrat.installation_id, chantier_ne.id)
