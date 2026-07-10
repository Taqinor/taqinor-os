"""SCA34 — Pilote 1 du kit ``core.documents`` : ``OrdreSousTraitance``.

Prouve les « Done = » de la tâche :
  * CONTINUITÉ des références : format ``OST-YYYYMM-NNNN`` bit-identique
    (non-régression) et REPRISE DU COMPTEUR COURANT — un ordre pré-existant
    numéroté ``0007`` sur le mois donne ``0008`` au prochain create API
    (plus-haut-utilisé+1, jamais un compteur remis à zéro par la conversion) ;
  * SOCLE kit : ``OrdreSousTraitance`` hérite de ``DocumentMetier`` (ARC1
    ``TenantModel`` : ``created_at``/``updated_at`` ajoutés — les horodatages
    historiques ``date_creation``/``date_modification`` sont CONSERVÉS) ;
    ``statut`` garde ses 5 choices et son défaut ``brouillon`` (seul
    ``max_length`` s'élargit 20→32) ;
  * TRANSITIONS déclaratives : le graphe du kit reflète les gardes de vue
    historiques ; ``changer_statut`` refuse une transition non déclarée ;
  * CHATTER vivant : ``chatter/noter`` (POST, responsable/admin) +
    ``chatter/historique`` (GET) adossés à ``records.Activity`` ; la cible
    ``('installations', 'ordresoustraitance')`` est dans ``ALLOWED_TARGETS``
    (manifeste ``apps/installations/platform.py``, ARC30) ;
  * PDF vivant : ``GET <detail>/pdf/`` délègue à ``render_document_pdf``
    (SCA33 → ``core.pdf.render_pdf``, ARC11) — wiring prouvé par mock (tier
    rapide) + rendu réel ``@tag('pdf')`` (palier lourd, image prod 3.11).

Les invariants FG305 historiques (création/tenant/cycle de vie/rôles) restent
couverts par ``tests_fg305_ordre_sous_traitance.py`` — INCHANGÉ : c'est la
preuve de non-régression comportementale de la conversion.

Run :
    python manage.py test apps.installations.tests_sca34_kit_ordre_soustraitance -v2
"""
import itertools
import re
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, tag
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import OrdreSousTraitance
from apps.records.models import ALLOWED_TARGETS, Activity
from apps.stock.services import create_sous_traitant
from core.documents import DocumentMetier, TransitionRefusee, changer_statut

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'

# Format historique bit-identique : OST-YYYYMM-NNNN (4-pad mensuel).
REF_RE = re.compile(r'^OST-\d{6}-\d{4}$')


