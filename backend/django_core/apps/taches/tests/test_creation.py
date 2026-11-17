"""TCH36 — `creer_taches()`, le seul créateur (invariants 1, 5, 9, 29, 32) + `couleur_d_office`.

Base requise (`TestCase`, et `TransactionTestCase` pour la course de deux envois) : joué par la CI.
Deux sociétés réelles (`'a'`, `'b'`), deux comptes dans A. Chaque test relit les lignes STOCKÉES.
"""
import datetime
import threading
from unittest import mock

from django.db import connection
from django.http import Http404
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework import serializers

from apps.taches.choix import Couleur, StatutProjet, StatutRappel, StatutTache
from apps.taches.models.projets import Projet
from apps.taches.models.rythme import ReglagesRythme
from apps.taches.models.taches import ElementChecklist, Etiquette, EtiquetteTache, Rappel, RegleRecurrence, Tache
from apps.taches.services import creation
from apps.taches.services.creation import couleur_d_office, creer_taches
from apps.taches.services.gestes import annuler_geste
from apps.taches.tests import fabriques
from core.conflit_etat import ConflitEtat


def _j(delta):
    return timezone.localdate() + datetime.timedelta(days=delta)


def _ligne(titre='Appeler Karim', **champs):
    return {'titre': titre, **champs}


class CreationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a, cls.b = fabriques.societe('a'), fabriques.societe('b')
        cls.u1 = fabriques.compte(cls.a, nom='u1')
        cls.voisin = fabriques.compte(cls.a, nom='u2')
        cls.ailleurs = fabriques.compte(cls.b, nom='u1')

    def _creer(self, *lignes, user=None, porte='saisie', source='rapide', **options):
        return creer_taches(user or self.u1, list(lignes), source=source, porte=porte, **options)

    # --- Invariant 1 : À trier et `triee_le` ------------------------------------------------

    def test_rien_de_reconnu_reste_a_trier(self):
        tache = self._creer(_ligne()).creees[0]
        self.assertIsNone(Tache.objects.get(pk=tache.pk).triee_le)

    def test_echeance_seule_reste_a_trier(self):
        tache = self._creer(_ligne(echeance=_j(3).isoformat())).creees[0]
        relue = Tache.objects.get(pk=tache.pk)
        self.assertEqual((relue.echeance, relue.triee_le), (_j(3), None))

    def test_projet_jour_ou_reserve_sortent_d_a_trier(self):
        projet = fabriques.projet(self.u1)
        lignes = [_ligne('a', projet_id=projet.pk), _ligne('b', jour_prevu=_j(1).isoformat()),
                  _ligne('c', quelque_jour=True)]
        for tache in self._creer(*lignes, porte='capture', source='capture').creees:
            self.assertIsNotNone(Tache.objects.get(pk=tache.pk).triee_le)

    def test_rappel_sans_jour_donne_son_jour(self):
        tache = self._creer(_ligne(rappel={'jour': _j(2).isoformat(), 'heure': '09:00'})).creees[0]
        relue = Tache.objects.get(pk=tache.pk)
        self.assertEqual(relue.jour_prevu, _j(2))
        self.assertIsNotNone(relue.triee_le)
        rappel = Rappel.objects.get(tache=relue)
        self.assertEqual((rappel.jour, rappel.heure, rappel.statut),
                         (_j(2), datetime.time(9, 0), StatutRappel.EN_ATTENTE))

    def test_jour_heure_moment_par_planifier_sans_report(self):
        tache = self._creer(_ligne(jour_prevu=_j(0).isoformat(), heure_debut='15:00')).creees[0]
        relue = Tache.objects.get(pk=tache.pk)
        self.assertEqual((relue.jour_prevu, relue.heure_debut, relue.moment, relue.reports, relue.premier_jour_prevu),
                         (_j(0), datetime.time(15, 0), 'apres_midi', 0, _j(0)))

    # --- Invariant 5 : récurrence -------------------------------------------------------------

    def test_regle_neuve_premiere_occurrence(self):
        spec = {'frequence': 'quotidien', 'intervalle': 1, 'jours_semaine': '0000000', 'jour_du_mois': None,
                'rang_dans_mois': None, 'mode': 'calendrier', 'date_debut': _j(1).isoformat()}
        tache = self._creer(_ligne(recurrence=spec)).creees[0]
        relue = Tache.objects.get(pk=tache.pk)
        regle = RegleRecurrence.objects.get(pk=relue.recurrence_id)
        self.assertEqual((regle.proprietaire_id, regle.company_id, regle.frequence),
                         (self.u1.pk, self.a.pk, 'quotidien'))
        self.assertEqual((relue.occurrence_du, relue.jour_prevu), (_j(1), _j(1)))

    def test_une_seule_occurrence_ouverte_par_regle(self):
        regle = RegleRecurrence.objects.create(company=self.a, proprietaire=self.u1, frequence='quotidien',
                                               date_debut=_j(0))
        fabriques.tache(self.u1, recurrence=regle, occurrence_du=_j(0), jour_prevu=_j(0))
        with self.assertRaises(serializers.ValidationError):
            self._creer(_ligne(recurrence=regle.pk, occurrence_du=_j(1).isoformat()),
                        porte='recurrence', source='recurrence')
        Tache.objects.filter(recurrence=regle).update(statut=StatutTache.FAIT, fait_le=timezone.now())
        suivante = self._creer(_ligne(recurrence=regle.pk, occurrence_du=_j(1).isoformat()),
                               porte='recurrence', source='recurrence')
        self.assertEqual(Tache.objects.get(pk=suivante.creees[0].pk).occurrence_du, _j(1))
        self.assertIsNone(suivante.geste)

    def test_regle_d_un_autre_404(self):
        regle = RegleRecurrence.objects.create(company=self.a, proprietaire=self.voisin, frequence='quotidien',
                                               date_debut=_j(0))
        with self.assertRaises(Http404):
            self._creer(_ligne(recurrence=regle.pk), porte='recurrence', source='recurrence')

    # --- Invariant 9 : même propriétaire sur tout identifiant ---------------------------------

    def test_projet_d_un_autre_refuse_rien_ecrit(self):
        a_lui = fabriques.projet(self.voisin)
        with self.assertRaises(serializers.ValidationError) as ctx:
            self._creer(_ligne('ok'), _ligne('ko', projet_id=a_lui.pk))
        self.assertEqual(ctx.exception.detail, {'lignes': {'1': {'projet_id': ['Projet inexistant.']}}})
        self.assertFalse(Tache.objects.filter(proprietaire=self.u1).exists())
        self.assertFalse(ReglagesRythme.objects.filter(proprietaire=self.u1).exists())

    def test_projet_d_une_autre_societe_refuse(self):
        mien = fabriques.projet(self.u1)
        with self.assertRaises(serializers.ValidationError) as ctx:
            self._creer(_ligne(projet_id=mien.pk), user=self.ailleurs, porte='ecran', source='manuel')
        self.assertEqual(ctx.exception.detail, {'projet_id': ['Projet inexistant.']})

    def test_etape_etiquette_parent_d_un_autre_404(self):
        projet = fabriques.projet(self.u1)
        etape_a_lui = fabriques.section(fabriques.projet(self.voisin))
        etiquette_a_lui = Etiquette.objects.create(company=self.a, proprietaire=self.voisin, nom='lui')
        parent_a_lui = fabriques.tache(self.voisin)
        with self.assertRaises(Http404):
            self._creer(_ligne(projet_id=projet.pk, section_id=etape_a_lui.pk))
        with self.assertRaises(Http404):
            self._creer(_ligne(etiquettes=[etiquette_a_lui.pk]))
        with self.assertRaises(Http404):
            self._creer(_ligne(), parent=parent_a_lui.pk)
        self.assertFalse(Tache.objects.filter(proprietaire=self.u1).exists())

    def test_sous_tache_herite_projet_et_etape_un_seul_niveau(self):
        projet = fabriques.projet(self.u1)
        etape = fabriques.section(projet)
        parent = fabriques.tache(self.u1, projet=projet, section=etape)
        enfant = self._creer(_ligne('photos'), parent=parent, porte='ecran', source='manuel').creees[0]
        relue = Tache.objects.get(pk=enfant.pk)
        self.assertEqual((relue.parent_id, relue.projet_id, relue.section_id), (parent.pk, projet.pk, etape.pk))
        with self.assertRaises(Http404):
            self._creer(_ligne('petit-enfant'), parent=relue, porte='ecran', source='manuel')

    def test_lien_hors_cible_liable_refuse(self):
        with self.assertRaises(serializers.ValidationError) as ctx:
            self._creer(_ligne(), lien={'cible': 'stock.produit', 'id': 1}, porte='ecran', source='manuel')
        self.assertEqual(ctx.exception.detail, {'lien': ["Ce type d'élément ne peut pas être lié à une tâche."]})

    def test_le_libelle_du_lien_est_pose_a_la_liaison(self):
        with mock.patch('apps.taches.selectors.liens._par_la_porte',
                        side_effect=lambda user, app, cle, pk: {cle: 'Benali Karim'}):
            tache = self._creer(_ligne(), lien={'cible': 'crm.lead', 'id': 1637}, porte='ecran',
                                source='manuel').creees[0]
        relue = Tache.objects.get(pk=tache.pk)
        self.assertEqual((relue.object_id, relue.lien_etat, relue.lien_libelle), (1637, 'ok', 'Benali Karim'))

    def test_lien_introuvable_refuse(self):
        # Porte unique de visibilité : selectors/liens.cible_visible (TCH13, même fusion F1).
        with self.assertRaises(serializers.ValidationError) as ctx:
            self._creer(_ligne(), lien={'cible': 'crm.lead', 'id': 987654321}, porte='ecran', source='manuel')
        self.assertEqual(ctx.exception.detail, {'lien': ['Élément introuvable ou hors de ta portée.']})
        self.assertFalse(Tache.objects.exists())

    # --- Invariant 29 : réglages du rythme nés à la première tâche ----------------------------

    def test_reglages_nes_a_la_premiere_tache_une_seule_fois(self):
        self.assertFalse(ReglagesRythme.objects.filter(proprietaire=self.u1).exists())
        self._creer(_ligne('un'))
        self._creer(_ligne('deux'))
        self.assertEqual(ReglagesRythme.objects.filter(company=self.a, proprietaire=self.u1).count(), 1)
        self.assertFalse(ReglagesRythme.objects.filter(proprietaire=self.voisin).exists())

    def test_reglages_poses_avant_la_premiere_ligne(self):
        """Le verrou des plafonds de rappels porte sur `ReglagesRythme` : la ligne existe déjà quand
        la première tâche (et son rappel) s'écrit."""
        vus = []
        with mock.patch.object(creation, '_creer_ligne', side_effect=lambda ctx, ligne, cid: vus.append(
                ReglagesRythme.objects.filter(company=self.a, proprietaire=self.u1).exists())):
            self._creer(_ligne('un'), _ligne('deux'))
        self.assertEqual(vus, [True, True])

    # --- Invariant 32 : rang dans la liste -----------------------------------------------------

    def test_rang_projet_dernier_plus_1024(self):
        projet = fabriques.projet(self.u1)
        fabriques.tache(self.u1, projet=projet, rang_projet=5000)
        creees = self._creer(_ligne('a', projet_id=projet.pk), _ligne('b', projet_id=projet.pk), _ligne('c')).creees
        rangs = [Tache.objects.get(pk=t.pk).rang_projet for t in creees]
        self.assertEqual(rangs, [5000 + 1024, 5000 + 2048, 1024])

    # --- Idempotence par client_id ---------------------------------------------------------------

    def test_rejeu_au_meme_client_id(self):
        premier = self._creer(_ligne('a'), _ligne('b'), client_id='c1f4')
        second = self._creer(_ligne('a'), _ligne('b'), client_id='c1f4')
        self.assertEqual(len(premier.creees), 2)
        self.assertEqual((second.creees, second.deja_creees, second.geste), ([], ['c1f4:0', 'c1f4:1'], None))
        self.assertEqual(Tache.objects.filter(proprietaire=self.u1).count(), 2)

    def test_client_id_d_une_tache_supprimee_ne_recree_rien(self):
        tache = self._creer(_ligne(), client_id='x1').creees[0]
        Tache.objects.get(pk=tache.pk).soft_delete(self.u1, record=False)
        rejeu = self._creer(_ligne(), client_id='x1')
        self.assertEqual(rejeu.deja_creees, ['x1'])
        self.assertEqual(Tache.all_objects.filter(proprietaire=self.u1).count(), 1)

    def test_client_id_propre_a_la_ligne_et_par_compte(self):
        self._creer(_ligne(client_id='abc:0'))
        autre = self._creer(_ligne(client_id='abc:0'), user=self.voisin)
        self.assertEqual(len(autre.creees), 1)

    def test_client_id_long_coupe_la_base_jamais_le_suffixe(self):
        """63 caractères + `:0`…`:11` : couper le tout à 64 confondait `:1` et `:10` (une ligne perdue)."""
        resultat = self._creer(*(_ligne(f'ligne {n}') for n in range(12)), client_id='c' * 63)
        self.assertEqual((len(resultat.creees), resultat.deja_creees), (12, []))
        cles = list(Tache.objects.filter(proprietaire=self.u1).values_list('client_id', flat=True))
        self.assertEqual(len(set(cles)), 12)
        self.assertTrue(all(len(cle) <= 64 for cle in cles))
        self.assertIn('c' * 61 + ':10', cles)

    def test_course_relue_apres_integrity_error(self):
        """Fenêtre de la course forcée : la lecture préalable ne voit pas encore la tâche que l'autre
        envoi vient d'écrire ; l'`IntegrityError` est relue → déjà créée, aucune seconde tâche."""
        fabriques.tache(self.u1, client_id='course')
        with mock.patch.object(creation, '_tache_existante', side_effect=[False, True]):
            resultat = self._creer(_ligne(), client_id='course')
        self.assertEqual((resultat.creees, resultat.deja_creees), ([], ['course']))
        self.assertEqual(Tache.objects.filter(client_id='course').count(), 1)

    # --- Projets nés de la saisie et couleur d'office ------------------------------------------

    def test_nouveau_projet_ne_une_fois_moyenne_couleur_d_office(self):
        fabriques.projet(self.u1, couleur=Couleur.TERRE)
        resultat = self._creer(_ligne('a', nouveau_projet={'nom': 'SiteWeb', 'priorite': 2}),
                               _ligne('b', nouveau_projet={'nom': 'siteweb', 'priorite': 2}))
        self.assertEqual(len(resultat.projets_crees), 1)
        projet = Projet.objects.get(pk=resultat.projets_crees[0].pk)
        self.assertEqual((projet.nom, projet.priorite, projet.couleur, projet.proprietaire_id),
                         ('SiteWeb', 2, Couleur.AMBRE, self.u1.pk))
        self.assertEqual({Tache.objects.get(pk=t.pk).projet_id for t in resultat.creees}, {projet.pk})

    def test_nouveau_projet_existant_repris(self):
        existant = fabriques.projet(self.u1, nom='Maison')
        resultat = self._creer(_ligne(nouveau_projet={'nom': 'maison', 'priorite': 2}))
        self.assertEqual(resultat.projets_crees, [])
        self.assertEqual(Tache.objects.get(pk=resultat.creees[0].pk).projet_id, existant.pk)

    def test_couleur_d_office(self):
        self.assertEqual(couleur_d_office(self.u1), Couleur.TERRE)
        fabriques.projet(self.u1, couleur=Couleur.TERRE)
        fabriques.projet(self.u1, couleur=Couleur.AMBRE, statut=StatutProjet.ARCHIVE)
        self.assertEqual(couleur_d_office(self.u1), Couleur.AMBRE)
        for couleur in Couleur.values:
            fabriques.projet(self.u1, couleur=couleur)
        fabriques.projet(self.u1, couleur=Couleur.TERRE)
        self.assertEqual(couleur_d_office(self.u1), Couleur.AMBRE)
        self.assertEqual(couleur_d_office(self.voisin), Couleur.TERRE)

    def test_nouvelle_etape_get_or_create(self):
        projet = fabriques.projet(self.u1)
        resultat = self._creer(_ligne('a', projet_id=projet.pk, nouvelle_section={'nom': 'Études'}),
                               _ligne('b', projet_id=projet.pk, nouvelle_section={'nom': 'etudes'}))
        sections = {Tache.objects.get(pk=t.pk).section_id for t in resultat.creees}
        self.assertEqual(len(sections), 1)

    # --- Étiquettes, check-list, rappel ancré, activité --------------------------------------

    def test_etiquettes_checklist_rappel_ancre(self):
        mienne = Etiquette.objects.create(company=self.a, proprietaire=self.u1, nom='bureau')
        ligne = _ligne(jour_prevu=_j(2).isoformat(), etiquettes=[mienne.pk, {'nom': 'magasin'}, mienne.pk],
                       checklist=['Numéro', 'Prix'],
                       rappel={'ancre': 'jour_prevu', 'decalage_jours': 0, 'heure': '08:00'})
        tache = self._creer(ligne).creees[0]
        noms = set(EtiquetteTache.objects.filter(tache_id=tache.pk).values_list('etiquette__nom', flat=True))
        self.assertEqual(noms, {'bureau', 'magasin'})
        self.assertEqual(list(ElementChecklist.objects.filter(tache_id=tache.pk).order_by('rang')
                              .values_list('libelle', 'rang')), [('Numéro', 1024), ('Prix', 2048)])
        rappel = Rappel.objects.get(tache_id=tache.pk)
        self.assertEqual((rappel.ancre, rappel.jour), ('jour_prevu', _j(2)))

    def test_activite_liee_puis_deja_liee(self):
        activite = fabriques.activite(self.u1)
        tache = self._creer(_ligne(), porte='lien_activite', source='activite', activite=activite).creees[0]
        self.assertEqual(Tache.objects.get(pk=tache.pk).activite_origine_id, activite.pk)
        with self.assertRaises(ConflitEtat) as ctx:
            self._creer(_ligne(), porte='lien_activite', source='activite', activite=activite)
        self.assertEqual(ctx.exception.detail['code'], 'deja_lie')

    def test_activite_d_un_autre_404(self):
        activite = fabriques.activite(self.voisin)
        with self.assertRaises(Http404):
            self._creer(_ligne(), porte='lien_activite', source='activite', activite=activite)

    def test_a_faire_personnel_d_un_collegue_assigne_a_moi_404(self):
        """Un à-faire `personnelle=True` créé par un collègue, même assigné au compte, est
        introuvable (même réponse qu'une activité d'autrui) ; rien n'est écrit."""
        activite = fabriques.activite(self.u1, created_by=self.voisin)
        with self.assertRaises(Http404) as ctx:
            self._creer(_ligne(), porte='lien_activite', source='activite', activite=activite)
        self.assertEqual(str(ctx.exception), 'Introuvable.')
        self.assertFalse(Tache.all_objects.filter(activite_origine_id=activite.pk).exists())

    # --- Geste, messages, portes ---------------------------------------------------------------

    def test_annuler_la_saisie_supprime_tache_et_projet_ne(self):
        resultat = self._creer(_ligne(nouveau_projet={'nom': 'Salon', 'priorite': 2},
                                      rappel={'jour': _j(1).isoformat(), 'heure': '09:00'}))
        self.assertEqual((resultat.geste.type, resultat.geste.message), ('creation', 'Ajoutée pour demain'))
        annuler_geste(self.u1, resultat.geste.pk)
        self.assertTrue(Tache.all_objects.get(pk=resultat.creees[0].pk).is_deleted)
        self.assertTrue(Projet.all_objects.get(pk=resultat.projets_crees[0].pk).is_deleted)
        self.assertFalse(Rappel.objects.filter(tache_id=resultat.creees[0].pk).exists())

    def test_messages_du_geste(self):
        self.assertEqual(self._creer(_ligne()).geste.message, 'Ajoutée')
        self.assertEqual(self._creer(_ligne('a'), _ligne('b')).geste.message, '2 tâches créées')

    def test_porte_modele_sans_geste_et_porte_inconnue(self):
        self.assertIsNone(self._creer(_ligne(), porte='modele', source='modele').geste)
        with self.assertRaises(ValueError):
            self._creer(_ligne(), porte='corbeille')

    def test_titre_vide_par_ligne_tout_ou_rien(self):
        with self.assertRaises(serializers.ValidationError) as ctx:
            self._creer(_ligne('a'), _ligne('   ', index=7))
        self.assertEqual(ctx.exception.detail,
                         {'lignes': {'7': {'titre': ['Le titre est vide une fois la date et le projet retirés.']}}})
        self.assertFalse(Tache.objects.exists())

    def test_crochet_des_revelations_appele(self):
        with mock.patch('apps.taches.services.revelations.apres_creation') as crochet:
            resultat = self._creer(_ligne(), porte='capture', source='capture')
        crochet.assert_called_once_with(self.u1, resultat.creees, [], porte='capture')


class CourseDeuxEnvoisTests(TransactionTestCase):
    """Deux envois simultanés au même `client_id` (deux connexions) = UNE tâche."""

    def test_deux_creations_concurrentes_une_tache(self):
        societe = fabriques.societe('course')
        compte = fabriques.compte(societe, nom='u1')
        depart, resultats, erreurs = threading.Barrier(2), [], []

        def envoyer():
            try:
                depart.wait(timeout=10)
                resultats.append(creer_taches(compte, [_ligne()], source='rapide', porte='saisie',
                                              client_id='meme-envoi'))
            except Exception as exc:  # noqa: BLE001 — rapporté par l'assertion ci-dessous
                erreurs.append(exc)
            finally:
                connection.close()

        fils = [threading.Thread(target=envoyer) for _ in range(2)]
        for fil in fils:
            fil.start()
        for fil in fils:
            fil.join(timeout=30)
        self.assertEqual(erreurs, [])
        self.assertEqual(Tache.all_objects.filter(proprietaire=compte, client_id='meme-envoi').count(), 1)
        self.assertEqual(sorted(len(r.creees) for r in resultats), [0, 1])
        self.assertEqual(sorted(r.deja_creees for r in resultats), [[], ['meme-envoi']])
