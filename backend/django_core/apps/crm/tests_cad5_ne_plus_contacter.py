"""CAD5 — la réponse « Ne plus me contacter » sur toutes les cadences.

Avant : aucune réponse de touche ne disait « arrêtez ». La commerciale
cliquait « Refus » — qui posait une étape « Décider la suite » et laissait la
porte ouverte à une relance — puis devait quitter l'écran pour cocher « Ne
plus contacter » sur la fiche. Or c'est le SEUL risque pénal nommé de la
cadence (loi 09-08 art. 9 al. 2 et art. 59) : l'opposition doit agir au
moment où elle est dite.

Ce module verrouille le Done de la tâche :

  * ``ne_plus_contacter=True`` sur le lead ;
  * la cadence est arrêtée et AUCUNE étape ne reste ouverte (pas d'étape de
    décision « perdu ou relance ultérieure ») ;
  * un redémarrage ultérieur est refusé en 400 ;
  * la réponse vaut sur TOUTES les cadences ;
  * contrat partagé : la réponse du « Fait » porte exactement les clés de
    l'exemple committé ``contract_samples/relance_etape_v2.json`` (plus
    ``prochaine_touche``), et le texte d'accusé proposé
    (``?cle=stop_contact``) a la forme committée de
    ``contract_samples/relance_etape_message.json``.

Temps gelé : les échéances et les créneaux de la société sont exactement ce
qu'une horloge vivante rend instable.
"""
import datetime
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, stages
from apps.crm.models import Lead, LeadActivity, RelanceEtape
from apps.crm.services import (
    FILET_REFUS_LIBELLE, MOTIF_NE_PLUS_CONTACTER, annuler_touche_relance,
    AnnulationToucheRefusee)
from apps.parametres.models import CompanyProfile

User = get_user_model()

#: Mercredi 23 septembre 2026, 10 h à Casablanca — jour ouvré, fenêtre ouverte.
MERCREDI = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)

CONTRATS = Path(__file__).resolve().parent / 'contract_samples'


def _contrat(nom):
    return json.loads((CONTRATS / f'{nom}.json').read_text(encoding='utf-8'))


class _Base(TestCase):
    slug = 'cad5'

    def setUp(self):
        gel = frozen(MERCREDI)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = Company.objects.create(
            nom='CAD5 Solaire', slug=self.slug)
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-resp', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Aziz', prenom='Benali',
            stage=stages.CONTACTED, owner=self.acteur,
            telephone='+212661000501', whatsapp='+212661000501')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')

    def _touche(self, *, cadence='contact', canal=RelanceEtape.Canal.APPEL,
                ordre=4, libelle='Appel 3', jours=0):
        quand = MERCREDI + datetime.timedelta(days=jours, hours=1)
        return RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence=cadence,
            ordre=ordre, canal=canal, libelle=libelle, due_at=quand,
            due_date=quand.astimezone(horaires.CASABLANCA).date(),
            cadence_depart=MERCREDI - datetime.timedelta(days=1))

    def _repondre(self, etape, **corps):
        return self.api.post(
            f'/api/django/crm/relance-etapes/{etape.pk}/fait/',
            {'reponse': 'ne_plus_contacter', **corps}, format='json')

    def _ouvertes(self):
        return list(self.lead.relance_etapes.filter(
            statut=RelanceEtape.Statut.A_FAIRE))


