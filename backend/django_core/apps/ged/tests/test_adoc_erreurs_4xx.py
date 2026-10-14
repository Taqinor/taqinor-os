"""ADOC22 — les exceptions métier GED sortent en 4xx nommés, jamais en 500.

Constats #24, #25, #26, #50, #53 de l'audit documents (2026-10-05) : doublon
d'armoire / de tampon, document archivé sur assigner/verrouiller, fusion de
PNG, disposition bloquée par un document archivé, archivage d'un document en
corbeille — tous répondaient 500.
"""
import io
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ged import services
from apps.ged.models import (
    ArchivageLegal, Cabinet, DemandeDisposition, Document, Folder,
    PolitiqueRetention, TamponSociete,
)
from authentication.models import Company

User = get_user_model()
BASE = '/api/django/ged/'


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def _png():
    from PIL import Image
    buf = io.BytesIO()
    Image.new('RGB', (4, 4), 'white').save(buf, format='PNG')
    return buf.getvalue()


class ErreursMetierTests(TestCase):
    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='adoc22', defaults={'nom': 'ADOC22'})[0]
        self.admin = User.objects.create_user(
            username='adoc22-admin', password='x', company=self.co,
            role_legacy='admin')
        self.admin2 = User.objects.create_user(
            username='adoc22-admin2', password='x', company=self.co,
            role_legacy='admin')
        self.cab = Cabinet.objects.create(company=self.co, nom='X')
        self.folder = Folder.objects.create(
            company=self.co, cabinet=self.cab, nom='R')
        self.api = auth(self.admin)

    def _archiver(self, doc):
        with mock.patch('apps.records.storage.fetch_attachment',
                        return_value=(b'abc', None)):
            return services.archiver_legalement(doc, user=self.admin)

    def test_doublon_armoire_409(self):
        # ENF7 — le doublon (société, nom) est refusé par la garde d'unicité
        # plateforme (409 `unique_conflict`), plus par un 400 maison.
        resp = self.api.post(f'{BASE}cabinets/', {'nom': 'X'}, format='json')
        self.assertEqual(resp.status_code, 409, resp.content)
        self.assertEqual(resp.data['error']['code'], 'unique_conflict')
        self.assertEqual(Cabinet.objects.filter(nom='X').count(), 1)

    def test_doublon_tampon_409(self):
        TamponSociete.objects.create(company=self.co, libelle='Y')
        resp = self.api.post(f'{BASE}tampons-societe/', {'libelle': 'Y'},
                             format='json')
        self.assertEqual(resp.status_code, 409, resp.content)
        self.assertEqual(resp.data['error']['code'], 'unique_conflict')
        self.assertEqual(TamponSociete.objects.filter(libelle='Y').count(), 1)

    def test_assigner_archive_403(self):
        doc = Document.objects.create(company=self.co, folder=self.folder,
                                      nom='archive.pdf')
        self._archiver(doc)
        for route, corps in (('assigner', {'proprietaire': self.admin.pk}),
                             ('verrouiller', {}), ('deverrouiller', {})):
            resp = self.api.post(f'{BASE}documents/{doc.pk}/{route}/', corps,
                                 format='json')
            self.assertEqual(resp.status_code, 403, (route, resp.content))
        doc.refresh_from_db()
        self.assertIsNone(doc.proprietaire_id)

    def test_fusion_png_400(self):
        octets = _png()
        docs = []
        for nom in ('a.png', 'b.png'):
            d = Document.objects.create(company=self.co, folder=self.folder,
                                        nom=nom)
            services.add_version(d, file_key=f'attachments/{nom}',
                                 company=self.co, mime='image/png')
            docs.append(d)
        avant = Document.objects.count()
        with mock.patch('apps.ged.services._fetch_version_bytes',
                        return_value=(octets, None)):
            resp = self.api.post(f'{BASE}documents/fusionner/', {
                'documents': [d.pk for d in docs]}, format='json')
            self.assertEqual(resp.status_code, 400, resp.content)
            self.assertIn('réservée aux PDF', resp.data['detail'])
            resp = self.api.post(f'{BASE}documents/{docs[0].pk}/scinder/',
                                 {'points_de_coupe': [1]}, format='json')
            self.assertEqual(resp.status_code, 400, resp.content)
            resp = self.api.post(f'{BASE}documents/{docs[0].pk}/caviarder/', {
                'zones': [{'page': 0, 'x0': 0, 'y0': 0, 'x1': 10,
                           'y1': 10}]}, format='json')
            self.assertEqual(resp.status_code, 400, resp.content)
            version = docs[0].versions.first()
            resp = self.api.get(
                f'{BASE}annotations/export-annote/?version={version.pk}')
            self.assertEqual(resp.status_code, 400, resp.content)
        self.assertEqual(Document.objects.count(), avant)

    def test_detagger_tag_obligatoire_400(self):
        # CI #956 (fuzz r13, « accepted schema-violating » sur detagger/) —
        # `tag` est obligatoire au schéma (TAG_CORPS) : sans corps ou mal
        # formé, 400 nommant le champ (avant : 200, retrait de rien).
        from apps.ged.models import DocumentTag, DocumentTagAssignment
        doc = Document.objects.create(company=self.co, folder=self.folder,
                                      nom='t.pdf')
        tag = DocumentTag.objects.create(company=self.co, nom='Important',
                                         slug='important')
        services.assign_tag(doc, tag, created_by=self.admin)
        for corps in ({}, {'tag': 'abc'}):
            resp = self.api.post(f'{BASE}documents/{doc.pk}/detagger/',
                                 corps, format='json')
            self.assertEqual(resp.status_code, 400, resp.data)
            self.assertIn('tag', resp.data)
        self.assertTrue(DocumentTagAssignment.objects.filter(
            document=doc, tag=tag).exists())
        resp = self.api.post(f'{BASE}documents/{doc.pk}/detagger/',
                             {'tag': tag.pk}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(DocumentTagAssignment.objects.filter(
            document=doc, tag=tag).exists())

    def test_fichier_introuvable_404_pas_400(self):
        # CI #956 (fuzz r13, « rejected schema-compliant request » sur
        # scinder/) — des octets ABSENTS du stockage ne sont pas une entrée
        # invalide : 404 (comme le proxy de téléchargement), jamais 400 ; même
        # règle sur caviarder, fusionner et l'export annoté.
        docs = []
        for nom in ('a.pdf', 'b.pdf'):
            d = Document.objects.create(company=self.co, folder=self.folder,
                                        nom=nom)
            services.add_version(d, file_key=f'attachments/{nom}',
                                 company=self.co, mime='application/pdf')
            docs.append(d)
        avant = Document.objects.count()
        with mock.patch('apps.ged.services._fetch_version_bytes',
                        return_value=(None, 'Fichier introuvable.')):
            resp = self.api.post(f'{BASE}documents/{docs[0].pk}/scinder/',
                                 {'points_de_coupe': []}, format='json')
            self.assertEqual(resp.status_code, 404, resp.content)
            self.assertEqual(resp.data['detail'], 'Fichier introuvable.')
            resp = self.api.post(f'{BASE}documents/{docs[0].pk}/caviarder/', {
                'zones': [{'page': 0, 'x0': 0, 'y0': 0, 'x1': 10,
                           'y1': 10}]}, format='json')
            self.assertEqual(resp.status_code, 404, resp.content)
            resp = self.api.post(f'{BASE}documents/fusionner/', {
                'documents': [d.pk for d in docs]}, format='json')
            self.assertEqual(resp.status_code, 404, resp.content)
            version = docs[0].versions.first()
            resp = self.api.get(
                f'{BASE}annotations/export-annote/?version={version.pk}')
            self.assertEqual(resp.status_code, 404, resp.content)
        self.assertEqual(Document.objects.count(), avant)

    def test_disposition_ignore_archive(self):
        PolitiqueRetention.objects.create(
            company=self.co, nom='Globale', duree_conservation_jours=30)
        vieux = Document.objects.create(company=self.co, folder=self.folder,
                                        nom='vieux.pdf')
        archive = Document.objects.create(company=self.co, folder=self.folder,
                                          nom='archive.pdf')
        Document.objects.filter(pk__in=[vieux.pk, archive.pk]).update(
            created_at=timezone.now() - timedelta(days=400))
        demande = services.creer_demande_disposition(
            self.co, libelle='Purge', document_ids=[vieux.pk, archive.pk],
            user=self.admin)
        services.approuver_demande_disposition(demande, user=self.admin2)
        self._archiver(archive)
        resp = auth(self.admin2).post(
            f'{BASE}demandes-disposition/{demande.pk}/executer/')
        self.assertEqual(resp.status_code, 200, resp.content)
        demande.refresh_from_db()
        self.assertEqual(demande.statut, 'executee')
        self.assertIn('1 document(s) ignoré(s)', demande.commentaire)
        self.assertFalse(Document.objects.filter(pk=vieux.pk).exists())
        self.assertTrue(Document.objects.filter(pk=archive.pk).exists())
        self.assertTrue(ArchivageLegal.objects.filter(document=archive).exists())
        self.assertEqual(DemandeDisposition.objects.count(), 1)

    def test_disposition_archiver_ignore_corbeille(self):
        """ADOC179 (sonde C-ADOC-VER-005) — « archiver » sur un document mis
        en corbeille entre-temps : compté ignoré, jamais un 500 ; le lot
        mixte archive les autres."""
        jete = Document.objects.create(company=self.co, folder=self.folder,
                                       nom='jete.pdf')
        vivant = Document.objects.create(company=self.co, folder=self.folder,
                                         nom='vivant.pdf')
        demande = services.creer_demande_disposition(
            self.co, libelle='Archivage', action='archiver',
            document_ids=[jete.pk, vivant.pk], user=self.admin)
        services.approuver_demande_disposition(demande, user=self.admin2)
        services.mettre_en_corbeille(jete, self.admin)
        with mock.patch('apps.records.storage.fetch_attachment',
                        return_value=(b'abc', None)):
            resp = auth(self.admin2).post(
                f'{BASE}demandes-disposition/{demande.pk}/executer/')
        self.assertEqual(resp.status_code, 200, resp.content)
        demande.refresh_from_db()
        self.assertEqual(demande.statut, 'executee')
        self.assertIn('1 document(s) ignoré(s)', demande.commentaire)
        self.assertFalse(ArchivageLegal.objects.filter(document=jete).exists())
        self.assertIsNotNone(Document.objects.get(pk=jete.pk).supprime_le)
        self.assertTrue(ArchivageLegal.objects.filter(document=vivant).exists())

    def test_archiver_corbeille_409(self):
        doc = Document.objects.create(company=self.co, folder=self.folder,
                                      nom='jete.pdf')
        services.mettre_en_corbeille(doc, self.admin)
        resp = self.api.post(f'{BASE}archivages-legaux/',
                             {'document': doc.pk}, format='json')
        self.assertEqual(resp.status_code, 409, resp.content)
        self.assertFalse(ArchivageLegal.objects.filter(document=doc).exists())


# ENF7 — le contrat OpenAPI de la GED décrit ce que les vues font vraiment. Couvre : identifiants
# non numériques et paramètres obligatoires/mal formés → 4xx nommé (jamais 500), doublons → 409,
# JSON seul hors envoi de fichier (D2), et le schéma des vues GED/records se génère sans erreur.
class Enf7ContratGedTests(TestCase):
    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='enf7-ged', defaults={'nom': 'ENF7 GED'})[0]
        self.admin = User.objects.create_user(
            username='enf7-ged-admin', password='x', company=self.co,
            role_legacy='admin')
        self.cab = Cabinet.objects.create(company=self.co, nom='C')
        self.folder = Folder.objects.create(
            company=self.co, cabinet=self.cab, nom='R')
        self.api = auth(self.admin)

    def test_archivage_corps_hors_schema_400(self):
        # ENF11 (api-fuzz) — `document: [null, null]` répondait 500.
        resp = self.api.post(f'{BASE}archivages-legaux/', {
            'document': [None, None], 'motif': '',
            'retain_until': '2000-01-01'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_identifiants_non_numeriques_jamais_500(self):
        for route in ('archivages-legaux/', 'legal-holds/'):
            resp = self.api.post(
                f'{BASE}{route}', {'document': 'AAA'}, format='json')
            self.assertIn(resp.status_code, (400, 404), (route, resp.content))
        resp = self.api.post(
            f'{BASE}documents/scan-lot/', {'folder': 'AAA'},
            format='multipart')
        self.assertIn(resp.status_code, (400, 404), resp.content)
        resp = self.api.post(
            f'{BASE}documents/import-masse/', {'folder': 'AAA'},
            format='multipart')
        self.assertIn(resp.status_code, (400, 404), resp.content)

    def test_parametres_obligatoires_ou_mal_formes(self):
        resp = self.api.get(f'{BASE}demandes-document/checklist/')
        self.assertEqual(resp.status_code, 400, resp.content)
        resp = self.api.get(f'{BASE}annotations/export-annote/')
        self.assertEqual(resp.status_code, 400, resp.content)
        resp = self.api.get(
            f'{BASE}demandes-signature/tableau-bord/?emetteur=abc')
        self.assertEqual(resp.status_code, 400, resp.content)
        resp = self.api.get(
            f'{BASE}demandes-signature/tableau-bord/?date_debut=2026-13-45')
        self.assertEqual(resp.status_code, 400, resp.content)
        resp = self.api.get(f'{BASE}analytique/?date_fin=pas-une-date')
        self.assertEqual(resp.status_code, 400, resp.content)
        resp = self.api.get(f'{BASE}analytique/?date_debut=2026-01-01')
        self.assertEqual(resp.status_code, 200, resp.content)

    def test_doublon_armoire_409_et_json_seul(self):
        resp = self.api.post(f'{BASE}cabinets/', {'nom': 'C'}, format='json')
        self.assertEqual(resp.status_code, 409, resp.content)
        # D2 : une vue sans fichier ne lit plus le multipart.
        resp = self.api.post(
            f'{BASE}roles-signataire/',
            {'nom': 'Client', 'peut_changer_signataire': '0'},
            format='multipart')
        self.assertEqual(resp.status_code, 415, resp.content)
        resp = self.api.post(
            f'{BASE}roles-signataire/',
            {'nom': 'Client', 'peut_changer_signataire': False},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.content)

    def test_methode_non_servie_405_avant_le_parseur(self):
        # CI #956 (fuzz « Unsupported methods ») : PUT sur `versions/` (hors
        # http_method_names, historique immuable ADOC17) répondait 415 car le
        # garde « objet JSON » lisait le corps multipart avant le 405 de DRF.
        resp = self.api.put(f'{BASE}versions/', {'document': '0'},
                            format='multipart')
        self.assertEqual(resp.status_code, 405, resp.content)
        self.assertNotIn('PUT', resp['Allow'])
        resp = self.api.patch(f'{BASE}versions/', {}, format='json')
        self.assertEqual(resp.status_code, 405, resp.content)
        # PUT sur une route de LISTE (aucun gestionnaire) : 405 aussi.
        resp = self.api.put(f'{BASE}cabinets/', {'nom': 'X'},
                            format='multipart')
        self.assertEqual(resp.status_code, 405, resp.content)
        # Une méthode SERVIE garde le 400 « Objet JSON attendu ».
        resp = self.api.post(f'{BASE}cabinets/', [1], format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_lien_vers_cible_introuvable_404(self):
        doc = self.api.post(f'{BASE}documents/', {
            'folder': self.folder.pk, 'nom': 'd.pdf'}, format='json')
        self.assertEqual(doc.status_code, 201, doc.content)
        resp = self.api.post(f'{BASE}liens/', {
            'document': doc.data['id'], 'model': 'crm.lead', 'id': 999999},
            format='json')
        self.assertEqual(resp.status_code, 404, resp.content)

    def test_schema_ged_et_records_se_genere(self):
        from drf_spectacular.generators import SchemaGenerator
        from django.urls import include, path

        from apps.ged import urls as ged_urls
        from apps.records import urls as records_urls

        generateur = SchemaGenerator(patterns=[
            path('api/django/ged/', include(ged_urls)),
            path('api/django/records/', include(records_urls)),
        ])
        schema = generateur.get_schema(request=None, public=True)
        chemins = schema['paths']
        self.assertIn('/api/django/ged/documents/{id}/tagger/', chemins)
        post = chemins['/api/django/ged/documents/{id}/tagger/']['post']
        self.assertIn('requestBody', post)
        liste = chemins['/api/django/ged/documents/']['get']
        noms = {p['name'] for p in liste['parameters']}
        self.assertTrue({'folder', 'coffre', 'tag', 'statut'} <= noms, noms)


class Enf11FuzzGedParametresTests(TestCase):
    """ERR-ENF11-FUZZ-GED — paramètres de requête stricts (api-fuzz « accepted
    schema-violating request ») : vide / illisible / hors bornes = 400."""

    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='enf11-ged-q', defaults={'nom': 'ENF11 GED Q'})[0]
        self.admin = User.objects.create_user(
            username='enf11-ged-q-admin', password='x', company=self.co,
            role_legacy='admin')
        self.cab = Cabinet.objects.create(company=self.co, nom='C')
        self.folder = Folder.objects.create(
            company=self.co, cabinet=self.cab, nom='R')
        self.api = auth(self.admin)

    def test_dates_vides_400(self):
        for route in ('analytique/', 'demandes-signature/tableau-bord/'):
            for param in ('date_debut', 'date_fin'):
                resp = self.api.get(f'{BASE}{route}?{param}=')
                self.assertEqual(resp.status_code, 400, (route, resp.content))
            resp = self.api.get(f'{BASE}{route}?date_fin=2026-01-31')
            self.assertEqual(resp.status_code, 200, (route, resp.content))

    def test_filtres_identifiant_vides_ou_illisibles_400(self):
        for route, param in (
                ('dossiers/', 'parent'), ('dossiers/', 'cabinet'),
                ('tags/', 'parent'), ('documents/', 'folder'),
                ('documents/', 'coffre'), ('documents/', 'tag'),
                ('documents/', 'proprietaire'), ('documents/', 'contact')):
            for valeur in ('', 'abc'):
                resp = self.api.get(f'{BASE}{route}?{param}={valeur}')
                self.assertEqual(
                    resp.status_code, 400, (route, param, valeur, resp.content))

    def test_filtres_identifiant_valides(self):
        resp = self.api.get(f'{BASE}dossiers/?parent=null')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['count'], 1)
        resp = self.api.get(f'{BASE}dossiers/?cabinet={self.cab.pk}')
        self.assertEqual(resp.data['count'], 1)
        # Un entier hors plage 32 bits n'existe pas : liste vide, jamais 500.
        resp = self.api.get(f'{BASE}dossiers/?cabinet=99999999999999999999')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['count'], 0)
        resp = self.api.get(f'{BASE}tags/?parent=null')
        self.assertEqual(resp.status_code, 200, resp.content)

    def test_limites_k_et_limit_bornees(self):
        for route, param in (('documents/docqa/', 'k'),
                             ('mes-recents/', 'limit')):
            for valeur in ('', 'null', '0', '51', '-1'):
                resp = self.api.get(f'{BASE}{route}?{param}={valeur}')
                self.assertEqual(
                    resp.status_code, 400, (route, valeur, resp.content))
            resp = self.api.get(f'{BASE}{route}?{param}=5')
            self.assertEqual(resp.status_code, 200, (route, resp.content))

    def test_permissions_effectives_csv_erreur_en_json(self):
        # `?format=csv` choisit le moteur CSV avant la vue : l'erreur 404 est
        # un corps JSON et l'annonce (Content-Type documenté application/json).
        for route in ('dossiers/999999/permissions-effectives/',
                      'documents/999999/permissions-effectives/'):
            resp = self.api.get(f'{BASE}{route}?format=csv')
            self.assertEqual(resp.status_code, 404, resp.content)
            self.assertTrue(
                resp['Content-Type'].startswith('application/json'),
                resp['Content-Type'])
        resp = self.api.get(
            f'{BASE}dossiers/{self.folder.pk}/permissions-effectives/'
            '?format=csv')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(resp['Content-Type'].startswith('text/csv'))


