"""ADEV41 (C-ADEV-025, critère C5) — garde de CLASSE « portée appliquée par le
seul ``DevisViewSet`` ».

Le test PARCOURT le résolveur de ``apps/ventes/urls.py`` (aucune liste de
routes recopiée) et rejoue, avec un Commercial de portée ``team`` (rôle
canonique réel : ``COMMERCIAL_PERMISSIONS`` porte ``records_scope_equipe``,
sans superviseur commun avec l'auteur), CHAQUE route qui sert ou écrit des
données de devis :

* toutes les routes de ``DevisViewSet`` et ``LigneDevisViewSet`` (actions
  ``detail=True`` ET ``detail=False``, toutes méthodes déclarées), avec des
  paramètres qui désignent D1 (``pk``, ``?devis=``, ``?client=``,
  ``?search=<référence>``, corps ``{devis, devis_id, ids, devis_ids}``) ;
* les vues hors viewset qui lisent un devis désigné (``DEVIS_HORS_VIEWSET``).

Échec si : une réponse contient l'id (objet devis), la référence, un montant
ou le téléphone de D1 ; D1 (ligne ``Devis`` + toutes ses relations inverses)
a changé après le balayage (CLAUSE PERSISTANCE) ; une route de ``ventes`` n'est
ni couverte ni déclarée dans une exemption NOMMÉE et justifiée (message
« route non couverte par la garde de portée »).

Test-du-test : retirer ``scope_queryset`` de ``LigneDevisViewSet.get_queryset``
⇒ la garde nomme ``lignedevis-list`` (référence/montant de D1 servis) et
échoue.
"""
import json
import re
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.forms.models import model_to_dict
from django.test import TestCase
from django.urls import URLResolver
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.roles.models import Role
from apps.roles.permissions_registre import COMMERCIAL_PERMISSIONS
from apps.ventes.models import Devis, LigneDevis
from authentication.models import Company

User = get_user_model()

PREFIXE = '/api/django/ventes/'

REF_D1 = 'DV-ADEV41-HORS-PORTEE'
TEL_D1 = '+212641414141'
PU_D1 = Decimal('98765.43')
MARQUEURS_MONTANT = ('98765.43', '98765,43', '98 765,43', '98 765,43',
                     '98\xa0765,43')

#: Viewsets dont TOUTES les routes (résolveur) sont balayées.
VIEWSETS_COUVERTS = ('DevisViewSet', 'LigneDevisViewSet')

#: Vues hors viewset qui lisent un devis désigné — nom de route → appel.
#: ('pk' : D1 dans le chemin ; 'corps' : POST ``{'devis': D1}``).
DEVIS_HORS_VIEWSET = {
    'devis-schema-unifilaire': 'pk',
    'devis-declaration-raccordement': 'pk',
    'etude-horaire-preview': 'corps',
    'etude-ci-preview': 'corps',
    'etude-pompage-preview': 'corps',
}

#: Routes EN ATTENTE d'une tâche ouverte qui leur applique la portée —
#: nommées, justifiées, retirées par la tâche qui les corrige.
EN_ATTENTE = {
    'devis-action-requise': (
        'ADEV64 (PLAN_AUDIT_LEAD) — « Relances du jour » : la portée équipe '
        'de views/devis_cadence.py + selectors_cadence.py est la tâche '
        'ADEV64, encore ouverte ; la garde la reprend dès son retrait ici.'),
}

_JUSTIF_PUBLIC = ('route publique à jeton : la portée est le jeton '
                  '(hors périmètre ADEV41)')
_JUSTIF_FACTURATION = ('document de facturation/encaissement : ne sert pas '
                       'de données de devis (portée facturation, hors classe '
                       'C-ADEV-025)')
_JUSTIF_CONFIG = 'réglage société ou calcul pur : ne désigne aucun devis'

