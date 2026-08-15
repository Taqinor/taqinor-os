"""Tests NTMIG22 — instance de playbook (checklist de déploiement).

Critère d'acceptation : instancier le playbook « Ventes » et cocher 5 étapes
sur 8 affiche 62 % d'avancement, PERSISTANT entre sessions (relu depuis la
base, pas depuis l'objet en mémoire).

Couvre aussi : le playbook est résolu via ``kb.selectors`` (scopé société +
type playbook), l'étape inconnue est refusée, la clôture est refusée tant qu'il
reste des étapes, l'isolation multi-société et la garde de rôle.
"""
from django.test import TestCase

from apps.kb.models import KbArticle
from apps.migration import services
from apps.migration.models import PlaybookInstance, ProjetMigration

from ._base import auth, make_admin, make_company, make_user

STRUCTURE = [
    {'cle': 'prerequis', 'titre': 'Prérequis', 'etapes': [
        {'cle': 'p1', 'libelle': 'Société'},
        {'cle': 'p2', 'libelle': 'Rôles'},
        {'cle': 'p3', 'libelle': 'Utilisateurs'},
    ]},
    {'cle': 'reglages', 'titre': 'Réglages', 'etapes': [
        {'cle': 'r1', 'libelle': 'TVA'},
        {'cle': 'r2', 'libelle': 'Numérotation'},
    ]},
    {'cle': 'golive', 'titre': 'Go-live', 'etapes': [
        {'cle': 'g1', 'libelle': 'Recette'},
        {'cle': 'g2', 'libelle': 'Bascule'},
        {'cle': 'g3', 'libelle': 'Formation'},
    ]},
]

INSTANCES = '/api/django/migration/playbook-instances/'


