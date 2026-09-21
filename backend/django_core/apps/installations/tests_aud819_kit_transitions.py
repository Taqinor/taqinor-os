"""AUD819 — la table ``TRANSITIONS`` du kit ``DocumentMetier`` est CONSULTÉE.

Constat réparé. ``DemandeAchat`` (SCA36) déclarait une table ``TRANSITIONS``
présentée comme la source de vérité de son graphe d'états, mais CINQ sites de
``views/demande_achat.py`` écrivaient ``statut = …`` à la main sans jamais la
consulter :

  * ouvrir/fermer une transition dans la table ne changeait STRICTEMENT rien
    au comportement réel ;
  * ``core.events.document_statut_change`` n'était JAMAIS émis pour ce
    document, rendant tout futur abonné (audit / notification / KPI)
    silencieusement aveugle aux demandes d'achat.

Ce que prouvent les tests ci-dessous (ROUGES avant le correctif) :

  1. **La table est le propriétaire réel.** En FERMANT une transition dans la
     table (``patch.object``), l'action de vue correspondante est REFUSÉE en 400
     et AUCUNE écriture n'a lieu. Avant le correctif elle répondait 200 et
     écrivait le statut : la table était ignorée.
  2. **Un événement, exactement un, par transition légitime.** Chacun des cinq
     sites (vues + services cross-app) émet un et un seul
     ``document_statut_change`` portant l'ancien statut, le nouveau,
     l'utilisateur et la société. Avant le correctif : ZÉRO sur les cinq.
  3. **La ré-application idempotente est préservée** (re-soumettre une demande
     déjà soumise) : 200, aucun événement — la table ne déclare pas la
     transition d'un statut vers lui-même.
  4. **Un refus ne laisse aucune trace** : les champs annexes de l'action
     (``approuvee_par`` / ``date_decision`` / ``motif_refus``) sont annulés avec
     la transition (écriture atomique).

Run :
    python manage.py test apps.installations.tests_aud819_kit_transitions -v2
"""
import itertools
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations import services
from apps.installations.models import (
    DemandeAchat, DemandeAchatLigne, EtapeApprobationAchat,
    RegleApprobationAchat,
)
from core import events

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company():
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'aud819-co-{n}', defaults={'nom': f'AUD819 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable'):
    return User.objects.create_user(
        username=f'aud819-{next(_seq)}', password='x',
        role_legacy=role, company=company)


class CaptureEvents:
    """Collecte les ``document_statut_change`` émis dans le bloc ``with``."""

    def __init__(self):
        self.recus = []

    def __enter__(self):
        events.document_statut_change.connect(self._on, weak=False)
        return self

    def __exit__(self, *exc):
        events.document_statut_change.disconnect(self._on)
        return False

    def _on(self, sender, **kwargs):
        self.recus.append(kwargs)

    def pour(self, instance):
        return [k for k in self.recus
                if getattr(k.get('instance'), 'pk', None) == instance.pk
                and type(k.get('instance')) is type(instance)]


class BaseAud819(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)

    def make_demande(self, statut=DemandeAchat.Statut.BROUILLON):
        return DemandeAchat.objects.create(
            company=self.company, reference=f'DA-A819-{next(_seq)}',
            objet='12 panneaux', statut=statut, created_by=self.user)


# ── 1. La table TRANSITIONS est le propriétaire RÉEL du graphe ────────────────

