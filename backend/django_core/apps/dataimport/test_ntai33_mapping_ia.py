"""NTAI33 — Mapping d'import intelligent (colonnes CSV → champs ERP).

Couvre :
  * ``proposer_mapping_ia`` propose un mapping SUR LES SEULS EN-TÊTES fournis
    (jamais une donnée de ligne) et filtre tout ce qui n'est ni un en-tête
    demandé ni un champ RÉELLEMENT connu de la cible (garde anti-
    hallucination) ;
  * sans clé LLM configurée : no-op propre, ``{}`` ;
  * sans en-tête non mappé, ou pour une cible sans ``FIELD_MAPS`` (écriture
    déléguée à une autre app) : no-op propre ;
  * ``dry_run`` expose la suggestion sous une clé SÉPARÉE
    (``mapping_propose_ia``), jamais fusionnée dans ``mapping`` (l'utilisateur
    valide) ; sans clé LLM le comportement manuel actuel est INCHANGÉ (la clé
    est absente).
"""
from django.test import TestCase, override_settings

from core.ai.providers import AIResult, LLMProvider
from core.ai.registry import register_provider

from apps.dataimport import services


class FauxLLMMapping(LLMProvider):
    """LLM factice : ACTIF, local, aucun appel réseau."""

    key = 'faux_llm_ntai33'
    label = 'LLM de test NTAI33'
    reponse = '{"Coordonnées tél.": "telephone", "Champ inexistant": "prix_achat"}'

    def is_configured(self):
        return True

    def complete(self, *, prompt, system=None, max_tokens=512):
        return AIResult(ok=True, configured=True, provider=self.key,
                        data={'text': type(self).reponse})


register_provider(FauxLLMMapping)


class ProposerMappingIaTests(TestCase):
    @override_settings(AI_PROVIDERS={'llm': 'faux_llm_ntai33'})
    def test_propose_uniquement_les_entetes_demandes_et_champs_connus(self):
        mapping = services.proposer_mapping_ia(
            'leads', ['Coordonnées tél.', 'Champ inexistant'])
        # « Champ inexistant » → prix_achat : ni un champ de `leads`, ni un
        # en-tête réel ne le sauve — halluciné, donc écarté.
        self.assertEqual(mapping, {'Coordonnées tél.': 'telephone'})

    def test_sans_cle_llm_no_op(self):
        self.assertEqual(
            services.proposer_mapping_ia('leads', ['Coordonnées tél.']), {})

    @override_settings(AI_PROVIDERS={'llm': 'faux_llm_ntai33'})
    def test_sans_en_tete_non_mappe_no_op(self):
        self.assertEqual(services.proposer_mapping_ia('leads', []), {})

    @override_settings(AI_PROVIDERS={'llm': 'faux_llm_ntai33'})
    def test_cible_sans_field_maps_no_op(self):
        # `equipements` a un FIELD_MAPS ; une cible purement plateforme (sans
        # entrée FIELD_MAPS) doit rester no-op ici — jamais une KeyError.
        self.assertEqual(
            services.proposer_mapping_ia('cible_inconnue_xyz',
                                         ['un en-tête']),
            {})


class DryRunMappingIaTests(TestCase):
    CSV = (
        'Nom;Coordonnées tél.\n'
        'Reda;0612345678\n'
    ).encode('utf-8')

    @override_settings(AI_PROVIDERS={'llm': 'faux_llm_ntai33'})
    def test_dry_run_expose_la_suggestion_separement(self):
        resultat = services.dry_run(self.CSV, 'leads.csv', 'leads')
        self.assertIn('Coordonnées tél.', resultat['non_mappees'])
        self.assertEqual(
            resultat['mapping_propose_ia'], {'Coordonnées tél.': 'telephone'})
        # Jamais fusionné dans le mapping automatique.
        self.assertNotIn('Coordonnées tél.', resultat['mapping'])

    def test_dry_run_sans_cle_llm_comportement_inchange(self):
        resultat = services.dry_run(self.CSV, 'leads.csv', 'leads')
        self.assertNotIn('mapping_propose_ia', resultat)
        self.assertIn('Coordonnées tél.', resultat['non_mappees'])
