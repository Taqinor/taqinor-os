"""VAO21 — le service de collecte : l'orchestration, seule à toucher la base.

Ce que ces tests PROUVENT, dans l'ordre du « Done = » de la tâche :

* collecte rejouée = 0 nouveau (idempotence, via le dédoublonnage VAO11) ;
* un mot-clé désactivé n'est plus interrogé ;
* un avis fautif est journalisé et les AUTRES passent (transaction par avis) ;
* aucune écriture hors service (garde d'introspection AST sur le module).

Aucun test ici ne touche le réseau : le lecteur est INJECTÉ. C'est exactement
ce que la conception cherche — le collecteur du portail (VAO15-VAO20) est gaté
par une décision fondateur (VAO2) et se branchera par ``enregistrer_lecteur``
sans réécrire une ligne de ce service.
"""
import ast
import pathlib

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from authentication.models import Company
from apps.veille_ao.lecteurs import (
    LecteurIndisponible, enregistrer_lecteur, lecteur_pour, retirer_lecteur,
)
from apps.veille_ao.models import (
    AvisMarche, MotCleVeille, NiveauMotCle, PorteeExclusion, RegleExclusion,
    SourceVeille, StatutAvis, TypeSource,
)
from apps.veille_ao.services import (
    VERDICT_ANOMALIE, VERDICT_ECHEC, VERDICT_SUCCES, collecter,
    collecter_toutes_les_sources,
)

MODULE_DIR = pathlib.Path(__file__).resolve().parents[1]


def _lignes(*objets):
    """Fabrique un lecteur qui rend ces avis, sans aucun réseau."""
    lignes = [
        {'ref_consultation': str(i + 1), 'org_acronyme': 'ORG',
         'objet': objet, 'acheteur': 'Commune de Test'}
        for i, objet in enumerate(objets)
    ]

    def lecteur(source, mots_cles):
        return lignes

    return lecteur


class CollecteTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name='Taqinor Test')
        self.source = SourceVeille.objects.create(
            company=self.company, code='pmmp', libelle='Portail test',
            type_source=TypeSource.PORTAIL_OFFICIEL,
            url_base='https://exemple.test/', actif=True)
        self.mot = MotCleVeille.objects.create(
            company=self.company, libelle='solaire',
            niveau=NiveauMotCle.NOYAU, poids=10, actif=True)

    # ── Idempotence ──────────────────────────────────────────────────────
    def test_collecte_rejouee_ne_cree_aucun_doublon(self):
        lecteur = _lignes('Pompage solaire à Figuig', 'Lot solaire Chichaoua')

        premier = collecter(self.source, self.company, lecteur=lecteur)
        second = collecter(self.source, self.company, lecteur=lecteur)

        self.assertEqual(premier['nouveaux'], 2)
        self.assertEqual(second['nouveaux'], 0)
        self.assertEqual(second['mis_a_jour'], 2)
        self.assertEqual(
            AvisMarche.objects.filter(company=self.company).count(), 2)

    def test_la_source_horodate_sa_derniere_collecte_reussie(self):
        self.assertIsNone(self.source.derniere_collecte_reussie)
        collecter(self.source, self.company,
                  lecteur=_lignes('Pompage solaire'))
        self.source.refresh_from_db()
        self.assertIsNotNone(self.source.derniere_collecte_reussie)
        self.assertLessEqual(self.source.derniere_collecte_reussie,
                             timezone.now())

    # ── Le scoring et les mots-clés ──────────────────────────────────────
    def test_un_mot_cle_desactive_n_est_plus_interroge(self):
        self.mot.actif = False
        self.mot.save(update_fields=['actif'])

        rapport = collecter(self.source, self.company,
                            lecteur=_lignes('Pompage solaire'))

        self.assertEqual(rapport['verdict'], VERDICT_ECHEC)
        self.assertEqual(rapport['mots_cles'], [])
        self.assertIn('mot-clé', rapport['message'])
        self.assertEqual(AvisMarche.objects.count(), 0)

    def test_le_score_et_les_mots_declencheurs_sont_ecrits(self):
        collecter(self.source, self.company,
                  lecteur=_lignes('Pompage solaire à Figuig'))
        avis = AvisMarche.objects.get()
        self.assertEqual(avis.score, 10)
        self.assertEqual(avis.mots_cles_declenches, ['solaire'])

    # ── Les règles d'exclusion (VAO10) ───────────────────────────────────
    def test_une_regle_active_auto_ignore_et_laisse_sa_trace(self):
        regle = RegleExclusion.objects.create(
            company=self.company, portee=PorteeExclusion.ACHETEUR,
            valeur='Commune de Test', motif='Hors périmètre', actif=True)

        rapport = collecter(self.source, self.company,
                            lecteur=_lignes('Pompage solaire'))

        self.assertEqual(rapport['auto_ignores'], 1)
        avis = AvisMarche.objects.get()
        self.assertEqual(avis.statut, StatutAvis.IGNORE)
        self.assertEqual(avis.regle_exclusion_id, regle.pk)

    # ── Robustesse : un avis fautif ne perd pas la collecte ──────────────
    def test_un_avis_fautif_est_journalise_et_les_autres_passent(self):
        def lecteur(source, mots_cles):
            return [
                {'ref_consultation': '1', 'objet': 'Pompage solaire'},
                # ``categorie`` hors des choix + valeur trop longue pour la
                # colonne : l'écriture de CETTE ligne échoue, pas la collecte.
                {'ref_consultation': '2', 'objet': 'Autre',
                 'acheteur': 'x' * 5000},
                {'ref_consultation': '3', 'objet': 'Luminaires solaires'},
            ]

        rapport = collecter(self.source, self.company, lecteur=lecteur)

        self.assertEqual(rapport['examines'], 3)
        self.assertEqual(rapport['nouveaux'], 2)
        self.assertEqual(len(rapport['erreurs']), 1)
        self.assertEqual(rapport['verdict'], VERDICT_ANOMALIE)

    # ── Échouer FRANC, jamais « 0 résultat » en silence ──────────────────
    def test_une_source_inactive_n_est_jamais_interrogee(self):
        self.source.actif = False
        self.source.save(update_fields=['actif'])
        appels = []

        def lecteur(source, mots_cles):
            appels.append(source)
            return []

        rapport = collecter(self.source, self.company, lecteur=lecteur)

        self.assertEqual(appels, [])
        self.assertEqual(rapport['verdict'], VERDICT_ECHEC)

    def test_une_panne_de_lecteur_est_un_echec_pas_un_zero_resultat(self):
        def lecteur(source, mots_cles):
            raise RuntimeError('portail injoignable')

        rapport = collecter(self.source, self.company, lecteur=lecteur)

        self.assertEqual(rapport['verdict'], VERDICT_ECHEC)
        self.assertEqual(rapport['examines'], 0)
        self.assertIn('portail injoignable', rapport['message'])

    def test_zero_nouveaute_reste_un_SUCCES(self):
        rapport = collecter(self.source, self.company,
                            lecteur=lambda s, m: [])
        self.assertEqual(rapport['verdict'], VERDICT_SUCCES)
        self.assertEqual(rapport['nouveaux'], 0)

    def test_sans_lecteur_branche_la_collecte_echoue_explicitement(self):
        rapport = collecter(self.source, self.company)
        self.assertEqual(rapport['verdict'], VERDICT_ECHEC)
        self.assertIn('collecteur', rapport['message'].lower())

    # ── Toutes les sources ───────────────────────────────────────────────
    def test_collecter_toutes_ignore_les_portes_humaines_et_les_inactives(self):
        SourceVeille.objects.create(
            company=self.company, code='tuyau', libelle='Tuyau partenaire',
            type_source=TypeSource.TUYAU_PARTENAIRE, actif=True)
        SourceVeille.objects.create(
            company=self.company, code='dormante', libelle='Dormante',
            type_source=TypeSource.AGREGATEUR,
            url_base='https://dormante.test/', actif=False)

        rapports = collecter_toutes_les_sources(
            self.company, lecteur=_lignes('Pompage solaire'))

        self.assertEqual([r['source_id'] for r in rapports], [self.source.pk])

    def test_isolation_multi_tenant_la_collecte_n_ecrit_que_sa_societe(self):
        autre = Company.objects.create(name='Autre société')
        collecter(self.source, self.company,
                  lecteur=_lignes('Pompage solaire'))
        self.assertEqual(
            AvisMarche.objects.filter(company=autre).count(), 0)
        self.assertEqual(
            AvisMarche.objects.filter(company=self.company).count(), 1)


