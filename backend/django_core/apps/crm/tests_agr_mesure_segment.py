"""AGR540 — mesure de cadence par segment (lecture seule) + commande de
comptage CADM7 par segment.

Contrat partagé : ``apps/crm/contract_samples/mesure_cadence.json``
(``exemple.par_segment`` / ``exemple_vide.par_segment``, AGR502).

Run :
    python manage.py test apps.crm.tests_agr_mesure_segment -v 2
"""
import datetime
import io
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, mesure_cadence, stages
from apps.crm.models import Client, Lead, LeadActivity, RelanceEtape
from apps.crm.services import TAG_ATTENTE_ACCORD
from apps.parametres.models import CompanyProfile
from apps.ventes.models import Devis

User = get_user_model()

MAINTENANT = datetime.datetime(2026, 9, 10, 12, 0, tzinfo=horaires.CASABLANCA)

CONTRAT = json.loads(
    (Path(__file__).resolve().parent / 'contract_samples'
     / 'mesure_cadence.json').read_text(encoding='utf-8'))


def _par_segment(lignes):
    return {ligne['segment']: ligne for ligne in lignes}


class _Base(TestCase):
    slug = 'agr540'

    def setUp(self):
        gel = frozen(MAINTENANT)
        gel.start()
        self.addCleanup(gel.stop)
        self.company, _ = Company.objects.get_or_create(
            slug=self.slug, defaults={'nom': self.slug})
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-resp', password='x',
            role_legacy='responsable', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', email=f'{self.slug}@ex.com')
        self._n = 0

    def _lead(self, nom, type_installation, company=None, **extra):
        return Lead.objects.create(
            company=company or self.company, nom=nom, owner=self.acteur,
            type_installation=type_installation, **extra)

    def _touche(self, lead, outcome, *, jours=2):
        instant = MAINTENANT - datetime.timedelta(days=jours)
        touche = RelanceEtape.objects.create(
            company=self.company, lead=lead, cadence='contact', ordre=1,
            due_at=instant, due_date=instant.date(),
            canal=RelanceEtape.Canal.APPEL, libelle='Appel', statut='fait',
            traite_le=instant, traite_par=self.acteur)
        if mesure_cadence._colonne_issue_disponible():
            setattr(touche, mesure_cadence.CHAMP_ISSUE, outcome)
            touche.save(update_fields=[mesure_cadence.CHAMP_ISSUE])
        activite = LeadActivity.objects.create(
            company=self.company, lead=lead, user=self.acteur,
            kind=LeadActivity.Kind.APPEL, body='Touche faite.',
            outcome=outcome)
        LeadActivity.objects.filter(pk=activite.pk).update(
            created_at=instant + datetime.timedelta(seconds=1))
        return touche

    def _devis(self, lead, mode, *, envoye_il_y_a=None):
        self._n += 1
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{self.slug}-{self._n}',
            client=self.client_obj, lead=lead, statut='brouillon',
            taux_tva=Decimal('20.00'), mode_installation=mode)
        if envoye_il_y_a is not None:
            Devis.objects.filter(pk=devis.pk).update(
                statut='envoye',
                date_envoi=MAINTENANT - datetime.timedelta(days=envoye_il_y_a))
        return devis


