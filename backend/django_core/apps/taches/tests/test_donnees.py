"""TCH74 — données personnelles : les deux portes d'effacement 09-08, « Mes données », « Tout effacer ».
TCH75 — la nuit : purges par dates (donnees.md §8) et revérification des liens des tâches ouvertes.

Base requise (`TestCase`) : joué par la CI. Deux sociétés réelles (`'a'`, `'b'`), deux comptes dans A.
Aucun modèle d'une autre app n'est lu ici : un lead ou un client lié est un couple (ContentType,
identifiant), la résolution d'un sujet par `crm` est remplacée par un double de
`crm.selectors.cibles_du_sujet` (sa propre preuve vit dans `crm/tests_acrm_dsr_copies_brutes.py`) ;
la présence d'un objet lié (`records.serializers.resolve_target`) et sa visibilité (la porte de
`selectors/liens.py`) sont doublées quand l'objet devrait exister. Jour et instant injectés.
"""
import datetime
from types import SimpleNamespace
from unittest import mock

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.taches import dsr
from apps.taches.choix import (
    CanalIncitation,
    CibleLiable,
    FamilleSuggestion,
    LienEtat,
    StatutRappel,
    StatutTache,
    TypeIncitationEcran,
    UsageJeton,
)
from apps.taches.models.erp import SuggestionTache
from apps.taches.models.journee import LignePlanJour, PlanJour
from apps.taches.models.rythme import IncitationCoach
from apps.taches.models.taches import Rappel, Tache
from apps.taches.serializers.formes import LIBELLE_LEAD_EFFACE, lien_de_tache
from apps.taches.services.donnees import MODELES, exporter, lignes_du_compte
from apps.taches.services.erp import reverifier_liens
from apps.taches.services.gestes import enregistrer_geste
from apps.taches.services.purge import purger
from apps.taches.tests import fabriques
from apps.taches.views.base import exemple_de
from core import dsr as registre_dsr
from core.events import lead_erased
from core.models import DeletionRecord

PREFIXE = '/api/django/taches/'
MES_DONNEES = PREFIXE + 'mes-donnees/'
TOUT_EFFACER = PREFIXE + 'tout-effacer/'
JOUR = datetime.date(2026, 11, 17)
LEAD, AUTRE_LEAD, CLIENT, AUTRE_CLIENT = 4242, 5555, 777, 778


def _type(cible):
    app_label, modele = cible.split('.', 1)
    return ContentType.objects.get_by_natural_key(app_label, modele)


def _liee(compte, cible, object_id, libelle='Karim Benali', **champs):
    """Tâche de `compte` liée à (`cible`, `object_id`), lien vérifié `ok`."""
    return fabriques.tache(compte, content_type=_type(cible), object_id=object_id,
                           lien_libelle=libelle, lien_etat=LienEtat.OK, **champs)


def _suggestion(compte, lead_ref, cle):
    return SuggestionTache.objects.create(
        company=compte.company, proprietaire=compte, famille=FamilleSuggestion.DEVIS_ACCEPTE, cle=cle,
        titre_propose='Préparer le chantier du devis accepté', lead_ref=lead_ref)


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a, cls.b = fabriques.societe('a'), fabriques.societe('b')
        cls.u1 = fabriques.compte(cls.a, nom='u1')
        cls.u2 = fabriques.compte(cls.a, nom='u2')
        cls.ailleurs = fabriques.compte(cls.b, nom='u1')

    def _api(self, compte=None):
        api = APIClient()
        api.force_authenticate(compte or self.u1)
        return api


