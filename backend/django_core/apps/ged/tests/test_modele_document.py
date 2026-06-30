"""GED27 — Modèles de documents (fusion/mailing → PDF WeasyPrint, hors /proposal).

Couvre :
  * CRUD du modèle scopé société (A ne voit/touche pas B) ;
  * société posée côté serveur (jamais lue du corps de requête) ;
  * fusion sûre des jetons `{{ champ }}` (substitution correcte ; jeton inconnu
    rendu vide ; aucune exécution de code arbitraire) ;
  * rendu PDF non vide (commence par %PDF) — via le service ET l'action `rendre` ;
  * dépôt en GED (action `generer`) idempotent par modèle ;
  * isolation société sur les actions de rendu (404 cross-société) ;
  * GED28 — classement automatique : le document généré atterrit dans le
    cabinet/dossier résolu depuis la règle du modèle (`cabinet_cible` /
    `dossier_cible` templaté par le contexte), auto-créé si absent ; dossier par
    défaut conservé sans cible ; isolation société du provisionnement.

`/proposal` (moteur premium de devis) n'est JAMAIS sollicité ici — GED27 est une
couche générique de documents internes, distincte (rule #4).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.ged import services
from apps.ged.models import Cabinet, Document, Folder, ModeleDocument

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


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data else data


class ModeleDocumentBase(TestCase):
    def setUp(self):
        self.co_a = make_company('mod-a', 'Modele A')
        self.co_b = make_company('mod-b', 'Modele B')
        self.admin_a = make_user(self.co_a, 'mod-admin-a', 'admin')
        self.admin_b = make_user(self.co_b, 'mod-admin-b', 'admin')


class FusionServiceTests(ModeleDocumentBase):
    """Substitution sûre des jetons de fusion (sans WeasyPrint)."""

    def test_fusion_substitue_les_jetons(self):
        html = services.fusionner_modele(
            "<p>Cher {{ nom }}, montant {{ montant }} MAD.</p>",
            {'nom': 'Alami', 'montant': '12 000'})
        self.assertIn('Cher Alami', html)
        self.assertIn('12 000 MAD', html)

    def test_jeton_inconnu_rendu_vide(self):
        # Un jeton sans valeur dans le contexte est rendu vide — jamais une fuite.
        html = services.fusionner_modele(
            "Bonjour {{ inconnu }}fin", {})
        # Le jeton inconnu est rendu vide (aucune fuite du nom de variable) ;
        # le texte littéral et son espace sont préservés.
        self.assertNotIn('inconnu', html)
        self.assertEqual(html.strip(), 'Bonjour fin')

    def test_pas_d_execution_de_code_arbitraire(self):
        # Le contexte est un dict de DONNÉES : une expression Python n'est jamais
        # évaluée — le moteur de gabarit n'exécute pas de code arbitraire.
        html = services.fusionner_modele(
            "{{ valeur }}", {'valeur': '7+7'})
        self.assertIn('7+7', html)
        self.assertNotIn('14', html)

    def test_corps_vide_donne_chaine_vide(self):
        self.assertEqual(services.fusionner_modele('', {'x': 1}), '')


class RenduPdfServiceTests(ModeleDocumentBase):
    """Rendu PDF réel via WeasyPrint (installé dans l'image prod)."""

    def test_rendre_modele_produit_un_pdf(self):
        modele = ModeleDocument.objects.create(
            company=self.co_a, nom='Attestation',
            corps_html="<p>Atteste que {{ nom }} est client.</p>")
        pdf = services.rendre_modele(modele, {'nom': 'Bennani'})
        self.assertTrue(pdf.startswith(b'%PDF'))
        self.assertGreater(len(pdf), 500)

    def test_generer_document_depose_en_ged_idempotent(self):
        modele = ModeleDocument.objects.create(
            company=self.co_a, nom='Courrier',
            corps_html="<p>Objet : {{ objet }}</p>")
        doc1, created1 = services.generer_document(
            modele, {'objet': 'Relance'},
            company=self.co_a, created_by=self.admin_a)
        self.assertTrue(created1)
        self.assertEqual(doc1.company_id, self.co_a.id)
        self.assertEqual(doc1.versions.count(), 1)
        version = doc1.versions.first()
        self.assertEqual(version.mime, 'application/pdf')
        # Idempotence : un second dépôt pour le même modèle ne duplique pas.
        doc2, created2 = services.generer_document(
            modele, {'objet': 'Relance'},
            company=self.co_a, created_by=self.admin_a)
        self.assertFalse(created2)
        self.assertEqual(doc1.id, doc2.id)

    def test_generer_refuse_modele_autre_societe(self):
        modele = ModeleDocument.objects.create(
            company=self.co_b, nom='X', corps_html='<p>{{ a }}</p>')
        with self.assertRaises(ValueError):
            services.generer_document(
                modele, {}, company=self.co_a, created_by=self.admin_a)


class ModeleDocumentApiTests(ModeleDocumentBase):
    """CRUD + actions de rendu via l'API REST (scopé société côté serveur)."""

    def test_create_pose_company_cote_serveur(self):
        api = auth(self.admin_a)
        # Même en tentant d'injecter une autre société dans le corps, elle est
        # ignorée : la société vient du serveur (TenantMixin).
        resp = api.post('/api/django/ged/modeles-document/', {
            'nom': 'Attestation', 'corps_html': '<p>{{ nom }}</p>',
            'company': self.co_b.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        modele = ModeleDocument.objects.get(pk=resp.data['id'])
        self.assertEqual(modele.company_id, self.co_a.id)

    def test_liste_scopee_societe(self):
        ModeleDocument.objects.create(company=self.co_a, nom='A1')
        ModeleDocument.objects.create(company=self.co_b, nom='B1')
        api = auth(self.admin_a)
        resp = api.get('/api/django/ged/modeles-document/')
        self.assertEqual(resp.status_code, 200)
        noms = {r['nom'] for r in rows(resp)}
        self.assertIn('A1', noms)
        self.assertNotIn('B1', noms)

    def test_retrieve_cross_societe_404(self):
        modele_b = ModeleDocument.objects.create(company=self.co_b, nom='B1')
        api = auth(self.admin_a)
        resp = api.get(f'/api/django/ged/modeles-document/{modele_b.id}/')
        self.assertEqual(resp.status_code, 404)

    def test_action_rendre_renvoie_un_pdf(self):
        modele = ModeleDocument.objects.create(
            company=self.co_a, nom='Attestation',
            corps_html='<p>Cher {{ nom }}</p>')
        api = auth(self.admin_a)
        resp = api.post(
            f'/api/django/ged/modeles-document/{modele.id}/rendre/',
            {'contexte': {'nom': 'Alami'}}, format='json')
        self.assertEqual(resp.status_code, 200, getattr(resp, 'data', resp))
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertTrue(resp.content.startswith(b'%PDF'))

    def test_action_rendre_contexte_invalide_400(self):
        modele = ModeleDocument.objects.create(
            company=self.co_a, nom='X', corps_html='<p>{{ a }}</p>')
        api = auth(self.admin_a)
        resp = api.post(
            f'/api/django/ged/modeles-document/{modele.id}/rendre/',
            {'contexte': 'pas-un-objet'}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_action_rendre_cross_societe_404(self):
        modele_b = ModeleDocument.objects.create(
            company=self.co_b, nom='B', corps_html='<p>{{ a }}</p>')
        api = auth(self.admin_a)
        resp = api.post(
            f'/api/django/ged/modeles-document/{modele_b.id}/rendre/',
            {'contexte': {}}, format='json')
        self.assertEqual(resp.status_code, 404)

    def test_action_generer_depose_en_ged(self):
        modele = ModeleDocument.objects.create(
            company=self.co_a, nom='Courrier',
            corps_html='<p>{{ objet }}</p>')
        api = auth(self.admin_a)
        resp = api.post(
            f'/api/django/ged/modeles-document/{modele.id}/generer/',
            {'contexte': {'objet': 'Bienvenue'}}, format='json')
        self.assertEqual(resp.status_code, 201, getattr(resp, 'data', resp))
        doc = Document.objects.get(pk=resp.data['document'])
        self.assertEqual(doc.company_id, self.co_a.id)


class ClassementServiceTests(ModeleDocumentBase):
    """GED28 — Classement automatique du document généré (`resoudre_classement`
    + `generer_document`). Le rendu PDF réel passe par WeasyPrint (image prod)."""

    def test_resoudre_classement_utilise_la_cible_du_modele(self):
        modele = ModeleDocument.objects.create(
            company=self.co_a, nom='Attestation',
            cabinet_cible='Attestations', dossier_cible='Clients')
        cab, fold = services.resoudre_classement(modele, {})
        self.assertEqual(cab, 'Attestations')
        self.assertEqual(fold, 'Clients')

    def test_resoudre_classement_dossier_templaté_depuis_le_contexte(self):
        # Le nom de dossier porte un jeton `{{ }}` résolu depuis le contexte.
        modele = ModeleDocument.objects.create(
            company=self.co_a, nom='Attestation',
            cabinet_cible='Attestations',
            dossier_cible='Attestations {{ annee }}')
        cab, fold = services.resoudre_classement(modele, {'annee': '2026'})
        self.assertEqual(cab, 'Attestations')
        self.assertEqual(fold, 'Attestations 2026')

    def test_resoudre_classement_retombe_sur_les_defauts_sans_cible(self):
        # Aucune cible (dossier vide) → on garde les défauts de l'appelant.
        modele = ModeleDocument.objects.create(
            company=self.co_a, nom='Sans cible',
            cabinet_cible='', dossier_cible='')
        cab, fold = services.resoudre_classement(
            modele, {}, cabinet_defaut='Modèles', folder_defaut='Mailing')
        self.assertEqual(cab, 'Modèles')
        self.assertEqual(fold, 'Mailing')

    def test_resoudre_classement_jeton_resolu_vide_retombe_sur_defaut(self):
        # Un dossier templaté qui se résout en chaîne vide retombe sur le défaut
        # (jamais un dossier au nom vide).
        modele = ModeleDocument.objects.create(
            company=self.co_a, nom='X',
            cabinet_cible='Docs', dossier_cible='{{ manquant }}')
        cab, fold = services.resoudre_classement(
            modele, {}, folder_defaut='Mailing')
        self.assertEqual(cab, 'Docs')
        self.assertEqual(fold, 'Mailing')

    def test_generer_document_classe_dans_la_cible_creee_si_absente(self):
        modele = ModeleDocument.objects.create(
            company=self.co_a, nom='Attestation',
            corps_html='<p>Atteste {{ nom }}</p>',
            cabinet_cible='Attestations',
            dossier_cible='Attestations {{ annee }}')
        # Le cabinet/dossier cibles n'existent pas encore.
        self.assertFalse(
            Cabinet.objects.filter(
                company=self.co_a, nom='Attestations').exists())
        doc, created = services.generer_document(
            modele, {'nom': 'Bennani', 'annee': '2026'},
            company=self.co_a, created_by=self.admin_a)
        self.assertTrue(created)
        # Le document a bien atterri dans le cabinet/dossier templaté, auto-créés.
        self.assertEqual(doc.folder.cabinet.nom, 'Attestations')
        self.assertEqual(doc.folder.nom, 'Attestations 2026')
        self.assertEqual(doc.folder.company_id, self.co_a.id)
        self.assertEqual(doc.folder.cabinet.company_id, self.co_a.id)

    def test_generer_document_sans_cible_garde_le_dossier_par_defaut(self):
        # Rétro-compatibilité : un modèle SANS cible (dossier vide) retombe sur
        # le dossier par défaut historique (« Modèles » / « Mailing »).
        modele = ModeleDocument.objects.create(
            company=self.co_a, nom='Mailing',
            corps_html='<p>{{ x }}</p>',
            cabinet_cible='', dossier_cible='')
        doc, created = services.generer_document(
            modele, {'x': '1'}, company=self.co_a, created_by=self.admin_a)
        self.assertTrue(created)
        self.assertEqual(doc.folder.cabinet.nom, 'Modèles')
        self.assertEqual(doc.folder.nom, 'Mailing')

    def test_generer_document_reutilise_le_dossier_cible_existant(self):
        # Idempotence du provisionnement : deux modèles vers la même cible
        # partagent le même cabinet/dossier (pas de doublon de dossier).
        modele1 = ModeleDocument.objects.create(
            company=self.co_a, nom='M1', corps_html='<p>{{ a }}</p>',
            cabinet_cible='Attestations', dossier_cible='Clients')
        modele2 = ModeleDocument.objects.create(
            company=self.co_a, nom='M2', corps_html='<p>{{ a }}</p>',
            cabinet_cible='Attestations', dossier_cible='Clients')
        doc1, _ = services.generer_document(
            modele1, {'a': '1'}, company=self.co_a, created_by=self.admin_a)
        doc2, _ = services.generer_document(
            modele2, {'a': '2'}, company=self.co_a, created_by=self.admin_a)
        self.assertEqual(doc1.folder_id, doc2.folder_id)
        self.assertEqual(
            Folder.objects.filter(
                company=self.co_a, cabinet__nom='Attestations',
                nom='Clients', parent__isnull=True).count(),
            1)

    def test_classement_isolation_societe(self):
        # Le classement d'un modèle de A ne touche jamais le référentiel de B :
        # cabinet/dossier sont créés sous la société du modèle.
        modele_a = ModeleDocument.objects.create(
            company=self.co_a, nom='A', corps_html='<p>{{ x }}</p>',
            cabinet_cible='Partagé', dossier_cible='Commun')
        modele_b = ModeleDocument.objects.create(
            company=self.co_b, nom='B', corps_html='<p>{{ x }}</p>',
            cabinet_cible='Partagé', dossier_cible='Commun')
        doc_a, _ = services.generer_document(
            modele_a, {'x': '1'}, company=self.co_a, created_by=self.admin_a)
        doc_b, _ = services.generer_document(
            modele_b, {'x': '2'}, company=self.co_b, created_by=self.admin_b)
        # Deux cabinets/dossiers homonymes mais distincts, un par société.
        self.assertNotEqual(doc_a.folder.cabinet_id, doc_b.folder.cabinet_id)
        self.assertEqual(doc_a.folder.cabinet.company_id, self.co_a.id)
        self.assertEqual(doc_b.folder.cabinet.company_id, self.co_b.id)

    def test_action_generer_classe_dans_la_cible_du_modele(self):
        modele = ModeleDocument.objects.create(
            company=self.co_a, nom='Courrier',
            corps_html='<p>{{ objet }}</p>',
            cabinet_cible='Courriers', dossier_cible='Sortants {{ annee }}')
        api = auth(self.admin_a)
        resp = api.post(
            f'/api/django/ged/modeles-document/{modele.id}/generer/',
            {'contexte': {'objet': 'Relance', 'annee': '2026'}},
            format='json')
        self.assertEqual(resp.status_code, 201, getattr(resp, 'data', resp))
        doc = Document.objects.get(pk=resp.data['document'])
        self.assertEqual(doc.folder.cabinet.nom, 'Courriers')
        self.assertEqual(doc.folder.nom, 'Sortants 2026')
