"""APX18 — Photo produit : pointeur `records.Attachment`, upload, isolation.

La photo produit a été DÉGATÉE par mot fondateur du 2026-08-01 (« photos ok »)
après avoir figuré sur deux listes « NE PAS FAIRE » (VX et VXD), amendées dans
le commit d'insertion du Groupe APX.

ARC26 — le fichier n'est PAS un `FileField` de plus : il vit dans MinIO via la
primitive plateforme `records.Attachment` (`stock.produit` est déjà une cible
autorisée du registre, cf. `apps/stock/platform.py`), et `Produit.photo` n'est
qu'un POINTEUR vers LA photo canonique.

Ce que ces tests prouvent :
  * `description` n'est déclaré qu'UNE fois sur `Produit` (la double
    déclaration silencieuse d'avant est corrigée — le champ effectif garde son
    `help_text`, donc l'état de migration est inchangé) ;
  * `photo` est ADDITIF : un produit se crée et se lit exactement comme avant
    sans photo, et `image_url` vaut `None` ;
  * `POST /stock/produits/<id>/photo/` téléverse ET rattache en UN appel ;
  * remplacer une photo ne laisse pas l'ancienne traîner dans MinIO ;
  * `DELETE` retire la photo (et la pièce jointe) sans toucher au produit ;
  * l'action est une ÉCRITURE : un rôle sans `stock_modifier` est refusé (le
    `get_permissions` du viewset prime sur le `permission_classes` de
    l'@action — sans le cas explicite, elle retomberait sur IsAdminRole) ;
  * ISOLATION SOCIÉTÉ : on ne pose jamais de photo sur le produit d'autrui ;
  * `image_url` pointe l'endpoint plateforme, jamais une URL média brute ;
  * PRIX D'ACHAT : la réponse de ce chemin n'expose aucune donnée d'achat.

Run:
    python manage.py test apps.stock.test_apx18_photo_produit -v 2
"""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.records.models import Attachment
from apps.roles.models import Role
from apps.stock.models import Produit

User = get_user_model()

PNG_1PX = b'\x89PNG\r\n\x1a\n' + b'\x00' * 8


def _meta(cle='attachments/1/apx18.png'):
    return {'file_key': cle, 'filename': 'photo.png', 'size': 16,
            'mime': 'image/png'}


def _company(slug):
    return Company.objects.create(nom=slug, slug=slug)


def _user(company, username, permissions=None):
    role = Role.objects.create(
        company=company, nom=f'r-{username}', permissions=permissions or [])
    return User.objects.create_user(
        username=username, password='x', company=company, role=role,
        role_legacy='responsable')


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def _fichier(nom='photo.png'):
    return SimpleUploadedFile(nom, PNG_1PX, content_type='image/png')


class Apx18ModeleTests(TestCase):
    """Le modèle : `description` unique + `photo` additive et nullable."""

    def test_description_declaree_une_seule_fois(self):
        champs = [f for f in Produit._meta.get_fields()
                  if f.name == 'description']
        self.assertEqual(
            len(champs), 1,
            'Produit.description doit être déclaré une seule fois (la double '
            'déclaration silencieuse était un bug latent).')
        # La déclaration SURVIVANTE est celle documentée (avec help_text) :
        # c'est déjà l'état de migration actuel, donc rien à migrer.
        self.assertIn('PDF', champs[0].help_text)

    def test_photo_est_additive_nullable_et_vide_par_defaut(self):
        champ = Produit._meta.get_field('photo')
        # Additif et RÉVERTABLE : nullable, facultatif, sans valeur par défaut
        # — aucun produit existant n'est touché par la migration.
        self.assertTrue(champ.null)
        self.assertTrue(champ.blank)
        # Supprimer la pièce jointe ne doit JAMAIS supprimer le produit.
        self.assertEqual(champ.remote_field.on_delete.__name__, 'SET_NULL')
        produit = Produit.objects.create(
            company=_company('apx18-modele'), nom='Panneau 550 Wc',
            prix_vente=Decimal('1000'))
        self.assertIsNone(produit.photo_id)

    def test_aucun_filefield_ajoute_au_modele(self):
        """ARC26 — la photo passe par records.Attachment, jamais par un
        FileField/ImageField de plus sur Produit."""
        from django.db.models import FileField
        ajouts = [
            f.name for f in Produit._meta.get_fields()
            if isinstance(f, FileField)
        ]
        self.assertEqual(ajouts, [])


