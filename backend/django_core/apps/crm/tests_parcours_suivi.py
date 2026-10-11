"""SUIVI-PARCOURS (30/09/2026) — LA GARDE DE PARCOURS du suivi commercial.

Ordre fondateur (Reda, 30/09/2026) : « test very well all the steps by yourself or make a
testing script that we can reuse afterward ». Les blocages subis étaient des CHAÎNES — une
étape, une réponse, l'étape suivante… — qu'aucun test ne parcourait.

La source de vérité est la table ``frontend/src/features/crm/relances/parcours_suivi.json``
(18 types d'étape, leurs réponses, ce que chacune envoie et la suite attendue), lue par
``parcours_suivi_outils`` — jamais recopiée. Elle décrit le comportement CIBLE (spec moteur du
30/09/2026 : réponses ``perdu``/``visite_abandonnee``/``joint_telephone``, planification qui
clôt la touche, ``prochaine_touche`` nommée, refus 400 d'une touche déjà traitée…) : ce
fichier est écrit contre ELLE, jamais affaibli pour coller au code du moment.

COMMENT LA RELANCER. La CI la joue à chaque merge (job ``backend-tests``). En local, sur un
poste avec docker : ``powershell -File scripts/test-backend.ps1 -Modules
"apps.crm.tests_parcours_suivi"`` (les tests sans base seuls : ``manage.py test
apps.crm.tests_parcours_suivi.TableParcoursTests``). Un échec imprime le CHEMIN complet du
cas (lead → étape → réponse → …) pour le rejouer à la main. La marche au hasard est
rejouable (graine fixe) ; ``PARCOURS_GRAINE=<entier>`` dans l'environnement en tire une autre.

Quatre étages :

1. ``TableParcoursTests`` — la table est saine (``SimpleTestCase``, sans base) ;
2. ``ChaqueReponseTests`` — chaque réponse de chaque étape (chaque variante, chaque « date pas
   encore fixée ») jouée par l'API réelle sur un lead neuf amené par un chemin réel, sa suite
   constatée en base, les invariants vérifiés après CHAQUE geste ;
3. ``ParcoursCompletsTests`` — des histoires de bout en bout, a → h ;
4. ``ParcoursAleatoiresTests`` — la marche au hasard, REJOUABLE (graine fixe), invariants
   seulement ; un échec imprime le chemin complet (étape → réponse → …).

Les invariants (``ParcoursBase.verifier_invariants``) : I1 jamais de 5xx, un refus porte
``erreurs`` ; I2 un lead actif a au moins une touche ouverte ; I3 jamais deux touches ouvertes
de même clé (ou libellé) ; I4 au plus un barreau ouvert par cadence réactive ; I5 chaque touche
ouverte sert une suite pour chaque réponse de son type, chaque code ayant sa phrase ; I6
``relance_date`` = la plus proche touche ouverte ; I7 ``prochaine_touche`` la désigne.

Horloge gelée : mercredi 30/09/2026, 10 h à Casablanca ; elle n'avance que par des blocs
``frozen(...)`` imbriqués.
"""
import datetime
import os
import random

from django.test import SimpleTestCase

from apps.crm import cadence_config, horaires, stages, cadence_reperes
from apps.crm.cadence_config import cle_de
from apps.crm.models import LeadActivity, MotifPerte, RelanceEtape
from apps.crm.parcours_suivi_outils import (
    CADENCE_DU_TYPE, CHEMINS, CHEMINS_SPECIAUX, CLES_RENDEZ_VOUS, CONTEXTES_VARIANTE,
    ETATS_FIN, FAMILLES, GESTES_PLANIFICATION, JOURS, MOTIF_COMMERCIAL, ORDRE_AMENE,
    REPONSES_SPEC, TYPES_SUIVI, ParcoursBase, cas_de_la_famille, etapes_de_la_table,
    reponse_de, reponses, reponses_appel, table, type_de)
from apps.parametres import models_relance
from apps.parametres.models_relance import (
    CADENCES_DEFAUT, CLE_CONFIRMATION, CLE_DEBRIEF, CLE_DEVIS, CLE_PLANIFIER, Cadence)
from apps.visites.selectors import visites_pour_lead

A_FAIRE = RelanceEtape.Statut.A_FAIRE


def _cles_du_moteur():
    """Les clés ``CLE_*`` du gabarit de Paramètres (``models_relance``)."""
    return {valeur for nom, valeur in vars(models_relance).items()
            if nom.startswith('CLE_') and isinstance(valeur, str)}


# ── 1. La table est saine ──────────────────────────────────────────────────────────────────

