"""TCH71-TCH72 — les suggestions venues de l'ERP (reference/regles.md §9 ; A3, A4) et leurs routes
(reference/api.md §3.2, §4 ; `suggestions.json`, `suggestion_refusee.json`, `tache_ecrite.json`).

Base requise (`TestCase`). De vraies lignes `crm.Lead`, `crm.Client`, `ventes.Devis` (lues par le registre
d'applications, jamais importées) ; `devis_accepted` / `devis_acceptation_annulee` sont ÉMIS sur le vrai
bus ; les abonnés de chantier et de visite reçoivent l'objet émis réduit aux attributs qu'ils lisent
(`pk`, `company_id`, `lead_id`), leur abonnement au bus étant vérifié à part. Chaque test relit les
`SuggestionTache` STOCKÉES.
"""
import datetime
from decimal import Decimal
from types import SimpleNamespace

from django.apps import apps as registre
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.roles.models import Role
from apps.taches import receivers
from apps.taches.choix import FamilleSuggestion, Source, StatutSuggestion
from apps.taches.models.erp import SuggestionTache
from apps.taches.models.gestes import GesteAnnulable
from apps.taches.models.rythme import ReglagesRythme
from apps.taches.models.taches import Tache
from apps.taches.tests import fabriques
from apps.taches.tests.test_routes import est_construite
from apps.taches.views.base import exemple_de
from core.event_coverage import orphan_signals
from core.events import (
    chantier_annule,
    chantier_receptionne,
    devis_acceptation_annulee,
    devis_accepted,
    visite_validee,
)
from core.models import ModuleToggle

DROITS = ['taches_voir', 'crm_voir', 'ventes_voir', 'records_scope_soi']
TITRE_DEVIS = 'Préparer le chantier du devis accepté'
PREFIXE = '/api/django/taches/'
LISTE = PREFIXE + 'suggestions/'
JOUR = '2030-01-15'


def _utilisateur(societe, nom, permissions):
    role = Role.objects.create(company=societe, nom=f'Rôle {nom}', permissions=permissions)
    return get_user_model().objects.create_user(
        username=f'{nom}@{societe.slug}', password=None, company=societe, role=role, first_name=nom)


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.Lead = registre.get_model('crm', 'Lead')
        Client = registre.get_model('crm', 'Client')
        cls.Devis = registre.get_model('ventes', 'Devis')
        cls.a, cls.b = fabriques.societe('a'), fabriques.societe('b')
        cls.commercial = _utilisateur(cls.a, 'commercial', DROITS)
        cls.collegue = _utilisateur(cls.a, 'collegue', DROITS)
        for compte in (cls.commercial, cls.collegue):
            fabriques.reglages(compte)
        cls.client_crm = Client.objects.create(
            company=cls.a, nom='Benali', prenom='Karim', email='karim.tch71@example.invalid')
        # Le lead est rattaché au client : le repli « dernier lead du client » le trouverait (il est exclu).
        cls.lead = cls.Lead.objects.create(company=cls.a, nom='Benali', prenom='Karim', owner=cls.commercial,
                                           client=cls.client_crm)
        cls.devis = cls._devis('DEV-TCH71-0001', lead=cls.lead)

    @classmethod
    def _devis(cls, reference, **champs):
        champs.setdefault('created_by', cls.commercial)
        return cls.Devis.objects.create(company=cls.a, reference=reference, client=cls.client_crm,
                                        taux_tva=Decimal('20'), **champs)

    def _accepter(self, devis=None, **kwargs):
        devis_accepted.send(sender=self.Devis, devis=devis or self.devis, user=self.commercial,
                            ancien_statut='envoye', avenant_de=kwargs.get('avenant_de'), canal='')

    def _de(self, compte):
        return SuggestionTache.objects.filter(company=compte.company, proprietaire=compte)


