"""ACAL222 — la remise EXPLICITE remplace le versionnement par lecture.

Prouvé ici, sur un calepinage fabriqué par les VRAIS écrivains
(``acal_livrables_helpers.calepinage_simule_reel``) puis enregistré en base,
avec le vrai client HTTP et le vrai magasin (MinIO de la CI) :

* ``GET`` d'une pièce n'écrit AUCUNE version ;
* ``POST remettre-document`` : 201 v1 (empreinte des entrées encodée dans le
  nom et publiée), puis 200 ``deja_remise`` même numéro sans geste ; après une
  modification : 201 v2 et v1 publiée ``perimee`` ;
* deux remises SIMULTANÉES (deux transactions réelles) ⇒ deux numéros ;
* un ancien nom sans empreinte est relu ``empreinte: null, perimee: true`` ;
* CHAQUE code du registre remet un fichier — ou relaie EXACTEMENT le refus de
  son GET (même statut, même corps) : la remise appelle le même rendu.

Seule substitution : le catalogue matériel (``patch_materiel``, seam
documenté des livrables) — la source sous test n'est jamais simulée.

Run :
    python manage.py test apps.calepinage.tests.test_acal_remise_document -v2
"""
import copy
import threading
import uuid

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import connections
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.calepinage.models import Calepinage
from apps.calepinage.services.documents.versions_document import (
    enregistrer_version_document, versions_du_document,
)
from apps.calepinage.services.layout import enregistrer_layout
from apps.calepinage.views.remise_document import REGISTRE_REMISE
from apps.crm.models import Lead
from apps.records.models import Attachment
from apps.roles.models import Role
from apps.roles.permissions_registre import DIRECTEUR_PERMISSIONS
from authentication.models import Company

from .acal_livrables_helpers import calepinage_simule_reel, patch_materiel

User = get_user_model()

BASE = '/api/django/calepinage/calepinages/'

#: Le chemin GET de chaque code du registre (la MÊME pièce, en lecture).
CHEMIN_GET = {
    'rapport_etude': 'rapport-etude.pdf/',
    'rapport_ombrage': 'rapport-ombrage.pdf/',
    'export_projet_json': 'export-projet.json/',
    'plan_cablage': 'plan-cablage.pdf/',
    'manuel_proprietaire': 'manuel-proprietaire.pdf/',
    'document_asbuilt': 'document-asbuilt.pdf/',
    'presentation_compacte': 'presentation-compacte.pdf/',
    'diagramme_pertes': 'diagramme-pertes.svg/',
    'planche_pdf': 'planche.pdf/',
    'plan_pose_pdf': 'plan-pose.pdf/',
    'plan_toiture_pdf': 'plan-toiture.pdf/',
    'plan_masse_pdf': 'plan-masse.pdf/',
    'note_calcul_pdf': 'note-calcul.pdf/',
}


def _societe(suffixe):
    # Suffixe UNIQUE par exécution : une purge de TransactionTestCase
    # interrompue (base --keepdb partagée) ne laisse jamais une société ou un
    # utilisateur de même slug qui ferait tomber le setUp suivant en doublon.
    suffixe = '%s-%s' % (suffixe, uuid.uuid4().hex[:8])
    societe = Company.objects.create(nom='ACAL222 %s' % suffixe,
                                     slug='acal222-%s' % suffixe)
    role = Role.objects.create(company=societe, nom='Directeur',
                               permissions=list(DIRECTEUR_PERMISSIONS))
    user = User.objects.create_user(username='acal222-%s' % suffixe,
                                    password='x', company=societe, role=role)
    lead = Lead.objects.create(company=societe, nom='Toiture 222')
    pivot = calepinage_simule_reel()
    calepinage = Calepinage.objects.create(
        company=societe, lead_id=lead.pk, titre='Remise 222',
        roof_layout=copy.deepcopy(pivot.roof_layout),
        resultat=copy.deepcopy(pivot.resultat),
        layout_hash=pivot.layout_hash or '',
        version_moteur=pivot.version_moteur or '')
    return societe, user, calepinage


def _pieces(calepinage):
    return Attachment.objects.filter(
        content_type=ContentType.objects.get_for_model(Calepinage),
        object_id=calepinage.pk)


