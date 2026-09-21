"""NTHOT19 — BEO (Banquet Event Order) imprimable.

Done = le BEO généré contient toutes les sections requises et se régénère si
les détails de l'événement changent, tests.
"""
from django.test import TestCase

from apps.hospitality.models import EvenementBanquet, Recette, SalleEvenement
from apps.hospitality.pdf import render_beo_html

from .helpers import auth, make_company, make_user


class RenderBeoHtmlTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client

        self.co = make_company('hot-beo', 'Hôtel')
        self.client_crm = Client.objects.create(
            company=self.co, nom='Famille Alaoui', telephone='0600000000')
        self.salle = SalleEvenement.objects.create(
            company=self.co, nom='Salle Atlas', capacite_max=150,
            types_amenagement_disponibles=['banquet'],
            description='Terrasse privative incluse.')
        self.recette = Recette.objects.create(
            company=self.co, nom_plat='Tagine royal', categorie_menu='plat',
            prix_vente_ht='120', description='Cuisson lente 4h.',
            allergenes=['gluten'])
        self.evenement = EvenementBanquet.objects.create(
            company=self.co, nom_evenement='Mariage Alaoui',
            client=self.client_crm, salle=self.salle, nb_convives=120,
            date_debut='2026-09-01T10:00:00Z', date_fin='2026-09-01T23:00:00Z',
        )
        self.evenement.menu_recettes.add(self.recette)

    def test_contient_toutes_les_sections_requises(self):
        html = render_beo_html(self.evenement)
        for section in (
                'Horaire détaillé', 'Plan de salle', 'Menu choisi',
                'Prestations annexes', 'Contact client', 'Notes cuisine'):
            self.assertIn(section, html)

    def test_contient_le_menu_choisi_et_ses_allergenes(self):
        html = render_beo_html(self.evenement)
        self.assertIn('Tagine royal', html)
        self.assertIn('gluten', html)

    def test_contient_le_plan_de_salle(self):
        html = render_beo_html(self.evenement)
        self.assertIn('Salle Atlas', html)
        self.assertIn('Terrasse privative', html)

    def test_contient_le_contact_client(self):
        html = render_beo_html(self.evenement)
        self.assertIn('Famille Alaoui', html)
        self.assertIn('0600000000', html)

    def test_se_regenere_si_le_menu_change(self):
        html_avant = render_beo_html(self.evenement)
        self.assertNotIn('Couscous royal', html_avant)
        autre_plat = Recette.objects.create(
            company=self.co, nom_plat='Couscous royal', prix_vente_ht='90')
        self.evenement.menu_recettes.add(autre_plat)
        html_apres = render_beo_html(self.evenement)
        self.assertIn('Couscous royal', html_apres)

    def test_sans_salle_ni_menu_reste_sans_erreur(self):
        vide = EvenementBanquet.objects.create(
            company=self.co, nom_evenement='Sans détails',
            date_debut='2026-10-01T10:00:00Z', date_fin='2026-10-01T22:00:00Z',
        )
        html = render_beo_html(vide)
        self.assertIn('Non assignée', html)
        self.assertIn('Aucun plat sélectionné', html)


class BeoPdfApiTests(TestCase):
    def setUp(self):
        self.co = make_company('hot-beo-api', 'Hôtel')
        self.user = make_user(self.co, 'hot-beo-api-user')
        self.evenement = EvenementBanquet.objects.create(
            company=self.co, nom_evenement='Anniversaire',
            date_debut='2026-09-01T10:00:00Z', date_fin='2026-09-01T22:00:00Z',
        )

    def test_endpoint_repond_pdf_ou_indisponible_proprement(self):
        resp = auth(self.user).get(
            f'/api/django/hospitality/evenements/{self.evenement.pk}/beo-pdf/')
        self.assertIn(resp.status_code, (200, 503))
        if resp.status_code == 200:
            self.assertEqual(resp['Content-Type'], 'application/pdf')
