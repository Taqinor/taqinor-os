"""CAL25 — « Resynchroniser le devis » depuis un calepinage.

Ce qui est prouvé ici :

* un devis `brouillon` se resynchronise par le service VENTES (aucun second
  chemin de resynchronisation) ;
* un devis `envoye` rend 409 avec ``revision_possible: true`` INCHANGÉ, un
  devis accepté 409 avec ``false`` : le comportement du serveur ventes se
  propage tel quel, ni traduit ni adouci ;
* sans devis lié, le refus NOMME le geste à faire (« Générer le devis ») ;
* un calepinage d'une autre société est introuvable (404).

Run :
    python manage.py test apps.calepinage.tests.test_api_sync_devis -v2
"""
from unittest import mock

from apps.calepinage.models import Calepinage
from apps.crm.models import Client, Lead
from apps.ventes.models import Devis

from .test_api_liste import BaseApiCalepinage, url_detail

LAYOUT = {'schema_version': 2, 'result': {'panels': 14, 'kwc': 10.08}}


def url_sync(pk):
    return f'{url_detail(pk)}sync-devis/'


class SyncDevisTest(BaseApiCalepinage):
    def setUp(self):
        super().setUp()
        self.client_lie = Client.objects.create(company=self.company,
                                                nom='Bâtiment Atlas 25')
        self.lead_lie = Lead.objects.create(company=self.company,
                                            nom='Toiture Anfa 25')
        self.devis = Devis.objects.create(
            company=self.company, client=self.client_lie, lead=self.lead_lie,
            reference='DEV-202609-2525')
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead_lie.pk, devis=self.devis,
            titre='Villa Anfa', roof_layout=LAYOUT, layout_hash='d' * 64)

    def test_brouillon_resynchronise(self):
        attendu = {'inchange': False, 'lignes_ajoutees': 2,
                   'avertissements': []}
        with mock.patch('apps.ventes.services.sync_devis_from_layout',
                        return_value=attendu) as sync:
            reponse = self.api.post(url_sync(self.calepinage.pk), {},
                                    format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data, attendu)
        self.assertEqual(sync.call_args.args[0].pk, self.devis.pk)
        self.assertEqual(sync.call_args.args[1], LAYOUT)
        self.assertEqual(sync.call_args.args[2], self.user)

    def _refus_409(self, revision_possible):
        from apps.ventes.services import SyncLayoutError

        return SyncLayoutError('Devis envoyé : révisez-le.',
                               revision_possible=revision_possible)

    def test_devis_envoye_rend_409_revision_possible_vrai(self):
        with mock.patch('apps.ventes.services.sync_devis_from_layout',
                        side_effect=self._refus_409(True)):
            reponse = self.api.post(url_sync(self.calepinage.pk), {},
                                    format='json')
        self.assertEqual(reponse.status_code, 409)
        self.assertTrue(reponse.data['revision_possible'])
        self.assertEqual(reponse.data['detail'], 'Devis envoyé : révisez-le.')

    def test_devis_accepte_rend_409_revision_possible_faux(self):
        with mock.patch('apps.ventes.services.sync_devis_from_layout',
                        side_effect=self._refus_409(False)):
            reponse = self.api.post(url_sync(self.calepinage.pk), {},
                                    format='json')
        self.assertEqual(reponse.status_code, 409)
        self.assertFalse(reponse.data['revision_possible'])

    def test_sans_devis_lie_le_refus_nomme_le_geste(self):
        nu = Calepinage.objects.create(
            company=self.company, lead_id=self.lead_lie.pk, titre='Nu',
            roof_layout=LAYOUT, layout_hash='e' * 64)
        reponse = self.api.post(url_sync(nu.pk), {}, format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('devis', reponse.data)
        self.assertIn('Générer le devis', str(reponse.data['devis']))

    def test_autre_societe_introuvable(self):
        etranger = Calepinage.objects.create(
            company=self.autre, lead_id=4, titre='Chez la voisine')
        reponse = self.api.post(url_sync(etranger.pk), {}, format='json')
        self.assertEqual(reponse.status_code, 404)

    def test_sans_permission_d_ecriture_403(self):
        reponse = self.api_sans.post(url_sync(self.calepinage.pk), {},
                                     format='json')
        self.assertEqual(reponse.status_code, 403)
