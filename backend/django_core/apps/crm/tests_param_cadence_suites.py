"""PARAM-CADENCE P4 — les suites annoncées restent vraies quand la société
renomme ou désactive un barreau.

Les codes CAD17 (``suite_touche``) décrivent des EFFETS. Ce qui dépendait d'un
LIBELLÉ (la nature d'une touche, l'escalier « ne décroche pas ») se lit
désormais sur la CLÉ ; un PALIER désactivé dans Paramètres est sauté par la
promesse exactement comme par le moteur — prouvé ici de bout en bout (la
promesse servie par l'API, puis l'effet observé après « Fait »).

Horloge FIXE : mercredi 23/09/2026, 10 h à Casablanca.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, services, stages
from apps.crm import suite_touche as st
from apps.crm.models import Lead, RelanceEtape
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import (
    CADENCES_DEFAUT, Cadence, CadenceRelanceEtape,
)

User = get_user_model()

GEL = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)
A_FAIRE = RelanceEtape.Statut.A_FAIRE
APPEL = RelanceEtape.Canal.APPEL
WHATSAPP = RelanceEtape.Canal.WHATSAPP


def _etape(cadence, libelle, *, cle='', canal=APPEL, ordre=1):
    etape = RelanceEtape(cadence=cadence, ordre=ordre, canal=canal,
                         libelle=libelle, cle=cle, statut=A_FAIRE)
    etape.lead = Lead(nom='témoin', stage=stages.CONTACTED)
    return etape


def _ordres(cadence):
    return frozenset(e['ordre'] for e in CADENCES_DEFAUT.get(cadence, []))


class NatureParCleTests(SimpleTestCase):
    """Une étape RENOMMÉE garde sa nature — aucune requête (touche sans
    société : lecture des défauts)."""

    def test_l_etape_devis_renommee_vaut_toujours_devis_parti(self):
        etape = _etape('generique', 'Faire le devis', cle='devis')
        self.assertEqual(st.nature_touche(etape), st.NATURE_ENVOI_DEVIS)
        promesses = st.promesses_touche(etape, ordres=_ordres('generique'))
        self.assertEqual(promesses[st.CLE_SANS_ISSUE],
                         [st.SUIVI_PROPOSITION_DEMARRE])

    def test_un_debrief_renomme_reste_un_geste_de_visite(self):
        etape = _etape('apres_devis', 'Rappeler après la visite',
                       cle='debrief', ordre=services.VISITE_ORDRE_DEBRIEF)
        self.assertEqual(st.nature_touche(etape), st.NATURE_VISITE)
        promesses = st.promesses_touche(etape, ordres=_ordres('apres_devis'))
        self.assertEqual(promesses['non_joint'],
                         [st.SUITE_SI_PLUS_RIEN_OUVERT])

    def test_une_etape_de_filet_renommee_reste_du_filet(self):
        etape = _etape('generique', 'Rappeler le client', cle='rappel_convenu')
        self.assertEqual(st.nature_touche(etape), st.NATURE_FILET)

    def test_un_libelle_renomme_sans_cle_est_un_barreau(self):
        etape = _etape('contact', 'Faire le devis', ordre=2)
        self.assertEqual(st.nature_touche(etape), st.NATURE_BARREAU)

    def test_l_escalier_renomme_se_lit_en_cles(self):
        etape = _etape('generique', 'Rappeler — il a écrit',
                       cle='appel_apres_reponse')
        promesses = st.promesses_touche(etape, ordres=_ordres('generique'))
        self.assertEqual(promesses['non_joint'], [st.ETAPE_MESSAGE_CRENEAU])

    def test_le_lecteur_sans_societe_ne_fait_aucune_requete(self):
        est_actif = st.lecteur_paliers_actifs(None)
        self.assertTrue(est_actif('message_creneau'))
        self.assertTrue(est_actif('devis'))


class PalierDesactivePromesseEtEffetTests(TestCase):
    """La promesse servie par l'API = l'effet du moteur, palier désactivé."""

    def setUp(self):
        gel = frozen(GEL)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = Company.objects.create(nom='PCAD S', slug='pcad-s')
        CompanyProfile.objects.get_or_create(company=self.company)
        for cadence in CADENCES_DEFAUT:
            CadenceRelanceEtape.cadence_pour(self.company, cadence)
        self.acteur = User.objects.create_user(
            username='pcad-s-resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')
        self.lead = Lead.objects.create(
            company=self.company, nom='Idrissi', stage=stages.CONTACTED,
            owner=self.acteur, telephone='+212661000852')

    def _desactiver(self, *cles):
        CadenceRelanceEtape.objects.filter(
            company=self.company, cadence=Cadence.APRES_CONTACT,
            cle__in=cles).update(actif=False)

    def _touche(self, **champs):
        valeurs = dict(company=self.company, lead=self.lead, due_at=GEL,
                       due_date=GEL.date(), cadence_depart=GEL)
        valeurs.update(champs)
        return RelanceEtape.objects.create(**valeurs)

    def _promesse_puis_effet(self, touche, reponse):
        ligne = self.api.get('/api/django/crm/relance-etapes/',
                             {'lead': self.lead.pk}).data['results'][0]
        self.assertEqual(ligne['id'], touche.pk)
        resp = self.api.post(
            f'/api/django/crm/relance-etapes/{touche.pk}/fait/',
            {'outcome': reponse}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        ouvertes = list(self.lead.relance_etapes.filter(statut=A_FAIRE))
        return ligne['suites'][reponse], ouvertes

    def _appel_apres_reponse(self):
        return self._touche(cadence='generique', ordre=1, canal=APPEL,
                            libelle=services.FILET_APPEL_LIBELLE,
                            cle='appel_apres_reponse')

    def test_message_creneau_desactive(self):
        self._desactiver('message_creneau')
        codes, [etape] = self._promesse_puis_effet(
            self._appel_apres_reponse(), 'non_joint')
        self.assertEqual(codes, [st.ETAPE_DERNIER_APPEL])
        self.assertEqual(etape.cle, 'dernier_appel')

    def test_les_deux_paliers_desactives(self):
        self._desactiver('message_creneau', 'dernier_appel')
        codes, [etape] = self._promesse_puis_effet(
            self._appel_apres_reponse(), 'non_joint')
        self.assertEqual(codes, [st.ETAPE_DEVIS_DEMAIN_SAUF_SUIVI])
        self.assertEqual(etape.cle, 'devis')

    def test_message_repondu_appel_desactive(self):
        self._desactiver('appel_apres_reponse')
        message = self._touche(cadence='contact', ordre=1, canal=WHATSAPP,
                               libelle="Message d'identité")
        codes, [etape] = self._promesse_puis_effet(message, 'joint')
        self.assertEqual(codes, [st.CONTACT_ARRETEE, st.ETAPE_DEVIS_DEMAIN])
        self.assertEqual(etape.cle, 'devis')

    def test_temoin_tout_actif(self):
        message = self._touche(cadence='contact', ordre=1, canal=WHATSAPP,
                               libelle="Message d'identité")
        codes, [etape] = self._promesse_puis_effet(message, 'joint')
        self.assertEqual(codes, [st.CONTACT_ARRETEE, st.ETAPE_APPELER])
        self.assertEqual(etape.cle, 'appel_apres_reponse')