class Apx18PhotoApiTests(TestCase):
    """L'action `photo/` : upload, remplacement, retrait, gardes."""

    def setUp(self):
        super().setUp()
        self.company = _company('apx18-co')
        self.user = _user(
            self.company, 'apx18-user',
            permissions=['stock_voir', 'stock_modifier'])
        self.api = _api(self.user)
        self.produit = Produit.objects.create(
            company=self.company, nom='Pompe OSP 30-15',
            prix_achat=Decimal('980.00'), prix_vente=Decimal('1350.00'))
        self.url = f'/api/django/stock/produits/{self.produit.id}/photo/'

    def _poser(self, api=None, url=None, cle='attachments/1/apx18.png'):
        with patch('apps.records.storage.store_attachment',
                   return_value=(_meta(cle), None)) as store:
            r = (api or self.api).post(
                url or self.url, {'file': _fichier()}, format='multipart')
        return r, store

    def test_sans_photo_image_url_est_null(self):
        r = self.api.get(f'/api/django/stock/produits/{self.produit.id}/')
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.data['image_url'])
        # La FK elle-même n'est JAMAIS exposée : l'accepter du corps
        # laisserait un client pointer la pièce jointe d'un autre objet.
        self.assertNotIn('photo', r.data)

    def test_upload_en_un_appel_stocke_et_rattache(self):
        r, store = self._poser()
        self.assertEqual(r.status_code, 201, r.data)
        store.assert_called_once()
        self.produit.refresh_from_db()
        self.assertIsNotNone(self.produit.photo_id)
        piece = self.produit.photo
        # La pièce jointe est bien scopée société et rattachée AU produit.
        self.assertEqual(piece.company_id, self.company.id)
        self.assertEqual(piece.object_id, self.produit.id)
        self.assertEqual(piece.content_type.model, 'produit')
        # L'URL renvoyée EST l'endpoint plateforme (même origine, cookie).
        self.assertEqual(
            r.data['image_url'],
            f'/api/django/records/attachments/{piece.id}/download/')

    def test_image_url_du_serializer_pointe_l_endpoint_plateforme(self):
        self._poser()
        self.produit.refresh_from_db()
        r = self.api.get(f'/api/django/stock/produits/{self.produit.id}/')
        self.assertEqual(
            r.data['image_url'],
            f'/api/django/records/attachments/{self.produit.photo_id}/download/')
        # Jamais une URL média brute ni une URL MinIO présignée.
        self.assertNotIn('minio', r.data['image_url'])
        self.assertNotIn('/media/', r.data['image_url'])

    def test_remplacer_une_photo_supprime_l_ancienne(self):
        self._poser(cle='attachments/1/ancienne.png')
        self.produit.refresh_from_db()
        ancienne_id = self.produit.photo_id

        with patch('apps.records.storage.delete_attachment') as suppr:
            self._poser(cle='attachments/1/nouvelle.png')
        self.produit.refresh_from_db()

        self.assertNotEqual(self.produit.photo_id, ancienne_id)
        self.assertFalse(Attachment.objects.filter(id=ancienne_id).exists())
        suppr.assert_called_once_with('attachments/1/ancienne.png')

    def test_delete_retire_la_photo_sans_toucher_au_produit(self):
        self._poser()
        self.produit.refresh_from_db()
        piece_id = self.produit.photo_id

        with patch('apps.records.storage.delete_attachment') as suppr:
            r = self.api.delete(self.url)
        self.assertEqual(r.status_code, 204)
        suppr.assert_called_once()

        self.produit.refresh_from_db()
        self.assertIsNone(self.produit.photo_id)
        self.assertFalse(Attachment.objects.filter(id=piece_id).exists())
        # Le produit lui-même est intact.
        self.assertEqual(self.produit.nom, 'Pompe OSP 30-15')
        self.assertEqual(self.produit.prix_vente, Decimal('1350.00'))

    def test_delete_sans_photo_est_idempotent(self):
        r = self.api.delete(self.url)
        self.assertEqual(r.status_code, 204)

    def test_sans_fichier_400_lisible(self):
        r = self.api.post(self.url, {}, format='multipart')
        self.assertEqual(r.status_code, 400)
        self.assertIn('fichier', r.data['detail'].lower())

    def test_format_refuse_par_la_plateforme_remonte_en_400(self):
        with patch('apps.records.storage.store_attachment',
                   return_value=(None, 'Format non supporté.')):
            r = self.api.post(self.url, {'file': _fichier('x.txt')},
                              format='multipart')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['detail'], 'Format non supporté.')
        self.produit.refresh_from_db()
        self.assertIsNone(self.produit.photo_id)

    def test_ecriture_gardee_par_stock_modifier(self):
        """L'action EST une écriture catalogue : un rôle en lecture seule est
        refusé. (Le `get_permissions` du viewset prime sur le
        `permission_classes` de l'@action — d'où le cas explicite.)"""
        lectrice = _user(
            self.company, 'apx18-lectrice', permissions=['stock_voir'])
        r, _ = self._poser(api=_api(lectrice))
        self.assertEqual(r.status_code, 403)

    def test_isolation_societe(self):
        autre = _company('apx18-autre')
        intrus = _user(autre, 'apx18-intrus',
                       permissions=['stock_voir', 'stock_modifier'])
        r, _ = self._poser(api=_api(intrus))
        self.assertEqual(r.status_code, 404)
        self.produit.refresh_from_db()
        self.assertIsNone(self.produit.photo_id)

    def test_la_reponse_photo_n_expose_aucune_donnee_d_achat(self):
        r, _ = self._poser()
        self.assertEqual(list(r.data.keys()), ['image_url'])
        self.assertNotIn('prix_achat', r.data)
        self.assertNotIn('980', str(r.data))
