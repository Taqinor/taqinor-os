"""MRY30 — Le SUIVI des relances par période, et le PLACEMENT des anciens leads.

Deux moitiés d'une même journée de travail, et deux pièges opposés.

Le SUIVI (`relance-etapes/suivi/`) regarde EN ARRIÈRE autant qu'en avant : ce
qui a été fait, ce qui a été sauté, ce qui reste, jour par jour. Son piège est
le RÉSUMÉ : compté après le filtre `statut`, l'onglet « fait » afficherait
« sauté : 0 » et Meryem croirait n'avoir rien laissé passer. Il est donc compté
sur la période AVANT ce filtre — et ces tests le verrouillent.

Le PLACEMENT (`placer_anciens_leads`) fait entrer le portefeuille EXISTANT dans
le moteur. Ses pièges sont plus graves, parce qu'ils s'appliquent à des
centaines de dossiers d'un coup :

  * un aperçu qui n'écrit rien mais annonce autre chose que ce que `--apply`
    fera (la reprise MRY23 avait payé la leçon) ;
  * une note chatter portant l'ACTEUR, qui déclarerait « contactés » (QJ7 :
    NEW → CONTACTED + `first_contacted_at`) les leads qu'on vient justement
    d'inscrire dans la cadence de PREMIER contact ;
  * une cadence positionnée dont toutes les touches sont déjà passées : elle
    ne relancerait personne, et laisserait un rappel fantôme derrière elle ;
  * 200 réveils le même matin, c'est-à-dire 200 messages en rafale depuis le
    même numéro ;
  * un aperçu qui CALCULE en écrivant : celui du 06/09 matérialisait les
    touches des 277 candidats dans une transaction annulée — plus de 20 s,
    donc deux 499 dans nginx le 07/09 (le navigateur abandonne à 20 s) et un
    écran qui n'affichait jamais rien. Aperçu comme application se traitent
    désormais par petits morceaux : calcul pur d'un côté, lots de `limite`
    leads de l'autre ;
  * des lots qui se marchent dessus : sans compter les réveils DÉJÀ posés,
    le lot 2 reposerait ses huit réveils sur les créneaux du lot 1.

Le temps est GELÉ dans tous ces tests : « aujourd'hui », « en retard » et les
créneaux étalés sont exactement les questions qu'une horloge vivante rend
instables (un passage à minuit décale toute la période).
"""
import datetime
import io
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, stages
from apps.crm.models import Client, Lead, LeadActivity, RelanceEtape
from apps.crm.selectors import relance_etapes_dues
from apps.crm.services import (
    PLACEMENT_CRENEAUX, PLACEMENT_NOTE_PASSEE, PLACEMENT_REVEILS_PAR_JOUR,
    calculer_echeances_cadence, initialiser_plan_relance, placer_anciens_leads)
from apps.parametres.models import CompanyProfile
from apps.ventes.models import Devis

User = get_user_model()

#: Mercredi 9 septembre 2026, 9 h à Casablanca — jour ouvré, DANS la fenêtre
#: d'appel (8 h 30 - 20 h) et AVANT le premier créneau de réveil (10 h) : les
#: créneaux étalés tombent donc tous dans le futur, ce qui rend leurs dates
#: lisibles sans arithmétique de rattrapage.
MERCREDI = datetime.datetime(2026, 9, 9, 9, 0, tzinfo=horaires.CASABLANCA)
JEUDI = MERCREDI.date() + datetime.timedelta(days=1)

SUIVI_URL = '/api/django/crm/relance-etapes/suivi/'
PLACEMENT_URL = '/api/django/crm/leads/placement-cadences/'


def _company(slug):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    CompanyProfile.objects.get_or_create(company=company)
    return company


def _jour(annee, mois, jour, heure=10, minute=0):
    return datetime.datetime(annee, mois, jour, heure, minute,
                             tzinfo=horaires.CASABLANCA)


class _Base(TestCase):
    """Société + responsable + horloge gelée sur MERCREDI."""

    slug = 'mry30'

    def setUp(self):
        gel = frozen(MERCREDI)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = _company(self.slug)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-resp', password='x',
            role_legacy='responsable', company=self.company)
        self._compteur = 0

    def _api(self, user=None):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user or self.acteur)}')
        return api

    def _lead(self, nom='Prospect', *, stage=stages.NEW, jours=0, owner=None,
              **kw):
        """Un lead de la société, éventuellement VIEILLI de ``jours``.

        ``date_creation`` est ``auto_now_add`` : on ne peut pas la poser à la
        création, d'où l'UPDATE (jamais un monkeypatch de l'horloge)."""
        self._compteur += 1
        lead = Lead.objects.create(
            company=self.company, nom=nom, stage=stage,
            owner=self.acteur if owner is None else owner,
            telephone=f'+21266111{self._compteur:04d}', **kw)
        if jours:
            Lead.objects.filter(pk=lead.pk).update(
                date_creation=MERCREDI - datetime.timedelta(days=jours))
            lead.refresh_from_db()
        return lead


# ═══════════════════════════════════════════════════════════════════════════
# 1. L'action « suivi » — la file PAR PÉRIODE, tous statuts
# ═══════════════════════════════════════════════════════════════════════════

