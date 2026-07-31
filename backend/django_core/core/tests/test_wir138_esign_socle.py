"""WIR138 — le socle e-signature canonique est DÉSIGNÉ et PARQUÉ.

Décision tracée dans ``docs/esign-socle.md`` et en tête de ``core/esign.py`` :
``core.esign`` est le socle canonique des demandes de signature adossées à un
prestataire externe, et il reste dormant tant qu'aucun compte Yousign/DocuSign
n'est provisionné (clé d'API fondateur).

Ce module verrouille les invariants du PARKING — sans eux, « parqué » serait
indistinguable d'« oublié » :
  * un socle parqué ne fait aucun appel réseau et ne dépasse jamais le
    brouillon ;
  * aucun endpoint n'expose ``EsignRequest`` (c'est volontaire) ;
  * les deux autres chemins (preuve d'acceptation devis, circuit GED) restent
    séparés : rien ne crée d'``EsignRequest`` en production aujourd'hui.

Quand le fondateur activera un prestataire, ce module DOIT être adapté (voir
la section « Activation » de ``docs/esign-socle.md``) — sa rougeur sera le
signal que le socle vient d'être branché.

Run :
    docker compose exec django_core python manage.py test \
        core.tests.test_wir138_esign_socle -v 2
"""
from django.test import TestCase
from django.urls import get_resolver

from authentication.models import Company
from core import esign
from core.models import EsignRequest


class WIR138SocleParqueTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='WIR138 Co', slug='wir138-co')

    def test_socle_parque_reste_en_brouillon_sans_prestataire(self):
        """Sans IntegrationConfig actif : brouillon, aucun appel réseau."""
        req = esign.creer_demande(
            self.company, signataire_email='client@example.com',
            signataire_nom='Client')
        self.assertEqual(req.statut, EsignRequest.STATUT_BROUILLON)

        esign.envoyer(req)
        req.refresh_from_db()
        # Le connecteur générique non configuré est un no-op propre : la
        # demande N'EST PAS envoyée et rien n'explose.
        self.assertEqual(req.statut, EsignRequest.STATUT_BROUILLON)
        self.assertEqual(req.external_id, '')
        self.assertIsNone(req.sent_le)

    def test_rafraichir_statut_est_un_noop_parque(self):
        req = esign.creer_demande(self.company)
        avant = req.statut
        esign.rafraichir_statut(req)
        req.refresh_from_db()
        self.assertEqual(req.statut, avant)

    def test_aucun_endpoint_nexpose_le_socle(self):
        """Le parking est un INVARIANT : aucune route ne nomme le socle."""
        noms = get_resolver().reverse_dict.keys()
        noms_str = {n for n in noms if isinstance(n, str)}
        fautifs = sorted(n for n in noms_str
                         if 'esignrequest' in n.lower().replace('-', ''))
        self.assertEqual(fautifs, [], f'Socle e-sign exposé : {fautifs}')

    def test_socle_reste_une_fondation_sans_import_metier(self):
        """``core.esign`` ne doit jamais importer une app domaine."""
        import inspect
        src = inspect.getsource(esign)
        for interdit in ('apps.ventes', 'apps.ged', 'apps.crm', 'apps.contrats'):
            self.assertNotIn(f'import {interdit}', src)
            self.assertNotIn(f'from {interdit}', src)

    def test_aucun_esign_request_cree_par_les_autres_chemins(self):
        """Tant que le socle est parqué, rien ne l'alimente en production."""
        self.assertEqual(EsignRequest.objects.count(), 0)
        # La preuve d'acceptation devis (loi 53-05) est un AUTRE objet : elle
        # ne passe pas — et ne passera pas — par le socle. Résolution par le
        # registre Django (jamais un import : `core` reste base-layer, cf. le
        # contrat import-linter `core-foundation-is-a-base-layer`).
        from django.apps import apps as django_apps
        devis_signature = django_apps.get_model('ventes', 'DevisSignature')
        self.assertFalse(
            issubclass(devis_signature, EsignRequest),
            'DevisSignature ne doit pas être fondue dans le socle e-sign.')
