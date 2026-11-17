"""TCH49, TCH50, TCH51 — tâches : liste, création, fiche, PATCH à verrou, suppression, actions d'état, rappels,
récurrence (api.md §3.2, §4 ; donnees.md invariants 1, 4, 5, 6, 7, 9, 15, 16, 19, 27, 32).

Base requise (`TestCase`) : joué par la CI. Chaque test relit les lignes STOCKÉES ; les réponses sont
comparées aux `exemple` de `contract_samples/` (clés ET ordre).
"""
import datetime

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from rest_framework.test import APIClient

from apps.taches.choix import StatutRappel, StatutTache
from apps.taches.models.gestes import GesteAnnulable
from apps.taches.models.taches import ElementChecklist, Etiquette, EtiquetteTache, Rappel, RegleRecurrence, Tache
from apps.taches.moteur.recurrence import prochaine_occurrence
from apps.taches.services.gestes import annuler_geste
from apps.taches.services.taches import VERSION_OCCURRENCE_NEUVE
from apps.taches.tests import fabriques
from apps.taches.tests.test_api_saisie import ASSISTANT, URL, BaseApi, exemple

TITRE_VIDE = 'Le titre est vide une fois la date et le projet retirés.'


def _j(delta=0):
    return timezone.localdate() + datetime.timedelta(days=delta)


def _relue(tache):
    return Tache.all_objects.get(pk=tache.pk)


class ListeTests(BaseApi):
    def _liste(self, requete='', compte=None, **entetes):
        return self._get(f'taches/?{requete}', compte, **entetes)

    def _ids(self, reponse):
        return {ligne['id'] for ligne in reponse.json()['results']}

    def test_a_trier_est_la_boite_de_reception(self):
        boite = fabriques.tache(self.u1)
        fabriques.tache(self.u1, projet=fabriques.projet(self.u1))        # rangée dans un projet
        fabriques.tache(self.u1, jour_prevu=_j(1))                         # triée par un jour
        fabriques.tache(self.u1, quelque_jour=True, triee_le=timezone.now())
        reponse = self._liste('vue=boite')
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(self._ids(reponse), {boite.pk})
        self.assertEqual(list(reponse.json()), ['count', 'next', 'previous', 'results'])
        self.assertEqual(list(reponse.json()['results'][0]), list(exemple('item')))

    def test_en_reserve(self):
        reserve = fabriques.tache(self.u1, quelque_jour=True, triee_le=timezone.now())
        fabriques.tache(self.u1, jour_prevu=_j(1))
        self.assertEqual(self._ids(self._liste('vue=quelque_jour')), {reserve.pk})

    def test_une_liste_ne_montre_que_ses_taches(self):
        propre = fabriques.tache(self.u1)
        fabriques.tache(self.u2)
        fabriques.tache(self.ext)
        self.assertEqual(self._ids(self._liste()), {propre.pk})

    def test_les_sous_taches_ne_sont_pas_des_lignes_de_liste(self):
        parent = fabriques.tache(self.u1)
        fabriques.tache(self.u1, parent=parent)
        self.assertEqual(self._ids(self._liste()), {parent.pk})

    def test_les_faites_sont_masquees_sauf_inclure_faites(self):
        ouverte = fabriques.tache(self.u1)
        faite = fabriques.tache(self.u1, statut=StatutTache.FAIT, fait_le=timezone.now())
        self.assertEqual(self._ids(self._liste()), {ouverte.pk})
        self.assertEqual(self._ids(self._liste('inclure_faites=1')), {ouverte.pk, faite.pk})
        self.assertEqual(self._ids(self._liste('inclure_faites=1&ouvertes=1')), {ouverte.pk})
        self.assertEqual(self._ids(self._liste('statut=fait')), {faite.pk})

    def test_filtres_projet_priorite_et_mots(self):
        projet = fabriques.projet(self.u1)
        voulue = fabriques.tache(self.u1, projet=projet, titre='Devis Settat', priorite=3)
        fabriques.tache(self.u1, projet=projet, titre='Autre', priorite=1)
        fabriques.tache(self.u1, titre='Devis ailleurs', priorite=3)
        self.assertEqual(self._ids(self._liste(f'projet={projet.pk}&priorite_min=3&q=devis')), {voulue.pk})

    def test_filtre_etiquette(self):
        etiquette = Etiquette.objects.create(company=self.a, proprietaire=self.u1, nom='magasin')
        etiquetee = fabriques.tache(self.u1)
        fabriques.tache(self.u1)
        EtiquetteTache.objects.create(company=self.a, tache=etiquetee, etiquette=etiquette)
        self.assertEqual(self._ids(self._liste(f'etiquette={etiquette.pk}')), {etiquetee.pk})

    def test_taches_liees_a_une_fiche_erp(self):
        cible = ContentType.objects.get_by_natural_key('crm', 'lead')
        liee = fabriques.tache(self.u1, content_type=cible, object_id=1637)
        fabriques.tache(self.u1, content_type=cible, object_id=1638)
        fabriques.tache(self.u1, parent=liee, content_type=cible, object_id=1637)  # sous-tâche : comptée aussi
        reponse = self._liste('cible=crm.lead&cible_id=1637&ouvertes=1')
        self.assertEqual(reponse.json()['count'], 2)
        self.assertIn(liee.pk, self._ids(reponse))

    def test_parametre_inconnu_ou_illisible_400_nomme(self):
        for requete, champ in (('cible=stock.produit', 'cible'), ('priorite_min=abc', 'priorite_min'),
                               ('vue=ailleurs', 'vue'), ('tri=hasard', 'tri'), ('projet=x', 'projet')):
            with self.subTest(requete=requete):
                reponse = self._liste(requete)
                self.assertEqual(reponse.status_code, 400)
                self.assertEqual(list(reponse.json()), [champ])

    def test_pagination(self):
        for _ in range(3):
            fabriques.tache(self.u1)
        reponse = self._liste('page_size=2').json()
        self.assertEqual((reponse['count'], len(reponse['results'])), (3, 2))
        self.assertIsNotNone(reponse['next'])

    def test_l_assistant_ne_voit_aucune_tache_confidentielle(self):
        fabriques.tache(self.u1, titre='Ordinaire')
        fabriques.tache(self.u1, titre='Secret', confidentiel=True)
        titres = [ligne['titre'] for ligne in self._liste('', **ASSISTANT).json()['results']]
        self.assertEqual(titres, ['Ordinaire'])