class Enf11FuzzGedCorpsTests(TestCase):
    """ERR-ENF11-FUZZ-GED — corps JSON des actions lues à la main, validés par
    sérialiseur (le schéma OpenAPI = le comportement) : 500 -> 400, données
    invalides refusées, refus d'état -> 409."""

    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='enf11-ged-c', defaults={'nom': 'ENF11 GED C'})[0]
        self.admin = User.objects.create_user(
            username='enf11-ged-c-admin', password='x', company=self.co,
            role_legacy='admin')
        self.cab = Cabinet.objects.create(company=self.co, nom='C')
        self.folder = Folder.objects.create(
            company=self.co, cabinet=self.cab, nom='R')
        self.doc = Document.objects.create(
            company=self.co, folder=self.folder, nom='d.pdf')
        self.api = auth(self.admin)

    def _post(self, route, corps):
        return self.api.post(f'{BASE}{route}', corps, format='json')

    def test_modele_document_sections_null_accepte(self):
        """CI #997 fuzz — ``sections: null`` (publié nullable) vaut « aucune
        section » : 201, plus « Ce champ ne peut être nul »."""
        resp = self._post('modeles-document/', {
            'nom': 'Modèle vide', 'description': '', 'categorie': '',
            'corps_html': '', 'sections': None, 'cabinet_cible': '',
            'dossier_cible': '', 'actif': False})
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.json()['sections'], [])

    def test_dossier_parent_autre_cabinet_404(self):
        """CI #997 fuzz — un parent d'un AUTRE cabinet (ou hors société) est un
        objet inexistant pour la requête : 404 nommant ``parent``, plus 400."""
        autre_cab = Cabinet.objects.create(company=self.co, nom='C2')
        autre_dossier = Folder.objects.create(
            company=self.co, cabinet=autre_cab, nom='R2')
        resp = self._post('dossiers/', {
            'cabinet': self.cab.pk, 'parent': autre_dossier.pk, 'nom': 'X'})
        self.assertEqual(resp.status_code, 404, resp.content)
        self.assertIn('parent', resp.json())

    def test_operations_lot_corps_strict(self):
        route = 'documents/operations-lot/'
        for corps in (
                {'documents': [self.doc.pk], 'operation': 'inconnue'},
                {'documents': ['a'], 'operation': 'corbeille'},
                {'documents': [], 'operation': 'corbeille'},
                {'documents': [self.doc.pk], 'operation': 'tagger',
                 'params': {'tag': []}},
                {'documents': [self.doc.pk], 'operation': 'deplacer',
                 'params': {}},
                {'documents': [self.doc.pk], 'operation': 'corbeille',
                 'params': 'x'},
                {'documents': [self.doc.pk], 'operation': 'demander_signature',
                 'params': {'signataire_nom': 'x' * 300}}):
            resp = self._post(route, corps)
            self.assertEqual(resp.status_code, 400, (corps, resp.content))
        resp = self._post(route, {
            'documents': [self.doc.pk], 'operation': 'corbeille'})
        self.assertEqual(resp.status_code, 200, resp.content)

    def test_demande_signature_texte_trop_long_ou_nul_400(self):
        base = {'document': self.doc.pk, 'signataire_nom': 'Ali',
                'signataire_email': 'ali@example.com'}
        for modif in ({'signataire_nom': 'x' * 256},
                      {'signataire_nom': 'a' + chr(0)},
                      {'signataire_email': 'pas-un-courriel'},
                      {'signataire_email': 5},
                      {'document': 2 ** 40}):
            resp = self._post('demandes-signature/', {**base, **modif})
            self.assertEqual(resp.status_code, 400, (modif, resp.content))

    def test_legal_hold_corps_strict(self):
        for corps in ({'document': self.doc.pk, 'motif': None},
                      {'document': str(self.doc.pk)},
                      {'document': 2 ** 40}, {}):
            resp = self._post('legal-holds/', corps)
            self.assertEqual(resp.status_code, 400, (corps, resp.content))
        resp = self._post(f'documents/{self.doc.pk}/placer-legal-hold/',
                          {'motif': None})
        self.assertEqual(resp.status_code, 400, resp.content)
        resp = self._post('legal-holds/', {'document': self.doc.pk})
        self.assertEqual(resp.status_code, 201, resp.content)

    def test_archiver_legalement_corps_et_conflit(self):
        route = f'documents/{self.doc.pk}/archiver-legalement/'
        for corps in ({'motif': None}, {'retain_until': ''},
                      {'retain_until': 'null'}, {'retain_until': '2026-1-1'}):
            resp = self._post(route, corps)
            self.assertEqual(resp.status_code, 400, (corps, resp.content))
        with mock.patch('apps.records.storage.fetch_attachment',
                        return_value=(b'abc', None)):
            resp = self._post(route, {'retain_until': None})
            self.assertEqual(resp.status_code, 201, resp.content)
            # Déjà archivé : conflit d'état (409), pas une saisie invalide.
            resp = self._post(route, {})
            self.assertEqual(resp.status_code, 409, resp.content)
            resp = self._post('archivages-legaux/', {'document': self.doc.pk})
            self.assertEqual(resp.status_code, 409, resp.content)

    def test_disposition_corps_strict_et_lot_non_eligible_409(self):
        for corps in ({'libelle': 'x', 'documents': [{}]},
                      {'libelle': 'x', 'documents': ['a']},
                      {'libelle': 'x', 'documents': []},
                      {'libelle': 'x', 'documents': [self.doc.pk],
                       'action': 'autre'},
                      {'libelle': 'x' * 201, 'documents': [self.doc.pk]}):
            resp = self._post('demandes-disposition/', corps)
            self.assertEqual(resp.status_code, 400, (corps, resp.content))
        resp = self._post('demandes-disposition/', {
            'libelle': 'x', 'action': 'archiver',
            'documents': [self.doc.pk + 1000]})
        self.assertEqual(resp.status_code, 409, resp.content)

    def test_textes_trop_longs_ou_nuls_400_sans_stockage(self):
        # `nom` > 255 / NUL faisaient lever DataError (500) APRÈS le stockage.
        fichier = io.BytesIO(b'%PDF-1.4 x')
        fichier.name = 'a.pdf'
        for nom in ('x' * 256, 'a' + chr(0)):
            fichier.seek(0)
            with mock.patch('apps.ged.views.store_attachment') as stockage:
                resp = self.api.post(
                    f'{BASE}documents/televerser/',
                    {'folder': self.folder.pk, 'nom': nom, 'file': fichier},
                    format='multipart')
            self.assertEqual(resp.status_code, 400, resp.content)
            stockage.assert_not_called()
        resp = self._post(f'documents/{self.doc.pk}/planifier/', {
            'libelle': 'x' * 201, 'echeance': '2030-01-01'})
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_import_masse_nom_trop_long_est_une_erreur_de_ligne(self):
        # Un nom > 255 (ou un NUL) dans le CSV faisait lever DataError (500) ;
        # c'est désormais une erreur de LIGNE, le reste de l'import continue.
        from django.core.files.uploadedfile import SimpleUploadedFile
        lf = chr(10)
        contenu = lf.join(['nom,description', 'Bon,ok', 'y' * 300 + ',trop long', '']).encode('utf-8')
        resp = self.api.post(f'{BASE}documents/import-masse/', {
            'folder': self.folder.pk,
            'csv': SimpleUploadedFile('m.csv', contenu, 'text/csv')},
            format='multipart')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.data['crees'], 1)
        self.assertEqual(resp.data['erreurs'], [
            {'ligne': 2, 'detail': 'Nom : 255 caractères au plus.'}])

    def test_ci997_listes_et_url_declarees(self):
        """CI #997 api-fuzz : ``actions`` / ``approbateurs`` publient un tableau
        (null refusé en 400), ``url_externe`` publie son motif http(s)."""
        import re

        from core.champs_stricts import MOTIF_URL_HTTP
        cg = {'field': 'nom', 'operator': 'eq', 'value': 'x'}
        for route, corps, champ in (
                ('regles-dossier/', {'folder': self.folder.pk, 'nom': 'r',
                                     'condition_group': cg, 'actions': None},
                 'actions'),
                ('regles-approbation/', {'libelle': 'r', 'condition_group': cg,
                                         'approbateurs': None},
                 'approbateurs')):
            resp = self._post(route, corps)
            self.assertEqual(resp.status_code, 400, resp.content)
            self.assertIn(champ, resp.json())
        self.assertEqual(self._post('regles-approbation/', {
            'libelle': 'r', 'condition_group': cg,
            'approbateurs': [self.admin.pk]}).status_code, 201)
        # Tout ce que le motif publié autorise est accepté par le serveur.
        for url in ('', 'http://a.bc', 'https://abcdefghij.klmnopqrst/a/b.c-d_e~'):
            self.assertTrue(re.match(MOTIF_URL_HTTP, url), url)
            resp = self._post('documents/', {
                'folder': self.folder.pk, 'nom': 'doc-lien', 'url_externe': url})
            self.assertEqual(resp.status_code, 201, (url, resp.content))
        self.assertFalse(re.match(MOTIF_URL_HTTP, '0' * 2000))
        resp = self._post('documents/', {
            'folder': self.folder.pk, 'nom': 'x', 'url_externe': '0' * 50})
        self.assertEqual(resp.status_code, 400, resp.content)