class TestTableEstConsultee(BaseAud819):
    """ROUGE avant AUD819 : fermer une transition dans la table ne changeait
    rien — les vues écrivaient ``statut`` à la main sans jamais la lire."""

    def test_demande_transition_fermee_refusee_en_400(self):
        da = self.make_demande()
        table_fermee = dict(DemandeAchat.TRANSITIONS)
        table_fermee[DemandeAchat.Statut.BROUILLON] = set()
        with patch.object(DemandeAchat, 'TRANSITIONS', table_fermee):
            r = self.api.post(f'{BASE}/demandes-achat/{da.id}/soumettre/')
        self.assertEqual(r.status_code, 400, r.data)
        da.refresh_from_db()
        self.assertEqual(da.statut, DemandeAchat.Statut.BROUILLON)

    def test_refus_ne_laisse_aucune_trace(self):
        """Écriture atomique : les champs annexes de l'action (approbateur,
        date de décision, motif) sont annulés AVEC la transition refusée."""
        da = self.make_demande(statut=DemandeAchat.Statut.SOUMISE)
        table_fermee = dict(DemandeAchat.TRANSITIONS)
        table_fermee[DemandeAchat.Statut.SOUMISE] = set()
        with patch.object(DemandeAchat, 'TRANSITIONS', table_fermee):
            r = self.api.post(f'{BASE}/demandes-achat/{da.id}/approuver/')
        self.assertEqual(r.status_code, 400, r.data)
        da.refresh_from_db()
        self.assertEqual(da.statut, DemandeAchat.Statut.SOUMISE)
        self.assertIsNone(da.approuvee_par_id)
        self.assertIsNone(da.date_decision)


# ── 2. Exactement UN événement par transition légitime ───────────────────────