class SuiviActionTests(_Base):
    slug = 'mry30-suivi'

    def setUp(self):
        super().setUp()
        self.lead = self._lead('Aziz')
        # Cinq touches : une en retard, une due aujourd'hui, une faite, une
        # sautée, une HORS période.
        self.en_retard = self._touche(_jour(2026, 9, 7))
        self.faite = self._touche(
            _jour(2026, 9, 8), statut=RelanceEtape.Statut.FAIT,
            traite_par=self.acteur, traite_le=_jour(2026, 9, 8, 11, 30))
        self.a_faire = self._touche(_jour(2026, 9, 9))
        self.sautee = self._touche(
            _jour(2026, 9, 10), statut=RelanceEtape.Statut.SAUTEE,
            traite_par=self.acteur, traite_le=_jour(2026, 9, 10, 10, 0))
        # CKP1 — la SIXIÈME colonne : une touche retirée du plan par le MOTEUR
        # (cadence arrêtée parce que le client a répondu). Elle ne doit JAMAIS
        # se confondre avec le saut humain ci-dessus : `traite_par` est NULL.
        self.annulee = self._touche(
            _jour(2026, 9, 11), statut=RelanceEtape.Statut.ANNULEE,
            note='joint', traite_le=_jour(2026, 9, 11, 10, 0))
        self.hors = self._touche(_jour(2026, 9, 20))

    def _touche(self, quand, *, statut=RelanceEtape.Statut.A_FAIRE, lead=None,
                **kw):
        return RelanceEtape.objects.create(
            company=self.company, lead=lead or self.lead, cadence='contact',
            ordre=1, due_at=quand, due_date=quand.date(),
            canal=RelanceEtape.Canal.APPEL, libelle='Appel', statut=statut,
            **kw)

    def _get(self, user=None, **params):
        params.setdefault('date_debut', '2026-09-07')
        params.setdefault('date_fin', '2026-09-13')
        return self._api(user).get(SUIVI_URL, params)

    def test_la_forme_est_celle_du_contrat(self):
        resp = self._get()
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(
            set(resp.data),
            {'count', 'date_debut', 'date_fin', 'resume', 'results'})
        self.assertEqual(resp.data['date_debut'], '2026-09-07')
        self.assertEqual(resp.data['date_fin'], '2026-09-13')

    def test_seules_les_touches_de_la_periode_sont_rendues(self):
        resp = self._get()
        self.assertEqual(resp.data['count'], 5)
        self.assertNotIn(self.hors.pk, [ligne['id'] for ligne in resp.data['results']])

    def test_le_resume_compte_les_colonnes(self):
        resume = self._get().data['resume']
        self.assertEqual(
            resume, {'a_faire': 2, 'en_retard': 1, 'fait': 1, 'sautee': 1,
                     'annulee': 1})

    def test_en_retard_est_un_sous_ensemble_de_a_faire(self):
        """Jamais une cinquième colonne qui s'ajouterait aux autres."""
        resume = self._get().data['resume']
        self.assertLessEqual(resume['en_retard'], resume['a_faire'])

    def test_le_resume_ignore_le_filtre_statut(self):
        """LE piège : compté après le filtre, l'onglet « fait » afficherait
        « sauté : 0 » et Meryem croirait n'avoir rien laissé passer."""
        resp = self._get(statut='fait')
        self.assertEqual(resp.data['count'], 1)
        self.assertEqual(
            resp.data['resume'],
            {'a_faire': 2, 'en_retard': 1, 'fait': 1, 'sautee': 1,
             'annulee': 1})

    def test_le_filtre_en_retard_ne_rend_que_le_retard(self):
        resp = self._get(statut='en_retard')
        self.assertEqual([ligne['id'] for ligne in resp.data['results']],
                         [self.en_retard.pk])

    def test_un_statut_inconnu_est_refuse(self):
        self.assertEqual(self._get(statut='inconnu').status_code, 400)

    def test_les_lignes_sont_triees_par_jour(self):
        resp = self._get()
        self.assertEqual(
            [ligne['id'] for ligne in resp.data['results']],
            [self.en_retard.pk, self.faite.pk, self.a_faire.pk,
             self.sautee.pk, self.annulee.pk])

    def test_traite_le_et_traite_par_nom_sont_servis(self):
        lignes = {ligne['id']: ligne for ligne in self._get().data['results']}
        self.assertEqual(lignes[self.faite.pk]['traite_par_nom'],
                         self.acteur.username)
        self.assertIsNotNone(lignes[self.faite.pk]['traite_le'])

    def test_une_annulation_moteur_ne_porte_aucun_nom_humain(self):
        """CKP1 — le badge doit pouvoir dire « Annulée (moteur) · motif » et
        JAMAIS « Sautée par Meryem » : le serveur sert le libellé du statut, et
        `traite_par_nom` reste vide sur une annulation."""
        lignes = {ligne['id']: ligne for ligne in self._get().data['results']}
        annulee = lignes[self.annulee.pk]
        self.assertEqual(annulee['statut'], 'annulee')
        self.assertEqual(annulee['statut_libelle'], 'Annulée (moteur)')
        self.assertEqual(annulee['traite_par_nom'], '')
        self.assertEqual(annulee['note'], 'joint')
        sautee = lignes[self.sautee.pk]
        self.assertEqual(sautee['statut'], 'sautee')
        self.assertEqual(sautee['traite_par_nom'], self.acteur.username)

    def test_le_filtre_annulee_ne_rend_que_les_annulations_moteur(self):
        resp = self._get(statut='annulee')
        self.assertEqual([ligne['id'] for ligne in resp.data['results']],
                         [self.annulee.pk])

    def test_une_touche_a_faire_na_ni_acteur_ni_horodatage(self):
        lignes = {ligne['id']: ligne for ligne in self._get().data['results']}
        self.assertEqual(lignes[self.a_faire.pk]['traite_par_nom'], '')
        self.assertIsNone(lignes[self.a_faire.pk]['traite_le'])

    def test_le_filtre_owner_borne_le_resume_aussi(self):
        autre = User.objects.create_user(
            username=f'{self.slug}-autre', password='x',
            role_legacy='responsable', company=self.company)
        self._touche(_jour(2026, 9, 9), lead=self._lead('Autre', owner=autre))
        resp = self._get(owner=str(self.acteur.pk))
        self.assertEqual(resp.data['count'], 4)
        self.assertEqual(resp.data['resume']['a_faire'], 2)

    def test_une_borne_manquante_est_refusee(self):
        resp = self._api().get(SUIVI_URL, {'date_fin': '2026-09-13'})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('date_debut', resp.data)

    def test_une_borne_invalide_est_refusee(self):
        self.assertEqual(self._get(date_debut='07/09/2026').status_code, 400)

    def test_une_periode_inversee_est_refusee(self):
        resp = self._get(date_debut='2026-09-13', date_fin='2026-09-07')
        self.assertEqual(resp.status_code, 400)

    def test_une_periode_trop_longue_est_refusee(self):
        resp = self._get(date_debut='2026-09-01', date_fin='2026-11-05')
        self.assertEqual(resp.status_code, 400)

    def test_soixante_deux_jours_passent(self):
        resp = self._get(date_debut='2026-09-01', date_fin='2026-11-02')
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_une_periode_vide_rend_un_resume_a_zero(self):
        resp = self._get(date_debut='2026-12-01', date_fin='2026-12-10')
        self.assertEqual(resp.data['count'], 0)
        self.assertEqual(
            resp.data['resume'],
            {'a_faire': 0, 'en_retard': 0, 'fait': 0, 'sautee': 0,
             'annulee': 0})

    def test_la_lecture_est_ouverte_a_tout_role(self):
        simple = User.objects.create_user(
            username=f'{self.slug}-simple', password='x',
            role_legacy='normal', company=self.company)
        self.assertEqual(self._get(user=simple).status_code, 200)