class Enf11FuzzGedTour2Tests(TestCase):
    """ERR-ENF11-FUZZ-GED (nocturne 13/10) — refus d'état en 409, doublons en
    409, libellés nuls servis sur un PATCH, règles de corps publiées."""

    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='enf11-ged-t2', defaults={'nom': 'ENF11 GED T2'})[0]
        self.admin = User.objects.create_user(
            username='enf11-ged-t2-admin', password='x', company=self.co,
            role_legacy='admin')
        self.cab = Cabinet.objects.create(company=self.co, nom='C')
        self.folder = Folder.objects.create(
            company=self.co, cabinet=self.cab, nom='R')
        self.api = auth(self.admin)

    def test_patch_dossier_sert_parent_nom_nul(self):
        resp = self.api.patch(f'{BASE}dossiers/{self.folder.pk}/', {},
                              format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertIn('parent_nom', resp.data)
        self.assertIsNone(resp.data['parent_nom'])

    def test_cycle_vie_meme_statut_409_statut_inconnu_400(self):
        doc = Document.objects.create(
            company=self.co, folder=self.folder, nom='D')
        url = f'{BASE}documents/{doc.pk}/cycle-vie/'
        resp = self.api.post(url, {'statut': doc.statut}, format='json')
        self.assertEqual(resp.status_code, 409, resp.content)
        resp = self.api.post(url, {'statut': 'inconnu'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_routage_doublon_409(self):
        corps = {'source': 'hypothese_interne', 'cabinet_cible': self.cab.pk,
                 'dossier_cible': 'Interne'}
        premier = self.api.post(f'{BASE}routages-documentaires/', corps,
                                format='json')
        self.assertEqual(premier.status_code, 201, premier.content)
        second = self.api.post(f'{BASE}routages-documentaires/', corps,
                               format='json')
        self.assertEqual(second.status_code, 409, second.content)

    def test_regles_publiees_au_schema(self):
        from drf_spectacular.generators import SchemaGenerator
        from django.urls import include, path

        from apps.ged import urls as ged_urls

        schema = SchemaGenerator(patterns=[
            path('api/django/ged/', include(ged_urls)),
        ]).get_schema(request=None, public=True)
        chemins = schema['paths']
        pdf = chemins['/api/django/ged/demandes-signature/{id}/pdf-signe/']
        self.assertIn('409', pdf['get']['responses'])
        acl = chemins['/api/django/ged/acls/']['post']['requestBody']
        corps = acl['content']['application/json']['schema']
        self.assertIn('oneOf', corps['allOf'][1]['allOf'][0])
        self.assertIn('anyOf', corps['allOf'][1]['allOf'][1])

    def test_ids_inconnus_404_meme_corps(self):
        """ERR-ENF11-FUZZ-GED (nocturnes 11-14/10) — un id bien formé qui ne
        désigne rien (``0`` compris) répond 404 : FK des sérialiseurs
        (``IdInconnu404Mixin``) et ids lus à la main (tagger, restaurer,
        creer-multi), au lieu d'un 400 « requis » / « objet inexistant »."""
        doc = Document.objects.create(
            company=self.co, folder=self.folder, nom='D')
        for route, corps, champ in (
                ('documents/', {'folder': 0, 'nom': 'X'}, 'folder'),
                ('documents/', {'folder': 999999, 'nom': 'X'}, 'folder'),
                ('tag-assignments/', {'document': 0, 'tag': 0}, 'document'),
                ('partages/', {'document': 0}, 'document'),
                ('depots-publics/', {'folder': 0}, 'folder'),
                ('annotations/', {'version': 0}, 'version'),
                (f'documents/{doc.pk}/tagger/', {'tag': 0}, 'tag'),
                (f'documents/{doc.pk}/restaurer/', {'version': 0}, 'version'),
                ('demandes-signature/creer-multi/', {
                    'document': 0, 'destinataires': [{'nom': 'A'}]},
                 'document')):
            resp = self.api.post(f'{BASE}{route}', corps, format='json')
            self.assertEqual(resp.status_code, 404, resp.content)
            self.assertIn(champ, resp.data)
        # Une erreur d'une autre nature, même mêlée, garde le 400.
        resp = self.api.post(f'{BASE}documents/', {'folder': 0},
                             format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_groupe_conditions_publie_et_valide_au_champ(self):
        """ERR-ENF11-FUZZ-GED — ``condition_group`` obligatoire à la création,
        publié avec sa structure ``core.rules`` et validé aussi en PATCH."""
        url = f'{BASE}regles-approbation/'
        resp = self.api.post(url, {'libelle': 'R'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn('condition_group', resp.data)
        ok = self.api.post(url, {'libelle': 'R', 'condition_group': {
            'field': 'nom', 'operator': 'eq', 'value': 'x'}}, format='json')
        self.assertEqual(ok.status_code, 201, ok.content)
        resp = self.api.patch(f"{url}{ok.data['id']}/",
                              {'condition_group': {}}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_regles_de_corps_et_motif_sans_nul_publies(self):
        from drf_spectacular.generators import SchemaGenerator
        from django.urls import include, path

        from apps.ged import urls as ged_urls
        from core.champs_stricts import MOTIF_NON_BLANC_SANS_NUL

        schema = SchemaGenerator(patterns=[
            path('api/django/ged/', include(ged_urls)),
        ]).get_schema(request=None, public=True)

        def corps(route):
            return schema['paths'][route]['post']['requestBody']['content'][
                'application/json']['schema']['allOf'][1]

        self.assertIn('oneOf', corps('/api/django/ged/coffres/'))
        multi = corps('/api/django/ged/demandes-signature/creer-multi/')
        self.assertEqual(
            multi['properties']['destinataires']['minItems'], 1)
        self.assertIn('not', multi['properties']['destinataires'])
        composants = schema['components']['schemas']
        self.assertEqual(
            composants['ModeleDocumentRequest']['properties']['nom']['pattern'],
            MOTIF_NON_BLANC_SANS_NUL)
        self.assertIn('anyOf', composants['RegleApprobationGedRequest'][
            'properties']['condition_group'])


class Ci997FuzzGedTour3Tests(TestCase):
    """CI #997 (api-fuzz sur toute l'API) — GED : 500 sur corps non objet,
    paramètres énumérés stricts, corps déclarés exacts, refus d'état en 409."""

    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='ci997-ged-t3', defaults={'nom': 'CI997 GED T3'})[0]
        self.admin = User.objects.create_user(
            username='ci997-ged-t3-admin', password='x', company=self.co,
            role_legacy='admin')
        self.cab = Cabinet.objects.create(company=self.co, nom='C')
        self.folder = Folder.objects.create(
            company=self.co, cabinet=self.cab, nom='R')
        self.doc = Document.objects.create(
            company=self.co, folder=self.folder, nom='D')
        self.api = auth(self.admin)

    def _post(self, route, corps):
        return self.api.post(f'{BASE}{route}', corps, format='json')

    def test_operations_lot_corps_non_objet_400_pas_500(self):
        for corps in ([None, None], [], 'x', None):
            resp = self._post('documents/operations-lot/', corps)
            self.assertEqual(resp.status_code, 400, (corps, resp.content))

    def test_parametres_enumeres_hors_liste_400_nommant_le_parametre(self):
        for route, nom in (
                ('documents/?statut=AAA', 'statut'),
                ('partages/?actif=AAA', 'actif'),
                ('legal-holds/?actif=AAA', 'actif'),
                ('politiques-retention/?actif=AAA', 'actif'),
                ('modeles-document/?actif=AAA', 'actif'),
                ('demandes-approbation/?en_attente=AAA', 'en_attente'),
                ('validations-ocr/?en_attente=AAA', 'en_attente'),
                ('liens/?model=', 'model')):
            resp = self.api.get(f'{BASE}{route}')
            self.assertEqual(resp.status_code, 400, (route, resp.content))
            self.assertIn(nom, resp.json(), route)
        tag = self._post('tags/', {'nom': 'T'}).json()['id']
        resp = self.api.get(f'{BASE}tags/{tag}/documents/?descendants=AAA')
        self.assertEqual(resp.status_code, 400, resp.content)
        for route in ('documents/?statut=brouillon', 'partages/?actif=true',
                      'legal-holds/?actif=0', 'politiques-retention/?actif=1',
                      'modeles-document/?actif=false',
                      'demandes-approbation/?en_attente=1',
                      'validations-ocr/?en_attente=true',
                      f'tags/{tag}/documents/?descendants=1'):
            resp = self.api.get(f'{BASE}{route}')
            self.assertEqual(resp.status_code, 200, (route, resp.content))

    def test_slug_tag_vide_derive_du_nom_et_motif_publie(self):
        resp = self._post('tags/', {'nom': 'Contrats', 'slug': ''})
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.json()['slug'], 'contrats')
        for slug in (' a', 'a b', 'é', 0):
            resp = self._post('tags/', {'nom': 'X', 'slug': slug})
            self.assertEqual(resp.status_code, 400, (slug, resp.content))

    def test_feuille_de_condition_blanche_400(self):
        blanche = {'field': '\f', 'operator': 'eq'}
        for route, corps in (
                ('regles-dossier/', {'folder': self.folder.pk, 'nom': 'r',
                                     'condition_group': blanche}),
                ('regles-approbation/', {'libelle': 'r',
                                         'condition_group': blanche}),
                ('regles-approbation/', {'libelle': 'r', 'condition_group': {
                    'op': 'and', 'conditions': [blanche]}})):
            resp = self._post(route, corps)
            self.assertEqual(resp.status_code, 400, (corps, resp.content))
            self.assertIn('condition_group', resp.json())

    def test_lien_document_zero_404_et_cible_illisible_400(self):
        from apps.crm.models import Client
        client = Client.objects.create(company=self.co, nom='Client')
        resp = self._post('liens/', {
            'document': 0, 'model': 'crm.client', 'id': client.pk})
        self.assertEqual(resp.status_code, 404, resp.content)
        resp = self.api.get(f'{BASE}liens/?model=crm.client&id=abc')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_deplacer_dossier_sous_lui_meme_409(self):
        resp = self._post(f'dossiers/{self.folder.pk}/deplacer/', {
            'parent': self.folder.pk})
        self.assertEqual(resp.status_code, 409, resp.content)
        self.assertIn('detail', resp.json())

    def test_type_champ_signature_decimaux_en_chaine(self):
        base = {'code': 'c997', 'libelle': 'L', 'mode_saisie': 'texte'}
        for corps in ({**base, 'hauteur_defaut': 0},
                      {**base, 'largeur_defaut': 2.5}):
            resp = self._post('types-champ-signature/', corps)
            self.assertEqual(resp.status_code, 400, (corps, resp.content))
        resp = self._post('types-champ-signature/', {
            **base, 'largeur_defaut': '0', 'hauteur_defaut': '5.5'})
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.json()['hauteur_defaut'], '5.50')

    def test_champ_signature_fk_inconnues_404(self):
        resp = self._post('champs-signature/', {
            'demande': None, 'modele': 999999, 'type_champ': 'signature',
            'type_champ_ref': 999999, 'page': 0})
        self.assertEqual(resp.status_code, 404, resp.content)
        self.assertIn('modele', resp.json())

    def test_vue_enregistree_criteres_null_lu_comme_vide(self):
        resp = self._post('vues/', {'nom': 'V', 'criteres': None,
                                    'partagee': True})
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.json()['criteres'], {})

    def test_modele_document_sections_liste_d_objets(self):
        base = {'nom': 'M', 'corps_html': ''}
        for sections in ({}, '', [{'conditions': None}],
                         [{'conditions': []}], [1]):
            resp = self._post('modeles-document/', {**base, 'sections': sections})
            self.assertEqual(resp.status_code, 400, (sections, resp.content))
        for sections in (None, [], [{'titre': 'T'}], [{'conditions': {}}]):
            resp = self._post('modeles-document/', {**base, 'sections': sections})
            self.assertEqual(resp.status_code, 201, (sections, resp.content))

    def test_document_custom_data_objet_seulement(self):
        resp = self._post('documents/', {
            'folder': self.folder.pk, 'nom': 'x', 'custom_data': [None, None]})
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn('custom_data', resp.json())
        resp = self._post('documents/', {
            'folder': self.folder.pk, 'nom': 'x', 'custom_data': {}})
        self.assertEqual(resp.status_code, 201, resp.content)

    def test_politique_retention_cible_unique_refusee_et_publiee(self):
        resp = self._post('politiques-retention/', {
            'nom': 'P', 'cabinet': self.cab.pk, 'folder': self.folder.pk,
            'duree_conservation_jours': 1, 'action_echeance': 'signaler'})
        self.assertEqual(resp.status_code, 400, resp.content)
        from django.urls import include, path
        from drf_spectacular.generators import SchemaGenerator

        from apps.ged import urls as ged_urls
        schema = SchemaGenerator(patterns=[
            path('api/django/ged/', include(ged_urls)),
        ]).get_schema(request=None, public=True)
        chemins = schema['paths']
        corps = chemins['/api/django/ged/politiques-retention/']['post'][
            'requestBody']['content']['application/json']['schema']
        self.assertIn('not', corps['allOf'][1])
        for route in ('scan-lot', 'assembler-photos', 'deposer-lot-scans-separe'):
            multipart = chemins[f'/api/django/ged/documents/{route}/']['post'][
                'requestBody']['content']['multipart/form-data']['schema']
            composant = schema['components']['schemas'][
                multipart['$ref'].rsplit('/', 1)[1]]
            liste = composant['properties'].get('files') or composant[
                'properties']['photos']
            self.assertEqual(liste['minItems'], 1, route)
        ocr = schema['components']['schemas']['GedOcrPieceCorpsRequest']
        self.assertTrue(ocr['properties']['type_piece']['nullable'])


class Ci997FuzzGedTour4Tests(TestCase):
    """CI #997 (2) — dépôts GED : le schéma publié dit ce que la vue accepte
    (``params`` selon ``operation``, textes bornés) et les fichiers minimaux que
    le harnais fuzz envoie (PDF, CSV d'une ligne) sont acceptés 201."""

    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='ci997-ged-t4', defaults={'nom': 'CI997 GED T4'})[0]
        self.admin = User.objects.create_user(
            username='ci997-ged-t4-admin', password='x', company=self.co,
            role_legacy='admin')
        self.cab = Cabinet.objects.create(company=self.co, nom='C')
        self.folder = Folder.objects.create(
            company=self.co, cabinet=self.cab, nom='R')
        self.doc = Document.objects.create(
            company=self.co, folder=self.folder, nom='D')
        self.api = auth(self.admin)

    def _multipart(self, route, corps):
        return self.api.post(f'{BASE}{route}', corps, format='multipart')

    def test_operations_lot_params_exiges_selon_l_operation(self):
        for operation in ('tagger', 'detaguer', 'deplacer'):
            resp = self.api.post(f'{BASE}documents/operations-lot/', {
                'documents': [self.doc.pk], 'operation': operation,
                'params': {}}, format='json')
            self.assertEqual(resp.status_code, 400, (operation, resp.content))
        resp = self.api.post(f'{BASE}documents/operations-lot/', {
            'documents': [self.doc.pk], 'operation': 'corbeille',
            'params': {}}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)

    def test_schema_publie_params_par_operation_et_textes_bornes(self):
        from django.urls import include, path
        from drf_spectacular.generators import SchemaGenerator

        from apps.ged import urls as ged_urls
        schema = SchemaGenerator(patterns=[
            path('api/django/ged/', include(ged_urls)),
        ]).get_schema(request=None, public=True)
        composants = schema['components']['schemas']
        branches = composants['GedOperationsLotCorpsRequest']['anyOf']
        par_operation = {}
        for branche in branches:
            operations = branche['properties']['operation']['anyOf'][0]['enum']
            for operation in operations:
                par_operation[operation] = branche
        self.assertEqual(set(par_operation), {
            'tagger', 'detaguer', 'deplacer', 'corbeille', 'telecharger_zip',
            'partager', 'demander_signature', 'demander_revue'})
        self.assertEqual(
            par_operation['tagger']['properties']['params']['required'], ['tag'])
        self.assertEqual(par_operation['deplacer']['properties']['params'][
            'required'], ['folder'])
        self.assertIn('params', par_operation['detaguer']['required'])
        self.assertNotIn('params', par_operation['corbeille']['required'])
        nom = composants['GedTeleverserCorpsRequest']['properties']['nom']
        self.assertEqual(nom['maxLength'], 255)
        base = composants['GedLotScansSepareCorpsRequest']['properties'][
            'nom_base']
        self.assertEqual(base['maxLength'], 200)

    def test_pdf_minimal_accepte_au_televerser_et_au_scan_lot(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        pdf = b'%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n'
        resp = self._multipart('documents/televerser/', {
            'folder': self.folder.pk,
            'file': SimpleUploadedFile('file', pdf)})
        self.assertEqual(resp.status_code, 201, resp.content)
        resp = self._multipart('documents/scan-lot/', {
            'folder': self.folder.pk,
            'files': [SimpleUploadedFile('files', pdf),
                      SimpleUploadedFile('files', pdf)]})
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(len(resp.json()['documents']), 2)

    def test_csv_d_une_ligne_accepte_a_l_import_en_masse(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        resp = self._multipart('documents/import-masse/', {
            'folder': self.folder.pk,
            'csv': SimpleUploadedFile(
                'csv', b'nom,description\r\nFuzz,Import\r\n')})
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.json()['crees'], 1)
