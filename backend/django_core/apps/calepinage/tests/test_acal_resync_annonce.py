"""ACAL38 (D-ACAL-1, C-ACAL-109) — « Resynchroniser le devis » depuis le module
annonce ENFIN ``layout_finalise``, UNE fois, sans rien réécrire du calepinage.

Catalogue tarifé réel, HTTP réel ; l'abonné crm (note au chatter du lead) est
le VRAI récepteur ; seul un compteur d'émissions est branché sur le signal.

Run :
    python manage.py test apps.calepinage.tests.test_acal_resync_annonce -v2
"""
import copy
from decimal import Decimal

from core import events

from apps.calepinage.models import Calepinage, CalepinageVersion
from apps.calepinage.services.layout import enregistrer_layout

from .test_api_liste import BaseApiCalepinage, url_detail

TOIT = {
    'areas': [{'vertices': [[0, 0], [10, 0], [10, 6], [0, 6]],
               'obstacles': [], 'roofType': 'flat', 'pitch': 10,
               'azimuth': 180}],
    'scenario': 'reseau',
    'result': {'panels': 12, 'kwc': 6.6, 'annualKwh': 10800, 'savings': 9200},
}


class ResyncAnnonceTest(BaseApiCalepinage):
    def setUp(self):
        super().setUp()
        from apps.ventes.tests.test_from_layout_endpoint import seed_catalogue
        seed_catalogue(self.company)
        # ACAL922 — lead DIMENSIONNÉ : « Générer » ne pose pas la question.
        self.lead.taille_souhaitee_kwc = Decimal('5')
        self.lead.save(update_fields=['taille_souhaitee_kwc'])
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='ACAL38')
        enregistrer_layout(self.calepinage, copy.deepcopy(TOIT),
                           user=self.user)
        self.base = url_detail(self.calepinage.pk)
        reponse = self.api.post(f'{self.base}generer-devis/', {},
                                format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.emissions = []

        def compter(sender, devis=None, **kwargs):
            self.emissions.append(getattr(devis, 'pk', None))
        self._compteur = compter
        events.layout_finalise.connect(compter, weak=False,
                                       dispatch_uid='acal38_compteur')

    def tearDown(self):
        events.layout_finalise.disconnect(dispatch_uid='acal38_compteur')
        super().tearDown()

    def test_resync_module_emet_layout_finalise_une_fois_sans_version(self):
        modifie = copy.deepcopy(TOIT)
        modifie['result']['panels'] = 14
        enregistrer_layout(self.calepinage, modifie, user=self.user)
        self.calepinage.refresh_from_db()
        document_avant = copy.deepcopy(self.calepinage.roof_layout)
        versions_avant = CalepinageVersion.objects.filter(
            calepinage=self.calepinage).count()

        reponse = self.api.post(f'{self.base}sync-devis/', {}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)

        self.assertEqual(len(self.emissions), 1)
        self.assertEqual(self.emissions[0], self.calepinage.devis_id)
        self.calepinage.refresh_from_db()
        # Aucune version déposée par la resynchro, aucun document réécrit.
        self.assertEqual(CalepinageVersion.objects.filter(
            calepinage=self.calepinage).count(), versions_avant)
        self.assertEqual(self.calepinage.roof_layout, document_avant)
        self.assertNotIn('_pans_geometry', self.calepinage.roof_layout)

    # ── Lane E6e, item 3 (T4-X5-010) — le devis né de l'atelier et l'onduleur désigné ──
    def _designer(self, nom):
        from apps.calepinage.services.electrique import CLE_ENTREE
        from apps.stock.models import Produit

        produit = Produit.objects.get(company=self.company, nom=nom)
        self.calepinage.refresh_from_db()
        resultat = dict(self.calepinage.resultat or {}, **{CLE_ENTREE: {'onduleur_produit': produit.pk}})
        Calepinage.objects.filter(pk=self.calepinage.pk).update(resultat=resultat)
        self.calepinage.refresh_from_db()
        return produit

    def test_e6e_devis_genere_porte_l_onduleur_du_scenario_pas_le_designe(self):
        """ÉTABLIT ce que fait « Générer le devis » d'un onduleur HYBRIDE désigné sur une pose
        « réseau » : le devis chiffre l'onduleur RÉSEAU du catalogue. Le fondateur n'a pas
        tranché la règle : ce test fige le constat, il ne l'invente pas."""
        from apps.ventes.models import Devis

        Devis.objects.filter(pk=self.calepinage.devis_id).update(is_active=False)
        Calepinage.objects.filter(pk=self.calepinage.pk).update(devis=None)
        modifie = copy.deepcopy(TOIT)
        modifie['result']['panels'] = 10  # une autre pose : aucun brouillon à la même empreinte
        self.calepinage.refresh_from_db()
        enregistrer_layout(self.calepinage, modifie, user=self.user)
        self._designer('Onduleur hybride Deye 5kW Monophasé')
        reponse = self.api.post(f'{self.base}generer-devis/', {'creer_autre_devis': True}, format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        devis = Devis.objects.get(pk=Calepinage.objects.get(pk=self.calepinage.pk).devis_id)
        onduleurs = [li.designation for li in devis.lignes.all() if 'nduleur' in li.designation]
        self.assertEqual(onduleurs, ['Onduleur réseau Huawei 5kW Monophasé'], onduleurs)

    def test_e6e_resynchro_refusee_pour_un_onduleur_non_designe_dit_l_issue(self):
        """Le refus de « Resynchroniser » qui juge l'onduleur du DEVIS alors qu'un autre est
        désigné à l'étape Électrique le dit, nomme les deux et propose le geste qui existe :
        désigner à l'étape Électrique l'onduleur du devis. Rien n'est écrit."""
        from unittest import mock

        from apps.ventes.services import SyncLayoutError

        self._designer('Onduleur hybride Deye 5kW Monophasé')
        refus = SyncLayoutError("7 panneaux « P » sont incompatibles avec « Onduleur réseau Huawei 5kW "
                                "Monophasé » : Isc. Corrigez le nombre de panneaux ou changez d'onduleur — le "
                                "devis n'a pas été modifié.", revision_possible=False)
        with mock.patch('apps.ventes.services.resynchroniser_conception', side_effect=refus):
            reponse = self.api.post(f'{self.base}sync-devis/', {}, format='json')
        self.assertEqual(reponse.status_code, 409, reponse.data)
        self.assertTrue(str(reponse.data['detail']).endswith(
            " L'étape Électrique juge l'onduleur désigné « Onduleur hybride Deye 5kW Monophasé » ; ce devis "
            "porte « Onduleur réseau Huawei 5kW Monophasé », c'est lui que ce refus juge. Pour aligner les "
            "deux, désignez « Onduleur réseau Huawei 5kW Monophasé » à l'étape Électrique (Matériel "
            "électrique), puis resynchronisez."), reponse.data)
        self.assertEqual(self.emissions, [])

    def test_e6e_resynchro_refusee_onduleur_designe_inchangee(self):
        """Le devis porte l'onduleur désigné : le refus reste celui du serveur, mot pour mot."""
        from unittest import mock

        from apps.ventes.services import SyncLayoutError

        self._designer('Onduleur réseau Huawei 5kW Monophasé')
        with mock.patch('apps.ventes.services.resynchroniser_conception',
                        side_effect=SyncLayoutError('Refus du serveur.', revision_possible=False)):
            reponse = self.api.post(f'{self.base}sync-devis/', {}, format='json')
        self.assertEqual((reponse.status_code, str(reponse.data['detail'])), (409, 'Refus du serveur.'))
