"""NTMIG19 — PV de migration (synthèse par lot, exportable en PDF).

Le PV doit lister TOUS les lots avec leur statut de conformité ET les
dérogations éventuelles : c'est la pièce remise au grand compte, elle ne doit
jamais laisser croire à une migration propre là où un écart a été dérogé.

Le contenu est testé sur le HTML (gate rapide, sans WeasyPrint) ; le rendu PDF
réel est couvert à part, étiqueté @tag('pdf').
"""
from django.test import TestCase, tag
from django.utils import timezone

from apps.migration.models import (
    LotMigration, ProjetMigration, RapportReconciliation)
from apps.migration.pdf_rapport import render_rapport_migration_html

from ._base import auth, make_admin, make_company


class RapportContenuTests(TestCase):
    def setUp(self):
        self.company = make_company('mig-g19-co', 'Migr G19')
        self.user = make_admin(self.company, 'mig-g19-admin')
        self.projet = ProjetMigration.objects.create(
            company=self.company, nom='Client E', source='odoo')
        # Lot conforme.
        self.lot_ok = LotMigration.objects.create(
            company=self.company, projet=self.projet, entite='clients',
            source_lignes=10, crees=10)
        RapportReconciliation.objects.create(
            company=self.company, lot=self.lot_ok, nb_source=10,
            nb_cible_crees=10, conforme=True)
        # Lot avec écarts + dérogation motivée.
        self.lot_derog = LotMigration.objects.create(
            company=self.company, projet=self.projet, entite='products',
            source_lignes=5, crees=3, erreurs=2,
            derogation_reconcile=True, derogation_motif='SKU manquants OK',
            derogation_par=self.user, derogation_at=timezone.now())
        RapportReconciliation.objects.create(
            company=self.company, lot=self.lot_derog, nb_source=5,
            nb_cible_crees=3, nb_erreurs=2,
            ecarts=[{'type': 'erreurs', 'detail': '2 lignes en erreur.'}],
            conforme=False)

    def test_liste_tous_les_lots_avec_leur_conformite(self):
        html = render_rapport_migration_html(self.projet)
        self.assertIn('Client E', html)
        self.assertIn('clients', html)
        self.assertIn('products', html)
        self.assertIn('Conforme', html)

    def test_une_derogation_est_visible_avec_son_motif_et_son_auteur(self):
        """Un écart dérogé ne doit JAMAIS passer pour un lot propre."""
        html = render_rapport_migration_html(self.projet)
        self.assertIn('Dérogé', html)
        self.assertIn('SKU manquants OK', html)
        self.assertIn('mig-g19-admin', html)
        self.assertIn('2 lignes en erreur.', html)
        self.assertIn('1 dérogation(s)', html)

    def test_lot_sans_rapport_marque_non_reconcilie(self):
        LotMigration.objects.create(
            company=self.company, projet=self.projet, entite='fournisseurs')
        html = render_rapport_migration_html(self.projet)
        self.assertIn('Non réconcilié', html)

    def test_totaux_financiers_rendus_quand_connus(self):
        lot = LotMigration.objects.create(
            company=self.company, projet=self.projet, entite='devis')
        RapportReconciliation.objects.create(
            company=self.company, lot=lot, nb_source=2,
            total_financier_source='1000.00', total_financier_cible='940.00',
            conforme=False, ecarts=[{'type': 'financier'}])
        html = render_rapport_migration_html(self.projet)
        self.assertIn('1000.00 MAD', html)
        self.assertIn('940.00 MAD', html)
        # L'écart est calculé, pas saisi.
        self.assertIn('-60.00 MAD', html)

    def test_projet_sans_lot_ne_casse_pas(self):
        vide = ProjetMigration.objects.create(
            company=self.company, nom='Vide', source='excel')
        html = render_rapport_migration_html(vide)
        self.assertIn('Aucun lot.', html)

    def test_nom_de_projet_echappe(self):
        piege = ProjetMigration.objects.create(
            company=self.company, nom='<script>x</script>', source='excel')
        html = render_rapport_migration_html(piege)
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)


@tag('pdf')
class RapportPdfEndpointTests(TestCase):
    def setUp(self):
        self.company = make_company('mig-g19pdf-co', 'Migr G19 PDF')
        self.admin = make_admin(self.company, 'mig-g19pdf-admin')
        self.projet = ProjetMigration.objects.create(
            company=self.company, nom='Client F', source='sage')
        LotMigration.objects.create(
            company=self.company, projet=self.projet, entite='clients',
            source_lignes=1, crees=1)

    def test_endpoint_renvoie_un_pdf(self):
        resp = auth(self.admin).get(
            f'/api/django/migration/projets-migration/{self.projet.pk}/'
            'rapport/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertTrue(resp.content.startswith(b'%PDF'))

    def test_pv_dune_autre_societe_est_404(self):
        autre_co = make_company('mig-g19pdf-autre', 'Autre')
        autre_admin = make_admin(autre_co, 'mig-g19pdf-autre-admin')
        resp = auth(autre_admin).get(
            f'/api/django/migration/projets-migration/{self.projet.pk}/'
            'rapport/')
        self.assertEqual(resp.status_code, 404)