class EffacementTests(_Base):
    def test_lead_efface_par_le_signal(self):
        a_moi = _liee(self.u1, CibleLiable.LEAD, LEAD, titre='Appeler Karim')
        au_voisin = _liee(self.u2, CibleLiable.LEAD, LEAD)
        autre_lead = _liee(self.u1, CibleLiable.LEAD, AUTRE_LEAD, libelle='Aziz')
        autre_societe = _liee(self.ailleurs, CibleLiable.LEAD, LEAD)
        du_lead = _suggestion(self.u1, LEAD, 'devis_accepte:1')
        gardees = [_suggestion(self.u1, AUTRE_LEAD, 'devis_accepte:2'),
                   _suggestion(self.ailleurs, LEAD, 'devis_accepte:1')]

        lead_erased.send(sender=None, company=self.a, crm_lead_id=LEAD)

        for tache in (a_moi, au_voisin):
            tache.refresh_from_db()
            self.assertEqual((tache.lien_libelle, tache.lien_etat), ('', LienEtat.EFFACE))
            self.assertEqual(lien_de_tache(tache)['libelle'], LIBELLE_LEAD_EFFACE)
        self.assertEqual(a_moi.titre, 'Appeler Karim')  # le titre tapé reste
        for tache, libelle in ((autre_lead, 'Aziz'), (autre_societe, 'Karim Benali')):
            tache.refresh_from_db()
            self.assertEqual((tache.lien_libelle, tache.lien_etat), (libelle, LienEtat.OK))
        self.assertFalse(SuggestionTache.objects.filter(pk=du_lead.pk).exists())
        self.assertEqual(set(SuggestionTache.objects.values_list('pk', flat=True)), {s.pk for s in gardees})

    def test_fournisseur_dsr_enregistre_avant_crm(self):
        fournisseur = registre_dsr._PROVIDERS[dsr.PROVIDER_NAME]
        self.assertIsNone(fournisseur['export'])
        self.assertIs(fournisseur['erase'], dsr.effacer_sujet)
        self.assertLess(fournisseur['erase_order'], registre_dsr._PROVIDERS['crm']['erase_order'])

    def test_effacer_sujet_resout_par_la_porte_de_crm(self):
        lead = _liee(self.u1, CibleLiable.LEAD, LEAD)
        client = _liee(self.u1, CibleLiable.CLIENT, CLIENT)
        autre = _liee(self.u1, CibleLiable.CLIENT, AUTRE_CLIENT, libelle='Autre client')
        suggestion = _suggestion(self.u1, LEAD, 'devis_accepte:1')
        cibles = {'leads': [LEAD], 'clients': [CLIENT]}
        with mock.patch('apps.crm.selectors.cibles_du_sujet', return_value=cibles) as porte:
            touchees = dsr.effacer_sujet(self.a, 'kenza@example.com')
        porte.assert_called_once_with(self.a, 'kenza@example.com')
        self.assertEqual(touchees, 3)
        for tache in (lead, client):
            tache.refresh_from_db()
            self.assertEqual((tache.lien_libelle, tache.lien_etat), ('', LienEtat.EFFACE))
        autre.refresh_from_db()
        self.assertEqual(autre.lien_etat, LienEtat.OK)
        self.assertFalse(SuggestionTache.objects.filter(pk=suggestion.pk).exists())

    def test_sujet_sans_cible_ne_touche_rien(self):
        tache = _liee(self.u1, CibleLiable.LEAD, LEAD)
        with mock.patch('apps.crm.selectors.cibles_du_sujet', return_value={'leads': [], 'clients': []}):
            self.assertEqual(dsr.effacer_sujet(self.a, 'personne@example.com'), 0)
        tache.refresh_from_db()
        self.assertEqual(tache.lien_etat, LienEtat.OK)


