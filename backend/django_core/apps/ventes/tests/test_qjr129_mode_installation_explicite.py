"""QJR129 — un devis né « à partir de rien » porte un MARCHÉ, jamais un blanc.

Constat CS7 (audit du 30/08/2026), vérifié en code : les chemins qui créent un
devis sans composition — document OCR, réserve d'intervention — laissaient
``mode_installation`` NULL, alors que le chemin canonique le pose
explicitement.

Or le discriminateur de rendu ACCEPTE le vide
(``quote_engine/residential/renderer.is_residential`` : ``if mode not in ("",
"residentiel", "résidentiel")``), un repli que le dépôt qualifie lui-même de
« défaut d'AFFICHAGE PDF choisi pour ne jamais perdre le rendu d'un devis, PAS
une preuve que ce devis EST résidentiel ». Et ``is_residential`` pilote AUSSI la
page publique client. Un bordereau de marché à prix unitaires (« Terrassement
(m³) ») partait donc au client dans la présentation « proposition solaire
résidentielle ».

Lancer :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr129_mode_installation_explicite -v 2
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from apps.ventes.domain.creation import (
    MODES_INSTALLATION, mode_installation_declare,
)
from apps.ventes.models import Devis
from apps.ventes.quote_engine.residential.renderer import is_residential

User = get_user_model()
_seq = itertools.count(1)


class _Porteur:
    """Un objet nu qui porte l'attribut qu'on lui donne — la fonction ne lit
    QUE des attributs, jamais la base."""

    def __init__(self, **attrs):
        self.__dict__.update(attrs)


class LeMarcheDeclarePasseDevantLeDefaut(SimpleTestCase):
    """La moitié PURE, sans base."""

    def test_les_quatre_modes_du_devis_sont_les_quatre_du_lead(self):
        """``crm.Lead.TypeInstallation`` et ``Devis.ModeInstallation`` portent
        les MÊMES valeurs : le recoupement est direct, sans table de
        correspondance qui pourrait dériver."""
        from apps.crm.models import Lead

        self.assertEqual(
            set(MODES_INSTALLATION),
            {v for v, _ in Devis.ModeInstallation.choices})
        self.assertEqual(
            set(MODES_INSTALLATION),
            {v for v, _ in Lead.TypeInstallation.choices})

    def test_le_premier_declare_gagne(self):
        self.assertEqual(
            mode_installation_declare(
                _Porteur(mode_installation='agricole'),
                _Porteur(type_installation='industriel'),
                defaut='commercial'),
            'agricole')

    def test_type_installation_est_lu_quand_mode_installation_manque(self):
        self.assertEqual(
            mode_installation_declare(
                _Porteur(type_installation='industriel'), defaut='commercial'),
            'industriel')

    def test_none_et_vide_sont_ignores(self):
        self.assertEqual(
            mode_installation_declare(
                None, _Porteur(mode_installation=''),
                _Porteur(type_installation=None), defaut='industriel'),
            'industriel')

    def test_une_valeur_hors_choix_est_ecartee(self):
        """Le champ est à choix FERMÉS : y poser une valeur inconnue la ferait
        rejeter par la validation du modèle, en silence côté service."""
        self.assertEqual(
            mode_installation_declare(
                _Porteur(type_installation='tertiaire'), defaut='commercial'),
            'commercial')

    def test_aucune_source_rend_le_defaut(self):
        self.assertEqual(
            mode_installation_declare(defaut='commercial'), 'commercial')


class _Base(TestCase):
    """Société + utilisateur, un par classe."""

    slug = 'qjr129'

    def setUp(self):
        from authentication.models import Company

        self.company, _ = Company.objects.get_or_create(
            slug=self.slug, defaults={'nom': self.slug})
        self.user = User.objects.create_user(
            username='qjr129-%d' % next(_seq), password='x',
            company=self.company, role_legacy='admin')


class LeBrouillonOcrPorteUnMarche(_Base):
    """CS7, chemin OCR."""

    slug = 'qjr129-ocr'

    def _lead(self, **extra):
        from apps.crm.models import Lead

        return Lead.objects.create(
            company=self.company, nom='Prospect', prenom='OCR',
            telephone='+21260000%04d' % next(_seq),
            email='qjr129-ocr-%d@example.com' % next(_seq), **extra)

    def test_sans_marche_declare_le_brouillon_est_commercial(self):
        from apps.ventes.domain.creation import create_draft_devis_from_ocr

        devis = create_draft_devis_from_ocr(
            company=self.company, user=self.user, lead=self._lead(),
            fields={'numero': 'F-2026-118', 'montant_ttc': '42000'})
        self.assertEqual(devis.mode_installation,
                         Devis.ModeInstallation.COMMERCIAL)
        self.assertFalse(is_residential(devis))
        # Le service CRÉE, il n'ouvre aucun statut aval (règle #4).
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)

    def test_le_marche_du_lead_passe_devant_le_defaut(self):
        from apps.ventes.domain.creation import create_draft_devis_from_ocr

        devis = create_draft_devis_from_ocr(
            company=self.company, user=self.user,
            lead=self._lead(type_installation='agricole'), fields={})
        self.assertEqual(devis.mode_installation, 'agricole')


class LeDevisDeReparationPorteLeMarcheDuChantier(_Base):
    """CS7, chemin réserve d'intervention."""

    slug = 'qjr129-reserve'

    def _reserve(self, **installation_extra):
        from apps.crm.models import Client
        from apps.installations.models import (
            Installation, Intervention, Reserve,
        )

        client = Client.objects.create(
            company=self.company, nom='Client', prenom='QJR129',
            email='qjr129-res-%d@example.com' % next(_seq))
        installation = Installation.objects.create(
            company=self.company, reference='CHT-QJR129-%d' % next(_seq),
            client=client, **installation_extra)
        intervention = Intervention.objects.create(
            company=self.company, installation=installation,
            type_intervention='depannage', created_by=self.user)
        return Reserve.objects.create(
            company=self.company, intervention=intervention,
            description='Fissure sur le rail de fixation.',
            created_by=self.user)

    def test_sans_marche_connu_le_devis_de_reparation_est_commercial(self):
        from apps.ventes.domain.gammes import create_devis_from_reserve

        devis = create_devis_from_reserve(
            reserve=self._reserve(), user=self.user)
        self.assertEqual(devis.mode_installation,
                         Devis.ModeInstallation.COMMERCIAL)
        self.assertFalse(is_residential(devis))
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)

    def test_le_type_du_chantier_est_repris(self):
        from apps.ventes.domain.gammes import create_devis_from_reserve

        devis = create_devis_from_reserve(
            reserve=self._reserve(type_installation='residentiel'),
            user=self.user)
        self.assertEqual(devis.mode_installation, 'residentiel')

    def test_le_devis_d_origine_du_chantier_passe_en_premier(self):
        """Le devis qui a fait naître le chantier est la déclaration la plus
        précise de son marché."""
        from apps.crm.models import Client
        from apps.ventes.domain.gammes import create_devis_from_reserve

        client = Client.objects.create(
            company=self.company, nom='Client', prenom='Origine',
            email='qjr129-origine-%d@example.com' % next(_seq))
        origine = Devis.objects.create(
            company=self.company, client=client,
            reference='DEV-QJR129-ORIG', statut=Devis.Statut.ACCEPTE,
            mode_installation='agricole', created_by=self.user)
        reserve = self._reserve(type_installation='residentiel')
        reserve.intervention.installation.devis = origine
        reserve.intervention.installation.save(update_fields=['devis'])

        devis = create_devis_from_reserve(reserve=reserve, user=self.user)
        self.assertEqual(devis.mode_installation, 'agricole')
