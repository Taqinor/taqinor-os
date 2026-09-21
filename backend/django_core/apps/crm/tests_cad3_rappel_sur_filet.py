"""CAD3 — « À rappeler le… » sur une étape de FILET la REPORTE.

L'étape du filet « Préparer et envoyer le devis (ou fixer un rappel) » invite
elle-même à fixer un rappel, et l'écran promet « L'étape est déplacée à la
date choisie ». Le serveur, lui, la CLÔTURAIT : le filet reprenait la main,
la ceinture anti-tapis-roulant renommait la nouvelle étape « Décider la
suite — perdu (motif) ou relance ultérieure », puis la date choisie lui était
appliquée. La commerciale demandait un rappel et récupérait un arbitrage
perdu/relance — sur l'étape qu'elle voit le plus souvent, puisque
« rappelez-moi la semaine prochaine » est la réponse la plus fréquente avant
décision.

Ce module verrouille les trois faits du Done :

  * l'étape est toujours OUVERTE après le geste ;
  * elle est à la date choisie ;
  * ``FILET_REFUS_LIBELLE`` n'apparaît nulle part.

Plus deux garde-fous : un barreau de PROTOCOLE garde son comportement
d'avant (report de la touche SUIVANTE après clôture), et un filet clôturé
« à rappeler » SANS date — le seul cas où une nouvelle étape doit malgré tout
être posée — reçoit un libellé de rappel, jamais d'arbitrage.

Temps gelé : la date de rappel et les créneaux de la société sont exactement
ce qu'une horloge vivante rend instable.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, stages
from apps.crm.models import Lead, RelanceEtape
from apps.crm.services import (
    FILET_JOINT_LIBELLE, FILET_RAPPEL_LIBELLE, FILET_REFUS_LIBELLE,
    calculer_echeances_cadence)
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import CadenceRelanceEtape

User = get_user_model()

#: Lundi 21 septembre 2026, 10 h à Casablanca — jour ouvré, dans la fenêtre
#: d'appel : aucune échéance n'est repoussée par le recalage.
LUNDI = datetime.datetime(2026, 9, 21, 10, 0, tzinfo=horaires.CASABLANCA)

#: « Rappelez-moi lundi prochain » — un lundi lui aussi, donc jamais recalé
#: au lendemain par la règle du dimanche.
RAPPEL_JOUR = '2026-09-28'
RAPPEL_HEURE = '11:00'


class _Base(TestCase):
    slug = 'cad3'

    def setUp(self):
        gel = frozen(LUNDI)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = Company.objects.create(
            nom='CAD3 Solaire', slug=self.slug)
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-resp', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Aziz', stage=stages.CONTACTED,
            owner=self.acteur, telephone='+212661000301')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')

    def _filet(self, libelle=FILET_JOINT_LIBELLE):
        """L'étape que `assurer_prochaine_etape_apres_succes` aurait posée."""
        quand = LUNDI + datetime.timedelta(days=1)
        return RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='generique',
            ordre=1, canal=RelanceEtape.Canal.APPEL, libelle=libelle,
            due_at=quand,
            due_date=quand.astimezone(horaires.CASABLANCA).date(),
            note='Posée automatiquement : aucune autre relance ouverte.')

    def _rappeler(self, etape, jour=RAPPEL_JOUR, heure=RAPPEL_HEURE):
        corps = {'outcome': 'rappel'}
        if jour:
            corps['rappel_le'] = jour
        if heure:
            corps['rappel_heure'] = heure
        return self.api.post(
            f'/api/django/crm/relance-etapes/{etape.pk}/fait/', corps,
            format='json')

    def _libelles(self):
        return list(self.lead.relance_etapes.values_list('libelle', flat=True))