class DevisAccepteTests(_Base):
    def test_un_meme_devis_accepte_emis_deux_fois_donne_une_suggestion(self):
        self._accepter()
        self._accepter()

        suggestion = self._de(self.commercial).get()
        self.assertEqual((suggestion.famille, suggestion.cle, suggestion.titre_propose, suggestion.statut),
                         (FamilleSuggestion.DEVIS_ACCEPTE, f'devis_accepte:{self.devis.pk}', TITRE_DEVIS,
                          StatutSuggestion.PROPOSEE))
        self.assertEqual((suggestion.content_type.app_label, suggestion.content_type.model,
                          suggestion.object_id, suggestion.lead_ref),
                         ('ventes', 'devis', self.devis.pk, self.lead.pk))
        self.assertNotIn('Benali', suggestion.titre_propose)  # A4 : aucun nom de client

    def test_destinataire_strict_un_collegue_ne_recoit_rien(self):
        self._accepter()
        self.assertFalse(self._de(self.collegue).exists())

    def test_devis_sans_lead_personne_meme_si_le_client_a_un_lead(self):
        sans_lead = self._devis('DEV-TCH71-0002')
        self._accepter(sans_lead)
        self.assertFalse(SuggestionTache.objects.exists())

    def test_avenant_ignore(self):
        self._accepter(avenant_de=self.devis.pk)
        self.assertFalse(SuggestionTache.objects.exists())

    def test_refusee_ou_acceptee_jamais_reproposee(self):
        self._accepter()
        self._de(self.commercial).update(statut=StatutSuggestion.REFUSEE)
        self._accepter()
        self.assertEqual(list(self._de(self.commercial).values_list('statut', flat=True)),
                         [StatutSuggestion.REFUSEE])


class ConditionsTests(_Base):
    def test_compte_sans_taches_voir_ne_recoit_rien(self):
        self.commercial.role.permissions = ['crm_voir', 'ventes_voir', 'records_scope_soi']
        self.commercial.role.save(update_fields=['permissions'])
        self._accepter()
        self.assertFalse(SuggestionTache.objects.exists())

    def test_module_coupe_dans_la_societe(self):
        ModuleToggle.objects.create(company=self.a, module='taches', actif=False)
        self._accepter()
        self.assertFalse(SuggestionTache.objects.exists())

    def test_sans_reglages_rythme_rien(self):
        ReglagesRythme.objects.filter(proprietaire=self.commercial).delete()
        self._accepter()
        self.assertFalse(SuggestionTache.objects.exists())

    def test_famille_eteinte_par_le_compte(self):
        ReglagesRythme.objects.filter(proprietaire=self.commercial).update(
            familles_suggestions=['chantier_receptionne'])
        self._accepter()
        self.assertFalse(SuggestionTache.objects.exists())

    def test_cible_hors_de_sa_portee(self):
        self.commercial.role.permissions = ['taches_voir', 'crm_voir', 'records_scope_soi']
        self.commercial.role.save(update_fields=['permissions'])
        self._accepter()
        self.assertFalse(SuggestionTache.objects.exists())

    def test_compte_desactive(self):
        self.commercial.is_active = False
        self.commercial.save(update_fields=['is_active'])
        self._accepter()
        self.assertFalse(SuggestionTache.objects.exists())

    def test_administrateur_avec_suggestions_societe_recoit_sa_ligne(self):
        admin = _utilisateur(self.a, 'admin', ['taches_voir', 'crm_voir', 'ventes_voir', 'roles_gerer'])
        fabriques.reglages(admin, suggestions_societe=True)
        sans_choix = _utilisateur(self.a, 'admin2', ['taches_voir', 'crm_voir', 'ventes_voir', 'roles_gerer'])
        fabriques.reglages(sans_choix)
        self._accepter()
        self.assertEqual(self._de(self.commercial).count(), 1)
        self.assertEqual(self._de(admin).count(), 1)
        self.assertFalse(self._de(sans_choix).exists())

    def test_non_administrateur_avec_suggestions_societe_ne_recoit_rien(self):
        ReglagesRythme.objects.filter(proprietaire=self.collegue).update(
            suggestions_societe=True)
        self._accepter()
        self.assertFalse(self._de(self.collegue).exists())


class RetraitTests(_Base):
    def test_acceptation_annulee_retire_la_suggestion_proposee(self):
        self._accepter()
        devis_acceptation_annulee.send(sender=self.Devis, devis=self.devis, user=self.commercial,
                                       option_acceptee='', date_acceptation=None, motif='test')
        suggestion = self._de(self.commercial).get()
        self.assertEqual(suggestion.statut, StatutSuggestion.RETIREE)
        self.assertIsNotNone(suggestion.decidee_le)

    def test_une_suggestion_deja_acceptee_reste_acceptee(self):
        self._accepter()
        self._de(self.commercial).update(statut=StatutSuggestion.ACCEPTEE)
        receivers.retirer_sur_acceptation_annulee(sender=self.Devis, devis=self.devis)
        self.assertEqual(self._de(self.commercial).get().statut, StatutSuggestion.ACCEPTEE)


