"""SUIVI E1 — une étape de VISITE ouverte n'empêche plus le suivi de
proposition de démarrer.

SUIVI-PARCOURS 30/09/2026 (constat prouvé : « after the call script it does
block »). Les quatre gestes de visite (planifier, confirmer, débrief, devis
modifié) portent la cadence ``apres_devis`` sans être des barreaux du
protocole. Trois lectures les prenaient pour « un suivi déjà en cours » :

* le récepteur de ``devis_sent`` (``.exclude(devis_id=X)`` garde les lignes à
  devis NULL) écrivait « Cadence après devis déjà en cours pour ? » et le
  devis partait SANS aucun suivi ;
* l'idempotence de ``initialiser_plan_relance`` rendait l'étape de visite
  comme « plan ouvert » ;
* le ``exists()`` de ``LeadViewSet.initialiser_relance``.

Décision : seuls les BARREAUX comptent. Et à l'envoi d'un devis, l'étape
« Préparer le devis modifié » encore ouverte est ANNULÉE (statut moteur,
note « devis envoyé ») : elle a rempli son office. Les autres gestes de
visite (planifier / confirmer / débrief) RESTENT ouverts.

Horloge FIXE : mercredi 23/09/2026, 10 h à Casablanca.
"""
import datetime
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from core.events import devis_sent
from testkit.time import frozen

from apps.crm import horaires, services, stages
from apps.crm import cadence_plan
from apps.crm import cadence_reperes
from apps.crm import cadence_reponses
from apps.crm.cadence_config import (
    CLE_CONFIRMATION, CLE_DEBRIEF, CLE_DEVIS_MODIFIE, CLE_PLANIFIER, q_etape)
from apps.crm.models import Client, Lead, LeadActivity, RelanceEtape
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import CADENCES_DEFAUT, CadenceRelanceEtape
from apps.ventes.models import Devis

User = get_user_model()

GEL = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)
#: Lundi 28/09 : le rendez-vous de visite.
VISITE_LE = datetime.date(2026, 9, 28)
A_FAIRE = RelanceEtape.Statut.A_FAIRE
ANNULEE = RelanceEtape.Statut.ANNULEE

_seq = itertools.count(1)


