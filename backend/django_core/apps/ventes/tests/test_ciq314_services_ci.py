"""CIQ314 — O&M, suivi de production et garanties : le document C&I ne
promet que ce que le devis porte (D-CIQ-12).

Rendu RÉEL des deux gabarits sur la charge utile du builder
(``build_quote_data`` → ``echapper_textes_client`` → ``_augment`` →
``build_html``), devis créés en base avec ou sans ligne au rôle ``om_ci``.
"""
from decimal import Decimal

from django.test import TestCase

from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_user,
)

LIGNES = [
    ('Panneau mono 450W', '40', '1500'),
    ('Onduleur réseau 20 kW', '1', '30000'),
]
INTERDITS = ('O&amp;M', 'O&M', 'upervision', 'performance garantie',
             'engagement de performance')


def _module(mode):
    if mode == 'commercial':
        from apps.ventes.quote_engine.commercial import render, renderer
    else:
        from apps.ventes.quote_engine.industriel import render, renderer
    return render, renderer


def _page_confiance(html, mode):
    racine = 'c3-root' if mode == 'commercial' else 'i3-root'
    return html[html.index(f'class="{racine}"'):]


class ServicesCi(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self._n = 0

    def _devis(self, mode, om=None):
        from apps.stock.models import Produit
        from apps.ventes.models import LigneDevis
        self._n += 10
        devis = make_devis(self.company, self.user, self.client_obj, LIGNES,
                           reference=f'DEV-CIQ314-{self._n:04d}')
        devis.mode_installation = mode
        devis.save(update_fields=['mode_installation'])
        if om is not None:
            produit = Produit.objects.create(
                company=self.company, nom='Contrat O&M annuel',
                sku=f'OM-{self._n}', prix_vente=Decimal(om),
                prix_achat=Decimal('0'), quantite_stock=0, role_ci='om_ci')
            LigneDevis.objects.create(
                devis=devis, produit=produit,
                designation='Contrat O&M : nettoyages, inspection',
                quantite=Decimal('1'), prix_unitaire=Decimal(om),
                remise=Decimal('0'), ordre=99)
        return devis

    def _rendu(self, devis, mode):
        from apps.ventes.quote_engine.builder import (
            build_quote_data, echapper_textes_client,
        )
        render, renderer = _module(mode)
        data = build_quote_data(devis, {'pdf_mode': 'full'})
        d = renderer._augment(echapper_textes_client(data))
        return d, render.build_html(d)

    def test_sans_ligne_om_aucune_promesse(self):
        for mode in ('commercial', 'industriel'):
            with self.subTest(mode=mode):
                d, html = self._rendu(self._devis(mode), mode)
                page = _page_confiance(html, mode)
                for mot in INTERDITS:
                    self.assertNotIn(mot, page)
                synthese = d.get('com_synthese') or d.get('ind_synthese')
                self.assertNotIn('om_option', synthese['services'])
                self.assertNotIn('suivi_production', synthese['services'])

    def test_ligne_om_sans_prix_a_renseigner(self):
        for mode in ('commercial', 'industriel'):
            with self.subTest(mode=mode):
                d, html = self._rendu(self._devis(mode, om='0'), mode)
                page = _page_confiance(html, mode)
                self.assertIn('prix à renseigner', page)
                self.assertIn('Contrat O&amp;M : nettoyages, inspection',
                              page)
                synthese = d.get('com_synthese') or d.get('ind_synthese')
                self.assertEqual(synthese['services']['om_option']['statut'],
                                 'tarif_a_renseigner')

    def test_ligne_om_prix_saisi(self):
        d, html = self._rendu(self._devis('commercial', om='4800'),
                              'commercial')
        page = _page_confiance(html, 'commercial')
        self.assertIn('MAD HT', page)
        self.assertNotIn('prix à renseigner', page)
        self.assertEqual(
            d['com_synthese']['services']['om_option']['statut'], 'souscrit')

    def test_delai_saisi_imprime_sinon_omis(self):
        from apps.parametres.models_company import CompanyProfile
        profil, _ = CompanyProfile.objects.get_or_create(company=self.company)
        for mode in ('commercial', 'industriel'):
            with self.subTest(mode=mode, delai=None):
                profil.delai_intervention_suivi_heures = None
                profil.save()
                _d, html = self._rendu(self._devis(mode), mode)
                self.assertNotIn('intervention sous', html)
            with self.subTest(mode=mode, delai=48):
                profil.delai_intervention_suivi_heures = 48
                profil.save()
                _d, html = self._rendu(self._devis(mode), mode)
                self.assertIn('intervention sous 48&#160;h', html)

    def test_garanties_du_fabricant(self):
        d, _html = self._rendu(self._devis('industriel'), 'industriel')
        for garantie in d['ind_synthese']['services']['garanties']:
            self.assertEqual(garantie['source'], 'garantie du fabricant')
            self.assertNotEqual(garantie['composant'], 'installation')
