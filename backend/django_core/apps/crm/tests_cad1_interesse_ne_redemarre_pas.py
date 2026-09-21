"""CAD1 — reproduction ROUGE : « Intéressé » sur une touche de suivi de
proposition relance tout le plan à la touche 1.

POURQUOI CE TEST ÉCHOUE SUR LE CODE D'AVANT — la chaîne, dans l'ordre :

1. `marquer_etape_relance` (apps/crm/services.py) écrit d'abord l'étape en
   FAIT, PUIS crée la `LeadActivity` porteuse de l'issue.
2. Ce `post_save` réveille SYNCHRONEMENT le récepteur MRY9
   `_arreter_cadence_on_outcome` (apps/crm/receivers.py). Sur « intéressé »
   il n'arrête que `contact` et `reveil` — la cadence `apres_devis` continue,
   c'est voulu — puis appelle `assurer_prochaine_etape_apres_succes`.
3. Ce filet ne voit plus AUCUNE touche ouverte (celle qu'on vient de clore
   l'était encore une ligne plus haut), trouve le devis envoyé, et appelle
   `initialiser_plan_relance(cadence='apres_devis', devis=devis)` SANS
   `depart`.
4. L'idempotence de `initialiser_plan_relance` ne porte que sur les touches
   OUVERTES (TREADMILL-1538) : toutes celles du plan étant closes, rien ne
   l'arrête. Le plan REPART au barreau 1, ancré sur « maintenant ».

Résultat en production : le client le plus chaud du portefeuille — celui qui
vient de dire « je suis intéressé » — reçoit « Le PDF s'ouvre bien ? », le
message du lendemain de l'envoi, pour la deuxième fois.

Ce que ce module verrouille, et rien d'autre :

  * `j1_pdf` n'est JAMAIS recréé (le cas « deux fois j1_pdf » reste à zéro) ;
  * la suite d'« Intéressé » est le barreau SUIVANT du protocole, exactement
    comme « Sans réponse » — la doctrine « aucun redémarrage de cadence
    n'existe nulle part » (apps/crm/services.py, docstring de
    `suspendre_plan_jusqu_apres_visite`) ;
  * une seule touche ouverte à la fois (CKP2), et aucune touche ajoutée,
    retirée ni réordonnée : le protocole après-devis garde ses 10 barreaux.

Le temps est gelé : l'ancre de cadence et les échéances J+N sont exactement
ce qu'une horloge vivante rend instable.
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, stages
from apps.crm.models import Client, Lead, RelanceEtape
from apps.crm.services import (
    calculer_echeances_cadence, marquer_etape_relance)
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import CadenceRelanceEtape
from apps.ventes.models import Devis

User = get_user_model()

#: Mercredi 23 septembre 2026, 10 h à Casablanca — jour ouvré, DANS la fenêtre
#: d'appel : aucune échéance calculée ici n'est repoussée par le recalage.
MERCREDI = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)

#: Le devis est parti 7 jours plus tôt : l'ancre du plan après-devis. Les
#: barreaux 1 à 5 (J+1, J+2, J+3, J+4, J+6) sont donc DERRIÈRE nous et le
#: barreau 6 (J+7) est le prochain geste du protocole.
DEPART = MERCREDI - datetime.timedelta(days=7)


class _Base(TestCase):
    """Un lead, un devis ENVOYÉ, un plan après-devis consommé jusqu'au 5."""

    slug = 'cad1'

    def setUp(self):
        gel = frozen(MERCREDI)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = Company.objects.create(
            nom='CAD1 Solaire', slug=self.slug)
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-resp', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Aziz', stage=stages.QUOTE_SENT,
            owner=self.acteur, telephone='+212661000101')
        self.client_vente = Client.objects.create(
            company=self.company, nom='Aziz', email=f'{self.slug}@example.com')
        self.devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{self.slug}-0001',
            client=self.client_vente, lead=self.lead,
            statut=Devis.Statut.ENVOYE, taux_tva=Decimal('20.00'),
            date_envoi=DEPART)
        self.gabarits = CadenceRelanceEtape.cadence_pour(
            self.company, 'apres_devis')
        self.echeances = calculer_echeances_cadence(
            self.lead, 'apres_devis', DEPART, gabarits=self.gabarits)

    def _poser_plan(self, jusqu_a):
        """Matérialise les barreaux 1..``jusqu_a`` comme le moteur l'aurait
        fait barreau par barreau : les précédents CLOS, le dernier OUVERT."""
        etapes = {}
        for gabarit, echeance in self.echeances:
            if gabarit.ordre > jusqu_a:
                break
            ouverte = gabarit.ordre == jusqu_a
            etapes[gabarit.ordre] = RelanceEtape.objects.create(
                company=self.company, lead=self.lead, cadence='apres_devis',
                ordre=gabarit.ordre, due_at=echeance,
                due_date=echeance.astimezone(horaires.CASABLANCA).date(),
                canal=gabarit.canal, libelle=gabarit.libelle,
                template_cle=gabarit.template_cle or '',
                devis=self.devis, cadence_depart=DEPART,
                statut=(RelanceEtape.Statut.A_FAIRE if ouverte
                        else RelanceEtape.Statut.FAIT),
                traite_par=None if ouverte else self.acteur,
                traite_le=None if ouverte else echeance,
            )
        return etapes

    def _ouvertes(self):
        return list(self.lead.relance_etapes
                    .filter(statut=RelanceEtape.Statut.A_FAIRE)
                    .order_by('ordre', 'due_date'))