# ═══════════════════════════════════════════════════════════════════════════
# 2. Les scopes « demain » et « semaine » de la file du jour
# ═══════════════════════════════════════════════════════════════════════════

class ScopesDuesTests(_Base):
    slug = 'mry30-scopes'

    def setUp(self):
        super().setUp()
        self.lead = self._lead('Aziz')
        self.hier = self._touche(_jour(2026, 9, 8))
        self.aujourdhui = self._touche(_jour(2026, 9, 9))
        self.demain = self._touche(_jour(2026, 9, 10))
        self.dans_six_jours = self._touche(_jour(2026, 9, 15))
        self.dans_dix_jours = self._touche(_jour(2026, 9, 19))

    def _touche(self, quand):
        return RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='contact', ordre=1,
            due_at=quand, due_date=quand.date(),
            canal=RelanceEtape.Canal.APPEL, libelle='Appel')

    def _ids(self, scope):
        return set(relance_etapes_dues(
            self.company, self.acteur, scope=scope).values_list('pk',
                                                                flat=True))

    def test_demain_ne_rend_que_demain(self):
        self.assertEqual(self._ids('tomorrow'), {self.demain.pk})

    def test_la_semaine_inclut_le_retard(self):
        """Une touche oubliée lundi doit rester sous les yeux toute la
        semaine, sinon elle disparaît quand elle devient urgente."""
        self.assertEqual(
            self._ids('week'),
            {self.hier.pk, self.aujourdhui.pk, self.demain.pk,
             self.dans_six_jours.pk})

    def test_les_trois_scopes_historiques_sont_inchanges(self):
        self.assertEqual(self._ids('today'), {self.aujourdhui.pk})
        self.assertEqual(self._ids('overdue'), {self.hier.pk})
        self.assertEqual(self._ids('all'), {self.hier.pk, self.aujourdhui.pk})


# ═══════════════════════════════════════════════════════════════════════════
# 3. Le placement — une décision par code
# ═══════════════════════════════════════════════════════════════════════════

class _PlacementBase(_Base):

    def _client(self):
        return Client.objects.create(
            company=self.company, nom='Client',
            email=f'{self.slug}@example.com')

    def _devis(self, lead, *, statut='envoye', jours=3, reference=None):
        self._compteur += 1
        return Devis.objects.create(
            company=self.company,
            reference=reference or f'DEV-{self.slug}-{self._compteur:04d}',
            client=self._client(), lead=lead, statut=statut,
            taux_tva=Decimal('20.00'),
            date_envoi=MERCREDI - datetime.timedelta(days=jours))

    def _placer(self, *, apply=True, limite=None):
        return placer_anciens_leads(self.company, self.acteur, apply=apply,
                                    limite=limite)

    def _codes(self, rapport):
        return {bloc['code']: bloc['nombre'] for bloc in rapport['par_etape']}

    def _reveils(self, lead):
        return list(lead.relance_etapes.filter(cadence='reveil')
                    .order_by('ordre'))