class MesDonneesTests(_Base):
    def test_export_des_21_modeles_sans_secret(self):
        projet = fabriques.projet(self.u1, nom='Ventes')
        tache = fabriques.tache(self.u1, projet=projet, titre='Devis Settat', notes='Appeler avant 11 h.')
        supprimee = fabriques.tache(self.u1, titre='Ancienne')
        supprimee.soft_delete(self.u1, record=False)
        jeton, clair = fabriques.jeton(self.u1, UsageJeton.FLUX)
        agenda = fabriques.agenda_externe(
            self.u1, url='https://outlook.office365.com/owa/calendar/secret-abc/reachcalendar.ics',
            libelle='Microsoft 365')
        fabriques.tache(self.u2, titre='Pas a moi')

        reponse = self._api().get(MES_DONNEES)

        self.assertEqual(reponse.status_code, 200, reponse.content)
        self.assertEqual(reponse['Cache-Control'], 'no-store')
        corps, exemple = reponse.json(), exemple_de('mes_donnees')
        self.assertEqual(set(corps), set(exemple))
        self.assertEqual(set(corps) - {'exporte_le'}, set(MODELES))
        self.assertEqual(len(MODELES), 21)
        self.assertEqual({t['id'] for t in corps['tache']}, {tache.pk, supprimee.pk})
        self.assertEqual(set(corps['tache'][0]), set(exemple['tache'][0]))
        self.assertEqual(set(corps['projet'][0]), set(exemple['projet'][0]))
        self.assertEqual(corps['projet'][0]['compteurs'], {'ouvertes': 1, 'faites': 0})
        self.assertEqual(corps['jeton_acces'],
                         [{'id': jeton.pk, 'usage': 'flux', 'prefixe': clair[:8], 'revoque_le': None}])
        self.assertEqual(corps['agenda_externe'],
                         [{'id': agenda.pk, 'hote': 'outlook.office365.com', 'libelle': 'Microsoft 365'}])
        texte = reponse.content.decode('utf-8')
        for secret in (clair, jeton.jeton_hash, 'secret-abc', 'Pas a moi'):
            self.assertNotIn(secret, texte)

    def test_lignes_brutes_et_instant_injecte(self):
        fabriques.plan(self.u1, JOUR, reflexion='Bonne journée')
        fabriques.reglages(self.u1)
        rendu = exporter(self.u1, maintenant=datetime.datetime(2026, 11, 17, 9, 0, tzinfo=datetime.timezone.utc))
        self.assertEqual(rendu['exporte_le'], '2026-11-17T10:00:00+01:00')
        self.assertEqual([(p['jour'], p['reflexion']) for p in rendu['plan_jour']], [('2026-11-17', 'Bonne journée')])
        for cle, lignes in rendu.items():
            for ligne in lignes if isinstance(lignes, list) else ():
                with self.subTest(cle=cle):
                    self.assertNotIn('company_id', ligne)
                    self.assertNotIn('proprietaire_id', ligne)


class ToutEffacerTests(_Base):
    def test_sans_effacer_400_au_champ(self):
        tache = fabriques.tache(self.u1)
        for corps in ({}, {'confirmation': 'effacer'}, {'confirmation': 'OUI'}):
            with self.subTest(corps=corps):
                reponse = self._api().post(TOUT_EFFACER, corps, format='json')
                self.assertEqual(reponse.status_code, 400)
                self.assertEqual(reponse.json()['confirmation'], ['Tape EFFACER pour confirmer.'])
        self.assertTrue(Tache.objects.filter(pk=tache.pk).exists())

    def test_efface_le_seul_couple_societe_utilisateur(self):
        projet = fabriques.projet(self.u1)
        fabriques.tache(self.u1, projet=projet)
        fabriques.tache(self.u1)
        activite = fabriques.activite(self.u1)
        fabriques.tache(self.u1, activite_origine=activite)
        fabriques.plan(self.u1, JOUR)
        fabriques.reglages(self.u1)
        fabriques.jeton(self.u1, UsageJeton.CAPTURE)
        fabriques.agenda_externe(self.u1)
        _suggestion(self.u1, LEAD, 'devis_accepte:1')
        du_voisin = fabriques.tache(self.u2)
        d_ailleurs = fabriques.tache(self.ailleurs)

        reponse = self._api().post(TOUT_EFFACER, {'confirmation': 'EFFACER'}, format='json')

        self.assertEqual(reponse.status_code, 200, reponse.content)
        corps = reponse.json()
        self.assertEqual(set(corps), set(exemple_de('tout_effacer')))
        self.assertEqual(corps['effacees'], {
            'tache': 3, 'projet': 1, 'plan_jour': 1, 'reglages_rythme': 1, 'jeton_acces': 1,
            'agenda_externe': 1, 'suggestion_tache': 1})
        for cle in MODELES:
            with self.subTest(cle=cle):
                self.assertFalse(lignes_du_compte(cle, self.u1).exists())
        self.assertEqual(set(Tache.all_objects.values_list('pk', flat=True)), {du_voisin.pk, d_ailleurs.pk})
        activite.refresh_from_db()  # l'activité de l'ERP n'appartient pas à `taches` : intacte
        self.assertFalse(activite.done)