class InteresseApresDevisTests(_Base):
    """La touche 5 du suivi, clôturée « Intéressé »."""

    slug = 'cad1-interesse'

    def setUp(self):
        super().setUp()
        self.etapes = self._poser_plan(jusqu_a=5)
        self.touche5 = self.etapes[5]

    def test_j1_pdf_n_est_jamais_recree(self):
        marquer_etape_relance(
            self.touche5, self.acteur, RelanceEtape.Statut.FAIT,
            outcome='interesse')
        # LE cas « deux fois j1_pdf » du Done : il reste à zéro.
        self.assertEqual(
            self.lead.relance_etapes.filter(template_cle='j1_pdf').count(), 1)

    def test_la_suite_est_le_barreau_suivant_du_protocole(self):
        marquer_etape_relance(
            self.touche5, self.acteur, RelanceEtape.Statut.FAIT,
            outcome='interesse')
        ouvertes = self._ouvertes()
        # CKP2 — une seule touche ouverte, et c'est le barreau 6.
        self.assertEqual(len(ouvertes), 1, [e.libelle for e in ouvertes])
        self.assertEqual(ouvertes[0].ordre, 6)
        self.assertEqual(ouvertes[0].cadence, 'apres_devis')
        self.assertEqual(ouvertes[0].devis_id, self.devis.pk)

    def test_l_ancre_du_plan_ne_bouge_pas(self):
        marquer_etape_relance(
            self.touche5, self.acteur, RelanceEtape.Statut.FAIT,
            outcome='interesse')
        ouverte = self._ouvertes()[0]
        # « Décaler, jamais redémarrer » : la touche née de l'issue garde
        # l'ancre du plan, donc son J+7 reste un J+7 depuis l'ENVOI du devis.
        self.assertEqual(ouverte.cadence_depart, DEPART)

    def test_le_nombre_de_touches_du_plan_ne_grossit_pas(self):
        avant = self.lead.relance_etapes.filter(cadence='apres_devis').count()
        marquer_etape_relance(
            self.touche5, self.acteur, RelanceEtape.Statut.FAIT,
            outcome='interesse')
        apres = self.lead.relance_etapes.filter(cadence='apres_devis').count()
        # Exactement UNE touche de plus : le barreau 6. Le redémarrage en
        # créait dix.
        self.assertEqual(apres, avant + 1)

    def test_aucun_barreau_deja_consomme_n_est_repose(self):
        """Aucun barreau DÉJÀ POSÉ n'existe en double après l'issue.

        Les ordres parcourus sont ceux que la partition de CE lead contient
        vraiment, pas `range(1, 6)` : le barreau 3 (« Dimanche famille »,
        `dimanche_ok`) est RÉSERVÉ aux dossiers étiquetés « Décision à
        plusieurs » (MRY4, `services._TEMPLATE_DIMANCHE_FAMILLE`) et ce lead
        ne porte pas l'étiquette — il n'a donc jamais été matérialisé, et en
        exiger un exemplaire revenait à reprocher au moteur une touche qu'il
        a EXPRÈS écartée. Le trou dans la numérotation est épinglé ici même
        pour que ce test reste un vrai contrôle de non-duplication.
        """
        ordres_poses = sorted(self.etapes)
        self.assertEqual(ordres_poses, [1, 2, 4, 5])
        marquer_etape_relance(
            self.touche5, self.acteur, RelanceEtape.Statut.FAIT,
            outcome='interesse')
        for ordre in ordres_poses:
            self.assertEqual(
                self.lead.relance_etapes.filter(
                    cadence='apres_devis', ordre=ordre).count(), 1,
                f'barreau {ordre} reposé')


