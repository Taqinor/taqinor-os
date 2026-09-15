"""VISITE-CADENCE — les trois routes de la fiche lead (contrats PACT10).

La moitié frontend se construit CONTRE ces formes
(``apps/crm/contract_samples/lead_visites.json``,
``lead_visite_planifier.json``, ``lead_message_visite.json``) : ce fichier les
verrouille.

Ce qui est prouvé :

* les formes servies sont EXACTEMENT celles des contrats — clés comprises ;
* chaque refus NOMME son champ (règle fondateur 08/09/2026), jamais un
  « non enregistré » générique ;
* l'isolation multi-société tient sur les trois routes (404, jamais 403 : on
  ne confirme pas l'existence d'une fiche qu'on n'a pas le droit de voir) ;
* la PORTÉE est celle du CRM (``crm_voir`` / ``crm_modifier``) et PAS la
  portée dure « mes visites » de l'app terrain : un responsable CRM voit les
  visites de son dossier même s'il n'est pas le commercial assigné.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from testkit.time import frozen

from apps.crm import horaires
from apps.crm.models import Lead
from apps.parametres.models import CompanyProfile
from apps.roles.models import Role
from apps.visites.models import VisiteTerrain
from authentication.models import Company

User = get_user_model()

MAINTENANT = datetime.datetime(2026, 9, 15, 10, 0, tzinfo=horaires.CASABLANCA)
AUJOURDHUI = datetime.date(2026, 9, 15)
DEMAIN = datetime.date(2026, 9, 16)

CRM_LECTURE = ['crm_voir']
CRM_ECRITURE = ['crm_voir', 'crm_modifier']


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, username, permissions):
    return User.objects.create_user(
        username=username, password='x', company=company,
        role_legacy='normal',
        role=Role.objects.create(company=company, nom=f'role-{username}',
                                 permissions=list(permissions)))


class VisiteApiBase(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='VCADAPI Solaire',
                                              slug='vcadapi-a')
        self.autre = Company.objects.create(nom='VCADAPI Concurrent',
                                            slug='vcadapi-b')
        CompanyProfile.objects.get_or_create(company=self.company)
        CompanyProfile.objects.get_or_create(company=self.autre)
        self.commerciale = make_user(self.company, 'vcadapi-com',
                                     CRM_ECRITURE)
        self.lecteur = make_user(self.company, 'vcadapi-lecteur',
                                 CRM_LECTURE)
        self.etranger = make_user(self.autre, 'vcadapi-etranger',
                                  CRM_ECRITURE)
        self.lead = Lead.objects.create(
            company=self.company, nom='Bennani', prenom='Karim',
            ville='Bouskoura', owner=self.commerciale)
        self.lead_autre = Lead.objects.create(
            company=self.autre, nom='Client concurrent')
        self.api = auth(self.commerciale)

    def _url(self, suffixe, lead=None):
        return f'/api/django/crm/leads/{(lead or self.lead).id}/{suffixe}'


class ListeVisitesTests(VisiteApiBase):
    URL = 'visites/'

    def test_sert_la_forme_du_contrat(self):
        VisiteTerrain.objects.create(
            company=self.company, lead=self.lead, date_prevue=DEMAIN,
            commercial=self.commerciale, notes='Portail bleu')
        reponse = self.api.get(self._url(self.URL))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(list(reponse.data), ['visites'])
        ligne = reponse.data['visites'][0]
        self.assertEqual(
            sorted(ligne),
            ['commercial_nom', 'date_prevue', 'date_realisee', 'id', 'notes',
             'retour_disponible', 'statut', 'statut_libelle'])
        self.assertEqual(ligne['date_prevue'], DEMAIN.isoformat())
        self.assertIs(ligne['retour_disponible'], True)

    def test_un_lead_sans_visite_rend_une_liste_vide(self):
        reponse = self.api.get(self._url(self.URL))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data, {'visites': []})

    def test_isolation_societe(self):
        VisiteTerrain.objects.create(
            company=self.autre, lead=self.lead_autre, date_prevue=DEMAIN)
        reponse = self.api.get(self._url(self.URL, lead=self.lead_autre))
        self.assertEqual(reponse.status_code, 404)

    def test_lecture_ouverte_a_qui_porte_crm_voir(self):
        """La portée dure « mes visites » (VTA6) n'est PAS recopiée ici : un
        lecteur CRM voit les visites de son dossier sans être l'assigné."""
        VisiteTerrain.objects.create(
            company=self.company, lead=self.lead, date_prevue=DEMAIN)
        reponse = auth(self.lecteur).get(self._url(self.URL))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(len(reponse.data['visites']), 1)


