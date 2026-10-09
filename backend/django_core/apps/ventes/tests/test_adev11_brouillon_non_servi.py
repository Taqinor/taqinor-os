"""ADEV11 (C-ADEV-004) — un BROUILLON n'est jamais servi au jeton CLIENT.

Un lien frappé par ``share-link`` (ou par un rendu PDF) AVANT l'envoi :
``/data/`` → 404 muet (aucun chiffre servi) ; ``/accept/``,
``/activer-option/``, OTP et contact → 409 ``{detail, code: "brouillon"}``
(contrat ``proposal_accept.json``, ADEV2). Le devis reste ``brouillon``, aucune
``DevisSignature``, aucun ``devis_accepted``. Le jeton INTERNE d'aperçu reste
servi (200) ; dès que le devis passe ``envoye``, le jeton client sert
normalement. ``accept_devis(…, user=None)`` refuse aussi le brouillon, même
appelé sans passer par le résolveur.

Test-du-test : retirer le contrôle de statut de ``_resolve_proposal_link`` ⇒
``test_data_404_jeton_client`` échoue ; retirer celui d'``accept_devis`` ⇒
``test_accept_service_refuse_brouillon`` échoue (et ``test_accept_409_brouillon``
si la vue le perd aussi).

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_adev11_brouillon_non_servi -v 2
"""
from decimal import Decimal

from django.core.cache import cache
from django.test import Client as DjangoClient, TestCase, override_settings

from apps.ventes.models import Devis, DevisSignature, LigneDevis, ShareLink
from apps.ventes.tests.test_l_niv_niveau import (
    make_client, make_company, make_devis, make_user,
)

CORPS_ACCEPT = {
    'nom': 'Karim Exemple', 'option': 'sans_batterie',
    'consent_esign': True,
}


@override_settings(CACHES={'default': {
    'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class BrouillonNonServiTests(TestCase):

    def setUp(self):
        cache.clear()
        self.company = make_company('adev11')
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.devis = make_devis(self.company, self.user, self.client_obj,
                                'DEV-ADEV11-0001')
        Devis.objects.filter(pk=self.devis.pk).update(
            statut=Devis.Statut.BROUILLON)
        self.devis.refresh_from_db()
        self.lien = ShareLink.for_devis(self.devis)
        self.http = DjangoClient()
        self.evenements = []
        from core.events import devis_accepted

        def _ecoute(sender, **kwargs):
            self.evenements.append(kwargs.get('devis'))

        devis_accepted.connect(_ecoute, dispatch_uid='adev11', weak=False)
        self.addCleanup(devis_accepted.disconnect, dispatch_uid='adev11')

    def _url(self, suffixe, token=None):
        return (f'/api/django/public/proposal/{token or self.lien.token}'
                f'/{suffixe}/')

    def _post(self, suffixe, corps=None, token=None):
        return self.http.post(self._url(suffixe, token), corps or {},
                              content_type='application/json')

    def _assert_toujours_brouillon(self):
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, Devis.Statut.BROUILLON)
        self.assertFalse(
            DevisSignature.objects.filter(devis=self.devis).exists())
        self.assertEqual(self.evenements, [])

    def _assert_409_brouillon(self, reponse):
        self.assertEqual(reponse.status_code, 409, reponse.content)
        self.assertEqual(reponse.json()['code'], 'brouillon')
        self.assertEqual(set(reponse.json()), {'detail', 'code'})

    def test_data_404_jeton_client(self):
        reponse = self.http.get(self._url('data'))
        self.assertEqual(reponse.status_code, 404)
        # CLAUSE CLIENT : aucun chiffre servi.
        self.assertNotIn(b'DEV-ADEV11-0001', reponse.content)
        self.assertNotIn(b'total_ttc', reponse.content)
        # Le PDF client du même jeton est refusé de la même façon.
        self.assertEqual(self.http.get(self._url('pdf')).status_code, 404)
        self._assert_toujours_brouillon()

    def test_accept_409_brouillon(self):
        self._assert_409_brouillon(self._post('accept', CORPS_ACCEPT))
        self._assert_toujours_brouillon()

    def test_accept_service_refuse_brouillon(self):
        """La garde vit AUSSI dans le service : une vue qui appellerait
        ``accept_devis(user=None)`` sans le résolveur est refusée."""
        from apps.ventes.services import AcceptError, accept_devis
        with self.assertRaises(AcceptError) as ctx:
            accept_devis(devis=self.devis, user=None, nom='X',
                         option='sans_batterie')
        self.assertTrue(ctx.exception.conflict)
        self.assertEqual(ctx.exception.code, 'brouillon')
        self._assert_toujours_brouillon()

    def test_activer_option_409(self):
        ligne = LigneDevis.objects.create(
            devis=self.devis, designation='Panneau optionnel 710 W',
            quantite=Decimal('4'), prix_unitaire=Decimal('1500'),
            remise=Decimal('0'), optionnelle=True)
        self._assert_409_brouillon(
            self._post('activer-option', {'ligne_id': ligne.pk}))
        ligne.refresh_from_db()
        self.assertTrue(ligne.optionnelle)
        self._assert_toujours_brouillon()

    def test_otp_et_contact_409(self):
        for suffixe in ('otp', 'otp-lecture/demander', 'contact'):
            with self.subTest(suffixe=suffixe):
                self._assert_409_brouillon(self._post(suffixe))
        self._assert_toujours_brouillon()

    def test_apercu_interne_200(self):
        jeton_interne = self.lien.jeton_interne_effectif()
        reponse = self.http.get(self._url('data', token=jeton_interne))
        self.assertEqual(reponse.status_code, 200, reponse.content)
        self._assert_toujours_brouillon()

    def test_envoye_servi(self):
        Devis.objects.filter(pk=self.devis.pk).update(
            statut=Devis.Statut.ENVOYE)
        lecture = self.http.get(self._url('data'))
        self.assertEqual(lecture.status_code, 200)
        # ADEV51 — la signature renvoie l'empreinte du contenu LU (servie
        # par ``data``) ; sans elle, 409 ``empreinte_perimee``.
        reponse = self._post('accept', {
            **CORPS_ACCEPT,
            'empreinte_contenu': lecture.json()['empreinte_contenu']})
        self.assertEqual(reponse.status_code, 200, reponse.content)
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, Devis.Statut.ACCEPTE)
