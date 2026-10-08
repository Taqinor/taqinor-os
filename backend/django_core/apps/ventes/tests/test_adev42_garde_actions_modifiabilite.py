"""ADEV42 (C-ADEV-040, critère C2) — garde de CLASSE « écriture d'un devis
hors prédicat de modifiabilité ».

Le test introspecte ``DevisViewSet.get_extra_actions()`` (mixins compris :
``views/devis_calepinage.py``, ``devis_cycle.py``, ``devis_etudes.py``…) et,
pour chaque ``@action`` d'ÉCRITURE (POST/PATCH/PUT/DELETE) :

* exemptée par NOM dans ``EXEMPTIONS`` (justification obligatoire) → sautée ;
* portée par une garde PROPRE documentée (``GARDES_PROPRES``) → APPELÉE sur
  un devis ACCEPTÉ, statut attendu vérifié, devis relu inchangé ;
* sinon → APPELÉE réellement sur un devis ACCEPTÉ : doit répondre 409
  (``_refus_modifiabilite`` / ``_reponse_non_modifiable``) et ne rien écrire.

Une action d'écriture nouvelle sans garde est donc NOMMÉE par l'échec
(exécution, jamais lecture du source).

Test-du-test : retirer la garde de ``conception_electrique`` ⇒
``conception_electrique POST → 200`` est nommé et le test échoue.
"""
import json
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.forms.models import model_to_dict
from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.ventes.models import Devis, LigneDevis
from apps.ventes.views import DevisViewSet
from authentication.models import Company

User = get_user_model()

_ECRITURES = ('post', 'put', 'patch', 'delete')

#: Actions d'écriture qui NE passent PAS par le prédicat de modifiabilité,
#: par NOM d'action — chacune justifiée (jamais ignorée en silence).
EXEMPTIONS = {
    'composition': 'dry-run : compose le kit sans rien créer (U3)',
    'auto': 'crée un NOUVEAU devis depuis un lead (detail=False)',
    'atomic': 'crée un NOUVEAU devis + lignes (detail=False)',
    'from_layout': 'crée un NOUVEAU brouillon depuis un layout '
                   '(detail=False)',
    'variante_config': 'réglage société des variantes (detail=False), '
                       'aucun devis',
    'revoquer_lien_public': 'sécurité : révoquer le lien public d\'un '
                            'accepté reste permis (aucun chiffre écrit)',
    'save_preset': 'LIT le devis pour créer un preset société',
    'dupliquer': 'crée une COPIE ; la source n\'est pas écrite',
    'dupliquer_variante': 'crée des variantes ; la source n\'est pas écrite',
    'dupliquer_variante_gamme': 'crée une gamme sœur ; la source n\'est '
                                'pas écrite',
    'reviser': 'D-QJR5-2 : LE geste d\'un accepté (crée la V2)',
    'renouveler': 'crée une nouvelle version d\'un devis expiré',
    'accepter': 'geste de CYCLE DE VIE (gardes propres de accept_devis, '
                'ADEV7/ADEV13)',
    'refuser': 'geste de CYCLE DE VIE (gardes propres, ADEV7)',
    'noter': 'note interne au chatter, permise à tout statut',
    'approuver_remise': 'approbation admin de la remise (drapeau), '
                        'aucune ligne ni chiffre réécrit',
    'share_link': 'diffusion : frappe un lien de lecture',
    'envoyer_email': 'diffusion (gardes de cycle ENVOYER propres)',
    'whatsapp_preview': 'diffusion : aperçu du message, aucune écriture',
    'whatsapp': 'diffusion (gardes de cycle propres)',
    'pdf_partage': 'diffusion du PDF /proposal (règle #4 : rendu seul)',
    'contacter_superieur': 'message interne au supérieur, aucun chiffre',
    'convertir_en_bc': 'aval d\'un accepté (BC) — exige l\'acceptation',
    'generer_facture': 'aval d\'un accepté (facture)',
    'facturer_complet': 'aval d\'un accepté (facture)',
    'proforma_pdf': 'rendu d\'une proforma, aucun chiffre du devis écrit',
    'generer_pdf': 'rendu /proposal (règle #4 : le moteur rend seulement)',
}