class PlanifierVisiteApiTests(VisiteApiBase):
    URL = 'visites/planifier/'

    def setUp(self):
        super().setUp()
        # Les POST de cette classe se jouent SOUS ``frozen(MAINTENANT)`` : un
        # jeton émis au vrai « maintenant » de la machine est déjà expiré (ou
        # pas encore valide) sous l'horloge gelée → 401 « Token invalide ou
        # expiré ». On émet donc le jeton À LA MÊME horloge que les requêtes.
        with frozen(MAINTENANT):
            self.api = auth(self.commerciale)

    def test_cree_et_rend_la_ligne_du_contrat(self):
        with frozen(MAINTENANT):
            reponse = self.api.post(
                self._url(self.URL),
                {'date_prevue': DEMAIN.isoformat(),
                 'commercial': self.commerciale.id,
                 'notes': 'Portail bleu'}, format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.assertEqual(list(reponse.data), ['visite'])
        ligne = reponse.data['visite']
        self.assertEqual(
            sorted(ligne),
            ['commercial_nom', 'date_prevue', 'date_realisee', 'id', 'notes',
             'retour_disponible', 'statut', 'statut_libelle'])
        self.assertEqual(ligne['statut'], 'brouillon')
        self.assertEqual(ligne['date_prevue'], DEMAIN.isoformat())

        visite = VisiteTerrain.objects.get(pk=ligne['id'])
        # La société est FORCÉE côté serveur, prise du lead.
        self.assertEqual(visite.company_id, self.company.id)
        # Et l'effet de bord attendu : la fiche porte la date.
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.visite_prevue_le, DEMAIN)

    def test_sans_commercial_la_visite_reste_non_assignee(self):
        with frozen(MAINTENANT):
            reponse = self.api.post(
                self._url(self.URL), {'date_prevue': DEMAIN.isoformat()},
                format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.assertEqual(reponse.data['visite']['commercial_nom'], '')

    def test_une_date_illisible_nomme_son_champ(self):
        # Sous frozen comme TOUTES les requêtes de la classe : le jeton du
        # setUp est émis à MAINTENANT — hors gel, il n'est « pas encore
        # valide » à l'heure réelle de la CI.
        with frozen(MAINTENANT):
            reponse = self.api.post(
                self._url(self.URL), {'date_prevue': '17 septembre'},
                format='json')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('date_prevue', reponse.data)
        self.assertEqual(VisiteTerrain.objects.count(), 0)

    def test_une_date_passee_nomme_son_champ(self):
        with frozen(MAINTENANT):
            reponse = self.api.post(
                self._url(self.URL),
                {'date_prevue': (
                    AUJOURDHUI - datetime.timedelta(days=1)).isoformat()},
                format='json')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('date_prevue', reponse.data)
        self.assertEqual(VisiteTerrain.objects.count(), 0)

    def test_une_date_absente_nomme_son_champ(self):
        with frozen(MAINTENANT):
            reponse = self.api.post(self._url(self.URL), {}, format='json')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('date_prevue', reponse.data)

    def test_un_commercial_dune_autre_societe_nomme_son_champ(self):
        with frozen(MAINTENANT):
            reponse = self.api.post(
                self._url(self.URL),
                {'date_prevue': DEMAIN.isoformat(),
                 'commercial': self.etranger.id}, format='json')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('commercial', reponse.data)
        self.assertEqual(VisiteTerrain.objects.count(), 0)

    def test_isolation_societe(self):
        with frozen(MAINTENANT):
            reponse = self.api.post(
                self._url(self.URL, lead=self.lead_autre),
                {'date_prevue': DEMAIN.isoformat()}, format='json')
        self.assertEqual(reponse.status_code, 404)
        self.assertEqual(VisiteTerrain.objects.count(), 0)

    def test_une_lecture_seule_ne_planifie_pas(self):
        with frozen(MAINTENANT):
            reponse = auth(self.lecteur).post(
                self._url(self.URL), {'date_prevue': DEMAIN.isoformat()},
                format='json')
        self.assertEqual(reponse.status_code, 403, reponse.status_code)
        self.assertEqual(VisiteTerrain.objects.count(), 0)


class MessageVisiteApiTests(VisiteApiBase):
    URL = 'message-visite/'

    def test_sert_les_deux_langues(self):
        self.lead.visite_prevue_le = datetime.date(2026, 9, 22)
        self.lead.save(update_fields=['visite_prevue_le'])
        reponse = self.api.get(
            self._url(self.URL) + '?cle=visite_confirmation')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(sorted(reponse.data), ['corps_darija', 'corps_fr'])
        self.assertIn('mardi 22 septembre', reponse.data['corps_fr'])

    def test_la_proposition_ne_reclame_aucune_date(self):
        reponse = self.api.get(
            self._url(self.URL) + '?cle=visite_proposition')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertIn('vérification technique gratuite',
                      reponse.data['corps_fr'])

    def test_une_cle_inconnue_nomme_son_champ(self):
        reponse = self.api.get(self._url(self.URL) + '?cle=apres_visite')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('cle', reponse.data)

    def test_une_cle_absente_nomme_son_champ(self):
        reponse = self.api.get(self._url(self.URL))
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('cle', reponse.data)

    def test_isolation_societe(self):
        reponse = self.api.get(
            self._url(self.URL, lead=self.lead_autre)
            + '?cle=visite_proposition')
        self.assertEqual(reponse.status_code, 404)

    def test_lecture_ouverte_a_qui_porte_crm_voir(self):
        reponse = auth(self.lecteur).get(
            self._url(self.URL) + '?cle=visite_proposition')
        self.assertEqual(reponse.status_code, 200, reponse.data)
