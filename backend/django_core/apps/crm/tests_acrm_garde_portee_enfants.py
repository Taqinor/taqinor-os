"""ACRM52 — garde de CLASSE : aucun viewset ENFANT de ``apps.crm`` (modèle
portant une FK vers ``Lead`` ou ``Client``) ni aucune action ``detail=True``
de ``LeadViewSet``/``ClientViewSet`` ne sort de la portée d'un Commercial
(portée ``team``).

Étend ALEA25 (actions ``detail=False``, fichier distinct, non modifié) :

* les viewsets sont DÉCOUVERTS sur le routeur réel (``router.registry``) ;
  chacun dont le modèle porte une FK lead/client doit figurer dans
  ``ENFANTS`` (sondé) ou ``EXEMPTES`` (raison motivée) — un viewset nouveau
  fait échouer la garde en le nommant ;
* pour chaque enfant : GET liste filtrée sur le lead/client hors portée,
  GET/PATCH détail d'une ligne rattachée au lead hors portée, POST d'une
  ligne désignant le lead/client hors portée ;
* les actions ``detail=True`` de ``LeadViewSet``/``ClientViewSet`` sont
  DÉCOUVERTES par ``get_extra_actions()`` : chacune est sondée (sur le lead
  ou client DANS la portée, corps portant les ids hors portée) ou déclarée
  avec sa raison ;
* aucune réponse ne contient le nom / l'e-mail / la fiche du lead ou client
  hors portée, et la base relue (CLAUSE PERSISTANCE) est identique.

Le lead dans la portée PARTAGE le téléphone du lead hors portée : une action
qui « rapproche un contact » sans borner la portée le ferait ressortir.

Aucun mock : routeur, rôles canoniques et vues réels. Test-du-test : retirer
le filtre de portée d'un seul viewset (``ConcurrentPerteViewSet``) ⇒ la garde
échoue en le nommant.
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import models, transaction
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.crm import stages
from apps.crm.models import (
    Appointment, Client, ConcurrentPerte, Lead, LeadActivity, PointContact,
)
from apps.crm.tests_alea_garde_portee_actions import (
    _cle_explicite, _contenu,
)
from apps.crm.urls import router
from apps.crm.views import ClientViewSet, LeadViewSet
from apps.roles.models import Role
from apps.roles.permissions_registre import COMMERCIAL_PERMISSIONS
from authentication.models import Company

User = get_user_model()

BASE = '/api/django/crm'
NOM_HORS = 'Zorglubenfant'
EMAIL_HORS = 'zorglub.enfant.hors@example.ma'
TEL_PARTAGE = '+212661509301'
CLIENT_HORS = 'Zorglubenfantclient'
CLIENT_EMAIL_HORS = 'zorglub.enfant.client@example.ma'

#: Viewsets enfants SONDÉS (préfixe du routeur).
ENFANTS = (
    'parrainages', 'appointments', 'concurrents-perte', 'points-contact',
    'site-profiles', 'relance-etapes', 'website-lead-payloads',
    'forecast-entries', 'plans-compte', 'salles-vente', 'deals-enregistres',
)

#: Viewsets portant une FK lead/client, EXEMPTÉS — une ligne par raison.
EXEMPTES = {
    'leads': 'le viewset du lead lui-même — sa portée est la garde ALEA25 '
             '+ les actions detail=True ci-dessous',
    'clients': 'le viewset du client lui-même — idem',
    'visites-externes': 'transparence CKP3 (traces de visite du site) — '
                        'décision non tranchée, laissée hors garde',
}

#: Actions ``detail=True`` sondées → (verbe, corps/params) ; ``{L1}``,
#: ``{C1}``, ``{ACT1}`` = ids du lead, du client et d'une activité HORS
#: portée.
SONDES_DETAIL_LEAD = {
    'merge': ('post', {'others': ['{L1}']}),
    'duplicates': ('get', {}),
    'client_match': ('get', {}),
    'references_proches': ('get', {}),
    'convertir_client': ('post', {'mode': 'lier', 'client_id': '{C1}'}),
    'synchroniser_client': ('post', {}),
    'historique': ('get', {}),
    'points_contact': ('get', {}),
    'panneau_appel': ('get', {}),
    'visites': ('get', {}),
    'jalons_devis': ('get', {}),
    'epingler': ('post', {}),
    'desepingler': ('post', {}),
    'appliquer_plan': ('post', {'plan_id': '{L1}'}),
    'resume_associe': ('post', {'devis_id': '{L1}', 'accord_client': True}),
    'noter': ('post', {'body': 'note de garde'}),
    'message_visite': ('get', {}),
}

NON_APPLICABLES_DETAIL_LEAD = {
    'archiver': 'agit sur le seul lead de l’URL (get_object borné), aucun id '
                'lu du corps',
    'restaurer': 'idem archiver',
    'arreter_relance': 'cadence du seul lead de l’URL, aucun id du corps',
    'initialiser_relance': 'plan du seul lead de l’URL ; l’id de devis lu '
                           'du corps est borné par ventes (garde ADEV41)',
    'devis_auto': 'crée un devis pour le lead de l’URL (écriture coûteuse '
                  'ventes), aucun id lead/client du corps',
    'locataire': 'fiche propriétaire saisie sur le lead de l’URL, aucun id',
    'log_interaction': 'interaction du lead de l’URL, aucun id du corps',
    'message_visite_ouvert': 'journalise une ouverture sur le lead de l’URL',
    'planifier_visite': 'visite du lead de l’URL ; le commercial du corps est '
                        'un utilisateur, pas un lead/client',
    'questionnaire_lien': 'lien public du lead de l’URL (aucun id du corps)',
    'salle_vente_analytics_view': 'analytique des salles du lead de l’URL',
    'whatsapp_devis': 'envoi externe (WhatsApp) du devis du lead de l’URL',
    'whatsapp_devis_apercu': 'aperçu du message du devis du lead de l’URL',
}

SONDES_DETAIL_CLIENT = {
    'consolidation': ('get', {}),
    'documents': ('get', {}),
    'engagement': ('get', {}),
    'data_export': ('get', {}),
    'relancer_dormance': ('post', {}),
}

NON_APPLICABLES_DETAIL_CLIENT = {
    'anonymize': 'irréversible sur le client de l’URL (get_object borné), '
                 'aucun id du corps',
    'dupliquer': 'copie le client de l’URL, aucun id lead/client du corps',
}


def _fiches_lead(donnee, pk):
    """Vrai si un dict qui ressemble à une FICHE DE LEAD (``id`` + ``stage``)
    porte l'id ``pk`` — un client ou une activité au même numéro n'en est
    pas une (séquences distinctes)."""
    if isinstance(donnee, dict):
        if donnee.get('id') == pk and 'stage' in donnee:
            return True
        return any(_fiches_lead(v, pk) for v in donnee.values())
    if isinstance(donnee, list):
        return any(_fiches_lead(v, pk) for v in donnee)
    return False


def _modele(viewset):
    qs = getattr(viewset, 'queryset', None)
    if qs is not None:
        return qs.model
    return viewset.serializer_class.Meta.model


def _fk_lead_client(model):
    """Noms des champs concrets du modèle qui pointent vers Lead/Client."""
    return [f.name for f in model._meta.concrete_fields
            if f.is_relation and f.related_model in (Lead, Client)]


class GardePorteeEnfantsTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor ACRM52', slug='taqinor-acrm52')
        role_com = Role.objects.create(
            company=self.company, nom='Commercial',
            permissions=list(COMMERCIAL_PERMISSIONS))
        self.commercial = User.objects.create_user(
            username='acrm52-com', password='x', company=self.company,
            role=role_com)
        self.collegue = User.objects.create_user(
            username='acrm52-collegue', password='x', company=self.company,
            role=role_com)
        self.c1 = Client.objects.create(
            company=self.company, nom=CLIENT_HORS, prenom='Hors',
            telephone=TEL_PARTAGE, email=CLIENT_EMAIL_HORS)
        self.l1 = Lead.objects.create(
            company=self.company, nom=NOM_HORS, prenom='Portee',
            telephone=TEL_PARTAGE, email=EMAIL_HORS, owner=self.collegue,
            stage=stages.CONTACTED, client=self.c1)
        self.c2 = Client.objects.create(
            company=self.company, nom='Dansclient', prenom='Portee',
            telephone='+212661509399')
        # DANS la portée, MÊME téléphone que L1 (rapprochement de contact).
        self.l2 = Lead.objects.create(
            company=self.company, nom='Dans', prenom='Portee',
            telephone=TEL_PARTAGE, email='dans.portee@example.ma',
            owner=self.commercial, stage=stages.CONTACTED, client=self.c2)
        self.act1 = LeadActivity.objects.create(
            company=self.company, lead=self.l1, user=self.collegue,
            kind=LeadActivity.Kind.NOTE, body='note hors portée')
        maintenant = timezone.now()
        Appointment.objects.create(
            company=self.company, lead=self.l1,
            scheduled_at=maintenant + datetime.timedelta(days=2))
        ConcurrentPerte.objects.create(
            company=self.company, lead=self.l1, concurrent_nom=NOM_HORS)
        PointContact.objects.create(
            company=self.company, lead=self.l1, canal='telephone',
            date_contact=maintenant)
        self.api = APIClient()
        self.api.force_authenticate(self.commercial)

    # ── outillage ───────────────────────────────────────────────────────
    def _instantane(self):
        l1 = Lead.objects.filter(pk=self.l1.pk).values().first()
        l1.pop('date_modification', None)
        compte = {}
        for prefixe, viewset, _b in router.registry:
            model = _modele(viewset)
            for champ in _fk_lead_client(model):
                cible = (self.l1.pk if model._meta.get_field(
                    champ).related_model is Lead else self.c1.pk)
                compte[f'{prefixe}.{champ}'] = model._base_manager.filter(
                    **{f'{champ}_id': cible}).count()
        return {
            'lead': l1,
            'client': Client.objects.filter(pk=self.c1.pk).values(
                'nom', 'telephone', 'email', 'parent_id').first(),
            'activites': LeadActivity.objects.filter(lead=self.l1).count(),
            'enfants': compte,
        }

    def _remplacer(self, valeur):
        table = {'{L1}': self.l1.pk, '{C1}': self.c1.pk,
                 '{ACT1}': self.act1.pk}
        if isinstance(valeur, list):
            return [self._remplacer(v) for v in valeur]
        return table.get(valeur, valeur) if isinstance(valeur, str) else valeur

    def _fuites(self, resp):
        texte = _contenu(resp)
        fuites = [mot for mot in (NOM_HORS, EMAIL_HORS, CLIENT_HORS,
                                  CLIENT_EMAIL_HORS) if mot in texte]
        try:
            donnee = resp.json()
        except Exception:  # noqa: BLE001 — binaire ou vide
            donnee = None
        if isinstance(donnee, (dict, list)):
            if _fiches_lead(donnee, self.l1.pk):
                fuites.append(f'fiche lead {self.l1.pk}')
            for cle in ('lead_id', 'lead', 'filleul_lead'):
                if _cle_explicite(donnee, cle, self.l1.pk):
                    fuites.append(f'{cle}={self.l1.pk}')
            for cle in ('client_id', 'client', 'filleul_client'):
                if _cle_explicite(donnee, cle, self.c1.pk):
                    fuites.append(f'{cle}={self.c1.pk}')
        return fuites

    def _appel(self, verbe, url, charge=None):
        """Un appel isolé dans un point de sauvegarde : une erreur serveur
        n'empoisonne jamais la transaction du test (elle est rapportée)."""
        try:
            with transaction.atomic():
                if verbe == 'get':
                    return self.api.get(url, charge or {})
                return getattr(self.api, verbe)(url, charge or {},
                                                format='json')
        except Exception as exc:  # noqa: BLE001 — rapporté, jamais masqué
            self.erreurs.append(f'{verbe.upper()} {url} → {exc!r}'[:200])
            return None

    def _remplir(self, model, champ_cible, cible):
        """Une ligne MINIMALE du modèle rattachée à ``cible`` (lead/client
        hors portée) ; ``None`` si le modèle exige une donnée qu'on ne sait
        pas fabriquer (alors le détail n'est pas sondé — le POST et la
        liste le restent)."""
        valeurs = {champ_cible: cible}
        for f in model._meta.concrete_fields:
            if f.primary_key or f.name in valeurs or f.null or f.has_default():
                continue
            if getattr(f, 'auto_now', False) or getattr(
                    f, 'auto_now_add', False):
                continue
            if f.is_relation:
                if f.related_model is Company:
                    valeurs[f.name] = self.company
                elif f.related_model is User:
                    valeurs[f.name] = self.collegue
                elif f.related_model is Client:
                    valeurs[f.name] = self.c1
                elif f.related_model is Lead:
                    valeurs[f.name] = self.l1
                else:
                    return None
            elif isinstance(f, models.DateTimeField):
                valeurs[f.name] = timezone.now()
            elif isinstance(f, models.DateField):
                valeurs[f.name] = timezone.localdate()
            elif isinstance(f, (models.DecimalField, models.FloatField)):
                valeurs[f.name] = Decimal('0')
            elif isinstance(f, models.IntegerField):
                valeurs[f.name] = 0
            elif isinstance(f, models.BooleanField):
                valeurs[f.name] = False
            elif isinstance(f, models.JSONField):
                valeurs[f.name] = {}
            elif isinstance(f, models.CharField) and f.choices:
                valeurs[f.name] = f.choices[0][0]
            elif isinstance(f, (models.CharField, models.TextField)):
                valeurs[f.name] = NOM_HORS[: f.max_length or 50]
            else:
                return None
        if 'company' in {f.name for f in model._meta.concrete_fields}:
            valeurs.setdefault('company', self.company)
        try:
            with transaction.atomic():
                return model._base_manager.create(**valeurs)
        except Exception:  # noqa: BLE001 — modèle non fabricable génériquement
            return None

    # ── découverte ──────────────────────────────────────────────────────
    def test_viewsets_enfants_tous_couverts(self):
        portant = sorted(
            prefixe for prefixe, viewset, _b in router.registry
            if _fk_lead_client(_modele(viewset)))
        non_couverts = [p for p in portant
                        if p not in ENFANTS and p not in EXEMPTES]
        self.assertEqual(
            non_couverts, [],
            'viewset portant une FK lead/client non couvert par la garde de '
            f'portée (ajouter à ENFANTS ou à EXEMPTES avec sa raison) : '
            f'{non_couverts}')
        perimes = [p for p in list(ENFANTS) + list(EXEMPTES)
                   if p not in portant]
        self.assertEqual(perimes, [], f'entrées périmées : {perimes}')

    def test_actions_detail_toutes_couvertes(self):
        for viewset, sondes, non_app in (
                (LeadViewSet, SONDES_DETAIL_LEAD,
                 NON_APPLICABLES_DETAIL_LEAD),
                (ClientViewSet, SONDES_DETAIL_CLIENT,
                 NON_APPLICABLES_DETAIL_CLIENT)):
            noms = {a.__name__ for a in viewset.get_extra_actions()
                    if a.detail}
            self.assertEqual(
                sorted(noms - set(sondes) - set(non_app)), [],
                f'{viewset.__name__} : action detail=True non couverte par '
                'la garde de portée')
            self.assertEqual(
                sorted((set(sondes) | set(non_app)) - noms), [],
                f'{viewset.__name__} : sonde périmée')

    # ── la garde ────────────────────────────────────────────────────────
    def test_aucun_viewset_enfant_ne_sort_de_la_portee(self):
        self.erreurs = []
        avant = self._instantane()
        fuites = []
        par_prefixe = {p: v for p, v, _b in router.registry}
        for prefixe in ENFANTS:
            model = _modele(par_prefixe[prefixe])
            for champ in _fk_lead_client(model):
                cible = (self.l1 if model._meta.get_field(
                    champ).related_model is Lead else self.c1)
                url = f'{BASE}/{prefixe}/'
                # GET liste filtrée sur la cible hors portée.
                resp = self._appel('get', url, {champ: cible.pk})
                if resp is not None:
                    fuites += [f'{prefixe} GET ?{champ} → {f}'
                               for f in self._fuites(resp)]
                # POST désignant la cible hors portée.
                resp = self._appel('post', url, {
                    champ: cible.pk, 'company': self.company.pk})
                if resp is not None:
                    if 200 <= resp.status_code < 300:
                        fuites.append(
                            f'{prefixe} POST {champ}=hors portée → '
                            f'{resp.status_code} (écriture acceptée)')
                    fuites += [f'{prefixe} POST → {f}'
                               for f in self._fuites(resp)]
                # GET / PATCH détail d'une ligne rattachée à la cible.
                ligne = self._remplir(model, champ, cible)
                if ligne is None:
                    continue
                detail = f'{url}{ligne.pk}/'
                resp = self._appel('get', detail)
                if resp is not None:
                    if resp.status_code == 200:
                        fuites.append(f'{prefixe} GET détail → 200')
                    fuites += [f'{prefixe} GET détail → {f}'
                               for f in self._fuites(resp)]
                resp = self._appel('patch', detail, {'notes': 'garde'})
                if resp is not None and 200 <= resp.status_code < 300:
                    fuites.append(f'{prefixe} PATCH détail → '
                                  f'{resp.status_code}')
                model._base_manager.filter(pk=ligne.pk).delete()

        for viewset, cible_url, sondes in (
                (LeadViewSet, f'leads/{self.l2.pk}', SONDES_DETAIL_LEAD),
                (ClientViewSet, f'clients/{self.c2.pk}',
                 SONDES_DETAIL_CLIENT)):
            actions = {a.__name__: a for a in viewset.get_extra_actions()
                       if a.detail}
            for nom, (verbe, charge) in sondes.items():
                chemin = actions[nom].url_path.replace(
                    '(?P<activite_id>[^/.]+)', str(self.act1.pk))
                charge = {k: self._remplacer(v) for k, v in charge.items()}
                resp = self._appel(
                    verbe, f'{BASE}/{cible_url}/{chemin}/', charge)
                if resp is not None:
                    fuites += [f'{viewset.__name__}.{nom} → {f}'
                               for f in self._fuites(resp)]

        apres = self._instantane()
        self.assertEqual(fuites, [], 'fuites de portée :\n' + '\n'.join(
            fuites + self.erreurs))
        self.assertEqual(avant, apres,
                         'une écriture a touché le lead/client hors portée')