class CreationTachesTests(BaseApi):
    def test_201_a_les_cles_de_l_echantillon(self):
        projet = fabriques.projet(self.u1, nom='Ventes')
        reponse = self._post('taches/', {'titre': 'Devis Settat', 'projet_id': projet.pk,
                                         'jour_prevu': _j(1).isoformat(), 'priorite': 2,
                                         'proprietaire_attendu': self.u1.pk})
        self.assertEqual(reponse.status_code, 201)
        corps = reponse.json()
        self.assertEqual(list(corps), list(exemple('tache_ecrite')))
        self.assertEqual(list(corps['tache']), list(exemple('tache_ecrite')['tache']))
        tache = Tache.objects.get(pk=corps['tache']['id'])
        self.assertEqual((tache.proprietaire, tache.company, tache.source, tache.projet),
                         (self.u1, self.a, 'manuel', projet))
        self.assertIsNotNone(corps['geste_id'])

    def test_un_titre_vide_est_refuse_sous_le_champ(self):
        reponse = self._post('taches/', {'titre': ''})
        self.assertEqual(reponse.status_code, 400)
        self.assertEqual(reponse.json(), {'titre': ['Le titre est vide une fois la date et le projet retirés.']})
        self.assertEqual(Tache.objects.count(), 0)

    def test_un_rejeu_du_meme_client_id_rend_la_tache_deja_creee(self):
        corps = {'titre': 'Appeler Karim', 'client_id': 'abc'}
        premier = self._post('taches/', corps)
        second = self._post('taches/', corps)
        self.assertEqual((premier.status_code, second.status_code), (201, 200))
        self.assertEqual(second.json()['tache']['id'], premier.json()['tache']['id'])
        self.assertEqual(Tache.objects.count(), 1)

    def test_idempotency_key_est_suffixee_par_compte(self):
        corps = {'titre': 'Appeler Karim'}
        premier = self._post('taches/', corps, HTTP_IDEMPOTENCY_KEY='k-taches')
        rejeu = self._post('taches/', corps, HTTP_IDEMPOTENCY_KEY='k-taches')
        collegue = self._post('taches/', corps, compte=self.u2, HTTP_IDEMPOTENCY_KEY='k-taches')
        self.assertEqual(rejeu.json(), premier.json())
        self.assertNotEqual(collegue.json()['tache']['id'], premier.json()['tache']['id'])
        self.assertEqual(Tache.objects.get(pk=collegue.json()['tache']['id']).proprietaire, self.u2)

    def test_une_sous_tache_prend_le_projet_de_son_parent(self):
        projet = fabriques.projet(self.u1)
        parent = fabriques.tache(self.u1, projet=projet)
        reponse = self._post('taches/', {'titre': 'Relire', 'parent_id': parent.pk})
        self.assertEqual(reponse.status_code, 201)
        enfant = reponse.json()['tache']
        self.assertEqual((enfant['parent_id'], enfant['projet']['id']), (parent.pk, projet.pk))

    def test_le_parent_d_un_autre_compte_repond_comme_inconnu(self):
        parent = fabriques.tache(self.u2)
        self.assertEqual(self._post('taches/', {'titre': 'x', 'parent_id': parent.pk}).status_code, 404)
        self.assertEqual(Tache.objects.filter(titre='x').count(), 0)

    def test_un_rappel_pose_a_la_creation_est_rendu(self):
        corps = {'titre': 'Appeler', 'rappel': {'jour': _j(1).isoformat(), 'heure': '09:00'}}
        reponse = self._post('taches/', corps).json()
        self.assertEqual(list(reponse['rappel']), ['id', 'jour', 'heure', 'ancre', 'decalage_jours', 'statut',
                                                   'hors_fenetre'])
        self.assertEqual((reponse['rappel']['jour'], reponse['rappel']['heure']), (_j(1).isoformat(), '09:00'))
        self.assertTrue(reponse['question_titres'])

    def test_l_assistant_cree_sous_sa_source(self):
        reponse = self._post('taches/', {'titre': 'Appeler'}, **ASSISTANT)
        self.assertEqual(Tache.objects.get(pk=reponse.json()['tache']['id']).source, 'assistant')

    def test_proprietaire_attendu_d_un_autre_compte_409(self):
        reponse = self._post('taches/', {'titre': 'x', 'proprietaire_attendu': self.u2.pk})
        self.assertEqual((reponse.status_code, reponse.json()['code']), (409, 'autre_compte'))
        self.assertEqual(Tache.objects.count(), 0)


class FicheTests(BaseApi):
    def test_la_fiche_a_les_cles_de_l_echantillon(self):
        tache = fabriques.tache(self.u1)
        fabriques.tache(self.u1, parent=tache)
        reponse = self._get(f'taches/{tache.pk}/')
        self.assertEqual(reponse.status_code, 200)
        corps = reponse.json()
        self.assertEqual(list(corps), list(exemple('tache')))
        self.assertEqual(corps['sous_taches'], {'faites': 0, 'total': 1})

    def test_la_tache_d_un_collegue_ou_d_une_autre_societe_repond_comme_inconnue(self):
        for autre in (fabriques.tache(self.u2), fabriques.tache(self.ext)):
            with self.subTest(autre=autre.pk):
                self.assertEqual(self._get(f'taches/{autre.pk}/').status_code, 404)

    def test_la_fiche_revérifie_le_lien_sans_bouger_lock_version(self):
        cible = ContentType.objects.get_by_natural_key('crm', 'lead')
        tache = fabriques.tache(self.u1, content_type=cible, object_id=999_999, lien_etat='ok',
                                lien_libelle='Ancien nom')
        version = _relue(tache).lock_version
        corps = self._get(f'taches/{tache.pk}/').json()
        self.assertEqual((corps['lien']['etat'], corps['lien']['libelle'], corps['lien']['url']),
                         ('introuvable', '', None))
        relue = _relue(tache)
        self.assertEqual((relue.lien_etat, relue.lien_libelle, relue.lock_version), ('introuvable', '', version))

    def test_l_assistant_ne_recoit_ni_notes_ni_titre_confidentiel(self):
        tache = fabriques.tache(self.u1, titre='Secret', notes='Mot de passe', confidentiel=True)
        corps = self._get(f'taches/{tache.pk}/', **ASSISTANT).json()
        self.assertEqual((corps['notes'], corps['titre']), ('', 'Tâche confidentielle'))


