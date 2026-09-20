"""NTAI34 — Détection de doublons assistée par similarité sémantique.

Couvre :
  * ``doublons_clients_semantiques`` propose un groupe pour deux fiches dont
    l'embedding indexé (``core.SearchChunk``, NTAI24) est PROCHE, même si
    leurs noms textuels sont éloignés (« STE ALPHA » / « Alpha S.A.R.L ») ;
  * sans fournisseur d'embedding configuré : ``[]`` — repli complet sur le
    seul détecteur par distance de chaînes existant (comportement inchangé,
    AUCUN appel réseau) ;
  * ``doublons_clients`` FUSIONNE les deux couches sans jamais dupliquer un
    groupe déjà trouvé par le détecteur exact/nom ;
  * les propositions sémantiques alimentent la MÊME file ``PropositionFusion``
    (NTDATA20, ``scanner_propositions``) — jamais une deuxième UI ;
  * isolation société ; le motif rendu est bien ``'semantique'`` (jamais un
    poids de :data:`POIDS_CRITERES`, qui mesurerait autre chose).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.crm.models import Client
from apps.dataquality import services
from apps.dataquality.dedoublonnage import cosine_similarite
from apps.dataquality.models import PropositionFusion
from authentication.models import Company
from core.ai import search as core_search
from core.models import SearchChunk

User = get_user_model()

VEC_A = [1.0] + [0.0] * 1023
VEC_PROCHE = [0.95] + [0.05] * 1023
VEC_ORTHOGONAL = [0.0] * 500 + [1.0] + [0.0] * 523


class FauxEmbeddingProvider:
    def embed(self, texte):  # pragma: no cover - jamais appelé (pas de recalcul ici)
        return VEC_A


class DoublonsClientsSemantiquesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(
            nom='NTAI34 SA', slug='ntai34-sa')
        cls.autre = Company.objects.create(
            nom='NTAI34 Autre', slug='ntai34-autre')
        cls.user = User.objects.create_user(
            username='ntai34_u', password='x', company=cls.company,
            role_legacy='admin')

    def _client(self, nom, company=None):
        return Client.objects.create(company=company or self.company, nom=nom)

    def _chunk(self, obj_id, titre, vecteur, company=None):
        return SearchChunk.objects.create(
            company=company or self.company, content_type='crm.client',
            object_id=obj_id, titre=titre, extrait=titre, embedding=vecteur)

    def test_cosine_similarite_pure(self):
        self.assertAlmostEqual(cosine_similarite(VEC_A, VEC_A), 1.0)
        self.assertAlmostEqual(cosine_similarite(VEC_A, VEC_ORTHOGONAL), 0.0)
        self.assertEqual(cosine_similarite([], VEC_A), 0.0)
        self.assertEqual(cosine_similarite(VEC_A, [1.0]), 0.0)  # dimensions

    def test_sans_fournisseur_embedding_repli_complet(self):
        a = self._client('STE ALPHA')
        b = self._client('Alpha S.A.R.L')
        self._chunk(a.id, 'STE ALPHA', VEC_A)
        self._chunk(b.id, 'Alpha S.A.R.L', VEC_PROCHE)
        # AUCUN fournisseur enregistré ici (chaque test démarre neutre) :
        # aucun appel, aucune comparaison.
        self.assertEqual(services.doublons_clients_semantiques(self.company), [])

    def test_deux_fiches_proches_semantiquement_remontent(self):
        core_search.register_embedding_provider(FauxEmbeddingProvider())
        self.addCleanup(core_search.clear_embedding_provider)

        a = self._client('STE ALPHA')
        b = self._client('Alpha S.A.R.L')
        c = self._client('Société sans rapport')
        self._chunk(a.id, 'STE ALPHA', VEC_A)
        self._chunk(b.id, 'Alpha S.A.R.L', VEC_PROCHE)
        self._chunk(c.id, 'Société sans rapport', VEC_ORTHOGONAL)

        groupes = services.doublons_clients_semantiques(self.company)
        self.assertEqual(len(groupes), 1)
        groupe = groupes[0]
        self.assertEqual(groupe['ids'], sorted([a.id, b.id]))
        self.assertEqual(groupe['motifs'], ['semantique'])
        self.assertGreaterEqual(groupe['score'], 0.85)

    def test_doublons_clients_fusionne_sans_dupliquer(self):
        core_search.register_embedding_provider(FauxEmbeddingProvider())
        self.addCleanup(core_search.clear_embedding_provider)

        a = self._client('STE ALPHA')
        b = self._client('Alpha S.A.R.L')
        self._chunk(a.id, 'STE ALPHA', VEC_A)
        self._chunk(b.id, 'Alpha S.A.R.L', VEC_PROCHE)

        groupes = services.doublons_clients(self.company, self.user)
        semantiques = [g for g in groupes if g['motifs'] == ['semantique']]
        self.assertEqual(len(semantiques), 1)
        self.assertEqual(semantiques[0]['ids'], sorted([a.id, b.id]))

    def test_isolation_societe(self):
        core_search.register_embedding_provider(FauxEmbeddingProvider())
        self.addCleanup(core_search.clear_embedding_provider)

        a = self._client('STE ALPHA', company=self.autre)
        b = self._client('Alpha S.A.R.L', company=self.autre)
        self._chunk(a.id, 'STE ALPHA', VEC_A, company=self.autre)
        self._chunk(b.id, 'Alpha S.A.R.L', VEC_PROCHE, company=self.autre)

        self.assertEqual(
            services.doublons_clients_semantiques(self.company), [])

    def test_alimente_la_meme_file_propositionfusion(self):
        core_search.register_embedding_provider(FauxEmbeddingProvider())
        self.addCleanup(core_search.clear_embedding_provider)

        a = self._client('STE ALPHA')
        b = self._client('Alpha S.A.R.L')
        self._chunk(a.id, 'STE ALPHA', VEC_A)
        self._chunk(b.id, 'Alpha S.A.R.L', VEC_PROCHE)

        nouvelles = services.scanner_propositions(self.company, 'client',
                                                  self.user)
        self.assertEqual(len(nouvelles), 1)
        proposition = PropositionFusion.objects.get(
            company=self.company, entite='client')
        self.assertEqual(proposition.ids_groupe, sorted([a.id, b.id]))
        self.assertEqual(proposition.motifs, ['semantique'])
