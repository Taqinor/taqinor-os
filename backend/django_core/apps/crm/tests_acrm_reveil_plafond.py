"""ACRM18 — ``poser_reveils_saisonniers`` sert CHAQUE dormant éligible une
fois par saison : les refus durables (déjà servi cette année, touche
ouverte, opposé) sont filtrés DANS la requête avant la troncature — 205
dormants sont servis en deux passages (200 puis 5 puis 0) — rejoue la sonde
LSVC4-2.

Test-du-test : remettre la troncature avant le filtre ⇒ 200 / 0 / 0.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.crm import horaires, stages
from apps.crm.cadence_reveil_saison import (
    REVEIL_SAISON_CLE, poser_reveils_saisonniers,
)
from apps.crm.mesure_cadence import lot_reactivation, trace_reactivation
from apps.crm.models import Lead, LeadActivity, RelanceEtape
from apps.parametres.models import CompanyProfile
from apps.roles.models import Role

# Un mercredi : la semaine passée va du lundi 6 au dimanche 12 juillet.
EN_SAISON = datetime.datetime(2026, 7, 15, 10, 0, tzinfo=horaires.CASABLANCA)
JEUDI_PASSE = datetime.datetime(2026, 7, 9, 12, 0, tzinfo=horaires.CASABLANCA)
STOP = {'kind': LeadActivity.Kind.MODIFICATION, 'field': 'ne_plus_contacter',
        'new_value': 'Oui'}
JOINT = {'kind': LeadActivity.Kind.APPEL, 'outcome': 'joint'}


class ReveilPlafondTests(TestCase):

    def setUp(self):
        from testkit.time import frozen
        gel = frozen(EN_SAISON)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = Company.objects.create(
            nom='ACRM18 Solaire', slug='acrm18-plafond')
        CompanyProfile.objects.create(company=self.company)
        Lead.objects.bulk_create([
            Lead(company=self.company, nom=f'Dormant {i}', stage=stages.COLD)
            for i in range(205)])

    def test_population_superieure_au_plafond(self):
        servis = [len(poser_reveils_saisonniers(
            self.company, maintenant=EN_SAISON, limite=200))
            for _ in range(3)]
        self.assertEqual(servis, [200, 5, 0])
        sans_touche = (Lead.objects.filter(company=self.company,
                                           stage=stages.COLD)
                       .exclude(relance_etapes__template_cle=REVEIL_SAISON_CLE)
                       .count())
        self.assertEqual(sans_touche, 0)
        self.assertEqual(RelanceEtape.objects.filter(
            company=self.company, template_cle=REVEIL_SAISON_CLE).count(),
            205)

    def _touches_de_la_semaine_passee(self, a_l_heure, en_retard):
        porteur = Lead.objects.filter(company=self.company).first()
        RelanceEtape.objects.bulk_create([
            RelanceEtape(
                company=self.company, lead=porteur, cadence='contact', ordre=rang,
                canal='appel', statut=RelanceEtape.Statut.FAIT, traite_le=JEUDI_PASSE,
                due_date=JEUDI_PASSE.date() - datetime.timedelta(
                    days=0 if rang < a_l_heure else 1))
            for rang in range(a_l_heure + en_retard)])

    def _premier_contact_en(self, minutes):
        cree = JEUDI_PASSE - datetime.timedelta(hours=2)
        lead = Lead.objects.bulk_create([Lead(
            company=self.company, nom='Rappelé', stage=stages.CONTACTED,
            first_contacted_at=cree + datetime.timedelta(minutes=minutes))])[0]
        Lead.objects.filter(pk=lead.pk).update(date_creation=cree)
        return lead

    def _chatter(self, leads, **champs):
        return LeadActivity.objects.bulk_create([
            LeadActivity(company=self.company, lead=lead, **champs) for lead in leads])

    def test_lot_hebdo_borne_par_la_marge_et_nul_sous_les_regles_d_arret(self):
        """CADV106. Mutant : retirer la borne 40 ⇒ le lot vaut 74 et échoue."""
        role = Role.objects.create(company=self.company, nom='Commercial', permissions=[])
        commerciaux = [get_user_model().objects.create_user(
            username=f'cadv106-{i}', password='x', company=self.company, role=role)
            for i in range(2)]
        # 150 touches faites (224 - 150 = 74), 140 à l'heure (93,3 %), médiane 4 min.
        self._touches_de_la_semaine_passee(140, 10)
        rappele = self._premier_contact_en(4)
        dormants = list(Lead.objects.filter(company=self.company, stage=stages.COLD))
        self._chatter(dormants[:20], kind=LeadActivity.Kind.NOTE,
                      body=trace_reactivation('k6_p1'))
        self._chatter(dormants[:1], **STOP)

        ouvert = {'taille': 40, 'motif_arret': None}
        self.assertEqual(lot_reactivation(self.company, EN_SAISON), ouvert)
        self.assertEqual(lot_reactivation(self.company, EN_SAISON), ouvert)

        # La marge manque : un seul commercial actif, 112 - 150 < 0.
        get_user_model().objects.filter(pk=commerciaux[1].pk).update(is_active=False)
        self.assertEqual(lot_reactivation(self.company, EN_SAISON),
                         {'taille': 0, 'motif_arret': 'marge_nulle'})
        get_user_model().objects.filter(pk=commerciaux[1].pk).update(is_active=True)

        # Un lead neuf attend depuis 30 minutes ouvrées.
        neuf = Lead.objects.bulk_create([Lead(
            company=self.company, nom='Neuf', stage=stages.NEW)])[0]
        Lead.objects.filter(pk=neuf.pk).update(
            date_creation=EN_SAISON - datetime.timedelta(minutes=30))
        self.assertEqual(lot_reactivation(self.company, EN_SAISON),
                         {'taille': 0, 'motif_arret': 'lead_neuf_sans_prise'})
        Lead.objects.filter(pk=neuf.pk).update(first_contacted_at=EN_SAISON)
        self.assertEqual(lot_reactivation(self.company, EN_SAISON), ouvert)

        # Le premier contact rate sa cible (5 minutes) : 6 minutes.
        Lead.objects.filter(pk=rappele.pk).update(
            first_contacted_at=JEUDI_PASSE - datetime.timedelta(minutes=114))
        self.assertEqual(lot_reactivation(self.company, EN_SAISON),
                         {'taille': 0, 'motif_arret': 'premier_contact'})
        Lead.objects.filter(pk=rappele.pk).update(
            first_contacted_at=JEUDI_PASSE - datetime.timedelta(minutes=116))

        # Deuxième réponse hostile sur les 20 derniers messages.
        self._chatter(dormants[1:2], **STOP)
        self.assertEqual(lot_reactivation(self.company, EN_SAISON),
                         {'taille': 0, 'motif_arret': 'reponses_hostiles'})

        # Ponctualité 80 % : le 90 % n'est plus tenu, et ce motif passe en tête.
        RelanceEtape.objects.filter(
            company=self.company, cadence='contact', ordre__lt=20,
        ).update(due_date=JEUDI_PASSE.date() - datetime.timedelta(days=1))
        self.assertEqual(lot_reactivation(self.company, EN_SAISON),
                         {'taille': 0, 'motif_arret': 'ponctualite'})

    def test_le_palier_2_s_arrete_pour_de_bon_sous_2_reponses_sur_100(self):
        """CADV106 (D-CADV-11) — 100 messages et 1 réponse : arrêté ; une seconde
        réponse le rouvre. Les autres seaux ne sont pas concernés par cet arrêt."""
        dormants = list(Lead.objects.filter(company=self.company, stage=stages.COLD)[:100])
        self._chatter(dormants, kind=LeadActivity.Kind.NOTE,
                      body=trace_reactivation('k6_p2'))
        self._chatter(dormants[:1], **JOINT)
        arrete = {'taille': 0, 'motif_arret': 'palier_2_arrete'}
        self.assertEqual(lot_reactivation(self.company, EN_SAISON, seau='k6_p2'), arrete)
        # Sans commercial : aucune marge, mais pas l'arrêt du palier 2.
        self.assertEqual(lot_reactivation(self.company, EN_SAISON),
                         {'taille': 0, 'motif_arret': 'marge_nulle'})
        self._chatter(dormants[1:2], **JOINT)
        self.assertEqual(lot_reactivation(self.company, EN_SAISON, seau='k6_p2'),
                         {'taille': 0, 'motif_arret': 'marge_nulle'})