class ChantierEtVisiteTests(_Base):
    def _installation(self, pk=4242, lead=True):
        return SimpleNamespace(pk=pk, company_id=self.a.pk, lead_id=self.lead.pk if lead else None)

    def test_chantier_receptionne_lie_au_lead_du_chantier(self):
        receivers.suggerer_sur_chantier_receptionne(sender=None, installation=self._installation())
        suggestion = self._de(self.commercial).get()
        self.assertEqual((suggestion.cle, suggestion.titre_propose, suggestion.content_type.model,
                          suggestion.object_id, suggestion.lead_ref),
                         ('chantier_receptionne:4242', 'Demander un avis au client : chantier réceptionné',
                          'lead', self.lead.pk, self.lead.pk))

    def test_chantier_annule(self):
        receivers.suggerer_sur_chantier_annule(sender=None, installation=self._installation(7))
        self.assertEqual(self._de(self.commercial).get().titre_propose, "Comprendre l'annulation du chantier")

    def test_chantier_sans_lead_personne(self):
        receivers.suggerer_sur_chantier_annule(sender=None, installation=self._installation(lead=False))
        self.assertFalse(SuggestionTache.objects.exists())

    def test_visite_validee_eteinte_par_defaut_puis_allumee(self):
        visite = SimpleNamespace(pk=88, company_id=self.a.pk)
        receivers.suggerer_sur_visite_validee(sender=None, visite=visite, lead_id=self.lead.pk)
        self.assertFalse(SuggestionTache.objects.exists())
        ReglagesRythme.objects.filter(proprietaire=self.commercial).update(
            familles_suggestions=['visite_validee'])
        receivers.suggerer_sur_visite_validee(sender=None, visite=visite, lead_id=self.lead.pk)
        self.assertEqual(self._de(self.commercial).get().titre_propose, 'Préparer le devis : visite validée')

    def test_autre_societe_ne_voit_jamais_le_lead(self):
        installation = SimpleNamespace(pk=1, company_id=self.b.pk, lead_id=self.lead.pk)
        receivers.suggerer_sur_chantier_receptionne(sender=None, installation=installation)
        self.assertFalse(SuggestionTache.objects.exists())


class AbonnementsTests(TestCase):
    def test_les_cinq_abonnes_sont_sur_le_bus(self):
        for signal, uid in ((devis_accepted, 'taches.suggerer_sur_devis_accepte'),
                            (devis_acceptation_annulee, 'taches.retirer_sur_acceptation_annulee'),
                            (chantier_receptionne, 'taches.suggerer_sur_chantier_receptionne'),
                            (chantier_annule, 'taches.suggerer_sur_chantier_annule'),
                            (visite_validee, 'taches.suggerer_sur_visite_validee')):
            with self.subTest(uid=uid):
                self.assertIn(uid, {entree[0][0] for entree in signal.receivers})

    def test_aucun_signal_orphelin(self):
        self.assertEqual(orphan_signals(), set())


# --- TCH72 : routes des suggestions ---------------------------------------------------------------

class _Routes(_Base):
    def setUp(self):
        self._accepter()
        self.suggestion = self._de(self.commercial).get()

    def _api(self, compte=None):
        api = APIClient()
        api.force_authenticate(compte or self.commercial)
        return api

    def _ligne(self, compte, cle, **champs):
        return SuggestionTache.objects.create(
            company=compte.company, proprietaire=compte, famille=FamilleSuggestion.CHANTIER_ANNULE, cle=cle,
            titre_propose="Comprendre l'annulation du chantier", **champs)