#: Actions gardées par une garde PROPRE au contrat historique (pas un 409) :
#: action → (corps, statut attendu sur un ACCEPTÉ). Exécutées réellement.
GARDES_PROPRES = {
    'reappliquer_lead': ({}, 400),        # _refus_derive_fige → devis_fige
    'acquitter_derive': ({}, 400),        # _refus_derive_fige → devis_fige
    # garde de statut de sync_devis_from_layout → 400 revision_possible
    'offres_tailles_appliquer': ({'cle': 'recommande'}, 400),
}


def _actions_ecriture():
    """(nom, url_path, méthodes d'écriture, detail) de chaque @action."""
    sortie = []
    for act in DevisViewSet.get_extra_actions():
        methodes = sorted(m for m in act.mapping if m in _ECRITURES)
        if methodes:
            sortie.append((act.__name__, act.url_path, methodes, act.detail))
    return sortie


class GardeActionsModifiabiliteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ADEV42', slug='adev42-co')
        cls.user = User.objects.create_user(
            username='adev42_admin', password='x', role_legacy='admin',
            company=cls.company)
        client = Client.objects.create(
            company=cls.company, nom='Client ADEV42',
            email='adev42@example.com')
        cls.devis = Devis.objects.create(
            company=cls.company, reference='DV-ADEV42-ACC', client=client,
            created_by=cls.user, statut=Devis.Statut.ACCEPTE)
        LigneDevis.objects.create(
            devis=cls.devis, designation='Panneau 550 W', quantite=10,
            prix_unitaire=Decimal('1200'))

    def setUp(self):
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self.api.raise_request_exception = False

    def _empreinte(self):
        d = Devis.objects.filter(pk=self.devis.pk).values().first()
        lignes = sorted(
            json.dumps(model_to_dict(lg), sort_keys=True, default=str)
            for lg in LigneDevis.objects.filter(devis_id=self.devis.pk))
        return json.dumps(d, sort_keys=True, default=str), lignes

    def _url(self, url_path):
        return '/api/django/ventes/devis/%s/%s/' % (self.devis.pk, url_path)

    def test_toute_action_ecriture_gardee(self):
        actions = _actions_ecriture()
        noms = {a[0] for a in actions}
        # La garde n'est pas vide : les actions gardées connues sont vues.
        for attendue in ('conception_electrique', 'simuler', 'replace_lines',
                         'etude_params', 'layout', 'sync_layout'):
            self.assertIn(attendue, noms)

        avant = self._empreinte()
        echecs = []
        # Tâche Celery de simulation doublée : aucune exécution réelle si une
        # garde manquait (l'échec est nommé, sans effet de bord).
        with mock.patch('apps.ventes.tasks.task_simulate_bankable_study'):
            for nom, url_path, methodes, detail in actions:
                if nom in EXEMPTIONS:
                    continue
                if not detail:
                    echecs.append('%s : action detail=False d\'écriture non '
                                  'classée (EXEMPTIONS)' % nom)
                    continue
                corps, attendu = GARDES_PROPRES.get(nom, ({}, 409))
                for methode in methodes:
                    reponse = getattr(self.api, methode)(
                        self._url(url_path), corps, format='json')
                    if reponse.status_code != attendu:
                        echecs.append('%s %s → %s (attendu %s)' % (
                            nom, methode.upper(), reponse.status_code,
                            attendu))
        self.assertEqual(
            echecs, [],
            'action d\'écriture hors prédicat de modifiabilité sur un devis '
            'ACCEPTÉ — la garder (_refus_modifiabilite) ou la déclarer '
            '(nom + justification) dans EXEMPTIONS : %s' % echecs)
        # Rien n'a été écrit sur l'accepté.
        self.assertEqual(self._empreinte(), avant)

    def test_exemptions_vivantes_et_justifiees(self):
        noms = {a[0] for a in _actions_ecriture()}
        for nom, justif in EXEMPTIONS.items():
            self.assertTrue(justif and len(justif) > 10, nom)
            self.assertIn(nom, noms, 'exemption morte : %s' % nom)
        for nom in GARDES_PROPRES:
            self.assertIn(nom, noms, 'garde propre morte : %s' % nom)
