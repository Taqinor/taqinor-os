"""MRY11 — Ce que devient un lead dont la cadence s'est épuisée sans réponse.

Il ne doit pas rester au milieu du pipeline à encombrer la vue de Meryem, et
il ne doit pas non plus disparaître : il part au PARKING (COLD) avec une
étiquette qui dit POURQUOI, et deux réveils J30/J60 qui le rendront un jour.
C'est ce qui distingue « mis de côté » de « oublié ».

La distinction que ce fichier verrouille avant tout : une cadence ARRÊTÉE
(MRY9 — on a joint le client) n'est PAS une cadence terminée. Clôturer un lead
qu'on vient de joindre serait exactement l'inverse du bon geste ; la clôture
n'est donc déclenchée que depuis `marquer_etape_relance`, jamais depuis
`arreter_cadence`.

Et COLD reste un PARKING, pas une perte : aucun motif de perte n'est posé ici.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm import horaires, stages
from apps.crm.models import Lead, RelanceEtape
from apps.crm.services import (
    arreter_cadence, initialiser_plan_relance, marquer_etape_relance)
from apps.parametres.models import CompanyProfile

User = get_user_model()

LUNDI = datetime.datetime(2026, 9, 7, 9, 0, tzinfo=horaires.CASABLANCA)


def _company(slug):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    CompanyProfile.objects.get_or_create(company=company)
    return company


class _Base(TestCase):
    slug = 'mry11'

    def setUp(self):
        self.company = _company(self.slug)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-u', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Prospect', owner=self.acteur,
            telephone='+212661112233')

    def _epuiser(self, cadence):
        """Traite TOUTES les touches d'une cadence, sans issue « joint »."""
        etapes = initialiser_plan_relance(
            self.lead, self.acteur, depart=LUNDI, cadence=cadence)
        for etape in etapes:
            marquer_etape_relance(
                etape, self.acteur, RelanceEtape.Statut.FAIT)
        self.lead.refresh_from_db()
        return etapes

    def _reveils(self):
        return self.lead.relance_etapes.filter(cadence='reveil')


class ClotureContactTests(_Base):
    slug = 'mry11-contact'

    def test_la_derniere_touche_traitee_met_le_lead_au_froid(self):
        self._epuiser('contact')
        self.assertEqual(self.lead.stage, stages.COLD)

    def test_letiquette_dit_pourquoi(self):
        self._epuiser('contact')
        self.assertIn('Injoignable 7 tentatives', self.lead.tags or '')

    def test_deux_reveils_sont_poses(self):
        self._epuiser('contact')
        reveils = self._reveils()
        self.assertEqual(reveils.count(), 2)
        self.assertEqual(
            {e.statut for e in reveils}, {RelanceEtape.Statut.A_FAIRE})

    def test_cold_est_un_parking_pas_une_perte(self):
        """Aucun motif de perte n'est posé : `perdu` est une décision humaine
        (MRY22), jamais la conséquence mécanique d'un silence."""
        self._epuiser('contact')
        self.assertFalse(self.lead.perdu)
        self.assertFalse(self.lead.motif_perte)


class ClotureApresDevisTests(_Base):
    slug = 'mry11-apres'

    def test_etiquette_dediee(self):
        # La cadence après devis parque un lead jusqu'à FOLLOW_UP inclus.
        self.lead.stage = stages.QUOTE_SENT
        self.lead.save(update_fields=['stage'])
        self._epuiser('apres_devis')
        self.assertIn('Devis sans suite', self.lead.tags or '')
        self.assertEqual(self.lead.stage, stages.COLD)


class NonRegressionTests(_Base):
    slug = 'mry11-non-regression'

    def test_un_lead_plus_avance_ne_recule_pas_vers_COLD(self):
        """`_bulk_stage_allowed` autorise « vers COLD » depuis N'IMPORTE OÙ
        (voulu pour un parking MANUEL) : sans le plafond de MRY11, épuiser une
        cadence `contact` sur un lead qui a depuis SIGNÉ le ferait retomber au
        froid — un devis signé effacé par un rappel resté ouvert."""
        etapes = initialiser_plan_relance(
            self.lead, self.acteur, depart=LUNDI, cadence='contact')
        self.lead.stage = stages.SIGNED
        self.lead.save(update_fields=['stage'])
        for etape in etapes:
            etape.refresh_from_db()
            if etape.statut == RelanceEtape.Statut.A_FAIRE:
                marquer_etape_relance(
                    etape, self.acteur, RelanceEtape.Statut.FAIT)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.SIGNED)

    def test_un_arret_MRY9_ne_declenche_PAS_la_cloture(self):
        """LE point du lot : on vient de JOINDRE le client — le mettre au
        froid et l'étiqueter « injoignable » serait l'inverse du bon geste."""
        initialiser_plan_relance(
            self.lead, self.acteur, depart=LUNDI, cadence='contact')
        arreter_cadence(self.lead, user=self.acteur, motif='joint',
                        cadences=['contact'])
        self.lead.refresh_from_db()
        self.assertNotEqual(self.lead.stage, stages.COLD)
        self.assertNotIn('Injoignable', self.lead.tags or '')
        self.assertEqual(self._reveils().count(), 0)

    def test_une_cadence_reveil_epuisee_ne_se_reclot_pas(self):
        """Sinon un lead réveillé sans réponse entrerait dans une boucle de
        réveils infinie."""
        etapes = initialiser_plan_relance(
            self.lead, self.acteur, depart=LUNDI, cadence='reveil')
        for etape in etapes:
            marquer_etape_relance(
                etape, self.acteur, RelanceEtape.Statut.FAIT)
        self.assertEqual(self._reveils().count(), len(etapes))

    def test_une_touche_restante_ne_declenche_rien(self):
        etapes = initialiser_plan_relance(
            self.lead, self.acteur, depart=LUNDI, cadence='contact')
        marquer_etape_relance(
            etapes[0], self.acteur, RelanceEtape.Statut.FAIT)
        self.lead.refresh_from_db()
        self.assertNotEqual(self.lead.stage, stages.COLD)
        self.assertEqual(self._reveils().count(), 0)