class TableParcoursTests(SimpleTestCase):
    """La table ``parcours_suivi.json`` est saine — et la garde la couvre tout entière."""

    def _toutes_les_suites(self):
        for etape in table()['etapes']:
            for reponse in reponses(etape):
                yield etape, reponse, 'suite', reponse.get('suite')
                if 'suite_sans_date' in reponse:
                    yield etape, reponse, 'suite_sans_date', reponse['suite_sans_date']
                for variante in reponse.get('variantes', ()):
                    yield (etape, reponse, f'variante {variante.get("contexte")}',
                           variante.get('suite'))
            for reponse in reponses_appel(etape):
                if 'suite' in reponse:
                    yield etape, reponse, 'suite (appel)', reponse['suite']
                    for variante in reponse.get('variantes', ()):
                        yield (etape, reponse, f'variante {variante.get("contexte")}',
                               variante.get('suite'))

    def test_chaque_reponse_reference_un_modele_et_porte_effet_et_suite(self):
        modeles = table()['modeles']
        for etape in table()['etapes']:
            for brute in etape['reponses']:
                with self.subTest(etape=etape['id'], modele=brute.get('modele')):
                    self.assertIn(brute.get('modele'), modeles, 'modèle inconnu')
                    reponse = {**modeles[brute['modele']], **brute}
                    self.assertTrue((reponse.get('label') or '').strip(), 'libellé vide')
                    self.assertTrue((reponse.get('effet') or '').strip(), 'effet vide')
                    self.assertIsInstance(reponse.get('suite'), dict, 'suite absente')

    def test_chaque_suite_est_une_suite_de_la_legende(self):
        legende = set(table()['legende_suite'])
        ids = set(etapes_de_la_table())
        for etape, reponse, ou, suite in self._toutes_les_suites():
            with self.subTest(etape=etape['id'], reponse=reponse['modele'], ou=ou):
                self.assertIsInstance(suite, dict)
                self.assertIn(suite.get('type'), legende)
                if 'jour' in suite:
                    self.assertIn(suite['jour'], JOURS)
                if suite['type'] == 'etape':
                    self.assertEqual(('cle' in suite) + ('id_etape' in suite), 1,
                                     'une étape se désigne par sa clé OU son type')
                    if 'id_etape' in suite:
                        self.assertIn(suite['id_etape'], ids)
                if suite['type'] == 'reprise_ou':
                    self.assertIn('cle', suite)
                if suite['type'] == 'fin':
                    self.assertIn(suite.get('etat'), ETATS_FIN)

    def test_chaque_cle_nommee_est_une_cle_du_moteur(self):
        cles = _cles_du_moteur()
        for etape, reponse, ou, suite in self._toutes_les_suites():
            if 'cle' in suite:
                with self.subTest(etape=etape['id'], reponse=reponse['modele'], ou=ou):
                    self.assertIn(suite['cle'], cles)
        for etape in table()['etapes']:
            with self.subTest(reconnaissance=etape['id']):
                self.assertLessEqual(set(etape['reconnaissance'].get('cles', ())), cles)

    def test_les_variantes_ont_un_contexte_que_la_garde_sait_construire(self):
        for etape in table()['etapes']:
            for reponse in reponses(etape):
                for variante in reponse.get('variantes', ()):
                    contexte = variante.get('contexte')
                    with self.subTest(etape=etape['id'], reponse=reponse['modele'],
                                      contexte=contexte):
                        self.assertIn(contexte, CONTEXTES_VARIANTE)
                        if contexte == 'derniere_touche':
                            # Un barreau de protocole : la garde en fait la dernière touche
                            # par le gabarit de la société.
                            self.assertIn(etape['id'], ORDRE_AMENE)
                        if contexte == 'perdu_junk':
                            self.assertTrue(reponse.get('junk'), 'aucun motif junk nommé')

    def test_aucun_libelle_ni_modele_en_double_dans_une_etape(self):
        for etape in table()['etapes']:
            with self.subTest(etape=etape['id']):
                libelles = [r['label'] for r in reponses(etape)]
                self.assertEqual(len(libelles), len(set(libelles)), libelles)
                modeles = [r['modele'] for r in etape['reponses']]
                self.assertEqual(len(modeles), len(set(modeles)), modeles)

    def test_chaque_envoi_est_connu_de_la_spec(self):
        issues = {cle for cle, _libelle in LeadActivity.OUTCOMES}
        for etape in table()['etapes']:
            for reponse in reponses(etape):
                with self.subTest(etape=etape['id'], reponse=reponse['modele']):
                    if 'reponse' in reponse:
                        self.assertIn(reponse['reponse'], REPONSES_SPEC)
                    if 'outcome' in reponse:
                        self.assertIn(reponse['outcome'], issues)
                    if 'geste' in reponse:
                        self.assertIn(reponse['geste'], GESTES_PLANIFICATION)
                    self.assertTrue({'reponse', 'outcome', 'geste'} & set(reponse),
                                    'la réponse n’envoie rien')
            for entree in etape.get('reponses_appel', ()):
                modele = entree['modele'] if isinstance(entree, dict) else entree
                with self.subTest(etape=etape['id'], reponse_appel=modele):
                    self.assertIn(modele, table()['modeles'])
                    if isinstance(entree, dict):
                        self.assertTrue((entree.get('effet') or '').strip(), 'effet vide')
                        self.assertIsInstance(entree.get('suite'), dict, 'suite absente')

    def test_chaque_type_a_une_reconnaissance_exploitable_sans_chevauchement(self):
        canaux = {valeur for valeur, _libelle in RelanceEtape.Canal.choices}
        cadences = {valeur for valeur, _libelle in Cadence.choices}
        par_cle, par_libelle, par_couple = {}, {}, {}
        for etape in table()['etapes']:
            reco = etape['reconnaissance']
            with self.subTest(etape=etape['id']):
                self.assertTrue(reco.get('cles') or reco.get('libelles') or reco.get('cadences'),
                                'reconnaissance vide')
                self.assertLessEqual(set(reco.get('cadences', ())), cadences)
                self.assertLessEqual(set(reco.get('canaux', ())), canaux)
                for cle in reco.get('cles', ()):
                    self.assertNotIn(cle, par_cle, f'clé « {cle} » dans deux types')
                    par_cle[cle] = etape['id']
                for libelle in reco.get('libelles', ()):
                    self.assertNotIn(libelle, par_libelle, f'libellé « {libelle} » en double')
                    par_libelle[libelle] = etape['id']
                for cadence in reco.get('cadences', ()):
                    for canal in (reco.get('canaux') or sorted(canaux)):
                        self.assertNotIn((cadence, canal), par_couple,
                                         f'({cadence}, {canal}) dans deux types')
                        par_couple[(cadence, canal)] = etape['id']

    def test_les_libelles_reconnus_sont_ceux_que_le_moteur_pose(self):
        # Une reconnaissance par libellé qui diverge du libellé réellement posé ne
        # reconnaîtrait plus rien : dérive gardée ici.
        defauts = {entree['cle']: entree['libelle']
                   for cadence in (Cadence.APRES_CONTACT, Cadence.VISITE)
                   for entree in CADENCES_DEFAUT[cadence]}
        for etape in table()['etapes']:
            reco = etape['reconnaissance']
            permis = {defauts[cle] for cle in reco.get('cles', ()) if cle in defauts}
            if CLE_DEVIS in reco.get('cles', ()):
                permis.add(cadence_config.LIBELLE_DEVIS_ANCIEN)
            if not reco.get('cles'):
                permis.add(cadence_reperes.QUESTION_PRIX_LIBELLE)
            for libelle in reco.get('libelles', ()):
                with self.subTest(etape=etape['id'], libelle=libelle):
                    self.assertIn(libelle, permis)

    def test_l_oracle_reconnait_chaque_type_dans_l_ordre_de_la_table(self):
        for etape in table()['etapes']:
            reco = etape['reconnaissance']
            exemples = []
            for cle in reco.get('cles', ()):
                # Une clé l'emporte sur la cadence (une étape du moteur vit en `generique`
                # ou en `apres_devis` sans être un barreau).
                exemples.append(RelanceEtape(cle=cle, libelle='', cadence='generique',
                                             canal='appel'))
            for libelle in reco.get('libelles', ()):
                exemples.append(RelanceEtape(cle='', libelle=libelle, cadence='generique',
                                             canal='appel'))
            for cadence in reco.get('cadences', ()):
                for canal in (reco.get('canaux') or ['appel']):
                    exemples.append(RelanceEtape(cle='', libelle='', cadence=cadence,
                                                 canal=canal))
            for exemple in exemples:
                with self.subTest(etape=etape['id'], cle=exemple.cle, libelle=exemple.libelle,
                                  cadence=exemple.cadence, canal=exemple.canal):
                    self.assertEqual(type_de(exemple), etape['id'])

    def test_chaque_famille_et_chaque_type_ont_leur_garde(self):
        familles = {etape['famille'] for etape in table()['etapes']}
        self.assertEqual(familles, set(FAMILLES), 'une famille sans test (ou l’inverse)')
        for suffixe in FAMILLES.values():
            self.assertTrue(callable(getattr(ChaqueReponseTests, f'test_{suffixe}', None)),
                            f'ChaqueReponseTests.test_{suffixe} manque')
        ids = set(etapes_de_la_table())
        self.assertEqual(set(CHEMINS) | CHEMINS_SPECIAUX, ids, 'un type sans chemin « amener »')
        self.assertFalse(set(CHEMINS) & CHEMINS_SPECIAUX)
        for type_id, (parent, modele, _options) in CHEMINS.items():
            with self.subTest(chemin=type_id):
                self.assertIn(parent, ids)
                self.assertTrue(reponse_de(parent, modele))
        for type_id in ORDRE_AMENE:
            self.assertIn(type_id, ids)
            self.assertIn(CADENCE_DU_TYPE[type_id], {c for c, _l in Cadence.choices})
        total = sum(len(cas_de_la_famille(famille)) for famille in FAMILLES)
        self.assertGreater(total, 100, 'la table ne produit presque aucun cas')

    def test_agr533_variantes_segment_ne_changent_que_la_lecture(self):
        """AGR533 — une ``variantes_segment`` (modèle, entrée d'étape, geste)
        ne remplace que ``label`` / ``precision`` / ``effet`` : jamais la clé
        serveur (``reponse``), l'issue ni la suite."""
        from apps.crm.parcours_suivi_outils import refus_variantes_segment
        t = table()
        objets = list(t['modeles'].values()) + list(t['gestes'])
        for etape in t['etapes']:
            objets += etape['reponses']
            objets += [e for e in etape.get('reponses_appel', ()) if isinstance(e, dict)]
        porteurs = [o for o in objets if o.get('variantes_segment')]
        self.assertTrue(porteurs)  # anti-faux-vert : la table en porte
        for objet in porteurs:
            with self.subTest(objet=objet.get('label')):
                self.assertEqual(refus_variantes_segment(objet), [])
        self.assertEqual(
            t['modeles']['decision_famille']['variantes_segment']['agricole']['label'],
            'Décision à plusieurs — associés / coopérative')
        # La garde REFUSE une variante qui changerait la clé serveur ou la suite.
        self.assertTrue(refus_variantes_segment(
            {'variantes_segment': {'agricole': {'reponse': 'plus_tard'}}}))
        self.assertTrue(refus_variantes_segment(
            {'variantes_segment': {'agricole': {'label': 'x', 'suite': {'type': 'fin'}}}}))


