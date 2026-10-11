"""ALEA25 — garde de CLASSE : aucune action annexe (``detail=False``) de
``LeadViewSet`` / ``ClientViewSet`` ne sort de la portée du rôle.

Constat C-ALEA-002 : une action qui repart de ``company`` au lieu de
``self.get_queryset()`` ignore la portée équipe/sous-arbre (sonde V4 LCOUT-2 :
``bulk reassign`` → ``updated: 1`` sur le lead d'un collègue hors équipe,
``check-duplicates`` qui rend ses coordonnées). ALEA27 a corrigé les cas
connus ; CETTE garde empêche la prochaine action oubliée :

* les actions sont DÉCOUVERTES par ``get_extra_actions()`` (introspection) ;
* chacune doit avoir une sonde dans ``SONDES_*`` ou figurer dans
  ``NON_APPLICABLES_*`` AVEC sa raison — une action nouvelle sans sonde
  échoue « action non couverte par la garde de portée » (jamais ignorée en
  silence) ; les opérations ``bulk`` sont découvertes de la même manière
  (``services.BULK_ACTIONS``) ;
* chaque sonde est rejouée avec un Commercial (portée ``team``) ET un
  Commercial responsable (portée ``subtree``) ; aucune réponse ne doit
  contenir nom / téléphone / e-mail / id du lead ou client hors portée, et
  la base relue (CLAUSE PERSISTANCE) doit être identique.

Aucun mock : rôles canoniques, ``core.scoping`` et vues réels. Le scanner de
fuite est lui-même éprouvé (test-du-test) : rejoué en Directeur (portée
``all``) il DOIT trouver le lead.
"""
import io
import zipfile

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm import stages
from apps.crm.models import Client, Lead, LeadActivity
from apps.crm.fiche_bulk import BULK_ACTIONS
from apps.crm.clients_views import ClientViewSet
from apps.crm.views import LeadViewSet
from apps.roles.models import Role
from apps.roles.permissions_registre import (
    COMMERCIAL_PERMISSIONS, COMMERCIAL_RESP_PERMISSIONS,
)
from authentication.models import Company

User = get_user_model()

BASE = '/api/django/crm'
NOM_HORS = 'Zorglub'
TEL_HORS = '+212661509001'
EMAIL_HORS = 'zorglub.hors.portee@example.ma'
CLIENT_HORS = 'Zorglubclient'
CLIENT_TEL_HORS = '+212661509002'
CLIENT_EMAIL_HORS = 'zorglubclient.hors@example.ma'

# ── Sondes : nom de la fonction d'action → liste de (verbe, chemin, charge) ──
# ``{L1}`` / ``{L1B}`` sont remplacés par les ids des leads hors portée,
# ``{C1}`` par l'id du client hors portée, ``{MOI}`` par l'utilisateur sondé.
_RECHERCHE = {'q': NOM_HORS, 'search': NOM_HORS, 'telephone': TEL_HORS,
              'phone': TEL_HORS, 'email': EMAIL_HORS}

SONDES_LEAD = {
    'check_duplicates': [('get', 'leads/check-duplicates/', _RECHERCHE)],
    'doublons': [('get', 'leads/doublons/', {})],
    'relances': [('get', 'leads/relances/', {'scope': 'today'}),
                 ('get', 'leads/relances/', {'scope': 'overdue'}),
                 ('get', 'leads/relances/', {'scope': 'all'})],
    'roi_sources': [('get', 'leads/roi-sources/', {})],
    'kpi_cadences': [('get', 'leads/kpi-cadences/', {})],
    'mesure_cadence': [('get', 'leads/mesure-cadence/', {})],
    'kpi_premier_contact': [('get', 'leads/kpi-premier-contact/', {})],
    'sla_breach': [('get', 'leads/sla-breach/', {})],
    'export_xlsx': [('post', 'leads/export-xlsx/', {'ids': ['{L1}', '{L1B}']})],
    'placement_cadences': [
        ('post', 'leads/placement-cadences/', {'apply': False}),
        ('post', 'leads/placement-cadences/', {'apply': True, 'limite': 200})],
    # ``bulk`` : une sonde PAR opération (voir ``_sondes_bulk``).
    'bulk': [],
}

