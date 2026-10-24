"""APAR49 (C-APAR-012) — toute entrée serveur de création de devis sans
``taux_tva`` prend le taux STANDARD de la société (``tva_standard``), plus
``Decimal('20')`` codé : pour une société à 14 %, le devis et les lignes sans
taux propre sont à 14 % ; un taux explicite (y compris 0) est respecté.

Sources réelles : ``composer_devis_residentiel``, ``build_devis_from_layout``,
``POST /ventes/devis/composition/`` (catalogue QJR80, produits sans TVA).

Test-du-test : remettre ``Decimal('20')`` comme défaut ⇒
``test_composition_sans_taux_prend_le_taux_societe`` échoue.

APAR80 — ``test_trois_entrees_http_relues_en_base`` : ``/devis/auto/``,
``/composition/`` et ``/from-layout/`` par HTTP, relus en base. Test-du-test :
``Decimal('20')`` au lieu de ``tva_standard(company)`` dans
``DevisViewSet.auto`` ou dans ``DevisCalepinageActionsMixin.from_layout`` ⇒
ce test échoue.
"""
from decimal import Decimal

from rest_framework.test import APIClient

from apps.parametres.models import CompanyProfile
from apps.ventes.domain import creation_auto, creation_calepinage
from apps.ventes.tests import test_qjr_pipeline_composer as qjr80


class TvaDefautSocieteTests(qjr80._Base):
    slug = 'apar49-tva'

    def setUp(self):
        super().setUp()
        profil = CompanyProfile.get(company=self.company)
        CompanyProfile.objects.filter(pk=profil.pk).update(
            tva_standard=Decimal('14'))

    def _taux_composition(self, **kwargs):
        charge = creation_auto.composer_devis_residentiel(
            company=self.company, nb_panneaux=qjr80.NB_PANNEAUX,
            panel_watt=qjr80.PANEL_WATT, scenario='sans', **kwargs)
        return {ligne['taux_tva'] for ligne in charge['lignes']}

    def test_composition_sans_taux_prend_le_taux_societe(self):
        self.assertEqual(self._taux_composition(), {'14'})

    def test_taux_explicite_respecte(self):
        self.assertEqual(self._taux_composition(taux_tva=Decimal('0')), {'0'})

    def test_from_layout_sans_taux(self):
        devis = creation_calepinage.build_devis_from_layout(
            layout=self._layout(), user=self.user, company=self.company,
            lead=self.lead)
        devis.refresh_from_db()
        self.assertEqual(devis.taux_tva, Decimal('14'))

    def test_endpoint_composition_sans_taux(self):
        api = APIClient()
        api.force_authenticate(self.user)
        resp = api.post('/api/django/ventes/devis/composition/',
                        {'nb_panneaux': qjr80.NB_PANNEAUX,
                         'panel_watt': qjr80.PANEL_WATT, 'scenario': 'sans'},
                        format='json')
        self.assertEqual(resp.status_code, 200, resp.content[:300])
        self.assertEqual({li['taux_tva'] for li in resp.json()['lignes']},
                         {'14'})

    def test_trois_entrees_http_relues_en_base(self):
        """APAR80 — sans taux puis à 0 : le devis et chaque ligne produit sans
        ``Produit.tva`` relus EN BASE (``/composition/`` n'écrit rien : ses
        lignes servies). Un lead par appel (dédup layout de from-layout) ;
        boucle sans ``subTest`` (test d'API), la route nommée en message."""
        from apps.crm.models import Lead
        from apps.ventes.models import Devis
        api = APIClient()
        api.force_authenticate(self.user)
        for taux, attendu in ((None, Decimal('14.00')), (0, Decimal('0.00'))):
            extra = {} if taux is None else {'taux_tva': taux}
            for route in ('auto', 'from-layout'):
                lead = Lead.objects.create(
                    company=self.company, nom='Apar80', prenom=route,
                    email='apar80-%s-%s@example.com' % (route, taux))
                corps = ({'target_kwc': qjr80.KWC, 'scenario': 'sans'}
                         if route == 'auto' else {'layout': self._layout()})
                resp = api.post('/api/django/ventes/devis/%s/' % route,
                                dict(corps, lead=lead.id, **extra),
                                format='json')
                self.assertEqual(resp.status_code, 201,
                                 (route, taux, resp.content[:300]))
                devis = Devis.objects.get(pk=resp.json()['id'],
                                          company=self.company, lead=lead)
                self.assertEqual(devis.taux_tva, attendu, (route, taux))
                lignes = devis.lignes.filter(type_ligne='produit',
                                             produit__tva__isnull=True)
                self.assertTrue(lignes.exists(), route)
                self.assertEqual({li.taux_tva for li in lignes}, {attendu},
                                 (route, taux))
            resp = api.post('/api/django/ventes/devis/composition/',
                            dict({'nb_panneaux': qjr80.NB_PANNEAUX,
                                  'panel_watt': qjr80.PANEL_WATT,
                                  'scenario': 'sans'}, **extra),
                            format='json')
            self.assertEqual(resp.status_code, 200, resp.content[:300])
            self.assertEqual({Decimal(li['taux_tva'])
                              for li in resp.json()['lignes']}, {attendu})
