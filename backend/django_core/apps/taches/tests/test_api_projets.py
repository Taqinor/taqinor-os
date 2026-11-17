"""TCH60-TCH63 — les routes `projets/` et `sections/` : liste, création, fiche, PATCH, suppression, ordre,
clôture, vue, étapes, planification, décalage (reference/api.md §3.3, §4 ; invariants 17, 25, 27).

Base requise (`TestCase`) : joué par la CI. Les jours des tests sont RELATIFS à aujourd'hui (`_j`) : les routes
lisent l'horloge à leur frontière (`timezone.localdate()`), comme `planifier`. Chaque réponse est comparée aux
CLÉS de son échantillon de `contract_samples/` ; chaque état est relu en base après l'écriture.
"""
import datetime

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.taches.models.projets import Projet
from apps.taches.models.taches import Tache
from apps.taches.services.gestes import annuler_geste
from apps.taches.tests import fabriques
from apps.taches.views.base import exemple_de

PREFIXE = '/api/django/taches/'
ENTETE_ASSISTANT = {'HTTP_X_TAQINOR_ASSISTANT': '1'}


def _j(delta):
    return timezone.localdate() + datetime.timedelta(days=delta)


def _url(chemin):
    return PREFIXE + chemin


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