class Ntmig22PlaybookInstanceTests(TestCase):

    def setUp(self):
        self.company = make_company('ntmig22', 'NTMIG22')
        self.admin = make_admin(self.company, 'ntmig22-admin')
        self.api = auth(self.admin)
        self.playbook = KbArticle.objects.create(
            company=self.company, titre='Déploiement module Ventes',
            type_article=KbArticle.TypeArticle.PLAYBOOK,
            contenu_structure=STRUCTURE)

    def _instancier(self, **extra):
        payload = {'playbook_article': self.playbook.pk}
        payload.update(extra)
        return self.api.post(f'{INSTANCES}instancier/', payload, format='json')

    def test_instancier_puis_cocher_5_sur_8_donne_62_pourcent(self):
        resp = self._instancier(client_final='Client Alpha')
        self.assertEqual(resp.status_code, 201, resp.data)
        instance_id = resp.data['id']
        self.assertEqual(resp.data['nb_etapes'], 8)
        self.assertEqual(resp.data['progression'], 0)
        self.assertEqual(resp.data['playbook_titre'],
                         'Déploiement module Ventes')

        for cle in ('p1', 'p2', 'p3', 'r1', 'r2'):
            coche = self.api.post(
                f'{INSTANCES}{instance_id}/cocher/', {'cle': cle},
                format='json')
            self.assertEqual(coche.status_code, 200, coche.data)

        self.assertEqual(coche.data['nb_faites'], 5)
        self.assertEqual(coche.data['progression'], 62)

        # PERSISTANT : relu depuis la base, pas depuis l'objet en mémoire.
        relu = PlaybookInstance.objects.get(pk=instance_id)
        self.assertEqual(relu.progression, 62)
        detail = self.api.get(f'{INSTANCES}{instance_id}/')
        self.assertEqual(detail.data['progression'], 62)

    def test_decocher_ramene_la_progression(self):
        instance_id = self._instancier().data['id']
        self.api.post(f'{INSTANCES}{instance_id}/cocher/', {'cle': 'p1'},
                      format='json')
        resp = self.api.post(
            f'{INSTANCES}{instance_id}/cocher/', {'cle': 'p1', 'fait': False},
            format='json')
        self.assertEqual(resp.data['nb_faites'], 0)
        self.assertEqual(resp.data['progression'], 0)

    def test_etape_inconnue_refusee(self):
        """Une clé fantôme ne doit jamais entrer dans ``avancement``."""
        instance_id = self._instancier().data['id']
        resp = self.api.post(
            f'{INSTANCES}{instance_id}/cocher/', {'cle': 'inexistante'},
            format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(
            PlaybookInstance.objects.get(pk=instance_id).avancement, {})

    def test_terminer_refuse_tant_qu_il_reste_des_etapes(self):
        instance_id = self._instancier().data['id']
        self.api.post(f'{INSTANCES}{instance_id}/cocher/', {'cle': 'p1'},
                      format='json')
        resp = self.api.post(f'{INSTANCES}{instance_id}/terminer/', {},
                             format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(len(resp.data['etapes_restantes']), 7)
        self.assertEqual(PlaybookInstance.objects.get(pk=instance_id).statut,
                         PlaybookInstance.Statut.EN_COURS)

        for cle in ('p2', 'p3', 'r1', 'r2', 'g1', 'g2', 'g3'):
            self.api.post(f'{INSTANCES}{instance_id}/cocher/', {'cle': cle},
                          format='json')
        resp = self.api.post(f'{INSTANCES}{instance_id}/terminer/', {},
                             format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], 'termine')
        self.assertEqual(resp.data['progression'], 100)

    def test_article_ordinaire_non_instanciable(self):
        ordinaire = KbArticle.objects.create(
            company=self.company, titre='Procédure')
        resp = self._instancier(playbook_article=ordinaire.pk)
        self.assertEqual(resp.status_code, 400)

    def test_playbook_sans_etape_non_instanciable(self):
        vide = KbArticle.objects.create(
            company=self.company, titre='Playbook vide',
            type_article=KbArticle.TypeArticle.PLAYBOOK,
            contenu_structure=[{'titre': 'Phase sans étape'}])
        resp = self._instancier(playbook_article=vide.pk)
        self.assertEqual(resp.status_code, 400)

    def test_playbook_d_une_autre_societe_introuvable(self):
        autre = make_company('ntmig22-bis', 'NTMIG22 bis')
        etranger = KbArticle.objects.create(
            company=autre, titre='Playbook voisin',
            type_article=KbArticle.TypeArticle.PLAYBOOK,
            contenu_structure=STRUCTURE)
        resp = self._instancier(playbook_article=etranger.pk)
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(PlaybookInstance.objects.exists())

    def test_projet_d_une_autre_societe_refuse(self):
        autre = make_company('ntmig22-ter', 'NTMIG22 ter')
        projet = ProjetMigration.objects.create(
            company=autre, nom='Projet voisin')
        resp = self._instancier(projet_migration=projet.pk)
        self.assertEqual(resp.status_code, 400)

    def test_liste_scopee_societe(self):
        self._instancier()
        autre = make_company('ntmig22-quat', 'NTMIG22 quat')
        autre_admin = make_admin(autre, 'ntmig22-autre-admin')
        resp = auth(autre_admin).get(INSTANCES)
        data = resp.data
        lignes = data['results'] if isinstance(data, dict) else data
        self.assertEqual(lignes, [])

    def test_role_limite_refuse(self):
        limite = make_user(self.company, 'ntmig22-limite')
        resp = auth(limite).get(INSTANCES)
        self.assertEqual(resp.status_code, 403)

    def test_post_direct_refuse(self):
        """Créer une instance sans passer par ``instancier`` donnerait une
        checklist SANS étapes, que rien ne remplirait jamais."""
        resp = self.api.post(INSTANCES, {'client_final': 'X'}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(PlaybookInstance.objects.exists())

    def test_instantane_fige_a_l_instanciation(self):
        """Éditer le playbook modèle ne réécrit pas une checklist en cours."""
        instance_id = self._instancier().data['id']
        self.playbook.contenu_structure = STRUCTURE + [
            {'cle': 'apres', 'titre': 'Ajoutée après', 'etapes': [
                {'cle': 'a1', 'libelle': 'Nouvelle étape'}]}]
        self.playbook.save(update_fields=['contenu_structure'])
        detail = self.api.get(f'{INSTANCES}{instance_id}/')
        self.assertEqual(detail.data['nb_etapes'], 8)

    def test_progression_ignore_les_cles_residuelles(self):
        """Une clé d'avancement hors instantané ne fait jamais dépasser 100 %."""
        instance = services.instancier_playbook(
            self.playbook, company=self.company)
        instance.avancement = {cle: True for cle in instance.cles_etapes}
        instance.avancement['fantome'] = True
        instance.save(update_fields=['avancement'])
        self.assertEqual(instance.nb_faites, 8)
        self.assertEqual(instance.progression, 100)

    def test_suppression_du_playbook_conserve_l_instance(self):
        """La trace d'un déploiement survit à la suppression du modèle."""
        instance_id = self._instancier().data['id']
        self.playbook.delete()
        instance = PlaybookInstance.objects.get(pk=instance_id)
        self.assertIsNone(instance.playbook_article_id)
        self.assertEqual(instance.playbook_titre,
                         'Déploiement module Ventes')
        self.assertEqual(instance.nb_etapes, 8)
