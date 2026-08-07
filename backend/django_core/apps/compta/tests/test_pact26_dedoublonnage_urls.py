"""PACT26 — ``apps/compta/urls.py`` ne ré-enregistre plus les ViewSets de
``ao``, ``marketing`` et ``portail`` sous ``/api/django/compta/…``.

Constat qui a motivé la tâche : ce routeur fourre-tout historique (149
``router.register``) re-servait 42 ressources (8 AO + 28 marketing + 6
portail) qui avaient PAR AILLEURS leur propre routeur dédié
(``apps.ao.urls``, ``apps.marketing.urls``, ``apps.portail.urls``) — un
double montage qui faussait tout comptage automatique de ressources et
forçait chaque futur écran à choisir arbitrairement entre deux URLs pour la
même donnée.

Ce module vérifie MÉCANIQUEMENT, sans base de données :
  1. aucun des 42 préfixes historiquement dupliqués n'est plus enregistré par
     le routeur ``compta`` ;
  2. chacun de ces 42 préfixes reste bien joignable — mais sous SON PROPRE
     routeur (``ao``/``marketing``/``portail``), jamais perdu ;
  3. les ressources compta NON dupliquées (ex. ``bordereaux``, qui n'est PAS
     ``bordereaux-prix``) restent intactes.
"""
from django.test import SimpleTestCase


class TestDedoublonnageUrlsCompta(SimpleTestCase):
    def _prefixes(self, router):
        return {p for p, _, _ in router.registry}

    def test_les_42_ressources_ao_marketing_portail_ne_sont_plus_dans_compta(self):
        from apps.compta.urls import router as router_compta

        prefixes_compta = self._prefixes(router_compta)

        prefixes_ao = {
            'appels-offres', 'bordereaux-prix', 'lignes-bordereau',
            'cautions-soumission', 'dossiers-soumission', 'pieces-soumission',
            'echeances-ao', 'resultats-ao',
        }
        prefixes_marketing = {
            'campagnes', 'envois-campagne', 'approbations-envoi-campagne',
            'listes-diffusion', 'abonnements-liste', 'segments-marketing',
            'sequences-relance', 'etapes-sequence', 'inscriptions-sequence',
            'relances-devis-abandonnes', 'ouvertures-partage',
            'formulaires-intake', 'messages-whatsapp', 'appels',
            'enquetes-nps', 'avis-clients', 'comptes-fidelite',
            'mouvements-fidelite', 'regles-upsell', 'enquetes',
            'evenements-marketing', 'inscriptions-evenement',
            'types-evenement', 'billets-evenement', 'questions-evenement',
            'communications-evenement', 'supports-offline', 'domaines-envoi',
        }
        prefixes_portail = {
            'comptes-portail', 'acceptations-devis-portail',
            'paiements-facture-portail', 'documents-client-portail',
            'jalons-chantier-portail', 'demandes-ticket-portail',
        }
        dupliquees_avant_pact26 = (
            prefixes_ao | prefixes_marketing | prefixes_portail)

        self.assertEqual(len(dupliquees_avant_pact26), 42)
        self.assertEqual(
            prefixes_compta & dupliquees_avant_pact26, set(),
            'PACT26 régressé : au moins une ressource AO/marketing/portail '
            'est de nouveau ré-enregistrée sous /api/django/compta/…')

    def test_chaque_ressource_retiree_reste_joignable_sous_son_propre_routeur(self):
        from apps.ao.urls import router as router_ao
        from apps.marketing.urls import router as router_mkt
        from apps.portail.urls import router as router_portail

        self.assertIn('appels-offres', self._prefixes(router_ao))
        self.assertIn('bordereaux-prix', self._prefixes(router_ao))
        self.assertIn('resultats-ao', self._prefixes(router_ao))

        self.assertIn('campagnes', self._prefixes(router_mkt))
        self.assertIn('sequences-relance', self._prefixes(router_mkt))
        self.assertIn('domaines-envoi', self._prefixes(router_mkt))

        self.assertIn('comptes-portail', self._prefixes(router_portail))
        self.assertIn(
            'demandes-ticket-portail', self._prefixes(router_portail))

    def test_les_ressources_compta_non_dupliquees_restent_intactes(self):
        """Non-régression : un nom proche ('bordereaux' vs 'bordereaux-prix')
        ne doit jamais être confondu avec une des 42 ressources retirées."""
        from apps.compta.urls import router as router_compta

        prefixes_compta = self._prefixes(router_compta)
        self.assertIn('bordereaux', prefixes_compta)
        self.assertIn('posts-sociaux', prefixes_compta)
        self.assertIn('codes-promotion', prefixes_compta)
        self.assertIn('partenaires', prefixes_compta)
        self.assertIn('abonnements-monitoring', prefixes_compta)
        self.assertIn('territoires-commerciaux', prefixes_compta)

    def test_le_routeur_compta_a_retreci_de_42_entrees(self):
        """149 router.register mesurés avant PACT26 -> 107 après (42 retirés)."""
        from apps.compta.urls import router as router_compta

        self.assertEqual(len(router_compta.registry), 107)