class ListeTests(_Routes):
    def test_forme_de_suggestions_json_cle_pour_cle(self):
        reponse = self._api().get(LISTE)

        self.assertEqual(reponse.status_code, 200, reponse.content)
        corps, modele = reponse.json(), exemple_de('suggestions')
        self.assertEqual(set(corps), set(modele))
        ligne, ligne_modele = corps['results'][0], modele['results'][0]
        self.assertEqual(set(ligne), set(ligne_modele))
        self.assertEqual(set(ligne['lien']), set(ligne_modele['lien']))
        self.assertEqual((ligne['id'], ligne['famille'], ligne['titre']),
                         (self.suggestion.pk, 'devis_accepte', TITRE_DEVIS))
        self.assertEqual((ligne['lien']['cible'], ligne['lien']['id'], ligne['lien']['url'], ligne['lien']['etat']),
                         ('ventes.devis', self.devis.pk, f'/ventes/devis?devis={self.devis.pk}', 'ok'))
        self.assertTrue(ligne['lien']['libelle'].startswith('DEV-TCH71-0001'))

    def test_au_plus_20_proposees_de_moins_de_7_jours_les_plus_recentes_d_abord(self):
        lignes = [self._ligne(self.commercial, f'chantier_annule:{n}') for n in range(25)]
        vieille = self._ligne(self.commercial, 'chantier_annule:vieille')
        SuggestionTache.objects.filter(pk=vieille.pk).update(
            created_at=timezone.now() - datetime.timedelta(days=8))
        self._ligne(self.commercial, 'chantier_annule:refusee', statut=StatutSuggestion.REFUSEE)
        self._ligne(self.collegue, 'chantier_annule:collegue')

        ids = [ligne['id'] for ligne in self._api().get(LISTE).json()['results']]

        attendus = [ligne.pk for ligne in sorted(lignes + [self.suggestion],
                                                 key=lambda x: (x.created_at, x.pk), reverse=True)][:20]
        self.assertEqual(ids, attendus)

    def test_cible_sortie_de_la_portee_servie_inaccessible_sans_libelle(self):
        self.commercial.role.permissions = ['taches_voir', 'crm_voir', 'records_scope_soi']
        self.commercial.role.save(update_fields=['permissions'])
        lien = self._api().get(LISTE).json()['results'][0]['lien']
        self.assertEqual((lien['etat'], lien['libelle'], lien['url']), ('inaccessible', '', None))

    def test_l_autre_compte_ne_voit_rien(self):
        self.assertEqual(self._api(self.collegue).get(LISTE).json(), {'results': []})


