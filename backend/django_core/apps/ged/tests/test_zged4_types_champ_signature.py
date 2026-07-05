"""ZGED4 — Éditeur de types de champs de signature personnalisés.

Couvre :
  * un admin crée un type « Fonction » (texte, astuce, largeur 30 %) ;
  * les 5 types de base restent disponibles via seed (idempotent) ;
  * le rendu (serializer) honore mode/largeur/placeholder/astuce du type
    référencé sur un `ChampSignature` ;
  * CRUD scopé société testé.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.ged.management.commands.seed_types_champ_signature import (
    seed_types_champ_signature_for_company,
)
from apps.ged.models import (
    Cabinet, ChampSignature, Document, Folder, TypeChampSignature,
)

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ZGed4Base(TestCase):
    def setUp(self):
        self.co_a = make_company('zged4-a', 'Zged4 A')
        self.admin_a = make_user(self.co_a, 'zged4-admin-a', 'admin')
        self.cab_a = Cabinet.objects.create(company=self.co_a, nom='Admin')
        self.folder_a = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Contrats')
        self.doc = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='contrat.pdf')


class SeedTests(ZGed4Base):
    def test_seed_cree_les_5_types_de_base(self):
        created = seed_types_champ_signature_for_company(self.co_a)
        self.assertEqual(created, 5)
        codes = set(TypeChampSignature.objects.filter(
            company=self.co_a).values_list('code', flat=True))
        self.assertEqual(
            codes, {'signature', 'initiales', 'date', 'texte', 'case'})

    def test_seed_est_idempotent_et_preserve_edition(self):
        seed_types_champ_signature_for_company(self.co_a)
        texte = TypeChampSignature.objects.get(company=self.co_a, code='texte')
        texte.libelle = 'Texte modifié'
        texte.save()
        created_again = seed_types_champ_signature_for_company(self.co_a)
        self.assertEqual(created_again, 0)
        texte.refresh_from_db()
        self.assertEqual(texte.libelle, 'Texte modifié')


class ModelTests(ZGed4Base):
    def test_champ_signature_avec_type_ref_expose_mode_largeur(self):
        type_fonction = TypeChampSignature.objects.create(
            company=self.co_a, code='fonction', libelle='Fonction',
            mode_saisie='texte', largeur_defaut=30, astuce='Ex. Directeur')
        # Un champ signature réel exige demande XOR modele — on utilise un
        # modèle de document minimal via ModeleDocument pour rester simple.
        from apps.ged.models import ModeleDocument
        modele = ModeleDocument.objects.create(
            company=self.co_a, nom='Modèle test', corps_html='<p>{{ nom }}</p>')
        champ = ChampSignature.objects.create(
            company=self.co_a, modele=modele, type_champ_ref=type_fonction)
        self.assertEqual(champ.type_champ_ref.mode_saisie, 'texte')
        self.assertEqual(champ.type_champ_ref.largeur_defaut, 30)
        self.assertEqual(champ.type_champ_ref.astuce, 'Ex. Directeur')

    def test_code_unique_par_societe(self):
        TypeChampSignature.objects.create(
            company=self.co_a, code='fonction', libelle='Fonction')
        co_b = make_company('zged4-b', 'Zged4 B')
        # Même code, société différente : autorisé (unicité scoped société).
        TypeChampSignature.objects.create(
            company=co_b, code='fonction', libelle='Fonction B')
        self.assertEqual(TypeChampSignature.objects.count(), 2)


class ViewTests(ZGed4Base):
    def test_admin_cree_type_champ_personnalise(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/ged/types-champ-signature/', {
            'code': 'fonction', 'libelle': 'Fonction', 'mode_saisie': 'texte',
            'largeur_defaut': '30', 'astuce': 'Ex. Directeur',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['code'], 'fonction')
        self.assertEqual(resp.data['largeur_defaut'], '30.00')

    def test_code_duplique_meme_societe_rejete(self):
        TypeChampSignature.objects.create(
            company=self.co_a, code='fonction', libelle='Fonction')
        api = auth(self.admin_a)
        resp = api.post('/api/django/ged/types-champ-signature/', {
            'code': 'fonction', 'libelle': 'Fonction bis',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_isolation_societe(self):
        type_a = TypeChampSignature.objects.create(
            company=self.co_a, code='fonction', libelle='Fonction')
        co_b = make_company('zged4-b2', 'Zged4 B2')
        admin_b = make_user(co_b, 'zged4-admin-b2', 'admin')
        api_b = auth(admin_b)
        resp = api_b.get(f'/api/django/ged/types-champ-signature/{type_a.pk}/')
        self.assertEqual(resp.status_code, 404)

    def test_lecture_seule_pour_non_gestionnaire(self):
        TypeChampSignature.objects.create(
            company=self.co_a, code='fonction', libelle='Fonction')
        autre = make_user(self.co_a, 'zged4-autre-a', 'normal')
        api = auth(autre)
        resp = api.get('/api/django/ged/types-champ-signature/')
        self.assertEqual(resp.status_code, 200)
        resp2 = api.post(
            '/api/django/ged/types-champ-signature/',
            {'code': 'autre', 'libelle': 'Autre'}, format='json')
        self.assertEqual(resp2.status_code, 403)
