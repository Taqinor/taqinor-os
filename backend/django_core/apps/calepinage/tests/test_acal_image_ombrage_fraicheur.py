"""ACAL224 — la carte de chaleur est liée à la conception qui l'a produite.

Constat C-ACAL-119 / C-ACAL-134 : une carte déposée pour la conception A était
imprimée, sans date, à côté de la matrice recalculée d'une conception B ; les
genres ``sankey``/``plan3d`` n'avaient aucun lecteur ; un utilisateur en
simple lecture pouvait déposer.

Chaîne RÉELLE : dépôt par ``POST image-document/`` (client HTTP, MinIO de la
CI), conception modifiée par ``enregistrer_layout``, puis le HTML des DEUX
rapports (rapport d'ombrage autonome et section ombrage du rapport d'étude).
Aucun mock.

Run :
    python manage.py test apps.calepinage.tests.test_acal_image_ombrage_fraicheur -v2
"""
import base64
import copy
import io

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.calepinage.models import Calepinage
from apps.calepinage.services.images_document import images_du_calepinage
from apps.calepinage.services.layout import enregistrer_layout
from apps.calepinage.services.rapport import ombrage as section_ombrage
from apps.calepinage.services.rapport_ombrage import (
    _table_matrice, _html_du_rapport_ombrage,
)
from apps.records.models import Attachment
from apps.roles.models import Role

from .test_api_liste import BaseApiCalepinage, url_detail
from .test_calx317_rapport_ombrage import LAYOUT_OMBRAGE, MATRICE_12X24

User = get_user_model()

MOTIF_PERIME = 'Carte de chaleur à rejoindre (conception modifiée depuis le'


def _data_uri_png():
    from PIL import Image

    tampon = io.BytesIO()
    Image.new('RGB', (20, 20), color=(200, 40, 40)).save(tampon,
                                                         format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(
        tampon.getvalue()).decode('ascii')


class ImageOmbrageFraicheurTest(BaseApiCalepinage):
    def setUp(self):
        super().setUp()
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa Anfa',
            roof_layout=copy.deepcopy(LAYOUT_OMBRAGE))

    def _deposer(self, api=None, genre='ombrage'):
        return (api or self.api).post(
            f'{url_detail(self.calepinage.pk)}image-document/',
            {'genre': genre, 'fichier': _data_uri_png()}, format='json')

    def _deux_rapports(self):
        self.calepinage.refresh_from_db()
        autonome = _html_du_rapport_ombrage(self.calepinage)
        section = section_ombrage.html_de_section(
            {'resultat': {'calepinage': self.calepinage.pk}})
        return autonome, section

    def _modifier_la_conception(self):
        layout = copy.deepcopy(self.calepinage.roof_layout)
        layout['zones'][0]['geometry']['count'] -= 2
        enregistrer_layout(self.calepinage, layout, user=self.user)

    def test_image_deposee_puis_conception_modifiee_n_est_plus_embarquee(self):
        depot = self._deposer()
        self.assertEqual(depot.status_code, 201, depot.data)
        self._modifier_la_conception()
        date = timezone.localtime(
            Attachment.objects.get(pk=depot.data['attachment']).created_at
        ).strftime('%d/%m/%Y')
        for html in self._deux_rapports():
            self.assertNotIn('data:image/png;base64,', html)
            self.assertIn('%s %s)' % (MOTIF_PERIME, date), html)
        image = images_du_calepinage(self.calepinage)[0]
        self.assertTrue(image['perimee'])
        self.assertEqual(image['empreinte'], depot.data['empreinte'])

    def test_image_fraiche_embarquee_avec_sa_date(self):
        depot = self._deposer()
        self.assertEqual(depot.status_code, 201, depot.data)
        self.assertEqual(len(depot.data['empreinte']), 12)
        self.assertFalse(depot.data['perimee'])
        date = timezone.localtime(
            Attachment.objects.get(pk=depot.data['attachment']).created_at
        ).strftime('%d/%m/%Y')
        for html in self._deux_rapports():
            self.assertIn('data:image/png;base64,', html)
            self.assertIn('déposée le %s' % date, html)
            self.assertNotIn(MOTIF_PERIME, html)
        inventaire = self.api.get(f'{url_detail(self.calepinage.pk)}documents/')
        self.assertEqual(inventaire.status_code, 200)
        self.assertFalse(inventaire.data['images'][0]['perimee'])
        self.assertEqual(inventaire.data['images'][0]['empreinte'],
                         depot.data['empreinte'])

    def test_image_sans_empreinte_consideree_perimee(self):
        Attachment.objects.create(
            company=self.company,
            content_type=ContentType.objects.get_for_model(Calepinage),
            object_id=self.calepinage.pk, file_key='attachments/ancienne.png',
            filename='image__ombrage__0123456789ab.png', size=10,
            mime='image/png')
        image = images_du_calepinage(self.calepinage)[0]
        self.assertIsNone(image['empreinte'])
        self.assertTrue(image['perimee'])
        for html in self._deux_rapports():
            self.assertNotIn('data:image/png;base64,', html)
            self.assertIn(MOTIF_PERIME, html)

    def test_genres_sankey_et_plan3d_refuses(self):
        for genre in ('sankey', 'plan3d'):
            with self.subTest(genre=genre):
                reponse = self._deposer(genre=genre)
                self.assertEqual(reponse.status_code, 400)
                self.assertIn('genre', reponse.data)
        self.assertEqual(images_du_calepinage(self.calepinage), [])

    def test_depot_refuse_403_sans_calepinage_gerer(self):
        role = Role.objects.create(company=self.company, nom='Lecteur 224',
                                   permissions=['calepinage_voir'])
        lecteur = User.objects.create_user(
            username='acal224_lecteur', password='x', company=self.company,
            role=role)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(lecteur)}')
        # Il LIT (le droit existe vraiment) …
        self.assertEqual(
            api.get(f'{url_detail(self.calepinage.pk)}documents/')
            .status_code, 200)
        # … mais ne dépose pas.
        self.assertEqual(self._deposer(api=api).status_code, 403)
        self.assertEqual(images_du_calepinage(self.calepinage), [])

    def test_les_deux_rapports_utilisent_le_meme_helper_d_ombrage(self):
        table = _table_matrice(MATRICE_12X24)
        autonome, section = self._deux_rapports()
        self.assertIn(table, autonome)
        self.assertIn(table, section)
        # Même règle de carte : aucune déposée ⇒ la même mention.
        self.assertIn('Aucune carte de chaleur déposée', autonome)
        self.assertIn('Aucune carte de chaleur déposée', section)
