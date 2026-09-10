"""MRY23 — La reprise des dossiers déjà présents, le jour de la mise en service.

Sans elle, le moteur ne démarrerait que sur les leads arrivés APRÈS le
déploiement : tout le portefeuille en cours resterait sans cadence.

Trois propriétés font la différence entre une reprise utile et une catastrophe :

  * DRY-RUN PAR DÉFAUT — une commande qui écrit 400 cadences ne doit jamais
    partir par accident ;
  * les touches DÉJÀ PASSÉES d'un devis repris sont SAUTÉES : les rejouer
    enverrait aujourd'hui le message du J+1 d'il y a dix jours ;
  * les réveils sont ÉTALÉS — lancer 400 réveils le même matin saturerait la
    journée de Meryem et ferait partir 400 messages en rafale depuis le même
    numéro, le meilleur moyen de se faire signaler comme spam.

Et la reprise n'est PAS une porte dérobée : elle passe par les mêmes gardes
que MRY6 (numéro exploitable, doublon vivant, ne plus contacter).
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from apps.crm import stages
from apps.crm.management.commands.demarrer_cadences_existantes import (
    demarrer_cadences_existantes)
from apps.crm.models import Client, Lead, RelanceEtape
from apps.parametres.models import CompanyProfile
from apps.ventes.models import Devis

User = get_user_model()


def _company(slug):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    CompanyProfile.objects.get_or_create(company=company)
    return company


class _Base(TestCase):
    slug = 'mry23'

    def setUp(self):
        self.company = _company(self.slug)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-u', password='x',
            role_legacy='responsable', company=self.company)

    def _lead(self, nom='Prospect', **kw):
        champs = {'company': self.company, 'nom': nom, 'owner': self.acteur,
                  'telephone': f'+21266{abs(hash(nom)) % 10000000:07d}',
                  'source': Lead.Source.OS_NATIVE}
        champs.update(kw)
        return Lead.objects.create(**champs)

    def _vieillir(self, lead, jours):
        Lead.objects.filter(pk=lead.pk).update(
            date_creation=timezone.now() - datetime.timedelta(days=jours))
        return Lead.objects.get(pk=lead.pk)

    def _devis(self, lead, reference, jours):
        client = Client.objects.create(
            company=self.company, nom='Client', email=f'{reference}@ex.com')
        return Devis.objects.create(
            company=self.company, reference=reference, client=client,
            lead=lead, statut='envoye', taux_tva=Decimal('20.00'),
            date_envoi=timezone.now() - datetime.timedelta(days=jours))

    def _touches(self, lead, cadence):
        return lead.relance_etapes.filter(cadence=cadence)


class DryRunTests(_Base):
    slug = 'mry23-dryrun'

    def test_le_dry_run_necrit_absolument_rien(self):
        """Une commande qui écrit 400 cadences ne doit jamais partir par
        accident : le défaut est la simulation."""
        lead = self._lead('Neuf')
        rapport = demarrer_cadences_existantes(self.company)
        self.assertEqual(rapport['contact']['nb'], 1)
        self.assertEqual(RelanceEtape.objects.count(), 0)
        self.assertEqual(self._touches(lead, 'contact').count(), 0)

    def test_le_rapport_donne_des_exemples_didentifiants(self):
        lead = self._lead('Neuf')
        rapport = demarrer_cadences_existantes(self.company)
        self.assertIn(lead.pk, rapport['contact']['exemples'])


class DevisRecentsTests(_Base):
    slug = 'mry23-devis'

    def test_un_devis_recent_recoit_sa_cadence(self):
        lead = self._lead('Avec devis')
        self._devis(lead, 'DEV-MRY23-0001', jours=2)
        demarrer_cadences_existantes(self.company, apply_changes=True)
        self.assertGreater(self._touches(lead, 'apres_devis').count(), 0)

    def test_les_touches_deja_passees_sont_ANNULEES(self):
        """Les rejouer enverrait aujourd'hui le message du J+1 d'il y a dix
        jours — un message hors sujet qui décrédibilise tout le reste.

        CKP1 — elles sont ANNULÉES (moteur), pas « sautées » : personne n'a
        décidé de les passer, et ``traite_par`` reste NULL."""
        lead = self._lead('Devis ancien')
        self._devis(lead, 'DEV-MRY23-0002', jours=10)
        demarrer_cadences_existantes(self.company, apply_changes=True)
        annulees = self._touches(lead, 'apres_devis').filter(
            statut=RelanceEtape.Statut.ANNULEE)
        self.assertGreater(annulees.count(), 0)
        for etape in annulees:
            self.assertEqual(etape.note, 'reprise : déjà passée')
            self.assertIsNone(etape.traite_par)
        self.assertEqual(
            self._touches(lead, 'apres_devis').filter(
                statut=RelanceEtape.Statut.SAUTEE).count(), 0)
        # Et il reste des touches À FAIRE (sinon la reprise ne sert à rien).
        self.assertGreater(
            self._touches(lead, 'apres_devis').filter(
                statut=RelanceEtape.Statut.A_FAIRE).count(), 0)

    def test_un_devis_trop_ancien_est_ignore(self):
        lead = self._lead('Devis périmé')
        self._devis(lead, 'DEV-MRY23-0003', jours=40)
        demarrer_cadences_existantes(self.company, apply_changes=True)
        self.assertEqual(self._touches(lead, 'apres_devis').count(), 0)

    def test_un_lead_perdu_ou_ne_plus_contacter_est_ecarte(self):
        perdu = self._lead('Perdu', perdu=True, motif_perte='Prix')
        self._devis(perdu, 'DEV-MRY23-0004', jours=2)
        stop = self._lead('Stop', ne_plus_contacter=True)
        self._devis(stop, 'DEV-MRY23-0005', jours=2)
        rapport = demarrer_cadences_existantes(
            self.company, apply_changes=True)
        self.assertEqual(self._touches(perdu, 'apres_devis').count(), 0)
        self.assertEqual(self._touches(stop, 'apres_devis').count(), 0)
        self.assertGreaterEqual(rapport['ignores'], 2)


class StatutDuDevisTests(_Base):
    """MRY23 — seuls les devis TOUJOURS EN ATTENTE sont repris.

    `devis_envoyes_periode` ne filtre QUE `date_envoi` : la reprise démarrait
    donc une cadence « après devis » sur des propositions déjà ACCEPTÉES,
    refusées ou expirées — et demandait « alors, ce PDF ? » trois jours après
    la signature.
    """

    slug = 'mry23-statut'

    def _devis_au_statut(self, nom, reference, statut):
        lead = self._lead(nom)
        devis = self._devis(lead, reference, jours=3)
        # `.update()` : on change le statut SANS déclencher les événements de
        # domaine (acceptation/refus), qui poseraient leurs propres cadences.
        Devis.objects.filter(pk=devis.pk).update(statut=statut)
        return lead

    def test_un_devis_ACCEPTE_recent_ne_declenche_aucune_cadence(self):
        lead = self._devis_au_statut('Signé', 'DEV-MRY23-0200', 'accepte')
        demarrer_cadences_existantes(self.company, apply_changes=True)
        self.assertEqual(self._touches(lead, 'apres_devis').count(), 0)

    def test_un_devis_REFUSE_recent_non_plus(self):
        lead = self._devis_au_statut('Refusé', 'DEV-MRY23-0201', 'refuse')
        demarrer_cadences_existantes(self.company, apply_changes=True)
        self.assertEqual(self._touches(lead, 'apres_devis').count(), 0)

    def test_un_devis_EXPIRE_non_plus(self):
        lead = self._devis_au_statut('Expiré', 'DEV-MRY23-0202', 'expire')
        demarrer_cadences_existantes(self.company, apply_changes=True)
        self.assertEqual(self._touches(lead, 'apres_devis').count(), 0)

    def test_un_devis_ENVOYE_reste_repris(self):
        """Contrôle positif : le filtre ne doit pas tout écarter."""
        lead = self._devis_au_statut('En attente', 'DEV-MRY23-0203', 'envoye')
        demarrer_cadences_existantes(self.company, apply_changes=True)
        self.assertGreater(self._touches(lead, 'apres_devis').count(), 0)


class PariteDryRunApplyTests(_Base):
    """MRY23 — la simulation annonce EXACTEMENT ce que `--apply` fera.

    Le dry-run ne vérifiait que « ce lead a-t-il déjà une cadence ? » et
    comptait donc des dossiers que `--apply` refusait ensuite (sans numéro,
    doublon vivant). C'est pourtant sur ce chiffre que se décide le lancement
    d'une reprise de portefeuille.
    """

    slug = 'mry23-parite'

    def test_les_compteurs_du_dry_run_valent_ceux_de_apply(self):
        self._lead('Joignable', telephone='+212661000001')
        self._lead('Sans numéro', telephone=None, whatsapp=None)
        simulation = demarrer_cadences_existantes(self.company)
        applique = demarrer_cadences_existantes(
            self.company, apply_changes=True)
        self.assertEqual(simulation['contact']['nb'],
                         applique['contact']['nb'])
        self.assertEqual(simulation['ignores'], applique['ignores'])

    def test_le_lead_sans_numero_est_compte_comme_ecarte_des_le_dry_run(self):
        self._lead('Joignable', telephone='+212661000002')
        self._lead('Sans numéro', telephone=None, whatsapp=None)
        simulation = demarrer_cadences_existantes(self.company)
        self.assertEqual(simulation['contact']['nb'], 1)
        self.assertGreaterEqual(simulation['ignores'], 1)


class LeadsNeufsTests(_Base):
    slug = 'mry23-neufs'

    def test_un_lead_neuf_recoit_la_cadence_de_contact(self):
        lead = self._lead('Neuf')
        demarrer_cadences_existantes(self.company, apply_changes=True)
        self.assertGreater(self._touches(lead, 'contact').count(), 0)

    def test_un_lead_trop_vieux_est_ignore(self):
        """« Vous venez de nous laisser une demande » serait faux au bout de
        cinq jours."""
        lead = self._vieillir(self._lead('Vieux'), 20)
        demarrer_cadences_existantes(self.company, apply_changes=True)
        self.assertEqual(self._touches(lead, 'contact').count(), 0)

    def test_les_gardes_de_MRY6_sappliquent(self):
        """La reprise n'est pas une porte dérobée : un lead sans numéro
        exploitable reste sans cadence."""
        lead = self._lead('Sans numéro', telephone=None, whatsapp=None)
        rapport = demarrer_cadences_existantes(
            self.company, apply_changes=True)
        self.assertEqual(self._touches(lead, 'contact').count(), 0)
        self.assertGreaterEqual(rapport['ignores'], 1)


class ReveilsEtalesTests(_Base):
    slug = 'mry23-reveils'

    def test_vingt_cinq_dormants_a_dix_par_jour_couvrent_trois_jours(self):
        """Lancer 400 réveils le même matin ferait partir 400 messages en
        rafale depuis le même numéro."""
        for i in range(25):
            self._lead(f'Froid {i}', stage=stages.COLD)
        # Bug CI #29 (récidive du 10/09/2026) — `now` est GELÉ sur un lundi :
        # le réveil ordre 1 vaut J+30, donc lancé un JEUDI les trois départs
        # étalés tombent Sam/Dim/Lun et le recalage week-end les fusionne TOUS
        # sur le même lundi (len(jours) == 1). La propriété testée est
        # l'étalement, pas le calendrier du jour de CI.
        lundi = timezone.make_aware(
            datetime.datetime(2026, 9, 7, 10, 0), datetime.timezone.utc)
        demarrer_cadences_existantes(
            self.company, apply_changes=True, par_jour=10, now=lundi)
        premieres = RelanceEtape.objects.filter(
            company=self.company, cadence='reveil', ordre=1)
        self.assertEqual(premieres.count(), 25)
        # Bug CI #29 — on n'épingle PAS « exactement 3 jours » : le recalage
        # sur la fenêtre d'appel peut ramener deux départs voisins au même
        # lundi. La propriété qui compte est qu'ils ne tombent pas TOUS le
        # même jour, et que les départs sont bien décalés.
        jours = {e.due_at.date() for e in premieres if e.due_at}
        self.assertGreater(len(jours), 1)

    def test_un_dormant_avec_activite_recente_nest_pas_reveille(self):
        from apps.crm.models import LeadActivity
        actif = self._lead('Encore suivi', stage=stages.QUOTE_SENT)
        LeadActivity.objects.create(
            company=self.company, lead=actif, user=self.acteur,
            kind=LeadActivity.Kind.APPEL)
        demarrer_cadences_existantes(self.company, apply_changes=True)
        self.assertEqual(self._touches(actif, 'reveil').count(), 0)

    def test_un_devis_sans_suite_depuis_longtemps_est_reveille(self):
        dormant = self._lead('Sans suite', stage=stages.FOLLOW_UP)
        demarrer_cadences_existantes(self.company, apply_changes=True)
        self.assertGreater(self._touches(dormant, 'reveil').count(), 0)


class IdempotenceEtIsolationTests(_Base):
    slug = 'mry23-idem'

    def test_un_second_passage_ne_cree_rien(self):
        lead = self._lead('Neuf')
        self._devis(self._lead('Avec devis'), 'DEV-MRY23-0100', jours=2)
        demarrer_cadences_existantes(self.company, apply_changes=True)
        avant = RelanceEtape.objects.count()
        rapport = demarrer_cadences_existantes(
            self.company, apply_changes=True)
        self.assertEqual(RelanceEtape.objects.count(), avant)
        self.assertEqual(rapport['contact']['nb'], 0)
        self.assertEqual(rapport['apres_devis']['nb'], 0)
        self.assertGreater(self._touches(lead, 'contact').count(), 0)

    def test_une_autre_societe_nest_jamais_touchee(self):
        voisine = _company('mry23-voisine')
        owner = User.objects.create_user(
            username='mry23-voisin-u', password='x', company=voisine)
        lead_voisin = Lead.objects.create(
            company=voisine, nom='Voisin', owner=owner,
            telephone='+212661998877', source=Lead.Source.OS_NATIVE)
        demarrer_cadences_existantes(self.company, apply_changes=True)
        self.assertEqual(
            lead_voisin.relance_etapes.count(), 0)
