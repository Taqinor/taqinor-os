"""APAR11 — enregistrer le profil société ne vide plus que le PDF en cache des
BROUILLONS, et seulement si un champ d'identité imprimé change ; jamais celui
d'un devis accepté / d'une facture émise, jamais d'une autre société
(C-APAR-013 volet signal)."""
from decimal import Decimal

from django.apps import apps
from django.test import TestCase

from apps.parametres.models import CompanyProfile
from authentication.models import Company


def _m(label, name):
    return apps.get_model(label, name)


class CachePdfBrouillonsTests(TestCase):
    def setUp(self):
        Client = _m('crm', 'Client')
        Devis = _m('ventes', 'Devis')
        Facture = _m('facturation', 'Facture')
        self.co = Company.objects.create(nom='APAR11 Co', slug='apar11-co')
        self.autre = Company.objects.create(nom='APAR11 B', slug='apar11-b')
        self.profile = CompanyProfile.get(company=self.co)
        CompanyProfile.get(company=self.autre)
        cli = Client.objects.create(company=self.co, nom='Client APAR11')
        cli_b = Client.objects.create(company=self.autre, nom='Client B')
        self.devis_accepte = Devis.objects.create(
            company=self.co, client=cli, reference='DEV-APAR11-0001',
            statut='accepte', taux_tva=Decimal('20'),
            fichier_pdf='devis/1/probe.pdf')
        self.devis_brouillon = Devis.objects.create(
            company=self.co, client=cli, reference='DEV-APAR11-0002',
            statut='brouillon', taux_tva=Decimal('20'),
            fichier_pdf='devis/1/brouillon.pdf')
        self.facture_emise = Facture.objects.create(
            company=self.co, client=cli, reference='FAC-APAR11-0001',
            devis=self.devis_accepte, statut='emise', taux_tva=Decimal('20'),
            fichier_pdf='factures/1/probe.pdf')
        self.facture_brouillon = Facture.objects.create(
            company=self.co, client=cli, reference='FAC-APAR11-0002',
            statut='brouillon', taux_tva=Decimal('20'),
            fichier_pdf='factures/1/brouillon.pdf')
        self.devis_autre = Devis.objects.create(
            company=self.autre, client=cli_b, reference='DEV-APAR11-B001',
            statut='brouillon', taux_tva=Decimal('20'),
            fichier_pdf='devis/43/probe.pdf')

    def _pdf(self, obj):
        return type(obj).objects.get(pk=obj.pk).fichier_pdf

    def _profil(self):
        return CompanyProfile.objects.get(pk=self.profile.pk)

    def test_save_sans_changement_ne_touche_rien(self):
        self._profil().save()
        self.assertEqual(self._pdf(self.devis_accepte), 'devis/1/probe.pdf')
        self.assertEqual(self._pdf(self.facture_emise), 'factures/1/probe.pdf')
        self.assertEqual(
            self._pdf(self.devis_brouillon), 'devis/1/brouillon.pdf')
        self.assertEqual(
            self._pdf(self.facture_brouillon), 'factures/1/brouillon.pdf')

    def test_changer_le_rib_ne_vide_que_les_brouillons(self):
        p = self._profil()
        p.rib = '011 780 0000000000000000 12'
        p.save()
        # Persistance : relire fichier_pdf.
        self.assertEqual(self._pdf(self.devis_accepte), 'devis/1/probe.pdf')
        self.assertEqual(self._pdf(self.facture_emise), 'factures/1/probe.pdf')
        self.assertEqual(self._pdf(self.devis_brouillon), '')
        self.assertEqual(self._pdf(self.facture_brouillon), '')
        # Autre société intacte.
        self.assertEqual(self._pdf(self.devis_autre), 'devis/43/probe.pdf')

    def test_champ_non_imprime_ne_vide_rien(self):
        p = self._profil()
        p.variante_pct = (p.variante_pct or 0) + 1
        p.save()
        self.assertEqual(
            self._pdf(self.devis_brouillon), 'devis/1/brouillon.pdf')
        self.assertEqual(self._pdf(self.devis_accepte), 'devis/1/probe.pdf')

    def test_profil_sans_societe_ne_vide_aucune_societe(self):
        orphelin = CompanyProfile.objects.create(company=None, nom='Orphelin')
        orphelin.nom = 'Orphelin modifié'
        orphelin.save()
        self.assertEqual(
            self._pdf(self.devis_brouillon), 'devis/1/brouillon.pdf')
        self.assertEqual(self._pdf(self.devis_autre), 'devis/43/probe.pdf')
        self.assertEqual(self._pdf(self.facture_emise), 'factures/1/probe.pdf')
