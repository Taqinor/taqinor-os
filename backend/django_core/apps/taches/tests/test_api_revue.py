"""TCH65 — la revue de la semaine : `GET revue/projets/` et `PUT revue/projets/{projet_id}/`
(reference/api.md §3.3, §4 ; invariants 17 et 25 ; textes.md §2.7, §4.6).

Base requise (`TestCase`) : joué par la CI. Les jours sont RELATIFS à aujourd'hui ; la semaine d'une revue
est toujours un lundi. Chaque réponse est comparée aux CLÉS de `revue_projets.json` / `revue_decision.json`.
"""
import datetime

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.taches.models.projets import Projet, RevueProjet
from apps.taches.models.taches import Tache
from apps.taches.selectors.projets import lundi_de
from apps.taches.services.gestes import annuler_geste
from apps.taches.tests import fabriques
from apps.taches.views.base import exemple_de

PREFIXE = '/api/django/taches/'
ENTETE_ASSISTANT = {'HTTP_X_TAQINOR_ASSISTANT': '1'}


def _aujourdhui():
    return timezone.localdate()


def _lundi():
    return lundi_de(_aujourdhui())


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

    def _cartes(self, parametre='', compte=None, **options):
        reponse = self._api(compte or self.u1, **options).get(_url(f'revue/projets/{parametre}'))
        self.assertEqual(reponse.status_code, 200)
        return reponse.json()