# ── 2. Chaque réponse de chaque étape ──────────────────────────────────────────────────────

def _famille(suffixe):
    return next(nom for nom, s in FAMILLES.items() if s == suffixe)


class ChaqueReponseTests(ParcoursBase):
    """Pour CHAQUE type d'étape et CHAQUE réponse de la table (chaque variante, chaque « date
    pas encore fixée ») : lead neuf → ``amener`` → la réponse → HTTP 2xx → la suite de la
    table constatée (``verifier_suite``) → les invariants. Un ``subTest`` par cas ; un test par
    famille de la table."""

    slug = 'parcours-reponses'

    def test_prise_de_contact(self):
        self.jouer_famille(_famille('prise_de_contact'))

    def test_apres_l_appel(self):
        self.jouer_famille(_famille('apres_l_appel'))

    def test_suivi_de_proposition(self):
        self.jouer_famille(_famille('suivi_de_proposition'))

    def test_visite(self):
        self.jouer_famille(_famille('visite'))

    def test_reveil(self):
        self.jouer_famille(_famille('reveil'))

    def test_autres(self):
        self.jouer_famille(_famille('autres'))


# ── 3. Les parcours complets ───────────────────────────────────────────────────────────────

class ParcoursCompletsTests(ParcoursBase):
    """Les histoires de bout en bout, chacune lisible comme un dossier réel."""

    slug = 'parcours-histoires'

    def _suivi_unique(self, lead):
        suivis = self.suivis_ouverts(lead)
        self.assertEqual(len(suivis), 1, self.msg('un (seul) barreau du suivi ouvert', lead))
        return suivis[0]

    def _etapes_de_cle(self, lead, *cles):
        return [e for e in self.ouvertes(lead) if cle_de(e) in cles]

    def test_saisies_humaines_rattrapees_depuis_le_journal(self):
        """AMET23 — le rattrapage marque la clé d'une modification journalisée AVEC
        utilisateur, jamais celle d'un champ touché par le seul système ; idempotent ;
        ``ecrire_si_libre`` refuse ensuite d'écraser (primitive AMET22)."""
        import importlib

        from django.apps import apps as django_apps

        from apps.crm.models import Lead
        from apps.records.provenance import ecrire_si_libre
        migration = importlib.import_module(
            'apps.crm.migrations.0133_amet23_lead_saisies_humaines')
        lead = Lead.objects.create(company=self.company, nom='Provenance')
        self.assertEqual(lead.saisies_humaines, [])
        LeadActivity.objects.create(
            company=self.company, lead=lead, kind='modification', field='whatsapp',
            old_value='0661000000', new_value='', user=self.acteur)
        LeadActivity.objects.create(
            company=self.company, lead=lead, kind='modification', field='ville',
            old_value='', new_value='Fès', user=None)
        migration.rattraper_saisies_humaines(django_apps, None)
        lead.refresh_from_db()
        self.assertEqual(lead.saisies_humaines, ['whatsapp'])
        migration.rattraper_saisies_humaines(django_apps, None)
        lead.refresh_from_db()
        self.assertEqual(lead.saisies_humaines, ['whatsapp'], 'rattrapage idempotent')
        self.assertFalse(ecrire_si_libre(lead, 'whatsapp', '0662000000', journal=False))
        self.assertTrue(ecrire_si_libre(lead, 'ville', 'Fès', journal=False))

    def _lead_relance_saisie(self, jour, touches):
        """Lead à ``relance_date`` saisie à la main + ses touches de contact
        ``[(ordre, jour, statut)]``."""
        from apps.crm.models import Lead
        lead = Lead.objects.create(
            company=self.company, nom='Relance saisie', owner=self.acteur,
            relance_date=jour, saisies_humaines=['relance_date'])
        for ordre, quand, statut in touches:
            RelanceEtape.objects.create(
                company=self.company, lead=lead, cadence='contact', ordre=ordre,
                due_date=quand, canal=RelanceEtape.Canal.APPEL, statut=statut)
        return lead

    def _recaler(self, lead):
        from apps.crm.cadence_plan import _recaler_file
        _recaler_file(lead, self.acteur)
        lead.refresh_from_db()
        return lead

    def test_relance_saisie_a_venir_gardee(self):
        """AMET20 (décision fondateur 11/10) — une date saisie À VENIR dont la
        touche est ouverte prime : le moteur ne la déplace pas."""
        j5, j2 = self.jour_ouvre(5), self.jour_ouvre(2)
        lead = self._recaler(self._lead_relance_saisie(
            j5, [(1, j2, A_FAIRE), (2, j5, A_FAIRE)]))
        self.assertEqual(lead.relance_date, j5)
        self.assertIn('relance_date', lead.saisies_humaines)

    def test_relance_saisie_passee_le_moteur_reprend(self):
        """AMET20 — la date saisie est passée : le moteur la déplace sur la
        prochaine touche ouverte et elle n'est plus une saisie humaine."""
        passee = self.aujourdhui() - datetime.timedelta(days=3)
        j2 = self.jour_ouvre(2)
        lead = self._recaler(self._lead_relance_saisie(passee, [(1, j2, A_FAIRE)]))
        self.assertEqual(lead.relance_date, j2)
        self.assertNotIn('relance_date', lead.saisies_humaines)

    def test_relance_saisie_touche_close_le_moteur_reprend(self):
        """AMET20 — la touche couverte par la date saisie est close : le moteur
        reprend la main."""
        j5, j7 = self.jour_ouvre(5), self.jour_ouvre(7)
        lead = self._recaler(self._lead_relance_saisie(
            j5, [(1, j5, RelanceEtape.Statut.FAIT), (2, j7, A_FAIRE)]))
        self.assertEqual(lead.relance_date, j7)
        self.assertNotIn('relance_date', lead.saisies_humaines)

    def test_fusion_garde_un_zero_saisi(self):
        """AMET21 — ``merge_leads`` : un 0 saisi du survivant survit (ACRM13), une clé de
        ``saisies_humaines`` du survivant n'est jamais remplacée (même vidée à la main), un
        champ réellement vide et non saisi prend la valeur du doublon."""
        from apps.crm.leads_fusion import merge_leads
        from apps.crm.models import Lead
        survivant = Lead.objects.create(
            company=self.company, nom='Survivant', owner=self.acteur, nb_etages=0,
            ville='', saisies_humaines=['nb_etages', 'ville'])
        doublon = Lead.objects.create(
            company=self.company, nom='Doublon', owner=self.acteur, nb_etages=2,
            ville='Fès', email='doublon.amet21@example.com')
        merge_leads(survivant, [doublon], self.acteur)
        survivant = Lead.objects.get(pk=survivant.pk)
        self.assertEqual(survivant.nb_etages, 0)
        self.assertEqual(survivant.ville, '')
        self.assertEqual(survivant.email, 'doublon.amet21@example.com')
        self.assertFalse(LeadActivity.objects.filter(
            lead=survivant, user__isnull=True, field__in=('nb_etages', 'ville')).exists())

    def _moment(self, jour, heure):
        return datetime.datetime.combine(jour, heure, tzinfo=horaires.CASABLANCA)

    def test_a_message_appel_devis_envoye_depuis_l_erp_puis_accepte(self):
        """Message sans réponse → appel → client joint → étape devis (datée de DEMAIN, traitée
        le jour même : le devis part aujourd'hui depuis l'ERP et l'étape se ferme d'elle-même)
        → suivi de proposition → client joint → … → devis accepté → SIGNÉ, zéro touche.
        (« Fait » sur l'étape devis le jour même : histoire f.)"""
        lead, message = self.amener('contact_message')
        self.jouer(lead, message, 'pas_de_reponse')
        appel = self.unique(lead, 'contact_appel')
        self.jouer(lead, appel, 'joint')
        etape_devis = self.unique(lead, 'devis')
        self.assertEqual(etape_devis.due_date, self.demain(),
                         self.msg('l’étape devis est posée pour demain', lead))
        devis = self.envoyer_devis(lead)
        etape_devis.refresh_from_db()
        self.assertNotEqual(etape_devis.statut, A_FAIRE,
                            self.msg('l’étape devis ne s’est pas fermée d’elle-même', lead))
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.QUOTE_SENT)
        pdf = self.unique(lead, 'suivi_message')
        self.assertEqual(pdf.devis_id, devis.pk)
        self.jouer(lead, pdf, 'a_repondu')
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.FOLLOW_UP, self.msg('le dossier passe « Relance »'))
        appel_suivi = self.unique(lead, 'suivi_appel')
        self.jouer(lead, appel_suivi, 'joint')
        suivant = self._suivi_unique(lead)
        self.assertGreater(suivant.ordre, appel_suivi.ordre)
        self.appel('post', f'/api/django/ventes/devis/{devis.pk}/accepter/', {
            'nom': 'Client parcours', 'date': self.aujourdhui().isoformat(),
            'option': 'sans_batterie'})
        self._journal(f'[{self.aujourdhui():%d/%m}] devis {devis.reference} accepté')
        self.verifier_invariants(lead)
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.SIGNED, self.msg('le lead n’est pas signé', lead))
        self.assertEqual(self.ouvertes(lead), [], self.msg('une relance survit au devis signé', lead))

    def test_b_visite_confirmee_retour_terrain_puis_devis_envoye(self):
        """Appel → visite acceptée + date → confirmation → « Confirmé » → retour de visite →
        étape devis → devis envoyé depuis l'ERP → suivi démarré, étape devis fermée."""
        lead, appel = self.amener('contact_appel')
        date = self.jour_ouvre(5)
        self.jouer(lead, appel, 'visite', date=date)
        confirmation = self.unique(lead, 'confirmation')
        debrief = self.unique(lead, 'debrief')
        self.jouer(lead, confirmation, 'joint')
        debrief.refresh_from_db()
        self.assertEqual(debrief.statut, A_FAIRE, self.msg('le débrief attend la visite', lead))
        self.avancer_a(self._moment(date, datetime.time(16, 0)))
        self.retour_de_visite(lead)
        etape_devis = self.unique(lead, 'devis')
        self.assertEqual(etape_devis.due_date, self.demain())
        devis = self.envoyer_devis(lead)
        etape_devis.refresh_from_db()
        self.assertNotEqual(etape_devis.statut, A_FAIRE)
        suivi = self.unique(lead, 'suivi_message')
        self.assertEqual(suivi.devis_id, devis.pk)
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.QUOTE_SENT)

    def test_b_constat_e1_devis_envoye_pendant_que_la_visite_est_ouverte(self):
        """Constat E1 : un devis envoyé ALORS QUE la confirmation et le débrief sont ouverts
        démarre quand même le suivi (barreau 1, daté de l'envoi) ; les étapes de visite
        restent. Puis « Confirmé », le retour terrain cale le débrief (un devis est parti), et
        « client joint après la visite » laisse le suivi reprendre — sans étape devis."""
        lead, appel = self.amener('contact_appel')
        date = self.jour_ouvre(5)
        self.jouer(lead, appel, 'visite', date=date)
        confirmation = self.unique(lead, 'confirmation')
        debrief = self.unique(lead, 'debrief')
        devis = self.envoyer_devis(lead)
        suivi = self.unique(lead, 'suivi_message')
        self.assertEqual(suivi.devis_id, devis.pk)
        self.assertEqual(suivi.due_date, self.demain(), self.msg('barreau 1 daté de l’envoi', lead))
        for etape in (confirmation, debrief):
            etape.refresh_from_db()
            self.assertEqual(etape.statut, A_FAIRE,
                             self.msg(f'« {etape.libelle} » ne doit pas disparaître', lead))
        self.jouer(lead, confirmation, 'joint')
        self.avancer_a(self._moment(date, datetime.time(16, 0)))
        self.retour_de_visite(lead)
        debrief.refresh_from_db()
        self.assertEqual(debrief.statut, A_FAIRE, self.msg('le débrief reste à faire', lead))
        self.assertEqual(debrief.due_date, self.demain(), self.msg('débrief calé sur le retour'))
        self.jouer(lead, debrief, 'joint')
        self.assertTrue(self.suivis_ouverts(lead), self.msg('le suivi ne reprend pas', lead))
        self.assertFalse(self._etapes_de_cle(lead, CLE_DEVIS),
                         self.msg('une étape devis est posée malgré le devis envoyé', lead))

    def test_c_visite_sans_date_planifier_sans_reponse_puis_date_calee(self):
        """Appel → visite acceptée SANS date → « Planifier la visite » → sans réponse →
        reposée DEMAIN → date calée : jamais deux étapes « planifier » ouvertes."""
        lead, appel = self.amener('contact_appel')
        self.jouer(lead, appel, 'visite', sans_date=True)
        planifier = self.unique(lead, 'planifier')
        self.assertEqual(planifier.due_date, self.aujourdhui())
        self.jouer(lead, planifier, 'sans_reponse')
        planifier.refresh_from_db()
        self.assertNotEqual(planifier.statut, A_FAIRE, self.msg('l’appel sans réponse compte'))
        reposee = self.unique(lead, 'planifier')
        self.assertNotEqual(reposee.pk, planifier.pk)
        self.assertEqual(reposee.due_date, self.demain(), self.msg('reposée pour demain', lead))
        self.avancer_a(reposee.due_at)
        date = self.jour_ouvre(5)
        self.jouer(lead, reposee, 'date_calee', date=date)
        self.assertFalse(self._etapes_de_cle(lead, CLE_PLANIFIER),
                         self.msg('une étape « planifier » survit à la date calée', lead))
        for cle in (CLE_CONFIRMATION, CLE_DEBRIEF):
            self.assertEqual(len(self._etapes_de_cle(lead, cle)), 1, self.msg(cle, lead))
        self.assertTrue(any(v['date_prevue'] == date.isoformat()
                            for v in visites_pour_lead(lead)))

    def test_d_onze_touches_sans_reponse_froid_puis_reveil_joint(self):
        """Onze touches sans réponse → Froid (« Injoignable ») + réveils J30/J60 → réveil J30
        « Client joint » → le dossier sort du Froid → étape devis."""
        lead, _message = self.amener('contact_message')
        self.touches_de_contact_sans_reponse(lead)
        lead.refresh_from_db()
        self.assertIn('Injoignable', lead.tags or '')
        self.assertEqual(sorted(type_de(e) for e in self.ouvertes(lead)),
                         ['reveil_appel', 'reveil_message'], self.msg('les deux réveils', lead))
        j30 = self.unique(lead, 'reveil_appel')
        self.avancer_a(j30.due_at)
        self.jouer(lead, j30, 'joint')
        lead.refresh_from_db()
        self.assertNotEqual(lead.stage, stages.COLD, self.msg('le dossier reste au Froid', lead))
        self.assertFalse([e for e in self.ouvertes(lead) if e.cadence == 'reveil'],
                         self.msg('un réveil survit au client joint', lead))
        self.unique(lead, 'devis')

    def test_e_refus_decider_la_suite_perdu_avec_motif(self):
        """Refus → « Décider la suite » → « Perdu — clore le dossier » avec son motif (refusé
        sans motif, ou avec un motif hors liste, ou par « Refus ») → lead perdu, zéro touche."""
        lead, appel = self.amener('contact_appel')
        self.jouer(lead, appel, 'refus')
        decider = self.unique(lead, 'decider_suite')
        self.assertEqual(decider.due_date, self.demain())
        url = f'/api/django/crm/relance-etapes/{decider.pk}/fait/'
        for corps, champ in (({'reponse': 'perdu'}, 'motif_perte'),
                             ({'reponse': 'perdu', 'motif_perte': 'Motif hors liste'},
                              'motif_perte'),
                             ({'outcome': 'refuse'}, 'outcome')):
            with self.subTest(refus=corps):
                resp = self.appel('post', url, corps, quatre_cents='attendu')
                self.assertIn(champ, resp.data['erreurs'], self.msg(f'refus nommé {resp.data}'))
                decider.refresh_from_db()
                self.assertEqual(decider.statut, A_FAIRE)
        self.verifier_invariants(lead)
        self.jouer(lead, decider, 'perdu', motif=MOTIF_COMMERCIAL)
        lead.refresh_from_db()
        self.assertTrue(lead.perdu)
        self.assertEqual(lead.motif_perte, MOTIF_COMMERCIAL)
        self.assertEqual(self.ouvertes(lead), [], self.msg('une relance survit au perdu', lead))

    def test_e_variante_relancer_plus_tard(self):
        """Refus → « Décider la suite » → « Relancer plus tard — le… » : la même étape,
        déplacée ; ce jour-là, « Le client revient — reprendre » pose l'étape devis."""
        lead, appel = self.amener('contact_appel')
        self.jouer(lead, appel, 'refus')
        decider = self.unique(lead, 'decider_suite')
        date = self.jour_ouvre(3)
        self.jouer(lead, decider, 'rappel', date=date)
        decider.refresh_from_db()
        self.assertEqual((decider.statut, decider.due_date), (A_FAIRE, date))
        self.assertEqual([e.pk for e in self.ouvertes(lead)], [decider.pk])
        self.avancer_a(decider.due_at)
        self.jouer(lead, decider, 'fait')
        self.unique(lead, 'devis')

    def test_f_devis_hors_erp_client_joint_question_de_prix_puis_reprise(self):
        """Devis parti hors ERP (« Devis envoyé — passer à la suite » le jour même, étape
        datée de demain) → suivi → « Client joint » : UNE seule touche ouverte (constat E6) →
        question de prix → décision prise → le suivi REPREND au barreau suivant, jamais
        « Le PDF s'ouvre bien ? » une seconde fois."""
        lead, etape_devis = self.amener('devis')
        self.assertEqual(etape_devis.due_date, self.demain())
        self.jouer(lead, etape_devis, 'fait')
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.QUOTE_SENT)
        pdf = self.unique(lead, 'suivi_message')
        self.assertIsNone(pdf.devis_id)
        self.jouer(lead, pdf, 'sans_reponse')
        appel = self.unique(lead, 'suivi_appel')
        self.jouer(lead, appel, 'joint')
        ouvertes = self.ouvertes(lead)
        self.assertEqual(len(ouvertes), 1, self.msg('E6 — UNE seule touche ouverte', lead))
        suivant = ouvertes[0]
        self.assertIn(type_de(suivant), TYPES_SUIVI)
        self.assertGreater(suivant.ordre, appel.ordre)
        self.jouer(lead, suivant, 'question_prix')
        question = self.unique(lead, 'question_prix')
        self.assertFalse(self.suivis_ouverts(lead), self.msg('le suivi est en pause', lead))
        self.jouer(lead, question, 'fait')
        reprise = self._suivi_unique(lead)
        self.assertGreater(reprise.ordre, suivant.ordre,
                           self.msg('le suivi a redémarré au lieu de reprendre', lead))
        self.assertEqual(lead.relance_etapes.filter(cadence='apres_devis',
                                                    ordre=pdf.ordre).count(), 1,
                         self.msg('« Le PDF s’ouvre bien ? » posé une seconde fois', lead))
        self.assertFalse(self._etapes_de_cle(lead, CLE_DEVIS))

    def test_g_rendez_vous_annule_le_suivi_continue(self):
        """Visite planifiée pendant le suivi, puis « Annule le rendez-vous » : la visite perd
        sa date, les étapes de visite sont retirées, le suivi de proposition continue."""
        lead, appel = self.amener('suivi_appel')
        self.jouer(lead, appel, 'visite', date=self.jour_ouvre(5))
        confirmation = self.unique(lead, 'confirmation')
        self.jouer(lead, confirmation, 'visite_abandonnee')
        lead.refresh_from_db()
        visites = visites_pour_lead(lead)
        self.assertTrue(visites)
        self.assertTrue(all(v['date_prevue'] is None for v in visites),
                        self.msg(f'la visite garde sa date ({visites})', lead))
        self.assertIsNone(lead.visite_prevue_le)
        self.assertFalse(self._etapes_de_cle(lead, *CLES_RENDEZ_VOUS),
                         self.msg('une étape de visite reste ouverte', lead))
        suivi = self._suivi_unique(lead)
        self.assertGreater(suivi.ordre, appel.ordre)
        self.assertFalse(self._etapes_de_cle(lead, CLE_DEVIS))

    def test_g_reportee_a_une_autre_date_une_seule_visite(self):
        """« Reportée à une autre date » : UNE seule visite, déplacée ; la confirmation (la
        même) et le débrief suivent la nouvelle date."""
        lead, confirmation = self.amener('confirmation')
        nouvelle = self.jour_ouvre(7)
        self.jouer(lead, confirmation, 'replanifier', date=nouvelle)
        visites = visites_pour_lead(lead)
        self.assertEqual([v['date_prevue'] for v in visites], [nouvelle.isoformat()],
                         self.msg(f'une seule visite, déplacée ({visites})', lead))
        lead.refresh_from_db()
        self.assertEqual(lead.visite_prevue_le, nouvelle)
        confirmation.refresh_from_db()
        self.assertEqual(confirmation.statut, A_FAIRE,
                         self.msg('la confirmation reste ouverte (veille de la nouvelle date)'))
        for cle in (CLE_CONFIRMATION, CLE_DEBRIEF):
            self.assertEqual(len(self._etapes_de_cle(lead, cle)), 1, self.msg(cle, lead))

    def test_h_double_clic_sur_une_touche_deja_traitee(self):
        """Double clic : rejouer « Fait » (et « Sauter », « Reporter ») sur une touche déjà
        traitée → 400 ``erreurs.etape``, et rien ne bouge."""
        lead, message = self.amener('contact_message')
        corps = self.corps_de(reponse_de('contact_message', 'pas_de_reponse'))
        base = f'/api/django/crm/relance-etapes/{message.pk}'
        self.appel('post', f'{base}/fait/', corps)
        self.verifier_invariants(lead)
        avant = [(e.pk, e.due_at) for e in self.ouvertes(lead)]
        for geste, url, contenu in (
                ('fait', f'{base}/fait/', corps),
                ('sauter', f'{base}/sauter/', {'note': ''}),
                ('reporter', f'{base}/reporter/', {
                    'rappel_le': self.jour_ouvre(2).isoformat(), 'rappel_heure': '11:00'})):
            with self.subTest(geste=geste):
                resp = self.appel('post', url, contenu, quatre_cents='attendu')
                self.assertIn('etape', resp.data['erreurs'], self.msg(f'{resp.data}'))
                self.assertEqual([(e.pk, e.due_at) for e in self.ouvertes(lead)], avant,
                                 self.msg('le double clic a bougé une touche', lead))
        self.verifier_invariants(lead)


