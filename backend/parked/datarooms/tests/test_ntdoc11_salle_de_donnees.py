"""NTDOC11 — Modèle ``SalleDeDonnees`` + appartenance de documents GED.

Couvre :
  * une salle regroupe des documents de DOSSIERS DIFFÉRENTS sans les déplacer
    ni les dupliquer ;
  * retirer un document de la salle ne le supprime pas de la GED ;
  * l'ajout est idempotent (pas de doublon) ;
  * isolation société : une salle d'une autre société est invisible (404), et
    un document d'une autre société ne peut pas être ajouté ;
  * la société est posée CÔTÉ SERVEUR, jamais lue du corps de requête.
"""
from django.test import TestCase

from apps.datarooms import selectors, services
from apps.datarooms.models import SalleDeDonnees, SalleDeDonneesDocument

from ._base import auth, make_admin, make_company, make_document


class NtDoc11Base(TestCase):
    def setUp(self):
        self.co_a = make_company('ntdoc11-a', 'Ntdoc11 A')
        self.co_b = make_company('ntdoc11-b', 'Ntdoc11 B')
        self.admin_a = make_admin(self.co_a, 'ntdoc11-admin-a')
        self.admin_b = make_admin(self.co_b, 'ntdoc11-admin-b')
        self.api = auth(self.admin_a)
        self.salle = services.creer_salle(
            company=self.co_a, nom='Due diligence 2026',
            deal_type='due diligence', created_by=self.admin_a)


class CollectionSansDeplacementTests(NtDoc11Base):
    def test_regroupe_des_documents_de_dossiers_differents(self):
        docs = [
            make_document(self.co_a, f'Pièce {i}',
                          folder_nom=f'Dossier {i % 4}')
            for i in range(12)
        ]
        dossiers = {d.folder_id for d in docs}
        self.assertGreater(len(dossiers), 1)

        services.ajouter_documents(self.salle, docs)

        self.assertEqual(
            selectors.documents_de_salle(self.salle).count(), 12)
        # Aucun document n'a bougé de dossier, aucun n'a été dupliqué.
        for doc, dossier_avant in zip(docs, [d.folder_id for d in docs]):
            doc.refresh_from_db()
            self.assertEqual(doc.folder_id, dossier_avant)
        from apps.ged.models import Document
        self.assertEqual(
            Document.objects.filter(company=self.co_a).count(), 12)

    def test_retirer_ne_supprime_pas_de_la_ged(self):
        from apps.ged.models import Document

        doc = make_document(self.co_a, 'Statuts')
        services.ajouter_documents(self.salle, [doc])
        self.assertTrue(services.retirer_document(self.salle, doc))
        self.assertEqual(selectors.documents_de_salle(self.salle).count(), 0)
        self.assertTrue(Document.objects.filter(pk=doc.pk).exists())

    def test_ajout_idempotent(self):
        doc = make_document(self.co_a, 'Bilan')
        services.ajouter_documents(self.salle, [doc])
        creees = services.ajouter_documents(self.salle, [doc])
        self.assertEqual(creees, [])
        self.assertEqual(
            SalleDeDonneesDocument.objects.filter(salle=self.salle).count(), 1)

    def test_ordre_incremente_a_chaque_ajout(self):
        d1 = make_document(self.co_a, 'A')
        d2 = make_document(self.co_a, 'B')
        services.ajouter_documents(self.salle, [d1])
        services.ajouter_documents(self.salle, [d2])
        ordres = list(selectors.documents_de_salle(self.salle)
                      .values_list('ordre', flat=True))
        self.assertEqual(ordres, sorted(ordres))
        self.assertEqual(len(set(ordres)), 2)


class ApiSalleTests(NtDoc11Base):
    def test_creation_pose_la_societe_cote_serveur(self):
        reponse = self.api.post('/api/django/datarooms/salles/', {
            'nom': 'Levée de fonds série A',
            'deal_type': 'levée de fonds',
            # Tentative d'injection : la société du corps est IGNORÉE.
            'company': self.co_b.pk,
        }, format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        salle = SalleDeDonnees.objects.get(pk=reponse.data['id'])
        self.assertEqual(salle.company_id, self.co_a.pk)
        self.assertEqual(salle.created_by_id, self.admin_a.pk)

    def test_statut_non_modifiable_par_patch_brut(self):
        reponse = self.api.patch(
            f'/api/django/datarooms/salles/{self.salle.pk}/',
            {'statut': 'fermee'}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.salle.refresh_from_db()
        self.assertEqual(self.salle.statut, SalleDeDonnees.Statut.OUVERTE)

    def test_ajouter_documents_par_api(self):
        docs = [make_document(self.co_a, f'P{i}') for i in range(3)]
        reponse = self.api.post(
            f'/api/django/datarooms/salles/{self.salle.pk}/'
            f'ajouter-documents/',
            {'documents': [d.pk for d in docs]}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['ajoutes'], 3)
        self.assertEqual(reponse.data['total'], 3)

    def test_document_d_une_autre_societe_jamais_ajoute(self):
        etranger = make_document(self.co_b, 'Secret voisin')
        reponse = self.api.post(
            f'/api/django/datarooms/salles/{self.salle.pk}/'
            f'ajouter-documents/',
            {'documents': [etranger.pk]}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['ajoutes'], 0)
        self.assertEqual(selectors.documents_de_salle(self.salle).count(), 0)

    def test_salle_d_une_autre_societe_invisible(self):
        salle_b = services.creer_salle(
            company=self.co_b, nom='Salle voisine', created_by=self.admin_b)
        reponse = self.api.get(f'/api/django/datarooms/salles/{salle_b.pk}/')
        self.assertEqual(reponse.status_code, 404)
        liste = self.api.get('/api/django/datarooms/salles/')
        self.assertEqual(liste.status_code, 200)
        resultats = liste.data.get('results', liste.data)
        self.assertNotIn(salle_b.pk, [r['id'] for r in resultats])

    def test_ligne_appartenance_refuse_un_document_hors_societe(self):
        etranger = make_document(self.co_b, 'Pièce voisine')
        reponse = self.api.post('/api/django/datarooms/salle-documents/', {
            'salle': self.salle.pk, 'document': etranger.pk,
        }, format='json')
        self.assertEqual(reponse.status_code, 400, reponse.data)