class RevueProjetsTests(_Base):
    def test_forme_de_l_echantillon(self):
        projet = fabriques.projet(self.u1, priorite=3)
        fabriques.tache(self.u1, projet=projet)
        corps = self._cartes()
        exemple = exemple_de('revue_projets')
        self.assertEqual(set(corps), set(exemple))
        self.assertEqual(set(corps['cartes'][0]), set(exemple['cartes'][0]))
        self.assertEqual(set(corps['cartes'][0]['projet']), set(exemple['cartes'][0]['projet']))
        self.assertEqual(set(corps['cartes'][0]['revue']), set(exemple['cartes'][0]['revue']))
        self.assertEqual(corps['semaine'], _lundi().isoformat())
        self.assertEqual(corps['cartes'][0]['revue'], {'intention': '', 'decision': '', 'focus': False})

    def test_une_carte_par_projet_actif_dans_l_ordre_priorite_puis_rang(self):
        basse = fabriques.projet(self.u1, priorite=1, rang=1024)
        haute_tard = fabriques.projet(self.u1, priorite=3, rang=4096)
        haute_tot = fabriques.projet(self.u1, priorite=3, rang=2048)
        fabriques.projet(self.u1, statut='en_pause')
        fabriques.projet(self.u1, statut='termine', issue='atteint')
        fabriques.projet(self.voisin)
        fabriques.projet(self.ailleurs)
        ids = [c['projet']['id'] for c in self._cartes()['cartes']]
        self.assertEqual(ids, [haute_tot.pk, haute_tard.pk, basse.pk])

    def test_aucun_projet_actif(self):
        corps = self._cartes()
        self.assertEqual(corps['cartes'], [])
        self.assertIsNone(corps['focus_projet_id'])

    def test_faites_de_la_semaine_trois_titres_au_plus_et_leur_nombre(self):
        projet = fabriques.projet(self.u1)
        for rang in range(5):
            self._fait(self.u1, projet, titre=f'Faite {rang}')
        ancienne = self._fait(self.u1, projet, titre='Vieille')
        Tache.objects.filter(pk=ancienne.pk).update(fait_le=timezone.now() - datetime.timedelta(days=30))
        carte = self._cartes()['cartes'][0]
        self.assertEqual(carte['faites_nb'], 5)
        self.assertEqual(len(carte['faites_semaine']), 3)
        self.assertEqual(set(carte['faites_semaine'][0]), {'id', 'titre'})
        self.assertNotIn('Vieille', [t['titre'] for t in carte['faites_semaine']])

    def test_prevues_aujourdhui_ce_qu_une_pause_laisse_dans_la_journee(self):
        """C-5 — par carte, les tâches ouvertes prévues aujourd'hui (préfiltre de la journée) : ni sous-tâche, ni
        bloquée, ni faite, ni demain, ni « Un jour » ; un autre projet compte à part ; en UNE requête pour toutes."""
        jour = _aujourdhui()
        ventes, site, vide = (fabriques.projet(self.u1, priorite=3, rang=r) for r in (1024, 2048, 3072))
        mere = fabriques.tache(self.u1, projet=ventes, jour_prevu=jour, titre='Mère')
        fabriques.tache(self.u1, projet=ventes, jour_prevu=jour, titre='Seconde')
        fabriques.tache(self.u1, projet=ventes, parent=mere, jour_prevu=jour, titre='Sous')
        fabriques.tache(self.u1, projet=ventes, jour_prevu=jour, titre='Bloquée', bloquee_par=mere)
        fabriques.tache(self.u1, projet=ventes, jour_prevu=jour + datetime.timedelta(days=1), titre='Demain')
        self._fait(self.u1, ventes, jour_prevu=jour, titre='Faite')
        fabriques.tache(self.u1, projet=site, jour_prevu=jour, titre='Site')
        fabriques.tache(self.voisin, projet=fabriques.projet(self.voisin), jour_prevu=jour, titre='Voisin')
        cartes = {c['projet']['id']: c['prevues_aujourdhui_nb'] for c in self._cartes()['cartes']}
        self.assertEqual(cartes, {ventes.pk: 2, site.pk: 1, vide.pk: 0})

    def test_une_autre_semaine_n_a_pas_ces_faites(self):
        projet = fabriques.projet(self.u1)
        self._fait(self.u1, projet)
        precedente = (_lundi() - datetime.timedelta(days=7)).isoformat()
        corps = self._cartes(f'?semaine={precedente}')
        self.assertEqual(corps['semaine'], precedente)
        self.assertEqual(corps['cartes'][0]['faites_nb'], 0)

    def test_un_jour_au_milieu_de_la_semaine_est_ramene_au_lundi(self):
        mercredi = _lundi() + datetime.timedelta(days=2)
        self.assertEqual(self._cartes(f'?semaine={mercredi.isoformat()}')['semaine'], _lundi().isoformat())

    def test_semaine_illisible_400(self):
        reponse = self._api(self.u1).get(_url('revue/projets/?semaine=demain'))
        self.assertEqual(reponse.status_code, 400)
        self.assertEqual(reponse.json()['semaine'], ['Date attendue (AAAA-MM-JJ).'])

    def test_bloquees_disent_ce_qu_elles_attendent(self):
        projet = fabriques.projet(self.u1)
        livraison = fabriques.tache(self.u1, projet=projet, titre='Livraison')
        pose = fabriques.tache(self.u1, projet=projet, titre='Pose', bloquee_par=livraison)
        libre = fabriques.tache(self.u1, projet=projet, titre='Libre')
        carte = self._cartes()['cartes'][0]
        self.assertEqual(carte['bloquees'], [{'id': pose.pk, 'titre': 'Pose',
                                              'attend': {'id': livraison.pk, 'titre': 'Livraison'}}])
        self.assertNotIn(libre.pk, [b['id'] for b in carte['bloquees']])

    def test_un_prerequis_fait_ne_bloque_plus(self):
        projet = fabriques.projet(self.u1)
        fait = self._fait(self.u1, projet, titre='Livraison')
        fabriques.tache(self.u1, projet=projet, titre='Pose', bloquee_par=fait)
        self.assertEqual(self._cartes()['cartes'][0]['bloquees'], [])

    def test_prochaine_action_est_la_premiere_a_faire_non_bloquee(self):
        projet = fabriques.projet(self.u1)
        livraison = fabriques.tache(self.u1, projet=projet, titre='Livraison')
        fabriques.tache(self.u1, projet=projet, titre='Pose', bloquee_par=livraison)
        carte = self._cartes()['cartes'][0]
        self.assertEqual(carte['prochaine_action']['id'], livraison.pk)
        self.assertEqual(set(carte['prochaine_action']), set(exemple_de('item')))

    def test_sans_tache_la_prochaine_action_est_nulle(self):
        fabriques.projet(self.u1)
        self.assertIsNone(self._cartes()['cartes'][0]['prochaine_action'])

    def test_projet_confidentiel_a_l_assistant(self):
        projet = fabriques.projet(self.u1, nom='Secret', confidentiel=True)
        self._fait(self.u1, projet, titre='Contrat très confidentiel')
        carte = self._cartes(assistant=True)['cartes'][0]
        self.assertNotIn('Secret', repr(carte['projet']['nom']))
        self.assertNotIn('très confidentiel', repr(carte['faites_semaine']))

    def test_sans_le_droit_403(self):
        sans_droit = fabriques.compte(self.a, voir=False, nom='sans')
        self.assertEqual(self._api(sans_droit).get(_url('revue/projets/')).status_code, 403)


