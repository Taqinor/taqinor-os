"""TCH60-TCH64 — les routes `projets/`, `sections/` et `modeles/` : liste, création, fiche, PATCH, suppression,
ordre, clôture, vue, étapes, planification, décalage, dupliquer, modèles (reference/api.md §3.3, §4 ; invariants
17, 25, 27).

Base requise (`TestCase`) : joué par la CI. Les jours des tests sont RELATIFS à aujourd'hui (`_j`) : les routes
lisent l'horloge à leur frontière (`timezone.localdate()`), comme `planifier`. Chaque réponse est comparée aux
CLÉS de son échantillon de `contract_samples/` ; chaque état est relu en base après l'écriture.
"""
import datetime

from django.http import Http404
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework import serializers
from rest_framework.test import APIClient

from apps.taches.models.projets import ModeleProjet, Projet, Section
from apps.taches.models.taches import ElementChecklist, Tache
from apps.taches.selectors.base import jours_travailles_de
from apps.taches.services.gestes import annuler_geste
from apps.taches.services.projets import _rangs_apres_insertion
from apps.taches.tests import fabriques
from apps.taches.views.base import exemple_de

PREFIXE = '/api/django/taches/'
ENTETE_ASSISTANT = {'HTTP_X_TAQINOR_ASSISTANT': '1'}


def _j(delta):
    return timezone.localdate() + datetime.timedelta(days=delta)


def _url(chemin):
    return PREFIXE + chemin


class OrdreSansBaseTests(SimpleTestCase):
    """`_rangs_apres_insertion` : où va l'élément déplacé (pas de base)."""

    ORDRE = [(1, 1024), (2, 2048), (3, 3072)]

    def test_avant_le_premier(self):
        self.assertEqual(_rangs_apres_insertion(self.ORDRE, 9, 1, None), {9: 0})

    def test_apres_le_dernier(self):
        self.assertEqual(_rangs_apres_insertion(self.ORDRE, 9, None, 3), {9: 4096})

    def test_entre_deux_voisins(self):
        self.assertEqual(_rangs_apres_insertion(self.ORDRE, 9, 3, None), {9: 2560})

    def test_sans_place_toute_la_liste_est_renumerotee(self):
        rangs = _rangs_apres_insertion([(1, 5), (2, 6)], 9, 2, None)
        self.assertEqual(rangs, {1: 1024, 9: 2048, 2: 3072})

    def test_voisin_inconnu_404(self):
        with self.assertRaises(Http404):
            _rangs_apres_insertion(self.ORDRE, 9, 42, None)

    def test_sans_voisin_400(self):
        with self.assertRaises(serializers.ValidationError):
            _rangs_apres_insertion(self.ORDRE, 9, None, None)

    def test_seul_dans_la_liste(self):
        with self.assertRaises(Http404):
            _rangs_apres_insertion([], 9, None, 7)


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a, cls.b = fabriques.societe('a'), fabriques.societe('b')
        cls.u1 = fabriques.compte(cls.a, nom='u1')
        cls.voisin = fabriques.compte(cls.a, nom='u2')
        cls.ailleurs = fabriques.compte(cls.b, nom='u1')

    def _api(self, compte, assistant=False):
        api = APIClient()
        api.force_authenticate(compte)
        if assistant:
            api.credentials(**ENTETE_ASSISTANT)
        return api

    def _fait(self, compte, projet, **champs):
        return fabriques.tache(compte, projet=projet, statut='fait', fait_le=timezone.now(), **champs)

    def _projet_avec_taches(self):
        projet = fabriques.projet(self.u1, nom='À supprimer')
        ouverte = fabriques.tache(self.u1, projet=projet)
        faite = self._fait(self.u1, projet)
        return projet, ouverte, faite


class ListeProjetsTests(_Base):
    def test_forme_de_l_echantillon_et_constat(self):
        projet = fabriques.projet(self.u1, priorite=3)
        fabriques.tache(self.u1, projet=projet)
        reponse = self._api(self.u1).get(_url('projets/'))
        self.assertEqual(reponse.status_code, 200)
        corps = reponse.json()
        exemple = exemple_de('projets_liste')
        self.assertEqual(set(corps), set(exemple))
        self.assertEqual(set(corps['results'][0]), set(exemple['results'][0]))
        self.assertEqual(set(corps['constat']), set(exemple['constat']))
        self.assertEqual(corps['constat']['actifs'], 1)
        self.assertEqual(corps['results'][0]['compteurs'], {'ouvertes': 1, 'faites': 0})

    def test_filtre_de_statut(self):
        actif = fabriques.projet(self.u1)
        pause = fabriques.projet(self.u1, statut='en_pause')
        termine = fabriques.projet(self.u1, statut='termine', issue='atteint')
        archive = fabriques.projet(self.u1, statut='archive')

        def ids(parametre=''):
            reponse = self._api(self.u1).get(_url(f'projets/{parametre}'))
            return {p['id'] for p in reponse.json()['results']}
        self.assertEqual(ids(), {actif.pk, pause.pk})
        self.assertEqual(ids('?statut=actif'), {actif.pk})
        self.assertEqual(ids('?statut=en_pause'), {pause.pk})
        self.assertEqual(ids('?statut=archive'), {termine.pk, archive.pk})

    def test_statut_inconnu_400(self):
        reponse = self._api(self.u1).get(_url('projets/?statut=zzz'))
        self.assertEqual(reponse.status_code, 400)
        self.assertEqual(reponse.json()['statut'], ['Valeur inconnue.'])

    def test_ordre_manuel_et_pagination(self):
        premier = fabriques.projet(self.u1, rang=2048)
        second = fabriques.projet(self.u1, rang=1024)
        reponse = self._api(self.u1).get(_url('projets/?page_size=1'))
        corps = reponse.json()
        self.assertEqual(corps['count'], 2)
        self.assertEqual([p['id'] for p in corps['results']], [second.pk])
        self.assertIsNotNone(corps['next'])
        self.assertNotEqual(premier.pk, second.pk)

    def test_isolation_societe_et_proprietaire(self):
        fabriques.projet(self.voisin)
        fabriques.projet(self.ailleurs)
        mien = fabriques.projet(self.u1)
        reponse = self._api(self.u1).get(_url('projets/'))
        self.assertEqual([p['id'] for p in reponse.json()['results']], [mien.pk])

    def test_constat_compte_les_projets_qui_ont_avance(self):
        avance, immobile = fabriques.projet(self.u1), fabriques.projet(self.u1)
        self._fait(self.u1, avance)
        fabriques.tache(self.u1, projet=immobile)
        constat = self._api(self.u1).get(_url('projets/')).json()['constat']
        self.assertEqual(constat, {'actifs': 2, 'avances_7j': 1})

    def test_sante_a_l_arret_tout_fait_et_sans_prochaine_action(self):
        ancien = fabriques.projet(self.u1)
        fabriques.tache(self.u1, projet=ancien)
        Projet.objects.filter(pk=ancien.pk).update(statut_depuis=timezone.now() - datetime.timedelta(days=60))
        fini = fabriques.projet(self.u1)
        self._fait(self.u1, fini)
        reserve = fabriques.projet(self.u1)
        fabriques.tache(self.u1, projet=reserve, quelque_jour=True)
        par_id = {p['id']: p for p in self._api(self.u1).get(_url('projets/')).json()['results']}
        codes = lambda projet: [s['code'] for s in par_id[projet.pk]['sante']]  # noqa: E731
        self.assertIn('a_l_arret', codes(ancien))
        self.assertEqual(codes(fini), ['tout_fait'])
        self.assertEqual(codes(reserve), ['sans_prochaine_action'])
        self.assertEqual(set(par_id[ancien.pk]['sante'][0]), {'code', 'phrase', 'donnees'})

    def test_a_planifier_tant_qu_il_n_y_a_aucune_tache_ni_planification(self):
        vide = fabriques.projet(self.u1)
        occupe = fabriques.projet(self.u1)
        fabriques.tache(self.u1, projet=occupe)
        planifie = fabriques.projet(self.u1, planification_le=timezone.now())
        par_id = {p['id']: p for p in self._api(self.u1).get(_url('projets/')).json()['results']}
        self.assertTrue(par_id[vide.pk]['a_planifier'])
        self.assertFalse(par_id[occupe.pk]['a_planifier'])
        self.assertFalse(par_id[planifie.pk]['a_planifier'])

    def test_sans_le_droit_403(self):
        sans_droit = fabriques.compte(self.a, voir=False, nom='sans')
        self.assertEqual(self._api(sans_droit).get(_url('projets/')).status_code, 403)