class ToucheJointeEnMilieuDeCadenceTests(_Base):
    """LE défaut BLOQUANT de MRY11 × MRY9, reproduit par le VRAI chemin de
    l'écran : le Cockpit poste « Fait » avec l'issue « joint ».

    L'enchaînement qui inversait le résultat : la vue appelle
    `marquer_etape_relance`, qui crée l'activité de chatter portant l'issue ;
    le récepteur `_arreter_cadence_on_outcome` (MRY9) tourne SYNCHRONEMENT sur
    ce post_save et passe toutes les touches restantes à SAUTEE ; de retour
    dans `marquer_etape_relance`, la question « reste-t-il une touche à
    faire ? » répondait « non » — et le lead qu'on venait de JOINDRE au 3ᵉ
    appel partait au froid, étiqueté injoignable, avec deux réveils.
    """

    slug = 'mry11-joint'

    def setUp(self):
        super().setUp()
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')
        self.etapes = initialiser_plan_relance(
            self.lead, self.acteur, depart=LUNDI, cadence='contact')

    def _fait(self, etape, **corps):
        return self.api.post(
            f'/api/django/crm/relance-etapes/{etape.pk}/fait/',
            corps, format='json')

    def test_la_cadence_de_contact_porte_bien_onze_touches(self):
        """Garde de lecture : le protocole v3 = 6 appels + 5 WhatsApp."""
        self.assertEqual(len(self.etapes), 11)

    def test_joint_au_troisieme_appel_ne_refroidit_pas_le_lead(self):
        resp = self._fait(self.etapes[2], outcome='joint')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.lead.refresh_from_db()
        self.assertNotEqual(self.lead.stage, stages.COLD)
        # Le seul mouvement d'étape légitime ici est QJ7 (NEW → CONTACTED sur
        # un contact humain) — jamais un parking au froid.
        self.assertIn(self.lead.stage, (stages.NEW, stages.CONTACTED))

    def test_joint_au_troisieme_appel_ne_pose_aucune_etiquette_injoignable(self):
        self._fait(self.etapes[2], outcome='joint')
        self.lead.refresh_from_db()
        self.assertNotIn('Injoignable', self.lead.tags or '')

    def test_joint_au_troisieme_appel_ne_programme_aucun_reveil(self):
        self._fait(self.etapes[2], outcome='joint')
        self.assertEqual(self._reveils().count(), 0)

    def test_les_touches_restantes_sont_bien_ARRETEES_par_MRY9(self):
        """L'arrêt de la cadence, lui, reste le bon geste : on a joint la
        personne, les dix autres rappels n'ont plus lieu d'être."""
        self._fait(self.etapes[2], outcome='joint')
        restantes = self.lead.relance_etapes.filter(
            cadence='contact').exclude(pk=self.etapes[2].pk)
        self.assertEqual(restantes.count(), 10)
        self.assertEqual(
            {e.statut for e in restantes}, {RelanceEtape.Statut.SAUTEE})
        self.etapes[2].refresh_from_db()
        self.assertEqual(self.etapes[2].statut, RelanceEtape.Statut.FAIT)

    def test_la_DERNIERE_touche_sautee_sans_issue_cloture_toujours(self):
        """Non-régression du comportement voulu de MRY11 : quand la cadence
        s'épuise VRAIMENT, le lead part au parking avec son étiquette et ses
        deux réveils."""
        for etape in self.etapes[:-1]:
            marquer_etape_relance(
                etape, self.acteur, RelanceEtape.Statut.FAIT)
        derniere = self.etapes[-1]
        derniere.refresh_from_db()
        self.assertEqual(derniere.statut, RelanceEtape.Statut.A_FAIRE)
        marquer_etape_relance(
            derniere, self.acteur, RelanceEtape.Statut.SAUTEE)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.COLD)
        self.assertIn('Injoignable', self.lead.tags or '')
        self.assertEqual(self._reveils().count(), 2)