class BilanDeSemaineTests(_Base):
    def _semaine(self, lundi, comptes, statut='evalue'):
        for rang, compte in enumerate(comptes):
            fabriques.plan(self.u1, lundi + datetime.timedelta(days=rang), statut_jour=statut, compte_rythme=compte)

    def test_bilan_de_la_semaine_et_de_la_precedente(self):
        fabriques.projet(self.u1)
        lundi = _lundi() - datetime.timedelta(days=7)
        self._semaine(lundi, [5, 6, 5, 4, 6])
        self._semaine(lundi - datetime.timedelta(days=7), [2, 2, 2, 1, 1])
        corps = self._cartes(f'?semaine={lundi.isoformat()}')
        self.assertFalse(corps['semaine_courte'])
        self.assertEqual(set(corps['bilan_semaine']), {'texte', 'donnees'})
        self.assertEqual(corps['bilan_semaine']['donnees'], {'faites': 26, 'jours': 5, 'prec': 8})
        self.assertIn('26 faites (8 la précédente)', corps['bilan_semaine']['texte'])

    def test_sans_semaine_precedente_pas_de_parenthese(self):
        lundi = _lundi() - datetime.timedelta(days=7)
        self._semaine(lundi, [3, 3, 3])
        bilan = self._cartes(f'?semaine={lundi.isoformat()}')['bilan_semaine']
        self.assertEqual(bilan['donnees'], {'faites': 9, 'jours': 3, 'prec': None})
        self.assertNotIn('précédente', bilan['texte'])

    def test_semaine_courte_sans_chiffres(self):
        lundi = _lundi() - datetime.timedelta(days=7)
        self._semaine(lundi, [0, 0, 0], statut='sans_donnees')
        self._semaine(lundi + datetime.timedelta(days=3), [4, 4], statut='evalue')
        corps = self._cartes(f'?semaine={lundi.isoformat()}')
        self.assertTrue(corps['semaine_courte'])
        self.assertIsNone(corps['bilan_semaine'])

    def test_aucun_jour_evalue_pas_de_bilan(self):
        corps = self._cartes()
        self.assertFalse(corps['semaine_courte'])
        self.assertIsNone(corps['bilan_semaine'])

    def test_le_bilan_ne_lit_que_les_jours_du_compte(self):
        lundi = _lundi() - datetime.timedelta(days=7)
        fabriques.plan(self.voisin, lundi, statut_jour='evalue', compte_rythme=9)
        self.assertIsNone(self._cartes(f'?semaine={lundi.isoformat()}')['bilan_semaine'])