#: Exemptions NOMMÉES par nom de route (jamais par numéro de ligne).
EXEMPTIONS_ROUTES = {
    'proposal-data': _JUSTIF_PUBLIC,
    'proposal-accept': _JUSTIF_PUBLIC,
    'proposal-pdf': _JUSTIF_PUBLIC,
    'proposal-roof-image': _JUSTIF_PUBLIC,
    'proposal-contact-ventes': _JUSTIF_PUBLIC,
    'proposal-otp-ventes': _JUSTIF_PUBLIC,
    'proposal-otp-lecture-demander': _JUSTIF_PUBLIC,
    'proposal-otp-lecture-verifier': _JUSTIF_PUBLIC,
    'proposal-engagement': _JUSTIF_PUBLIC,
    'proposal-virement-ventes': _JUSTIF_PUBLIC,
    'proposal-activate-option-ventes': _JUSTIF_PUBLIC,
    'suivi-public': _JUSTIF_PUBLIC,
    'export-status': 'jeton d\'export (statut d\'une tâche), aucun devis',
    'journal-ventes': _JUSTIF_FACTURATION,
    'export-comptable': _JUSTIF_FACTURATION,
    'relances-list': _JUSTIF_FACTURATION,
    'balance-agee': _JUSTIF_FACTURATION,
    'client-releve': _JUSTIF_FACTURATION,
    'client-releve-pdf': _JUSTIF_FACTURATION,
    'client-score-comportement': _JUSTIF_FACTURATION,
    'lettre-relance-pdf': _JUSTIF_FACTURATION,
    'lettre-relance-premium': _JUSTIF_FACTURATION,
    'paiements-import-releve-dry-run': _JUSTIF_FACTURATION,
    'paiements-import-releve-commit': _JUSTIF_FACTURATION,
    'ventes-cash-flow': _JUSTIF_FACTURATION,
    'ventes-analyse-facturation': _JUSTIF_FACTURATION,
    'client-credit-warning': ('avertissement de crédit du CLIENT (encours '
                              'facturé), aucune donnée de devis'),
    'fiche-remise-premium': ('fiche de remise d\'un CHANTIER (portée '
                             'installations)'),
    'numerotation-audit': 'administrateur seul (IsAdminRole) — portée all',
    'numerotation-preview': 'prochaine référence calculée, aucun devis lu',
    'schema-unifilaire': (_JUSTIF_CONFIG + ' (paramètres du corps, '
                          'jamais un devis)'),
    'toiture-charge': _JUSTIF_CONFIG,
    'economie-pompage-preview': (_JUSTIF_CONFIG + ' (calcul pur sur le '
                                 'corps, ne lit aucun devis)'),
    'economie-ci-preview': (_JUSTIF_CONFIG + ' (calcul pur sur le corps, '
                            'ne lit aucun devis)'),
    'email-config': _JUSTIF_CONFIG,
    'roof-config': _JUSTIF_CONFIG,
    'prix-applicable': _JUSTIF_CONFIG + ' (liste de prix)',
    'parametres-gammes': _JUSTIF_CONFIG,
    'calendrier-reglementaire': ('échéances des dossiers réglementaires '
                                 '(chantier), aucun devis'),
    'ventes-dashboard': (
        'agrégats société du tableau de bord quote-to-cash (aucune ligne de '
        'devis servie) ; la portée des AGRÉGATS par rôle est une décision '
        'distincte de C-ADEV-025 (ligne-à-ligne)'),
    'api-root': 'racine du routeur DRF (liens), aucune donnée',
}

