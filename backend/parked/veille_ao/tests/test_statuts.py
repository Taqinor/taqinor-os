"""VAO14 — service UNIQUE de changement de statut + journal au chatter.

Ce qui est vérifié :
  * le statut n'est JAMAIS muté hors du service (test d'introspection AST sur
    tout le module) ;
  * la table de transitions est déclarative, et une transition interdite est
    refusée en 400 avec un message EN FRANÇAIS ;
  * chaque transition écrit une activité ``records`` lisible (qui, quand,
    pourquoi) — jamais une classe ``*Activity`` maison ;
  * AUCUN nouveau signal ``core/events.py`` n'est déclaré : le dépôt fait
    rougir la CI sur tout signal sans abonné réel, et rien ici n'en a besoin.
"""
import ast
import datetime as dt
from pathlib import Path

from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.records.models import Activity
from apps.veille_ao.models import (
    AvisMarche, PorteeExclusion, RegleExclusion, SourceVeille, StatutAvis,
    TypeSource,
)
from apps.veille_ao.services import (
    MOTIF_EXPIRATION_AUTOMATIQUE, TRANSITIONS_AVIS, appliquer_regles_exclusion,
    changer_statut_avis, transitions_possibles,
)
from authentication.models import Company, CustomUser

MODULE_DIR = Path(__file__).resolve().parent.parent

#: Le SEUL fichier du module autorisé à écrire ``…statut = …``.
FICHIER_DU_SERVICE = 'services.py'


class TableDeTransitionsTests(SimpleTestCase):
    def test_table_declarative_complete(self):
        """Chaque statut a une entrée : rien n'est laissé à la déduction."""
        self.assertEqual(set(TRANSITIONS_AVIS),
                         set(StatutAvis.values))

    def test_un_avis_nouveau_se_trie(self):
        self.assertEqual(
            set(transitions_possibles(StatutAvis.NOUVEAU)),
            {StatutAvis.RETENU, StatutAvis.IGNORE, StatutAvis.EXPIRE})

    def test_un_avis_retenu_se_convertit(self):
        self.assertIn(StatutAvis.CONVERTI,
                      transitions_possibles(StatutAvis.RETENU))

    def test_tout_avis_peut_expirer_sauf_deja_expire(self):
        for statut in StatutAvis.values:
            if statut == StatutAvis.EXPIRE:
                self.assertEqual(transitions_possibles(statut), ())
            else:
                self.assertIn(StatutAvis.EXPIRE,
                              transitions_possibles(statut))

    def test_aucun_statut_ne_boucle_sur_lui_meme(self):
        for statut, cibles in TRANSITIONS_AVIS.items():
            self.assertNotIn(statut, cibles, statut)