class ObjectifAtteintDeLaSemaineTests(_Base):
    """Revue F2 tour 2 #4 : « Objectif atteint X jours sur N » compte les jours où le compte a atteint
    l'objectif du jour (le « objectif atteint » du bilan du soir), sur les jours jugés ; « Jours non
    travaillés » ne compte que des jours qu'il travaille d'habitude. Semaine du lun. 9/11/2026."""

    LUNDI = datetime.date(2026, 11, 9)

    def jour(self, n):
        return self.LUNDI + datetime.timedelta(days=n)

    def instant(self, jour, heure=11):
        return timezone.make_aware(datetime.datetime.combine(jour, datetime.time(heure)))

    def texte(self):
        from apps.taches.selectors.projets import bilan_de_semaine
        return bilan_de_semaine(self.u1, self.LUNDI, 'pousser')[1]['texte']

    def test_objectif_atteint_meme_sans_l_essentiel(self):
        fabriques.plan(self.u1, self.jour(0), statut_jour='evalue', compte_rythme=3, objectif_du_jour=3,
                       essentiels_choisis=1, essentiels_faits=0)
        fabriques.plan(self.u1, self.jour(1), statut_jour='evalue', compte_rythme=2, objectif_du_jour=5)
        self.assertIn('Objectif atteint 1 jour sur 2', self.texte())

    def test_la_nuit_pose_l_objectif_de_chaque_jour_juge(self):
        from apps.taches.models.journee import PlanJour
        from apps.taches.services.journee import clore_jour_precedent
        fabriques.reglages(self.u1)
        projet = fabriques.projet(self.u1)
        for n in range(4):
            for _ in range(6):
                fabriques.tache(self.u1, projet=projet, statut='fait', fait_le=self.instant(self.jour(n)))
        for n in (0, 1):  # « Garder ces N » touché ces deux jours-là seulement
            fabriques.plan(self.u1, self.jour(n), planifie_le=self.instant(self.jour(n), 8), objectif_du_jour=5)
        for n in range(1, 5):
            clore_jour_precedent(self.u1.company_id, self.jour(n))
        self.assertEqual(list(PlanJour.objects.filter(proprietaire=self.u1).order_by('jour')
                              .values_list('statut_jour', 'compte_rythme', 'objectif_du_jour')),
                         [('evalue', 6, 5)] * 4)
        self.assertIn('24 faites. Objectif atteint 4 jours sur 4.', self.texte())

    def test_jours_non_travailles_seulement_parmi_ses_jours_travailles(self):
        from apps.taches.services.journee import clore_jour_precedent
        from apps.taches.services.rythme import poser_preference
        fabriques.reglages(self.u1)
        poser_preference(self.u1, 'conges', [{'du': self.jour(2).isoformat(), 'au': self.jour(2).isoformat()}],
                         'ecran')
        projet = fabriques.projet(self.u1)
        for n in (0, 1, 3, 4):
            for _ in range(5):
                fabriques.tache(self.u1, projet=projet, statut='fait', fait_le=self.instant(self.jour(n)))
        for n in range(1, 6):  # nuits du mar. au sam. : la revue lue le vendredi soir ou le samedi
            clore_jour_precedent(self.u1.company_id, self.jour(n))
        vendredi_soir = self.texte()
        for n in (6, 7):  # nuits de dim. et lun. : le samedi et le dimanche, non travaillés, sont clos
            clore_jour_precedent(self.u1.company_id, self.jour(n))
        self.assertEqual(self.texte(), vendredi_soir)
        self.assertTrue(vendredi_soir.endswith('Jour non travaillé : 1.'), vendredi_soir)

    def test_cette_semaine_seulement_pour_la_semaine_en_cours(self):
        """V2-C (R2-034) — « Cette semaine : … » ne se dit que de la semaine EN COURS ; une revue d'une semaine passée
        garde ses dates (« Du lun. 9 au ven. 13 : … »), sinon elle se présenterait comme celle de maintenant."""
        from apps.taches.selectors.projets import bilan_de_semaine
        fabriques.plan(self.u1, self.jour(0), statut_jour='evalue', compte_rythme=3, objectif_du_jour=3)
        fabriques.plan(self.u1, self.jour(1), statut_jour='evalue', compte_rythme=2, objectif_du_jour=5)
        en_cours = bilan_de_semaine(self.u1, self.LUNDI, 'pousser', aujourdhui=self.jour(4))[1]['texte']
        self.assertTrue(en_cours.startswith('Cette semaine : 5 faites.'), en_cours)
        passee = bilan_de_semaine(self.u1, self.LUNDI, 'pousser', aujourdhui=self.jour(9))[1]['texte']
        self.assertTrue(passee.startswith('Du lun. 9 au ven. 13 : 5 faites.'), passee)


