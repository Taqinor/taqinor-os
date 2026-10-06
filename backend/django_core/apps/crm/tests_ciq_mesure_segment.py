"""CIQ518 — mesure par segment : ce que le C&I ajoute.

Cinq clés de plus par entrée de ``par_segment`` (contrat CIQ10,
``mesure_cadence.json``) : ``attente_accord_par_raison`` (étiquettes de
CIQ508), ``touches_converties`` (la MÊME fonction pure que CIQ505),
``joints_par_creneau`` (des comptes, aucun %), ``delais_signature_jours`` (liste
triée) et ``incoherents`` élargi aux devis commerciaux/industriels portés par
un lead d'un autre type. Lecture seule, bornée à la société ; ``null`` quand
rien n'a été tenté.

Le temps est GELÉ.
"""
import datetime
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, mesure_cadence, stages
from apps.crm.models import Client, Lead, LeadActivity, RelanceEtape
from apps.crm.services import RAISONS_ATTENTE
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import CadenceRelanceEtape
from apps.ventes.models import Devis

User = get_user_model()

MAINTENANT = datetime.datetime(2026, 9, 10, 12, 0, tzinfo=horaires.CASABLANCA)
FIXE = '+212522334455'
MOBILE = '+212661000518'

CONTRAT = json.loads(
    (Path(__file__).resolve().parent / 'contract_samples'
     / 'mesure_cadence.json').read_text(encoding='utf-8'))
CLES_CIQ518 = ('attente_accord_par_raison', 'touches_converties',
               'joints_par_creneau', 'delais_signature_jours')


def _par_segment(lignes):
    return {ligne['segment']: ligne for ligne in lignes}