class ModifierTests(BaseApi):
    def _patch(self, tache, corps, compte=None, **entetes):
        envoi = {'lock_version': _relue(tache).lock_version, **corps}
        return self._api(compte).patch(f'{URL}taches/{tache.pk}/', envoi, format='json', **entetes)

    def test_un_patch_ecrit_et_rend_la_tache_ecrite(self):
        tache = fabriques.tache(self.u1, titre='Devis Settat')
        reponse = self._patch(tache, {'titre': 'Devis Settat — relance', 'priorite': 3, 'echeance': _j(5).isoformat()})
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(list(reponse.json()), list(exemple('tache_ecrite')))
        relue = _relue(tache)
        self.assertEqual((relue.titre, relue.priorite, relue.echeance, relue.lock_version),
                         ('Devis Settat — relance', 3, _j(5), tache.lock_version + 1))
        self.assertIsNotNone(reponse.json()['geste_id'])

    def test_annuler_le_patch_restaure_les_champs(self):
        tache = fabriques.tache(self.u1, titre='Avant', priorite=1)
        geste = self._patch(tache, {'titre': 'Après', 'priorite': 3}).json()['geste_id']
        bilan = annuler_geste(self.u1, geste)
        self.assertEqual(bilan['restaurees'], [{'objet': 'tache', 'id': tache.pk}])
        relue = _relue(tache)
        self.assertEqual((relue.titre, relue.priorite), ('Avant', 1))

    def test_lock_version_est_requis(self):
        tache = fabriques.tache(self.u1)
        reponse = self._api().patch(f'{URL}taches/{tache.pk}/', {'titre': 'x'}, format='json')
        self.assertEqual((reponse.status_code, reponse.json()), (400, {'lock_version': ['Requis.']}))

    def test_une_version_perimee_409_avec_la_tache_complete_et_rien_d_ecrit(self):
        tache = fabriques.tache(self.u1, titre='Avant')
        perimee = _relue(tache).lock_version
        self._patch(tache, {'titre': 'Premier'})
        reponse = self._api().patch(f'{URL}taches/{tache.pk}/', {'titre': 'Second', 'lock_version': perimee},
                                    format='json')
        self.assertEqual(reponse.status_code, 409)
        corps = reponse.json()
        self.assertEqual((corps['code'], corps['lock_version']), ('conflit_version', perimee + 1))
        self.assertEqual(list(corps['actuel']), list(exemple('tache')))
        self.assertEqual((corps['actuel']['titre'], _relue(tache).titre), ('Premier', 'Premier'))

    def test_le_jour_ne_passe_que_par_planifier(self):
        tache = fabriques.tache(self.u1)
        for champ, valeur in (('jour_prevu', _j(1).isoformat()), ('heure_debut', '10:00'), ('moment', 'matin'),
                              ('quelque_jour', True)):
            with self.subTest(champ=champ):
                reponse = self._patch(tache, {champ: valeur})
                self.assertEqual((reponse.status_code, reponse.json()), (400, {champ: ['Passe par « Quand ».']}))
        self.assertIsNone(_relue(tache).jour_prevu)

    def test_un_champ_inconnu_ou_interdit_est_refuse(self):
        tache = fabriques.tache(self.u1)
        for champ in ('statut', 'proprietaire', 'company', 'reports', 'client_id'):
            with self.subTest(champ=champ):
                reponse = self._patch(tache, {champ: 1})
                self.assertEqual((reponse.status_code, reponse.json()), (400, {champ: ['Non modifiable ici.']}))

    def test_la_tache_d_un_collegue_repond_comme_inconnue(self):
        autre = fabriques.tache(self.u2, titre='Avant')
        reponse = self._patch(autre, {'titre': 'Piraté'})
        self.assertEqual(reponse.status_code, 404)
        self.assertEqual(_relue(autre).titre, 'Avant')

    def test_valeurs_refusees_sous_leur_champ(self):
        tache = fabriques.tache(self.u1)
        for corps, attendu in (({'estimation_minutes': 3}, {'estimation_minutes': ['Entre 5 et 960 minutes.']}),
                               ({'titre': ' '}, {'titre': [TITRE_VIDE]}),
                               ({'titre': 'x' * 281}, {'titre': ['280 caractères au plus.']}),
                               ({'priorite': 9}, {'priorite': ['Valeur inconnue.']}),
                               ({'echeance_heure': '10:00'}, {'echeance_heure': ['Une heure demande une échéance.']})):
            with self.subTest(corps=corps):
                reponse = self._patch(tache, corps)
                self.assertEqual((reponse.status_code, reponse.json()), (400, attendu))

    def test_une_echeance_et_son_heure(self):
        tache = fabriques.tache(self.u1)
        reponse = self._patch(tache, {'echeance': _j(2).isoformat(), 'echeance_heure': '18:30'})
        self.assertEqual(reponse.status_code, 200)
        relue = _relue(tache)
        self.assertEqual((relue.echeance, relue.echeance_heure), (_j(2), datetime.time(18, 30)))
        self._patch(tache, {'echeance': None})
        relue = _relue(tache)
        self.assertEqual((relue.echeance, relue.echeance_heure), (None, None))

    def test_les_rappels_ancres_suivent_l_echeance(self):
        tache = fabriques.tache(self.u1, echeance=_j(3), jour_prevu=_j(1))
        rappel = Rappel.objects.create(company=self.a, proprietaire=self.u1, tache=tache, ancre='echeance',
                                       decalage_jours=-1, jour=_j(2), heure=datetime.time(9, 0))
        self._patch(tache, {'echeance': _j(6).isoformat()})
        rappel.refresh_from_db()
        self.assertEqual((rappel.jour, rappel.statut), (_j(5), StatutRappel.EN_ATTENTE))
        self._patch(tache, {'echeance': None})
        rappel.refresh_from_db()
        self.assertEqual(rappel.statut, StatutRappel.ANNULE)

    # --- Invariant 6 : prérequis ---------------------------------------------------------------

    def test_un_prerequis_garde_le_statut_a_faire(self):
        visite, devis = fabriques.tache(self.u1, titre='Visite'), fabriques.tache(self.u1, titre='Devis')
        reponse = self._patch(devis, {'bloquee_par_id': visite.pk})
        self.assertEqual(reponse.status_code, 200)
        corps = reponse.json()['tache']
        self.assertEqual((corps['statut'], corps['bloquee_par']), ('a_faire', {'id': visite.pk, 'titre': 'Visite'}))

    def test_une_boucle_est_refusee_avec_son_message(self):
        visite = fabriques.tache(self.u1, titre='Visite')
        devis = fabriques.tache(self.u1, titre='Devis', bloquee_par=visite)
        reponse = self._patch(visite, {'bloquee_par_id': devis.pk})
        self.assertEqual(reponse.status_code, 400)
        self.assertEqual(reponse.json(), {'bloquee_par_id': ['Boucle : « Devis » attend déjà « Visite ».']})

    def test_jamais_soi_meme(self):
        tache = fabriques.tache(self.u1)
        self.assertEqual(self._patch(tache, {'bloquee_par_id': tache.pk}).status_code, 400)

    def test_une_chaine_de_plus_de_50_maillons_est_refusee(self):
        precedente = None
        for rang in range(52):
            precedente = fabriques.tache(self.u1, titre=f'maillon {rang}', bloquee_par=precedente)
        neuve = fabriques.tache(self.u1, titre='neuve')
        reponse = self._patch(neuve, {'bloquee_par_id': precedente.pk})
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('bloquee_par_id', reponse.json())

    def test_le_prerequis_d_un_collegue_repond_comme_inconnu(self):
        tache, autre = fabriques.tache(self.u1), fabriques.tache(self.u2)
        self.assertEqual(self._patch(tache, {'bloquee_par_id': autre.pk}).status_code, 404)

    # --- Invariants 7 et 9 : projet, étape, étiquettes -------------------------------------------

    def test_un_projet_d_un_autre_compte_est_inexistant(self):
        tache = fabriques.tache(self.u1)
        reponse = self._patch(tache, {'projet_id': fabriques.projet(self.ext).pk})
        self.assertEqual((reponse.status_code, reponse.json()), (400, {'projet_id': ['Projet inexistant.']}))

    def test_deplacer_dans_un_projet_trie_et_range_la_tache_et_ses_sous_taches(self):
        projet = fabriques.projet(self.u1)
        section = fabriques.section(projet)
        tache = fabriques.tache(self.u1)
        enfant = fabriques.tache(self.u1, parent=tache)
        reponse = self._patch(tache, {'projet_id': projet.pk, 'section_id': section.pk})
        self.assertEqual(reponse.status_code, 200)
        relue, enfant = _relue(tache), _relue(enfant)
        self.assertEqual((relue.projet_id, relue.section_id), (projet.pk, section.pk))
        self.assertIsNotNone(relue.triee_le)
        self.assertEqual((enfant.projet_id, enfant.section_id), (projet.pk, section.pk))

    def test_changer_de_projet_vide_l_etape(self):
        un, deux = fabriques.projet(self.u1), fabriques.projet(self.u1)
        tache = fabriques.tache(self.u1, projet=un)
        tache.section = fabriques.section(un)
        tache.save(update_fields=['section'])
        self._patch(tache, {'projet_id': deux.pk})
        relue = _relue(tache)
        self.assertEqual((relue.projet_id, relue.section_id), (deux.pk, None))

    def test_une_etape_d_un_autre_projet_repond_comme_inconnue(self):
        un, deux = fabriques.projet(self.u1), fabriques.projet(self.u1)
        tache = fabriques.tache(self.u1, projet=un)
        self.assertEqual(self._patch(tache, {'section_id': fabriques.section(deux).pk}).status_code, 404)

    def test_une_sous_tache_garde_le_projet_de_son_parent(self):
        parent = fabriques.tache(self.u1, projet=fabriques.projet(self.u1))
        enfant = fabriques.tache(self.u1, parent=parent, projet=parent.projet)
        reponse = self._patch(enfant, {'projet_id': None})
        self.assertEqual((reponse.status_code, reponse.json()), (400, {'projet_id': ['Non modifiable ici.']}))

    def test_les_etiquettes_sont_remplacees(self):
        tache = fabriques.tache(self.u1)
        un = Etiquette.objects.create(company=self.a, proprietaire=self.u1, nom='magasin')
        deux = Etiquette.objects.create(company=self.a, proprietaire=self.u1, nom='urgent')
        reponse = self._patch(tache, {'etiquettes': [un.pk, deux.pk]})
        self.assertEqual({e['id'] for e in reponse.json()['tache']['etiquettes']}, {un.pk, deux.pk})
        reponse = self._patch(tache, {'etiquettes': [deux.pk]})
        self.assertEqual([e['id'] for e in reponse.json()['tache']['etiquettes']], [deux.pk])
        self.assertEqual(EtiquetteTache.objects.filter(tache=tache).count(), 1)

    def test_une_etiquette_d_un_collegue_repond_comme_inconnue(self):
        tache = fabriques.tache(self.u1)
        etrangere = Etiquette.objects.create(company=self.a, proprietaire=self.u2, nom='privee')
        self.assertEqual(self._patch(tache, {'etiquettes': [etrangere.pk]}).status_code, 404)
        self.assertEqual(EtiquetteTache.objects.count(), 0)

    def test_un_lien_hors_cible_liable_est_refuse(self):
        tache = fabriques.tache(self.u1)
        reponse = self._patch(tache, {'lien': {'cible': 'stock.produit', 'id': 3}})
        self.assertEqual(reponse.status_code, 400)
        self.assertEqual(reponse.json(), {'lien': ["Ce type d'élément ne peut pas être lié à une tâche."]})

    def test_retirer_le_lien(self):
        cible = ContentType.objects.get_by_natural_key('crm', 'lead')
        tache = fabriques.tache(self.u1, content_type=cible, object_id=7, lien_etat='ok')
        reponse = self._patch(tache, {'lien': None})
        self.assertIsNone(reponse.json()['tache']['lien'])
        relue = _relue(tache)
        self.assertEqual((relue.content_type_id, relue.object_id), (None, None))

    def test_la_confidentialite_et_le_jalon_s_ecrivent(self):
        tache = fabriques.tache(self.u1)
        corps = self._patch(tache, {'confidentiel': True, 'jalon': True, 'duree_reelle_minutes': 25}).json()['tache']
        self.assertEqual((corps['confidentiel'], corps['confidentielle'], corps['jalon'],
                          corps['duree_reelle_minutes']), (True, True, True, 25))