class NePlusContacterTests(_Base):
    slug = 'cad5-base'

    def test_le_lead_est_coche_et_la_cadence_arretee(self):
        etape = self._touche()
        # Une AUTRE touche encore ouverte (visite, filet…) : elle aussi part.
        autre = self._touche(cadence='generique', ordre=1,
                             libelle='Autre étape', jours=2)
        resp = self._repondre(etape)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.lead.refresh_from_db()
        self.assertTrue(self.lead.ne_plus_contacter)
        etape.refresh_from_db()
        self.assertEqual(etape.statut, RelanceEtape.Statut.FAIT)
        self.assertEqual(etape.outcome, 'refuse')
        autre.refresh_from_db()
        self.assertEqual(autre.statut, RelanceEtape.Statut.ANNULEE)
        self.assertEqual(autre.note, MOTIF_NE_PLUS_CONTACTER)
        self.assertEqual(self._ouvertes(), [])
        self.assertIsNone(self.lead.relance_date)

    def test_aucune_etape_de_decision_n_est_posee(self):
        self._repondre(self._touche())
        libelles = set(self.lead.relance_etapes.values_list(
            'libelle', flat=True))
        self.assertNotIn(FILET_REFUS_LIBELLE, libelles)
        self.assertEqual(self._ouvertes(), [])

    def test_la_note_typee_est_sur_la_ligne_de_la_touche(self):
        self._repondre(self._touche(), note='Très ferme au téléphone')
        ligne = (LeadActivity.objects
                 .filter(lead=self.lead, kind=LeadActivity.Kind.APPEL)
                 .latest('created_at'))
        self.assertEqual(ligne.outcome, 'refuse')
        self.assertIn('Ne plus me contacter', ligne.body)
        self.assertIn('Très ferme au téléphone', ligne.body)

    def test_la_case_est_journalisee_comme_sur_la_fiche(self):
        self._repondre(self._touche())
        self.assertTrue(LeadActivity.objects.filter(
            lead=self.lead, kind=LeadActivity.Kind.MODIFICATION,
            field='ne_plus_contacter').exists())

    def test_un_redemarrage_ulterieur_est_refuse(self):
        self._repondre(self._touche())
        resp = self.api.post(
            f'/api/django/crm/leads/{self.lead.pk}/relance/initialiser/',
            {'cadence': 'contact'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual(self._ouvertes(), [])

    def test_l_annulation_de_la_touche_est_refusee(self):
        etape = self._touche()
        self._repondre(etape)
        etape.refresh_from_db()
        with self.assertRaises(AnnulationToucheRefusee) as ctx:
            annuler_touche_relance(etape, self.acteur)
        self.assertEqual(ctx.exception.champ, 'lead')
        self.assertEqual(self._ouvertes(), [])


class ToutesCadencesTests(_Base):
    """« sur toutes les cadences » : prise de contact, suivi de proposition,
    réveil et étape générique (filet)."""

    slug = 'cad5-cadences'

    def test_chaque_cadence_accepte_la_reponse(self):
        for cadence, canal in (
                ('contact', RelanceEtape.Canal.APPEL),
                ('apres_devis', RelanceEtape.Canal.WHATSAPP),
                ('reveil', RelanceEtape.Canal.APPEL),
                ('generique', RelanceEtape.Canal.APPEL)):
            with self.subTest(cadence=cadence):
                Lead.objects.filter(pk=self.lead.pk).update(
                    ne_plus_contacter=False)
                self.lead.refresh_from_db()
                etape = self._touche(cadence=cadence, canal=canal)
                resp = self._repondre(etape)
                self.assertEqual(resp.status_code, 200, resp.data)
                self.lead.refresh_from_db()
                self.assertTrue(self.lead.ne_plus_contacter)
                self.assertEqual(self._ouvertes(), [])


class RefusNommeTests(_Base):
    slug = 'cad5-refus'

    def test_une_reponse_inconnue_nomme_le_champ(self):
        resp = self.api.post(
            f'/api/django/crm/relance-etapes/{self._touche().pk}/fait/',
            {'reponse': 'arretez'}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('reponse', resp.data['erreurs'])
        self.assertIn('arretez', resp.data['erreurs']['reponse'])

    def test_une_touche_deja_traitee_est_refusee(self):
        etape = self._touche()
        RelanceEtape.objects.filter(pk=etape.pk).update(
            statut=RelanceEtape.Statut.FAIT)
        resp = self._repondre(etape)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('reponse', resp.data['erreurs'])
        self.lead.refresh_from_db()
        self.assertFalse(self.lead.ne_plus_contacter)


class ContratPartageTests(_Base):
    slug = 'cad5-contrat'

    def test_la_reponse_du_fait_a_la_forme_du_contrat(self):
        resp = self._repondre(self._touche())
        self.assertEqual(resp.status_code, 200, resp.data)
        attendu = set(_contrat('relance_etape_v2')['exemple']['results'][0])
        self.assertEqual(set(resp.data) - {'prochaine_touche'}, attendu)
        self.assertIsNone(resp.data['prochaine_touche'])

    def test_l_accuse_stop_contact_est_propose_a_la_forme_du_contrat(self):
        etape = self._touche()
        self._repondre(etape)
        resp = self.api.get(
            f'/api/django/crm/relance-etapes/{etape.pk}/message/',
            {'cle': 'stop_contact'})
        self.assertEqual(resp.status_code, 200, resp.data)
        attendu = set(_contrat('relance_etape_message')['exemple'])
        self.assertEqual(set(resp.data), attendu)
        self.assertIn('je ne vous rappellerai plus', resp.data['message'])
        self.assertTrue(resp.data['wa_url'])

    def test_un_texte_de_reponse_inconnu_nomme_le_champ(self):
        resp = self.api.get(
            f'/api/django/crm/relance-etapes/{self._touche().pk}/message/',
            {'cle': 'offre_reda'})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('cle', resp.data['erreurs'])