class _Base(TestCase):
    slug = 'ciq518'

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

    def _lead(self, nom, segment, company=None, **extra):
        return Lead.objects.create(
            company=company or self.company, nom=nom, owner=self.acteur,
            type_installation=segment, **extra)

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

    def _touche_close(self, lead, outcome, *, jours=2, heure=12, ordre=1):
        instant = (MAINTENANT - datetime.timedelta(days=jours)).replace(
            hour=heure, minute=0)
        touche = RelanceEtape.objects.create(
            company=self.company, lead=lead, cadence='contact', ordre=ordre,
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

    def _signer(self, lead):
        LeadActivity.objects.create(
            company=self.company, lead=lead, user=self.acteur,
            kind=LeadActivity.Kind.MODIFICATION, field='stage',
            old_value=stages.STAGE_LABELS[stages.QUOTE_SENT],
            new_value=stages.STAGE_LABELS[stages.SIGNED])

    def _mesure(self):
        return _par_segment(mesure_cadence.par_segment(self.company))


class ComptesParSegmentTests(_Base):
    def test_a_raisons_d_attente_comptes_et_seaux_separes(self):
        self._lead('C1', 'commercial', tags='Attend la direction / le comité')
        self._lead('C2', 'commercial',
                   tags="Attend la banque / l'organisme de financement")
        self._lead('I1', 'industriel',
                   tags="Attend la banque / l'organisme de financement")
        seg = self._mesure()
        commercial = seg['commercial']['attente_accord_par_raison']
        self.assertEqual(commercial['direction'], 1)
        self.assertEqual(commercial['financement'], 1)
        self.assertEqual(commercial['bailleur_murs'], 0)
        self.assertEqual(
            seg['industriel']['attente_accord_par_raison']['financement'], 1)
        self.assertEqual(
            seg['industriel']['attente_accord_par_raison']['direction'], 0)
        self.assertEqual(seg['residentiel']['attente_accord_par_raison'],
                         {r[0]: 0 for r in RAISONS_ATTENTE})

    def test_a_joints_par_creneau_et_delais_de_signature(self):
        c1 = self._lead('C1', 'commercial')
        c2 = self._lead('C2', 'commercial')
        self._touche_close(c1, 'joint', jours=3, heure=9)
        self._touche_close(c2, 'joint', jours=2, heure=15)
        self._touche_close(c2, 'non_joint', jours=1, heure=19, ordre=2)
        self._devis(c1, 'commercial', envoye_il_y_a=5)
        self._devis(c2, 'commercial', envoye_il_y_a=3)
        self._signer(c1)
        self._signer(c2)
        ligne = self._mesure()['commercial']
        self.assertEqual(ligne['joints_par_creneau'],
                         {'matin': 1, 'midi': 0, 'apres_midi': 1, 'soir': 0})
        # Aucun pourcentage : des comptes entiers.
        for valeur in ligne['joints_par_creneau'].values():
            self.assertIsInstance(valeur, int)
        self.assertEqual(ligne['delais_signature_jours'], [3.0, 5.0])

    def test_e_un_lead_d_une_autre_societe_est_exclu(self):
        autre, _ = Company.objects.get_or_create(
            slug='ciq518-autre', defaults={'nom': 'ciq518-autre'})
        self._lead('Autre', 'commercial', company=autre,
                   tags='Attend la direction / le comité')
        seg = self._mesure()
        self.assertEqual(seg['commercial']['nb_leads'], 0)
        self.assertEqual(
            seg['commercial']['attente_accord_par_raison']['direction'], 0)


class ToucheConvertieTests(_Base):
    slug = 'ciq518-conv'

    def setUp(self):
        super().setUp()
        # Le protocole de la société (seedé à la volée).
        CadenceRelanceEtape.cadence_pour(self.company, 'apres_devis')

    def _touche_email(self, lead, canal='email', ordre=1, cle='j1_pdf'):
        return RelanceEtape.objects.create(
            company=self.company, lead=lead, cadence='apres_devis',
            ordre=ordre, due_at=MAINTENANT, due_date=MAINTENANT.date(),
            canal=canal, libelle='Le PDF s\'ouvre bien ?', template_cle=cle)

    def test_b_une_touche_convertie_est_comptee_une_fois(self):
        fixe = self._lead('Standard', 'commercial', telephone=FIXE,
                          email='standard@hotel.ma')
        self._touche_email(fixe)
        for _ in range(2):
            ligne = self._mesure()['commercial']
            self.assertEqual(ligne['touches_converties'],
                             {'email': 1, 'appel': 0})

    def test_une_conversion_en_appel_est_comptee_en_appel(self):
        fixe = self._lead('Standard', 'industriel', telephone=FIXE)
        self._touche_email(fixe, canal='appel')
        self.assertEqual(self._mesure()['industriel']['touches_converties'],
                         {'email': 0, 'appel': 1})

    def test_un_lead_sur_mobile_ne_compte_rien(self):
        mobile = self._lead('Mobile', 'commercial', telephone=MOBILE,
                            email='m@hotel.ma')
        self._touche_email(mobile)
        self.assertEqual(self._mesure()['commercial']['touches_converties'],
                         {'email': 0, 'appel': 0})

    def test_un_appel_du_protocole_nest_pas_une_conversion(self):
        fixe = self._lead('Standard', 'commercial', telephone=FIXE,
                          email='standard@hotel.ma')
        self._touche_email(fixe, canal='appel', ordre=2,
                           cle='appel_suivi_j2')
        self.assertEqual(self._mesure()['commercial']['touches_converties'],
                         {'email': 0, 'appel': 0})


class IncoherentsTests(_Base):
    slug = 'ciq518-inc'

    def test_c_devis_industriel_sur_lead_residentiel(self):
        residentiel = self._lead('R1', 'residentiel')
        self._devis(residentiel, 'industriel')
        seg = self._mesure()
        self.assertEqual(seg['industriel']['incoherents'], 1)
        self.assertEqual(seg['residentiel']['incoherents'], 0)
        self.assertEqual(seg['commercial']['incoherents'], 0)

    def test_devis_commercial_sur_lead_non_renseigne(self):
        sans_type = self._lead('S1', None)
        self._devis(sans_type, 'commercial')
        self.assertEqual(self._mesure()['commercial']['incoherents'], 1)

    def test_un_devis_pro_sur_un_lead_pro_n_est_pas_incoherent(self):
        pro = self._lead('P1', 'industriel')
        self._devis(pro, 'industriel')
        self.assertEqual(self._mesure()['industriel']['incoherents'], 0)

    def test_l_incoherence_agricole_d_agr540_est_inchangee(self):
        residentiel = self._lead('R1', 'residentiel')
        self._devis(residentiel, 'agricole')
        seg = self._mesure()
        self.assertEqual(seg['residentiel']['incoherents'], 1)
        self.assertEqual(seg['agricole']['incoherents'], 0)


class NullEtContratTests(_Base):
    slug = 'ciq518-null'

    def test_d_segment_sans_touche_close_joints_par_creneau_null(self):
        self._lead('C1', 'commercial')
        ligne = self._mesure()['commercial']
        self.assertIsNone(ligne['joints_par_creneau'])
        self.assertEqual(ligne['delais_signature_jours'], [])
        self.assertIsNone(ligne['taux_joint_pct'])

    def test_forme_conforme_au_contrat(self):
        self._lead('R1', 'residentiel')
        attendu = CONTRAT['exemple']['par_segment'][0]
        for ligne in mesure_cadence.par_segment(self.company):
            self.assertEqual(set(ligne), set(attendu), ligne['segment'])
            for cle in CLES_CIQ518:
                self.assertIn(cle, ligne)

    def test_vide_egale_l_exemple_vide_du_contrat(self):
        self.assertEqual(mesure_cadence.par_segment(self.company),
                         CONTRAT['exemple_vide']['par_segment'])

    def test_les_raisons_du_contrat_sont_celles_du_serveur(self):
        for ligne in CONTRAT['exemple']['par_segment']:
            self.assertEqual(list(ligne['attente_accord_par_raison']),
                             [r[0] for r in RAISONS_ATTENTE])

    def test_creneaux(self):
        cas = {0: 'matin', 11: 'matin', 12: 'midi', 13: 'midi',
               14: 'apres_midi', 17: 'apres_midi', 18: 'soir', 23: 'soir'}
        for heure, attendu in cas.items():
            self.assertEqual(mesure_cadence.creneau_de_heure(heure), attendu)
