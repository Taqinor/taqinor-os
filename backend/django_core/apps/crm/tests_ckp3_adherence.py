"""CKP3 — les deux agrégats du cockpit CRM « suivre les étapes ».

Commande fondateur du 10/09/2026 : « moi et Meryem on ne voit pas assez ce
qu'elle fait et si elle le fait bien ». Ce fichier verrouille les trois choses
qui font qu'un tel chiffre est honnête — ou ne vaut rien :

  * une ANNULATION MOTEUR (CKP1) n'est JAMAIS comptée comme un saut humain, ni
    au dénominateur de l'adhérence : une cadence arrêtée parce que le client a
    répondu n'est pas un manquement, et un tableau qui la compte ainsi accuse
    quelqu'un à tort ;
  * dénominateur 0 → ``null``, jamais un 0 % qui se lirait comme un échec là
    où il n'y a rien à mesurer ;
  * multi-tenant ET portée : une société ne voit pas les touches de l'autre,
    et « mes stats » ne parlent que des leads dont je suis responsable.

Le temps est GELÉ : « à l'heure », « en retard » et « les 7 derniers jours »
sont exactement les questions qu'une horloge vivante rend instables.
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
from apps.crm.selectors import kpi_adherence, mes_stats_relance
from apps.parametres.models import CompanyProfile

User = get_user_model()

#: Jeudi 10 septembre 2026, 12 h à Casablanca — jour ouvré, en pleine fenêtre.
MAINTENANT = datetime.datetime(2026, 9, 10, 12, 0, tzinfo=horaires.CASABLANCA)
AUJOURDHUI = MAINTENANT.date()

ADHERENCE_URL = '/api/django/crm/relance-etapes/kpi-adherence/'
MES_STATS_URL = '/api/django/crm/relance-etapes/mes-stats/'


def _company(slug):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    CompanyProfile.objects.get_or_create(company=company)
    return company


def _quand(jours_avant, heure=10):
    return datetime.datetime.combine(
        AUJOURDHUI - datetime.timedelta(days=jours_avant),
        datetime.time(heure, 0), tzinfo=horaires.CASABLANCA)


class _Base(TestCase):
    slug = 'ckp3'

    def setUp(self):
        gel = frozen(MAINTENANT)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = _company(self.slug)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-resp', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Aziz', prenom='Benali',
            ville='Bouskoura', stage=stages.CONTACTED, owner=self.acteur)

    def _touche(self, *, statut, due_jours, traite_jours=None, ordre=1,
                canal=RelanceEtape.Canal.APPEL, libelle='Appel d\'ouverture',
                lead=None, note='', traite_par=-1):
        due = _quand(due_jours)
        return RelanceEtape.objects.create(
            company=self.company, lead=lead or self.lead, cadence='contact',
            ordre=ordre, due_at=due, due_date=due.date(), canal=canal,
            libelle=libelle, statut=statut, note=note,
            traite_le=(None if traite_jours is None else _quand(traite_jours)),
            traite_par=(self.acteur if traite_par == -1 else traite_par))

    def _api(self, user=None):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer '
                               f'{AccessToken.for_user(user or self.acteur)}')
        return api


class FormeDuContratTests(_Base):
    slug = 'ckp3-contrat'

    def test_kpi_adherence_a_la_forme_de_lechantillon(self):
        import json
        from pathlib import Path
        echantillon = json.loads(
            (Path(__file__).resolve().parent / 'contract_samples'
             / 'kpi_adherence.json').read_text(encoding='utf-8'))
        resp = self._api().get(ADHERENCE_URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(set(resp.data), set(echantillon['exemple']))
        self.assertEqual(set(resp.data['vitesse_premier_contact']),
                         set(echantillon['exemple']
                             ['vitesse_premier_contact']))

    def test_mes_stats_a_la_forme_de_lechantillon(self):
        import json
        from pathlib import Path
        echantillon = json.loads(
            (Path(__file__).resolve().parent / 'contract_samples'
             / 'mes_stats_relance.json').read_text(encoding='utf-8'))
        resp = self._api().get(MES_STATS_URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(set(resp.data), set(echantillon['exemple']))

    def test_les_deux_sont_lisibles_par_TOUS_les_roles(self):
        """Décision fondateur de TRANSPARENCE : pas de tableau caché sur
        Meryem — un rôle normal lit exactement les mêmes chiffres."""
        simple = User.objects.create_user(
            username=f'{self.slug}-simple', password='x',
            role_legacy='normal', company=self.company)
        for url in (ADHERENCE_URL, MES_STATS_URL):
            resp = self._api(simple).get(url)
            self.assertEqual(resp.status_code, 200, (url, resp.data))

    def test_un_nombre_de_jours_invalide_est_NORMALISE_jamais_refuse(self):
        """« Normaliser plutôt que refuser quand l'intention est claire »
        (règle fondateur 08/09) : ``jours`` est un paramètre d'AFFICHAGE — un
        tableau de bord ne se casse pas dessus. Hors bornes, il est ramené
        dans 1-365 ; illisible, il retombe sur la fenêtre par défaut. La
        période effectivement calculée est TOUJOURS annoncée dans la réponse
        (`periode_jours`), jamais laissée deviner."""
        for valeur, attendu in (('0', 1), ('400', 365), ('trente', 30)):
            resp = self._api().get(ADHERENCE_URL, {'jours': valeur})
            self.assertEqual(resp.status_code, 200, valeur)
            self.assertEqual(resp.data['periode_jours'], attendu, valeur)


class FormulesTests(_Base):
    slug = 'ckp3-formules'

    def setUp(self):
        super().setUp()
        # Trois touches FAITES : deux le jour dû, une en retard d'un jour.
        self._touche(statut='fait', due_jours=5, traite_jours=5)
        self._touche(statut='fait', due_jours=4, traite_jours=4, ordre=2,
                     canal=RelanceEtape.Canal.WHATSAPP,
                     libelle="Message d'identité")
        self._touche(statut='fait', due_jours=3, traite_jours=2, ordre=3)
        # Un saut HUMAIN — il compte au dénominateur (la touche n'a pas été
        # faite) et dans sa propre colonne.
        self._touche(statut='sautee', due_jours=3, traite_jours=3, ordre=4)
        # Deux ANNULATIONS MOTEUR — jamais comptées nulle part ailleurs.
        for ordre in (5, 6):
            self._touche(statut='annulee', due_jours=2, traite_jours=2,
                         ordre=ordre, note='joint', traite_par=None)

    def test_a_lheure_pct_compte_le_jour_du_jamais_la_minute(self):
        kpi = kpi_adherence(self.company, self.acteur, 30)
        # 3 faites + 1 sautée humaine = 4 closes ; 2 à l'heure.
        self.assertEqual(kpi['touches_faites'], 3)
        self.assertEqual(kpi['a_lheure_pct'], 50.0)

    def test_une_annulation_moteur_nest_jamais_une_sautee(self):
        kpi = kpi_adherence(self.company, self.acteur, 30)
        self.assertEqual(kpi['sautees_humaines'], 1)
        self.assertEqual(kpi['annulees_moteur'], 2)

    def test_les_annulations_moteur_sortent_du_denominateur(self):
        """LE point du lot : sans cette exclusion, les deux touches annulées
        parce que le client a répondu feraient tomber l'adhérence de 50 % à
        33 % — un manquement inventé de toutes pièces."""
        kpi = kpi_adherence(self.company, self.acteur, 30)
        self.assertEqual(kpi['a_lheure_pct'], round(100.0 * 2 / 4, 1))

    def test_le_drop_off_par_touche_separe_les_deux_colonnes(self):
        kpi = kpi_adherence(self.company, self.acteur, 30)
        par_ordre = {ligne['ordre']: ligne for ligne in kpi['par_etape']}
        self.assertEqual(par_ordre[1]['faites'], 1)
        self.assertEqual(par_ordre[1]['a_lheure_pct'], 100.0)
        self.assertEqual(par_ordre[3]['a_lheure_pct'], 0.0)
        self.assertEqual(par_ordre[4]['sautees_humaines'], 1)
        self.assertEqual(par_ordre[4]['faites'], 0)
        self.assertEqual(par_ordre[5]['annulees_moteur'], 1)
        self.assertEqual(par_ordre[5]['a_lheure_pct'], None)

    def test_le_canal_et_le_libelle_voyagent_avec_la_touche(self):
        kpi = kpi_adherence(self.company, self.acteur, 30)
        par_ordre = {ligne['ordre']: ligne for ligne in kpi['par_etape']}
        self.assertEqual(par_ordre[2]['canal'], 'whatsapp')
        self.assertEqual(par_ordre[2]['libelle'], "Message d'identité")

    def test_la_tendance_hebdo_est_datee_au_lundi(self):
        kpi = kpi_adherence(self.company, self.acteur, 30)
        self.assertTrue(kpi['tendance_a_lheure'])
        for point in kpi['tendance_a_lheure']:
            jour = datetime.date.fromisoformat(point['semaine'])
            self.assertEqual(jour.weekday(), 0, point)


class DenominateurNulTests(_Base):
    slug = 'ckp3-vide'

    def test_aucune_touche_rend_null_jamais_zero_pourcent(self):
        """« Pas encore de données » n'est pas « 0 % » : un 0 % inventé se
        lirait comme un échec là où il n'y a rien à mesurer."""
        kpi = kpi_adherence(self.company, self.acteur, 30)
        self.assertIsNone(kpi['a_lheure_pct'])
        self.assertEqual(kpi['touches_faites'], 0)
        self.assertEqual(kpi['sautees_humaines'], 0)
        self.assertEqual(kpi['annulees_moteur'], 0)
        self.assertIsNone(kpi['vitesse_premier_contact']['mediane_heures'])
        self.assertEqual(kpi['par_etape'], [])
        self.assertEqual(kpi['tendance_a_lheure'], [])

    def test_mes_stats_rend_null_quand_rien_na_ete_traite(self):
        stats = mes_stats_relance(self.company, self.acteur)
        self.assertIsNone(stats['a_lheure_7j_pct'])
        self.assertEqual(stats['a_faire_maintenant'], 0)
        self.assertEqual(stats['en_retard'], 0)
        self.assertEqual(stats['cadences_completees_14j'], 0)

    def test_la_conversion_par_stage_suit_les_cles_de_STAGES_py(self):
        kpi = kpi_adherence(self.company, self.acteur, 30)
        rendues = [ligne['stage'] for ligne in kpi['conversion_par_stage']]
        attendues = [s for s in stages.STAGES if s != stages.COLD]
        self.assertEqual(rendues, attendues)

    def test_un_stage_sans_entrant_rend_un_taux_null(self):
        kpi = kpi_adherence(self.company, self.acteur, 30)
        par_stage = {ligne['stage']: ligne
                     for ligne in kpi['conversion_par_stage']}
        # Le lead de `_Base` est à CONTACTED : personne n'a atteint SIGNED.
        self.assertEqual(par_stage[stages.SIGNED]['entres'], 0)
        self.assertIsNone(par_stage[stages.SIGNED]['taux_pct'])
        self.assertEqual(par_stage[stages.NEW]['entres'], 1)
        self.assertEqual(par_stage[stages.CONTACTED]['entres'], 1)


