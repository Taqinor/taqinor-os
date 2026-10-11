"""ACRM53 — garde de CLASSE : le masquage PII est une propriété de la
RÉPONSE, pas seulement du sérialiseur. Un rôle = ``COMMERCIAL_PERMISSIONS``
− ``client_pii_voir`` rejoue CHAQUE action GET/POST de ``LeadViewSet`` et de
``ClientViewSet`` (list/retrieve + ``get_extra_actions()``, découvertes par
introspection) sur un lead / client / activité de SA portée porteurs du
numéro témoin ; aucune réponse (JSON, texte ou xlsx) ne doit contenir le
numéro, brut ni normalisé.

Chaque appel est rejoué dans un point de sauvegarde ANNULÉ : toutes les
actions partent du même état, une écriture n'en contamine aucune autre.
Une action d'écriture coûteuse ou externe est déclarée dans
``EXCLUES`` avec sa raison ; une action NOUVELLE non déclarée fait échouer
la garde en la nommant.

Test-du-test : retirer ``context=`` d'un seul sérialiseur (la réponse de
``convertir-client``) ⇒ la garde échoue en nommant l'action.
"""
from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm import stages
from apps.crm.models import Client, Lead, LeadActivity
from apps.crm.tests_alea_garde_portee_actions import _contenu
from apps.crm.clients_views import ClientViewSet
from apps.crm.views import LeadViewSet
from apps.roles.models import Role
from apps.roles.permissions_registre import COMMERCIAL_PERMISSIONS
from authentication.models import Company

User = get_user_model()

BASE = '/api/django/crm'
TEMOIN = '+212661909901'
TEMOIN_NORMALISE = '661909901'

#: Corps / paramètres des actions qui ne répondent utilement qu'avec une
#: entrée valide. ``{L}`` / ``{C}`` = lead / client témoins.
CHARGES = {
    ('LeadViewSet', 'convertir_client'): {'mode': 'nouveau'},
    ('LeadViewSet', 'noter'): {'body': 'note de garde'},
    ('LeadViewSet', 'log_interaction'): {'kind': 'appel',
                                         'body': 'appel de garde'},
    ('LeadViewSet', 'check_duplicates'): {'telephone': TEMOIN,
                                          'phone': TEMOIN},
    ('LeadViewSet', 'export_xlsx'): {'ids': ['{L}']},
    ('LeadViewSet', 'bulk'): {'action': 'add_tag', 'ids': ['{L}'],
                              'tag': 'garde'},
    ('LeadViewSet', 'relances'): {'scope': 'all'},
    ('LeadViewSet', 'placement_cadences'): {'apply': False},
    ('ClientViewSet', 'export_xlsx'): {'ids': ['{C}']},
    ('ClientViewSet', 'search'): {'q': 'Temoin', 'telephone': TEMOIN},
    ('ClientViewSet', 'segments'): {'segment': 'top'},
}

#: Actions NON rejouées — une ligne par raison (écriture coûteuse/externe).
EXCLUES = {
    ('LeadViewSet', 'scan_carte'): 'OCR externe (Zhipu) sur une photo, ne '
                                   'lit aucun lead existant',
    ('LeadViewSet', 'resoudre_gps'): 'géocodeur réseau externe, ne lit '
                                     'aucun lead',
    ('LeadViewSet', 'whatsapp_devis'): 'envoi externe WhatsApp du devis',
    ('LeadViewSet', 'devis_auto'): 'écriture coûteuse : fabrique un devis '
                                   'complet côté ventes',
}


class _Annule(Exception):
    """Sentinelle : annule le point de sauvegarde après capture."""


class GardePiiTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor ACRM53', slug='taqinor-acrm53')
        sans_pii = Role.objects.create(
            company=self.company, nom='Commercial sans PII',
            permissions=[p for p in COMMERCIAL_PERMISSIONS
                         if p != 'client_pii_voir'])
        self.user = User.objects.create_user(
            username='acrm53-masque', password='x', company=self.company,
            role=sans_pii)
        self.client_c = Client.objects.create(
            company=self.company, nom='Temoin', prenom='Client',
            telephone=TEMOIN, email='temoin-acrm53@example.com')
        self.lead = Lead.objects.create(
            company=self.company, nom='Temoin', prenom='Lead',
            telephone=TEMOIN, whatsapp=TEMOIN,
            email='temoin-acrm53@example.com', owner=self.user,
            stage=stages.CONTACTED, client=self.client_c)
        self.activite = LeadActivity.objects.create(
            company=self.company, lead=self.lead, user=self.user,
            kind=LeadActivity.Kind.MODIFICATION, field='telephone',
            old_value='', new_value=TEMOIN)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _remplacer(self, valeur):
        if isinstance(valeur, list):
            return [self._remplacer(v) for v in valeur]
        return {'{L}': self.lead.pk, '{C}': self.client_c.pk}.get(
            valeur, valeur) if isinstance(valeur, str) else valeur

    def _rejouer(self, verbe, url, charge):
        """Appel dans un point de sauvegarde ANNULÉ ; rend le texte de la
        réponse (ou une erreur rapportée)."""
        sortie = {}
        try:
            with transaction.atomic():
                if verbe == 'get':
                    resp = self.api.get(url, charge)
                else:
                    resp = self.api.post(url, charge, format='json')
                sortie['statut'] = resp.status_code
                sortie['texte'] = _contenu(resp)
                raise _Annule
        except _Annule:
            pass
        except Exception as exc:  # noqa: BLE001 — rapportée, jamais masquée
            sortie['erreur'] = repr(exc)[:200]
        return sortie

    def _appels(self, viewset, prefixe, pk):
        """(nom, verbe, url, charge) de list/retrieve + toutes les actions."""
        appels = [('list', 'get', f'{BASE}/{prefixe}/', {}),
                  ('retrieve', 'get', f'{BASE}/{prefixe}/{pk}/', {})]
        for action in viewset.get_extra_actions():
            cle = (viewset.__name__, action.__name__)
            if cle in EXCLUES:
                continue
            chemin = action.url_path.replace(
                '(?P<activite_id>[^/.]+)', str(self.activite.pk))
            url = (f'{BASE}/{prefixe}/{pk}/{chemin}/' if action.detail
                   else f'{BASE}/{prefixe}/{chemin}/')
            charge = {k: self._remplacer(v)
                      for k, v in CHARGES.get(cle, {}).items()}
            for verbe in sorted(set(action.mapping) & {'get', 'post'}):
                appels.append((action.__name__, verbe, url, charge))
        return appels

    def test_exclusions_a_jour(self):
        noms = {(vs.__name__, a.__name__)
                for vs in (LeadViewSet, ClientViewSet)
                for a in vs.get_extra_actions()}
        self.assertEqual(
            sorted(k for k in list(EXCLUES) + list(CHARGES)
                   if k not in noms), [],
            'exclusion/charge pour une action qui n’existe plus')

    def test_aucune_action_ne_rend_le_numero(self):
        fuites, erreurs = [], []
        for viewset, prefixe, pk in (
                (LeadViewSet, 'leads', self.lead.pk),
                (ClientViewSet, 'clients', self.client_c.pk)):
            for nom, verbe, url, charge in self._appels(
                    viewset, prefixe, pk):
                sortie = self._rejouer(verbe, url, charge)
                if 'erreur' in sortie:
                    erreurs.append(f'{viewset.__name__}.{nom} '
                                   f'{verbe.upper()} → {sortie["erreur"]}')
                    continue
                texte = sortie['texte']
                for numero in (TEMOIN, TEMOIN_NORMALISE):
                    if numero in texte:
                        fuites.append(
                            f'{viewset.__name__}.{nom} {verbe.upper()} '
                            f'{url} → {sortie["statut"]} contient {numero}')
        self.assertEqual(fuites, [], 'numéro témoin rendu à un rôle sans '
                         'client_pii_voir :\n' + '\n'.join(fuites + erreurs))