class SupprimerTests(BaseApi):
    def _supprimer(self, tache, compte=None):
        return self._api(compte).delete(f'{URL}taches/{tache.pk}/')

    def test_supprimer_emporte_les_sous_taches_dans_un_geste(self):
        parent = fabriques.tache(self.u1)
        enfant = fabriques.tache(self.u1, parent=parent)
        reponse = self._supprimer(parent)
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(list(reponse.json()), ['geste_id'])
        self.assertTrue(_relue(parent).is_deleted)
        self.assertTrue(_relue(enfant).is_deleted)
        self.assertFalse(Tache.objects.filter(pk__in=[parent.pk, enfant.pk]).exists())

    def test_annuler_la_suppression_les_restaure_tous_les_deux(self):
        parent = fabriques.tache(self.u1)
        enfant = fabriques.tache(self.u1, parent=parent)
        geste = self._supprimer(parent).json()['geste_id']
        bilan = annuler_geste(self.u1, geste)
        self.assertEqual({(r['objet'], r['id']) for r in bilan['restaurees']},
                         {('tache', parent.pk), ('tache', enfant.pk)})
        self.assertFalse(_relue(parent).is_deleted or _relue(enfant).is_deleted)

    def test_les_rappels_en_attente_sont_annules(self):
        tache = fabriques.tache(self.u1, jour_prevu=_j(1))
        rappel = Rappel.objects.create(company=self.a, proprietaire=self.u1, tache=tache, jour=_j(1),
                                       heure=datetime.time(9, 0))
        self._supprimer(tache)
        rappel.refresh_from_db()
        self.assertEqual(rappel.statut, StatutRappel.ANNULE)

    def test_la_tache_d_un_collegue_repond_comme_inconnue(self):
        autre = fabriques.tache(self.u2)
        self.assertEqual(self._supprimer(autre).status_code, 404)
        self.assertFalse(_relue(autre).is_deleted)

    def test_sans_le_droit_403_et_anonyme_401(self):
        sans = fabriques.compte(self.a, voir=False, nom='sans')
        tache = fabriques.tache(self.u1)
        self.assertEqual(self._supprimer(tache, sans).status_code, 403)
        self.assertEqual(APIClient().delete(f'{URL}taches/{tache.pk}/').status_code, 401)


