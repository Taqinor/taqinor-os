"""ADEV41 (C-ADEV-025) — garde de CLASSE : la portée équipe n'est pas appliquée
par le seul ``DevisViewSet``. Un Commercial de portée ``team`` (rôle canonique
réel, ``COMMERCIAL_PERMISSIONS``) rejoue CHAQUE route de ``apps/ventes/urls.py``
qui sert ou écrit des données de devis, avec des paramètres qui désignent D1
(le devis d'un collègue hors équipe) :

* les routes sont DÉCOUVERTES en parcourant le résolveur de ``apps.ventes.urls``
  (viewsets du routeur : liste ET détail, actions ``detail=False`` comprises ;
  vues fonction) ;
* chacune est SONDÉE (``ROUTES_SONDEES`` : toute route de ``DevisViewSet`` /
  ``LigneDevisViewSet``, plus les vues fonction nommées) ou EXEMPTÉE par NOM
  (route ou viewset) avec sa raison — une route nouvelle non classée échoue
  « route non couverte par la garde de portée », jamais ignorée ;
* aucune réponse ne doit contenir l'id (fiche), la référence, un montant, le
  nom ou le téléphone du client de D1 ; D1 relu après le balayage (CLAUSE
  PERSISTANCE) doit être identique, et aucune copie de D1 ne doit exister.

Test-du-test : ``test_sonde_voit_hors_portee_en_portee_all`` rejoue la liste en
Directeur (portée ``all``) — le scanner DOIT y trouver D1. Retirer
``scope_queryset`` de ``LigneDevisViewSet`` ⇒ la garde nomme ``lignedevis-list``
/ ``lignedevis-detail`` et échoue. Aucun mock : rôles, ``core.scoping``, vues
et résolveur réels. Routes publiques à jeton : hors périmètre (portée = jeton).
"""
import io
import re
import zipfile
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import URLPattern, URLResolver
from rest_framework.test import APIClient

from apps.crm.models import Client, Lead
from apps.roles.models import Role
from apps.roles.permissions_registre import COMMERCIAL_PERMISSIONS
from apps.stock.models import Produit
from apps.ventes.models import (
    ConfigurationDevisSnapshot, Devis, DevisActivity, LigneDevis, ShareLink)
from authentication.models import Company

User = get_user_model()

BASE = '/api/django/ventes/'
REF_HORS = 'DEV-HORS-4141'
CLIENT_HORS = 'Zorglub41'
TEL_HORS = '+212661541041'
EMAIL_HORS = 'zorglub41.hors@example.ma'
LIGNE_HORS = 'Ligne Zorglub41 hors portee'
PU_HORS = Decimal('98765.43')
#: Montants de D1 (HT, TTC à 20 %), cherchés séparateurs retirés.
MONTANTS_HORS = ('98765.43', '98765,43', '118518.52', '118518,52')

#: Viewsets dont TOUTES les routes sont sondées (liste, détail, actions).
VIEWSETS_SONDES = {'DevisViewSet', 'LigneDevisViewSet'}

#: Vues fonction qui lisent un devis désigné (``<pk>`` ou ``devis`` du corps).
ROUTES_SONDEES = {
    'devis-schema-unifilaire', 'devis-declaration-raccordement',
    'etude-horaire-preview', 'etude-ci-preview', 'etude-pompage-preview',
    'economie-pompage-preview', 'economie-ci-preview',
    'ventes-dashboard',
}

#: Routes sondées dont la fuite est CONNUE et portée par une tâche ouverte :
#: leurs fuites sont rapportées sans faire échouer la garde. Retirer l'entrée
#: dès que la tâche est livrée.
EN_ATTENTE = {
    'devis-action-requise':
        'ADEV64 (PLAN_AUDIT_LEAD) — portée équipe de « Relances du jour ».',
}