class DecisionDeRevueTests(_Base):
    def _corps(self, **plus):
        return {'semaine': _aujourdhui().isoformat(), 'intention': 'Signer Settat', 'decision': 'garder',
                'focus': False, **plus}

    def _put(self, projet, compte=None, **plus):
        return self._api(compte or self.u1).put(_url(f'revue/projets/{projet.pk}/'), self._corps(**plus),
                                                format='json')

    def test_garder_enregistre_la_revue_et_rend_l_echantillon(self):
        projet = fabriques.projet(self.u1)
        action = fabriques.tache(self.u1, projet=projet)
        reponse = self._put(projet, prochaine_action_id=action.pk, focus=True)
        self.assertEqual(reponse.status_code, 200)
        corps = reponse.json()
        exemple = exemple_de('revue_decision')
        self.assertEqual(set(corps), set(exemple))
        self.assertEqual(set(corps['revue']), set(exemple['revue']))
        self.assertEqual(set(corps['projet']), set(exemple['projet']))
        self.assertEqual(corps['revue'], {'semaine': _lundi().isoformat(), 'intention': 'Signer Settat',
                                          'decision': 'garder', 'focus': True, 'prochaine_action_id': action.pk})
        revue = RevueProjet.objects.get(projet=projet)
        self.assertEqual((revue.semaine, revue.proprietaire_id, revue.company_id), (_lundi(), self.u1.pk, self.a.pk))
        self.assertEqual(revue.prochaine_action_id, action.pk)
        self.assertTrue(revue.focus)
        self.assertEqual(Projet.objects.get(pk=projet.pk).statut, 'actif')
        self.assertIsNotNone(corps['geste_id'])

    def test_la_carte_relue_porte_la_decision_et_le_projet_de_la_semaine(self):
        projet = fabriques.projet(self.u1)
        choisie = fabriques.tache(self.u1, projet=projet, titre='Choisie')
        fabriques.tache(self.u1, projet=projet, titre='Première')
        self._put(projet, prochaine_action_id=choisie.pk, focus=True)
        corps = self._cartes()
        self.assertEqual(corps['focus_projet_id'], projet.pk)
        carte = corps['cartes'][0]
        self.assertEqual(carte['revue'], {'intention': 'Signer Settat', 'decision': 'garder', 'focus': True})
        self.assertEqual(carte['prochaine_action']['id'], choisie.pk)
        self.assertTrue(carte['projet']['focus_semaine'])

    def test_une_nouvelle_decision_met_la_meme_revue_a_jour(self):
        projet = fabriques.projet(self.u1)
        self._put(projet, intention='A')
        self._put(projet, intention='B', decision='passe')
        revues = RevueProjet.objects.filter(projet=projet)
        self.assertEqual(revues.count(), 1)
        self.assertEqual((revues[0].intention, revues[0].decision), ('B', 'passe'))

    def test_un_seul_projet_de_la_semaine(self):
        premier, second = fabriques.projet(self.u1, nom='Premier'), fabriques.projet(self.u1, nom='Second')
        self.assertEqual(self._put(premier, focus=True).status_code, 200)
        refus = self._put(second, focus=True)
        self.assertEqual(refus.status_code, 400)
        self.assertEqual(refus.json()['focus'], ['Déjà « Premier » cette semaine.'])
        self.assertFalse(RevueProjet.objects.filter(projet=second).exists())

    def test_le_projet_de_la_semaine_peut_garder_sa_case_et_changer_de_semaine(self):
        premier, second = fabriques.projet(self.u1), fabriques.projet(self.u1)
        self.assertEqual(self._put(premier, focus=True).status_code, 200)
        self.assertEqual(self._put(premier, focus=True, intention='Encore').status_code, 200)
        prochaine = (_lundi() + datetime.timedelta(days=7)).isoformat()
        self.assertEqual(self._put(second, focus=True, semaine=prochaine).status_code, 200)

    def test_le_projet_de_la_semaine_d_un_autre_compte_ne_gene_pas(self):
        fabriques.projet(self.voisin)
        mien = fabriques.projet(self.u1)
        voisin = Projet.objects.get(proprietaire=self.voisin)
        self.assertEqual(self._put(voisin, compte=self.voisin, focus=True).status_code, 200)
        self.assertEqual(self._put(mien, focus=True).status_code, 200)

    def test_pause_met_le_projet_en_pause(self):
        projet = fabriques.projet(self.u1)
        reponse = self._put(projet, decision='pause')
        self.assertEqual(reponse.json()['projet']['statut'], 'en_pause')
        self.assertEqual(Projet.objects.get(pk=projet.pk).statut, 'en_pause')
        self.assertNotIn(projet.pk, [c['projet']['id'] for c in self._cartes()['cartes']])

    def test_terminer_exige_l_issue(self):
        projet = fabriques.projet(self.u1)
        reponse = self._put(projet, decision='terminer')
        self.assertEqual(reponse.status_code, 400)
        self.assertEqual(reponse.json()['issue'], ['Atteint ou abandonné ?'])
        self.assertEqual(Projet.objects.get(pk=projet.pk).statut, 'actif')
        self.assertFalse(RevueProjet.objects.filter(projet=projet).exists())

    def test_terminer_passe_par_le_service_de_cloture(self):
        projet = fabriques.projet(self.u1)
        ouverte = fabriques.tache(self.u1, projet=projet)
        reponse = self._put(projet, decision='terminer', issue='atteint')
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual((reponse.json()['projet']['statut'], reponse.json()['projet']['issue']),
                         ('termine', 'atteint'))
        projet.refresh_from_db()
        ouverte.refresh_from_db()
        self.assertIsNotNone(projet.termine_le)
        self.assertIsNone(ouverte.projet_id)
        self.assertIsNotNone(reponse.json()['geste_id'])
        bilan = annuler_geste(self.u1, reponse.json()['geste_id'])
        self.assertEqual(bilan['conflits'], [])
        self.assertEqual(Projet.objects.get(pk=projet.pk).statut, 'actif')

    def test_decision_inconnue_et_semaine_requise(self):
        projet = fabriques.projet(self.u1)
        inconnue = self._put(projet, decision='demain')
        self.assertEqual(inconnue.status_code, 400)
        self.assertEqual(inconnue.json()['decision'], ['Valeur inconnue.'])
        api = self._api(self.u1)
        sans = api.put(_url(f'revue/projets/{projet.pk}/'), {'decision': 'garder'}, format='json')
        self.assertEqual(sans.json()['semaine'], ['Requis.'])

    def test_prochaine_action_d_un_autre_projet_ou_compte_404(self):
        projet, autre = fabriques.projet(self.u1), fabriques.projet(self.u1)
        ailleurs = fabriques.tache(self.u1, projet=autre)
        etrangere = fabriques.tache(self.voisin, projet=fabriques.projet(self.voisin))
        self.assertEqual(self._put(projet, prochaine_action_id=ailleurs.pk).status_code, 404)
        self.assertEqual(self._put(projet, prochaine_action_id=etrangere.pk).status_code, 404)
        self.assertFalse(RevueProjet.objects.filter(projet=projet).exists())

    def test_projet_d_un_autre_compte_404(self):
        for autre in (self.voisin, self.ailleurs):
            projet = fabriques.projet(autre)
            self.assertEqual(self._put(projet).status_code, 404)

    def test_la_decision_compte_les_faites_de_la_semaine(self):
        projet = fabriques.projet(self.u1)
        self._fait(self.u1, projet)
        self._fait(self.u1, projet)
        self._put(projet)
        self.assertEqual(RevueProjet.objects.get(projet=projet).faites_semaine, 2)

    def test_sans_le_droit_403(self):
        projet = fabriques.projet(self.u1)
        sans_droit = fabriques.compte(self.a, voir=False, nom='sans')
        self.assertEqual(self._put(projet, compte=sans_droit).status_code, 403)