# --- TCH50 : actions d'état -------------------------------------------------------------------------

def _serie_hebdo(compte, **champs):
    """Règle « chaque lundi » (calendrier) du compte, débutée il y a une semaine."""
    champs.setdefault('frequence', 'hebdo')
    champs.setdefault('jours_semaine', '1000000')
    champs.setdefault('date_debut', _j(-7))
    return RegleRecurrence.objects.create(company=compte.company, proprietaire=compte, **champs)


def _occurrence(compte, regle, jour, **champs):
    """L'occurrence OUVERTE d'une série, posée par l'ORM."""
    return fabriques.tache(compte, titre='Rapport hebdo', recurrence=regle, occurrence_du=jour, jour_prevu=jour,
                           **champs)


class PlanifierActionTests(BaseApi):
    def _planifier(self, tache, corps, compte=None):
        envoi = {'lock_version': _relue(tache).lock_version, **corps}
        return self._post(f'taches/{tache.pk}/planifier/', envoi, compte)

    def test_pose_un_jour_une_heure_et_rend_la_tache_ecrite(self):
        tache = fabriques.tache(self.u1)
        reponse = self._planifier(tache, {'jour_prevu': _j(2).isoformat(), 'heure_debut': '10:00'})
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(list(reponse.json()), list(exemple('tache_ecrite')))
        relue = _relue(tache)
        self.assertEqual((relue.jour_prevu, relue.heure_debut, relue.moment, relue.reports),
                         (_j(2), datetime.time(10, 0), 'matin', 0))
        self.assertIsNotNone(reponse.json()['geste_id'])

    def test_lock_version_est_requis(self):
        tache = fabriques.tache(self.u1)
        reponse = self._post(f'taches/{tache.pk}/planifier/', {'jour_prevu': _j(1).isoformat()})
        self.assertEqual((reponse.status_code, reponse.json()), (400, {'lock_version': ['Requis.']}))

    def test_une_version_perimee_409_avec_la_tache_complete(self):
        tache = fabriques.tache(self.u1)
        perimee = _relue(tache).lock_version
        self._planifier(tache, {'jour_prevu': _j(1).isoformat()})
        reponse = self._post(f'taches/{tache.pk}/planifier/', {'jour_prevu': _j(3).isoformat(),
                                                               'lock_version': perimee})
        self.assertEqual(reponse.status_code, 409)
        corps = reponse.json()
        self.assertEqual(corps['code'], 'conflit_version')
        self.assertEqual(list(corps['actuel']), list(exemple('tache')))
        self.assertEqual(_relue(tache).jour_prevu, _j(1))

    def test_une_heure_sans_jour_est_refusee_sous_son_champ(self):
        tache = fabriques.tache(self.u1)
        reponse = self._planifier(tache, {'heure_debut': '10:00'})
        self.assertEqual((reponse.status_code, reponse.json()),
                         (400, {'heure_debut': ['Une heure demande un jour prévu.']}))

    def test_un_report_est_compte_seulement_selon_l_invariant_4(self):
        retard = fabriques.tache(self.u1, jour_prevu=_j(-1))
        self._planifier(retard, {'jour_prevu': _j(2).isoformat()})
        self.assertEqual(_relue(retard).reports, 1)
        futur = fabriques.tache(self.u1, jour_prevu=_j(3))
        self._planifier(futur, {'jour_prevu': _j(5).isoformat()})
        premier = fabriques.tache(self.u1)
        self._planifier(premier, {'jour_prevu': _j(5).isoformat()})
        self.assertEqual((_relue(futur).reports, _relue(premier).reports), (0, 0))

    def test_en_reserve_compte_un_report_pour_une_tache_en_retard(self):
        retard = fabriques.tache(self.u1, jour_prevu=_j(0))
        self._planifier(retard, {'quelque_jour': True})
        relue = _relue(retard)
        self.assertEqual((relue.reports, relue.quelque_jour, relue.jour_prevu), (1, True, None))

    def test_prevue_apres_l_echeance_est_un_avertissement(self):
        tache = fabriques.tache(self.u1, echeance=_j(2))
        reponse = self._planifier(tache, {'jour_prevu': _j(4).isoformat()})
        self.assertIn('prevue_apres_echeance', [a['code'] for a in reponse.json()['avertissements']])

    def test_proprietaire_attendu_et_collegue(self):
        tache = fabriques.tache(self.u1)
        self.assertEqual(self._planifier(tache, {'proprietaire_attendu': self.u2.pk}).status_code, 409)
        autre = fabriques.tache(self.u2)
        self.assertEqual(self._planifier(autre, {'jour_prevu': _j(1).isoformat()}).status_code, 404)