class TestEvenementDemandeAchat(BaseAud819):
    def test_soumettre_emet_un_evenement(self):
        da = self.make_demande()
        with CaptureEvents() as cap:
            r = self.api.post(f'{BASE}/demandes-achat/{da.id}/soumettre/')
        self.assertEqual(r.status_code, 200, r.data)
        recus = cap.pour(da)
        self.assertEqual(len(recus), 1, recus)
        self.assertEqual(recus[0]['ancien_statut'], 'brouillon')
        self.assertEqual(recus[0]['nouveau_statut'], 'soumise')

    def test_approuver_emet_un_evenement(self):
        da = self.make_demande(statut=DemandeAchat.Statut.SOUMISE)
        with CaptureEvents() as cap:
            r = self.api.post(f'{BASE}/demandes-achat/{da.id}/approuver/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(len(cap.pour(da)), 1, cap.recus)
        da.refresh_from_db()
        self.assertEqual(da.statut, DemandeAchat.Statut.APPROUVEE)
        self.assertEqual(da.approuvee_par_id, self.user.id)
        self.assertIsNotNone(da.date_decision)

    def test_refuser_emet_un_evenement_et_pose_le_motif(self):
        da = self.make_demande(statut=DemandeAchat.Statut.SOUMISE)
        with CaptureEvents() as cap:
            r = self.api.post(f'{BASE}/demandes-achat/{da.id}/refuser/',
                              {'motif_refus': 'Hors budget'})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(len(cap.pour(da)), 1, cap.recus)
        da.refresh_from_db()
        self.assertEqual(da.statut, DemandeAchat.Statut.REFUSEE)
        self.assertEqual(da.motif_refus, 'Hors budget')

    def test_marquer_commandee_emet_un_evenement(self):
        da = self.make_demande(statut=DemandeAchat.Statut.APPROUVEE)
        with CaptureEvents() as cap:
            r = self.api.post(
                f'{BASE}/demandes-achat/{da.id}/marquer_commandee/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(len(cap.pour(da)), 1, cap.recus)
        da.refresh_from_db()
        self.assertEqual(da.statut, DemandeAchat.Statut.COMMANDEE)

    def test_generer_bcf_emet_un_evenement_et_lie_le_bcf(self):
        from apps.stock.models import Fournisseur

        da = self.make_demande(statut=DemandeAchat.Statut.APPROUVEE)
        DemandeAchatLigne.objects.create(
            demande=da, designation='Panneau 550W', quantite=12,
            prix_estime=1500)
        fournisseur = Fournisseur.objects.create(
            company=self.company, nom='SolarImport')
        with CaptureEvents() as cap:
            r = self.api.post(f'{BASE}/demandes-achat/{da.id}/generer-bcf/',
                              {'fournisseur': fournisseur.id})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(len(cap.pour(da)), 1, cap.recus)
        da.refresh_from_db()
        self.assertEqual(da.statut, DemandeAchat.Statut.COMMANDEE)
        self.assertIsNotNone(da.bon_commande_id)


class TestEvenementServicesCrossApp(BaseAud819):
    """Les 4 écritures de ``services.py`` (boîte d'approbations XKB1 + plan
    d'approbation NTP2P2) passent aussi par le garde."""

    def test_decider_demande_achat_approuve_emet_un_evenement(self):
        da = self.make_demande(statut=DemandeAchat.Statut.SOUMISE)
        with CaptureEvents() as cap:
            services.decider_demande_achat(
                da, approuver=True, user=self.user)
        self.assertEqual(len(cap.pour(da)), 1, cap.recus)
        da.refresh_from_db()
        self.assertEqual(da.statut, DemandeAchat.Statut.APPROUVEE)
        self.assertEqual(da.approuvee_par_id, self.user.id)

    def test_decider_demande_achat_refuse_emet_un_evenement(self):
        da = self.make_demande(statut=DemandeAchat.Statut.SOUMISE)
        with CaptureEvents() as cap:
            services.decider_demande_achat(
                da, approuver=False, user=self.user, motif_refus='Trop cher')
        self.assertEqual(len(cap.pour(da)), 1, cap.recus)
        da.refresh_from_db()
        self.assertEqual(da.statut, DemandeAchat.Statut.REFUSEE)
        self.assertEqual(da.motif_refus, 'Trop cher')

    def _demande_avec_etape(self):
        da = self.make_demande(statut=DemandeAchat.Statut.SOUMISE)
        regle = RegleApprobationAchat.objects.create(
            company=self.company, libelle='Règle AUD819', actif=True,
            nombre_approbateurs=1)
        approbateur = make_user(self.company, role='admin')
        etape = EtapeApprobationAchat.objects.create(
            company=self.company, demande=da, regle=regle, niveau=1,
            statut=EtapeApprobationAchat.Statut.EN_ATTENTE)
        return da, etape, approbateur

    def test_approuver_etape_finale_emet_un_evenement(self):
        da, etape, approbateur = self._demande_avec_etape()
        with CaptureEvents() as cap:
            services.approuver_etape_achat(etape, approbateur=approbateur)
        self.assertEqual(len(cap.pour(da)), 1, cap.recus)
        da.refresh_from_db()
        self.assertEqual(da.statut, DemandeAchat.Statut.APPROUVEE)

    def test_rejeter_etape_emet_un_evenement(self):
        da, etape, approbateur = self._demande_avec_etape()
        with CaptureEvents() as cap:
            services.rejeter_etape_achat(
                etape, approbateur=approbateur, commentaire='Non justifié')
        self.assertEqual(len(cap.pour(da)), 1, cap.recus)
        da.refresh_from_db()
        self.assertEqual(da.statut, DemandeAchat.Statut.REFUSEE)
        self.assertEqual(da.motif_refus, 'Non justifié')


# ── 3. Ré-application idempotente : préservée, SANS événement ────────────────

class TestReapplicationIdempotente(BaseAud819):
    def test_resoumettre_une_demande_deja_soumise(self):
        da = self.make_demande(statut=DemandeAchat.Statut.SOUMISE)
        with CaptureEvents() as cap:
            r = self.api.post(f'{BASE}/demandes-achat/{da.id}/soumettre/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(cap.pour(da), [])
        da.refresh_from_db()
        self.assertEqual(da.statut, DemandeAchat.Statut.SOUMISE)


# ── 4. Plus AUCUNE écriture directe de ``statut`` sur le document ────────────

class TestPlusDEcritureDirecte(TestCase):
    """Garde de non-régression : les fichiers de la lane ne contiennent plus
    d'affectation ``<obj>.statut = DemandeAchat.Statut.…`` — le seul point
    d'écriture est ``appliquer_statut_document``."""

    FICHIERS = (
        'views/demande_achat.py',
        'services.py',
    )

    def test_aucune_affectation_directe(self):
        import os
        import re

        racine = os.path.dirname(
            os.path.abspath(services.__file__))
        motif = re.compile(
            r'\.statut\s*=\s*DemandeAchat\.Statut\.')
        fautifs = []
        for rel in self.FICHIERS:
            chemin = os.path.join(racine, *rel.split('/'))
            with open(chemin, encoding='utf-8') as fh:
                for num, ligne in enumerate(fh, start=1):
                    if motif.search(ligne):
                        fautifs.append(f'{rel}:{num}: {ligne.strip()}')
        self.assertEqual(fautifs, [], '\n'.join(fautifs))