#: Exemptions NOMMÉES par viewset (routeur) : documents distincts du devis.
EXEMPTIONS_VIEWSETS = {
    'BonCommandeViewSet': 'bon de commande (aval) — portée propre au BC',
    'FactureViewSet': _JUSTIF_FACTURATION,
    'LigneFactureViewSet': _JUSTIF_FACTURATION,
    'PaiementViewSet': _JUSTIF_FACTURATION,
    'AvoirViewSet': _JUSTIF_FACTURATION,
    'NoteDebitViewSet': _JUSTIF_FACTURATION,
    'FollowupLevelViewSet': _JUSTIF_FACTURATION,
    'ParametrageRelanceClientViewSet': _JUSTIF_FACTURATION,
    'PromessePaiementViewSet': _JUSTIF_FACTURATION,
    'RemiseEncaissementViewSet': _JUSTIF_FACTURATION,
    'MandatPaiementViewSet': _JUSTIF_FACTURATION,
    'DevisPresetViewSet': ('preset de composition (gabarit société), aucun '
                           'devis client'),
    'RegulatoryDossierViewSet': 'dossier réglementaire (chantier)',
    'DossierChecklistItemViewSet': 'dossier réglementaire (chantier)',
    'DossierExchangeViewSet': 'dossier réglementaire (chantier)',
    'SubventionDossierViewSet': 'dossier de subvention (chantier)',
    'Regularisation8221ViewSet': 'régularisation 82-21 (chantier)',
    'CommissioningTestViewSet': 'recette de mise en service (chantier)',
    'IVCurveCaptureViewSet': 'courbe I-V (chantier)',
    'AsBuiltPackViewSet': 'pack as-built (chantier)',
    'AttestationConformiteViewSet': 'attestation de conformité (chantier)',
    'TestPerformanceReceptionViewSet': 'test PR de réception (chantier)',
    'AttestationREViewSet': 'attestation EnR (chantier)',
    'ListePrixViewSet': _JUSTIF_CONFIG + ' (liste de prix)',
    'PlanCommissionViewSet': ('plan de commission (gate prix_achat_voir), '
                              'aucun devis'),
}

_METHODES = ('get', 'post', 'put', 'patch', 'delete')


def _routes_ventes():
    """(nom, route brute, callback) de chaque URLPattern de ``ventes``,
    préfixes d'``include`` concaténés (parcours du résolveur)."""
    import apps.ventes.urls as urls_ventes

    def parcourir(motifs, prefixe=''):
        for motif in motifs:
            if isinstance(motif, URLResolver):
                yield from parcourir(motif.url_patterns,
                                     prefixe + str(motif.pattern))
            else:
                yield motif.name, prefixe + str(motif.pattern), motif.callback

    return list(parcourir(urls_ventes.urlpatterns))


def _parametres(route):
    noms = re.findall(r'<(?:\w+:)?(\w+)>', route)
    noms += re.findall(r'\(\?P<(\w+)>', route)
    return noms


def _construire(route, valeurs):
    url = re.sub(r'<(?:\w+:)?(\w+)>',
                 lambda m: str(valeurs[m.group(1)]), route)
    url = re.sub(r'\(\?P<(\w+)>[^)]*\)',
                 lambda m: str(valeurs[m.group(1)]), url)
    url = url.replace('^', '').replace('$', '').replace('\\.', '.')
    return PREFIXE + url


def _methodes(callback):
    actions = getattr(callback, 'actions', None)
    if actions:
        return sorted(m for m in actions if m in _METHODES)
    cls = getattr(callback, 'cls', None)
    if cls is None:
        return ['get']
    return [m for m in _METHODES if hasattr(cls, m)]


def _classe(callback):
    cls = getattr(callback, 'cls', None)
    return cls.__name__ if cls is not None else ''


def _corps(reponse):
    if getattr(reponse, 'streaming', False):
        return b''.join(reponse.streaming_content)
    return reponse.content or b''


class GardePorteeVentesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ADEV41', slug='adev41-co')
        role = Role.objects.create(
            company=cls.company, nom='Commercial',
            permissions=list(COMMERCIAL_PERMISSIONS), est_systeme=False)
        cls.commercial = User.objects.create_user(
            username='adev41_com', password='x', role=role,
            role_legacy='responsable', company=cls.company)
        cls.collegue = User.objects.create_user(
            username='adev41_collegue', password='x',
            role_legacy='responsable', company=cls.company)
        cls.client_d1 = Client.objects.create(
            company=cls.company, nom='Client Hors Portée ADEV41',
            email='adev41-d1@example.com', telephone=TEL_D1)
        cls.client_d2 = Client.objects.create(
            company=cls.company, nom='Client Propre ADEV41',
            email='adev41-d2@example.com', telephone='+212600000002')
        cls.d1 = Devis.objects.create(
            company=cls.company, reference=REF_D1, client=cls.client_d1,
            created_by=cls.collegue)
        LigneDevis.objects.create(
            devis=cls.d1, designation='Onduleur ADEV41', quantite=1,
            prix_unitaire=PU_D1)
        cls.d2 = Devis.objects.create(
            company=cls.company, reference='DV-ADEV41-PROPRE',
            client=cls.client_d2, created_by=cls.commercial)
        LigneDevis.objects.create(
            devis=cls.d2, designation='Câblage ADEV41', quantite=1,
            prix_unitaire=Decimal('100'))

    def setUp(self):
        self.api = APIClient()
        self.api.force_authenticate(self.commercial)
        # Une 500 doit rester une RÉPONSE inspectée (marqueurs), pas lever.
        self.api.raise_request_exception = False

    # -- empreinte de D1 (CLAUSE PERSISTANCE) --------------------------------
    def _empreinte_d1(self):
        ligne = Devis.objects.filter(pk=self.d1.pk).values().first()
        relations = {}
        for rel in Devis._meta.related_objects:
            if rel.many_to_many or not getattr(rel, 'field', None):
                continue
            modele = rel.related_model
            try:
                lignes = modele._base_manager.filter(
                    **{rel.field.name: self.d1.pk})
                relations[rel.name] = sorted(
                    json.dumps(model_to_dict(o), sort_keys=True, default=str)
                    for o in lignes)
            except Exception:  # relation non filtrable par pk : ignorée
                continue
        return json.dumps(ligne, sort_keys=True, default=str), relations

    # -- détection d'une fuite ----------------------------------------------
    def _objets_d1(self, noeud):
        if isinstance(noeud, dict):
            if noeud.get('devis') == self.d1.pk \
                    or noeud.get('devis_id') == self.d1.pk:
                return True
            if noeud.get('id') == self.d1.pk and 'reference' in noeud:
                return True
            return any(self._objets_d1(v) for v in noeud.values())
        if isinstance(noeud, list):
            return any(self._objets_d1(v) for v in noeud)
        return False

    def _fuite(self, reponse):
        corps = _corps(reponse)
        texte = corps.decode('utf-8', errors='ignore')
        motifs = []
        if REF_D1 in texte:
            motifs.append('référence')
        if TEL_D1 in texte or TEL_D1[4:] in texte:
            motifs.append('téléphone')
        if any(m in texte for m in MARQUEURS_MONTANT):
            motifs.append('montant')
        ctype = reponse.get('Content-Type', '') or ''
        if 'json' in ctype and texte:
            try:
                if self._objets_d1(json.loads(texte)):
                    motifs.append('id')
            except ValueError:
                pass
        if 200 <= reponse.status_code < 300 and (
                'pdf' in ctype or ctype.startswith('image/')):
            motifs.append('document binaire %s servi' % ctype)
        return motifs

    # -- balayage ------------------------------------------------------------
    def _appels(self):
        """Liste (nom, méthode, url, corps) des appels à rejouer, et la liste
        des routes non classées."""
        valeurs = {'pk': self.d1.pk, 'client_id': self.client_d1.pk}
        requete = '?devis=%s&devis_id=%s&client=%s&search=%s' % (
            self.d1.pk, self.d1.pk, self.client_d1.pk, REF_D1)
        # Jamais ``client`` dans le corps : un ``create`` réussi rattacherait
        # un devis PROPRE au client de D1 (faux positif « téléphone »).
        corps = {'devis': self.d1.pk, 'devis_id': self.d1.pk,
                 'ids': [self.d1.pk], 'devis_ids': [self.d1.pk]}
        appels, non_classees, vues = [], [], set()
        for nom, route, callback in _routes_ventes():
            params = _parametres(route)
            if 'format' in params:
                continue  # doublon suffixe de format du routeur
            classe = _classe(callback)
            if classe in VIEWSETS_COUVERTS:
                cle = (nom, route)
                if cle in vues:
                    continue
                vues.add(cle)
                if nom in EN_ATTENTE:
                    continue
                url = _construire(route, {p: valeurs.get(p, self.d1.pk)
                                          for p in params})
                for methode in _methodes(callback):
                    if methode == 'get':
                        appels.append((nom, methode, url + requete, None))
                    else:
                        appels.append((nom, methode, url, corps))
            elif nom in DEVIS_HORS_VIEWSET:
                if DEVIS_HORS_VIEWSET[nom] == 'pk':
                    url = _construire(route, {p: valeurs.get(p, self.d1.pk)
                                              for p in params})
                    appels.append((nom, 'get', url, None))
                else:
                    appels.append((nom, 'post', _construire(route, {}),
                                   {'devis': self.d1.pk}))
            elif nom in EXEMPTIONS_ROUTES or classe in EXEMPTIONS_VIEWSETS:
                continue
            else:
                non_classees.append('%s (%s, %s)' % (nom, route, classe))
        return appels, non_classees

    def test_aucune_route_ne_sort_de_la_portee(self):
        avant = self._empreinte_d1()
        appels, non_classees = self._appels()
        self.assertEqual(
            non_classees, [],
            'route non couverte par la garde de portée — la couvrir ou la '
            'déclarer (nom + justification) dans EXEMPTIONS_ROUTES / '
            'EXEMPTIONS_VIEWSETS : %s' % non_classees)
        # La garde n'est pas vide : le viewset devis a bien été parcouru.
        noms = {a[0] for a in appels}
        self.assertIn('devis-detail', noms)
        self.assertIn('devis-list', noms)
        self.assertTrue(any(n.startswith('lignedevis') for n in noms), noms)
        self.assertGreater(len(appels), 40)

        fuites = []
        for nom, methode, url, corps in appels:
            if corps is None:
                reponse = getattr(self.api, methode)(url)
            else:
                reponse = getattr(self.api, methode)(url, corps,
                                                     format='json')
            motifs = self._fuite(reponse)
            if motifs:
                fuites.append('%s %s %s → %s %s' % (
                    nom, methode.upper(), url, reponse.status_code, motifs))
        self.assertEqual(fuites, [], 'données du devis hors portée D1 '
                                     'servies : %s' % fuites)

        # CLAUSE PERSISTANCE — D1 relu après le balayage : identique.
        self.assertEqual(self._empreinte_d1(), avant,
                         'une écriture a modifié le devis hors portée D1')

    def test_propre_devis_reste_lisible(self):
        """Témoin : la garde ne passe pas « à vide » (D2 se lit)."""
        reponse = self.api.get('%sdevis/%s/' % (PREFIXE, self.d2.pk))
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.data['reference'], 'DV-ADEV41-PROPRE')
        lignes = self.api.get('%sdevis-lignes/?devis=%s' % (
            PREFIXE, self.d2.pk))
        self.assertEqual(lignes.status_code, 200)
        self.assertIn('Câblage ADEV41', lignes.content.decode('utf-8'))

    def test_exemptions_toutes_justifiees_et_vivantes(self):
        """Une exemption sans justification, ou qui ne nomme plus aucune
        route réelle, est refusée (la liste ne pourrit pas)."""
        routes = {nom for nom, _r, _c in _routes_ventes()}
        classes = {_classe(c) for _n, _r, c in _routes_ventes()}
        for nom, justif in {**EXEMPTIONS_ROUTES, **EN_ATTENTE}.items():
            self.assertTrue(justif and len(justif) > 10, nom)
            self.assertIn(nom, routes, 'exemption morte : %s' % nom)
        for nom in DEVIS_HORS_VIEWSET:
            self.assertIn(nom, routes, 'route couverte disparue : %s' % nom)
        for classe, justif in EXEMPTIONS_VIEWSETS.items():
            self.assertTrue(justif, classe)
            self.assertIn(classe, classes, 'exemption morte : %s' % classe)