class DecisionContactTests(_PlacementBase):
    slug = 'mry30-contact'

    def test_un_lead_neuf_et_recent_recoit_la_cadence_complete(self):
        lead = self._lead('Neuf', stage=stages.NEW, jours=2)
        rapport = self._placer()
        self.assertEqual(self._codes(rapport), {'contact_complete': 1})
        touches = lead.relance_etapes.filter(cadence='contact')
        self.assertEqual(touches.count(), 11)
        self.assertEqual(
            set(touches.values_list('statut', flat=True)),
            {RelanceEtape.Statut.A_FAIRE})

    def test_le_placement_ne_declare_pas_le_lead_contacte(self):
        """QJ7 — une note chatter portant l'ACTEUR ferait avancer NEW →
        CONTACTED et stamperait `first_contacted_at` : 270 dossiers déclarés
        joints sans qu'un humain ait décroché. La note est SYSTÈME."""
        lead = self._lead('Neuf', stage=stages.NEW, jours=2)
        self._placer()
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.NEW)
        self.assertIsNone(lead.first_contacted_at)

    def test_la_note_chatter_nomme_la_cadence_et_la_touche(self):
        lead = self._lead('Neuf', stage=stages.NEW, jours=2)
        self._placer()
        note = lead.activites.filter(body__startswith='Placé dans').first()
        self.assertIsNotNone(note)
        self.assertIn('contact', note.body)
        self.assertIn('moteur', note.body)

    def test_un_lead_contacte_est_positionne_et_les_touches_passees_annulees(self):
        """CKP1 — les touches déjà échues d'une cadence rétrodatée sont
        ANNULÉES par le moteur : les compter comme des sauts de Meryem
        inventerait des manquements sur un plan qu'elle n'a jamais vu."""
        lead = self._lead('Suivi', stage=stages.CONTACTED, jours=10)
        rapport = self._placer()
        self.assertEqual(self._codes(rapport), {'contact_positionne': 1})
        touches = lead.relance_etapes.filter(cadence='contact')
        annulees = touches.filter(statut=RelanceEtape.Statut.ANNULEE)
        self.assertGreater(annulees.count(), 0)
        self.assertEqual(set(annulees.values_list('note', flat=True)),
                         {PLACEMENT_NOTE_PASSEE})
        self.assertEqual(set(annulees.values_list('traite_par_id', flat=True)),
                         {None})
        self.assertEqual(
            touches.filter(statut=RelanceEtape.Statut.SAUTEE).count(), 0)
        self.assertGreater(
            touches.filter(statut=RelanceEtape.Statut.A_FAIRE).count(), 0)

    def test_le_positionnement_recale_la_date_de_relance(self):
        """`initialiser_plan_relance` pointe la PREMIÈRE touche — celle qu'on
        vient de sauter. Sans recalage, « Ma file » montrerait un rappel qui
        n'existe plus."""
        lead = self._lead('Suivi', stage=stages.CONTACTED, jours=10)
        self._placer()
        lead.refresh_from_db()
        prochaine = (lead.relance_etapes
                     .filter(statut=RelanceEtape.Statut.A_FAIRE)
                     .order_by('due_at').first())
        self.assertEqual(lead.relance_date, prochaine.due_date)

    def test_le_positionnement_ne_touche_jamais_a_letape(self):
        lead = self._lead('Suivi', stage=stages.CONTACTED, jours=10)
        self._placer()
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.CONTACTED)


class DecisionApresDevisTests(_PlacementBase):
    slug = 'mry30-devis'

    def test_un_devis_envoye_date_la_cadence_depuis_son_envoi(self):
        lead = self._lead('Chiffré', stage=stages.QUOTE_SENT, jours=20)
        devis = self._devis(lead, jours=3)
        rapport = self._placer()
        self.assertEqual(self._codes(rapport), {'apres_devis_positionne': 1})
        touches = lead.relance_etapes.filter(cadence='apres_devis')
        self.assertGreater(touches.count(), 0)
        self.assertEqual(set(touches.values_list('devis_id', flat=True)),
                         {devis.pk})
        self.assertGreater(
            touches.filter(statut=RelanceEtape.Statut.ANNULEE).count(), 0)
        self.assertGreater(
            touches.filter(statut=RelanceEtape.Statut.A_FAIRE).count(), 0)

    def test_une_relance_recente_sans_devis_erp_est_positionnee(self):
        lead = self._lead('Relancé', stage=stages.FOLLOW_UP, jours=5)
        rapport = self._placer()
        self.assertEqual(self._codes(rapport), {'apres_devis_positionne': 1})
        self.assertGreater(
            lead.relance_etapes.filter(cadence='apres_devis').count(), 0)

    def test_un_devis_trop_ancien_bascule_en_dormance(self):
        """Toutes les touches (J1…J14) sont passées : cette cadence ne
        relancerait personne. Elle est DÉFAITE et le lead part en dormance."""
        lead = self._lead('Vieux devis', stage=stages.QUOTE_SENT, jours=40)
        self._devis(lead, jours=30)
        rapport = self._placer()
        self.assertEqual(self._codes(rapport), {'dormant_devis': 1})
        lead.refresh_from_db()
        self.assertEqual(
            lead.relance_etapes.filter(cadence='apres_devis').count(), 0)
        self.assertEqual(lead.stage, stages.COLD)
        self.assertIn('Devis sans suite', lead.tags or '')

    def test_la_bascule_ne_laisse_pas_de_rappel_fantome(self):
        lead = self._lead('Vieux devis', stage=stages.QUOTE_SENT, jours=40)
        self._devis(lead, jours=30)
        self._placer()
        lead.refresh_from_db()
        reveil = self._reveils(lead)[0]
        self.assertEqual(lead.relance_date, reveil.due_date)

    def test_un_devis_accepte_nest_jamais_relance(self):
        lead = self._lead('Signé bientôt', stage=stages.QUOTE_SENT, jours=5)
        self._devis(lead, statut='accepte', jours=5)
        rapport = self._placer()
        self.assertEqual(rapport['ignores']['devis_accepte_non_signe'], 1)
        self.assertEqual(rapport['a_placer'], 0)
        self.assertEqual(lead.relance_etapes.count(), 0)