def _il_y_a(jours, heure=12):
    """Instant (heure murale de la société) du jour `JOUR` − `jours`."""
    jour = JOUR - datetime.timedelta(days=jours)
    return timezone.make_aware(datetime.datetime.combine(jour, datetime.time(heure)))


def _jour(jours):
    return JOUR - datetime.timedelta(days=jours)


class PurgeTests(_Base):
    def _supprimee(self, objet, jours):
        objet.soft_delete(self.u1, record=False)
        type(objet).all_objects.filter(pk=objet.pk).update(deleted_at=_il_y_a(jours))
        return objet

    def _cree_il_y_a(self, objet, jours):
        type(objet).objects.filter(pk=objet.pk).update(created_at=_il_y_a(jours))
        return objet

    def _rappel(self, tache, jours, statut):
        return Rappel.objects.create(company=self.a, proprietaire=self.u1, tache=tache, jour=_jour(jours),
                                     heure=datetime.time(9, 0), statut=statut)

    def _incitation(self, jours):
        return IncitationCoach.objects.create(company=self.a, proprietaire=self.u1, jour=_jour(jours),
                                              type=TypeIncitationEcran.CONSTAT, canal=CanalIncitation.ECRAN)

    def test_retentions_par_dates_puis_rejeu_idempotent(self):
        tache = fabriques.tache(self.u1)
        plan_91, plan_90 = fabriques.plan(self.u1, _jour(91)), fabriques.plan(self.u1, _jour(90))
        lignes = [LignePlanJour.objects.create(company=self.a, plan=plan, tache=tache, prevue_au_plan=True)
                  for plan in (plan_91, plan_90)]
        purges = [
            fabriques.plan(self.u1, _jour(401)), lignes[0], self._incitation(91),
            self._rappel(tache, 31, StatutRappel.ENVOYE), self._rappel(tache, 31, StatutRappel.ANNULE),
            self._cree_il_y_a(enregistrer_geste(self.u1, 'creation', 'vieux', []), 8),
            self._cree_il_y_a(_suggestion(self.u1, LEAD, 'devis_accepte:1'), 31),
            self._supprimee(fabriques.tache(self.u1), 31), self._supprimee(fabriques.projet(self.u1), 31),
        ]
        gardes = [
            fabriques.plan(self.u1, _jour(400)), plan_91, plan_90, lignes[1], self._incitation(90),
            self._rappel(tache, 31, StatutRappel.EN_ATTENTE), self._rappel(tache, 30, StatutRappel.ENVOYE),
            self._cree_il_y_a(enregistrer_geste(self.u1, 'creation', 'récent', []), 6),
            self._cree_il_y_a(_suggestion(self.u1, LEAD, 'devis_accepte:2'), 29),
            self._supprimee(fabriques.tache(self.u1), 29), tache, fabriques.plan(self.ailleurs, _jour(401)),
        ]
        projet_habite = fabriques.projet(self.u1)
        restauree = fabriques.tache(self.u1, projet=projet_habite)
        self._supprimee(projet_habite, 31)
        gardes += [projet_habite, restauree]

        premier = purger(self.a.pk, JOUR)

        for objet in purges:
            with self.subTest(purge=f'{type(objet).__name__} {objet.pk}'):
                self.assertFalse(type(objet)._base_manager.filter(pk=objet.pk).exists())
        for objet in gardes:
            with self.subTest(garde=f'{type(objet).__name__} {objet.pk}'):
                self.assertTrue(type(objet)._base_manager.filter(pk=objet.pk).exists())
        self.assertEqual((premier['taches_supprimees'], premier['projets_supprimes']), (1, 1))
        self.assertFalse(DeletionRecord.objects.filter(content_type__app_label='taches').exists())  # inv. 26
        self.assertEqual(set(purger(self.a.pk, JOUR).values()), {0})

    def test_la_nuit_appelle_les_vraies_etapes(self):
        from apps.taches import nocturne
        vieux = fabriques.plan(self.u1, _jour(401))
        self.assertTrue(all(nocturne.executer(self.a.pk, JOUR).values()))
        self.assertFalse(PlanJour.objects.filter(pk=vieux.pk).exists())