class TerminerTests(BaseApi):
    def _terminer(self, tache, compte=None, corps=None):
        return self._post(f'taches/{tache.pk}/terminer/', corps, compte)

    def test_cocher_pose_fait_le_et_rend_la_tache_ecrite(self):
        tache = fabriques.tache(self.u1)
        reponse = self._terminer(tache, corps={'proprietaire_attendu': self.u1.pk})
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(list(reponse.json()), list(exemple('tache_ecrite')))
        relue = _relue(tache)
        self.assertEqual((relue.statut, relue.annule_le), (StatutTache.FAIT, None))
        self.assertIsNotNone(relue.fait_le)
        self.assertIsNone(reponse.json()['suivante'])
        self.assertEqual(GesteAnnulable.objects.get(pk=reponse.json()['geste_id']).message, 'Faite')

    def test_cocher_deux_fois_ne_change_rien(self):
        tache = fabriques.tache(self.u1)
        premier = self._terminer(tache).json()
        fait_le = _relue(tache).fait_le
        second = self._terminer(tache).json()
        self.assertIsNone(second['geste_id'])
        self.assertEqual((_relue(tache).fait_le, premier['tache']['statut']), (fait_le, 'fait'))

    def test_terminer_un_parent_termine_ses_sous_taches_ouvertes(self):
        parent = fabriques.tache(self.u1)
        ouverte = fabriques.tache(self.u1, parent=parent)
        hier = timezone.now() - datetime.timedelta(days=1)
        deja = fabriques.tache(self.u1, parent=parent, statut=StatutTache.FAIT, fait_le=hier)
        fait_avant = _relue(deja).fait_le
        self._terminer(parent)
        self.assertEqual(_relue(ouverte).statut, StatutTache.FAIT)
        self.assertIsNotNone(_relue(ouverte).fait_le)
        self.assertEqual(_relue(deja).fait_le, fait_avant)

    def test_les_rappels_en_attente_sont_annules(self):
        tache = fabriques.tache(self.u1, jour_prevu=_j(1))
        rappel = Rappel.objects.create(company=self.a, proprietaire=self.u1, tache=tache, jour=_j(1),
                                       heure=datetime.time(9, 0))
        self._terminer(tache)
        rappel.refresh_from_db()
        self.assertEqual(rappel.statut, StatutRappel.ANNULE)

    def test_cocher_sort_la_tache_d_a_trier(self):
        tache = fabriques.tache(self.u1)
        self.assertIsNone(tache.triee_le)
        self._terminer(tache)
        self.assertIsNotNone(_relue(tache).triee_le)

    def test_annuler_la_terminaison_rouvre_tout(self):
        parent = fabriques.tache(self.u1)
        enfant = fabriques.tache(self.u1, parent=parent)
        geste = self._terminer(parent).json()['geste_id']
        annuler_geste(self.u1, geste)
        for tache in (parent, enfant):
            relue = _relue(tache)
            self.assertEqual((relue.statut, relue.fait_le), (StatutTache.A_FAIRE, None))

    def test_la_tache_d_un_collegue_repond_comme_inconnue(self):
        autre = fabriques.tache(self.u2)
        self.assertEqual(self._terminer(autre).status_code, 404)
        propre = fabriques.tache(self.u1)
        reponse = self._terminer(propre, corps={'proprietaire_attendu': self.u2.pk})
        self.assertEqual((reponse.status_code, _relue(propre).statut), (409, StatutTache.A_FAIRE))

    # --- Invariant 5 : récurrence ----------------------------------------------------------------

    def test_cocher_une_occurrence_fait_naitre_la_suivante(self):
        regle = _serie_hebdo(self.u1)
        tache = _occurrence(self.u1, regle, _j(0))
        reponse = self._terminer(tache)
        corps = reponse.json()
        self.assertEqual(list(corps), list(exemple('tache_recurrente_ecrite')))
        attendu = prochaine_occurrence(regle, _j(0), _j(0), fait_le=_j(0))
        suivante = Tache.objects.get(pk=corps['suivante']['id'])
        self.assertEqual((suivante.jour_prevu, suivante.occurrence_du, suivante.recurrence, suivante.statut),
                         (attendu, attendu, regle, StatutTache.A_FAIRE))
        self.assertEqual((suivante.source, suivante.titre), ('recurrence', 'Rapport hebdo'))
        self.assertEqual(Tache.objects.filter(recurrence=regle, statut=StatutTache.A_FAIRE).count(), 1)
        self.assertTrue(GesteAnnulable.objects.get(pk=corps['geste_id']).message.startswith('Faite · prochaine '))

    def test_la_suivante_nait_a_la_version_que_rouvrir_attend(self):
        regle = _serie_hebdo(self.u1)
        reponse = self._terminer(_occurrence(self.u1, regle, _j(0))).json()
        self.assertEqual(Tache.objects.get(pk=reponse['suivante']['id']).lock_version, VERSION_OCCURRENCE_NEUVE)

    def test_la_suivante_reprend_projet_etiquettes_et_check_list_remise_a_zero(self):
        regle = _serie_hebdo(self.u1)
        projet = fabriques.projet(self.u1)
        tache = _occurrence(self.u1, regle, _j(0), projet=projet)
        etiquette = Etiquette.objects.create(company=self.a, proprietaire=self.u1, nom='bureau')
        EtiquetteTache.objects.create(company=self.a, tache=tache, etiquette=etiquette)
        ElementChecklist.objects.create(company=self.a, tache=tache, libelle='Chiffres', fait=True, rang=1024)
        suivante = Tache.objects.get(pk=self._terminer(tache).json()['suivante']['id'])
        self.assertEqual(suivante.projet, projet)
        self.assertEqual(list(EtiquetteTache.objects.filter(tache=suivante).values_list('etiquette_id', flat=True)),
                         [etiquette.pk])
        self.assertEqual(list(ElementChecklist.objects.filter(tache=suivante).values_list('libelle', 'fait')),
                         [('Chiffres', False)])

    def test_une_serie_close_n_a_plus_de_suivante(self):
        regle = _serie_hebdo(self.u1, date_fin=_j(0))
        reponse = self._terminer(_occurrence(self.u1, regle, _j(0))).json()
        self.assertIsNone(reponse['suivante'])
        regle.refresh_from_db()
        self.assertFalse(regle.actif)

    def test_une_serie_arretee_n_a_plus_de_suivante(self):
        regle = _serie_hebdo(self.u1, actif=False)
        reponse = self._terminer(_occurrence(self.u1, regle, _j(0))).json()
        self.assertIsNone(reponse['suivante'])

    def test_annuler_la_terminaison_retire_la_suivante(self):
        regle = _serie_hebdo(self.u1)
        tache = _occurrence(self.u1, regle, _j(0))
        corps = self._terminer(tache).json()
        annuler_geste(self.u1, corps['geste_id'])
        self.assertEqual(_relue(tache).statut, StatutTache.A_FAIRE)
        self.assertTrue(Tache.all_objects.get(pk=corps['suivante']['id']).is_deleted)