class DecisionDormantTests(_PlacementBase):
    slug = 'mry30-dormant'

    def test_un_dossier_jamais_chiffre_part_au_froid_etiquete(self):
        lead = self._lead('Dormant', stage=stages.NEW, jours=60)
        rapport = self._placer()
        self.assertEqual(self._codes(rapport), {'dormant_jamais_chiffre': 1})
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.COLD)
        self.assertIn('Jamais chiffré', lead.tags or '')
        self.assertFalse(lead.perdu)          # Froid = parking, pas perte.

    def test_le_dormant_jamais_chiffre_garde_les_gabarits_sans_devis(self):
        lead = self._lead('Dormant', stage=stages.NEW, jours=60)
        self._placer()
        self.assertEqual([e.template_cle for e in self._reveils(lead)],
                         ['reveil_a2', 'reveil_a3'])

    def test_le_dormant_devis_parle_bien_dune_proposition_recue(self):
        """Ces leads ONT reçu un devis — dans Odoo — même sans devis ERP :
        `_adapter_gabarits_reveil`, qui ne lit que les devis ERP, choisirait
        sinon le message « jamais chiffré », faux pour eux."""
        lead = self._lead('Sans suite', stage=stages.FOLLOW_UP, jours=60)
        rapport = self._placer()
        self.assertEqual(self._codes(rapport), {'dormant_devis': 1})
        self.assertEqual([e.template_cle for e in self._reveils(lead)],
                         ['reveil_a1', 'reveil_a3'])

    def test_deux_reveils_sont_poses(self):
        lead = self._lead('Dormant', stage=stages.NEW, jours=60)
        self._placer()
        self.assertEqual(len(self._reveils(lead)), 2)


class PerimetreTests(_PlacementBase):
    slug = 'mry30-perimetre'

    def test_le_miroir_odoo_est_inclus(self):
        """Décision fondateur 06/09 : la garde « miroir » de
        `_garde_cadence_contact` protège un démarrage AUTOMATIQUE, pas un
        placement demandé sur ce même portefeuille."""
        self._lead('Miroir', stage=stages.NEW, jours=2,
                   source=Lead.Source.ODOO_IMPORT_TEST)
        rapport = self._placer()
        self.assertEqual(rapport['total_candidats'], 1)
        self.assertEqual(self._codes(rapport), {'contact_complete': 1})

    def test_un_lead_deja_en_cadence_est_ignore(self):
        lead = self._lead('Déjà suivi', stage=stages.NEW, jours=2)
        initialiser_plan_relance(lead, self.acteur, depart=MERCREDI,
                                 cadence='contact')
        rapport = self._placer()
        self.assertEqual(rapport['ignores']['deja_en_cadence'], 1)
        self.assertEqual(rapport['a_placer'], 0)

    def test_froid_signe_perdu_archive_et_stop_sont_hors_candidats(self):
        self._lead('Froid', stage=stages.COLD)
        self._lead('Signé', stage=stages.SIGNED)
        self._lead('Perdu', stage=stages.NEW, perdu=True)
        self._lead('Archivé', stage=stages.NEW, is_archived=True)
        self._lead('Stop', stage=stages.NEW, ne_plus_contacter=True)
        rapport = self._placer()
        self.assertEqual(rapport['total_candidats'], 0)
        self.assertEqual(rapport['par_etape'], [])

    def test_lapercu_porte_les_champs_du_contrat(self):
        lead = self._lead('Neuf', stage=stages.NEW, jours=2)
        ligne = self._placer(apply=False)['apercu'][0]
        self.assertEqual(
            set(ligne),
            {'lead', 'nom', 'stage_libelle', 'source', 'ancre', 'jours',
             'code', 'cadence', 'prochaine_touche', 'prochaine_le'})
        self.assertEqual(ligne['lead'], lead.pk)
        self.assertEqual(ligne['stage_libelle'], stages.STAGE_LABELS[stages.NEW])
        self.assertEqual(ligne['ancre'], '2026-09-07')
        self.assertEqual(ligne['jours'], 2)
        self.assertTrue(ligne['prochaine_touche'])


# ═══════════════════════════════════════════════════════════════════════════
# 4. L'aperçu, l'idempotence, l'étalement
# ═══════════════════════════════════════════════════════════════════════════

class ApercuTests(_PlacementBase):
    slug = 'mry30-apercu'

    def setUp(self):
        super().setUp()
        self.neuf = self._lead('Neuf', stage=stages.NEW, jours=2)
        self.dormant = self._lead('Dormant', stage=stages.NEW, jours=60)

    def test_lapercu_necrit_rien(self):
        avant = (RelanceEtape.objects.count(), LeadActivity.objects.count())
        rapport = self._placer(apply=False)
        self.assertEqual(rapport['applique'], 0)
        self.assertFalse(rapport['apply'])
        self.assertEqual(
            (RelanceEtape.objects.count(), LeadActivity.objects.count()),
            avant)

    def test_lapercu_ne_deplace_ni_letape_ni_les_etiquettes(self):
        self._placer(apply=False)
        self.dormant.refresh_from_db()
        self.assertEqual(self.dormant.stage, stages.NEW)
        self.assertEqual(self.dormant.tags or '', '')

    def test_lapercu_annonce_exactement_ce_que_apply_fera(self):
        """La leçon de MRY23 : un dry-run qui recalcule « à côté » annonce
        des dossiers que --apply n'atteint jamais."""
        apercu = self._placer(apply=False)
        applique = self._placer(apply=True)
        for cle in ('total_candidats', 'a_placer', 'ignores', 'par_etape',
                    'apercu', 'reveils_jusqu_au'):
            self.assertEqual(apercu[cle], applique[cle], cle)

    def test_le_rapport_porte_les_cles_du_contrat(self):
        self.assertEqual(
            set(self._placer(apply=False)),
            {'apply', 'total_candidats', 'a_placer', 'ignores', 'par_etape',
             'apercu', 'reveils_jusqu_au', 'applique', 'erreurs', 'restants'})

    def test_sans_dormant_reveils_jusqu_au_est_nul(self):
        self.dormant.delete()
        self.assertIsNone(self._placer(apply=False)['reveils_jusqu_au'])


