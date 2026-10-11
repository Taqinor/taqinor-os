"""ACRM12 (C-ACRM-007) — seule la fin RÉELLE du gabarit clôt une cadence.

Sonde V_VB LSVC1-1 : le barreau de la touche ouverte désactivé par l'API
Paramètres, « Fait » sur cette touche → le lead partait au Froid, étiqueté
« Injoignable 6 appels », avec réveils J30/J60 — alors que cinq barreaux
actifs restaient. Désormais ``materialiser_touche_suivante`` rend une raison
TYPÉE et ``marquer_etape_relance`` ne clôt que sur ``FIN_GABARIT`` :
(a) barreau désactivé → la suite part du barreau actif suivant ;
(b) panne de la matérialisation (doublure DÉCLARÉE sur cette seule
dépendance) → raison indéterminée, le filet pose une suite, jamais le Froid ;
(c) gabarit réellement épuisé → clôture au Froid comme avant.

Jumeau ``assurer_prochaine_etape_apres_succes`` : il ne clôt jamais (une
suite absente y retombe sur l'étape générique du filet) — non touché.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm import stages
from apps.crm.models import Lead, RelanceEtape
from apps.crm.cadence_plan import initialiser_plan_relance
from apps.parametres.models_relance import CadenceRelanceEtape
from apps.roles.models import Role
from apps.roles.permissions_registre import DIRECTEUR_PERMISSIONS

User = get_user_model()


class CadenceFinAmbigueTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='ACRM12 Solaire', slug='acrm12-cadence')
        role = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=list(DIRECTEUR_PERMISSIONS), est_systeme=True)
        self.user = User.objects.create_user(
            username='acrm12-dir', password='x', company=self.company,
            role=role)
        self.lead = Lead.objects.create(
            company=self.company, nom='Cadence', owner=self.user,
            stage=stages.CONTACTED, telephone='+212661121212')
        RelanceEtape.objects.filter(lead=self.lead).delete()
        initialiser_plan_relance(self.lead, self.user, cadence='contact')
        self.touche = (self.lead.relance_etapes
                       .filter(statut=RelanceEtape.Statut.A_FAIRE)
                       .order_by('ordre').first())
        self.assertIsNotNone(self.touche)
        self.api = APIClient()
        self.api.credentials(HTTP_AUTHORIZATION=(
            f'Bearer {AccessToken.for_user(self.user)}'))

    def _barreau(self, ordre):
        return CadenceRelanceEtape.objects.get(
            company=self.company, cadence='contact', ordre=ordre)

    def _fait(self):
        corps = ({'outcome': 'pas_de_reponse'}
                 if self.touche.canal == RelanceEtape.Canal.APPEL else {})
        resp = self.api.post(
            f'/api/django/crm/relance-etapes/{self.touche.pk}/fait/',
            corps, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)

    def _assert_pas_parque(self):
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.CONTACTED)
        self.assertNotIn('Injoignable', self.lead.tags or '')
        self.assertTrue(self.lead.relance_etapes.filter(
            statut=RelanceEtape.Statut.A_FAIRE).exists())

    def test_barreau_desactive_ne_parque_pas(self):
        barreau = self._barreau(self.touche.ordre)
        resp = self.api.patch(
            f'/api/django/parametres/cadence-relance/{barreau.pk}/',
            {'actif': False}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self._fait()
        self._assert_pas_parque()
        # La suite est le premier barreau ACTIF d'ordre supérieur.
        suivant = (CadenceRelanceEtape.objects
                   .filter(company=self.company, cadence='contact',
                           actif=True, ordre__gt=self.touche.ordre)
                   .order_by('ordre').first())
        self.assertTrue(self.lead.relance_etapes.filter(
            statut=RelanceEtape.Statut.A_FAIRE, cadence='contact',
            ordre=suivant.ordre).exists())

    def test_exception_ne_parque_pas(self):
        with patch('apps.crm.cadence_plan._materialiser_touche_suivante',
                   side_effect=RuntimeError('panne déclarée')):
            self._fait()
        self._assert_pas_parque()

    def test_fin_reelle_parque(self):
        CadenceRelanceEtape.objects.filter(
            company=self.company, cadence='contact',
            ordre__gt=self.touche.ordre).update(actif=False)
        # CI #904 — ``initialiser_plan_relance`` matérialise aussi les touches
        # DÉJÀ ÉCHUES : passé l'ouverture des appels (09:00, Casablanca), les
        # touches du jour même sont échues et restent ouvertes, donc la touche
        # close n'est plus la DERNIÈRE ouverte (``restantes_avant`` > 0) et la
        # cadence ne se clôt pas — le test ne passait qu'avant 09:00. Une fin
        # RÉELLE, c'est aussi : plus aucune touche ouverte des barreaux qu'on
        # vient de désactiver. On la pose explicitement, à toute heure.
        self.lead.relance_etapes.filter(
            cadence='contact', statut=RelanceEtape.Statut.A_FAIRE,
            ordre__gt=self.touche.ordre).delete()
        self.assertEqual(
            self.lead.relance_etapes.filter(
                cadence='contact',
                statut=RelanceEtape.Statut.A_FAIRE).count(), 1)
        self._fait()
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.COLD)