class ReverificationTests(_Base):
    MAINTENANT = datetime.datetime(2026, 11, 17, 2, 0, tzinfo=datetime.timezone.utc)

    def _reverifier(self):
        return reverifier_liens(self.a.pk, JOUR, maintenant=self.MAINTENANT)

    def test_lien_introuvable(self):
        tache = _liee(self.u1, CibleLiable.CLIENT, 999999)
        self.assertEqual(self._reverifier(), 1)
        tache.refresh_from_db()
        self.assertEqual((tache.lien_etat, tache.lien_libelle, tache.lien_verifie_le),
                         (LienEtat.INTROUVABLE, '', self.MAINTENANT))
        self.assertEqual(tache.lock_version, 0)  # écrit sans conflit pour une fiche ouverte
        self.assertEqual(tache.content_type_id, _type(CibleLiable.CLIENT).pk)  # tâche et lien gardés

    def test_ok_inaccessible_et_archive_vus_par_le_proprietaire(self):
        objets = {CLIENT: SimpleNamespace(is_archived=False), AUTRE_CLIENT: SimpleNamespace(is_archived=True)}

        def presence(cible, object_id, company, **_options):
            self.assertEqual(company, self.a)
            return _type(cible), objets[object_id]

        def porte(user, app, cle, pk):
            return {cle: 'Benali Karim'} if user.pk == self.u1.pk else {}
        a_moi = _liee(self.u1, CibleLiable.CLIENT, CLIENT, libelle='Ancien libellé')
        au_voisin = _liee(self.u2, CibleLiable.CLIENT, CLIENT)
        archivee = _liee(self.u1, CibleLiable.CLIENT, AUTRE_CLIENT)
        with mock.patch('apps.records.serializers.resolve_target', side_effect=presence), \
                mock.patch('apps.taches.selectors.liens._par_la_porte', side_effect=porte):
            self.assertEqual(self._reverifier(), 3)
        attendus = ((a_moi, LienEtat.OK, 'Benali Karim'), (au_voisin, LienEtat.INACCESSIBLE, ''),
                    (archivee, LienEtat.ARCHIVE, ''))
        for tache, etat, libelle in attendus:
            tache.refresh_from_db()
            self.assertEqual((tache.lien_etat, tache.lien_libelle), (etat, libelle))

    def test_ni_fermees_ni_effacees_ni_autre_societe(self):
        faite = _liee(self.u1, CibleLiable.CLIENT, 999999, statut=StatutTache.FAIT, fait_le=self.MAINTENANT)
        effacee = fabriques.tache(self.u1, content_type=_type(CibleLiable.LEAD), object_id=LEAD,
                                  lien_etat=LienEtat.EFFACE)
        ailleurs = _liee(self.ailleurs, CibleLiable.CLIENT, 999999)
        sans_lien = fabriques.tache(self.u1)
        self.assertEqual(self._reverifier(), 0)
        for tache, etat in ((faite, LienEtat.OK), (effacee, LienEtat.EFFACE), (ailleurs, LienEtat.OK),
                            (sans_lien, '')):
            tache.refresh_from_db()
            self.assertEqual((tache.lien_etat, tache.lien_verifie_le), (etat, None))