class RouvrirTests(BaseApi):
    def _rouvrir(self, tache, compte=None):
        return self._post(f'taches/{tache.pk}/rouvrir/', None, compte)

    def test_rouvrir_remet_fait_le_et_annule_le_a_nul(self):
        for statut, champ in ((StatutTache.FAIT, 'fait_le'), (StatutTache.ANNULE, 'annule_le')):
            with self.subTest(statut=statut):
                tache = fabriques.tache(self.u1, statut=statut, **{champ: timezone.now()})
                reponse = self._rouvrir(tache)
                self.assertEqual(reponse.status_code, 200)
                self.assertEqual(list(reponse.json()), list(exemple('tache_ecrite')))
                relue = _relue(tache)
                self.assertEqual((relue.statut, relue.fait_le, relue.annule_le), (StatutTache.A_FAIRE, None, None))

    def test_rouvrir_une_tache_ouverte_ne_change_rien(self):
        tache = fabriques.tache(self.u1)
        self.assertIsNone(self._rouvrir(tache).json()['geste_id'])

    def test_rouvrir_supprime_la_suivante_intacte(self):
        regle = _serie_hebdo(self.u1)
        tache = _occurrence(self.u1, regle, _j(0))
        suivante = self._post(f'taches/{tache.pk}/terminer/')
        suivante = Tache.objects.get(pk=suivante.json()['suivante']['id'])
        self._rouvrir(tache)
        self.assertTrue(Tache.all_objects.get(pk=suivante.pk).is_deleted)
        self.assertEqual(_relue(tache).statut, StatutTache.A_FAIRE)

    def test_rouvrir_garde_la_suivante_deja_modifiee(self):
        regle = _serie_hebdo(self.u1)
        tache = _occurrence(self.u1, regle, _j(0))
        suivante = Tache.objects.get(pk=self._post(f'taches/{tache.pk}/terminer/').json()['suivante']['id'])
        corps = {'titre': 'Déjà reprise', 'lock_version': suivante.lock_version}
        self._api().patch(f'{URL}taches/{suivante.pk}/', corps, format='json')
        self._rouvrir(tache)
        self.assertFalse(Tache.all_objects.get(pk=suivante.pk).is_deleted)

    def test_annuler_la_reouverture_referme(self):
        tache = fabriques.tache(self.u1, statut=StatutTache.FAIT, fait_le=timezone.now())
        geste = self._rouvrir(tache).json()['geste_id']
        annuler_geste(self.u1, geste)
        self.assertEqual(_relue(tache).statut, StatutTache.FAIT)

    def test_la_tache_d_un_collegue_repond_comme_inconnue(self):
        autre = fabriques.tache(self.u2, statut=StatutTache.FAIT, fait_le=timezone.now())
        self.assertEqual(self._rouvrir(autre).status_code, 404)


class SauterTests(BaseApi):
    def test_sauter_abandonne_l_occurrence_et_fait_naitre_la_suivante(self):
        regle = _serie_hebdo(self.u1)
        tache = _occurrence(self.u1, regle, _j(0))
        corps = self._post(f'taches/{tache.pk}/sauter/').json()
        relue = _relue(tache)
        self.assertEqual((relue.statut, relue.fait_le), (StatutTache.ANNULE, None))
        self.assertIsNotNone(relue.annule_le)
        self.assertEqual(corps['suivante']['recurrente'], True)
        self.assertEqual(Tache.objects.filter(recurrence=regle, statut=StatutTache.A_FAIRE).count(), 1)

    def test_sauter_une_tache_qui_ne_se_repete_pas_est_refuse(self):
        tache = fabriques.tache(self.u1)
        reponse = self._post(f'taches/{tache.pk}/sauter/')
        self.assertEqual(reponse.status_code, 400)
        self.assertEqual(list(reponse.json()), ['recurrence'])
        self.assertEqual(_relue(tache).statut, StatutTache.A_FAIRE)