class ParSegmentTests(_Base):
    def test_a_deux_residentiels_et_un_agricole_comptes_justes(self):
        r1 = self._lead('R1', 'residentiel')
        r2 = self._lead('R2', 'residentiel', tags=TAG_ATTENTE_ACCORD)
        self._lead('A1', 'agricole', dossier_subvention='a_deposer')
        self._lead('S1', None)
        self._touche(r1, 'joint')
        self._touche(r2, 'non_joint')
        # Froid AU MOMENT DE LA MESURE : posé APRÈS la touche, car un client
        # joint sur un lead froid le réactive vers CONTACTED (receivers M1) —
        # posé avant, la touche « joint » l'aurait sorti du Froid.
        Lead.objects.filter(pk=r1.pk).update(stage=stages.COLD)
        self._devis(r2, 'residentiel', envoye_il_y_a=1)
        self._devis(r2, 'agricole')  # brouillon : compte l'incohérence
        LeadActivity.objects.create(
            company=self.company, lead=r2, user=self.acteur,
            kind=LeadActivity.Kind.MODIFICATION, field='stage',
            old_value=stages.STAGE_LABELS[stages.QUOTE_SENT],
            new_value=stages.STAGE_LABELS[stages.SIGNED])

        lignes = mesure_cadence.par_segment(self.company, jours=90)
        self.assertEqual([ligne['segment'] for ligne in lignes],
                         ['residentiel', 'commercial', 'industriel',
                          'agricole', 'non_renseigne'])
        seg = _par_segment(lignes)
        res = seg['residentiel']
        self.assertEqual(res['nb_leads'], 2)
        self.assertEqual(res['devis_envoyes'], 1)
        self.assertEqual(res['taux_froid_pct'], 50.0)
        self.assertEqual(res['taux_joint_pct'], 50.0)
        self.assertEqual(res['signatures'], 1)
        self.assertEqual(res['signatures_par_mois'],
                         [{'mois': '2026-09', 'signatures': 1}])
        self.assertEqual(res['delai_median_signature_jours'], 1.0)
        self.assertEqual(res['en_attente_accord'], 1)
        self.assertEqual(res['incoherents'], 1)
        self.assertEqual(seg['agricole']['nb_leads'], 1)
        self.assertEqual(seg['agricole']['dossiers_subvention'],
                         {'a_deposer': 1})
        self.assertEqual(seg['agricole']['incoherents'], 0)
        self.assertEqual(seg['non_renseigne']['nb_leads'], 1)
        self.assertEqual(seg['commercial']['nb_leads'], 0)

    def test_b_segment_sans_touche_close_taux_joint_null(self):
        self._lead('A1', 'agricole')
        seg = _par_segment(mesure_cadence.par_segment(self.company))
        self.assertIsNone(seg['agricole']['taux_joint_pct'])
        self.assertEqual(seg['agricole']['taux_froid_pct'], 0.0)
        self.assertIsNone(seg['commercial']['taux_froid_pct'])
        self.assertIsNone(seg['agricole']['delai_median_premier_devis_jours'])

    def test_c_lead_d_une_autre_societe_exclu(self):
        autre, _ = Company.objects.get_or_create(
            slug='agr540-autre', defaults={'nom': 'agr540-autre'})
        self._lead('Autre', 'agricole', company=autre)
        seg = _par_segment(mesure_cadence.par_segment(self.company))
        self.assertEqual(seg['agricole']['nb_leads'], 0)

    def test_forme_conforme_au_contrat(self):
        self._lead('R1', 'residentiel')
        attendu = CONTRAT['exemple']['par_segment'][0]
        for ligne in mesure_cadence.par_segment(self.company):
            self.assertEqual(set(ligne), set(attendu), ligne['segment'])
        self.assertIn('par_segment', mesure_cadence.mesure_cadence(
            self.company))

    def test_vide_egale_l_exemple_vide_du_contrat(self):
        self.assertEqual(mesure_cadence.par_segment(self.company),
                         CONTRAT['exemple_vide']['par_segment'])


class CommandeLectureSeuleTests(_Base):
    slug = 'agr540-cmd'

    def _compter(self):
        return (Lead.objects.count(), LeadActivity.objects.count(),
                RelanceEtape.objects.count(), Devis.objects.count())

    def test_d_la_commande_n_ecrit_aucune_ligne(self):
        lead = self._lead('R1', 'residentiel')
        self._touche(lead, 'joint')
        avant = self._compter()
        sortie = io.StringIO()
        call_command('mesurer_par_segment', self.slug, '--jours', '30',
                     stdout=sortie)
        self.assertEqual(self._compter(), avant)
        document = json.loads(sortie.getvalue())
        self.assertEqual(document['jours'], 30)
        self.assertEqual(
            _par_segment(document['par_segment'])['residentiel']['nb_leads'],
            1)