class _Base(TestCase):

    def setUp(self):
        gel = frozen(GEL)
        gel.start()
        self.addCleanup(gel.stop)
        n = next(_seq)
        self.company = Company.objects.create(
            nom=f'Suivi E1 {n}', slug=f'suivi-e1-{n}')
        CompanyProfile.objects.get_or_create(company=self.company)
        for cadence in CADENCES_DEFAUT:
            CadenceRelanceEtape.cadence_pour(self.company, cadence)
        self.acteur = User.objects.create_user(
            username=f'suivi-e1-resp-{n}', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')
        self.lead = Lead.objects.create(
            company=self.company, nom=f'Prospect E1 {n}',
            stage=stages.CONTACTED, owner=self.acteur,
            telephone=f'+21266110{n:04d}')

    def _devis(self, *, date_envoi=GEL):
        n = next(_seq)
        client = Client.objects.create(
            company=self.company, nom=f'Client E1 {n}',
            email=f'suivi-e1-{n}@example.com')
        return Devis.objects.create(
            company=self.company, reference=f'DEV-E1-{n:05d}', client=client,
            lead=self.lead, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20.00'), date_envoi=date_envoi)

    def _envoyer(self, devis):
        devis_sent.send(sender='test', devis=devis, user=self.acteur,
                        ancien_statut='brouillon')

    def _touche(self, **champs):
        valeurs = dict(company=self.company, lead=self.lead, due_at=GEL,
                       due_date=GEL.date())
        valeurs.update(champs)
        return RelanceEtape.objects.create(**valeurs)

    def _ouvertes(self, *q, **filtres):
        return self.lead.relance_etapes.filter(*q, statut=A_FAIRE, **filtres)

    def _barreau_1_ouvert(self, devis):
        barreaux = self._ouvertes(cadence='apres_devis', ordre=1, devis=devis)
        self.assertEqual(barreaux.count(), 1, list(
            self._ouvertes().values_list('cadence', 'ordre', 'libelle')))
        return barreaux.get()

    def _aucun_refus_deja_en_cours(self):
        self.assertFalse(self.lead.activites.filter(
            body__startswith='Cadence après devis déjà en cours').exists())


class DevisEnvoyeAvecVisiteOuverteTests(_Base):

    def test_visite_acceptee_au_telephone_puis_devis_envoye(self):
        # L'appel de prise de contact : « Visite acceptée », date pas encore
        # fixée → l'étape « Planifier la visite » est posée.
        appel = self._touche(cadence='contact', ordre=2,
                             canal=RelanceEtape.Canal.APPEL,
                             libelle="Appel d'ouverture", cadence_depart=GEL)
        resp = self.api.post(
            f'/api/django/crm/relance-etapes/{appel.pk}/fait/',
            {'outcome': cadence_reperes.OUTCOME_VISITE_ACCEPTEE}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        planifier = self._ouvertes(q_etape(CLE_PLANIFIER)).get()

        devis = self._devis()
        self._envoyer(devis)

        barreau = self._barreau_1_ouvert(devis)
        # Daté de l'ENVOI, jamais de « maintenant ».
        self.assertEqual(barreau.cadence_depart, devis.date_envoi)
        planifier.refresh_from_db()
        self.assertEqual(planifier.statut, A_FAIRE)
        self._aucun_refus_deja_en_cours()

    def test_confirmation_et_debrief_ouverts(self):
        services.appliquer_visite_planifiee(self.lead, self.acteur, VISITE_LE)
        confirmation = self._ouvertes(q_etape(CLE_CONFIRMATION)).get()
        debrief = self._ouvertes(q_etape(CLE_DEBRIEF)).get()

        devis = self._devis()
        self._envoyer(devis)

        self._barreau_1_ouvert(devis)
        for etape in (confirmation, debrief):
            etape.refresh_from_db()
            self.assertEqual(etape.statut, A_FAIRE)
        self._aucun_refus_deja_en_cours()

    def test_devis_modifie_puis_nouveau_devis_envoye(self):
        self.lead.stage = stages.QUOTE_SENT
        self.lead.save(update_fields=['stage'])
        ancien = self._devis(date_envoi=GEL - datetime.timedelta(days=7))
        suivi = self._touche(cadence='apres_devis', ordre=2,
                             canal=RelanceEtape.Canal.APPEL,
                             libelle='Appel de suivi', devis=ancien,
                             cadence_depart=GEL - datetime.timedelta(days=7))
        resp = self.api.post(
            f'/api/django/crm/relance-etapes/{suivi.pk}/fait/',
            {'reponse': cadence_reponses.REPONSE_DEVIS_MODIFIE}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        modifie = self._ouvertes(q_etape(CLE_DEVIS_MODIFIE)).get()

        nouveau = self._devis()
        self._envoyer(nouveau)

        modifie.refresh_from_db()
        self.assertEqual(modifie.statut, ANNULEE)
        self.assertEqual(modifie.note, 'devis envoyé')
        self.assertIsNone(modifie.traite_par)
        self._barreau_1_ouvert(nouveau)
        self.assertFalse(self._ouvertes(cadence='apres_devis',
                                        devis=ancien).exists())
        self._aucun_refus_deja_en_cours()

    def test_relance_date_ne_pointe_jamais_sur_l_etape_annulee(self):
        """SUIVI I6 (écart confirmé sur E1) — l'étape « devis modifié »
        annulée à l'envoi était la plus proche (aujourd'hui) : ``relance_date``
        suit la plus proche touche RESTANTE, jamais la date d'une étape
        annulée."""
        self.lead.stage = stages.QUOTE_SENT
        self.lead.save(update_fields=['stage'])
        modifie = self._touche(cadence='apres_devis',
                               ordre=cadence_reperes.VISITE_ORDRE_DEBRIEF,
                               canal=RelanceEtape.Canal.APPEL,
                               cle=CLE_DEVIS_MODIFIE,
                               libelle=cadence_reperes.VISITE_DEVIS_LIBELLE)
        cadence_plan._recaler_file(self.lead, self.acteur)
        self.lead.refresh_from_db(fields=['relance_date'])
        self.assertEqual(self.lead.relance_date, GEL.date())

        nouveau = self._devis()
        self._envoyer(nouveau)

        modifie.refresh_from_db()
        self.assertEqual(modifie.statut, ANNULEE)
        barreau = self._barreau_1_ouvert(nouveau)
        proche = cadence_plan._prochaine_touche_a_faire(self.lead)
        self.assertEqual(proche.pk, barreau.pk)
        self.lead.refresh_from_db(fields=['relance_date'])
        self.assertEqual(self.lead.relance_date, proche.due_date)

    def test_un_vrai_suivi_en_cours_bloque_toujours_une_seconde_serie(self):
        """Témoin : la garde « une seule série après devis » tient pour un
        vrai BARREAU d'un autre devis (MRY7 inchangé)."""
        premier = self._devis(date_envoi=GEL - datetime.timedelta(days=2))
        self._touche(cadence='apres_devis', ordre=2,
                     canal=RelanceEtape.Canal.APPEL, libelle='Appel de suivi',
                     devis=premier,
                     cadence_depart=GEL - datetime.timedelta(days=2))
        second = self._devis()
        self._envoyer(second)
        self.assertFalse(self.lead.relance_etapes.filter(
            devis=second).exists())
        self.assertTrue(self.lead.activites.filter(
            body__startswith='Cadence après devis déjà en cours').exists())


class InitialisationAvecVisiteOuverteTests(_Base):

    def test_le_service_ne_rend_jamais_l_etape_de_visite(self):
        planifier = services.poser_filet_visite_a_planifier(
            self.lead, self.acteur)
        etapes = cadence_plan.initialiser_plan_relance(
            self.lead, self.acteur, cadence='apres_devis', depart=GEL)
        self.assertTrue(etapes)
        self.assertNotIn(planifier.pk, [e.pk for e in etapes])
        self.assertTrue(all(e.ordre < cadence_reperes.VISITE_ORDRE_CONFIRMATION
                            for e in etapes))

    def test_la_fiche_demarre_le_suivi_du_devis_envoye(self):
        planifier = services.poser_filet_visite_a_planifier(
            self.lead, self.acteur)
        devis = self._devis()
        resp = self.api.post(
            f'/api/django/crm/leads/{self.lead.pk}/relance/initialiser/',
            {'cadence': 'apres_devis'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn((1, devis.pk),
                      [(ligne['ordre'], ligne['devis']) for ligne in resp.data])
        self.assertNotIn(planifier.pk, [ligne['id'] for ligne in resp.data])
        planifier.refresh_from_db()
        self.assertEqual(planifier.statut, A_FAIRE)
        # La note d'initialisation du plan est bien écrite : rien n'a bloqué.
        self.assertTrue(LeadActivity.objects.filter(
            lead=self.lead,
            body__startswith='Plan de relance initialisé — cadence '
                             '« apres_devis »').exists())