class JointApresDevisTests(_Base):
    """« Joint » suit exactement le même chemin : le récepteur MRY9 n'arrête
    QUE `contact` et `reveil`, la proposition reste à relancer."""

    slug = 'cad1-joint'

    def test_joint_ne_redemarre_pas_le_plan(self):
        touche5 = self._poser_plan(jusqu_a=5)[5]
        marquer_etape_relance(
            touche5, self.acteur, RelanceEtape.Statut.FAIT, outcome='joint')
        self.assertEqual(
            self.lead.relance_etapes.filter(template_cle='j1_pdf').count(), 1)
        ouvertes = self._ouvertes()
        self.assertEqual(len(ouvertes), 1, [e.libelle for e in ouvertes])
        self.assertEqual(ouvertes[0].ordre, 6)


class FinDeProtocoleTests(_Base):
    """Le barreau 10 clôturé « Intéressé » : plus de barreau à faire naître,
    donc le filet reprend la main — mais il ne rejoue JAMAIS le plan."""

    slug = 'cad1-fin'

    def test_le_dernier_barreau_ne_relance_pas_le_plan(self):
        touche10 = self._poser_plan(jusqu_a=10)[10]
        marquer_etape_relance(
            touche10, self.acteur, RelanceEtape.Statut.FAIT,
            outcome='interesse')
        self.assertEqual(
            self.lead.relance_etapes.filter(template_cle='j1_pdf').count(), 1)
        ouvertes = self._ouvertes()
        # QJ-INVARIANT : le dossier ne disparaît pas des files — une étape de
        # filet `generique` prend le relais, jamais un barreau du protocole.
        self.assertEqual(len(ouvertes), 1, [e.libelle for e in ouvertes])
        self.assertEqual(ouvertes[0].cadence, 'generique')


class RefusInchangeTests(_Base):
    """Garde-fou : « Refuse » arrête `apres_devis` — rien ne doit naître du
    protocole. Ce test échouerait si le correctif matérialisait trop large."""

    slug = 'cad1-refus'

    def test_refus_ne_fait_naitre_aucun_barreau(self):
        touche5 = self._poser_plan(jusqu_a=5)[5]
        marquer_etape_relance(
            touche5, self.acteur, RelanceEtape.Statut.FAIT, outcome='refuse')
        ouvertes = self._ouvertes()
        self.assertEqual(len(ouvertes), 1, [e.libelle for e in ouvertes])
        self.assertEqual(ouvertes[0].cadence, 'generique')
        self.assertEqual(
            self.lead.relance_etapes.filter(
                cadence='apres_devis', ordre=6).count(), 0)


class PremierContactInchangeTests(_Base):
    """Garde-fou : sur la cadence `contact`, « Intéressé » ARRÊTE bien la
    cadence (MRY9) — aucun barreau de prise de contact ne naît."""

    slug = 'cad1-contact'

    def test_interesse_sur_le_premier_contact_arrete_la_cadence(self):
        gabarits = CadenceRelanceEtape.cadence_pour(self.company, 'contact')
        echeances = calculer_echeances_cadence(
            self.lead, 'contact', DEPART, gabarits=gabarits)
        gabarit, echeance = echeances[0]
        touche = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='contact',
            ordre=gabarit.ordre, due_at=echeance,
            due_date=echeance.astimezone(horaires.CASABLANCA).date(),
            canal=gabarit.canal, libelle=gabarit.libelle,
            template_cle=gabarit.template_cle or '', cadence_depart=DEPART)
        marquer_etape_relance(
            touche, self.acteur, RelanceEtape.Statut.FAIT,
            outcome='interesse')
        self.assertEqual(
            self.lead.relance_etapes.filter(
                cadence='contact', statut=RelanceEtape.Statut.A_FAIRE).count(),
            0)
