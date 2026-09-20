"""CAL39 — tout enregistrement de layout VENTES alimente le calepinage.

Ce qui est prouvé ici :

* le module s'abonne RÉELLEMENT à ``layout_finalise`` dans ``apps.py``
  ``ready()`` (pas seulement dans un fichier jamais chargé) ;
* les TROIS chemins d'enregistrement de ventes alimentent
  ``Calepinage.roof_layout`` + ``layout_hash``, avec l'auteur et la société
  posés CÔTÉ SERVEUR ;
* l'action « best-effort » ``POST /ventes/devis/<id>/layout/`` pose désormais
  ``layout_hash`` et émet l'événement — c'était le chemin muet ;
* le miroir est IDEMPOTENT (le même devis rend toujours le même calepinage) et
  n'écrit AUCUN statut ;
* un abonné en échec ne fait PAS échouer l'enregistrement du devis.

Run :
    python manage.py test apps.calepinage.tests.test_miroir_layout_ventes -v2
"""
from unittest import mock

from core import events

from apps.calepinage.models import Calepinage
from apps.crm.models import Client, Lead
from apps.ventes.models import Devis

from .test_api_liste import BaseApiCalepinage

LAYOUT = {'schema_version': 2, 'result': {'panels': 12, 'kwc': 8.64}}
LAYOUT_2 = {'schema_version': 2, 'result': {'panels': 14, 'kwc': 10.08}}


class MiroirLayoutTest(BaseApiCalepinage):
    def setUp(self):
        super().setUp()
        self.client_lie = Client.objects.create(company=self.company,
                                                nom='Bâtiment Atlas 39')
        self.lead_lie = Lead.objects.create(company=self.company,
                                            nom='Toiture Anfa 39')
        self.devis = Devis.objects.create(
            company=self.company, client=self.client_lie, lead=self.lead_lie,
            reference='DEV-202609-3939')

    def _calepinage(self):
        return Calepinage.objects.filter(company=self.company,
                                         devis=self.devis).first()

    def test_le_module_est_abonne_dans_ready(self):
        from django.apps import apps as registre

        config = registre.get_app_config('calepinage')
        self.assertTrue(hasattr(config, 'ready'))
        recepteurs = [r for _, r in events.layout_finalise.receivers]
        self.assertTrue(recepteurs, "aucun abonné à layout_finalise")

    def test_evenement_alimente_le_calepinage(self):
        self.devis.roof_layout = LAYOUT
        self.devis.save(update_fields=['roof_layout'])
        events.layout_finalise.send(sender='test', devis=self.devis,
                                    user=self.user)
        calepinage = self._calepinage()
        self.assertIsNotNone(calepinage)
        self.assertEqual(calepinage.roof_layout, LAYOUT)
        self.assertEqual(len(calepinage.layout_hash), 64)
        self.assertEqual(calepinage.company_id, self.company.pk)
        self.assertEqual(calepinage.cree_par_id, self.user.pk)

    def test_miroir_idempotent_et_suit_les_changements(self):
        self.devis.roof_layout = LAYOUT
        self.devis.save(update_fields=['roof_layout'])
        events.layout_finalise.send(sender='test', devis=self.devis,
                                    user=self.user)
        premier = self._calepinage()
        self.devis.roof_layout = LAYOUT_2
        self.devis.save(update_fields=['roof_layout'])
        events.layout_finalise.send(sender='test', devis=self.devis,
                                    user=self.user)
        self.assertEqual(
            Calepinage.objects.filter(devis=self.devis).count(), 1)
        premier.refresh_from_db()
        self.assertEqual(premier.roof_layout, LAYOUT_2)
        # L'historique a suivi : deux enregistrements significatifs.
        self.assertEqual(premier.versions.count(), 2)

    def test_aucun_statut_n_est_ecrit(self):
        statut_devis = self.devis.statut
        self.devis.roof_layout = LAYOUT
        self.devis.save(update_fields=['roof_layout'])
        events.layout_finalise.send(sender='test', devis=self.devis,
                                    user=self.user)
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, statut_devis)
        self.assertEqual(self._calepinage().statut,
                         Calepinage.Statut.BROUILLON)

    def test_action_layout_de_ventes_pose_l_empreinte_et_emet(self):
        url = f'/api/django/ventes/devis/{self.devis.pk}/layout/'
        reponse = self.api.post(url, LAYOUT, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.roof_layout, LAYOUT)
        self.assertEqual(len(self.devis.layout_hash), 64)
        calepinage = self._calepinage()
        self.assertIsNotNone(calepinage, "le chemin muet n'alimente toujours "
                                         "pas le calepinage")
        self.assertEqual(calepinage.layout_hash, self.devis.layout_hash)

    def test_un_abonne_en_echec_ne_casse_pas_l_enregistrement(self):
        url = f'/api/django/ventes/devis/{self.devis.pk}/layout/'
        with mock.patch('apps.calepinage.services.creation'
                        '.obtenir_ou_creer_pour_devis',
                        side_effect=RuntimeError('miroir cassé')):
            reponse = self.api.post(url, LAYOUT, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.roof_layout, LAYOUT)
