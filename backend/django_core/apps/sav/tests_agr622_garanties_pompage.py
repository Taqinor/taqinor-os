"""AGR622 — garanties pompe / variateur au SAV : une seule source (fiche
produit), la garantie légale dite, et les durées non sourcées signalées.

Run :
    python manage.py test apps.sav.tests_agr622_garanties_pompage -v 2
"""
from datetime import date
from html import unescape
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from apps.crm.models import Client
from apps.installations.models import Installation
from apps.sav.models import Equipement
from apps.stock.management.commands.audit_garanties_pompage import (
    SIGNAL_SANS_SOURCE, audit_garanties_pompage,
)
from apps.stock.models import Produit
from apps.ventes.quote_engine.residential.theme import WARRANTIES
from authentication.models import Company

TEXTE_LEGAL = (
    'Garantie constructeur : non renseignée — garantie légale de conformité '
    '12 mois (loi 31-08) jusqu\'au 15/03/2028')


class _Base(TestCase):
    def setUp(self):
        self.co, _ = Company.objects.get_or_create(
            slug='agr622-co', defaults={'nom': 'AGR622 Co'})
        self.cli = Client.objects.create(
            company=self.co, nom='Ferme', prenom='AGR622',
            email='agr622-client@example.invalid')
        self.inst = Installation.objects.create(
            company=self.co, reference='CHT-AGR622', client=self.cli,
            type_installation='agricole', date_pose_reelle='2027-03-15')

    def _pompe(self, nom='Pompe immergée 4 CV', garantie_mois=None,
               garantie=''):
        return Produit.objects.create(
            company=self.co, nom=nom, sku=f'P-{nom[:12]}',
            prix_vente=Decimal('5000'), prix_achat=Decimal('3210.98'),
            garantie_mois=garantie_mois, garantie=garantie)


class HorlogeGarantieTests(_Base):
    def test_garantie_vide_legale_court(self):
        produit = self._pompe()
        eq = Equipement.objects.create(
            company=self.co, produit=produit, installation=self.inst,
            date_pose=date(2027, 3, 15))
        eq.recompute_garanties()
        self.assertIsNone(eq.date_fin_garantie)
        self.assertEqual(eq.date_fin_garantie_legale, date(2028, 3, 15))


@patch('apps.ventes.utils.pdf._download', return_value=None)
@patch('apps.documents.builders._html_to_pdf')
class DossierRemiseTests(_Base):
    def _html(self, mock_pdf):
        from apps.documents import builders
        mock_pdf.return_value = b'%PDF-fake'
        builders.generate_dossier_remise(self.inst)
        # Le gabarit échappe l'apostrophe (« jusqu&#x27;au ») : on compare le
        # TEXTE rendu, pas sa forme HTML échappée.
        return unescape(mock_pdf.call_args[0][0])

    def test_texte_exact_sans_garantie_constructeur(self, mock_pdf, _dl):
        produit = self._pompe()
        eq = Equipement.objects.create(
            company=self.co, produit=produit, installation=self.inst,
            numero_serie='SN-AGR622-1', date_pose=date(2027, 3, 15))
        eq.recompute_garanties()
        eq.save()
        html = self._html(mock_pdf)
        self.assertIn(TEXTE_LEGAL, html)
        self.assertNotIn('3210.98', html)
        # Garde : aucune durée du thème résidentiel (WARRANTIES) dans la
        # remise d'un chantier agricole.
        for n, u, _label, _sub in WARRANTIES:
            self.assertNotIn(f'{n} {u}', html)


class AuditCommandeTests(_Base):
    def test_liste_pompe_24_mois_texte_vide_sans_ecrire(self):
        pompe = self._pompe(garantie_mois=24, garantie='')
        variateur = self._pompe(
            nom='Variateur VEICHI 5,5 kW', garantie_mois=None,
            garantie='')
        panneau = Produit.objects.create(
            company=self.co, nom='Panneau 710 W', sku='PAN-AGR622',
            prix_vente=Decimal('1000'), garantie_mois=144,
            garantie='')
        avant = list(Produit.objects.order_by('id').values_list(
            'id', 'garantie_mois', 'garantie'))
        nb_avant = Produit.objects.count()

        lignes = audit_garanties_pompage('agr622-co')
        par_id = {ligne['produit_id']: ligne for ligne in lignes}
        self.assertIn(pompe.id, par_id)
        self.assertEqual(par_id[pompe.id]['garantie_mois'], 24)
        self.assertEqual(par_id[pompe.id]['signaux'], [SIGNAL_SANS_SOURCE])
        self.assertIn(variateur.id, par_id)
        self.assertEqual(par_id[variateur.id]['signaux'], [])
        self.assertNotIn(panneau.id, par_id)

        out = StringIO()
        call_command('audit_garanties_pompage', company_slug='agr622-co',
                     stdout=out)
        sortie = out.getvalue()
        self.assertIn(SIGNAL_SANS_SOURCE, sortie)
        self.assertIn('Aucune ligne modifiée', sortie)
        self.assertNotIn('3210.98', sortie)
        self.assertEqual(Produit.objects.count(), nb_avant)
        self.assertEqual(list(Produit.objects.order_by('id').values_list(
            'id', 'garantie_mois', 'garantie')), avant)
