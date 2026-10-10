"""ADOC37 — garde de classe : aucune liste GED ouverte à tout rôle ne fuit un
document invisible pour l'utilisateur (coffre d'un collègue, ACL, corbeille).

Découverte par INTROSPECTION de `apps.ged.urls.router.registry` : chaque
viewset dont le modèle est Document / DocumentVersion ou porte une FK
`document` / `version` est appelé en GET liste par emp2 (rôle normal) ; une
liste qu'il ne peut pas lire (palier de gouvernance, 403) est exclue PAR SA
PERMISSION, jamais par une liste de noms. Oracle de non-vacuité : le
propriétaire du coffre (emp1) voit, lui, la ligne rattachée au document.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import FieldDoesNotExist
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ged import services
from apps.ged.models import (
    AclGed, AnnotationDocument, Cabinet, Coffre, DemandeApprobation, DemandeDocument,
    ChampSignature, DemandeSignatureDocument, Document, DocumentLien,
    DocumentTag, DocumentTagAssignment, DocumentVersion, FavoriGed, Folder,
    LegalHold, PlanificationDocument, SignataireDemande, ValidationOcrDocument,
)
from apps.ged.urls import router
from authentication.models import Company

User = get_user_model()
BASE = '/api/django/ged/'


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def _lignes(resp):
    data = resp.data
    if isinstance(data, dict) and 'results' in data:
        return data['results']
    return data if isinstance(data, list) else []


def _fk_vers(modele, nom):
    try:
        champ = modele._meta.get_field(nom)
    except FieldDoesNotExist:
        return False
    return bool(getattr(champ, 'is_relation', False))


def _fks_indirectes(modele):
    """ADOC173 — FK d'un modèle vers un modèle qui porte lui-même une FK
    `document` (intermédiaire) : ex. SignataireDemande -> DemandeSignatureDocument."""
    trouvees = []
    for champ in modele._meta.get_fields():
        if not (getattr(champ, 'many_to_one', False) and champ.concrete):
            continue
        cible = champ.related_model
        if cible is not None and _fk_vers(cible, 'document'):
            trouvees.append(champ)
    return trouvees


class GardeVisibiliteGed(TestCase):
    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='adoc37', defaults={'nom': 'ADOC37'})[0]
        self.emp1 = User.objects.create_user(
            username='adoc37-emp1', password='x', company=self.co,
            role_legacy='normal')
        self.emp2 = User.objects.create_user(
            username='adoc37-emp2', password='x', company=self.co,
            role_legacy='normal')
        cab = Cabinet.objects.create(company=self.co, nom='Cab')
        folder = Folder.objects.create(company=self.co, cabinet=cab, nom='R')
        coffre = Coffre.objects.create(
            company=self.co, nom='Coffre emp1', proprietaire=self.emp1)
        self.doc = Document.objects.create(
            company=self.co, folder=folder, coffre=coffre, nom='Paie emp1')
        self.version = DocumentVersion.objects.create(
            company=self.co, document=self.doc, version=1,
            file_key='attachments/paie.pdf', mime='application/pdf')
        AnnotationDocument.objects.create(
            company=self.co, version=self.version, type_annotation='note')
        DocumentLien.objects.create(
            company=self.co, document=self.doc,
            content_type=ContentType.objects.get_for_model(Folder),
            object_id=folder.pk)
        tag = DocumentTag.objects.create(company=self.co, nom='RH')
        DocumentTagAssignment.objects.create(
            company=self.co, document=self.doc, tag=tag)
        DemandeApprobation.objects.create(
            company=self.co, document=self.doc, demandeur=self.emp1)
        services.create_partage(
            document=self.doc, company=self.co, created_by=self.emp1)
        ValidationOcrDocument.objects.create(company=self.co, document=self.doc)
        PlanificationDocument.objects.create(
            company=self.co, document=self.doc, libelle='Relancer',
            echeance='2026-12-01')
        demande_sig = DemandeSignatureDocument.objects.create(
            company=self.co, document=self.doc, signataire_nom='S',
            signataire_email='s@example.com', created_by=self.emp1)
        SignataireDemande.objects.create(
            company=self.co, demande=demande_sig, nom='Signataire D',
            email='sd@example.com')
        ChampSignature.objects.create(
            company=self.co, demande=demande_sig, page=1, x=0.1, y=0.1,
            largeur=0.2, hauteur=0.1)
        # ADOC173 — document en corbeille : ses lignes sortent aussi des listes.
        doc_corbeille = Document.objects.create(
            company=self.co, folder=folder, nom='Corbeille')
        demande_corbeille = DemandeSignatureDocument.objects.create(
            company=self.co, document=doc_corbeille, signataire_nom='T',
            signataire_email='t@example.com', created_by=self.emp2)
        SignataireDemande.objects.create(
            company=self.co, demande=demande_corbeille, nom='Signataire C',
            email='sc@example.com')
        Document.objects.filter(pk=doc_corbeille.pk).update(
            supprime_le=timezone.now())
        self.demandes_invisibles = {demande_sig.pk, demande_corbeille.pk}
        DemandeDocument.objects.create(
            company=self.co, folder=folder, libelle='Paie', statut='soldee',
            document=self.doc)
        LegalHold.objects.create(company=self.co, document=self.doc,
                                 place_par=self.emp1, actif=True)
        archive = Document.objects.create(
            company=self.co, folder=folder, coffre=coffre, nom='Archive emp1')
        with mock.patch('apps.records.storage.fetch_attachment',
                        return_value=(b'abc', None)):
            services.archiver_legalement(archive, user=self.emp1)
        self.archive = archive
        FavoriGed.objects.create(company=self.co, utilisateur=self.emp2,
                                 document=self.doc)
        AclGed.objects.create(company=self.co, document=self.doc,
                              utilisateur=self.emp1, niveau='gestion')

    def _references(self, modele, ligne):
        ids_docs = {self.doc.pk, self.archive.pk}
        for champ in _fks_indirectes(modele):
            if champ.name == 'demande' and (
                    ligne.get('demande') in self.demandes_invisibles):
                return True
        if modele is Document:
            return ligne.get('id') in ids_docs
        if modele is DocumentVersion:
            return ligne.get('id') == self.version.pk
        return (ligne.get('document') in ids_docs
                or ligne.get('document_id') in ids_docs
                or ligne.get('version') == self.version.pk)

    def _fixture_attendue(self, modele):
        """Une liste rattachée par un intermédiaire n'est jugée « vide à tort »
        que si la fixture porte au moins une de ses lignes."""
        indirectes = _fks_indirectes(modele)
        direct = (_fk_vers(modele, 'document') or _fk_vers(modele, 'version')
                  or modele in (Document, DocumentVersion))
        if not indirectes or direct:
            return True
        return any(
            modele.objects.filter(**{f'{c.name}__in': self.demandes_invisibles}
                                  ).exists()
            for c in indirectes if c.name == 'demande')

    def test_aucune_liste_ne_fuit(self):
        fuites, vides, anormales = [], [], []
        routes_controlees = 0
        for prefixe, viewset, _base in router.registry:
            modele = getattr(getattr(viewset, 'queryset', None), 'model', None)
            if modele is None:
                continue
            if not (modele in (Document, DocumentVersion)
                    or _fk_vers(modele, 'document')
                    or _fk_vers(modele, 'version')
                    or _fks_indirectes(modele)):
                continue
            url = f'{BASE}{prefixe}/?page_size=200'
            resp = auth(self.emp2).get(url)
            if resp.status_code == 403:
                continue  # liste non ouverte à ce rôle (permission).
            if resp.status_code != 200:
                # ADOC173 — une 404/500 ne « saute » plus la garde.
                anormales.append((prefixe, resp.status_code))
                continue
            routes_controlees += 1
            if any(self._references(modele, ligne) for ligne in _lignes(resp)):
                fuites.append(prefixe)
            proprio = auth(self.emp1).get(url)
            voit = any(self._references(modele, ligne)
                       for ligne in _lignes(proprio))
            if (proprio.status_code == 200 and not voit
                    and self._fixture_attendue(modele)):
                vides.append(prefixe)
        self.assertEqual(anormales, [], f'Listes en erreur : {anormales}')
        self.assertGreaterEqual(routes_controlees, 8)
        self.assertEqual(fuites, [], f'Listes qui fuient : {fuites}')
        self.assertEqual(
            vides, [],
            f'Fixture absente (le propriétaire ne voit rien) : {vides}')
        favoris = auth(self.emp2).get(f'{BASE}mes-favoris/')
        self.assertNotIn(self.doc.pk,
                         [d['id'] for d in favoris.data['documents']])
        recents = auth(self.emp2).get(f'{BASE}mes-recents/')
        self.assertEqual(recents.status_code, 200)
        for cle in ('consultes', 'deposes'):
            self.assertNotIn(self.doc.pk, [d['id'] for d in recents.data[cle]])
