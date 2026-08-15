"""NTAI24 — Tests de l'index sémantique cross-module (``core.ai.search``).

Couvre :
  * l'index est ÉTEINT par défaut (aucune ligne écrite au ``post_save``) ;
  * activé, créer un lead l'indexe automatiquement, et le modifier réindexe
    la MÊME ligne (pas de doublon) ;
  * l'index est SCOPÉ SOCIÉTÉ, et supprimer l'objet (ou sa société) le retire ;
  * sans fournisseur d'embeddings : ``embedding`` reste NULL, aucun appel
    réseau, et la recherche retombe proprement sur le plein-texte ;
  * l'indexation est BEST-EFFORT (un champ manquant dégrade l'extrait, une
    erreur n'empêche jamais l'enregistrement) ;
  * ``core`` reste fondation : les modèles sont déclarés par CHAÎNE.
"""
from django.test import TestCase, override_settings

from authentication.models import Company
from apps.crm.models import Client, Lead
from core.ai import search
from core.models import SearchChunk


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class Ntai24RegistreTests(TestCase):
    """Le registre ne référence QUE des chaînes « app.model »."""

    def tearDown(self):
        search.reset_registry()

    def test_specs_par_defaut_sont_des_chaines(self):
        for label in search.SPECS_PAR_DEFAUT:
            self.assertIsInstance(label, str)
            self.assertIn('.', label)
            self.assertEqual(label, label.lower())

    def test_modeles_cles_declares(self):
        for label in ('crm.lead', 'crm.client', 'ventes.devis',
                      'sav.ticket', 'contrats.contrat', 'kb.kbarticle'):
            self.assertIn(label, search.registered_labels())

    def test_enregistrement_et_retrait(self):
        search.register_indexable('demo.exemple', titre=('nom',))
        self.assertIn('demo.exemple', search.registered_labels())
        search.unregister_indexable('demo.exemple')
        self.assertNotIn('demo.exemple', search.registered_labels())

    def test_declaration_invalide_refusee(self):
        with self.assertRaises(ValueError):
            search.register_indexable('', titre=('nom',))
        with self.assertRaises(ValueError):
            search.register_indexable('demo.exemple')

    def test_signaux_branches_sur_des_modeles_installes(self):
        # Un libellé introuvable est ignoré (jamais une connexion pendante,
        # qui serait signalée par le check Django models.E022).
        connectes = search.connect_signals()
        self.assertIn('crm.lead', connectes)


class Ntai24IndexEteintTests(TestCase):
    def test_eteint_par_defaut(self):
        self.assertFalse(search.index_enabled())

    def test_aucune_ligne_sans_le_flag(self):
        co = make_company('ntai24a', 'NTAI24 A')
        Lead.objects.create(company=co, nom='Prospect A')
        self.assertEqual(SearchChunk.objects.count(), 0)