class RappelSurFiletTests(_Base):
    slug = 'cad3-filet'

    def test_l_etape_reste_ouverte_a_la_date_choisie(self):
        etape = self._filet()
        resp = self._rappeler(etape)
        self.assertEqual(resp.status_code, 200, resp.data)
        etape.refresh_from_db()
        self.assertEqual(etape.statut, RelanceEtape.Statut.A_FAIRE)
        self.assertEqual(
            etape.due_date, datetime.date.fromisoformat(RAPPEL_JOUR))

    def test_le_libelle_d_arbitrage_n_apparait_nulle_part(self):
        self._rappeler(self._filet())
        self.assertNotIn(FILET_REFUS_LIBELLE, self._libelles())

    def test_aucune_etape_n_est_ajoutee(self):
        etape = self._filet()
        self._rappeler(etape)
        # La touche est DÉPLACÉE, pas remplacée : une seule ligne, la même.
        self.assertEqual(self.lead.relance_etapes.count(), 1)
        self.assertEqual(self.lead.relance_etapes.first().pk, etape.pk)

    def test_le_lead_pointe_sur_la_date_choisie(self):
        self._rappeler(self._filet())
        self.lead.refresh_from_db()
        self.assertEqual(
            self.lead.relance_date, datetime.date.fromisoformat(RAPPEL_JOUR))

    def test_la_reponse_annonce_la_touche_deplacee(self):
        resp = self._rappeler(self._filet())
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(
            resp.data['prochaine_touche']['due_date'], RAPPEL_JOUR)

    def test_l_etape_de_decision_se_reporte_aussi(self):
        # Le filet « décider la suite » est lui aussi une étape de filet : un
        # rappel convenu dessus la déplace, il ne la consomme pas.
        etape = self._filet(libelle=FILET_REFUS_LIBELLE)
        self._rappeler(etape)
        etape.refresh_from_db()
        self.assertEqual(etape.statut, RelanceEtape.Statut.A_FAIRE)
        self.assertEqual(self.lead.relance_etapes.count(), 1)


class RappelSansDateTests(_Base):
    """Le seul cas où une nouvelle étape doit malgré tout être posée."""

    slug = 'cad3-sansdate'

    def test_sans_date_le_filet_pose_un_libelle_de_rappel(self):
        etape = self._filet()
        resp = self._rappeler(etape, jour='', heure='')
        self.assertEqual(resp.status_code, 200, resp.data)
        etape.refresh_from_db()
        self.assertEqual(etape.statut, RelanceEtape.Statut.FAIT)
        ouvertes = list(self.lead.relance_etapes.filter(
            statut=RelanceEtape.Statut.A_FAIRE))
        self.assertEqual(len(ouvertes), 1, [e.libelle for e in ouvertes])
        self.assertEqual(ouvertes[0].libelle, FILET_RAPPEL_LIBELLE)
        self.assertNotIn(FILET_REFUS_LIBELLE, self._libelles())


class BarreauDeProtocoleInchangeTests(_Base):
    """Garde-fou : sur un vrai barreau, « à rappeler » garde le comportement
    MRY10 — la touche est traitée et c'est la SUIVANTE qui se décale."""

    slug = 'cad3-protocole'

    def test_un_barreau_de_protocole_est_toujours_consomme(self):
        gabarits = CadenceRelanceEtape.cadence_pour(self.company, 'contact')
        echeances = calculer_echeances_cadence(
            self.lead, 'contact', LUNDI, gabarits=gabarits)
        gabarit, echeance = echeances[0]
        etape = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='contact',
            ordre=gabarit.ordre, due_at=echeance,
            due_date=echeance.astimezone(horaires.CASABLANCA).date(),
            canal=gabarit.canal, libelle=gabarit.libelle,
            template_cle=gabarit.template_cle or '', cadence_depart=LUNDI)
        resp = self._rappeler(etape)
        self.assertEqual(resp.status_code, 200, resp.data)
        etape.refresh_from_db()
        self.assertEqual(etape.statut, RelanceEtape.Statut.FAIT)
        # MRY10 inchangé : la touche SUIVANTE du protocole porte la date.
        ouvertes = list(self.lead.relance_etapes.filter(
            statut=RelanceEtape.Statut.A_FAIRE))
        self.assertEqual(len(ouvertes), 1, [e.libelle for e in ouvertes])
        self.assertEqual(
            ouvertes[0].due_date, datetime.date.fromisoformat(RAPPEL_JOUR))