class CreerProjetTests(_Base):
    def test_cree_avec_couleur_d_office_et_rend_projet_ecrit(self):
        reponse = self._api(self.u1).post(_url('projets/'), {'nom': 'Chantier X', 'priorite': 2}, format='json')
        self.assertEqual(reponse.status_code, 201)
        corps = reponse.json()
        exemple = exemple_de('projet_ecrit')
        self.assertEqual(set(corps), set(exemple))
        self.assertEqual(set(corps['projet']), set(exemple['projet']))
        projet = Projet.objects.get(pk=corps['projet']['id'])
        self.assertEqual((projet.nom, projet.priorite, projet.couleur), ('Chantier X', 2, 'terre'))
        self.assertEqual((projet.company_id, projet.proprietaire_id), (self.a.pk, self.u1.pk))
        self.assertTrue(corps['projet']['a_planifier'])
        self.assertIsNotNone(corps['geste_id'])

    def test_deuxieme_projet_prend_la_couleur_suivante(self):
        self._api(self.u1).post(_url('projets/'), {'nom': 'Un'}, format='json')
        reponse = self._api(self.u1).post(_url('projets/'), {'nom': 'Deux'}, format='json')
        self.assertEqual(reponse.json()['projet']['couleur'], 'ambre')

    def test_nom_requis(self):
        reponse = self._api(self.u1).post(_url('projets/'), {}, format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertEqual(reponse.json()['nom'], ['Requis.'])

    def test_nom_deja_pris_400_meme_avec_une_autre_casse(self):
        fabriques.projet(self.u1, nom='Chantier X')
        reponse = self._api(self.u1).post(_url('projets/'), {'nom': 'chantier  x'}, format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertEqual(reponse.json()['nom'], ['Un projet « chantier  x » existe déjà.'])

    def test_meme_nom_chez_un_autre_compte_est_permis(self):
        fabriques.projet(self.voisin, nom='Chantier X')
        reponse = self._api(self.u1).post(_url('projets/'), {'nom': 'Chantier X'}, format='json')
        self.assertEqual(reponse.status_code, 201)

    def test_societe_et_proprietaire_jamais_lus_du_corps(self):
        corps = {'nom': 'Piège', 'company': self.b.pk, 'company_id': self.b.pk, 'proprietaire': self.voisin.pk}
        reponse = self._api(self.u1).post(_url('projets/'), corps, format='json')
        projet = Projet.objects.get(pk=reponse.json()['projet']['id'])
        self.assertEqual((projet.company_id, projet.proprietaire_id), (self.a.pk, self.u1.pk))

    def test_valeurs_inconnues_400(self):
        reponse = self._api(self.u1).post(_url('projets/'), {'nom': 'Z', 'priorite': 9, 'couleur': 'rouge'},
                                          format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertEqual(reponse.json()['priorite'], ['Valeur inconnue.'])
        self.assertEqual(reponse.json()['couleur'], ['Valeur inconnue.'])

    def test_rejeu_avec_la_meme_cle_d_idempotence(self):
        api = self._api(self.u1)
        premier = api.post(_url('projets/'), {'nom': 'Une fois'}, format='json', HTTP_IDEMPOTENCY_KEY='cle-1')
        second = api.post(_url('projets/'), {'nom': 'Une fois'}, format='json', HTTP_IDEMPOTENCY_KEY='cle-1')
        self.assertEqual((premier.status_code, second.status_code), (201, 201))
        self.assertEqual(premier.json()['projet']['id'], second.json()['projet']['id'])
        self.assertEqual(Projet.objects.filter(company=self.a, proprietaire=self.u1, nom='Une fois').count(), 1)

    def test_le_geste_annule_la_creation(self):
        corps = self._api(self.u1).post(_url('projets/'), {'nom': 'Éphémère'}, format='json').json()
        annuler_geste(self.u1, corps['geste_id'])
        self.assertFalse(Projet.objects.filter(pk=corps['projet']['id']).exists())


class FicheEtPatchTests(_Base):
    def test_fiche_forme_projet(self):
        projet = fabriques.projet(self.u1)
        reponse = self._api(self.u1).get(_url(f'projets/{projet.pk}/'))
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(set(reponse.json()), set(exemple_de('projet')))

    def test_fiche_d_un_autre_compte_404(self):
        for autre in (self.voisin, self.ailleurs):
            projet = fabriques.projet(autre)
            self.assertEqual(self._api(self.u1).get(_url(f'projets/{projet.pk}/')).status_code, 404)

    def test_patch_modifie_et_avance_la_version(self):
        projet = fabriques.projet(self.u1, nom='Avant')
        corps = {'nom': 'Après', 'objectif': 'Fini quand…', 'priorite': 3, 'echeance': '2026-12-15',
                 'lock_version': projet.lock_version}
        reponse = self._api(self.u1).patch(_url(f'projets/{projet.pk}/'), corps, format='json')
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.json()['nom'], 'Après')
        projet.refresh_from_db()
        self.assertEqual((projet.nom, projet.nom_cle, projet.priorite), ('Après', 'apres', 3))
        self.assertEqual(reponse.json()['lock_version'], projet.lock_version)
        self.assertGreater(projet.lock_version, 0)

    def test_patch_sans_lock_version_400(self):
        projet = fabriques.projet(self.u1)
        reponse = self._api(self.u1).patch(_url(f'projets/{projet.pk}/'), {'nom': 'X'}, format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertEqual(reponse.json()['lock_version'], ['Requis.'])

    def test_patch_version_perimee_409_avec_l_etat_courant(self):
        projet = fabriques.projet(self.u1)
        api = self._api(self.u1)
        api.patch(_url(f'projets/{projet.pk}/'), {'objectif': 'A', 'lock_version': 0}, format='json')
        reponse = api.patch(_url(f'projets/{projet.pk}/'), {'objectif': 'B', 'lock_version': 0}, format='json')
        self.assertEqual(reponse.status_code, 409)
        corps = reponse.json()
        self.assertEqual(corps['code'], 'conflit_version')
        self.assertEqual(corps['actuel']['id'], projet.pk)
        self.assertEqual(corps['actuel']['objectif'], 'A')
        self.assertEqual(set(corps['actuel']), set(exemple_de('projet')))
        projet.refresh_from_db()
        self.assertEqual(projet.objectif, 'A')

    def test_statut_termine_passe_par_terminer(self):
        projet = fabriques.projet(self.u1)
        corps = {'statut': 'termine', 'lock_version': projet.lock_version}
        reponse = self._api(self.u1).patch(_url(f'projets/{projet.pk}/'), corps, format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertEqual(reponse.json()['statut'], ['Passe par « Terminer ».'])
        projet.refresh_from_db()
        self.assertEqual(projet.statut, 'actif')

    def test_mise_en_pause_et_reprise(self):
        projet = fabriques.projet(self.u1)
        api = self._api(self.u1)
        pause = api.patch(_url(f'projets/{projet.pk}/'), {'statut': 'en_pause', 'lock_version': 0}, format='json')
        self.assertEqual(pause.json()['statut'], 'en_pause')
        reprise = api.patch(_url(f'projets/{projet.pk}/'),
                            {'statut': 'actif', 'lock_version': pause.json()['lock_version']}, format='json')
        self.assertEqual(reprise.json()['statut'], 'actif')

    def test_affichage_fusionne_et_cles_fermees(self):
        projet = fabriques.projet(self.u1)
        api = self._api(self.u1)
        bon = api.patch(_url(f'projets/{projet.pk}/'), {'affichage': {'vue': 'tableau'}, 'lock_version': 0},
                        format='json')
        self.assertEqual(bon.json()['affichage'], {'vue': 'tableau', 'tri': 'manuel', 'groupe': 'section',
                                                   'montrer_faites': False})
        mauvais = api.patch(_url(f'projets/{projet.pk}/'),
                            {'affichage': {'couleur': 'x'}, 'lock_version': bon.json()['lock_version']},
                            format='json')
        self.assertEqual(mauvais.status_code, 400)
        self.assertEqual(mauvais.json()['affichage'], ['Clé inconnue.'])

    def test_nom_pris_par_un_autre_projet_400(self):
        fabriques.projet(self.u1, nom='Pris')
        projet = fabriques.projet(self.u1, nom='Libre')
        reponse = self._api(self.u1).patch(_url(f'projets/{projet.pk}/'), {'nom': 'pris', 'lock_version': 0},
                                           format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertEqual(reponse.json()['nom'], ['Un projet « pris » existe déjà.'])

    def test_patch_d_un_autre_compte_404(self):
        projet = fabriques.projet(self.voisin)
        reponse = self._api(self.u1).patch(_url(f'projets/{projet.pk}/'), {'nom': 'X', 'lock_version': 0},
                                           format='json')
        self.assertEqual(reponse.status_code, 404)

    def test_confidentiel_masque_le_nom_a_l_assistant(self):
        projet = fabriques.projet(self.u1, nom='Secret', confidentiel=True)
        ecran = self._api(self.u1).get(_url(f'projets/{projet.pk}/')).json()
        assistant = self._api(self.u1, assistant=True).get(_url(f'projets/{projet.pk}/')).json()
        self.assertEqual(ecran['nom'], 'Secret')
        self.assertNotEqual(assistant['nom'], 'Secret')


class SupprimerProjetTests(_Base):
    def test_supprime_le_projet_et_ses_taches_en_un_geste(self):
        projet, ouverte, faite = self._projet_avec_taches()
        reponse = self._api(self.u1).delete(_url(f'projets/{projet.pk}/'))
        self.assertEqual(reponse.status_code, 200)
        corps = reponse.json()
        self.assertEqual(set(corps), set(exemple_de('projet_ecrit')))
        self.assertEqual(corps['supprimees'], 2)
        self.assertIsNotNone(corps['geste_id'])
        self.assertTrue(Projet.all_objects.get(pk=projet.pk).is_deleted)
        for tache in (ouverte, faite):
            self.assertTrue(Tache.all_objects.get(pk=tache.pk).is_deleted)

    def test_annuler_rend_le_projet_et_ses_taches(self):
        projet, ouverte, faite = self._projet_avec_taches()
        geste = self._api(self.u1).delete(_url(f'projets/{projet.pk}/')).json()['geste_id']
        bilan = annuler_geste(self.u1, geste)
        self.assertEqual(bilan['conflits'], [])
        self.assertFalse(Projet.all_objects.get(pk=projet.pk).is_deleted)
        for tache in (ouverte, faite):
            vivante = Tache.all_objects.get(pk=tache.pk)
            self.assertFalse(vivante.is_deleted)
            self.assertEqual(vivante.projet_id, projet.pk)

    def test_supprimer_un_projet_d_un_autre_compte_404(self):
        projet = fabriques.projet(self.voisin)
        self.assertEqual(self._api(self.u1).delete(_url(f'projets/{projet.pk}/')).status_code, 404)
        self.assertFalse(Projet.all_objects.get(pk=projet.pk).is_deleted)


class RestaurerProjetTests(_Base):
    def test_restaurer_rend_seulement_les_taches_supprimees_avec_lui(self):
        projet, ouverte, faite = self._projet_avec_taches()
        avant = fabriques.tache(self.u1, projet=projet)
        avant.soft_delete(self.u1, record=False)
        api = self._api(self.u1)
        api.delete(_url(f'projets/{projet.pk}/'))
        reponse = api.post(_url(f'projets/{projet.pk}/restaurer/'))
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.json()['restaurees'], 2)
        self.assertFalse(Projet.all_objects.get(pk=projet.pk).is_deleted)
        self.assertFalse(Tache.all_objects.get(pk=ouverte.pk).is_deleted)
        self.assertFalse(Tache.all_objects.get(pk=faite.pk).is_deleted)
        self.assertTrue(Tache.all_objects.get(pk=avant.pk).is_deleted)

    def test_restaurer_409_nom_pris_quand_un_projet_actif_porte_le_nom(self):
        projet, _, _ = self._projet_avec_taches()
        api = self._api(self.u1)
        api.delete(_url(f'projets/{projet.pk}/'))
        fabriques.projet(self.u1, nom='À supprimer')
        reponse = api.post(_url(f'projets/{projet.pk}/restaurer/'))
        self.assertEqual(reponse.status_code, 409)
        self.assertEqual(reponse.json()['code'], 'nom_pris')
        self.assertTrue(Projet.all_objects.get(pk=projet.pk).is_deleted)

    def test_restaurer_un_projet_d_un_autre_compte_404(self):
        projet = fabriques.projet(self.voisin)
        projet.soft_delete(self.voisin, record=False)
        self.assertEqual(self._api(self.u1).post(_url(f'projets/{projet.pk}/restaurer/')).status_code, 404)


class OrdreEtClotureTests(_Base):
    def _ordre(self):
        return list(Projet.objects.filter(proprietaire=self.u1).order_by('rang', 'id').values_list('pk', flat=True))

    def test_mettre_en_haut(self):
        un, deux, trois = (fabriques.projet(self.u1, rang=r) for r in (1024, 2048, 3072))
        reponse = self._api(self.u1).post(_url(f'projets/{trois.pk}/reordonner/'), {'avant_id': un.pk}, format='json')
        self.assertEqual(reponse.status_code, 204)
        self.assertEqual(self._ordre(), [trois.pk, un.pk, deux.pk])

    def test_apres_un_voisin(self):
        un, deux, trois = (fabriques.projet(self.u1, rang=r) for r in (1024, 2048, 3072))
        self._api(self.u1).post(_url(f'projets/{un.pk}/reordonner/'), {'apres_id': deux.pk}, format='json')
        self.assertEqual(self._ordre(), [deux.pk, un.pk, trois.pk])

    def test_reordonner_ne_touche_ni_a_la_version_ni_au_nom(self):
        un, deux = fabriques.projet(self.u1, rang=1024), fabriques.projet(self.u1, rang=2048)
        self._api(self.u1).post(_url(f'projets/{deux.pk}/reordonner/'), {'avant_id': un.pk}, format='json')
        deux.refresh_from_db()
        self.assertEqual(deux.lock_version, 0)

    def test_voisin_d_un_autre_compte_404_et_sans_voisin_400(self):
        un = fabriques.projet(self.u1)
        etranger = fabriques.projet(self.voisin)
        api = self._api(self.u1)
        self.assertEqual(api.post(_url(f'projets/{un.pk}/reordonner/'), {'avant_id': etranger.pk},
                                  format='json').status_code, 404)
        self.assertEqual(api.post(_url(f'projets/{un.pk}/reordonner/'), {}, format='json').status_code, 400)

    def test_trier_par_priorite(self):
        basse = fabriques.projet(self.u1, priorite=1, rang=1024)
        haute = fabriques.projet(self.u1, priorite=3, rang=2048)
        moyenne = fabriques.projet(self.u1, priorite=2, rang=3072)
        reponse = self._api(self.u1).post(_url('projets/trier-par-priorite/'))
        self.assertEqual(reponse.status_code, 204)
        self.assertEqual(self._ordre(), [haute.pk, moyenne.pk, basse.pk])

    def test_terminer_exige_atteint_ou_abandonne(self):
        projet = fabriques.projet(self.u1)
        reponse = self._api(self.u1).post(_url(f'projets/{projet.pk}/terminer/'), {}, format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertEqual(reponse.json()['issue'], ['Atteint ou abandonné ?'])
        projet.refresh_from_db()
        self.assertEqual(projet.statut, 'actif')

    def test_terminer_remet_les_taches_ouvertes_dans_a_trier(self):
        projet = fabriques.projet(self.u1)
        ouverte = fabriques.tache(self.u1, projet=projet)
        faite = self._fait(self.u1, projet)
        corps = {'issue': 'atteint', 'bilan': 'Signé', 'taches_ouvertes': 'boite'}
        reponse = self._api(self.u1).post(_url(f'projets/{projet.pk}/terminer/'), corps, format='json')
        self.assertEqual(reponse.status_code, 200)
        rendu = reponse.json()
        self.assertEqual(set(rendu), set(exemple_de('projet_ecrit')))
        self.assertEqual((rendu['projet']['statut'], rendu['projet']['issue'], rendu['deplacees']),
                         ('termine', 'atteint', 1))
        projet.refresh_from_db()
        self.assertEqual((projet.bilan, projet.statut), ('Signé', 'termine'))
        self.assertIsNotNone(projet.termine_le)
        ouverte.refresh_from_db()
        faite.refresh_from_db()
        self.assertIsNone(ouverte.projet_id)
        self.assertIsNone(ouverte.triee_le)
        self.assertEqual(faite.projet_id, projet.pk)

    def test_terminer_abandonne_les_taches_ouvertes(self):
        projet = fabriques.projet(self.u1)
        ouverte = fabriques.tache(self.u1, projet=projet)
        corps = {'issue': 'abandonne', 'taches_ouvertes': 'annuler'}
        self._api(self.u1).post(_url(f'projets/{projet.pk}/terminer/'), corps, format='json')
        ouverte.refresh_from_db()
        self.assertEqual(ouverte.statut, 'annule')
        self.assertIsNotNone(ouverte.annule_le)
        self.assertEqual(ouverte.projet_id, projet.pk)

    def test_terminer_deplace_vers_un_autre_projet(self):
        projet, cible = fabriques.projet(self.u1), fabriques.projet(self.u1)
        deja = fabriques.tache(self.u1, projet=cible)
        ouverte = fabriques.tache(self.u1, projet=projet)
        corps = {'issue': 'atteint', 'taches_ouvertes': 'deplacer', 'projet_cible_id': cible.pk}
        reponse = self._api(self.u1).post(_url(f'projets/{projet.pk}/terminer/'), corps, format='json')
        self.assertEqual(reponse.status_code, 200)
        ouverte.refresh_from_db()
        self.assertEqual(ouverte.projet_id, cible.pk)
        self.assertGreater(ouverte.rang_projet, deja.rang_projet)

    def test_deplacer_exige_une_cible_du_compte(self):
        projet = fabriques.projet(self.u1)
        fabriques.tache(self.u1, projet=projet)
        etranger = fabriques.projet(self.voisin)
        api = self._api(self.u1)
        sans = api.post(_url(f'projets/{projet.pk}/terminer/'),
                        {'issue': 'atteint', 'taches_ouvertes': 'deplacer'}, format='json')
        self.assertEqual(sans.json()['projet_cible_id'], ['Requis.'])
        autre = api.post(_url(f'projets/{projet.pk}/terminer/'),
                         {'issue': 'atteint', 'taches_ouvertes': 'deplacer', 'projet_cible_id': etranger.pk},
                         format='json')
        self.assertEqual(autre.status_code, 400)
        self.assertEqual(autre.json()['projet_cible_id'], ['Projet inexistant.'])
        projet.refresh_from_db()
        self.assertEqual(projet.statut, 'actif')

    def test_terminer_avec_des_ouvertes_exige_leur_sort(self):
        projet = fabriques.projet(self.u1)
        fabriques.tache(self.u1, projet=projet)
        reponse = self._api(self.u1).post(_url(f'projets/{projet.pk}/terminer/'), {'issue': 'atteint'},
                                          format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertEqual(reponse.json()['taches_ouvertes'], ['Requis.'])

    def test_annuler_la_cloture_rend_projet_et_taches(self):
        projet = fabriques.projet(self.u1)
        ouverte = fabriques.tache(self.u1, projet=projet)
        corps = {'issue': 'atteint', 'taches_ouvertes': 'boite'}
        geste = self._api(self.u1).post(_url(f'projets/{projet.pk}/terminer/'), corps, format='json').json()['geste_id']
        bilan = annuler_geste(self.u1, geste)
        self.assertEqual(bilan['conflits'], [])
        projet.refresh_from_db()
        ouverte.refresh_from_db()
        self.assertEqual((projet.statut, projet.issue), ('actif', ''))
        self.assertIsNone(projet.termine_le)
        self.assertEqual(ouverte.projet_id, projet.pk)

    def test_terminer_un_projet_termine_ne_fait_rien(self):
        projet = fabriques.projet(self.u1, statut='termine', issue='atteint')
        reponse = self._api(self.u1).post(_url(f'projets/{projet.pk}/terminer/'), {'issue': 'abandonne'},
                                          format='json')
        self.assertEqual(reponse.status_code, 200)
        self.assertIsNone(reponse.json()['geste_id'])
        projet.refresh_from_db()
        self.assertEqual(projet.issue, 'atteint')

    def test_rouvrir(self):
        projet = fabriques.projet(self.u1, statut='termine', issue='atteint', bilan='Bravo',
                                  termine_le=timezone.now())
        reponse = self._api(self.u1).post(_url(f'projets/{projet.pk}/rouvrir/'))
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.json()['projet']['statut'], 'actif')
        projet.refresh_from_db()
        self.assertEqual((projet.issue, projet.bilan), ('', 'Bravo'))
        self.assertIsNone(projet.termine_le)

    def test_rouvrir_un_projet_d_un_autre_compte_404(self):
        projet = fabriques.projet(self.voisin, statut='archive')
        self.assertEqual(self._api(self.u1).post(_url(f'projets/{projet.pk}/rouvrir/')).status_code, 404)


class VueEtEtapesTests(_Base):
    def test_vue_forme_de_l_echantillon(self):
        projet = fabriques.projet(self.u1)
        etape = fabriques.section(projet, nom='Études')
        fabriques.tache(self.u1, projet=projet, section=etape)
        fabriques.tache(self.u1, projet=projet)
        reponse = self._api(self.u1).get(_url(f'projets/{projet.pk}/vue/?vue=tableau'))
        self.assertEqual(reponse.status_code, 200)
        corps = reponse.json()
        exemple = exemple_de('projet_vue')
        self.assertEqual(set(corps), set(exemple))
        self.assertEqual(set(corps['sections'][0]), set(exemple['sections'][0]))
        self.assertEqual(set(corps['sections'][0]['taches'][0]), set(exemple_de('item')))
        self.assertEqual(len(corps['sections'][0]['taches']), 1)
        self.assertEqual(len(corps['sans_section']), 1)
        self.assertEqual(corps['avancement'], {'faites': 0, 'total': 2, 'derniere_faite_le': None})

    def test_vue_inconnue_400_et_projet_etranger_404(self):
        projet = fabriques.projet(self.u1)
        etranger = fabriques.projet(self.voisin)
        api = self._api(self.u1)
        self.assertEqual(api.get(_url(f'projets/{projet.pk}/vue/?vue=zzz')).status_code, 400)
        self.assertEqual(api.get(_url(f'projets/{etranger.pk}/vue/')).status_code, 404)

    def test_avancement_et_faites_nb(self):
        projet = fabriques.projet(self.u1)
        fabriques.tache(self.u1, projet=projet)
        self._fait(self.u1, projet)
        self._fait(self.u1, projet)
        fabriques.tache(self.u1, projet=projet, statut='annule', annule_le=timezone.now())
        corps = self._api(self.u1).get(_url(f'projets/{projet.pk}/vue/')).json()
        self.assertEqual(corps['avancement']['faites'], 2)
        self.assertEqual(corps['avancement']['total'], 3)
        self.assertEqual(corps['avancement']['derniere_faite_le'], timezone.localdate().isoformat())
        self.assertEqual(corps['faites_nb'], 2)

    def test_les_faites_ne_sont_servies_que_si_montrer_faites(self):
        projet = fabriques.projet(self.u1)
        ouverte = fabriques.tache(self.u1, projet=projet)
        faite = self._fait(self.u1, projet)
        api = self._api(self.u1)

        def ids():
            corps = api.get(_url(f'projets/{projet.pk}/vue/')).json()
            return {t['id'] for t in corps['sans_section']}
        self.assertEqual(ids(), {ouverte.pk})
        Projet.objects.filter(pk=projet.pk).update(affichage={'montrer_faites': True})
        self.assertEqual(ids(), {ouverte.pk, faite.pk})

    def test_prochain_jalon_et_prochaine_action(self):
        projet = fabriques.projet(self.u1)
        fabriques.tache(self.u1, projet=projet, quelque_jour=True)
        action = fabriques.tache(self.u1, projet=projet)
        fabriques.tache(self.u1, projet=projet, jalon=True, echeance=_j(30))
        proche = fabriques.tache(self.u1, projet=projet, jalon=True, echeance=_j(10))
        corps = self._api(self.u1).get(_url(f'projets/{projet.pk}/vue/')).json()
        self.assertEqual(corps['prochain_jalon']['id'], proche.pk)
        self.assertEqual(corps['prochaine_action']['id'], action.pk)

    def test_compte_par_etape_et_faites_du_projet(self):
        projet = fabriques.projet(self.u1)
        etape = fabriques.section(projet)
        fabriques.tache(self.u1, projet=projet, section=etape)
        ancienne = self._fait(self.u1, projet, section=etape)
        Tache.objects.filter(pk=ancienne.pk).update(fait_le=timezone.now() - datetime.timedelta(days=2))
        recente = self._fait(self.u1, projet)
        corps = self._api(self.u1).get(_url(f'projets/{projet.pk}/vue/')).json()
        self.assertEqual(corps['sections'][0]['compteurs'], {'ouvertes': 1, 'faites': 1})
        self.assertEqual(corps['sans_section_compteurs'], {'ouvertes': 0, 'faites': 1})
        # « Faites (n) » : la liste paginée des tâches, la plus récemment faite d'abord.
        faites = self._api(self.u1).get(_url(f'taches/?projet={projet.pk}&statut=fait&tri=fait_le')).json()
        self.assertEqual([t['id'] for t in faites['results']], [recente.pk, ancienne.pk])
        self.assertEqual(faites['count'], 2)

    def test_les_item_portent_explication_essentielle_et_plan_comme_la_journee(self):
        from apps.taches.models.journee import LignePlanJour
        from apps.taches.selectors import journee as sel
        from apps.taches.serializers.formes import charger_items
        from apps.taches.serializers.journee import Rendu
        jour = timezone.localdate()
        projet = fabriques.projet(self.u1, nom='Ventes')
        etoilee = fabriques.tache(self.u1, projet=projet, jour_prevu=jour)
        simple = fabriques.tache(self.u1, projet=projet)
        plan = fabriques.plan(self.u1, jour)
        LignePlanJour.objects.create(company=self.a, plan=plan, tache=etoilee, prevue_au_plan=True, essentielle=True)
        corps = self._api(self.u1).get(_url(f'projets/{projet.pk}/vue/')).json()
        items = {t['id']: t for t in corps['sans_section']}
        self.assertEqual((items[etoilee.pk]['essentielle'], items[etoilee.pk]['prevue_au_plan']), (True, True))
        self.assertEqual((items[simple.pk]['essentielle'], items[simple.pk]['prevue_au_plan']), (False, False))
        attendu = Rendu(sel.lire_journee(self.u1, jour, charger=charger_items)).calcul(('tache', etoilee.pk))
        self.assertTrue(attendu['explication'])
        self.assertEqual(items[etoilee.pk]['explication'], attendu['explication'])
        self.assertEqual(corps['prochaine_action']['explication'], attendu['explication'])

    def test_sans_jalon_ni_action_les_deux_sont_nuls(self):
        projet = fabriques.projet(self.u1)
        corps = self._api(self.u1).get(_url(f'projets/{projet.pk}/vue/')).json()
        self.assertIsNone(corps['prochain_jalon'])
        self.assertIsNone(corps['prochaine_action'])
        self.assertEqual((corps['burnup'], corps['burnup_legende']), ([], ''))

    def test_burnup_par_semaine_close_avec_sa_legende(self):
        projet = fabriques.projet(self.u1)
        ancienne = fabriques.tache(self.u1, projet=projet)
        Tache.objects.filter(pk=ancienne.pk).update(created_at=timezone.now() - datetime.timedelta(days=20))
        corps = self._api(self.u1).get(_url(f'projets/{projet.pk}/vue/')).json()
        self.assertGreaterEqual(len(corps['burnup']), 2)
        self.assertEqual(set(corps['burnup'][0]), {'semaine', 'total', 'faites'})
        self.assertEqual(datetime.date.fromisoformat(corps['burnup'][0]['semaine']).weekday(), 0)
        self.assertEqual(corps['burnup_legende'], 'reconstruit depuis les dates actuelles')

    # --- Étapes ------------------------------------------------------------------------------

    def test_creer_une_etape(self):
        projet = fabriques.projet(self.u1)
        corps = {'projet_id': projet.pk, 'nom': 'Études', 'date_fin': '2026-11-30'}
        reponse = self._api(self.u1).post(_url('sections/'), corps, format='json')
        self.assertEqual(reponse.status_code, 201)
        self.assertEqual(set(reponse.json()), {'id', 'projet_id', 'nom', 'rang', 'date_debut', 'date_fin', 'geste_id'})
        section = Section.objects.get(pk=reponse.json()['id'])
        self.assertEqual((section.projet_id, section.company_id, section.nom), (projet.pk, self.a.pk, 'Études'))
        self.assertEqual(section.date_fin, datetime.date(2026, 11, 30))

    def test_etape_nom_pris_dates_inversees_et_projet_etranger(self):
        projet = fabriques.projet(self.u1)
        fabriques.section(projet, nom='Études')
        etranger = fabriques.projet(self.voisin)
        api = self._api(self.u1)
        pris = api.post(_url('sections/'), {'projet_id': projet.pk, 'nom': 'études'}, format='json')
        self.assertEqual(pris.status_code, 400)
        self.assertEqual(pris.json()['nom'], ['Une étape « études » existe déjà.'])
        inversees = api.post(_url('sections/'), {'projet_id': projet.pk, 'nom': 'Pose', 'date_debut': '2026-12-02',
                                                 'date_fin': '2026-12-01'}, format='json')
        self.assertEqual(inversees.json()['date_fin'], ['La date de fin précède la date de début.'])
        autre = api.post(_url('sections/'), {'projet_id': etranger.pk, 'nom': 'Pose'}, format='json')
        self.assertEqual(autre.status_code, 400)
        self.assertEqual(autre.json()['projet_id'], ['Projet inexistant.'])

    def test_renommer_une_etape(self):
        section = fabriques.section(fabriques.projet(self.u1), nom='Avant')
        reponse = self._api(self.u1).patch(_url(f'sections/{section.pk}/'), {'nom': 'Après'}, format='json')
        self.assertEqual(reponse.status_code, 200)
        section.refresh_from_db()
        self.assertEqual((section.nom, section.nom_cle), ('Après', 'apres'))

    def test_etape_d_un_autre_compte_404(self):
        section = fabriques.section(fabriques.projet(self.voisin))
        api = self._api(self.u1)
        self.assertEqual(api.patch(_url(f'sections/{section.pk}/'), {'nom': 'X'}, format='json').status_code, 404)
        self.assertEqual(api.delete(_url(f'sections/{section.pk}/')).status_code, 404)
        self.assertEqual(api.post(_url(f'sections/{section.pk}/reordonner/'), {'avant_id': 1},
                                  format='json').status_code, 404)

    def test_supprimer_une_etape_laisse_ses_taches_sans_etape_et_s_annule(self):
        projet = fabriques.projet(self.u1)
        section = fabriques.section(projet)
        tache = fabriques.tache(self.u1, projet=projet, section=section)
        reponse = self._api(self.u1).delete(_url(f'sections/{section.pk}/'))
        self.assertEqual(reponse.status_code, 200)
        self.assertFalse(Section.objects.filter(pk=section.pk).exists())
        tache.refresh_from_db()
        self.assertIsNone(tache.section_id)
        bilan = annuler_geste(self.u1, reponse.json()['geste_id'])
        self.assertEqual(bilan['conflits'], [])
        tache.refresh_from_db()
        self.assertEqual(tache.section_id, section.pk)
        self.assertEqual(Section.objects.get(pk=section.pk).nom, section.nom)

    def test_reordonner_les_etapes(self):
        projet = fabriques.projet(self.u1)
        un, deux, trois = (fabriques.section(projet, rang=r) for r in (1024, 2048, 3072))
        reponse = self._api(self.u1).post(_url(f'sections/{trois.pk}/reordonner/'), {'avant_id': un.pk},
                                          format='json')
        self.assertEqual(reponse.status_code, 204)
        ordre = list(Section.objects.filter(projet=projet).order_by('rang', 'id').values_list('pk', flat=True))
        self.assertEqual(ordre, [trois.pk, un.pk, deux.pk])


class PlanificationTests(_Base):
    TEXTE = 'Études :\nVisite\n- photos\n◆ Mise en service'

    def test_apercu_rend_exactement_l_echantillon_sans_rien_ecrire(self):
        projet = fabriques.projet(self.u1)
        reponse = self._api(self.u1).post(_url(f'projets/{projet.pk}/planification/apercu/'),
                                          {'texte': self.TEXTE}, format='json')
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.json(), exemple_de('planification_apercu'))
        self.assertEqual(Tache.objects.count(), 0)
        self.assertEqual(Section.objects.count(), 0)

    def test_apercu_limites_et_projet_etranger(self):
        projet = fabriques.projet(self.u1)
        etranger = fabriques.projet(self.voisin)
        api = self._api(self.u1)
        trop = api.post(_url(f'projets/{projet.pk}/planification/apercu/'), {'texte': 'a\n' * 201}, format='json')
        self.assertEqual(trop.status_code, 400)
        self.assertEqual(trop.json()['texte'],
                         ['Liste trop longue : 200 lignes au plus (ici 201). Colle-la en deux fois.'])
        self.assertEqual(api.post(_url(f'projets/{projet.pk}/planification/apercu/'), {},
                                  format='json').status_code, 400)
        self.assertEqual(api.post(_url(f'projets/{etranger.pk}/planification/apercu/'), {'texte': 'a'},
                                  format='json').status_code, 404)

    def test_apercu_403_sous_l_en_tete_assistant_pour_un_projet_confidentiel(self):
        secret = fabriques.projet(self.u1, confidentiel=True)
        ordinaire = fabriques.projet(self.u1)
        assistant = self._api(self.u1, assistant=True)
        refus = assistant.post(_url(f'projets/{secret.pk}/planification/apercu/'), {'texte': 'a'}, format='json')
        self.assertEqual(refus.status_code, 403)
        ok = assistant.post(_url(f'projets/{ordinaire.pk}/planification/apercu/'), {'texte': 'a'}, format='json')
        self.assertEqual(ok.status_code, 200)
        ecran = self._api(self.u1).post(_url(f'projets/{secret.pk}/planification/apercu/'), {'texte': 'a'},
                                        format='json')
        self.assertEqual(ecran.status_code, 200)

    def _plan(self, projet, **plus):
        corps = {
            'priorite': 3, 'objectif': 'Stand monté', 'echeance': _j(40).isoformat(), 'risque': 'Retard transport',
            'sections': [{'nom': 'Études', 'taches': [
                {'titre': 'Visite', 'jalon': False, 'sous_taches': ['photos']},
                {'titre': 'Mise en service', 'jalon': True, 'sous_taches': []}]}],
            'actions': [{'titre': 'Réserver le stand', 'quand': 'aujourdhui'}],
            'lock_version': projet.lock_version, **plus}
        return corps

    def test_cree_tout_en_un_et_rend_l_echantillon(self):
        projet = fabriques.projet(self.u1)
        reponse = self._api(self.u1).post(_url(f'projets/{projet.pk}/planification/'), self._plan(projet),
                                          format='json')
        self.assertEqual(reponse.status_code, 201)
        corps = reponse.json()
        exemple = exemple_de('planification')
        self.assertEqual(set(corps), set(exemple))
        self.assertEqual(set(corps['projet']), set(exemple['projet']))
        self.assertEqual(set(corps['creees'][0]), set(exemple['creees'][0]))
        self.assertEqual(len(corps['creees']), 4)
        projet.refresh_from_db()
        self.assertEqual((projet.priorite, projet.objectif, projet.risque), (3, 'Stand monté', 'Retard transport'))
        self.assertEqual(projet.echeance, _j(40))
        self.assertIsNotNone(projet.planification_le)
        etape = Section.objects.get(projet=projet, nom='Études')
        visite = Tache.objects.get(projet=projet, titre='Visite')
        self.assertEqual(visite.section_id, etape.pk)
        self.assertTrue(Tache.objects.get(projet=projet, titre='Mise en service').jalon)
        photos = Tache.objects.get(projet=projet, titre='photos')
        self.assertEqual((photos.parent_id, photos.projet_id, photos.section_id), (visite.pk, projet.pk, etape.pk))
        action = Tache.objects.get(projet=projet, titre='Réserver le stand')
        self.assertEqual((action.jour_prevu, action.section_id), (_j(0), None))
        self.assertEqual(Tache.objects.filter(projet=projet).count(), 4)
        self.assertFalse(corps['projet']['a_planifier'])

    def test_une_etape_existante_est_reprise(self):
        projet = fabriques.projet(self.u1)
        existante = fabriques.section(projet, nom='études')
        self._api(self.u1).post(_url(f'projets/{projet.pk}/planification/'), self._plan(projet), format='json')
        self.assertEqual(Section.objects.filter(projet=projet).count(), 1)
        self.assertEqual(Tache.objects.get(projet=projet, titre='Visite').section_id, existante.pk)

    def test_un_geste_annule_tout(self):
        projet = fabriques.projet(self.u1)
        geste = self._api(self.u1).post(_url(f'projets/{projet.pk}/planification/'), self._plan(projet),
                                        format='json').json()['geste_id']
        bilan = annuler_geste(self.u1, geste)
        self.assertEqual(bilan['conflits'], [])
        self.assertEqual(Tache.objects.filter(projet=projet).count(), 0)
        self.assertEqual(Section.objects.filter(projet=projet).count(), 0)
        projet.refresh_from_db()
        self.assertEqual((projet.priorite, projet.objectif), (0, ''))
        self.assertIsNone(projet.planification_le)

    def test_version_requise_et_perimee(self):
        projet = fabriques.projet(self.u1)
        api = self._api(self.u1)
        sans = self._plan(projet)
        del sans['lock_version']
        self.assertEqual(api.post(_url(f'projets/{projet.pk}/planification/'), sans, format='json').json()
                         ['lock_version'], ['Requis.'])
        perimee = api.post(_url(f'projets/{projet.pk}/planification/'), self._plan(projet, lock_version=7),
                           format='json')
        self.assertEqual(perimee.status_code, 409)
        self.assertEqual(perimee.json()['code'], 'conflit_version')
        self.assertEqual(perimee.json()['actuel']['id'], projet.pk)
        self.assertEqual(Tache.objects.filter(projet=projet).count(), 0)

    def test_tout_ou_rien_sur_une_erreur(self):
        projet = fabriques.projet(self.u1)
        corps = self._plan(projet, actions=[{'titre': 'x' * 300}])
        reponse = self._api(self.u1).post(_url(f'projets/{projet.pk}/planification/'), corps, format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertEqual(Tache.objects.filter(projet=projet).count(), 0)
        self.assertEqual(Section.objects.filter(projet=projet).count(), 0)

    def test_rejeu_avec_la_meme_cle(self):
        projet = fabriques.projet(self.u1)
        api = self._api(self.u1)
        corps = self._plan(projet)
        api.post(_url(f'projets/{projet.pk}/planification/'), corps, format='json', HTTP_IDEMPOTENCY_KEY='plan-1')
        api.post(_url(f'projets/{projet.pk}/planification/'), corps, format='json', HTTP_IDEMPOTENCY_KEY='plan-1')
        self.assertEqual(Tache.objects.filter(projet=projet).count(), 4)

    def test_planification_d_un_projet_etranger_404(self):
        etranger = fabriques.projet(self.voisin)
        reponse = self._api(self.u1).post(_url(f'projets/{etranger.pk}/planification/'), self._plan(etranger),
                                          format='json')
        self.assertEqual(reponse.status_code, 404)


class DecalerTests(_Base):
    def _projet_date(self):
        projet = fabriques.projet(self.u1, echeance=_j(20))
        section = fabriques.section(projet, date_fin=_j(15))
        tache = fabriques.tache(self.u1, projet=projet, section=section, jour_prevu=_j(3), echeance=_j(6))
        faite = self._fait(self.u1, projet, jour_prevu=_j(2))
        return projet, section, tache, faite

    def test_apercu_ne_change_rien(self):
        projet, section, tache, faite = self._projet_date()
        reponse = self._api(self.u1).post(_url(f'projets/{projet.pk}/decaler/'),
                                          {'delta_jours': 7, 'apercu': True}, format='json')
        self.assertEqual(reponse.status_code, 200)
        corps = reponse.json()
        exemple = exemple_de('decalage')
        self.assertEqual(set(corps), set(exemple))
        self.assertEqual(set(corps['changements'][0]), set(exemple['changements'][0]))
        self.assertIsNone(corps['geste_id'])
        objets = {(c['objet'], c['id'], c['champ']) for c in corps['changements']}
        self.assertEqual(objets, {('projet', projet.pk, 'echeance'), ('section', section.pk, 'date_fin'),
                                  ('tache', tache.pk, 'jour_prevu'), ('tache', tache.pk, 'echeance')})
        self.assertEqual(Tache.objects.get(pk=tache.pk).jour_prevu, _j(3))
        self.assertEqual(Projet.objects.get(pk=projet.pk).echeance, _j(20))

    def test_sans_apercu_rien_n_est_ecrit_non_plus(self):
        projet, _, tache, _ = self._projet_date()
        self._api(self.u1).post(_url(f'projets/{projet.pk}/decaler/'), {'delta_jours': 7}, format='json')
        self.assertEqual(Tache.objects.get(pk=tache.pk).jour_prevu, _j(3))

    def test_applique_sur_des_jours_travailles_et_laisse_les_faites_intactes(self):
        projet, section, tache, faite = self._projet_date()
        reponse = self._api(self.u1).post(_url(f'projets/{projet.pk}/decaler/'),
                                          {'delta_jours': 7, 'apercu': False}, format='json')
        self.assertEqual(reponse.status_code, 200)
        self.assertIsNotNone(reponse.json()['geste_id'])
        tache.refresh_from_db()
        projet.refresh_from_db()
        section.refresh_from_db()
        for date, avant in ((tache.jour_prevu, _j(3)), (tache.echeance, _j(6)), (projet.echeance, _j(20)),
                            (section.date_fin, _j(15))):
            self.assertGreaterEqual(date, avant + datetime.timedelta(days=7))
            self.assertEqual(jours_travailles_de(self.u1, date, date), {date})
        self.assertEqual(Tache.objects.get(pk=faite.pk).jour_prevu, _j(2))
        self.assertEqual(Tache.objects.get(pk=tache.pk).reports, 0)

    def test_refus_quand_une_tache_passerait_avant_aujourd_hui(self):
        projet = fabriques.projet(self.u1)
        fabriques.tache(self.u1, projet=projet, jour_prevu=_j(0))
        reponse = self._api(self.u1).post(_url(f'projets/{projet.pk}/decaler/'),
                                          {'delta_jours': -3, 'apercu': False}, format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertEqual(reponse.json()['delta_jours'], ["1 tâche passerait avant aujourd'hui."])

    def test_le_refus_rend_l_apercu_titre(self):
        projet = fabriques.projet(self.u1)
        tache = fabriques.tache(self.u1, projet=projet, jour_prevu=_j(0), titre='Signer Settat')
        corps = self._api(self.u1).post(_url(f'projets/{projet.pk}/decaler/'),
                                        {'delta_jours': -3, 'apercu': False}, format='json').json()
        self.assertEqual(corps['avant_aujourdhui'], [tache.pk])
        self.assertEqual([(c['objet'], c['id'], c['champ'], c['titre']) for c in corps['changements']],
                         [('tache', tache.pk, 'jour_prevu', 'Signer Settat')])
        self.assertEqual(Tache.objects.get(pk=tache.pk).jour_prevu, _j(0))  # rien n'est écrit

    def test_les_lignes_portent_leur_titre_confidentialite_comprise(self):
        projet, section, tache, _ = self._projet_date()
        corps = self._api(self.u1).post(_url(f'projets/{projet.pk}/decaler/'), {'delta_jours': 7},
                                        format='json').json()
        titres = {(c['objet'], c['id']): c['titre'] for c in corps['changements']}
        self.assertEqual(titres[('tache', tache.pk)], tache.titre)
        self.assertEqual(titres[('section', section.pk)], section.nom)
        self.assertEqual(titres[('projet', projet.pk)], projet.nom)
        Projet.objects.filter(pk=projet.pk).update(confidentiel=True)
        corps = self._api(self.u1, assistant=True).post(_url(f'projets/{projet.pk}/decaler/'), {'delta_jours': 7},
                                                        format='json').json()
        titres = {(c['objet'], c['id']): c['titre'] for c in corps['changements']}
        self.assertEqual(titres[('tache', tache.pk)], 'Tâche confidentielle')
        self.assertEqual(titres[('section', section.pk)], 'Étape')
        self.assertEqual(titres[('projet', projet.pk)], 'Projet confidentiel')

    def test_le_geste_annule_le_decalage(self):
        projet, section, tache, _ = self._projet_date()
        geste = self._api(self.u1).post(_url(f'projets/{projet.pk}/decaler/'),
                                        {'delta_jours': 7, 'apercu': False}, format='json').json()['geste_id']
        bilan = annuler_geste(self.u1, geste)
        self.assertEqual(bilan['conflits'], [])
        tache.refresh_from_db()
        self.assertEqual((tache.jour_prevu, tache.echeance), (_j(3), _j(6)))
        self.assertEqual(Projet.objects.get(pk=projet.pk).echeance, _j(20))
        self.assertEqual(Section.objects.get(pk=section.pk).date_fin, _j(15))

    def test_projet_sans_date_ni_changement(self):
        projet = fabriques.projet(self.u1)
        reponse = self._api(self.u1).post(_url(f'projets/{projet.pk}/decaler/'),
                                          {'delta_jours': 7, 'apercu': False}, format='json')
        self.assertEqual(reponse.json(), {'changements': [], 'geste_id': None})

    def test_delta_requis_et_projet_etranger(self):
        projet, etranger = fabriques.projet(self.u1), fabriques.projet(self.voisin)
        api = self._api(self.u1)
        self.assertEqual(api.post(_url(f'projets/{projet.pk}/decaler/'), {}, format='json').status_code, 400)
        self.assertEqual(api.post(_url(f'projets/{etranger.pk}/decaler/'), {'delta_jours': 7},
                                  format='json').status_code, 404)


class ModelesTests(_Base):
    """TCH64 — dupliquer, « Enregistrer comme modèle », modèles (liste, fiche, renommer, supprimer, instancier)."""

    def _source(self, **champs):
        """Un projet daté : une étape, une tâche avec check-list, notes et sous-tâche, un jalon bloqué par elle,
        une tâche faite (comptée), une abandonnée et une confidentielle (ces deux-là ne sont jamais figées)."""
        projet = fabriques.projet(self.u1, nom='Salon 2026', objectif='Stand monté', priorite=2,
                                  date_debut=_j(10), **champs)
        etape = fabriques.section(projet, nom='Préparation', date_debut=_j(10), date_fin=_j(24))
        a = fabriques.tache(self.u1, projet=projet, section=etape, titre='Réserver le stand', priorite=3,
                            jour_prevu=_j(10), echeance=_j(15), notes='Appeler Lydec')
        ElementChecklist.objects.create(company=self.a, tache=a, libelle='Prix', rang=1024)
        fabriques.tache(self.u1, projet=projet, section=etape, titre='photos', parent=a)
        fabriques.tache(self.u1, projet=projet, titre='Montage', jalon=True, bloquee_par=a, echeance=_j(30))
        self._fait(self.u1, projet, titre='Déjà faite', jour_prevu=_j(12))
        fabriques.tache(self.u1, projet=projet, titre='Abandonnée', statut='annule')
        fabriques.tache(self.u1, projet=projet, titre='Secrète', confidentiel=True)
        return projet, etape, a

    def _enregistrer(self, projet, nom='Salon', **plus):
        return self._api(self.u1).post(_url(f'projets/{projet.pk}/enregistrer-modele/'), {'nom': nom, **plus},
                                       format='json')

    # --- Enregistrer comme modèle ---------------------------------------------------------------

    def test_enregistrer_fige_le_projet_en_decalages_et_rend_l_echantillon(self):
        projet, _, _ = self._source()
        reponse = self._enregistrer(projet, inclure_notes=True)
        self.assertEqual(reponse.status_code, 201)
        corps = reponse.json()
        exemple = exemple_de('modele')
        self.assertEqual(set(corps), set(exemple))
        self.assertEqual(set(corps['contenu']), set(exemple['contenu']))
        self.assertEqual(set(corps['contenu']['sections'][0]), set(exemple['contenu']['sections'][0]))
        self.assertEqual(set(corps['contenu']['taches'][0]), set(exemple['contenu']['taches'][0]))
        contenu = corps['contenu']
        self.assertEqual((contenu['v'], contenu['objectif'], contenu['priorite']), (1, 'Stand monté', 2))
        self.assertEqual(contenu['sections'], [{'nom': 'Préparation', 'decalage_debut': 0, 'decalage_fin': 14}])
        titres = [t['titre'] for t in contenu['taches']]
        self.assertEqual(titres, ['Réserver le stand', 'photos', 'Montage', 'Déjà faite'])
        reserver, photos, montage, faite = contenu['taches']
        self.assertEqual((reserver['decalage_jour'], reserver['decalage_echeance']), (0, 5))
        self.assertEqual((reserver['section_index'], reserver['priorite'], reserver['notes']),
                         (0, 3, 'Appeler Lydec'))
        self.assertEqual(reserver['checklist'], ['Prix'])
        self.assertEqual((photos['parent_index'], montage['bloquee_par_index'], montage['jalon']), (0, 0, True))
        self.assertEqual(faite['decalage_jour'], 2)
        modele = ModeleProjet.objects.get(pk=corps['id'])
        self.assertEqual((modele.proprietaire_id, modele.company_id, modele.cree_depuis_id),
                         (self.u1.pk, self.a.pk, projet.pk))

    def test_les_notes_ne_sont_figees_que_sur_demande(self):
        projet, _, _ = self._source()
        sans = self._enregistrer(projet, nom='Sans notes').json()
        self.assertNotIn('notes', sans['contenu']['taches'][0])
        avec = self._enregistrer(projet, nom='Avec notes', inclure_notes=True).json()
        self.assertEqual(avec['contenu']['taches'][0]['notes'], 'Appeler Lydec')

    def test_ni_l_abandonnee_ni_la_confidentielle_ne_partent_dans_un_modele(self):
        projet, _, _ = self._source()
        titres = [t['titre'] for t in self._enregistrer(projet).json()['contenu']['taches']]
        self.assertNotIn('Abandonnée', titres)
        self.assertNotIn('Secrète', titres)
        self.assertEqual(Tache.objects.get(titre='Secrète').projet_id, projet.pk)  # rien n'est retiré du projet

    def test_enregistrer_refus_nom_pris_projet_etranger_et_nom_requis(self):
        projet, _, _ = self._source()
        etranger = fabriques.projet(self.voisin)
        self.assertEqual(self._enregistrer(projet).status_code, 201)
        pris = self._enregistrer(projet, nom='SALON')
        self.assertEqual(pris.status_code, 400)
        self.assertEqual(pris.json()['nom'], ['Un modèle « SALON » existe déjà.'])
        self.assertEqual(self._api(self.u1).post(_url(f'projets/{projet.pk}/enregistrer-modele/'), {},
                                                 format='json').status_code, 400)
        self.assertEqual(self._enregistrer(etranger, nom='Autre').status_code, 404)
        self.assertEqual(ModeleProjet.objects.count(), 1)

    def test_un_projet_confidentiel_ne_s_enregistre_pas_par_l_assistant(self):
        secret = fabriques.projet(self.u1, confidentiel=True)
        assistant = self._api(self.u1, assistant=True)
        refus = assistant.post(_url(f'projets/{secret.pk}/enregistrer-modele/'), {'nom': 'X'}, format='json')
        self.assertEqual(refus.status_code, 403)
        self.assertEqual(ModeleProjet.objects.count(), 0)
        self.assertEqual(self._enregistrer(secret, nom='Écran').status_code, 201)

    # --- Liste, fiche, renommer, supprimer --------------------------------------------------------

    def test_liste_paginee_a_la_forme_de_l_echantillon(self):
        projet, _, _ = self._source()
        self._enregistrer(projet, nom='Salon')
        etranger = fabriques.projet(self.voisin)
        ModeleProjet.objects.create(company=self.a, proprietaire=self.voisin, nom='Autre', contenu={'v': 1},
                                    cree_depuis=etranger)
        reponse = self._api(self.u1).get(_url('modeles/'))
        self.assertEqual(reponse.status_code, 200)
        corps = reponse.json()
        exemple = exemple_de('modeles_liste')
        self.assertEqual(set(corps), set(exemple))
        self.assertEqual(set(corps['results'][0]), set(exemple['results'][0]))
        self.assertEqual([(m['nom'], m['nb_taches'], m['nb_sections']) for m in corps['results']],
                         [('Salon', 4, 1)])

    def test_enregistrer_puis_relire_rend_le_meme_objet(self):
        projet, _, _ = self._source()
        ecrit = self._enregistrer(projet, inclure_notes=True).json()
        relu = self._api(self.u1).get(_url(f'modeles/{ecrit["id"]}/')).json()
        self.assertEqual(relu, ecrit)
        renomme = self._api(self.u1).patch(_url(f'modeles/{ecrit["id"]}/'), {'nom': relu['nom']}, format='json')
        self.assertEqual(renomme.status_code, 200)
        self.assertEqual(self._api(self.u1).get(_url(f'modeles/{ecrit["id"]}/')).json(), ecrit)

    def test_renommer_un_modele(self):
        projet, _, _ = self._source()
        premier = self._enregistrer(projet, nom='Salon').json()['id']
        second = self._enregistrer(projet, nom='Foire').json()['id']
        api = self._api(self.u1)
        ok = api.patch(_url(f'modeles/{premier}/'), {'nom': 'Salon 2027'}, format='json')
        self.assertEqual((ok.status_code, ok.json()['nom']), (200, 'Salon 2027'))
        pris = api.patch(_url(f'modeles/{second}/'), {'nom': 'salon 2027'}, format='json')
        self.assertEqual((pris.status_code, pris.json()['nom']), (400, ['Un modèle « salon 2027 » existe déjà.']))
        self.assertEqual(api.patch(_url(f'modeles/{second}/'), {}, format='json').status_code, 400)
        self.assertEqual(ModeleProjet.objects.get(pk=second).nom, 'Foire')

    def test_supprimer_un_modele_laisse_les_projets(self):
        projet, _, _ = self._source()
        modele = self._enregistrer(projet).json()['id']
        reponse = self._api(self.u1).delete(_url(f'modeles/{modele}/'))
        self.assertEqual((reponse.status_code, reponse.json()), (200, {'geste_id': None}))
        self.assertFalse(ModeleProjet.objects.filter(pk=modele).exists())
        self.assertTrue(Projet.objects.filter(pk=projet.pk).exists())
        self.assertEqual(self._api(self.u1).get(_url(f'modeles/{modele}/')).status_code, 404)

    def test_le_modele_d_un_autre_compte_repond_comme_un_id_inconnu(self):
        etranger = fabriques.projet(self.voisin)
        modele = ModeleProjet.objects.create(company=self.a, proprietaire=self.voisin, nom='Autre',
                                             contenu={'v': 1}, cree_depuis=etranger)
        api = self._api(self.u1)
        corps = {'nom': 'X', 'apercu': True}
        for reponse in (api.get(_url(f'modeles/{modele.pk}/')), api.delete(_url(f'modeles/{modele.pk}/')),
                        api.patch(_url(f'modeles/{modele.pk}/'), {'nom': 'X'}, format='json'),
                        api.post(_url(f'modeles/{modele.pk}/instancier/'), corps, format='json')):
            self.assertEqual(reponse.status_code, 404)
        self.assertTrue(ModeleProjet.objects.filter(pk=modele.pk, nom='Autre').exists())

    def test_un_modele_issu_d_un_projet_confidentiel_est_ferme_a_l_assistant(self):
        secret = fabriques.projet(self.u1, confidentiel=True)
        modele = self._enregistrer(secret, nom='Secret').json()['id']
        assistant = self._api(self.u1, assistant=True)
        self.assertEqual(assistant.get(_url(f'modeles/{modele}/')).status_code, 403)
        self.assertEqual(assistant.post(_url(f'modeles/{modele}/instancier/'), {'nom': 'X'},
                                        format='json').status_code, 403)
        self.assertEqual(assistant.get(_url('modeles/')).status_code, 200)  # le décompte seul
        self.assertEqual(self._api(self.u1).get(_url(f'modeles/{modele}/')).status_code, 200)

    # --- Instancier -------------------------------------------------------------------------------

    def _modele(self):
        projet, _, _ = self._source()
        return self._enregistrer(projet, inclure_notes=False).json()['id']

    def _premier_jour_travaille(self, jour):
        return min(jours_travailles_de(self.u1, jour, jour + datetime.timedelta(days=14)))

    def test_apercu_annonce_les_dates_rectifiees_sans_rien_ecrire(self):
        modele = self._modele()
        projets, taches, sections = Projet.objects.count(), Tache.objects.count(), Section.objects.count()
        reponse = self._api(self.u1).post(_url(f'modeles/{modele}/instancier/'),
                                          {'nom': 'Salon 2027', 'date_lancement': _j(40).isoformat(),
                                           'apercu': True}, format='json')
        self.assertEqual(reponse.status_code, 200)
        corps = reponse.json()
        exemple = exemple_de('modele_instancier')
        self.assertEqual(set(corps), set(exemple))
        self.assertEqual(set(corps['projet']), set(exemple['projet']))
        self.assertEqual(set(corps['sections'][0]), set(exemple['sections'][0]))
        self.assertEqual(set(corps['taches'][0]), set(exemple['taches'][0]))
        self.assertEqual(corps['projet'], {'nom': 'Salon 2027'})
        self.assertIsNone(corps['geste_id'])
        reserver = corps['taches'][0]
        self.assertEqual(reserver['jour_prevu'], self._premier_jour_travaille(_j(40)).isoformat())
        self.assertEqual(reserver['echeance'], self._premier_jour_travaille(_j(45)).isoformat())
        self.assertEqual((Projet.objects.count(), Tache.objects.count(), Section.objects.count()),
                         (projets, taches, sections))

    def test_apercu_est_le_defaut_et_rien_n_est_ecrit(self):
        modele = self._modele()
        projets = Projet.objects.count()
        reponse = self._api(self.u1).post(_url(f'modeles/{modele}/instancier/'), {'nom': 'Salon 2027'},
                                          format='json')
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(Projet.objects.count(), projets)

    def test_creer_le_projet_depuis_le_modele(self):
        modele = self._modele()
        reponse = self._api(self.u1).post(_url(f'modeles/{modele}/instancier/'),
                                          {'nom': 'Salon 2027', 'date_lancement': _j(40).isoformat(),
                                           'apercu': False}, format='json')
        self.assertEqual(reponse.status_code, 201)
        corps = reponse.json()
        exemple = exemple_de('projet_ecrit')
        self.assertEqual(set(corps), set(exemple))
        self.assertEqual(set(corps['projet']), set(exemple['projet']))
        projet = Projet.objects.get(pk=corps['projet']['id'])
        self.assertEqual((projet.nom, projet.priorite, projet.objectif, projet.proprietaire_id),
                         ('Salon 2027', 2, 'Stand monté', self.u1.pk))
        self.assertFalse(projet.confidentiel)
        etape = Section.objects.get(projet=projet)
        self.assertEqual((etape.nom, etape.date_debut), ('Préparation', self._premier_jour_travaille(_j(40))))
        taches = {t.titre: t for t in Tache.objects.filter(projet=projet)}
        self.assertEqual(sorted(taches), ['Déjà faite', 'Montage', 'Réserver le stand', 'photos'])
        reserver = taches['Réserver le stand']
        self.assertEqual((reserver.section_id, reserver.priorite, reserver.source, reserver.notes),
                         (etape.pk, 3, 'modele', ''))
        self.assertEqual(reserver.jour_prevu, self._premier_jour_travaille(_j(40)))
        self.assertEqual(list(ElementChecklist.objects.filter(tache=reserver).values_list('libelle', flat=True)),
                         ['Prix'])
        self.assertEqual((taches['photos'].parent_id, taches['photos'].section_id), (reserver.pk, etape.pk))
        self.assertEqual((taches['Montage'].bloquee_par_id, taches['Montage'].jalon), (reserver.pk, True))
        self.assertEqual(taches['Déjà faite'].statut, 'a_faire')  # remise à faire
        self.assertEqual(Tache.objects.filter(projet=projet).exclude(source='modele').count(), 0)

    def test_annuler_supprime_le_projet_cree(self):
        modele = self._modele()
        corps = self._api(self.u1).post(_url(f'modeles/{modele}/instancier/'),
                                        {'nom': 'Salon 2027', 'apercu': False}, format='json').json()
        self.assertIsNotNone(corps['geste_id'])
        projet = Projet.objects.get(pk=corps['projet']['id'])
        bilan = annuler_geste(self.u1, corps['geste_id'])
        self.assertEqual(bilan['conflits'], [])
        self.assertFalse(Projet.objects.filter(pk=projet.pk).exists())
        self.assertEqual(Tache.objects.filter(projet=projet).count(), 0)
        self.assertEqual(Section.objects.filter(projet=projet).count(), 0)

    def test_nom_de_projet_pris_et_rejeu_de_la_meme_cle(self):
        modele = self._modele()
        api = self._api(self.u1)
        pris = api.post(_url(f'modeles/{modele}/instancier/'), {'nom': 'salon 2026', 'apercu': True}, format='json')
        self.assertEqual((pris.status_code, pris.json()['nom']), (400, ['Un projet « salon 2026 » existe déjà.']))
        corps = {'nom': 'Salon 2027', 'apercu': False}
        for _ in range(2):
            api.post(_url(f'modeles/{modele}/instancier/'), corps, format='json', HTTP_IDEMPOTENCY_KEY='inst-1')
        self.assertEqual(Projet.objects.filter(nom='Salon 2027').count(), 1)

    def test_un_modele_d_un_projet_confidentiel_donne_un_projet_confidentiel(self):
        secret = fabriques.projet(self.u1, confidentiel=True)
        modele = self._enregistrer(secret, nom='Secret').json()['id']
        corps = self._api(self.u1).post(_url(f'modeles/{modele}/instancier/'), {'nom': 'Copie', 'apercu': False},
                                        format='json').json()
        self.assertTrue(Projet.objects.get(pk=corps['projet']['id']).confidentiel)

    def test_un_modele_sans_date_cree_un_projet_sans_date(self):
        projet = fabriques.projet(self.u1, nom='Sans dates')
        fabriques.tache(self.u1, projet=projet, titre='Une tâche')
        modele = self._enregistrer(projet, nom='Nu').json()['id']
        corps = self._api(self.u1).post(_url(f'modeles/{modele}/instancier/'), {'nom': 'Copie nue'},
                                        format='json').json()
        self.assertEqual(corps['taches'], [{'titre': 'Une tâche', 'jour_prevu': None, 'echeance': None}])

    # --- Dupliquer --------------------------------------------------------------------------------

    def test_dupliquer_apercu_puis_creation_avec_les_notes(self):
        projet, _, _ = self._source()
        api = self._api(self.u1)
        url = _url(f'projets/{projet.pk}/dupliquer/')
        apercu = api.post(url, {'nom': 'Salon 2027', 'date_debut': _j(40).isoformat(), 'apercu': True},
                          format='json')
        self.assertEqual(apercu.status_code, 200)
        exemple = exemple_de('modele_instancier')
        self.assertEqual(set(apercu.json()), set(exemple))
        self.assertEqual(Projet.objects.filter(nom='Salon 2027').count(), 0)
        cree = api.post(url, {'nom': 'Salon 2027', 'date_debut': _j(40).isoformat(), 'apercu': False},
                        format='json')
        self.assertEqual(cree.status_code, 201)
        double = Projet.objects.get(pk=cree.json()['projet']['id'])
        self.assertEqual((double.objectif, double.priorite), ('Stand monté', 2))
        reserver = Tache.objects.get(projet=double, titre='Réserver le stand')
        self.assertEqual(reserver.notes, 'Appeler Lydec')
        self.assertEqual(reserver.jour_prevu, self._premier_jour_travaille(_j(40)))
        self.assertEqual(Tache.objects.filter(projet=projet).count(), 6)  # l'original ne bouge pas
        self.assertFalse(Tache.objects.filter(projet=double, titre='Secrète').exists())

    def test_dupliquer_un_projet_confidentiel_donne_un_double_confidentiel(self):
        secret = fabriques.projet(self.u1, confidentiel=True, nom='Secret')
        fabriques.tache(self.u1, projet=secret, titre='Une tâche')
        corps = self._api(self.u1).post(_url(f'projets/{secret.pk}/dupliquer/'), {'nom': 'Double', 'apercu': False},
                                        format='json').json()
        self.assertTrue(Projet.objects.get(pk=corps['projet']['id']).confidentiel)
        refus = self._api(self.u1, assistant=True).post(_url(f'projets/{secret.pk}/dupliquer/'), {'nom': 'Autre'},
                                                        format='json')
        self.assertEqual(refus.status_code, 403)

    def test_dupliquer_refus_nom_pris_projet_etranger_et_nom_requis(self):
        projet, _, _ = self._source()
        etranger = fabriques.projet(self.voisin)
        api = self._api(self.u1)
        pris = api.post(_url(f'projets/{projet.pk}/dupliquer/'), {'nom': 'Salon 2026'}, format='json')
        self.assertEqual((pris.status_code, pris.json()['nom']), (400, ['Un projet « Salon 2026 » existe déjà.']))
        self.assertEqual(api.post(_url(f'projets/{projet.pk}/dupliquer/'), {}, format='json').status_code, 400)
        self.assertEqual(api.post(_url(f'projets/{etranger.pk}/dupliquer/'), {'nom': 'X'},
                                  format='json').status_code, 404)

    def test_dupliquer_annule_en_un_geste(self):
        projet, _, _ = self._source()
        corps = self._api(self.u1).post(_url(f'projets/{projet.pk}/dupliquer/'),
                                        {'nom': 'Double', 'apercu': False}, format='json').json()
        double = Projet.objects.get(pk=corps['projet']['id'])
        self.assertEqual(annuler_geste(self.u1, corps['geste_id'])['conflits'], [])
        self.assertFalse(Projet.objects.filter(pk=double.pk).exists())
        self.assertEqual(Tache.objects.filter(projet=double).count(), 0)
