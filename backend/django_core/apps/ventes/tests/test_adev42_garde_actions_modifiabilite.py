"""ADEV42 (C-ADEV-040) — garde de CLASSE : toute ``@action`` d'ÉCRITURE
(POST/PATCH/PUT/DELETE) de ``DevisViewSet`` et de ses mixins (dont
``views/devis_calepinage.py``) passe par le prédicat de modifiabilité
(``_refus_modifiabilite`` → 409) ou figure dans une exemption NOMMÉE et
justifiée.

* les actions sont DÉCOUVERTES par introspection (``get_extra_actions()`` +
  les écritures standard ``update``/``partial_update``/``destroy``) ;
* une action d'écriture nouvelle, ni gardée ni exemptée, est NOMMÉE par
  ``test_toute_action_ecriture_classee`` ;
* chaque action gardée est APPELÉE pour de vrai sur un devis ACCEPTÉ et doit
  répondre 409 (exécution, pas lecture du source) ; chaque refus historique
  en 400 (contrats QJR588 / QJR557 / en-tête figé) est rejoué et doit
  répondre 400 ; dans tous les cas le devis relu est identique.

Test-du-test : retirer la garde de ``conception_electrique`` (POST) ⇒
``test_toute_action_ecriture_gardee`` la nomme (200 au lieu de 409).
Complémentaire de ``test_actions_devis_ont_appelant.py`` (autre classe).
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, DevisActivity, LigneDevis, LotDevis
from apps.ventes import urls as _urls  # noqa: F401 — actions greffées
from apps.ventes.views import DevisViewSet
from authentication.models import Company

User = get_user_model()
BASE = '/api/django/ventes/devis/'
ECRITURES = ('post', 'put', 'patch', 'delete')

#: Actions GARDÉES par ``_refus_modifiabilite`` : (verbe, corps) rejoués sur
#: un devis ACCEPTÉ → 409. Le corps suffit à franchir les contrôles de forme
#: qui précèdent la garde.
GARDEES_409 = {
    'sync_layout': [('post', {'result': {'panels': 9, 'kwc': 4.95}})],
    'conception_electrique': [('post', {})],
    'simuler': [('post', {})],
    'ajouter_boq_electrique': [('post', {})],
    'layout': [('post', {'result': {'panels': 9}})],
    'roof_image': [('post', {})],
    'lots': [('post', {'nom_lot': 'Lot A'})],
    'replace_lines': [('post', {'lignes': []})],
    'etude_params': [('patch', {'note_interne': 'x'})],
    'offres_tailles_config': [('patch', {})],
    'offres_tailles_regenerer': [('post', {})],
    'overrides': [('patch', {}), ('delete', {})],
    'destroy': [('delete', {})],
}

#: Refus HISTORIQUES en 400 (même prédicat, code conservé par contrat) :
#: rejoués → 400, devis inchangé.
REFUS_400 = {
    'reappliquer_lead': [('post', {})],   # QJR588 400 devis_fige
    'acquitter_derive': [('post', {})],   # QJR588 400 devis_fige
    'offres_tailles_appliquer': [('post', {'cle': 'recommande'})],  # QJR557
    'partial_update': [('patch', {'note': 'Retouche'})],  # 400 {statut}
    'update': [('put', {'note': 'Retouche'})],  # 400 (validation / figé)
}

#: Écritures LÉGITIMES sur un devis accepté (elles ne modifient pas son
#: contenu, ou sont le geste de cycle lui-même) — exemptions NOMMÉES.
EXEMPTEES = {
    'accepter': 'geste de cycle (garde geste_cycle_permis, ADEV7).',
    'refuser': 'geste de cycle (garde geste_cycle_permis, ADEV7).',
    'reviser': 'LE geste attendu sur un accepté : crée la V+1.',
    'renouveler': 'crée un nouveau devis (renouvellement).',
    'dupliquer': 'crée une copie brouillon indépendante.',
    'dupliquer_variante': 'crée des copies brouillon (variantes).',
    'dupliquer_variante_gamme': 'crée la sœur de gamme (brouillon).',
    'save_preset': 'enregistre un modèle de la société.',
    'noter': 'note au chatter, contenu du devis inchangé.',
    'share_link': 'lien client (envoi), contenu inchangé.',
    'envoyer_email': 'renvoi au client, contenu inchangé.',
    'whatsapp': 'envoi WhatsApp, contenu inchangé.',
    'whatsapp_preview': 'aperçu du message, aucune écriture du devis.',
    'pdf_partage': 'rendu PDF partagé (règle #4 : le moteur rend).',
    'revoquer_lien_public': 'révoque le lien client.',
    'contacter_superieur': 'demande au supérieur (notification).',
    'approuver_remise': 'approbation administrateur, contenu inchangé.',
    'generer_pdf': 'rendu PDF (règle #4 : le moteur rend seulement).',
    'proforma_pdf': 'rendu de la proforma.',
    'convertir_en_bc': 'aval d’un accepté (BonCommande).',
    'generer_facture': 'aval d’un accepté (facture).',
    'facturer_complet': 'aval d’un accepté (factures).',
    # detail=False — ne visent aucun devis existant.
    'atomic': 'création d’un NOUVEAU devis (detail=False).',
    'auto': 'création d’un NOUVEAU devis (detail=False).',
    'composition': 'aperçu à blanc, aucune écriture (detail=False).',
    'from_layout': 'création d’un NOUVEAU devis (detail=False).',
    'variante_config': 'réglage de la société (detail=False).',
}


def _ecritures_decouvertes():
    """``{nom: url_path}`` des actions d'écriture du viewset (+ standard)."""
    trouvees = {}
    for action in DevisViewSet.get_extra_actions():
        if any(m in ECRITURES for m in action.mapping):
            trouvees[action.__name__] = action.url_path
    for nom in ('update', 'partial_update', 'destroy'):
        if hasattr(DevisViewSet, nom):
            trouvees[nom] = None
    return trouvees


class GardeActionsModifiabiliteTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor ADEV42', slug='taqinor-adev42')
        self.user = User.objects.create_user(
            username='adev42-admin', password='x', company=self.company,
            role_legacy='admin')
        client = Client.objects.create(
            company=self.company, nom='Client', prenom='ADEV42',
            telephone='+212661542042')
        produit = Produit.objects.create(
            company=self.company, nom='Panneau ADEV42 710W', sku='ADEV42-PV',
            prix_vente=Decimal('1000'), prix_achat=Decimal('700'),
            quantite_stock=100)
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-ADEV42-0001', client=client,
            created_by=self.user, taux_tva=Decimal('20'),
            statut=Devis.Statut.ACCEPTE,
            roof_layout={'result': {'panels': 9, 'kwc': 4.95}},
            electrical_design={'bom': [{'designation': 'Câble', 'q': 1}]})
        LigneDevis.objects.create(
            devis=self.devis, produit=produit, designation=produit.nom,
            quantite=Decimal('9'), prix_unitaire=Decimal('1000'),
            remise=Decimal('0'))
        self.api = APIClient()
        self.api.raise_request_exception = False
        self.api.force_authenticate(self.user)

    def _instantane(self):
        return {
            'devis': Devis.objects.filter(pk=self.devis.pk).values().first(),
            'lignes': list(LigneDevis.objects.filter(devis_id=self.devis.pk)
                           .order_by('pk').values()),
            'lots': LotDevis.objects.filter(devis_id=self.devis.pk).count(),
            'activites': DevisActivity.objects.filter(
                devis_id=self.devis.pk).count(),
        }

    def _url(self, url_path):
        if url_path is None:
            return f'{BASE}{self.devis.pk}/'
        return f'{BASE}{self.devis.pk}/{url_path}/'

    def _jouer(self, table, attendu):
        decouvertes = _ecritures_decouvertes()
        ecarts = []
        for nom, appels in table.items():
            for verbe, corps in appels:
                resp = getattr(self.api, verbe)(
                    self._url(decouvertes[nom]), corps, format='json')
                if resp.status_code != attendu:
                    ecarts.append(
                        f'{nom} {verbe.upper()} → {resp.status_code} '
                        f'(attendu {attendu}) '
                        f'{getattr(resp, "content", b"")[:160]!r}')
        return ecarts

    def test_toute_action_ecriture_classee(self):
        decouvertes = _ecritures_decouvertes()
        classees = set(GARDEES_409) | set(REFUS_400) | set(EXEMPTEES)
        non_classees = sorted(set(decouvertes) - classees)
        self.assertEqual(
            non_classees, [],
            'action d’écriture de DevisViewSet ni gardée par '
            '_refus_modifiabilite (GARDEES_409) ni exemptée avec sa raison '
            '(EXEMPTEES / REFUS_400)')
        perimees = sorted(classees - set(decouvertes))
        self.assertEqual(perimees, [],
                         'entrée de la garde pour une action disparue')

    def test_toute_action_ecriture_gardee(self):
        avant = self._instantane()
        ecarts = self._jouer(GARDEES_409, 409)
        self.assertEqual(ecarts, [], '\n'.join(ecarts))
        # Aucun geste refusé n'a écrit (statut LU, jamais écrit — règle #4).
        self.assertEqual(self._instantane(), avant)

    def test_refus_historiques_400(self):
        avant = self._instantane()
        ecarts = self._jouer(REFUS_400, 400)
        self.assertEqual(ecarts, [], '\n'.join(ecarts))
        self.assertEqual(self._instantane(), avant)
