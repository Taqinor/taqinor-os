"""AGR621 — étiquette SAV publique du coffret : téléphone de la société et
référence du chantier.

Run :
    python manage.py test apps.sav.tests_agr621_etiquette_sav -v 2
"""
from django.test import TestCase

from apps.parametres.models import CompanyProfile
from apps.stock.labels import render_labels_html
from apps.sav.tests_fg81_fg90 import (
    auth, make_company, make_equipement, make_installation, make_produit,
    make_user,
)

URL = '/api/django/sav/equipements/etiquettes/'


class EtiquetteSavTests(TestCase):
    def setUp(self):
        self.co = make_company(slug='agr621-co', nom='AGR621 Co')
        self.user = make_user(self.co, username='agr621_admin')
        self.api = auth(self.user)
        self.inst, _client = make_installation(self.co, ref='CHT-AGR621')
        produit = make_produit(self.co, nom='Pompe AGR621', sku='PMP-AGR621')
        self.eq = make_equipement(
            self.co, self.user, produit, self.inst, serie='SN-AGR621')

    def _html(self, params):
        r = self.api.get(URL, {'ids': str(self.eq.id), **params})
        self.assertEqual(r.status_code, 200)
        return r.content.decode('utf-8')

    def test_etiquette_publique_telephone_et_reference(self):
        profil = CompanyProfile.get(company=self.co)
        profil.telephone = '+212 5 22 00 00 00'
        profil.save()
        html = self._html({'public': '1'})
        self.assertIn('SAV : +212 5 22 00 00 00 · Chantier CHT-AGR621', html)
        self.assertNotIn('délai', html.lower())

    def test_telephone_vide_partie_omise(self):
        profil = CompanyProfile.get(company=self.co)
        profil.telephone = ''
        profil.save()
        html = self._html({'public': '1'})
        self.assertNotIn('SAV :', html)
        self.assertIn('<div class="pied">Chantier CHT-AGR621</div>', html)

    def test_etiquette_interne_octet_identique(self):
        profil = CompanyProfile.get(company=self.co)
        profil.telephone = '+212 5 22 00 00 00'
        profil.save()
        html = self._html({})
        self.assertNotIn('class="pied"', html)
        self.assertNotIn('.pied', html)
        token = self.eq.equipement_token or f'EQUIP:{self.eq.pk}'
        attendu = render_labels_html([{
            'token': token, 'titre': 'Pompe AGR621',
            'sous_titre': 'SN-AGR621'}])
        self.assertEqual(html, attendu)

    def test_render_sans_pied_identique(self):
        items = [{'token': 'EQUIP:1', 'titre': 'A', 'sous_titre': 'B'}]
        self.assertEqual(
            render_labels_html(items),
            render_labels_html([dict(items[0], pied='')]))