class LeadsQuiDecrochentTests(_Base):
    slug = 'ckp3-decroche'

    def test_un_lead_dont_la_touche_est_en_retard_est_LISTE(self):
        """Une LISTE actionnable, jamais un simple compte : Meryem doit
        pouvoir cliquer sur le dossier, pas lire « 6 »."""
        self._touche(statut='a_faire', due_jours=1, traite_jours=None,
                     traite_par=None)
        kpi = kpi_adherence(self.company, self.acteur, 30)
        self.assertEqual(len(kpi['leads_sans_touche']), 1)
        ligne = kpi['leads_sans_touche'][0]
        self.assertEqual(ligne['lead_id'], self.lead.pk)
        self.assertEqual(ligne['nom'], 'Aziz Benali')
        self.assertEqual(ligne['ville'], 'Bouskoura')
        self.assertEqual(ligne['prochaine_touche'], "Appel d'ouverture")
        self.assertGreater(ligne['en_retard_depuis_heures'], 0)

    def test_un_lead_dont_la_touche_est_a_venir_nest_pas_liste(self):
        due = _quand(-3)
        RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='contact', ordre=1,
            due_at=due, due_date=due.date(), canal=RelanceEtape.Canal.APPEL,
            libelle='Appel', statut='a_faire')
        kpi = kpi_adherence(self.company, self.acteur, 30)
        self.assertEqual(kpi['leads_sans_touche'], [])

    def test_un_lead_actif_SANS_aucune_touche_ouverte_est_liste(self):
        kpi = kpi_adherence(self.company, self.acteur, 30)
        self.assertEqual(len(kpi['leads_sans_touche']), 1)
        self.assertIsNone(kpi['leads_sans_touche'][0]['prochaine_touche'])

    def test_un_lead_signe_ou_froid_nest_jamais_liste(self):
        for etape in (stages.SIGNED, stages.COLD):
            self.lead.stage = etape
            self.lead.save(update_fields=['stage'])
            kpi = kpi_adherence(self.company, self.acteur, 30)
            self.assertEqual(kpi['leads_sans_touche'], [], etape)

    def test_les_retards_ouverts_sont_comptes_a_part(self):
        self._touche(statut='a_faire', due_jours=1, traite_jours=None,
                     traite_par=None)
        kpi = kpi_adherence(self.company, self.acteur, 30)
        self.assertEqual(kpi['touches_en_retard_ouvertes'], 1)


