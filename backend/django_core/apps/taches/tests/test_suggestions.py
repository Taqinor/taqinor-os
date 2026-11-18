"""TCH71 — les suggestions venues de l'ERP (reference/regles.md §9 ; A3, A4).

Base requise (`TestCase`). De vraies lignes `crm.Lead`, `crm.Client`, `ventes.Devis` (lues par le registre
d'applications, jamais importées) ; `devis_accepted` / `devis_acceptation_annulee` sont ÉMIS sur le vrai
bus ; les abonnés de chantier et de visite reçoivent l'objet émis réduit aux attributs qu'ils lisent
(`pk`, `company_id`, `lead_id`), leur abonnement au bus étant vérifié à part. Chaque test relit les
`SuggestionTache` STOCKÉES.
"""
from decimal import Decimal
from types import SimpleNamespace

from django.apps import apps as registre
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.roles.models import Role
from apps.taches import receivers
from apps.taches.choix import FamilleSuggestion, StatutSuggestion
from apps.taches.models.erp import SuggestionTache
from apps.taches.models.rythme import ReglagesRythme
from apps.taches.tests import fabriques
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