NON_APPLICABLES_LEAD = {
    'scan_carte': "reçoit une photo de carte de visite, ne désigne aucun lead "
                  "existant (ne crée rien, 503 sans clé OCR)",
    'resoudre_gps': "résolveur PUR (lien/adresse → coordonnées), ne lit aucun "
                    "enregistrement du lead",
    'ville_statut': "référentiel de villes (statut d'une ville tapée), ne lit "
                    "aucun lead",
}

SONDES_CLIENT = {
    'export_xlsx': [('post', 'clients/export-xlsx/', {'ids': ['{C1}']})],
    'search': [('get', 'clients/search/', _RECHERCHE)],
    'dormants': [('get', 'clients/dormants/', {})],
    'engagement_bulk': [('get', 'clients/engagement-bulk/', {})],
    'mon_portefeuille': [('get', 'clients/mon-portefeuille/', {})],
}

NON_APPLICABLES_CLIENT = {}

# Paramètres valides par opération ``bulk`` ({MOI} = utilisateur sondé).
PARAMS_BULK = {
    'reassign': {'owner': '{MOI}'},
    'add_tag': {'tag': 'zorglub'},
    'remove_tag': {'tag': 'zorglub'},
    'set_stage': {'stage': stages.QUOTE_SENT},
    'set_canal': {'canal': 'site'},
    'set_priorite': {'priorite': 'haute'},
    'set_relance': {'relance_date': '2026-12-01'},
    'clear_relance': {},
    'set_perdu': {},
    'unset_perdu': {},
    'archive': {},
    'unarchive': {},
    'delete': {},
    'plan_activity': {'summary': 'Zorglub', 'type_nom': 'Appel',
                      'due_date': '2026-12-01'},
    'prepare_whatsapp': {},
}


def _actions_detail_false(viewset):
    """{nom_de_fonction: fonction} des actions ``detail=False`` du viewset."""
    return {a.__name__: a for a in viewset.get_extra_actions()
            if not a.detail}


def _contenu(resp):
    """Texte scannable d'une réponse (JSON/texte, ou XML d'un .xlsx)."""
    brut = resp.content if hasattr(resp, 'content') else b''
    if brut[:2] == b'PK':
        try:
            with zipfile.ZipFile(io.BytesIO(brut)) as z:
                return '\n'.join(
                    z.read(n).decode('utf-8', 'ignore') for n in z.namelist())
        except zipfile.BadZipFile:
            pass
    return brut.decode('utf-8', 'ignore')


def _fiches_interdites(donnee, interdits):
    """Ids interdits retrouvés dans des dicts qui ressemblent à une FICHE (un
    ``id`` égal à un pk interdit ET une clé descriptive) — un entier nu n'est
    jamais une fuite (comptes, pagination)."""
    trouves = set()
    if isinstance(donnee, dict):
        descriptif = any(k in donnee for k in (
            'nom', 'prenom', 'telephone', 'email', 'reference', 'stage'))
        if descriptif and donnee.get('id') in interdits:
            trouves.add(donnee['id'])
        for v in donnee.values():
            trouves |= _fiches_interdites(v, interdits)
    elif isinstance(donnee, list):
        for v in donnee:
            trouves |= _fiches_interdites(v, interdits)
    return trouves


def _cle_explicite(donnee, cle, pk):
    """Vrai si une clé EXPLICITE (``lead_id``, ``client_id``…) vaut ``pk``."""
    if isinstance(donnee, dict):
        if donnee.get(cle) == pk:
            return True
        return any(_cle_explicite(v, cle, pk) for v in donnee.values())
    if isinstance(donnee, list):
        return any(_cle_explicite(v, cle, pk) for v in donnee)
    return False


class GardePorteeActionsTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor ALEA25', slug='taqinor-alea25')
        role_com = Role.objects.create(
            company=self.company, nom='Commercial',
            permissions=list(COMMERCIAL_PERMISSIONS))
        role_resp = Role.objects.create(
            company=self.company, nom='Commercial responsable',
            permissions=list(COMMERCIAL_RESP_PERMISSIONS))
        # Utilisateur de portée ``team`` (sans superviseur → soi seul).
        self.commercial = User.objects.create_user(
            username='alea25-com', password='x', company=self.company,
            role=role_com)
        # Responsable de portée ``subtree`` + un subordonné.
        self.responsable = User.objects.create_user(
            username='alea25-resp', password='x', company=self.company,
            role=role_resp)
        self.subordonne = User.objects.create_user(
            username='alea25-sub', password='x', company=self.company,
            role=role_com, supervisor=self.responsable)
        # Le collègue hors équipe : AUCUN superviseur commun.
        self.collegue = User.objects.create_user(
            username='alea25-collegue', password='x', company=self.company,
            role=role_com)
        self.directeur = User.objects.create_user(
            username='alea25-dir', password='x', company=self.company,
            role_legacy='admin')

        self.client_hors = Client.objects.create(
            company=self.company, nom=CLIENT_HORS, prenom='Hors',
            telephone=CLIENT_TEL_HORS, email=CLIENT_EMAIL_HORS)
        self.l1 = Lead.objects.create(
            company=self.company, nom=NOM_HORS, prenom='Portee',
            telephone=TEL_HORS, email=EMAIL_HORS, owner=self.collegue,
            stage=stages.CONTACTED, client=self.client_hors)
        self.l1b = Lead.objects.create(
            company=self.company, nom=NOM_HORS, prenom='Portee',
            telephone=TEL_HORS, owner=self.collegue)
        # Un lead DANS la portée de chacun (les sondes ont de quoi renvoyer).
        Lead.objects.create(
            company=self.company, nom='Dans', prenom='Portee',
            telephone='+212661509099', owner=self.commercial)
        Lead.objects.create(
            company=self.company, nom='Dans', prenom='Sub',
            telephone='+212661509098', owner=self.subordonne)
        self.api = APIClient()

    # ── outillage ───────────────────────────────────────────────────────
    def _instantane(self):
        """Etat complet des enregistrements hors portée (+ activités)."""
        leads = {
            pk: Lead.objects.filter(pk=pk).values().first()
            for pk in (self.l1.pk, self.l1b.pk)}
        return {
            'leads': leads,
            'client': Client.objects.filter(
                pk=self.client_hors.pk).values().first(),
            'activites': LeadActivity.objects.filter(
                lead_id__in=[self.l1.pk, self.l1b.pk]).count(),
            'nb_leads': Lead.objects.filter(company=self.company).count(),
        }

    def _remplacer(self, valeur, moi):
        if valeur == '{L1}':
            return self.l1.pk
        if valeur == '{L1B}':
            return self.l1b.pk
        if valeur == '{C1}':
            return self.client_hors.pk
        if valeur == '{MOI}':
            return moi.pk
        if isinstance(valeur, list):
            return [self._remplacer(v, moi) for v in valeur]
        return valeur

    def _fuites(self, resp):
        """Liste des fuites d'identité (lead/client hors portée) d'une réponse."""
        texte = _contenu(resp)
        fuites = [mot for mot in (
            NOM_HORS, TEL_HORS, EMAIL_HORS, CLIENT_HORS, CLIENT_TEL_HORS,
            CLIENT_EMAIL_HORS) if mot in texte]
        try:
            donnee = resp.json()
        except Exception:  # noqa: BLE001 — binaire (xlsx) ou vide
            donnee = None
        if isinstance(donnee, (dict, list)):
            # Fiches de LEAD uniquement sur les pk de lead (un pk de client
            # numériquement égal n'est pas une fuite de lead).
            for pk in sorted(_fiches_interdites(
                    donnee, {self.l1.pk, self.l1b.pk})):
                fuites.append(f'fiche id {pk}')
            for pk in (self.l1.pk, self.l1b.pk):
                if _cle_explicite(donnee, 'lead_id', pk):
                    fuites.append(f'lead_id {pk}')
            if _cle_explicite(donnee, 'client_id', self.client_hors.pk):
                fuites.append(f'client_id {self.client_hors.pk}')
        return fuites

    def _sondes_bulk(self, moi):
        sondes = []
        for op in sorted(BULK_ACTIONS):
            params = {k: self._remplacer(v, moi)
                      for k, v in PARAMS_BULK[op].items()}
            sondes.append((
                'post', 'leads/bulk/',
                {'action': op, 'ids': [self.l1.pk, self.l1b.pk], **params}))
        return sondes

    def _jouer(self, user, viewset, sondes, non_applicables, prefixe):
        """Rejoue toutes les sondes ; renvoie la liste des fuites relevées."""
        actions = _actions_detail_false(viewset)
        non_couvertes = sorted(
            n for n in actions if n not in sondes and n not in non_applicables)
        self.assertEqual(
            non_couvertes, [],
            f'{prefixe} : action non couverte par la garde de portée — '
            f'ajouter une sonde (SONDES_*) ou la déclarer avec sa raison '
            f'(NON_APPLICABLES_*) : {non_couvertes}')
        perimees = sorted(
            n for n in list(sondes) + list(non_applicables)
            if n not in actions)
        self.assertEqual(
            perimees, [],
            f'{prefixe} : sonde pour une action qui n’existe plus : '
            f'{perimees}')
        manquantes_bulk = sorted(set(BULK_ACTIONS) - set(PARAMS_BULK))
        self.assertEqual(
            manquantes_bulk, [],
            'opération bulk non couverte par la garde de portée : '
            f'{manquantes_bulk}')

        self.api.force_authenticate(user)
        fuites = []
        for nom, liste in sondes.items():
            appels = liste
            if nom == 'bulk':
                appels = self._sondes_bulk(user)
            for verbe, chemin, charge in appels:
                charge = {k: self._remplacer(v, user)
                          for k, v in charge.items()}
                url = f'{BASE}/{chemin}'
                if verbe == 'get':
                    resp = self.api.get(url, charge)
                else:
                    resp = self.api.post(url, charge, format='json')
                self.assertLess(
                    resp.status_code, 500,
                    f'{nom} {charge} → {resp.status_code} '
                    f'{resp.content[:200]!r}')
                for f in self._fuites(resp):
                    fuites.append(f'{nom} {charge} → fuite {f}')
        return fuites

    # ── la garde ────────────────────────────────────────────────────────
    def test_aucune_action_ne_sort_de_la_portee(self):
        avant = self._instantane()
        fuites = []
        for user in (self.commercial, self.responsable):
            fuites += [f'[{user.username}] {f}' for f in self._jouer(
                user, LeadViewSet, SONDES_LEAD, NON_APPLICABLES_LEAD,
                'LeadViewSet')]
            fuites += [f'[{user.username}] {f}' for f in self._jouer(
                user, ClientViewSet, SONDES_CLIENT, NON_APPLICABLES_CLIENT,
                'ClientViewSet')]
        self.assertEqual(fuites, [], '\n'.join(fuites))
        # CLAUSE PERSISTANCE : L1, L1b et le client relus → identiques.
        self.assertEqual(self._instantane(), avant)

    def test_sonde_voit_hors_portee_en_portee_all(self):
        """Test-du-test : le scanner de fuite n'est pas aveugle — rejoué par
        un Directeur (portée ``all``), ``check-duplicates`` DOIT rendre le
        lead de L1 ; sinon la garde ci-dessus serait verte pour rien."""
        self.api.force_authenticate(self.directeur)
        resp = self.api.get(f'{BASE}/leads/check-duplicates/', _RECHERCHE)
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(self._fuites(resp), _contenu(resp)[:300])