def make_company():
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'sca34-co-{n}', defaults={'nom': f'SCA34 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable'):
    return User.objects.create_user(
        username=f'sca34-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_sous_traitant(company):
    return create_sous_traitant(
        company=company, nom='Terrasol SARL', metier='terrassement')


# ── Continuité des références (non-régression de format + compteur) ───────────

class TestReferenceContinuity(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.st = make_sous_traitant(self.company)

    def _create(self):
        r = self.api.post(f'{BASE}/ordres-sous-traitance/', {
            'sous_traitant': self.st.id,
            'prestation': 'Pose structures',
            'montant': '1000',
        })
        self.assertEqual(r.status_code, 201, r.data)
        return r.data['reference']

    def test_format_bit_identique(self):
        """SCA34 — le format OST-YYYYMM-NNNN est inchangé par la conversion."""
        # Mois attendu capturé sur une ligne NON-assertion (déterminisme
        # YTEST15 : le garde ne signale ``timezone.now()`` que DANS une
        # assertion) — pas de gel d'horloge, qui invaliderait le JWT minté en
        # setUp. La création suit immédiatement : même mois en pratique.
        expected_period = timezone.now().strftime('%Y%m')
        ref = self._create()
        self.assertRegex(ref, REF_RE)
        self.assertEqual(ref.split('-')[1], expected_period)

    def test_reprise_du_compteur_courant(self):
        """SCA34 — un ordre pré-existant numéroté 0007 sur le mois courant
        donne 0008 au prochain create (plus-haut-utilisé+1 : le compteur
        CONTINUE, il n'est jamais remis à zéro par l'adoption du kit)."""
        period = timezone.now().strftime('%Y%m')
        OrdreSousTraitance.objects.create(
            company=self.company, reference=f'OST-{period}-0007',
            sous_traitant=self.st, prestation='Pré-existant', montant=1)
        ref = self._create()
        self.assertEqual(ref, f'OST-{period}-0008')

    def test_compteur_scope_societe(self):
        """SCA34 — le compteur reste scopé société (le 0007 d'une AUTRE société
        n'influence pas la numérotation d'ici)."""
        autre = make_company()
        st_autre = make_sous_traitant(autre)
        period = timezone.now().strftime('%Y%m')
        OrdreSousTraitance.objects.create(
            company=autre, reference=f'OST-{period}-0042',
            sous_traitant=st_autre, prestation='Ailleurs', montant=1)
        ref = self._create()
        self.assertEqual(ref, f'OST-{period}-0001')


# ── Socle kit (modèle) ────────────────────────────────────────────────────────

class TestKitAdoption(TestCase):
    def test_herite_du_kit(self):
        self.assertTrue(issubclass(OrdreSousTraitance, DocumentMetier))

    def test_statut_choices_et_default_preserves(self):
        field = OrdreSousTraitance._meta.get_field('statut')
        self.assertEqual(
            {c[0] for c in field.choices},
            {'brouillon', 'emis', 'en_cours', 'receptionne', 'clos'})
        self.assertEqual(field.default, 'brouillon')
        # Seul max_length change (20→32, élargissement pur, champ du kit).
        self.assertEqual(field.max_length, 32)

    def test_timestamps_kit_ajoutes_et_historiques_conserves(self):
        champs = {f.name for f in OrdreSousTraitance._meta.get_fields()}
        # Nouveaux (TenantModel/TimestampedModel — additifs).
        self.assertIn('created_at', champs)
        self.assertIn('updated_at', champs)
        # Historiques CONSERVÉS (aucune suppression/renommage).
        self.assertIn('date_creation', champs)
        self.assertIn('date_modification', champs)

    def test_statut_injection_toujours_ignoree_par_l_api(self):
        """SCA34 — parité API : ``statut`` reste en ``read_only_fields`` dans
        le serializer, donc l'injection d'un statut au create est IGNORÉE
        (défaut ``brouillon`` posé) — exactement comme avant la conversion.
        (Le ``blank=True`` du champ du kit est sans effet API : un champ
        read-only n'accepte jamais d'entrée.)"""
        company = make_company()
        user = make_user(company)
        st = make_sous_traitant(company)
        r = auth(user).post(f'{BASE}/ordres-sous-traitance/', {
            'sous_traitant': st.id,
            'prestation': 'Pose',
            'montant': '100',
            'statut': 'clos',    # tentative d'injection
        })
        self.assertEqual(r.status_code, 201, r.data)
        ordre = OrdreSousTraitance.objects.get(id=r.data['id'])
        self.assertEqual(ordre.statut, 'brouillon')

    def test_transitions_declaratives_et_garde(self):
        company = make_company()
        st = make_sous_traitant(company)
        ordre = OrdreSousTraitance.objects.create(
            company=company, reference='OST-K-1',
            sous_traitant=st, prestation='Pose', montant=1)
        self.assertEqual(ordre.statut, 'brouillon')
        self.assertEqual(ordre.transitions_permises(), {'emis'})
        # Transition non déclarée refusée SANS écriture.
        with self.assertRaises(TransitionRefusee):
            changer_statut(ordre, 'clos')
        ordre.refresh_from_db()
        self.assertEqual(ordre.statut, 'brouillon')
        # Transition déclarée : mute + persiste.
        changer_statut(ordre, 'emis')
        ordre.refresh_from_db()
        self.assertEqual(ordre.statut, 'emis')


# ── Chatter (ARC8 via le manifeste ARC30) ─────────────────────────────────────

class TestChatter(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.st = make_sous_traitant(self.company)
        self.ordre = OrdreSousTraitance.objects.create(
            company=self.company, reference='OST-C-1',
            sous_traitant=self.st, prestation='Pose', montant=1)

    def test_cible_declaree_dans_allowed_targets(self):
        """SCA34 — la cible est déclarée via le manifeste platform.py (ARC30),
        jamais en modifiant apps/records/models.py."""
        self.assertIn(
            ('installations', 'ordresoustraitance'), ALLOWED_TARGETS)

    def test_noter_puis_historique(self):
        r = self.api.post(
            f'{BASE}/ordres-sous-traitance/{self.ordre.id}/chatter/noter/',
            {'body': 'Sous-traitant relancé au téléphone.'})
        self.assertEqual(r.status_code, 201, r.data)
        # Auteur + société posés côté serveur.
        act = Activity.objects.get(pk=r.data['id'])
        self.assertEqual(act.company_id, self.company.id)
        self.assertEqual(act.created_by_id, self.user.id)
        r = self.api.get(
            f'{BASE}/ordres-sous-traitance/{self.ordre.id}'
            f'/chatter/historique/')
        self.assertEqual(r.status_code, 200, r.data)
        bodies = [row['body'] for row in r.data]
        self.assertIn('Sous-traitant relancé au téléphone.', bodies)

    def test_noter_reserve_responsable_admin(self):
        lecteur = make_user(self.company, role='normal')
        r = auth(lecteur).post(
            f'{BASE}/ordres-sous-traitance/{self.ordre.id}/chatter/noter/',
            {'body': 'Tentative.'})
        self.assertEqual(r.status_code, 403, r.data)

    def test_historique_lisible_tout_role(self):
        """SCA34 — la lecture du chatter est tout rôle ('chatter_historique'
        déclaré dans READ_ACTIONS, patron flotte — le get_permissions maison
        prime sur les permission_classes du mixin)."""
        lecteur = make_user(self.company, role='normal')
        r = auth(lecteur).get(
            f'{BASE}/ordres-sous-traitance/{self.ordre.id}'
            f'/chatter/historique/')
        self.assertEqual(r.status_code, 200, r.data)

    def test_chatter_cross_company_404(self):
        autre = make_user(make_company())
        r = auth(autre).get(
            f'{BASE}/ordres-sous-traitance/{self.ordre.id}'
            f'/chatter/historique/')
        self.assertEqual(r.status_code, 404)


# ── PDF (SCA33 → core.pdf, ARC11) ─────────────────────────────────────────────

class TestPdfWiring(TestCase):
    """Wiring de l'action ``pdf`` (tier rapide — service PDF mocké)."""

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.st = make_sous_traitant(self.company)
        self.ordre = OrdreSousTraitance.objects.create(
            company=self.company, reference='OST-P-1',
            sous_traitant=self.st, prestation='Pose', montant=1)

    def test_pdf_delegue_au_service_partage(self):
        with patch('core.pdf.render_pdf', return_value=b'%PDF-1.4 fake') as m:
            r = self.api.get(
                f'{BASE}/ordres-sous-traitance/{self.ordre.id}/pdf/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')
        self.assertIn(self.ordre.reference, r['Content-Disposition'])
        self.assertTrue(r.content.startswith(b'%PDF'))
        _args, kwargs = m.call_args
        self.assertEqual(
            kwargs['template'],
            'installations/ordre_soustraitance_pdf.html')
        self.assertEqual(kwargs['context']['document'].pk, self.ordre.pk)
        self.assertEqual(kwargs['company'], self.company)

    def test_pdf_lecture_tout_role(self):
        """SCA34 — le PDF est une LECTURE (même barrière que retrieve)."""
        lecteur = make_user(self.company, role='normal')
        with patch('core.pdf.render_pdf', return_value=b'%PDF-1.4 fake'):
            r = auth(lecteur).get(
                f'{BASE}/ordres-sous-traitance/{self.ordre.id}/pdf/')
        self.assertEqual(r.status_code, 200)

    def test_pdf_cross_company_404(self):
        autre = make_user(make_company())
        r = auth(autre).get(
            f'{BASE}/ordres-sous-traitance/{self.ordre.id}/pdf/')
        self.assertEqual(r.status_code, 404)


@tag('pdf')
class TestPdfRealRender(TestCase):
    """Rendu RÉEL WeasyPrint (palier lourd, image prod 3.11)."""

    def test_pdf_reel(self):
        company = make_company()
        user = make_user(company)
        st = make_sous_traitant(company)
        ordre = OrdreSousTraitance.objects.create(
            company=company, reference='OST-R-1',
            sous_traitant=st, prestation='Pose structures + câblage DC',
            montant=45000)
        r = auth(user).get(
            f'{BASE}/ordres-sous-traitance/{ordre.id}/pdf/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')
        self.assertTrue(r.content.startswith(b'%PDF'))