#: Viewsets EXEMPTÉS (par nom de classe), avec leur raison.
VIEWSETS_EXEMPTES = {
    'BonCommandeViewSet': 'document aval (BC) — portée du module facturation.',
    'FactureViewSet': 'facturation — portée propre au module facturation.',
    'LigneFactureViewSet': 'lignes de facture — portée facturation.',
    'PaiementViewSet': 'encaissements — portée facturation.',
    'AvoirViewSet': 'avoirs — portée facturation.',
    'NoteDebitViewSet': 'notes de débit — portée facturation.',
    'FollowupLevelViewSet': 'paramétrage des niveaux de relance (société).',
    'ParametrageRelanceClientViewSet': 'paramétrage relance par client.',
    'PromessePaiementViewSet': 'promesses de paiement — facturation.',
    'DevisPresetViewSet': 'modèles de devis de la société (aucun devis).',
    'RegulatoryDossierViewSet': 'dossiers réglementaires (chantier).',
    'DossierChecklistItemViewSet': 'checklist réglementaire (chantier).',
    'DossierExchangeViewSet': 'échanges réglementaires (chantier).',
    'SubventionDossierViewSet': 'dossiers de subvention (chantier).',
    'Regularisation8221ViewSet': 'régularisations 82-21 (chantier).',
    'CommissioningTestViewSet': 'recettes de mise en service (chantier).',
    'IVCurveCaptureViewSet': 'courbes I-V (chantier).',
    'AsBuiltPackViewSet': 'dossiers des ouvrages exécutés (chantier).',
    'AttestationConformiteViewSet': 'attestations de conformité (chantier).',
    'TestPerformanceReceptionViewSet': 'tests PR de réception (chantier).',
    'AttestationREViewSet': 'attestations RE (chantier).',
    'RemiseEncaissementViewSet': 'remises en banque — facturation.',
    'ListePrixViewSet': 'listes de prix de la société (catalogue).',
    'PlanCommissionViewSet': 'plans de commission (paramétrage).',
    'APIRootView': 'racine navigable du routeur, aucune donnée.',
}

#: Vues fonction EXEMPTÉES (par nom de route), avec leur raison.
ROUTES_EXEMPTEES = {
    'proposal-data': 'publique à jeton (portée = jeton).',
    'proposal-accept': 'publique à jeton.',
    'proposal-pdf': 'publique à jeton.',
    'proposal-roof-image': 'publique à jeton.',
    'proposal-contact-ventes': 'publique à jeton.',
    'proposal-otp-ventes': 'publique à jeton.',
    'proposal-otp-lecture-demander': 'publique à jeton.',
    'proposal-otp-lecture-verifier': 'publique à jeton.',
    'proposal-engagement': 'publique à jeton.',
    'proposal-virement-ventes': 'publique à jeton.',
    'proposal-activate-option-ventes': 'publique à jeton.',
    'suivi-public': 'publique à jeton.',
    'export-status': 'statut d’un export par jeton.',
    'journal-ventes': 'journal comptable (factures), palier comptable.',
    'export-comptable': 'export comptable (factures), palier comptable.',
    'numerotation-audit': 'audit de numérotation (références seules).',
    'numerotation-preview': 'aperçu du prochain numéro (aucun devis).',
    'relances-list': 'relances de FACTURES — portée facturation.',
    'balance-agee': 'balance âgée des factures — portée facturation.',
    'client-releve': 'relevé client (factures) — portée facturation.',
    'client-releve-pdf': 'relevé client PDF — portée facturation.',
    'client-score-comportement': 'score de paiement client — facturation.',
    'lettre-relance-pdf': 'lettre de relance de facture.',
    'lettre-relance-premium': 'lettre de relance de facture.',
    'fiche-remise-premium': 'fiche de remise de chantier.',
    'schema-unifilaire': 'calcul PUR depuis les paramètres du corps.',
    'toiture-charge': 'calcul PUR de charge de toiture.',
    'email-config': 'configuration e-mail de la société.',
    'roof-config': 'configuration toiture de la société.',
    'client-credit-warning': 'encours client — portée facturation.',
    'paiements-import-releve-dry-run': 'import de relevé — facturation.',
    'paiements-import-releve-commit': 'import de relevé — facturation.',
    'ventes-cash-flow': 'prévision de trésorerie (factures).',
    'ventes-analyse-facturation': 'analyse de facturation (factures).',
    'calendrier-reglementaire': 'calendrier réglementaire (chantiers).',
    'prix-applicable': 'prix catalogue d’un produit (aucun devis).',
    'parametres-gammes': 'paramètres de gammes de la société.',
}