class IdempotenceTests(_PlacementBase):
    slug = 'mry30-idem'

    def test_un_second_passage_ne_replace_personne(self):
        for rang in range(3):
            self._lead(f'Lead {rang}', stage=stages.NEW, jours=2)
        premier = self._placer()
        self.assertEqual(premier['applique'], 3)
        touches = RelanceEtape.objects.count()

        second = self._placer()
        self.assertEqual(second['a_placer'], 0)
        self.assertEqual(second['ignores']['deja_en_cadence'], 3)
        self.assertEqual(second['applique'], 0)
        self.assertEqual(RelanceEtape.objects.count(), touches)


class EtalementTests(_PlacementBase):
    slug = 'mry30-etalement'

    def test_les_reveils_partent_a_huit_par_jour_ouvre(self):
        """Lancer 200 réveils le même matin ferait partir 200 messages en
        rafale depuis le même numéro — le meilleur moyen d'être signalé."""
        leads = [self._lead(f'Dormant {rang}', stage=stages.NEW,
                            jours=60 + rang)
                 for rang in range(PLACEMENT_REVEILS_PAR_JOUR + 2)]
        self._placer()

        premieres = [
            self._reveils(lead)[0].due_at.astimezone(horaires.CASABLANCA)
            for lead in leads]
        # Les ancres les plus RÉCENTES d'abord : `leads[0]` (60 jours) occupe
        # le premier créneau, `leads[9]` (69 jours) le dernier.
        self.assertEqual(
            [(quand.date(), quand.hour, quand.minute) for quand in premieres],
            [(MERCREDI.date(), 10, 0), (MERCREDI.date(), 10, 20),
             (MERCREDI.date(), 10, 40), (MERCREDI.date(), 11, 0),
             (MERCREDI.date(), 11, 20), (MERCREDI.date(), 11, 40),
             (MERCREDI.date(), 12, 0), (MERCREDI.date(), 12, 20),
             (JEUDI, 10, 0), (JEUDI, 10, 20)])

    def test_reveils_jusqu_au_nomme_le_dernier_creneau(self):
        for rang in range(PLACEMENT_REVEILS_PAR_JOUR + 1):
            self._lead(f'Dormant {rang}', stage=stages.NEW, jours=60 + rang)
        rapport = self._placer()
        self.assertEqual(rapport['reveils_jusqu_au'], JEUDI.isoformat())

    def test_lance_l_apres_midi_l_etalement_commence_le_lendemain(self):
        """À 15 h, les créneaux 10 h-12 h 20 du jour sont derrière nous : la
        première touche part le prochain jour ouvré — jamais « en retard »
        à la seconde où elle naît."""
        lead = self._lead('Dormant tardif', stage=stages.NEW, jours=60)
        with frozen(MERCREDI.replace(hour=15, minute=0)):
            self._placer()
        quand = self._reveils(lead)[0].due_at.astimezone(horaires.CASABLANCA)
        self.assertEqual((quand.date(), quand.hour, quand.minute),
                         (JEUDI, 10, 0))


# ═══════════════════════════════════════════════════════════════════════════
# 5. La porte HTTP et la porte ligne de commande
# ═══════════════════════════════════════════════════════════════════════════