class TrancherTests(BaseApi):
    def _trancher(self, tache, corps):
        return self._post(f'taches/{tache.pk}/trancher/', corps)

    def test_aujourdhui_compte_le_report_et_pose_reports_tranches(self):
        tache = fabriques.tache(self.u1, jour_prevu=_j(-2), reports=3)
        reponse = self._trancher(tache, {'choix': 'aujourdhui'})
        self.assertEqual(reponse.status_code, 200)
        relue = _relue(tache)
        self.assertEqual((relue.jour_prevu, relue.reports, relue.reports_tranches), (_j(0), 4, 4))

    def test_garder_une_date_future_la_conserve(self):
        tache = fabriques.tache(self.u1, jour_prevu=_j(3), reports=3)
        self._trancher(tache, {'choix': 'garder'})
        relue = _relue(tache)
        self.assertEqual((relue.jour_prevu, relue.reports, relue.reports_tranches), (_j(3), 3, 3))

    def test_garder_une_date_passee_la_ramene_a_aujourdhui(self):
        tache = fabriques.tache(self.u1, jour_prevu=_j(-4), reports=3)
        self._trancher(tache, {'choix': 'garder'})
        self.assertEqual(_relue(tache).jour_prevu, _j(0))

    def test_un_jour_precis(self):
        tache = fabriques.tache(self.u1, jour_prevu=_j(0), reports=3)
        self._trancher(tache, {'choix': 'jour', 'jour': _j(6).isoformat()})
        relue = _relue(tache)
        self.assertEqual((relue.jour_prevu, relue.reports_tranches), (_j(6), relue.reports))

    def test_jour_est_requis_pour_choisir_un_jour(self):
        tache = fabriques.tache(self.u1, jour_prevu=_j(0))
        reponse = self._trancher(tache, {'choix': 'jour'})
        self.assertEqual((reponse.status_code, reponse.json()), (400, {'jour': ['Requis.']}))

    def test_un_jour_met_en_reserve(self):
        tache = fabriques.tache(self.u1, jour_prevu=_j(0))
        self._trancher(tache, {'choix': 'un_jour'})
        relue = _relue(tache)
        self.assertEqual((relue.quelque_jour, relue.jour_prevu), (True, None))

    def test_abandonner(self):
        tache = fabriques.tache(self.u1, jour_prevu=_j(0))
        reponse = self._trancher(tache, {'choix': 'abandonner'})
        relue = _relue(tache)
        self.assertEqual((relue.statut, reponse.json()['tache']['statut']), (StatutTache.ANNULE, 'annule'))
        self.assertIsNotNone(relue.annule_le)

    def test_choix_inconnu_refuse(self):
        tache = fabriques.tache(self.u1, jour_prevu=_j(0))
        for corps in ({'choix': 'plus_tard'}, {'choix': 'prochain_jour_ouvre'}, {}):
            with self.subTest(corps=corps):
                self.assertEqual(self._trancher(tache, corps).status_code, 400)

    def test_annuler_la_decision_restaure_le_jour_et_le_compteur(self):
        tache = fabriques.tache(self.u1, jour_prevu=_j(-2), reports=3)
        geste = self._trancher(tache, {'choix': 'aujourdhui'}).json()['geste_id']
        annuler_geste(self.u1, geste)
        relue = _relue(tache)
        self.assertEqual((relue.jour_prevu, relue.reports, relue.reports_tranches), (_j(-2), 3, 0))


class AttendreEtRecuTests(BaseApi):
    def test_attendre_pose_le_statut_et_le_texte(self):
        tache = fabriques.tache(self.u1)
        reponse = self._post(f'taches/{tache.pk}/attendre/', {'en_attente_de': 'Lydec'})
        self.assertEqual(reponse.status_code, 200)
        relue = _relue(tache)
        self.assertEqual((relue.statut, relue.en_attente_de), (StatutTache.EN_ATTENTE, 'Lydec'))
        self.assertEqual(reponse.json()['tache']['en_attente_de'], 'Lydec')

    def test_attendre_sans_texte_est_refuse_sous_son_champ(self):
        tache = fabriques.tache(self.u1)
        for corps in ({}, {'en_attente_de': '  '}):
            with self.subTest(corps=corps):
                reponse = self._post(f'taches/{tache.pk}/attendre/', corps)
                self.assertEqual((reponse.status_code, reponse.json()),
                                 (400, {'en_attente_de': ['Dis de qui ou de quoi tu attends.']}))
        self.assertEqual(_relue(tache).statut, StatutTache.A_FAIRE)

    def test_recu_remet_a_faire_et_vide_le_texte(self):
        tache = fabriques.tache(self.u1, statut=StatutTache.EN_ATTENTE, en_attente_de='Lydec')
        reponse = self._post(f'taches/{tache.pk}/recu/')
        self.assertEqual(reponse.status_code, 200)
        relue = _relue(tache)
        self.assertEqual((relue.statut, relue.en_attente_de), (StatutTache.A_FAIRE, ''))

    def test_annuler_l_attente(self):
        tache = fabriques.tache(self.u1)
        geste = self._post(f'taches/{tache.pk}/attendre/', {'en_attente_de': 'Lydec'}).json()['geste_id']
        annuler_geste(self.u1, geste)
        relue = _relue(tache)
        self.assertEqual((relue.statut, relue.en_attente_de), (StatutTache.A_FAIRE, ''))

    def test_la_tache_d_un_collegue_repond_comme_inconnue(self):
        autre = fabriques.tache(self.u2)
        self.assertEqual(self._post(f'taches/{autre.pk}/attendre/', {'en_attente_de': 'x'}).status_code, 404)
        self.assertEqual(self._post(f'taches/{autre.pk}/recu/').status_code, 404)


class RestaurerTests(BaseApi):
    def test_restaurer_une_tache_supprimee_avec_ses_sous_taches(self):
        parent = fabriques.tache(self.u1)
        enfant = fabriques.tache(self.u1, parent=parent)
        self._api().delete(f'{URL}taches/{parent.pk}/')
        reponse = self._post(f'taches/{parent.pk}/restaurer/')
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(list(reponse.json()), list(exemple('tache_ecrite')))
        self.assertFalse(_relue(parent).is_deleted or _relue(enfant).is_deleted)

    def test_restaurer_dont_le_projet_reste_supprime_revient_dans_a_trier(self):
        projet = fabriques.projet(self.u1)
        tache = fabriques.tache(self.u1, projet=projet)
        self._api().delete(f'{URL}taches/{tache.pk}/')
        projet.soft_delete(self.u1, record=False)
        reponse = self._post(f'taches/{tache.pk}/restaurer/')
        relue = _relue(tache)
        self.assertEqual((relue.is_deleted, relue.projet_id, relue.triee_le), (False, None, None))
        self.assertEqual(GesteAnnulable.objects.get(pk=reponse.json()['geste_id']).message,
                         'Restaurée dans À trier')

    def test_une_tache_vivante_ou_d_un_collegue_repond_comme_inconnue(self):
        vivante = fabriques.tache(self.u1)
        self.assertEqual(self._post(f'taches/{vivante.pk}/restaurer/').status_code, 404)
        autre = fabriques.tache(self.u2)
        autre.soft_delete(self.u2, record=False)
        self.assertEqual(self._post(f'taches/{autre.pk}/restaurer/').status_code, 404)
        self.assertTrue(_relue(autre).is_deleted)

    def test_annuler_la_restauration_supprime_de_nouveau(self):
        tache = fabriques.tache(self.u1)
        self._api().delete(f'{URL}taches/{tache.pk}/')
        geste = self._post(f'taches/{tache.pk}/restaurer/').json()['geste_id']
        annuler_geste(self.u1, geste)
        self.assertTrue(_relue(tache).is_deleted)