class RemiseDocumentTest(TestCase):
    def setUp(self):
        self.societe, self.user, self.calepinage = _societe('a')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _url(self, chemin):
        return f'{BASE}{self.calepinage.pk}/{chemin}'

    def _remettre(self, code='diagramme_pertes', langue='fr'):
        with patch_materiel():
            return self.api.post(self._url('remettre-document/'),
                                 {'code': code, 'langue': langue},
                                 format='json')

    def _documents(self):
        with patch_materiel():
            return self.api.get(self._url('documents/'))

    def _modifier_le_toit(self):
        layout = copy.deepcopy(self.calepinage.roof_layout)
        layout['zones'][0]['geometry']['count'] -= 1
        with patch_materiel():
            enregistrer_layout(self.calepinage, layout, user=self.user)

    def test_get_n_ecrit_aucune_version(self):
        for chemin in ('rapport-etude.pdf/', 'diagramme-pertes.svg/',
                       'export-projet.json/'):
            for _ in range(3):
                with patch_materiel():
                    self.api.get(self._url(chemin))
        self.assertEqual(_pieces(self.calepinage).count(), 0)
        self.assertEqual(
            versions_du_document(self.calepinage, 'rapport_etude'), [])

    def test_remise_deux_fois_sans_changement_un_seul_numero(self):
        premiere = self._remettre()
        self.assertEqual(premiere.status_code, 201,
                         getattr(premiere, 'data', premiere.content[:300]))
        self.assertEqual(premiere.data['numero'], 1)
        self.assertFalse(premiere.data['deja_remise'])
        self.assertEqual(len(premiere.data['empreinte']), 16)
        piece = Attachment.objects.get(pk=premiere.data['attachment'])
        self.assertEqual(
            piece.filename,
            'diagramme_pertes__v001__fr__%s.svg' % premiere.data['empreinte'])

        seconde = self._remettre()
        self.assertEqual(seconde.status_code, 200)
        self.assertTrue(seconde.data['deja_remise'])
        self.assertEqual(seconde.data['numero'], 1)
        self.assertEqual(seconde.data['attachment'],
                         premiere.data['attachment'])
        self.assertEqual(_pieces(self.calepinage).count(), 1)

        # Aller-retour : l'inventaire publie la version, à jour.
        inventaire = self._documents()
        self.assertEqual(inventaire.status_code, 200)
        carte = next(d for d in inventaire.data['documents']
                     if d['code'] == 'diagramme_pertes')
        self.assertEqual(carte['versions'][0]['numero'], 1)
        self.assertEqual(carte['versions'][0]['empreinte'],
                         premiere.data['empreinte'])
        self.assertFalse(carte['versions'][0]['perimee'])

    def test_remise_apres_modification_cree_v2_et_perime_v1(self):
        premiere = self._remettre(code='export_projet_json')
        self.assertEqual(premiere.status_code, 201,
                         getattr(premiere, 'data', premiere.content[:300]))
        self._modifier_le_toit()
        seconde = self._remettre(code='export_projet_json')
        self.assertEqual(seconde.status_code, 201,
                         getattr(seconde, 'data', seconde.content[:300]))
        self.assertEqual(seconde.data['numero'], 2)
        self.assertNotEqual(seconde.data['empreinte'],
                            premiere.data['empreinte'])
        self.calepinage.refresh_from_db()
        with patch_materiel():
            versions = versions_du_document(self.calepinage,
                                            'export_projet_json')
        self.assertEqual([v['numero'] for v in versions], [2, 1])
        self.assertEqual([v['perimee'] for v in versions], [False, True])

    def test_ancien_nom_sans_empreinte_est_perime(self):
        Attachment.objects.create(
            company=self.societe,
            content_type=ContentType.objects.get_for_model(Calepinage),
            object_id=self.calepinage.pk, file_key='attachments/ancien.pdf',
            filename='rapport_etude__v001__fr.pdf', size=10,
            mime='application/pdf')
        with patch_materiel():
            versions = versions_du_document(self.calepinage, 'rapport_etude')
        self.assertEqual(len(versions), 1)
        self.assertEqual(versions[0]['numero'], 1)
        self.assertIsNone(versions[0]['empreinte'])
        self.assertTrue(versions[0]['perimee'])

    def test_code_inconnu_refuse_sous_code(self):
        reponse = self._remettre(code='rapport_x')
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('code', reponse.data)
        self.assertEqual(_pieces(self.calepinage).count(), 0)

    def test_chaque_code_du_registre_remet_un_fichier(self):
        self.assertEqual(set(REGISTRE_REMISE), set(CHEMIN_GET))
        for code, (_action, extension, _mime) in REGISTRE_REMISE.items():
            with self.subTest(code=code):
                with patch_materiel():
                    lecture = self.api.get(self._url(CHEMIN_GET[code]),
                                           {'langue': 'fr'})
                remise = self._remettre(code=code)
                if lecture.status_code != 200:
                    # Même rendu ⇒ même refus, relayé tel quel, rien d'écrit.
                    self.assertEqual(remise.status_code, lecture.status_code)
                    self.assertEqual(remise.data, lecture.data)
                    self.assertEqual(
                        len(versions_du_document(self.calepinage, code)), 0)
                    continue
                self.assertEqual(remise.status_code, 201,
                                 getattr(remise, 'data', None))
                piece = Attachment.objects.get(pk=remise.data['attachment'])
                self.assertTrue(piece.filename.startswith(code + '__v001__'))
                self.assertTrue(piece.filename.endswith('.' + extension))
                self.assertGreater(piece.size, 0)
                if extension in ('json', 'svg'):
                    # Rendu déterministe : les octets stockés = ceux du GET.
                    from apps.records.storage import fetch_attachment

                    octets, erreur = fetch_attachment(piece.file_key)
                    self.assertIsNone(erreur)
                    self.assertEqual(octets, lecture.content)


class NumerotationConcurrenteTest(TransactionTestCase):
    """Deux transactions RÉELLES, simultanées : deux numéros distincts."""

    def test_numerotation_concurrente_sans_doublon(self):
        _societe_, user, calepinage = _societe('b')
        depart = threading.Barrier(2)
        numeros, erreurs = [], []

        def remettre(empreinte):
            try:
                depart.wait(timeout=10)
                version = enregistrer_version_document(
                    Calepinage.objects.get(pk=calepinage.pk),
                    code='diagramme_pertes', octets=b'<svg/>', langue='fr',
                    user=user, empreinte=empreinte, extension='svg',
                    mime='image/svg+xml')
                numeros.append(version['numero'])
            except Exception as erreur:  # noqa: BLE001 - remonté au test
                erreurs.append(erreur)
            finally:
                connections.close_all()

        fils = [threading.Thread(target=remettre, args=(e * 16,))
                for e in ('a', 'b')]
        for fil in fils:
            fil.start()
        for fil in fils:
            fil.join(timeout=60)
        self.assertEqual(erreurs, [])
        self.assertEqual(sorted(numeros), [1, 2])