class BaseStatut(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME Statuts')
        cls.user = CustomUser.objects.create_user(
            username='vao_statuts', password='x', company=cls.company)
        cls.source = SourceVeille.objects.create(
            company=cls.company, code='src', libelle='Source',
            type_source=TypeSource.SAISIE_MANUELLE, actif=True)

    def _avis(self, **kwargs):
        params = {
            'company': self.company, 'source': self.source,
            'objet': 'Centrale photovoltaïque de 300 kWc',
            'acheteur': 'Commune de Test',
        }
        params.update(kwargs)
        return AvisMarche.objects.create(**params)


class TransitionsAutoriseesTests(BaseStatut):
    def test_nouveau_vers_retenu(self):
        avis = self._avis()
        changer_statut_avis(avis, StatutAvis.RETENU, user=self.user,
                            motif='Dans notre métier.')
        avis.refresh_from_db()
        self.assertEqual(avis.statut, StatutAvis.RETENU)

    def test_nouveau_vers_ignore(self):
        avis = self._avis()
        changer_statut_avis(avis, StatutAvis.IGNORE, user=self.user,
                            motif='Hors périmètre.')
        avis.refresh_from_db()
        self.assertEqual(avis.statut, StatutAvis.IGNORE)

    def test_retenu_vers_converti_avec_champ_supplementaire(self):
        avis = self._avis(statut=StatutAvis.RETENU)
        changer_statut_avis(
            avis, StatutAvis.CONVERTI, user=self.user,
            motif="Créé en appel d'offres.",
            champs_supplementaires={'appel_offre_id': 4242})
        avis.refresh_from_db()
        self.assertEqual(avis.statut, StatutAvis.CONVERTI)
        self.assertEqual(avis.appel_offre_id, 4242)


class TransitionsRefuseesTests(BaseStatut):
    def test_transition_interdite_leve_un_400_en_francais(self):
        avis = self._avis()
        with self.assertRaises(ValidationError) as contexte:
            changer_statut_avis(avis, StatutAvis.CONVERTI, user=self.user)
        message = str(contexte.exception.detail['statut'][0])
        self.assertIn('Transition interdite', message)
        self.assertIn('Statuts atteignables', message)

    def test_avis_refuse_n_est_pas_modifie(self):
        avis = self._avis()
        with self.assertRaises(ValidationError):
            changer_statut_avis(avis, StatutAvis.CONVERTI)
        avis.refresh_from_db()
        self.assertEqual(avis.statut, StatutAvis.NOUVEAU)

    def test_statut_inconnu_refuse(self):
        avis = self._avis()
        with self.assertRaises(ValidationError) as contexte:
            changer_statut_avis(avis, 'en_cours_de_reflexion')
        self.assertIn('Statut inconnu',
                      str(contexte.exception.detail['statut'][0]))

    def test_un_avis_expire_ne_bouge_plus(self):
        avis = self._avis(statut=StatutAvis.EXPIRE)
        with self.assertRaises(ValidationError):
            changer_statut_avis(avis, StatutAvis.RETENU)

    def test_le_statut_ne_passe_pas_par_les_champs_supplementaires(self):
        """La porte dérobée est fermée explicitement."""
        avis = self._avis()
        with self.assertRaises(ValidationError):
            changer_statut_avis(
                avis, StatutAvis.RETENU,
                champs_supplementaires={'statut': StatutAvis.CONVERTI})

    def test_aucune_activite_ecrite_quand_la_transition_est_refusee(self):
        avis = self._avis()
        with self.assertRaises(ValidationError):
            changer_statut_avis(avis, StatutAvis.CONVERTI)
        self.assertEqual(
            Activity.objects.filter(company=self.company).count(), 0)


class JournalAuChatterTests(BaseStatut):
    def test_chaque_transition_ecrit_une_activite(self):
        avis = self._avis()
        changer_statut_avis(avis, StatutAvis.RETENU, user=self.user,
                            motif='Cible exactement dans notre métier.')

        activite = Activity.objects.get(company=self.company)
        self.assertEqual(activite.kind, Activity.Kind.MODIFICATION)
        self.assertEqual(activite.field, 'statut')
        self.assertEqual(activite.field_label, 'Statut')
        self.assertEqual(activite.old_value, 'Nouveau')
        self.assertEqual(activite.new_value, 'Retenu')
        self.assertEqual(activite.body,
                         'Cible exactement dans notre métier.')
        self.assertEqual(activite.created_by_id, self.user.pk)

    def test_historique_lisible_dans_l_ordre(self):
        avis = self._avis()
        changer_statut_avis(avis, StatutAvis.RETENU, user=self.user,
                            motif='On y va.')
        changer_statut_avis(avis, StatutAvis.CONVERTI, user=self.user,
                            motif='Dossier ouvert.')

        historique = list(
            Activity.objects.filter(company=self.company).order_by('id')
            .values_list('old_value', 'new_value'))
        self.assertEqual(
            historique,
            [('Nouveau', 'Retenu'),
             ('Retenu', "Converti en appel d'offres")])

    def test_expiration_automatique_journalisee_sans_utilisateur(self):
        self._avis(
            date_limite_remise=timezone.now() - dt.timedelta(days=1))

        bascules = AvisMarche.objects.filter(
            company=self.company).expirer_les_depasses()

        self.assertEqual(bascules, 1)
        activite = Activity.objects.get(company=self.company)
        self.assertIsNone(activite.created_by_id)
        self.assertEqual(activite.body, MOTIF_EXPIRATION_AUTOMATIQUE)
        self.assertEqual(activite.new_value, 'Expiré')

    def test_exclusion_automatique_journalisee_avec_le_motif_de_la_regle(self):
        RegleExclusion.objects.create(
            company=self.company, portee=PorteeExclusion.ACHETEUR,
            valeur='Commune de Test', motif='Acheteur hors périmètre',
            actif=True)
        avis = self._avis()

        appliquer_regles_exclusion(avis)

        avis.refresh_from_db()
        self.assertEqual(avis.statut, StatutAvis.IGNORE)
        activite = Activity.objects.get(company=self.company)
        self.assertIn('Acheteur hors périmètre', activite.body)

    def test_un_avis_deja_ignore_n_empile_pas_les_activites(self):
        RegleExclusion.objects.create(
            company=self.company, portee=PorteeExclusion.ACHETEUR,
            valeur='Commune de Test', motif='Acheteur hors périmètre',
            actif=True)
        avis = self._avis()
        appliquer_regles_exclusion(avis)
        appliquer_regles_exclusion(avis)
        self.assertEqual(
            Activity.objects.filter(company=self.company).count(), 1)


class StatutJamaisMuteHorsServiceTests(SimpleTestCase):
    """Test d'INTROSPECTION : ``services.py`` est le seul point de mutation.

    Une garde de revue humaine ne tient pas six mois ; celle-ci est mécanique
    et balaie tout le module (le collecteur et les imports à venir compris).
    """

    def _fichiers_du_module(self):
        for chemin in sorted(MODULE_DIR.rglob('*.py')):
            relatif = chemin.relative_to(MODULE_DIR).as_posix()
            if relatif.startswith(('migrations/', 'tests/')):
                continue
            if relatif == FICHIER_DU_SERVICE:
                continue
            yield relatif, chemin

    def test_aucune_affectation_de_statut_hors_du_service(self):
        fautifs = []
        for relatif, chemin in self._fichiers_du_module():
            arbre = ast.parse(chemin.read_text(encoding='utf-8'))
            for noeud in ast.walk(arbre):
                if not isinstance(noeud, ast.Assign):
                    continue
                for cible in noeud.targets:
                    if (isinstance(cible, ast.Attribute)
                            and cible.attr == 'statut'):
                        fautifs.append(f'{relatif}:{noeud.lineno}')
        self.assertEqual(
            fautifs, [],
            'Le statut ne se mute que par services.changer_statut_avis : '
            f'{fautifs}')

    def test_aucun_update_de_statut_en_masse_hors_du_service(self):
        """``.update(statut=…)`` contournerait le journal du chatter."""
        fautifs = []
        for relatif, chemin in self._fichiers_du_module():
            arbre = ast.parse(chemin.read_text(encoding='utf-8'))
            for noeud in ast.walk(arbre):
                if not isinstance(noeud, ast.Call):
                    continue
                fonction = noeud.func
                if not (isinstance(fonction, ast.Attribute)
                        and fonction.attr == 'update'):
                    continue
                if any(kw.arg == 'statut' for kw in noeud.keywords):
                    fautifs.append(f'{relatif}:{noeud.lineno}')
        self.assertEqual(fautifs, [], fautifs)


class AucunSignalCoreEventsTests(SimpleTestCase):
    """« Ne déclarer AUCUN nouveau signal ``core/events.py``. »

    Le dépôt fait rougir la CI sur tout signal sans abonné réel, et rien ici
    n'a besoin d'un abonné cross-app : la notification passera par un appel
    direct au service de notifications.
    """

    def test_le_module_n_importe_pas_le_bus_d_evenements(self):
        """Vérifié sur les IMPORTS réels (AST), pas sur le texte : un
        commentaire qui EXPLIQUE pourquoi on n'utilise pas le bus n'est pas
        une utilisation du bus."""
        fautifs = []
        for chemin in sorted(MODULE_DIR.rglob('*.py')):
            relatif = chemin.relative_to(MODULE_DIR).as_posix()
            if relatif.startswith(('migrations/', 'tests/')):
                continue
            arbre = ast.parse(chemin.read_text(encoding='utf-8'))
            for noeud in ast.walk(arbre):
                if isinstance(noeud, ast.Import):
                    if any(a.name.startswith('core.events')
                           for a in noeud.names):
                        fautifs.append(f'{relatif}:{noeud.lineno}')
                elif isinstance(noeud, ast.ImportFrom):
                    module = noeud.module or ''
                    if module.startswith('core.events'):
                        fautifs.append(f'{relatif}:{noeud.lineno}')
                    elif module == 'core' and any(
                            a.name == 'events' for a in noeud.names):
                        fautifs.append(f'{relatif}:{noeud.lineno}')
        self.assertEqual(fautifs, [], fautifs)

    def test_aucun_signal_declare_dans_core_events_pour_ce_module(self):
        from core import events
        fautifs = [
            nom for nom in dir(events)
            if 'veille' in nom.lower() or 'avis_marche' in nom.lower()
        ]
        self.assertEqual(fautifs, [], fautifs)