class MesStatsTests(_Base):
    slug = 'ckp3-messtats'

    def setUp(self):
        super().setUp()
        self.collegue = User.objects.create_user(
            username=f'{self.slug}-collegue', password='x',
            role_legacy='responsable', company=self.company)
        self.lead_collegue = Lead.objects.create(
            company=self.company, nom='Salma', stage=stages.CONTACTED,
            owner=self.collegue)

    def test_mes_tuiles_ne_comptent_que_MES_leads(self):
        """Actionnables, jamais comparatives : la touche du collègue n'entre
        dans aucune de mes tuiles."""
        self._touche(statut='a_faire', due_jours=1, traite_par=None)
        self._touche(statut='a_faire', due_jours=1, traite_par=None,
                     lead=self.lead_collegue, ordre=2)
        stats = mes_stats_relance(self.company, self.acteur)
        self.assertEqual(stats['en_retard'], 1)
        self.assertEqual(stats['a_faire_maintenant'], 1)

    def test_mon_a_lheure_7j_ignore_les_annulations_moteur(self):
        self._touche(statut='fait', due_jours=2, traite_jours=2)
        self._touche(statut='fait', due_jours=2, traite_jours=1, ordre=2)
        self._touche(statut='annulee', due_jours=2, traite_jours=2, ordre=3,
                     note='lead signé', traite_par=None)
        stats = mes_stats_relance(self.company, self.acteur)
        self.assertEqual(stats['a_lheure_7j_pct'], 50.0)

    def test_une_cadence_menee_a_terme_est_comptee_une_fois(self):
        self._touche(statut='fait', due_jours=3, traite_jours=3)
        self._touche(statut='fait', due_jours=2, traite_jours=2, ordre=2)
        stats = mes_stats_relance(self.company, self.acteur)
        self.assertEqual(stats['cadences_completees_14j'], 1)

    def test_une_touche_encore_ouverte_empeche_de_compter_la_cadence(self):
        self._touche(statut='fait', due_jours=3, traite_jours=3)
        self._touche(statut='a_faire', due_jours=1, ordre=2, traite_par=None)
        stats = mes_stats_relance(self.company, self.acteur)
        self.assertEqual(stats['cadences_completees_14j'], 0)

    def test_la_serie_sappuie_sur_des_jours_termines(self):
        """Une touche laissée en retard hier CASSE la série ; une journée
        propre la fait courir."""
        propre = mes_stats_relance(
            self.company, self.acteur)['serie_jours_sans_retard']
        self.assertGreater(propre, 0)
        self._touche(statut='a_faire', due_jours=1, traite_par=None)
        casse = mes_stats_relance(
            self.company, self.acteur)['serie_jours_sans_retard']
        # `assertLess` et non `== 0` : le calendrier ouvré de la société
        # décide si la veille comptait — la propriété vérifiée est « un
        # retard CASSE la série », pas une valeur de calendrier.
        self.assertLess(casse, propre)


class IsolationSocieteTests(_Base):
    slug = 'ckp3-tenant'

    def test_les_touches_dune_autre_societe_nentrent_dans_aucun_chiffre(self):
        autre = _company('ckp3-tenant-autre')
        proprio = User.objects.create_user(
            username='ckp3-autre-u', password='x', company=autre)
        voisin = Lead.objects.create(
            company=autre, nom='Voisin', stage=stages.CONTACTED,
            owner=proprio)
        due = _quand(2)
        RelanceEtape.objects.create(
            company=autre, lead=voisin, cadence='contact', ordre=1,
            due_at=due, due_date=due.date(), canal=RelanceEtape.Canal.APPEL,
            libelle='Appel', statut='fait', traite_le=due,
            traite_par=proprio)
        kpi = kpi_adherence(self.company, self.acteur, 30)
        self.assertEqual(kpi['touches_faites'], 0)
        self.assertEqual(
            [ligne['lead_id'] for ligne in kpi['leads_sans_touche']],
            [self.lead.pk])
        stats = mes_stats_relance(self.company, self.acteur)
        self.assertEqual(stats['a_faire_maintenant'], 0)