class AccepterTests(_Routes):
    def _url(self, pk=None):
        return f'{LISTE}{pk or self.suggestion.pk}/accepter/'

    def test_ajouter_avec_le_titre_edite(self):
        reponse = self._api().post(self._url(), {'titre': 'Préparer le chantier', 'jour_prevu': JOUR},
                                   format='json')

        self.assertEqual(reponse.status_code, 201, reponse.content)
        corps = reponse.json()
        self.assertEqual(set(corps), set(exemple_de('tache_ecrite')))
        tache = Tache.objects.get(pk=corps['tache']['id'])
        self.assertEqual((tache.titre, tache.source, tache.proprietaire_id, tache.jour_prevu.isoformat()),
                         ('Préparer le chantier', Source.SUGGESTION, self.commercial.pk, JOUR))
        self.assertEqual((tache.content_type.model, tache.object_id, tache.lien_etat),
                         ('devis', self.devis.pk, 'ok'))
        self.suggestion.refresh_from_db()
        self.assertEqual((self.suggestion.statut, self.suggestion.tache_id),
                         (StatutSuggestion.ACCEPTEE, tache.pk))
        self.assertIsNotNone(self.suggestion.decidee_le)
        self.assertEqual(corps['geste_id'], GesteAnnulable.objects.get(proprietaire=self.commercial).pk)

    def test_sans_titre_le_titre_propose(self):
        reponse = self._api().post(self._url(), {}, format='json')
        self.assertEqual(reponse.status_code, 201, reponse.content)
        self.assertEqual(Tache.objects.get(proprietaire=self.commercial).titre, TITRE_DEVIS)

    def test_meme_etat_que_le_semis_de_demonstration(self):
        """`seed_taches_demo` écrit une suggestion « acceptée » : tâche `source=suggestion`, statut
        `acceptee`, `tache` et `decidee_le` posés — la route produit le même état par le service."""
        self._api().post(self._url(), {}, format='json')
        stockee = SuggestionTache.objects.select_related('tache').get(pk=self.suggestion.pk)
        self.assertEqual((stockee.statut, stockee.tache.source, stockee.tache.titre),
                         (StatutSuggestion.ACCEPTEE, Source.SUGGESTION, stockee.titre_propose))
        self.assertIsNotNone(stockee.decidee_le)

    def test_rejeu_rend_la_meme_tache_sans_doublon(self):
        premiere = self._api().post(self._url(), {}, format='json').json()
        seconde = self._api().post(self._url(), {}, format='json')
        self.assertEqual(seconde.status_code, 201)
        self.assertEqual(seconde.json()['tache']['id'], premiere['tache']['id'])
        self.assertIsNone(seconde.json()['geste_id'])
        self.assertEqual(Tache.objects.filter(proprietaire=self.commercial).count(), 1)

    def test_annuler_rend_la_suggestion_proposee_et_retire_la_tache(self):
        geste_id = self._api().post(self._url(), {}, format='json').json()['geste_id']
        reponse = self._api().post(f'{PREFIXE}gestes/{geste_id}/annuler/', {}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.content)
        self.suggestion.refresh_from_db()
        self.assertEqual((self.suggestion.statut, self.suggestion.tache_id, self.suggestion.decidee_le),
                         (StatutSuggestion.PROPOSEE, None, None))
        self.assertFalse(Tache.objects.filter(proprietaire=self.commercial).exists())

    def test_id_d_un_autre_404(self):
        autre = self._ligne(self.collegue, 'chantier_annule:1')
        self.assertEqual(self._api().post(self._url(autre.pk), {}, format='json').status_code, 404)
        self.assertEqual(self._api().post(self._url(987654), {}, format='json').status_code, 404)
        autre.refresh_from_db()
        self.assertEqual(autre.statut, StatutSuggestion.PROPOSEE)

    def test_refusee_404(self):
        self._de(self.commercial).update(statut=StatutSuggestion.REFUSEE)
        self.assertEqual(self._api().post(self._url(), {}, format='json').status_code, 404)
        self.assertFalse(Tache.objects.exists())

    def test_titre_trop_long_400(self):
        reponse = self._api().post(self._url(), {'titre': 'x' * 281}, format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('titre', reponse.json())


class RefuserTests(_Routes):
    def _url(self, pk=None):
        return f'{LISTE}{pk or self.suggestion.pk}/refuser/'

    def test_pas_utile_suggestion_refusee_json(self):
        reponse = self._api().post(self._url(), format='json')

        self.assertEqual(reponse.status_code, 200, reponse.content)
        corps = reponse.json()
        self.assertEqual(set(corps), set(exemple_de('suggestion_refusee')))
        geste = GesteAnnulable.objects.get(proprietaire=self.commercial)
        self.assertEqual(corps, {'id': self.suggestion.pk, 'statut': 'refusee', 'geste_id': geste.pk})
        self.suggestion.refresh_from_db()
        self.assertEqual(self.suggestion.statut, StatutSuggestion.REFUSEE)
        self.assertEqual(self._api().get(LISTE).json(), {'results': []})

    def test_rejeu_sans_geste_neuf(self):
        self._api().post(self._url(), format='json')
        rejeu = self._api().post(self._url(), format='json')
        self.assertEqual(rejeu.json(), {'id': self.suggestion.pk, 'statut': 'refusee', 'geste_id': None})
        self.assertEqual(GesteAnnulable.objects.filter(proprietaire=self.commercial).count(), 1)

    def test_annuler_la_rend_proposee(self):
        geste_id = self._api().post(self._url(), format='json').json()['geste_id']
        self._api().post(f'{PREFIXE}gestes/{geste_id}/annuler/', {}, format='json')
        self.suggestion.refresh_from_db()
        self.assertEqual(self.suggestion.statut, StatutSuggestion.PROPOSEE)

    def test_id_d_un_autre_404(self):
        autre = self._ligne(self.collegue, 'chantier_annule:1')
        self.assertEqual(self._api().post(self._url(autre.pk), format='json').status_code, 404)
        autre.refresh_from_db()
        self.assertEqual(autre.statut, StatutSuggestion.PROPOSEE)


class RoutesConstruitesTests(TestCase):
    def test_les_trois_routes_sortent_des_501(self):
        for methode, chemin in (('GET', 'suggestions/'), ('POST', 'suggestions/{id}/accepter/'),
                                ('POST', 'suggestions/{id}/refuser/')):
            with self.subTest(chemin=chemin):
                self.assertTrue(est_construite(methode, chemin))