class RegistreDeLecteursTests(TestCase):
    """Le registre est la PRISE du futur collecteur portail — pas un ``if``."""

    def setUp(self):
        self.company = Company.objects.create(name='Taqinor Registre')
        self.source = SourceVeille.objects.create(
            company=self.company, code='pmmp', libelle='Portail test',
            type_source=TypeSource.PORTAIL_OFFICIEL,
            url_base='https://exemple.test/', actif=True)

    def tearDown(self):
        retirer_lecteur(TypeSource.PORTAIL_OFFICIEL)

    def test_une_porte_humaine_ne_se_collecte_pas(self):
        humaine = SourceVeille.objects.create(
            company=self.company, code='tuyau', libelle='Tuyau',
            type_source=TypeSource.TUYAU_PARTENAIRE, actif=True)
        with self.assertRaises(LecteurIndisponible):
            lecteur_pour(humaine)

    def test_un_lecteur_branche_est_utilise_sans_toucher_au_service(self):
        MotCleVeille.objects.create(
            company=self.company, libelle='solaire',
            niveau=NiveauMotCle.NOYAU, poids=10, actif=True)
        enregistrer_lecteur(
            TypeSource.PORTAIL_OFFICIEL, _lignes('Pompage solaire'))

        rapport = collecter(self.source, self.company)

        self.assertEqual(rapport['verdict'], VERDICT_SUCCES)
        self.assertEqual(rapport['nouveaux'], 1)


class AucunReseauDansLeModuleTests(SimpleTestCase):
    """Règle #5 — le collecteur portail est GATÉ : rien ne parle au réseau.

    Garde mécanique (AST), pas une garde de revue : elle balaie tout le module
    hors ``portail/`` (qui n'existe pas encore et naîtra sous gate) et refuse
    tout import de client HTTP.
    """

    CLIENTS_HTTP = {'httpx', 'requests', 'urllib', 'urllib3', 'http',
                    'aiohttp', 'socket'}

    def test_aucun_client_http_importe_dans_le_module(self):
        fautifs = []
        for chemin in sorted(MODULE_DIR.rglob('*.py')):
            relatif = chemin.relative_to(MODULE_DIR).as_posix()
            if relatif.startswith(('migrations/', 'tests/', 'portail/')):
                continue
            arbre = ast.parse(chemin.read_text(encoding='utf-8'))
            for noeud in ast.walk(arbre):
                racines = []
                if isinstance(noeud, ast.Import):
                    racines = [a.name.split('.')[0] for a in noeud.names]
                elif isinstance(noeud, ast.ImportFrom):
                    racines = [(noeud.module or '').split('.')[0]]
                if any(r in self.CLIENTS_HTTP for r in racines):
                    fautifs.append(f'{relatif}:{noeud.lineno}')
        self.assertEqual(
            fautifs, [],
            'Le réseau appartient au collecteur GATÉ (VAO15-VAO20), jamais à '
            f'l\'orchestration : {fautifs}')

    def test_aucune_url_de_portail_en_dur_hors_de_la_table(self):
        """VAO7 — les URL vivent dans ``SourceVeille``, pas dans le code."""
        fautifs = []
        for chemin in sorted(MODULE_DIR.rglob('*.py')):
            relatif = chemin.relative_to(MODULE_DIR).as_posix()
            if relatif.startswith(('migrations/', 'tests/')):
                continue
            texte = chemin.read_text(encoding='utf-8')
            if 'marchespublics' in texte or 'gov.ma' in texte:
                fautifs.append(relatif)
        self.assertEqual(fautifs, [], fautifs)