# ── 4. La marche au hasard (rejouable) ─────────────────────────────────────────────────────

class ParcoursAleatoiresTests(ParcoursBase):
    """40 leads, jusqu'à 30 gestes chacun : à chaque pas, la PROCHAINE touche ouverte, son
    type, une réponse tirée dans la table (dates entre demain et +20 jours ouvrés, motif tiré
    des motifs de la société) ; l'horloge avance d'un jour ouvré tous les 3 gestes.

    Seuls les INVARIANTS sont vérifiés. REJOUABLE : la graine maîtresse est fixe, chaque lead
    a la sienne (imprimée), et tout échec imprime le chemin complet."""

    slug = 'parcours-hasard'
    #: Graine FIXE (rejouable) ; ``PARCOURS_GRAINE`` dans l'environnement en tire une autre.
    GRAINE = int(os.environ.get('PARCOURS_GRAINE', '20260930'))
    NB_LEADS = 40
    NB_GESTES = 30

    def test_marche_au_hasard(self):
        maitre = random.Random(self.GRAINE)
        graines = [maitre.randrange(2 ** 32) for _ in range(self.NB_LEADS)]
        motifs = sorted(MotifPerte.objects.filter(
            company=self.company, archived=False).values_list('nom', flat=True))
        for rang, graine in enumerate(graines):
            with self.subTest(lead=rang, graine=graine):
                with self.cas_isole(entete=f'marche {rang} (graine {graine})'):
                    self._marcher(random.Random(graine), motifs)

    def _marcher(self, hasard, motifs):
        lead = self.creer_lead()
        for geste in range(1, self.NB_GESTES + 1):
            ouvertes = self.ouvertes(lead)
            if not ouvertes:
                return
            etape = ouvertes[0]
            type_id = type_de(etape)
            self.assertIsNotNone(type_id, self.msg('touche ouverte hors de la table', lead))
            reponse = hasard.choice(reponses(etapes_de_la_table()[type_id]))
            geste_table = reponse.get('geste')
            sans_date = geste_table == 'planification' and hasard.random() < 0.5
            date = None
            if reponse.get('date') or (geste_table in GESTES_PLANIFICATION and not sans_date):
                date = self.jour_ouvre(hasard.randint(1, 20))
            junk = bool(reponse.get('junk')) and hasard.random() < 0.3
            motif = hasard.choice(motifs) if reponse.get('motif_perte') else None
            motif_refus = (hasard.choice(motifs)
                           if reponse.get('motif_refus') and hasard.random() < 0.5 else None)
            resp, _envoye = self.repondre(
                etape, reponse, date=date, motif=motif, junk=junk, motif_refus=motif_refus,
                sans_date=sans_date, quatre_cents='tolere')
            self.verifier_invariants(lead, resp=resp)
            if geste % 3 == 0:
                self.avancer_d_un_jour_ouvre()