class EndpointTests(_PlacementBase):
    slug = 'mry30-endpoint'

    def setUp(self):
        super().setUp()
        self._lead('Neuf', stage=stages.NEW, jours=2)

    def test_un_role_simple_est_refuse(self):
        simple = User.objects.create_user(
            username=f'{self.slug}-simple', password='x',
            role_legacy='normal', company=self.company)
        resp = self._api(simple).post(PLACEMENT_URL, {}, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_le_responsable_recoit_lapercu(self):
        resp = self._api().post(PLACEMENT_URL, {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(resp.data['apply'])
        self.assertEqual(resp.data['applique'], 0)
        self.assertEqual(RelanceEtape.objects.count(), 0)

    def test_la_reponse_a_la_forme_de_lechantillon(self):
        import json
        from pathlib import Path
        echantillon = json.loads(
            (Path(__file__).resolve().parent / 'contract_samples'
             / 'placement_anciens_leads.json').read_text(encoding='utf-8'))
        resp = self._api().post(PLACEMENT_URL, {}, format='json')
        self.assertEqual(set(resp.data), set(echantillon['exemple']))

    def test_apply_true_applique_vraiment(self):
        resp = self._api().post(PLACEMENT_URL, {'apply': True}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['apply'])
        self.assertEqual(resp.data['applique'], 1)
        self.assertGreater(RelanceEtape.objects.count(), 0)

    def test_une_limite_hors_bornes_est_refusee(self):
        """`limite` borne le nombre d'écritures d'UNE requête : 0 ne placerait
        rien pour toujours, 201 ramène le cas qui a produit le 499."""
        for valeur in (0, 201):
            resp = self._api().post(
                PLACEMENT_URL, {'apply': True, 'limite': valeur},
                format='json')
            self.assertEqual(resp.status_code, 400, valeur)
            self.assertIn('limite', resp.data)
        self.assertEqual(RelanceEtape.objects.count(), 0)

    def test_la_limite_borne_le_lot_et_restants_annonce_la_suite(self):
        self._lead('Second', stage=stages.NEW, jours=3)
        resp = self._api().post(PLACEMENT_URL, {'apply': True, 'limite': 1},
                                format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['a_placer'], 2)
        self.assertEqual(resp.data['applique'], 1)
        self.assertEqual(resp.data['restants'], 1)

    def test_un_apply_non_booleen_est_refuse(self):
        resp = self._api().post(PLACEMENT_URL, {'apply': 'oui'},
                                format='json')
        self.assertEqual(resp.status_code, 400)


class CommandeTests(_PlacementBase):
    slug = 'mry30-commande'

    def setUp(self):
        super().setUp()
        self._lead('Neuf', stage=stages.NEW, jours=2)
        self._lead('Dormant', stage=stages.NEW, jours=60)

    def _appeler(self, *args):
        sortie = io.StringIO()
        call_command('placer_anciens_leads', '--company', self.company.slug,
                     *args, stdout=sortie)
        return sortie.getvalue()

    def test_le_dry_run_imprime_les_totaux_sans_rien_ecrire(self):
        texte = self._appeler()
        self.assertIn('Candidats : 2', texte)
        self.assertIn('à placer : 2', texte)
        self.assertIn('contact_complete', texte)
        self.assertIn('dormant_jamais_chiffre', texte)
        self.assertIn('AUCUNE écriture', texte)
        self.assertEqual(RelanceEtape.objects.count(), 0)

    def test_apply_ecrit_et_le_dit(self):
        texte = self._appeler('--apply')
        self.assertIn('2 lead(s) placé(s).', texte)
        self.assertGreater(RelanceEtape.objects.count(), 0)

    def test_apply_par_lots_boucle_jusqu_a_restants_zero(self):
        """La commande suit la même découpe que l'écran : un lot par appel,
        et elle rappelle tant qu'il reste quelque chose. Sans la boucle,
        `--apply --limite 2` laisserait 3 dossiers non placés en silence."""
        for rang in range(3):
            self._lead(f'Dormant {rang}', stage=stages.NEW, jours=70 + rang)
        texte = self._appeler('--apply', '--limite', '2')
        lots = [ligne for ligne in texte.splitlines()
                if ligne.startswith('Lot ')]
        self.assertEqual(len(lots), 3, texte)
        self.assertTrue(lots[-1].endswith('restants 0.'), lots)
        self.assertIn('5 lead(s) placé(s).', texte)
        self.assertEqual(
            Lead.objects.filter(company=self.company,
                                relance_etapes__isnull=True).count(), 0)

    def test_une_limite_hors_bornes_est_refusee(self):
        with self.assertRaises(CommandError):
            call_command('placer_anciens_leads', '--company',
                         self.company.slug, '--apply', '--limite', '0',
                         stdout=io.StringIO())

    def test_une_societe_introuvable_est_refusee(self):
        with self.assertRaises(CommandError):
            call_command('placer_anciens_leads', '--company', 'inexistante',
                         stdout=io.StringIO())

    def test_plusieurs_societes_exigent_le_choix(self):
        """`--company` n'est facultatif que là où il n'y a aucun choix à
        faire : placer des centaines de leads dans la mauvaise société ne se
        défait pas d'un clic."""
        _company(f'{self.slug}-bis')
        with self.assertRaises(CommandError):
            call_command('placer_anciens_leads', stdout=io.StringIO())


# ═══════════════════════════════════════════════════════════════════════════
# 6. Le calcul d'échéances, extrait — et l'aperçu qui s'en sert
# ═══════════════════════════════════════════════════════════════════════════

class CalculEcheancesTests(_Base):
    """`calculer_echeances_cadence` est la fonction que l'aperçu du placement
    utilise pour DATER une cadence sans l'écrire. Si elle divergeait d'un
    cheveu de ce qu'`initialiser_plan_relance` crée, l'aperçu recommencerait à
    mentir — la faute même que le dry-run en transaction annulée évitait."""

    slug = 'mry30-echeances'

    def test_le_calcul_pur_donne_exactement_les_echeances_ecrites(self):
        lead = self._lead('Neuf', stage=stages.NEW, jours=2)
        calcule = [echeance for _, echeance in calculer_echeances_cadence(
            lead, 'contact', MERCREDI)]
        ecrites = [etape.due_at for etape in initialiser_plan_relance(
            lead, self.acteur, cadence='contact', depart=MERCREDI)]
        self.assertEqual(ecrites, calcule)
        self.assertGreater(len(calcule), 1)

    def test_la_touche_dominicale_est_datee_a_lidentique(self):
        """Le barreau `dimanche_famille` est le seul qui ne suit pas la
        formule : il se PLACE sur un dimanche. C'est donc lui qu'un calcul
        « à côté » raterait en premier."""
        lead = self._lead('Famille', stage=stages.QUOTE_SENT, jours=1,
                          tags='Décision à plusieurs')
        calcule = [echeance for _, echeance in calculer_echeances_cadence(
            lead, 'apres_devis', MERCREDI)]
        ecrites = [etape.due_at for etape in initialiser_plan_relance(
            lead, self.acteur, cadence='apres_devis', depart=MERCREDI)]
        self.assertEqual(ecrites, calcule)
        self.assertTrue(
            any(echeance.astimezone(horaires.CASABLANCA).weekday() == 6
                for echeance in calcule))

    def test_le_calcul_pur_necrit_aucune_touche(self):
        lead = self._lead('Neuf', stage=stages.NEW, jours=2)
        calculer_echeances_cadence(lead, 'contact', MERCREDI)
        self.assertEqual(RelanceEtape.objects.count(), 0)


class ApercuPurTests(_PlacementBase):
    """L'aperçu ne passe plus par une exécution annulée : il CALCULE."""

    slug = 'mry30-apercu-pur'

    def setUp(self):
        super().setUp()
        self.neuf = self._lead('Neuf', stage=stages.NEW, jours=2)
        self.suivi = self._lead('Suivi', stage=stages.CONTACTED, jours=10)
        self.dormant = self._lead('Dormant', stage=stages.NEW, jours=60)

    def test_lapercu_ne_cree_ni_touche_ni_ligne_de_chatter(self):
        avant = (RelanceEtape.objects.count(), LeadActivity.objects.count())
        rapport = self._placer(apply=False)
        self.assertEqual(
            (RelanceEtape.objects.count(), LeadActivity.objects.count()),
            avant)
        self.assertEqual(rapport['applique'], 0)
        self.assertEqual(rapport['erreurs'], 0)

    def test_deux_apercus_de_suite_annoncent_la_meme_chose(self):
        """Rien n'ayant été écrit, le second aperçu doit être le premier —
        au caractère près. Un aperçu qui écrivait « un peu » (un gabarit, une
        touche oubliée) se trahirait ici."""
        premier = self._placer(apply=False)
        second = self._placer(apply=False)
        self.assertEqual(premier['apercu'], second['apercu'])
        self.assertEqual(premier['par_etape'], second['par_etape'])
        self.assertEqual(premier['reveils_jusqu_au'],
                         second['reveils_jusqu_au'])

    def test_en_apercu_restants_vaut_a_placer(self):
        rapport = self._placer(apply=False)
        self.assertEqual(rapport['a_placer'], 3)
        self.assertEqual(rapport['restants'], rapport['a_placer'])

    def test_lapercu_date_chacune_de_ses_lignes(self):
        for ligne in self._placer(apply=False)['apercu']:
            self.assertTrue(ligne['prochaine_touche'], ligne)
            self.assertTrue(ligne['prochaine_le'], ligne)


class ApercuPositionneTests(_PlacementBase):
    slug = 'mry30-apercu-positionne'

    def test_la_ligne_positionnee_date_la_premiere_touche_non_passee(self):
        """La cadence part d'il y a dix jours : ses premières touches sont
        derrière nous. L'aperçu doit annoncer la première touche À VENIR — et
        exactement celle que l'application créera ensuite."""
        lead = self._lead('Suivi', stage=stages.CONTACTED, jours=10)
        ligne = self._placer(apply=False)['apercu'][0]
        self.assertEqual(ligne['code'], 'contact_positionne')

        self._placer(apply=True)
        touche = (lead.relance_etapes
                  .filter(statut=RelanceEtape.Statut.A_FAIRE)
                  .order_by('due_at').first())
        self.assertIsNotNone(touche)
        self.assertGreaterEqual(touche.due_at, MERCREDI)
        self.assertEqual(ligne['prochaine_touche'], touche.libelle)
        self.assertEqual(
            ligne['prochaine_le'],
            touche.due_at.astimezone(horaires.CASABLANCA).isoformat())

    def test_une_cadence_entierement_passee_est_annoncee_dormante(self):
        """La bascule appartient à la DÉCISION : annoncée « après devis » puis
        écrite « dormant », la carte montrerait deux chiffres différents pour
        le même clic."""
        lead = self._lead('Vieux devis', stage=stages.QUOTE_SENT, jours=40)
        self._devis(lead, jours=30)
        apercu = self._placer(apply=False)
        self.assertEqual(self._codes(apercu), {'dormant_devis': 1})
        self.assertEqual(apercu['apercu'][0]['cadence'], 'reveil')
        self.assertEqual(self._codes(self._placer(apply=True)),
                         {'dormant_devis': 1})


class LotsTests(_PlacementBase):
    """L'application par lots — et la continuité des créneaux entre eux."""

    slug = 'mry30-lots'

    def setUp(self):
        super().setUp()
        # Ancres décroissantes : `dormants[0]` (60 j) prend le premier
        # créneau, `dormants[4]` (64 j) le dernier.
        self.dormants = [
            self._lead(f'Dormant {rang}', stage=stages.NEW, jours=60 + rang)
            for rang in range(5)]

    def _creneau(self, rang):
        return datetime.datetime.combine(
            MERCREDI.date(), PLACEMENT_CRENEAUX[rang],
            tzinfo=horaires.CASABLANCA)

    def _premiere(self, lead):
        return self._reveils(lead)[0].due_at.astimezone(horaires.CASABLANCA)

    def test_un_lot_de_deux_place_deux_leads_et_annonce_le_reste(self):
        rapport = self._placer(limite=2)
        self.assertEqual(rapport['a_placer'], 5)
        self.assertEqual(rapport['applique'], 2)
        self.assertEqual(rapport['erreurs'], 0)
        self.assertEqual(rapport['restants'], 3)
        self.assertEqual([self._premiere(lead) for lead in self.dormants[:2]],
                         [self._creneau(0), self._creneau(1)])
        self.assertEqual(
            RelanceEtape.objects.filter(lead__in=self.dormants[2:]).count(), 0)

    def test_le_lot_suivant_prolonge_la_file_au_lieu_de_la_recommencer(self):
        """LE piège des lots : sans compter les réveils déjà posés, les trois
        derniers dormants repartiraient au créneau de 10 h — cinq messages
        empilés sur deux créneaux, depuis le même numéro."""
        self._placer(limite=2)
        rapport = self._placer(limite=40)
        self.assertEqual(rapport['a_placer'], 3)
        self.assertEqual(rapport['applique'], 3)
        self.assertEqual(rapport['restants'], 0)
        self.assertEqual([self._premiere(lead) for lead in self.dormants],
                         [self._creneau(rang) for rang in range(5)])

    def test_un_apercu_entre_deux_lots_annonce_le_prochain_creneau_libre(self):
        self._placer(limite=2)
        ligne = self._placer(apply=False)['apercu'][0]
        self.assertEqual(ligne['lead'], self.dormants[2].pk)
        self.assertEqual(ligne['prochaine_le'], self._creneau(2).isoformat())
        self.assertEqual(ligne['prochaine_touche'], 'Réveil J30')

    def test_le_lot_ne_deborde_pas_sur_le_jour_suivant_sans_raison(self):
        """Cinq dormants tiennent dans les huit créneaux d'un jour ouvré :
        aucun ne doit partir au lendemain."""
        self._placer(limite=40)
        self.assertEqual(
            {self._premiere(lead).date() for lead in self.dormants},
            {MERCREDI.date()})
