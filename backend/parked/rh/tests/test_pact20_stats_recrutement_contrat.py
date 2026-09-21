"""PACT20 — la forme de `stats_recrutement` est un CONTRAT, plus une supposition.

L'onglet « RH → Recrutement → Statistiques » affichait « — » sur ses 4 tuiles
POUR TOUJOURS : il lisait `delai_embauche_moyen`, `total_candidatures`,
`total_embauches`, `ouvertures_actives` ; le serveur renvoie
`delai_embauche_moyen_jours`, `entonnoir`, `candidatures_par_ouverture`,
`sources`. Aucune erreur, aucune alerte — juste quatre tirets que personne ne
remarque.

L'écran est désormais dérivé de ce que le serveur SAIT dire, et son test vitest
importe l'exemple committé (`contract_samples/stats_recrutement.json`, PACT10/
PACT13) au lieu de réinventer la charge utile. Ce module est l'autre moitié du
lien : il affirme que la VRAIE réponse du sélecteur a exactement les clés de cet
exemple. `scripts/check_api_shapes.py` ne peut pas dériver statiquement la forme
de `RecrutementStatistiquesViewSet.list` (le doute ne rougit jamais), donc sans
ce test l'exemple pourrirait dans son coin — ce que le README de
`contract_samples/` désigne comme pire que pas d'exemple du tout.
"""
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.rh.selectors import stats_recrutement

User = get_user_model()
URL = '/api/django/rh/recrutement/statistiques/'
ECHANTILLON = (Path(__file__).resolve().parent.parent
               / 'contract_samples' / 'stats_recrutement.json')
ETAPES_ENTONNOIR = ['embauche', 'entretien', 'offre', 'preselection', 'recu',
                    'rejete']


class Pact20StatsRecrutementContratTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='PACT20 Co')
        self.user = User.objects.create_user(
            username='pact20_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.contrat = json.loads(ECHANTILLON.read_text(encoding='utf-8'))

    def test_les_cles_du_selecteur_sont_celles_de_l_exemple(self):
        reelle = stats_recrutement(self.company)
        for variante in ('exemple', 'exemple_vide'):
            self.assertEqual(sorted(self.contrat[variante]), sorted(reelle),
                             variante)

    def test_l_entonnoir_publie_toujours_ses_six_etages(self):
        """Les 4 tuiles en dérivent (candidatures = recu + rejete, embauches =
        embauche) : un étage absent les remettrait à « — »."""
        reelle = stats_recrutement(self.company)
        self.assertEqual(sorted(reelle['entonnoir']), ETAPES_ENTONNOIR)
        for variante in ('exemple', 'exemple_vide'):
            self.assertEqual(sorted(self.contrat[variante]['entonnoir']),
                             ETAPES_ENTONNOIR, variante)

    def test_l_ancienne_forme_lue_par_l_ecran_n_a_jamais_existe(self):
        """La régression de PACT20, épinglée : ces 4 clés ne doivent JAMAIS
        réapparaître dans l'exemple — c'est ce que l'écran lisait à tort."""
        reelle = stats_recrutement(self.company)
        for cle in ('delai_embauche_moyen', 'total_candidatures',
                    'total_embauches', 'ouvertures_actives'):
            self.assertNotIn(cle, reelle)
            self.assertNotIn(cle, self.contrat['exemple'])

    def test_la_route_renvoie_bien_cette_forme(self):
        api = APIClient()
        api.force_authenticate(user=self.user)
        resp = api.get(URL)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(sorted(resp.data),
                         sorted(self.contrat['exemple_vide']))