@override_settings(AI_SEMANTIC_INDEX_ENABLED=True)
class Ntai24IndexationTests(TestCase):
    def setUp(self):
        self.co = make_company('ntai24b', 'NTAI24 B')

    def test_creer_un_lead_l_indexe(self):
        lead = Lead.objects.create(
            company=self.co, nom='Alpha', societe='STE ALPHA',
            ville='Casablanca', email='contact@alpha.ma')
        chunk = SearchChunk.objects.get(content_type='crm.lead',
                                        object_id=lead.pk)
        self.assertEqual(chunk.company_id, self.co.id)
        self.assertEqual(chunk.module, 'crm')
        self.assertIn('Alpha', chunk.titre)
        self.assertIn('Casablanca', chunk.extrait)
        # Sans fournisseur d'embeddings : aucun vecteur, aucun appel réseau.
        self.assertIsNone(chunk.embedding)

    def test_modifier_reindexe_la_meme_ligne(self):
        lead = Lead.objects.create(company=self.co, nom='Alpha')
        lead.ville = 'Rabat'
        lead.save()
        chunks = SearchChunk.objects.filter(content_type='crm.lead',
                                            object_id=lead.pk)
        self.assertEqual(chunks.count(), 1)
        self.assertIn('Rabat', chunks.first().extrait)

    def test_supprimer_desindexe(self):
        client = Client.objects.create(company=self.co, nom='Beta')
        self.assertEqual(SearchChunk.objects.count(), 1)
        client.delete()
        self.assertEqual(SearchChunk.objects.count(), 0)

    def test_cascade_suppression_societe(self):
        Lead.objects.create(company=self.co, nom='Alpha')
        self.assertEqual(SearchChunk.objects.count(), 1)
        self.co.delete()
        self.assertEqual(SearchChunk.objects.count(), 0)

    def test_index_scope_societe(self):
        autre = make_company('ntai24c', 'NTAI24 C')
        Lead.objects.create(company=self.co, nom='Alpha')
        Lead.objects.create(company=autre, nom='Alpha')
        self.assertEqual(
            SearchChunk.objects.filter(company=self.co).count(), 1)
        self.assertEqual(
            SearchChunk.objects.filter(company=autre).count(), 1)

    def test_modele_non_declare_jamais_indexe(self):
        # ``Company`` n'est pas un modèle indexable : rien ne doit apparaître.
        make_company('ntai24d', 'NTAI24 D')
        self.assertFalse(
            SearchChunk.objects.filter(content_type='authentication.company')
            .exists())

    def test_indexation_best_effort_ne_leve_jamais(self):
        lead = Lead.objects.create(company=self.co, nom='Alpha')
        SearchChunk.objects.all().delete()
        # Un modèle déclaré avec un champ inexistant dégrade l'extrait sans
        # jamais lever.
        search.register_indexable('crm.lead', titre=('nom',),
                                  extrait=('champ_inexistant',))
        self.addCleanup(search.reset_registry)
        self.assertTrue(search.indexer(lead))
        chunk = SearchChunk.objects.get(object_id=lead.pk)
        self.assertEqual(chunk.extrait, '')

    def test_objet_sans_societe_ignore(self):
        lead = Lead.objects.create(company=self.co, nom='Alpha')
        SearchChunk.objects.all().delete()
        lead.company_id = None
        self.assertFalse(search.indexer(lead))


@override_settings(AI_SEMANTIC_INDEX_ENABLED=True)
class Ntai24RechercheTests(TestCase):
    def setUp(self):
        self.co = make_company('ntai24e', 'NTAI24 E')
        self.autre = make_company('ntai24f', 'NTAI24 F')
        Lead.objects.create(company=self.co, nom='Alpha',
                            societe='STE ALPHA', ville='Casablanca')
        Lead.objects.create(company=self.co, nom='Beta',
                            societe='BETA SARL', ville='Agadir')
        Lead.objects.create(company=self.autre, nom='Gamma',
                            societe='GAMMA', ville='Casablanca')

    def test_repli_plein_texte_sans_cle(self):
        self.assertFalse(search.embedding_enabled())
        resultats = search.rechercher(self.co, 'Casablanca')
        self.assertEqual(len(resultats), 1)
        self.assertIn('Alpha', resultats[0]['titre'])
        self.assertEqual(resultats[0]['content_type'], 'crm.lead')
        # Aucune URL inventée : sans route déclarée, la citation porte le
        # couple content_type + object_id.
        self.assertIsNone(resultats[0]['route'])

    def test_recherche_jamais_cross_tenant(self):
        resultats = search.rechercher(self.autre, 'Casablanca')
        self.assertEqual(len(resultats), 1)
        self.assertIn('Gamma', resultats[0]['titre'])

    def test_restriction_par_module(self):
        self.assertEqual(
            len(search.rechercher(self.co, 'Casablanca', modules=['ventes'])),
            0)
        self.assertEqual(
            len(search.rechercher(self.co, 'Casablanca', modules=['crm'])), 1)

    def test_question_vide_ou_societe_absente(self):
        self.assertEqual(search.rechercher(self.co, '   '), [])
        self.assertEqual(search.rechercher(None, 'Casablanca'), [])

    def test_embedding_no_op_sans_fournisseur(self):
        self.assertIsNone(search.compute_embedding('un texte'))

    def test_fournisseur_de_mauvaise_dimension_ignore(self):
        class FauxProvider:
            def embed(self, texte):
                return [0.1, 0.2]  # dimension incorrecte

        search.register_embedding_provider(FauxProvider())
        self.addCleanup(search.clear_embedding_provider)
        self.assertIsNone(search.compute_embedding('un texte'))