METHODES = ('get', 'post', 'put', 'patch', 'delete')


def _routes():
    """``[(nom, motif, callback)]`` de ``apps.ventes.urls`` (hors suffixes de
    format du routeur)."""
    from apps.ventes import urls

    def _parcourir(motifs, prefixe=''):
        for m in motifs:
            if isinstance(m, URLResolver):
                yield from _parcourir(m.url_patterns, prefixe + str(m.pattern))
            elif isinstance(m, URLPattern):
                yield m.name, prefixe + str(m.pattern), m.callback

    return [r for r in _parcourir(urls.urlpatterns)
            if '(?P<format>' not in r[1] and 'drf_format_suffix' not in r[1]]


def _classe(callback):
    cls = getattr(callback, 'cls', None)
    return getattr(cls, '__name__', getattr(callback, '__name__', ''))


def _methodes(callback):
    actions = getattr(callback, 'actions', None)
    if actions:
        return sorted(m for m in actions if m in METHODES)
    cls = getattr(callback, 'cls', None)
    return [m for m in METHODES if cls is not None and hasattr(cls, m)]


def _url(motif, kwargs):
    """URL concrète d'un motif (regex du routeur ou ``path``)."""
    def _valeur(m):
        return str(kwargs[m.group(1)])
    s = re.sub(r'\(\?P<(\w+)>[^)]*\)', _valeur, motif)
    s = re.sub(r'<(?:\w+:)?(\w+)>', _valeur, s)
    return BASE + s.lstrip('^').rstrip('$')


def _contenu(resp):
    if getattr(resp, 'streaming', False):
        brut = b''.join(resp.streaming_content)
    else:
        brut = getattr(resp, 'content', b'') or b''
    if brut[:2] == b'PK':
        try:
            with zipfile.ZipFile(io.BytesIO(brut)) as z:
                return '\n'.join(
                    z.read(n).decode('utf-8', 'ignore') for n in z.namelist())
        except zipfile.BadZipFile:
            pass
    return brut.decode('utf-8', 'ignore')


def _fiches(donnee, pk, cles):
    """Vrai si un dict a ``id == pk`` ET une clé descriptive de ``cles``."""
    if isinstance(donnee, dict):
        if donnee.get('id') == pk and any(k in donnee for k in cles):
            return True
        return any(_fiches(v, pk, cles) for v in donnee.values())
    if isinstance(donnee, list):
        return any(_fiches(v, pk, cles) for v in donnee)
    return False


class GardePorteeVentesTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor ADEV41', slug='taqinor-adev41')
        role_com = Role.objects.create(
            company=self.company, nom='Commercial',
            permissions=list(COMMERCIAL_PERMISSIONS))
        # Portée ``team`` sans superviseur → soi seul ; le collègue n'a aucun
        # superviseur commun.
        self.commercial = User.objects.create_user(
            username='adev41-com', password='x', company=self.company,
            role=role_com)
        self.collegue = User.objects.create_user(
            username='adev41-collegue', password='x', company=self.company,
            role=role_com)
        self.directeur = User.objects.create_user(
            username='adev41-dir', password='x', company=self.company,
            role_legacy='admin')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau ADEV41 710W', sku='ADEV41-PV',
            prix_vente=Decimal('1000'), prix_achat=Decimal('700'),
            quantite_stock=100)
        client_hors = Client.objects.create(
            company=self.company, nom=CLIENT_HORS, prenom='Hors',
            telephone=TEL_HORS, email=EMAIL_HORS)
        lead_hors = Lead.objects.create(
            company=self.company, nom=CLIENT_HORS, prenom='Hors',
            telephone=TEL_HORS, owner=self.collegue, client=client_hors)
        self.d1 = Devis.objects.create(
            company=self.company, reference=REF_HORS, client=client_hors,
            lead=lead_hors, created_by=self.collegue, taux_tva=Decimal('20'),
            statut=Devis.Statut.BROUILLON)
        self.l1 = LigneDevis.objects.create(
            devis=self.d1, produit=self.produit, designation=LIGNE_HORS,
            quantite=Decimal('1'), prix_unitaire=PU_HORS,
            remise=Decimal('0'))
        # D2 : le devis de l'utilisateur sondé (les sondes ont de quoi rendre).
        client_moi = Client.objects.create(
            company=self.company, nom='Dans', prenom='Portee',
            telephone='+212661541099')
        self.d2 = Devis.objects.create(
            company=self.company, reference='DEV-DANS-4142',
            client=client_moi, created_by=self.commercial,
            taux_tva=Decimal('20'))
        LigneDevis.objects.create(
            devis=self.d2, produit=self.produit, designation='Ligne propre',
            quantite=Decimal('2'), prix_unitaire=Decimal('1000'),
            remise=Decimal('0'))

    # ── outillage ───────────────────────────────────────────────────────
    def _api(self, user):
        api = APIClient()
        api.raise_request_exception = False
        api.force_authenticate(user)
        return api

    def _instantane(self):
        return {
            'devis': Devis.objects.filter(pk=self.d1.pk).values().first(),
            'lignes': list(LigneDevis.objects.filter(devis_id=self.d1.pk)
                           .order_by('pk').values()),
            'activites': DevisActivity.objects.filter(
                devis_id=self.d1.pk).count(),
            'liens': ShareLink.objects.filter(devis_id=self.d1.pk).count(),
            'instantanes': ConfigurationDevisSnapshot.objects.filter(
                devis_id=self.d1.pk).count(),
            # Une COPIE de D1 (duplication, variante, gamme, révision…)
            # emporte sa ligne : elle ne doit exister nulle part ailleurs.
            'copies': LigneDevis.objects.filter(
                designation=LIGNE_HORS).exclude(devis_id=self.d1.pk).count(),
        }

    def _fuites(self, resp):
        texte = _contenu(resp)
        compact = re.sub(r'[\s  ]', '', texte)
        fuites = [m for m in (REF_HORS, CLIENT_HORS, TEL_HORS, EMAIL_HORS,
                              LIGNE_HORS) if m in texte]
        fuites += ['montant %s' % m for m in MONTANTS_HORS if m in compact]
        try:
            donnee = resp.json()
        except Exception:  # noqa: BLE001 — binaire, PDF ou vide
            donnee = None
        if isinstance(donnee, (dict, list)):
            if _fiches(donnee, self.d1.pk, (
                    'reference', 'statut', 'total_ttc', 'client', 'lignes')):
                fuites.append('fiche devis id %s' % self.d1.pk)
            if _fiches(donnee, self.l1.pk, ('designation', 'prix_unitaire')):
                fuites.append('fiche ligne id %s' % self.l1.pk)
        return fuites

    def _sondes(self):
        """``[(nom, verbe, url, charge)]`` de toutes les routes sondées, et
        la liste des routes non classées."""
        d1, l1 = self.d1.pk, self.l1.pk
        designer_get = {'devis': d1, 'devis_id': d1, 'ids': d1,
                        'search': REF_HORS, 'q': REF_HORS}
        designer_post = {'devis': d1, 'devis_id': d1, 'ids': [d1],
                         'devis_ids': [d1], 'source': d1}
        sondes, non_classees = [], []
        for nom, motif, callback in _routes():
            classe = _classe(callback)
            sondee = classe in VIEWSETS_SONDES or nom in ROUTES_SONDEES
            if not sondee:
                if classe not in VIEWSETS_EXEMPTES \
                        and nom not in ROUTES_EXEMPTEES:
                    non_classees.append(f'{nom} ({classe})')
                continue
            pk = l1 if classe == 'LigneDevisViewSet' else d1
            url = _url(motif, {'pk': pk, 'token': '0' * 32})
            detail = bool(re.search(r'<(?:\w+:)?pk>|\(\?P<pk>', motif))
            for verbe in _methodes(callback):
                if verbe == 'get':
                    charge = {} if detail else designer_get
                elif nom == 'lignedevis-list':
                    # Une vraie tentative d'ÉCRITURE sur D1.
                    charge = {'devis': d1, 'produit': self.produit.pk,
                              'designation': 'Intrus', 'quantite': '1',
                              'prix_unitaire': '1', 'remise': '0'}
                else:
                    charge = {} if detail else designer_post
                sondes.append((nom, verbe, url, charge))
        # Les suppressions en DERNIER : une fuite d'écriture ne doit pas
        # masquer les lectures suivantes.
        sondes.sort(key=lambda s: s[1] == 'delete')
        return sondes, non_classees

    def _jouer(self, user):
        api = self._api(user)
        fuites, attendues = [], []
        for nom, verbe, url, charge in self._sondes()[0]:
            if verbe == 'get':
                resp = api.get(url, charge)
            else:
                resp = getattr(api, verbe)(url, charge, format='json')
            for f in self._fuites(resp):
                ligne = (f'{nom} {verbe.upper()} {url} → '
                         f'{resp.status_code} fuite {f}')
                (attendues if nom in EN_ATTENTE else fuites).append(ligne)
        return fuites, attendues

    # ── la garde ────────────────────────────────────────────────────────
    def test_toutes_les_routes_sont_classees(self):
        _sondes, non_classees = self._sondes()
        self.assertEqual(
            sorted(non_classees), [],
            'route non couverte par la garde de portée — la sonder '
            '(VIEWSETS_SONDES / ROUTES_SONDEES) ou l’exempter avec sa raison '
            '(VIEWSETS_EXEMPTES / ROUTES_EXEMPTEES).')
        noms = {r[0] for r in _routes()}
        classes = {_classe(r[2]) for r in _routes()}
        perimees = sorted(
            [n for n in list(ROUTES_SONDEES) + list(ROUTES_EXEMPTEES)
             + list(EN_ATTENTE) if n not in noms]
            + [c for c in list(VIEWSETS_EXEMPTES) + list(VIEWSETS_SONDES)
               if c not in classes])
        self.assertEqual(perimees, [],
                         'entrée de la garde pour une route qui n’existe plus')

    def test_aucune_route_ne_sort_de_la_portee(self):
        avant = self._instantane()
        fuites, _attendues = self._jouer(self.commercial)
        self.assertEqual(fuites, [], '\n'.join(fuites))
        # CLAUSE PERSISTANCE — D1 relu après le balayage : identique.
        self.assertEqual(self._instantane(), avant)

    def test_sonde_voit_hors_portee_en_portee_all(self):
        """Test-du-test : en Directeur (portée ``all``), la liste ``devis/``
        DOIT rendre D1 au scanner — sinon la garde serait verte pour rien."""
        resp = self._api(self.directeur).get(BASE + 'devis/')
        self.assertEqual(resp.status_code, 200, resp.content[:300])
        self.assertTrue(self._fuites(resp), _contenu(resp)[:300])
        resp = self._api(self.directeur).get(
            BASE + 'devis-lignes/', {'devis': self.d1.pk})
        self.assertEqual(resp.status_code, 200, resp.content[:300])
        self.assertTrue(self._fuites(resp), _contenu(resp)[:300])
