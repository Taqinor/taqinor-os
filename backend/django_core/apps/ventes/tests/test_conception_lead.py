# -*- coding: utf-8 -*-
"""Le moteur unique (D-ACAL-97) — le résultat d'une conception rangé sur le lead.

Module neuf du paquet ``apps/ventes/conception/`` (conception :
``docs/audits/l5-calepinage/controles/C4-un-seul-moteur.md``, §4).

* ADEV129 — le CONTRAT ``contract_samples/conception_lead.json``, posé SEUL sur
  ``main`` avant le modèle, le moteur et la route (PACT10) : chaque clé du §4,
  la forme ACTUELLE des blocs d'étude du devis (jamais redéfinie ici : relue
  dans les contrats et le schéma existants), aucune clé d'achat ni de marge.
* ADEV130 — ``apps/ventes/conception/champs.py::CHAMPS_ENTREES`` : les
  colonnes du lead que lisent les trois adaptateurs (résidentiel, C&I,
  pompage), déduites en ESPIONNANT leurs lectures sur un lead renseigné ; un
  adaptateur qui lit une colonne hors liste est rouge.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_conception_lead"
"""
import json
from decimal import Decimal
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase, TestCase

DOSSIER = Path(__file__).resolve().parents[1] / 'contract_samples'
CONTRAT = DOSSIER / 'conception_lead.json'

#: La sortie du moteur (§3) — aussi la réponse de l'aperçu, sans écriture.
CLES_RESULTAT = {
    'etat', 'refus', 'marche', 'option_retenue', 'valeurs', 'blocs',
    'suppositions', 'entrees_utilisees', 'empreinte', 'niveau_regles',
    'version_moteur',
}
#: Ce que la version RANGÉE ajoute (§4, §5) ; ``lead`` / ``calepinage`` /
#: ``empreinte_pose`` : le porteur et la pose utilisée (ADEV131).
CLES_RANGEES = {
    'declencheur', 'version', 'calcule_le', 'perimee', 'ecart_devis',
    'brouillons_a_mettre_a_jour', 'lead', 'calepinage', 'empreinte_pose',
    'payback_devis',  # relecture E6 : le devis de référence du payback servi à la lecture
}
CLES_VALEUR = {'valeur', 'unite', 'source'}
CLES_ENTREES_PAYBACK = set('investissement base investissement_ttc economie_annuelle cout_onduleur_ttc calcul'.split())
SOURCES_VALEUR = {'moteur', 'pose', 'plan_par_defaut', 'impose', 'devis', 'defaut'}  # ADEV155 : niveau 15
SOURCES_ENTREE = {'lead', 'calepinage', 'reglage_societe', 'defaut'}
CLES_SUPPOSITION = {'code', 'champ', 'valeur', 'source', 'message'}
CLES_DECLENCHEUR = {'raison', 'champs', 'origine'}
CLES_CHAMP_MODIFIE = {'champ', 'avant', 'apres'}
ORIGINES = {'lead_entrees_modifiees', 'pose_enregistree', 'regles',
            'remplissage', 'manuel', 'filet'}
CLES_ECART = {'valeur', 'devis', 'conception', 'devis_ref',
              'reviser_possible', 'mise_a_jour_proposee', 'courante_refusee'}
CLES_REFUS = {'code', 'champ', 'message'}
#: La table §2, par option (résidentiel, commercial, industriel).
VALEURS_SOLAIRES = {
    'nb_panneaux', 'puissance_kwc', 'module', 'onduleurs', 'nombre_onduleurs',
    'chaines', 'temperature_froid', 'tension_froid', 'ratio_dc_ac',
    'production_annuelle', 'production_mensuelle', 'autoconsommation',
    'couverture', 'economies_annuelles', 'payback', 'consommation_annuelle',
    'forme_horaire', 'forme_horaire_24', 'module_produit', 'onduleur_produit', 'batterie_produit', 'verdicts',
}
#: La table §2 en agricole (la pompe remplace taille / matériel / bilan).
VALEURS_POMPAGE = {'nb_panneaux', 'puissance_kwc', 'pompe', 'variateur', 'm3_jour'}
CLES_CORPS_APERCU = {'lead', 'calepinage', 'entrees', 'imposes', 'investissement'}
#: ADEV137 — la forme des champs imposés de ``POST devis/auto/`` (celle du moteur).
CLES_IMPOSES = {'nb_panneaux', 'panneau_produit_id', 'onduleur_produit_id', 'onduleur_kw',
                'onduleur_phase', 'batterie_produit_id', 'batterie_kwh'}


def _lire(nom):
    return json.loads((DOSSIER / nom).read_text(encoding='utf-8'))


def _cles_interdites(noeud, chemin='$'):
    """Chemins de toute clé d'achat ou de marge, à toute profondeur."""
    trouves = []
    if isinstance(noeud, dict):
        for cle, valeur in noeud.items():
            if 'prix_achat' in cle or cle.startswith('marge'):
                trouves.append(f'{chemin}.{cle}')
            trouves += _cles_interdites(valeur, f'{chemin}.{cle}')
    elif isinstance(noeud, list):
        for i, valeur in enumerate(noeud):
            trouves += _cles_interdites(valeur, f'{chemin}[{i}]')
    return trouves


class ContratConceptionLeadTests(SimpleTestCase):
    """ADEV129 — l'échantillon porte chaque clé du §4 et aucune clé interdite."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.doc = json.loads(CONTRAT.read_text(encoding='utf-8'))
        cls.exemples = {k: v for k, v in cls.doc.items()
                        if k.startswith('exemple')}

    def test_route_et_exemples(self):
        self.assertEqual(self.doc['endpoint'],
                         'GET /api/django/ventes/conception/<int:lead_id>/')
        self.assertIn('exemple', self.exemples)
        self.assertGreaterEqual(len(self.exemples), 3)

    def test_chaque_cle_du_resultat_range(self):
        for nom, ex in self.exemples.items():
            with self.subTest(exemple=nom):
                self.assertEqual(set(ex), CLES_RESULTAT | CLES_RANGEES)
                self.assertIn(ex['etat'], {'complet', 'refus'})
                self.assertEqual(len(ex['empreinte']), 64)
                int(ex['empreinte'], 16)
                self.assertIsInstance(ex['niveau_regles'], int)
                self.assertIsInstance(ex['version'], int)
                self.assertIsInstance(ex['perimee'], bool)
                self.assertTrue(ex['lead'] or ex['calepinage'])
                self.assertIn(len(ex['empreinte_pose']), (0, 64))
                if ex['etat'] == 'refus':
                    self.assertEqual(set(ex['refus']), CLES_REFUS)
                    self.assertEqual(ex['valeurs'], {})
                else:
                    self.assertIsNone(ex['refus'])
                    self.assertIn(ex['option_retenue'], ex['valeurs'])

    def test_valeurs_par_option(self):
        for nom, ex in self.exemples.items():
            attendues = (VALEURS_POMPAGE if ex['marche'] == 'agricole'
                         else VALEURS_SOLAIRES)
            for option, valeurs in ex['valeurs'].items():
                with self.subTest(exemple=nom, option=option):
                    self.assertIn(option, {'sans', 'avec'})
                    self.assertEqual(set(valeurs), attendues)
                    for cle, valeur in valeurs.items():
                        # T4-X9-016 — le payback servi d'un devis porte aussi ses entrées.
                        attendu = (CLES_VALEUR | CLES_ENTREES_PAYBACK
                                   if cle == 'payback' and valeur.get('source') == 'devis' else CLES_VALEUR)
                        self.assertEqual(set(valeur), attendu, cle)
                        self.assertIn(valeur['source'], SOURCES_VALEUR, cle)

    def test_suppositions_entrees_et_declencheur(self):
        for nom, ex in self.exemples.items():
            with self.subTest(exemple=nom):
                for sup in ex['suppositions']:
                    self.assertEqual(set(sup), CLES_SUPPOSITION)
                for champ, entree in ex['entrees_utilisees'].items():
                    self.assertEqual(set(entree), {'valeur', 'source'}, champ)
                    self.assertIn(entree['source'], SOURCES_ENTREE, champ)
                dec = ex['declencheur']
                self.assertEqual(set(dec), CLES_DECLENCHEUR)
                self.assertIn(dec['origine'], ORIGINES)
                for modif in dec['champs']:
                    self.assertEqual(set(modif), CLES_CHAMP_MODIFIE)
                for ecart in ex['ecart_devis']:
                    self.assertEqual(set(ecart), CLES_ECART)
                    self.assertIn(ecart['valeur'], VALEURS_SOLAIRES | VALEURS_POMPAGE)
                for brouillon in ex['brouillons_a_mettre_a_jour']:
                    self.assertEqual(set(brouillon), {'devis', 'reference', 'motif'})
        self.assertTrue(self.doc['exemple']['ecart_devis'])
        self.assertTrue(self.doc['exemple']['declencheur']['champs'])

    def test_apercu_sans_ecriture(self):
        apercu = self.doc['apercu']
        self.assertEqual(apercu['endpoint'],
                         'POST /api/django/ventes/conception/apercu/')
        self.assertEqual(set(apercu['corps']), CLES_CORPS_APERCU)
        self.assertEqual(set(apercu['corps']['imposes']), CLES_IMPOSES)
        from apps.ventes.domain.composition_imposee import CHAMPS_IMPOSES
        self.assertEqual(CLES_IMPOSES, set(CHAMPS_IMPOSES))  # une seule forme : celle du moteur
        self.assertEqual(set(apercu['reponse']), CLES_RESULTAT)
        # Une valeur tapée et non enregistrée n'est jamais dite « du lead ».
        for champ, entree in apercu['reponse']['entrees_utilisees'].items():
            self.assertIn(entree['source'], SOURCES_ENTREE | {'saisie'}, champ)

    def test_blocs_forme_actuelle_du_devis(self):
        """Les blocs sont ce que le devis porte AUJOURD'HUI dans
        ``etude_params`` (ADEV135 : son contenu COMPLET, sans ``journal_auto``) :
        clés du schéma, sous-clés des blocs d'étude relues dans les contrats
        existants (jamais une seconde définition)."""
        from apps.ventes.domain import etude_schema as es

        horaire = _lire('etude_horaire.json')['exemple']
        ci = _lire('etude_ci_preview.json')['cles_etude_params_ci_v2']
        pompage = _lire('etude_pompage_preview.json')['cles_etude_params_v2']
        sous_cles = {
            'etude_horaire': set(horaire['etude']) | {'_empreinte_entrees'},
            'etude_horaire_sans': set(horaire['etude']) | {'_empreinte_entrees'},
            'dimensionnement': (set(horaire['dimensionnement'])
                                | {'_empreinte_entrees'}),
            'etude_ci': set(next(d['contient'] for d in ci['derivees']
                                 if d['cle'] == 'etude_ci')),
        }
        derivees_pompage = {d['cle'] for d in pompage['derivees']}
        vus = set()
        for nom, ex in [*self.exemples.items(),
                        ('apercu', self.doc['apercu']['reponse'])]:
            for cle, bloc in ex['blocs'].items():
                with self.subTest(exemple=nom, bloc=cle):
                    regle = es.SCHEMA.get(cle)
                    self.assertIsNotNone(regle, cle)
                    self.assertNotEqual(cle, 'journal_auto')
                    if regle['proprietaire'] == es.MOTEUR_POMPAGE and regle['nature'] == es.DERIVEE:
                        self.assertTrue(cle in derivees_pompage
                                        or not isinstance(bloc, dict), cle)
                    if cle in sous_cles:
                        self.assertLessEqual(set(bloc), sous_cles[cle])
                    vus.add(cle)
        self.assertLessEqual({'etude_horaire', 'dimensionnement', 'etude_ci', 'puissance_kwc',
                              'ville_calcul', 'origine_conception'}, vus)

    def test_aucune_cle_d_achat_ni_de_marge(self):
        self.assertEqual(_cles_interdites(self.doc), [])
        # Le parcours détecte bien une clé interdite enfouie.
        self.assertEqual(_cles_interdites({'a': [{'b': {'prix_achat_ht': 1}}]}),
                         ['$.a[0].b.prix_achat_ht'])


# ── ADEV130 — les colonnes du lead qui sont des entrées du moteur ────────────

#: Un lead renseigné sur toutes les entrées connues des trois adaptateurs, pour
#: que chaque branche de lecture s'exécute (valeurs illustratives).
_LEAD_RENSEIGNE = {
    'ville': 'Casablanca', 'ville_reference': 'Casablanca',
    'gps_lat': Decimal('33.5731'), 'gps_lng': Decimal('-7.5898'),
    'facture_hiver': Decimal('1200'), 'facture_ete': Decimal('900'),
    'ete_differente': True, 'conso_mensuelle_kwh': Decimal('500'),
    'bill_kwh': Decimal('500'), 'raccordement': 'triphase',
    'occupation_jour': 'present', 'equip_clim': True, 'equip_piscine': True,
    'equip_voiture_electrique': True, 'equip_chauffe_eau_electrique': True,
    'tension_raccordement': 'bt', 'contrat_electricite': 'bt_patente',
    'compteur_puissance_kva': Decimal('36'), 'regime_equipes': '2x8',
    'jours_ouverture': [1, 2, 3, 4, 5], 'heure_debut': 8, 'heure_fin': 18,
    'fermeture_mois': [8], 'type_surface': 'toiture',
    'type_toiture': 'terrasse_beton', 'surface_toiture_m2': Decimal('200'),
    'tva_recuperable': 'oui', 'pompe_hmt_m': Decimal('40'),
    'pompe_debit_m3h': Decimal('5'), 'besoin_eau_m3j': Decimal('30'),
}


class ChampsEntreesTests(TestCase):
    """ADEV130 — un adaptateur qui lit une colonne absente de
    ``CHAMPS_ENTREES`` est rouge. L'espion compte TOUTE lecture d'une colonne
    sur une instance ``Lead`` pendant l'appel de l'adaptateur (y compris dans
    les sélecteurs du CRM qu'il appelle)."""

    def _lead(self, marche):
        from apps.crm.models import Lead
        from authentication.models import Company

        company = Company.objects.create(nom=f'Moteur {marche}',
                                         slug=f'moteur-unique-{marche}')
        lead = Lead.objects.create(company=company, nom='Lead', prenom=marche,
                                   telephone='+212600000000',
                                   type_installation=marche, **_LEAD_RENSEIGNE)
        return company, lead

    def _colonnes_lues(self, appel):
        from apps.crm.models import Lead

        colonnes = {}
        for champ in Lead._meta.concrete_fields:
            colonnes[champ.name] = champ.name
            colonnes[champ.attname] = champ.name
        lues = set()
        lecture = object.__getattribute__

        def espion(instance, nom):
            if nom in colonnes:
                lues.add(colonnes[nom])
            return lecture(instance, nom)

        with mock.patch.object(Lead, '__getattribute__', espion):
            appel()
        return lues

    def _adaptateur(self, marche, company, lead):
        from apps.ventes.domain import entrees, etude_ci, pompage

        if marche == 'residentiel':
            return lambda: entrees.entrees_depuis_lead(lead, company)
        if marche == 'agricole':
            return lambda: pompage.resoudre_entrees(company, {}, lead=lead)
        return lambda: etude_ci.resoudre_entrees({}, lead=lead)

    def test_chaque_colonne_lue_par_l_adaptateur_est_dans_la_liste(self):
        from apps.ventes.conception.champs import (
            CHAMPS_ENTREES, CHAMPS_LUS_HORS_ENTREES, champs_pour)

        self.assertEqual(set(CHAMPS_ENTREES),
                         {'residentiel', 'commercial', 'industriel', 'agricole'})
        for marche in CHAMPS_ENTREES:
            with self.subTest(marche=marche):
                company, lead = self._lead(marche)
                lues = self._colonnes_lues(self._adaptateur(marche, company, lead))
                # L'espion voit bien les lectures (preuve qu'il n'est pas muet).
                self.assertIn('gps_lat', lues)
                hors_liste = lues - set(champs_pour(marche)) - set(CHAMPS_LUS_HORS_ENTREES)
                self.assertEqual(
                    hors_liste, set(),
                    f"{marche} : colonnes lues par l'adaptateur et absentes de "
                    f"CHAMPS_ENTREES['{marche}'] : {sorted(hors_liste)}")

    def test_listes_sur_de_vraies_colonnes_sans_identite(self):
        from apps.crm.models import Lead
        from apps.ventes.conception.champs import (
            CHAMPS_ENTREES, CHAMPS_LUS_HORS_ENTREES, champs_pour)

        colonnes = {f.name for f in Lead._meta.concrete_fields}
        for marche, champs in CHAMPS_ENTREES.items():
            with self.subTest(marche=marche):
                self.assertIsInstance(champs, tuple)
                self.assertEqual(champs_pour(marche), champs)
                self.assertLessEqual(set(champs), colonnes)
                self.assertEqual(set(champs) & set(CHAMPS_LUS_HORS_ENTREES), set())
                self.assertIn('type_installation', champs)
                for identite in ('nom', 'prenom', 'telephone', 'email', 'notes'):
                    self.assertNotIn(identite, champs)
        self.assertIn('facture_hiver', champs_pour('residentiel'))
        self.assertLessEqual(set(CHAMPS_LUS_HORS_ENTREES), colonnes)
        with self.assertRaises(KeyError):
            champs_pour('inconnu')


class EntreesConceptionTests(TestCase):
    """ADEV132 — ``EntreesConception`` : l'adaptateur du marché enveloppé,
    la provenance de chaque valeur, et l'empreinte résidentielle IDENTIQUE à
    celle des blocs d'aujourd'hui (``empreinte_entrees``)."""

    _lead = ChampsEntreesTests._lead
    _colonnes_lues = ChampsEntreesTests._colonnes_lues

    def test_residentiel_empreinte_egale_a_celle_des_blocs(self):
        from apps.ventes.conception.entrees import completer, entrees_pour
        from apps.ventes.domain.entrees import empreinte_entrees, entrees_depuis_lead

        company, lead = self._lead('residentiel')
        lead.occupation_jour = ''
        lead.save(update_fields=['occupation_jour'])
        entrees = entrees_pour(lead, company)
        attendue = entrees_depuis_lead(lead, company)
        self.assertEqual(entrees.marche, 'residentiel')
        self.assertEqual(entrees.moteur, attendue)
        # Base = l'empreinte des blocs ; relecture E4 B1 : + raccordement, TVA, catalogue.
        self.assertEqual(entrees.empreinte, completer(empreinte_entrees(attendue), lead, company, {}))
        utilisees = entrees.entrees_utilisees
        self.assertEqual(utilisees['facture_hiver'], {'valeur': 1200.0, 'source': 'lead'})
        self.assertEqual(utilisees['ville']['source'], 'lead')
        # Présence jamais posée : la valeur retenue est le défaut, et c'est dit.
        self.assertEqual(utilisees['occupation_jour']['source'], 'defaut')
        self._sources_du_contrat(utilisees)

    def test_ci_et_pompage_portent_leur_provenance(self):
        from apps.ventes.conception.entrees import entrees_pour

        for marche in ('commercial', 'industriel', 'agricole'):
            with self.subTest(marche=marche):
                company, lead = self._lead(marche)
                entrees = entrees_pour(lead, company)
                self.assertEqual(entrees.marche, marche)
                self.assertIsNone(entrees.moteur)
                self.assertIsNotNone(entrees.resolution)
                self.assertEqual(len(entrees.empreinte), 64)
                self.assertTrue(entrees.entrees_utilisees)
                self.assertIn('lead', {e['source'] for e in entrees.entrees_utilisees.values()})
                self._sources_du_contrat(entrees.entrees_utilisees)
                # Même lead, mêmes entrées : même empreinte (aucun aléa).
                self.assertEqual(entrees_pour(lead, company).empreinte, entrees.empreinte)

    def test_empreinte_change_avec_une_entree_et_avec_la_pose(self):
        from types import SimpleNamespace

        from apps.ventes.conception.entrees import entrees_pour

        company, lead = self._lead('residentiel')
        avant = entrees_pour(lead, company).empreinte
        self.assertNotEqual(entrees_pour(lead, company, toit=SimpleNamespace(empreinte='c' * 64)).empreinte,
                            avant)
        # Le kWh déclaré prime sur les factures (CAD166) : une facture changée
        # ne bouge rien tant qu'il est posé ; le kWh, lui, bouge l'empreinte.
        lead.facture_hiver = Decimal('1500')
        lead.save(update_fields=['facture_hiver'])
        self.assertEqual(entrees_pour(lead, company).empreinte, avant)
        lead.conso_mensuelle_kwh = Decimal('650')
        lead.save(update_fields=['conso_mensuelle_kwh'])
        self.assertNotEqual(entrees_pour(lead, company).empreinte, avant)

    def test_lecture_complete_ne_lit_que_des_colonnes_d_entree(self):
        """Point 2 de la lane : TOUTE colonne du lead lue par ``entrees_pour``
        est dans ``CHAMPS_ENTREES[marche]`` (ou dans la liste de provenance)."""
        from apps.ventes.conception.champs import CHAMPS_LUS_HORS_ENTREES, champs_pour
        from apps.ventes.conception.entrees import entrees_pour

        for marche in ('residentiel', 'commercial', 'industriel', 'agricole'):
            with self.subTest(marche=marche):
                company, lead = self._lead(marche)
                lues = self._colonnes_lues(lambda: entrees_pour(lead, company))
                hors_liste = lues - set(champs_pour(marche)) - set(CHAMPS_LUS_HORS_ENTREES)
                self.assertEqual(hors_liste, set(), sorted(hors_liste))

    def _sources_du_contrat(self, utilisees):
        for champ, entree in utilisees.items():
            self.assertEqual(set(entree), {'valeur', 'source'}, champ)
            self.assertIn(entree['source'], SOURCES_ENTREE, champ)
        json.dumps(utilisees)


# ── ADEV131 — le résultat rangé : une seule version courante par porteur ─────

def _champs_version(**extra):
    """Une version de conception complète (valeurs illustratives)."""
    champs = {
        'etat': 'complet', 'refus': None, 'marche': 'residentiel',
        'option_retenue': 'sans',
        'valeurs': {'sans': {'nb_panneaux': {'valeur': 10, 'unite': 'panneaux',
                                             'source': 'moteur'}}},
        'blocs': {'etude_horaire': {'version': 1, 'kwc': 7.1}},
        'entrees_utilisees': {'facture_hiver': {'valeur': 1200, 'source': 'lead'}},
        'suppositions': [{'code': 'occupation_supposee', 'champ': 'occupation_jour',
                          'valeur': 'presence_jour', 'source': 'defaut',
                          'message': 'Présence en journée supposée.'}],
        'empreinte': 'a' * 64, 'empreinte_pose': '', 'niveau_regles': 14,
        'version_moteur': 'qjr43-2',
        'declencheur': {'raison': 'remplissage initial', 'champs': [],
                        'origine': 'remplissage'},
    }
    champs.update(extra)
    return champs


class ConceptionLeadModeleTests(TestCase):
    """ADEV131 — ``ConceptionLead`` : une seule ``courante`` par porteur
    (lead, ou calepinage sans lead), version = plus haut utilisé + 1, société
    venue du porteur, rien n'est jamais supprimé."""

    def setUp(self):
        from apps.crm.models import Lead
        from authentication.models import Company

        self.company = Company.objects.create(nom='Conception A', slug='conception-a')
        self.autre = Company.objects.create(nom='Conception B', slug='conception-b')
        self.lead = Lead.objects.create(company=self.company, nom='Lead', prenom='A',
                                        telephone='+212600000001')

    def test_deux_versions_la_seconde_devient_seule_courante(self):
        from apps.ventes.models import ConceptionLead

        v1 = ConceptionLead.ranger(lead=self.lead, **_champs_version())
        v2 = ConceptionLead.ranger(lead=self.lead, **_champs_version(empreinte='b' * 64))
        v1.refresh_from_db()
        self.assertEqual((v1.version, v1.courante), (1, False))
        self.assertEqual((v2.version, v2.courante), (2, True))
        self.assertEqual(ConceptionLead.objects.filter(lead=self.lead).count(), 2)
        self.assertEqual(ConceptionLead.objects.get(lead=self.lead, courante=True).pk, v2.pk)

    def test_lead_efface_ses_versions_partent_les_autres_restent(self):
        """Effacement d'un lead (DSR, rétention) : ses versions rangées, qui
        copient ses entrées (factures, ville, GPS), sont supprimées ; celles
        d'un autre lead restent, et une autre société n'efface rien."""
        from apps.crm.models import Lead
        from apps.ventes.models import ConceptionLead
        from core.events import lead_erased

        voisin = Lead.objects.create(company=self.company, nom='Voisin', prenom='B',
                                     telephone='+212600000002')
        ConceptionLead.ranger(lead=self.lead, **_champs_version())
        ConceptionLead.ranger(lead=self.lead, **_champs_version(empreinte='b' * 64))
        garde = ConceptionLead.ranger(lead=voisin, **_champs_version())

        lead_erased.send(sender=None, company=self.autre,
                         crm_lead_id=self.lead.pk, phone_key='')
        self.assertEqual(ConceptionLead.objects.filter(lead=self.lead).count(), 2)

        lead_erased.send(sender=None, company=self.company,
                         crm_lead_id=self.lead.pk, phone_key='')
        self.assertFalse(ConceptionLead.objects.filter(lead=self.lead).exists())
        self.assertTrue(ConceptionLead.objects.filter(pk=garde.pk).exists())

    def test_contrainte_refuse_deux_courantes_pour_un_lead(self):
        from django.db import IntegrityError, transaction

        from apps.ventes.models import ConceptionLead

        ConceptionLead.ranger(lead=self.lead, **_champs_version())
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                ConceptionLead.objects.create(company=self.company, lead=self.lead,
                                              version=9, courante=True, **_champs_version())

    def test_contrainte_refuse_deux_courantes_pour_un_calepinage_sans_lead(self):
        from django.db import IntegrityError, transaction

        from apps.ventes.models import ConceptionLead

        ConceptionLead.objects.create(company=self.company, calepinage_id=77, version=1,
                                      courante=True, **_champs_version())
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                ConceptionLead.objects.create(company=self.company, calepinage_id=77,
                                              version=2, courante=True, **_champs_version())

    def test_version_plus_haut_utilise_plus_un_jamais_le_compte(self):
        from apps.ventes.models import ConceptionLead

        # Une seule ligne, mais de version 5 : un count()+1 rendrait 2.
        ConceptionLead.objects.create(company=self.company, lead=self.lead, version=5,
                                      courante=False, **_champs_version())
        nouvelle = ConceptionLead.ranger(lead=self.lead, **_champs_version())
        self.assertEqual(nouvelle.version, 6)

    def test_societe_venue_du_lead_jamais_d_ailleurs(self):
        from apps.ventes.models import ConceptionLead

        version = ConceptionLead.ranger(lead=self.lead, **_champs_version())
        self.assertEqual(version.company_id, self.company.pk)
        with self.assertRaises(ValueError):
            ConceptionLead.ranger(lead=self.lead, company=self.autre, **_champs_version())

    def test_porteur_obligatoire_et_lead_en_chaine_cascade(self):
        from django.db import models

        from apps.ventes.models import ConceptionLead

        with self.assertRaises(ValueError):
            ConceptionLead.ranger(company=self.company, **_champs_version())
        champ = ConceptionLead._meta.get_field('lead')
        self.assertEqual(champ.related_model._meta.label, 'crm.Lead')
        self.assertTrue(champ.null)
        self.assertIs(champ.remote_field.on_delete, models.CASCADE)

    def test_version_relue_champ_pour_champ(self):
        from apps.ventes.models import ConceptionLead

        champs = _champs_version()
        rangee = ConceptionLead.ranger(lead=self.lead, **champs)
        relue = ConceptionLead.objects.get(pk=rangee.pk)
        for nom in ('valeurs', 'blocs', 'suppositions', 'entrees_utilisees', 'declencheur',
                    'etat', 'marche', 'option_retenue', 'empreinte', 'niveau_regles',
                    'version_moteur'):
            self.assertEqual(getattr(relue, nom), champs[nom], nom)
        self.assertIsNotNone(relue.calcule_le)
        self.assertIsNone(relue.calcule_par)


# ── ADEV159 — figer avant de toucher : ce que build_devis_auto écrit AUJOURD'HUI ─
#
# Goldens de CARACTÉRISATION (un JSON par cas sous ``golden/conception/``) pris
# sur le code de création INTACT, avant l'extraction du pipeline pur (ADEV160)
# et le moteur unique (ADEV133) : lignes du devis, TOUTES les clés de
# ``etude_params``, ``electrical_design`` et les champs du devis que la création
# écrit. Leads = les fabriques des trois modules de test du devis automatique
# (``test_devis_auto``, ``test_ciq120_devis_auto_ci``,
# ``test_agr124_devis_auto_agricole``), leurs patrons hors réseau compris.
#
# Capture (une fois, puis à chaque changement VOULU d'un chiffre — jamais pour
# faire passer une extraction) : ``UPDATE_GOLDEN=1`` dans l'environnement du
# conteneur de test. Golden absent ⇒ rouge ; un écart nomme les clés fautives.

DOSSIER_FIGEAGE = Path(__file__).resolve().parent / 'golden' / 'conception'
INSTANT_FIGEAGE = '2026-10-01T10:00:00+01:00'

#: Normalisés (seule instabilité réelle) : identifiants de base et horodatages
#: (les séquences avancent d'une exécution à l'autre sur la base gardée), la
#: référence du devis. Les produits des lignes sont nommés, jamais numérotés.
CLES_IDS_FIGEAGE = frozenset({
    'id', 'pk', 'uuid', 'token', 'jeton', 'produit', 'produit_id', 'client', 'client_id',
    'lead', 'lead_id', 'devis', 'devis_id', 'company', 'company_id', 'user', 'user_id',
    'created_by', 'updated_by', 'created_at', 'updated_at', 'date_creation',
    'date_modification', 'date_validite', 'ligne_id', '_company_id', 'source_lead_id',
})
#: Empreintes calculées SUR des identifiants de base (relevées instables à la
#: double exécution, ``(bloc parent, clé)``) : la valeur est masquée, la
#: PRÉSENCE de la clé reste figée. Les empreintes résidentielles
#: (``_empreinte_entrees``, ``dimensionnement._empreinte``) restent figées.
EMPREINTES_SUR_IDS = frozenset({('etude_ci', 'empreinte'), ('provenance_pompage', '_empreinte')})
#: Lecteurs de la création qui ne CALCULENT rien (identifiés par la pile) : la
#: résolution du client (identité, et les signaux du ``Lead.save`` qu'elle
#: déclenche) et le tampon de provenance recopié sur le devis
#: (``crm.fiche_selectors.lead_provenance_stamp``). Aucun ne relance le moteur.
#: ADEV142 : la création relance la conception, dont la garde d'effacement
#: (``crm.selectors.lead_efface``, loi 09-08) lit ``nom`` sans rien calculer.
LECTEURS_HORS_CALCUL = frozenset({'resolve_client_for_lead', 'lead_provenance_stamp', 'lead_efface'})
#: Colonnes lues par un sélecteur de calcul sans entrer dans aucun chiffre :
#: ``crm.devis_selectors.site_location_for_devis`` rend aussi l'adresse du
#: chantier (``site_adresse``), qu'aucune étude ne lit (ville et GPS seuls).
COLONNES_LUES_SANS_CHIFFRE = frozenset({'adresse'})
#: Clés d'hypothèse suffixées par l'id d'un produit (``section_ac_<id du câble>``).
CLE_SUFFIXEE_PAR_UN_ID = r'\b(section_ac)_\d+\b'

#: Le tracé du client des cas « contour » (zone du calepinage).
CONTOUR_CLIENT = {'roof_outline': [[33.57310, -7.58980], [33.57310, -7.58970],
                                   [33.57301, -7.58970], [33.57301, -7.58980]],
                  'roof_point': {'lat': 33.573055, 'lng': -7.58975}}
#: Ce que l'APPELANT passe à ``build_devis_auto`` pour un cas (hors lead).
APPELS_FIGEAGE = {
    'res_contour_plafond': {'plafond_toit': 8},
    'journal_taille_souhaitee': {'journal': True},
    'journal_taille_cible': {'journal': True, 'target_kwc': '5'},
    'journal_site_isole': {'journal': True},
    'journal_site_isole_sans': {'journal': True},
    'journal_contour_plafond': {'journal': True, 'plafond_toit': 8},
}

CHAMPS_DEVIS_FIGES = ('mode_installation', 'statut', 'taux_tva', 'remise_globale', 'devise',
                      'regles_calcul', 'option_acceptee', 'prix_par_kwc', 'prix_cible_kwc',
                      'version', 'is_active', 'overrides', 'echeancier', 'roof_layout',
                      'layout_hash', 'offres_tailles_config', 'variante_tier',
                      'electrical_design_hash')
CHAMPS_LIGNE_FIGES = ('ordre', 'designation', 'quantite', 'prix_unitaire', 'remise', 'taux_tva',
                      'tva_base_legale', 'type_ligne', 'variante', 'optionnelle',
                      'quantite_manuelle', 'prix_manuel', 'ligne_composee', 'role_devis',
                      'groupe_index', 'groupe_label')


def _normaliser_figeage(noeud, parent=None):
    import re
    from datetime import date, datetime

    if isinstance(noeud, dict):
        sortie = {}
        for cle, valeur in noeud.items():
            cle = str(cle)
            if valeur is not None and (cle in CLES_IDS_FIGEAGE or (parent, cle) in EMPREINTES_SUR_IDS):
                sortie[cle] = '<masque>'
            else:
                sortie[cle] = _normaliser_figeage(valeur, cle)
        return sortie
    if isinstance(noeud, (list, tuple)):
        return [_normaliser_figeage(v, parent) for v in noeud]
    if isinstance(noeud, Decimal):
        return str(noeud)
    if isinstance(noeud, (date, datetime)):
        return '<date>'
    if isinstance(noeud, str):
        noeud = re.sub(CLE_SUFFIXEE_PAR_UN_ID, r'\1_<id>', noeud)
        return re.sub(r'\b(DEV|BROUILLON)-[0-9-]+\b', r'\1-<ref>', noeud)
    return noeud


def _ecarts_figeage(attendu, reel, chemin='$'):
    """Chemins où ``reel`` diffère d'``attendu``, clé par clé."""
    if isinstance(attendu, dict) and isinstance(reel, dict):
        ecarts = []
        for cle in sorted(set(attendu) | set(reel)):
            if cle not in attendu or cle not in reel:
                ecarts.append(f'{chemin}.{cle} ({"ajoutée" if cle in reel else "absente"})')
            else:
                ecarts += _ecarts_figeage(attendu[cle], reel[cle], f'{chemin}.{cle}')
        return ecarts
    if isinstance(attendu, list) and isinstance(reel, list) and len(attendu) == len(reel):
        ecarts = []
        for i, (a, r) in enumerate(zip(attendu, reel)):
            ecarts += _ecarts_figeage(a, r, f'{chemin}[{i}]')
        return ecarts
    return [] if attendu == reel else [f'{chemin} : {attendu!r} -> {reel!r}'[:300]]


def _photo_du_devis(devis):
    """Ce que la création a écrit : champs, lignes (produit NOMMÉ), étude,
    conception électrique, totaux. Jamais ``marge_snapshot`` (prix d'achat)."""
    devis.refresh_from_db()
    lignes = []
    for ligne in devis.lignes.select_related('produit').order_by('ordre', 'pk'):
        photo = {nom: getattr(ligne, nom) for nom in CHAMPS_LIGNE_FIGES}
        photo['produit_nom'] = getattr(ligne.produit, 'nom', None)
        lignes.append(photo)
    champs = {nom: getattr(devis, nom) for nom in CHAMPS_DEVIS_FIGES}
    champs.update(total_ht=devis.total_ht, total_tva=devis.total_tva, total_ttc=devis.total_ttc)
    return _normaliser_figeage({
        'champs_devis': champs, 'lignes': lignes, 'etude_params': devis.etude_params or {},
        'electrical_design': devis.electrical_design})


def _emprunt(classe, *noms):
    """Une classe porteuse des fabriques ``noms`` d'une classe de test voisine
    (jamais importée dans ce module : le chargeur la rejouerait)."""
    return type('Fabriques' + classe.__name__, (), {nom: classe.__dict__[nom] for nom in noms})


class FigeageDevisAutoTests(TestCase):
    """ADEV159 — figer avant de toucher : un golden par cas de ``build_devis_auto``."""

    def setUp(self):
        from freezegun import freeze_time

        figeur = freeze_time(INSTANT_FIGEAGE)
        figeur.start()
        self.addCleanup(figeur.stop)
        # Hors réseau (patron SPL160) : chaque lecture PVGIS prend son repli.
        coupure = mock.patch('urllib.request.urlopen', side_effect=OSError('ADEV159 hors réseau'))
        coupure.start()
        self.addCleanup(coupure.stop)

    def _patcher(self, cible, nom, **kw):
        patcher = mock.patch.object(cible, nom, **kw)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _utilisateur(self, company):
        from django.contrib.auth import get_user_model

        return get_user_model().objects.create_user(
            username=f'figeage-{company.pk}', password='x', role_legacy='responsable',
            company=company)

    # ── fabriques des trois modules voisins ─────────────────────────────────
    def _residentiel(self, **extra):
        from apps.crm.models import Lead
        from apps.ventes.tests import test_devis_auto as res

        company = res.make_company('auto-co')
        res.seed_catalogue(company)
        extra.setdefault('ville', res.VILLE_ANCRE)
        extra.setdefault('email', 'auto@ex.com')
        return company, Lead.objects.create(company=company, nom='Auto', prenom='Lead', **extra)

    def _ci(self, *, batteries=False, boulangerie=False, **kw):
        from apps.ventes import tarif_ci
        from apps.ventes.domain import etude_ci
        from apps.ventes.tests import test_ciq120_devis_auto_ci as ci

        fab = _emprunt(ci._Base, 'setUpTestData', '_lead')
        fab._boulangerie = ci.OptionBatterieCITests.__dict__['_boulangerie']
        fab.setUpTestData()
        fab = fab()
        if batteries:
            ci._semer_batterie(fab)
        self._patcher(etude_ci, 'lire_production', side_effect=ci._production_casablanca)
        self._patcher(tarif_ci, 'tarif_applicable', side_effect=ci._tarif_grille)
        return fab.co, (fab._boulangerie(**kw) if boulangerie else fab._lead(**kw))

    def _agricole(self, *, existante=False, **kw):
        from apps.ventes.domain import pompage
        from apps.ventes.tests import test_agr124_devis_auto_agricole as agr

        fab = _emprunt(agr.DevisAutoAgricoleTests, 'setUpTestData', '_produit', '_pompe', '_lead',
                       '_lead_existante')
        fab.setUpTestData()
        fab = fab()
        fab._pompe('15000')
        self._patcher(pompage, 'profils_horaires_site', return_value=agr.PROFILS)
        self._patcher(pompage, 'temperatures_du_site', return_value=None)
        return fab.co, (fab._lead_existante(**kw) if existante else fab._lead(**kw))

    def _fiches_residentielles(self, company):
        """ADEV160 (préalable) — fiches COMPLÈTES du panneau et des deux
        onduleurs de ``seed_catalogue`` (valeurs de fiche de test, 550 Wc
        mono, onduleurs 5 kW mono à 2 MPPT) : sans elles la conception
        électrique n'est jamais rangée (``fiches_manquantes_du_devis``)."""
        from apps.stock.models import FicheTechnique, Produit

        produits = Produit.objects.filter(company=company)
        FicheTechnique.objects.create(
            company=company, produit=produits.get(nom='Panneau Jinko 550W'), type_fiche='module',
            pmax_wc=Decimal('550'), voc_v=Decimal('49.90'), isc_a=Decimal('14.02'),
            vmp_v=Decimal('41.80'), imp_a=Decimal('13.16'), noct_c=Decimal('45'),
            temp_coeff_voc_pct_c=Decimal('-0.270'), temp_coeff_pmax_pct_c=Decimal('-0.350'))
        for nom in ('Onduleur réseau Huawei 5kW Monophasé', 'Onduleur hybride Deye 5kW Monophasé'):
            FicheTechnique.objects.create(
                company=company, produit=produits.get(nom=nom), type_fiche='onduleur',
                ond_ac_kw=Decimal('5'), ond_phases=1, ond_n_mppt=2, ond_mppt_v_min=Decimal('90'),
                ond_mppt_v_max=Decimal('560'), ond_v_max_abs=Decimal('600'),
                ond_i_max_mppt_a=Decimal('16'), ond_rendement_euro_pct=Decimal('97.5'))

    def _site_isole(self, **extra):
        from apps.stock.models import Produit

        company, lead = self._residentiel(facture_hiver=Decimal('1800'), raccordement='aucun', **extra)
        Produit.objects.create(company=company, nom='Onduleur autonome Deye 5kW Monophasé',
                               sku=f'ONDA-{company.pk}', prix_vente=Decimal('15000'),
                               prix_achat=Decimal('1'), quantite_stock=100)
        return company, lead

    def _structures(self, company):
        from apps.stock.models import Produit

        for nom, sku in (('Structure acier toiture', 'STR-AC'), ('Structure aluminium toiture', 'STR-AL')):
            Produit.objects.create(company=company, nom=nom, sku=f'{sku}-{company.pk}',
                                   prix_vente=Decimal('300'), prix_achat=Decimal('1'), quantite_stock=100)

    def _fiches_ci(self, company):
        from apps.stock.models import FicheTechnique

        FicheTechnique.objects.filter(company=company, type_fiche='module').update(
            noct_c=Decimal('45'), temp_coeff_voc_pct_c=Decimal('-0.250'),
            temp_coeff_pmax_pct_c=Decimal('-0.300'))

    def _cas(self, nom):
        """``(company, lead)`` du golden ``nom`` — UNE fabrique, lue par les
        goldens ET par la parité du moteur unique (``MoteurUniqueTests``)."""
        f = Decimal('1800')

        def _puis(paire, completer):
            completer(paire[0])
            return paire
        cas = {
            'res_facture_dirhams': lambda: self._residentiel(facture_hiver=f),
            'res_kwh_declare_ete_different': lambda: self._residentiel(
                facture_hiver=f, facture_ete=Decimal('2600'), ete_differente=True,
                conso_mensuelle_kwh=Decimal('700'), occupation_jour='present'),
            'res_batterie_avec': lambda: self._residentiel(facture_hiver=Decimal('2500'), batterie_souhaitee='avec'),
            'res_batterie_sans': lambda: self._residentiel(facture_hiver=Decimal('2500'), batterie_souhaitee='sans'),
            'ci_commercial': lambda: self._ci(conso_mensuelle_kwh=Decimal('6000')),
            'ci_commercial_deux_options': lambda: self._ci(batteries=True, boulangerie=True),
            'ci_industriel': lambda: self._ci(
                conso_mensuelle_kwh=Decimal('20000'), type_installation='industriel',
                categorie_commerciale=None, jours_ouverture=[1, 2, 3, 4, 5, 6], heure_debut=7, heure_fin=19),
            'agr_pompe_courbe': lambda: self._agricole(),
            'agr_pompe_existante': lambda: self._agricole(existante=True),
            'res_conception_electrique': lambda: _puis(self._residentiel(facture_hiver=f),
                                                       self._fiches_residentielles),
            'res_taille_souhaitee': lambda: self._residentiel(facture_hiver=f, taille_souhaitee_kwc=Decimal('4.40')),
            'res_contour_plafond': lambda: self._residentiel(facture_hiver=f, **CONTOUR_CLIENT),
            'res_structure_alu': lambda: _puis(self._residentiel(facture_hiver=f, structure_pref='aluminium'),
                                               self._structures),
            'res_site_isole': self._site_isole,
            'ci_taille_souhaitee': lambda: self._ci(conso_mensuelle_kwh=Decimal('6000'),
                                                    taille_souhaitee_kwc=Decimal('30')),
            'ci_fiches_completes': lambda: _puis(self._ci(conso_mensuelle_kwh=Decimal('6000')), self._fiches_ci),
            'journal_taille_souhaitee': lambda: self._residentiel(facture_hiver=f,
                                                                  taille_souhaitee_kwc=Decimal('4.40')),
            'journal_taille_cible': lambda: self._residentiel(facture_hiver=f),
            'journal_site_isole': self._site_isole,
            'journal_site_isole_sans': lambda: self._site_isole(batterie_souhaitee='sans'),
            'journal_contour_plafond': lambda: self._residentiel(facture_hiver=f, **CONTOUR_CLIENT),
        }
        return cas[nom]()

    def _golden(self, nom):
        return self._figer(nom, *self._cas(nom), **APPELS_FIGEAGE.get(nom, {}))

    # ── capture / comparaison ───────────────────────────────────────────────
    def _figer(self, nom, company, lead, *, journal=False, **appel):
        """``journal`` : l'appel porte un ``journal_auto`` (dict, comme le
        tunnel et ``POST devis/auto/``) ; le golden fige alors son contenu
        final ET la liste d'alertes que l'appelant rend (``views/devis.py`` :
        ``list(journal.get('alertes') or [])``)."""
        import os

        from apps.ventes.services import build_devis_auto

        journal_auto = {} if journal else None
        if journal:
            appel['journal_auto'] = journal_auto
        devis = build_devis_auto(lead=lead, user=self._utilisateur(company), company=company, **appel)
        photo = _photo_du_devis(devis)
        if journal:
            photo['journal_auto'] = _normaliser_figeage(journal_auto)
            photo['alertes_appelant'] = _normaliser_figeage(list(journal_auto.get('alertes') or []))
        photo = json.loads(json.dumps(photo, default=str))
        self.assertEqual(_cles_interdites(photo), [], "prix d'achat ou marge dans le golden")
        fichier = DOSSIER_FIGEAGE / f'{nom}.json'
        if os.environ.get('UPDATE_GOLDEN') == '1':
            DOSSIER_FIGEAGE.mkdir(parents=True, exist_ok=True)
            fichier.write_text(json.dumps(photo, indent=1, sort_keys=True, ensure_ascii=False) + '\n',
                               encoding='utf-8')
        self.assertTrue(fichier.is_file(), f'golden {nom} absent : capturer avec UPDATE_GOLDEN=1')
        ecarts = _ecarts_figeage(json.loads(fichier.read_text(encoding='utf-8')), photo)
        self.assertEqual(ecarts, [], f'{nom} : ce que build_devis_auto écrit a changé :\n'
                                     + '\n'.join(ecarts[:40]))
        return photo

    def test_residentiel_facture_en_dirhams_seule(self):
        photo = self._golden('res_facture_dirhams')
        self.assertIn('etude_horaire', photo['etude_params'])
        self.assertIn('dimensionnement', photo['etude_params'])
        # Le golden n'est pas vide : lignes et totaux réellement figés.
        self.assertTrue(photo['lignes'])
        self.assertGreater(float(photo['champs_devis']['total_ttc']), 0)

    def test_residentiel_kwh_declare_ete_different(self):
        self._golden('res_kwh_declare_ete_different')

    def test_residentiel_batterie_souhaitee_avec(self):
        self._golden('res_batterie_avec')

    def test_residentiel_batterie_souhaitee_sans(self):
        self._golden('res_batterie_sans')

    def test_commercial(self):
        photo = self._golden('ci_commercial')
        self.assertIn('etude_ci', photo['etude_params'])

    def test_commercial_deux_options_batterie(self):
        self._golden('ci_commercial_deux_options')

    def test_industriel(self):
        self._golden('ci_industriel')

    def test_agricole_pompe_a_courbe(self):
        photo = self._golden('agr_pompe_courbe')
        self.assertTrue(any((li['produit_nom'] or '').startswith('Pompe') for li in photo['lignes']))

    def test_creation_complete_ne_lit_que_des_colonnes_connues(self):
        """Point 2 (ADEV133) : toute colonne du lead lue pendant UN
        ``build_devis_auto`` complet est une entrée du moteur
        (``CHAMPS_ENTREES[marche]``), une provenance, ou sert la seule
        RÉSOLUTION DU CLIENT / l'auteur (``LUES_POUR_LE_CLIENT``, jamais un
        chiffre), ou le TAMPON de provenance du devis
        (``crm.fiche_selectors.LEAD_PROVENANCE_FIELDS``, recopié sans calcul) —
        sinon la relance du moteur manquerait ce champ."""
        from apps.ventes.conception.champs import CHAMPS_LUS_HORS_ENTREES, champs_pour

        cas = (('residentiel', self._residentiel(facture_hiver=Decimal('1800'))),
               ('commercial', self._ci(conso_mensuelle_kwh=Decimal('6000'))),
               ('agricole', self._agricole()))
        for marche, (company, lead) in cas:
            with self.subTest(marche=marche):
                lues, hors_calcul = self._lectures_de_la_creation(company, lead)
                self.assertIn('type_installation', lues)
                # Les lecteurs hors calcul lisent bien (l'exclusion n'est pas muette).
                self.assertIn('nom', hors_calcul)
                hors = (lues - set(champs_pour(marche)) - set(CHAMPS_LUS_HORS_ENTREES)
                        - COLONNES_LUES_SANS_CHIFFRE)
                self.assertEqual(hors, set(), f'{marche} : {sorted(hors)}')

    def _lectures_de_la_creation(self, company, lead):
        """``(colonnes lues par le calcul, colonnes lues par un lecteur hors
        calcul)`` pendant un ``build_devis_auto`` complet. Le lecteur est
        identifié par la PILE (jamais par le nom de la colonne) : une colonne
        lue À LA FOIS par le tampon et par le calcul compte pour le calcul."""
        import sys

        from apps.crm.models import Lead
        from apps.ventes.services import build_devis_auto

        user = self._utilisateur(company)
        colonnes = {f.attname: f.name for f in Lead._meta.concrete_fields}
        colonnes.update({f.name: f.name for f in Lead._meta.concrete_fields})
        lues, hors_calcul = set(), set()
        lecture = object.__getattribute__

        def espion(instance, nom):
            if nom in colonnes:
                cadre, profondeur = sys._getframe(1), 0
                while cadre is not None and profondeur < 60:
                    if cadre.f_code.co_name in LECTEURS_HORS_CALCUL:
                        hors_calcul.add(colonnes[nom])
                        break
                    cadre, profondeur = cadre.f_back, profondeur + 1
                else:
                    lues.add(colonnes[nom])
            return lecture(instance, nom)

        with mock.patch.object(Lead, '__getattribute__', espion):
            build_devis_auto(lead=lead, user=user, company=company)
        return lues, hors_calcul

    def test_agricole_pompe_existante(self):
        photo = self._golden('agr_pompe_existante')
        self.assertFalse(any((li['produit_nom'] or '').startswith('Pompe') for li in photo['lignes']))

    # ── ADEV160 (préalable) — les chemins que les neuf cas ne traversent pas ──
    def test_residentiel_conception_electrique_rangee(self):
        """Fiches complètes ⇒ ``electrical_design`` rangé (chaînes, verdict
        d'onduleur) : le seul cas où le golden fige la conception électrique."""
        photo = self._golden('res_conception_electrique')
        self.assertIsNotNone(photo['electrical_design'])

    def test_residentiel_taille_souhaitee_de_la_fiche(self):
        """``taille_souhaitee_kwc`` souveraine : aucun moteur ne dimensionne."""
        photo = self._golden('res_taille_souhaitee')
        panneaux = sum(float(li['quantite']) for li in photo['lignes']
                       if (li['produit_nom'] or '').startswith('Panneau'))
        self.assertEqual(panneaux, 7)  # ⌈4 400 / 710⌉ : le compte du panneau de dimensionnement

    def test_residentiel_contour_du_client_et_plafond_du_toit(self):
        """Tracé du client (zone du calepinage) + plafond physique passé par le
        tunnel (``plafond_toit``) qui RÉDUIT le compte du moteur (11 → 8)."""
        photo = self._golden('res_contour_plafond')
        self.assertTrue(photo['champs_devis']['roof_layout'].get('outline'))
        panneaux = sum(float(li['quantite']) for li in photo['lignes']
                       if (li['produit_nom'] or '').startswith('Panneau'))
        self.assertEqual(panneaux, 8)

    def test_residentiel_structure_aluminium_du_lead(self):
        """``structure_pref`` du lead (STKCAT9) : la structure aluminium est
        composée, jamais l'acier par défaut."""
        photo = self._golden('res_structure_alu')
        noms = [li['produit_nom'] for li in photo['lignes']]
        self.assertIn('Structure aluminium toiture', noms)
        self.assertNotIn('Structure acier toiture', noms)

    def test_residentiel_site_isole(self):
        """Raccordement « aucun » : onduleur autonome + batterie, option unique."""
        photo = self._golden('res_site_isole')
        self.assertTrue(any('autonome' in (li['produit_nom'] or '') for li in photo['lignes']))

    def test_commercial_taille_souhaitee(self):
        """C&I : la taille souhaitée de la fiche est SOUVERAINE (taille explicite)."""
        self._golden('ci_taille_souhaitee')

    def test_commercial_fiches_completes(self):
        """C&I aux fiches complètes (coefficients de température du module) :
        la conception électrique est rangée. Les chaînes de l'étude C&I, elles,
        restent nulles à la création (``etude_ci._combinaison_imposee`` : le
        rafraîchisseur étudie les onduleurs DES LIGNES)."""
        photo = self._golden('ci_fiches_completes')
        self.assertIsNotNone(photo['electrical_design'])
        self.assertIsNone(photo['etude_params']['etude_ci']['composition']['onduleurs']['chaines'])

    # ── Le JOURNAL de la décision résidentielle (seul mécanisme que
    # l'extraction ADEV160 a changé : alertes et clés notées par la décision
    # pure, versées ensuite au journal de l'appelant). Capturés sur le code de
    # création d'AVANT l'extraction (ef400a21f8). ───────────────────────────────
    def _codes(self, photo):
        return [a['code'] for a in photo['alertes_appelant']]

    def test_journal_taille_souhaitee_de_la_fiche(self):
        photo = self._golden('journal_taille_souhaitee')
        self.assertIn('taille_demandee', self._codes(photo))
        self.assertEqual(photo['journal_auto']['alertes'], photo['alertes_appelant'])

    def test_journal_taille_cible_du_devis(self):
        photo = self._golden('journal_taille_cible')
        self.assertIn('taille_demandee', self._codes(photo))

    def test_journal_site_isole_sans_choix_explicite(self):
        """Hors réseau sans « sans » explicite : batterie d'office, AUCUNE alerte
        ``batterie_hors_reseau`` (elle ne dit qu'un choix écarté)."""
        photo = self._golden('journal_site_isole')
        self.assertNotIn('batterie_hors_reseau', self._codes(photo))

    def test_journal_site_isole_sans_explicite(self):
        photo = self._golden('journal_site_isole_sans')
        self.assertIn('batterie_hors_reseau', self._codes(photo))

    def test_journal_contour_et_plafond_du_toit(self):
        """Clés lues par la note du tunnel : ``contour_client``,
        ``plafond_applique``, ``panneaux_avant_plafond``."""
        photo = self._golden('journal_contour_plafond')
        self.assertEqual((photo['journal_auto']['plafond_applique'],
                          photo['journal_auto']['contour_client']), (8, 4))
        self.assertGreater(photo['journal_auto']['panneaux_avant_plafond'], 8)


def _ecritures(requetes):
    """Les requêtes d'ÉCRITURE capturées (un pipeline pur n'en émet aucune),
    blancs et commentaires SQL de tête ignorés."""
    import re

    tete = re.compile(r'^(?:\s+|/\*.*?\*/|--[^\n]*(?:\n|$))*', re.S)
    return [q['sql'][:160] for q in requetes.captured_queries
            if tete.sub('', q['sql'], count=1).upper().startswith(('INSERT', 'UPDATE', 'DELETE', 'MERGE'))]


def _json(valeur):
    return json.loads(json.dumps(valeur, default=str, sort_keys=True))


def _reglages_de_la_societe(company):
    """Les singletons de réglages société naissent à leur PREMIÈRE lecture
    (``TariffSettings.get`` : ``get_or_create``) — une lecture de réglage, pas
    une écriture du pipeline : matérialisés AVANT la capture."""
    from apps.parametres.models import CompanyProfile
    from apps.parametres.models_tariff import TariffSettings

    TariffSettings.get(company=company)
    # ADEV133 — le profil société naît aussi à sa première lecture
    # (``creation.devise_par_defaut`` : ``CompanyProfile.get``).
    CompanyProfile.get(company=company)


class PipelinePurTests(_emprunt(FigeageDevisAutoTests, 'setUp', '_patcher', '_utilisateur',
                                '_residentiel', '_ci', '_agricole'), TestCase):
    """ADEV160 — le pipeline PUR extrait du devis automatique : les décisions
    des trois marchés et les moitiés « calcul » des études, PAR LIGNES. Elles
    n'écrivent rien, et des lignes passées en argument ne sont jamais relues
    en base (la parité avec le devis écrit est celle des goldens ci-dessus)."""

    def _panneaux_du_golden(self, nom):
        golden = json.loads((DOSSIER_FIGEAGE / f'{nom}.json').read_text(encoding='utf-8'))
        return sum(float(li['quantite']) for li in golden['lignes']
                   if (li['produit_nom'] or '').startswith('Panneau'))

    def test_decisions_des_trois_marches_sans_aucune_ecriture(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        from apps.ventes.conception.decisions import (
            decider_agricole, decider_ci, decider_taille_residentielle, etude_params_creation_ci,
            verifier_composition_residentielle)

        company, lead = self._residentiel(facture_hiver=Decimal('1800'))
        _reglages_de_la_societe(company)
        with CaptureQueriesContext(connection) as requetes:
            decision = decider_taille_residentielle(lead=lead, company=company)
            structure = verifier_composition_residentielle(decision, lead=lead, company=company)
        self.assertEqual(_ecritures(requetes), [])
        self.assertEqual((decision.source, decision.deux_options, structure),
                         ('moteur_horaire', True, (None, 'acier')))
        self.assertEqual(decision.panneaux, self._panneaux_du_golden('res_facture_dirhams'))

        company, lead = self._ci(conso_mensuelle_kwh=Decimal('6000'))
        _reglages_de_la_societe(company)
        with CaptureQueriesContext(connection) as requetes:
            etude, lignes, scenario = decider_ci(lead=lead, company=company)
            entrees = etude_params_creation_ci(etude, mode=lead.type_installation, scenario=scenario)
        self.assertEqual(_ecritures(requetes), [])
        self.assertEqual(sum(float(li['quantite']) for li in lignes if li['designation'].startswith('Panneau')),
                         self._panneaux_du_golden('ci_commercial'))
        self.assertEqual(entrees['mode'], 'commercial')

        company, lead = self._agricole()
        _reglages_de_la_societe(company)
        with CaptureQueriesContext(connection) as requetes:
            agricole = decider_agricole(lead=lead, company=company)
        self.assertEqual(_ecritures(requetes), [])
        golden = json.loads((DOSSIER_FIGEAGE / 'agr_pompe_courbe.json').read_text(encoding='utf-8'))
        self.assertEqual([li['designation'] for li in agricole.lignes],
                         [li['designation'] for li in golden['lignes']])

    def _devis_et_lignes(self, company, lead):
        from apps.ventes.models import Devis
        from apps.ventes.services import build_devis_auto

        devis = build_devis_auto(lead=lead, user=self._utilisateur(company), company=company)
        # Même un devis ACCEPTÉ : le calcul par lignes ne le modifie jamais.
        Devis.objects.filter(pk=devis.pk).update(statut='accepte')
        devis.refresh_from_db()
        return devis, list(devis.lignes.select_related('produit', 'produit__fiche_technique').all())

    def _par_lignes(self, devis, calcul):
        """``calcul()`` sous capture : aucune écriture, aucune lecture des lignes."""
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        from apps.ventes.models import LigneDevis

        avant = (devis.statut, _json(devis.etude_params))
        with CaptureQueriesContext(connection) as requetes:
            resultat = calcul()
        self.assertEqual(_ecritures(requetes), [])
        table = LigneDevis._meta.db_table
        self.assertEqual([q['sql'][:120] for q in requetes.captured_queries if table in q['sql']], [])
        devis.refresh_from_db()
        self.assertEqual((devis.statut, _json(devis.etude_params)), avant)
        return resultat

    def test_etudes_residentielles_par_lignes_egales_au_devis_ecrit(self):
        from apps.ventes.conception.etudes_lignes import (
            avec_lignes, blocs_horaires_des_lignes, dimensionnement_des_lignes, puissances_des_lignes)
        from apps.ventes.domain.etudes import puissances_etude_horaire

        devis, lignes = self._devis_et_lignes(*self._residentiel(
            facture_hiver=Decimal('1800'), facture_ete=Decimal('2600'), ete_differente=True,
            conso_mensuelle_kwh=Decimal('700'), occupation_jour='present'))

        def calcul():
            kwc, kwc_sans = puissances_des_lignes(devis, lignes)
            return ((kwc, kwc_sans),
                    blocs_horaires_des_lignes(devis, lignes, kwc=kwc, kwc_sans=kwc_sans),
                    dimensionnement_des_lignes(devis, lignes, force=True))
        puissances, (bloc, bloc_sans), (etat, dimensionnement) = self._par_lignes(devis, calcul)
        self.assertEqual(puissances, puissances_etude_horaire(devis))
        self.assertIsNotNone(puissances[1], 'cas L-2OPT divergent attendu (deux blocs)')
        etude = devis.etude_params
        self.assertEqual(_json(bloc), _json(etude['etude_horaire']))
        self.assertEqual(_json(bloc_sans), _json(etude['etude_horaire_sans']))
        self.assertEqual((etat, _json(dimensionnement)), ('calcule', _json(etude['dimensionnement'])))
        with self.assertRaises(AttributeError):
            avec_lignes(devis, lignes).statut = 'brouillon'

    def test_etude_ci_par_lignes_egale_au_chemin_du_devis(self):
        from apps.ventes.conception.etudes_lignes import etude_ci_calculee, preparation_etude_ci

        devis, lignes = self._devis_et_lignes(*self._ci(batteries=True, boulangerie=True))

        def calcul():
            preparation = preparation_etude_ci(devis, lignes)
            return preparation, etude_ci_calculee(devis, preparation, lignes)
        preparation, (_etude, bloc) = self._par_lignes(devis, calcul)
        attendu = preparation_etude_ci(devis)
        self.assertIsNotNone(preparation['imposee'], 'option « avec » des lignes attendue')
        self.assertEqual(preparation['empreinte'], attendu['empreinte'])
        self.assertEqual(preparation['empreinte'], devis.etude_params['etude_ci']['empreinte'])
        self.assertEqual(_json(bloc), _json(etude_ci_calculee(devis, attendu)[1]))

    def test_etude_pompage_par_lignes_egale_au_chemin_du_devis(self):
        from apps.ventes.conception.etudes_lignes import etude_pompage_des_lignes

        devis, lignes = self._devis_et_lignes(*self._agricole())
        derivees, _a_ecrire = self._par_lignes(
            devis, lambda: etude_pompage_des_lignes(devis, lignes, force=True))
        self.assertEqual(derivees['provenance_pompage']['_empreinte'],
                         devis.etude_params['provenance_pompage']['_empreinte'])
        self.assertEqual(_json(derivees), _json(etude_pompage_des_lignes(devis, force=True)[0]))


# ── ADEV133 — le point d'entrée unique, sans écriture, à PARITÉ des goldens ───
#
# Pour chaque golden de ``FigeageDevisAutoTests`` (même fabrique ``_cas``),
# ``calculer_conception`` rend, sans une requête d'écriture, l'``etude_params``,
# les lignes (taille, matériel, prix) et la conception électrique que
# ``build_devis_auto`` a écrits — clé par clé, la première clé fautive nommée.
# Le plafond du toit que passe le tunnel voyage par ``toit.plafond_panneaux``.

#: Goldens HORS parité, avec la raison (aucun n'est « assoupli ») :
HORS_PARITE = {
    'journal_taille_cible': ("``target_kwc`` est une demande POUR UN devis (corps de POST devis/auto/), "
                             "pas une entrée du lead : le moteur ne la prend pas (tâche ADEV150, pose souveraine)."),
}
PARITE = tuple(sorted({n.stem for n in DOSSIER_FIGEAGE.glob('*.json')} - set(HORS_PARITE)))


def _photo_des_lignes(lignes):
    """Les lignes NON enregistrées du moteur à la forme du golden (décimaux à
    la précision de leur colonne, comme relus en base)."""
    from django.db import models

    from apps.ventes.models import LigneDevis

    photos = []
    for ligne in sorted(lignes, key=lambda li: li.ordre):
        photo = {}
        for nom in CHAMPS_LIGNE_FIGES:
            valeur, champ = getattr(ligne, nom), LigneDevis._meta.get_field(nom)
            if valeur is not None and isinstance(champ, models.DecimalField):
                valeur = Decimal(valeur).quantize(Decimal(1).scaleb(-champ.decimal_places))
            photo[nom] = valeur
        photo['produit_nom'] = getattr(ligne.produit, 'nom', None)
        photos.append(photo)
    return photos


class MoteurUniqueTests(_emprunt(FigeageDevisAutoTests, 'setUp', '_patcher', '_utilisateur', '_residentiel',
                                 '_ci', '_agricole', '_fiches_residentielles', '_site_isole', '_structures',
                                 '_fiches_ci', '_cas'), TestCase):
    """ADEV133 — ``calculer_conception`` : un appel par marché, aucune écriture,
    parité avec ce que le devis automatique écrit ; refus nommé sans lieu."""

    def _calculer(self, company, lead, **kw):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        from apps.ventes.conception.moteur import calculer_conception

        _reglages_de_la_societe(company)
        with CaptureQueriesContext(connection) as requetes:
            resultat = calculer_conception(lead, company, **kw)
        self.assertEqual(_ecritures(requetes), [], 'le moteur a écrit en base')
        return resultat

    def _parite(self, nom):
        from types import SimpleNamespace

        from apps.ventes.domain.creation_auto import cles_rapides

        appel = APPELS_FIGEAGE.get(nom, {})
        company, lead = self._cas(nom)
        toit = (SimpleNamespace(empreinte='', plafond_panneaux=appel['plafond_toit'])
                if 'plafond_toit' in appel else None)
        resultat = self._calculer(company, lead, toit=toit)
        self.assertEqual((resultat.etat, resultat.absents), ('complet', {}), resultat.refus)
        etude_params = dict(resultat.etude_params)
        if appel.get('journal'):  # un appelant À JOURNAL fait ranger ses suppositions
            etude_params.update(cles_rapides(resultat.journal))
        photo = {'etude_params': etude_params, 'lignes': _photo_des_lignes(resultat.lignes),
                 'electrical_design': resultat.conception_electrique}
        if appel.get('journal'):
            photo.update(journal_auto=resultat.journal, alertes_appelant=list(resultat.journal.get('alertes') or []))
        golden = json.loads((DOSSIER_FIGEAGE / f'{nom}.json').read_text(encoding='utf-8'))
        ecarts = _ecarts_figeage({cle: golden[cle] for cle in photo},
                                 json.loads(json.dumps(_normaliser_figeage(photo), default=str)))
        self.assertEqual(ecarts, [], f'{nom} : le moteur diffère du devis automatique, première clé : '
                                     f'{ecarts[0] if ecarts else ""}\n' + '\n'.join(ecarts[:20]))
        self._forme_du_contrat(resultat)
        return resultat

    def _forme_du_contrat(self, resultat):
        sortie = resultat.sortie()
        self.assertEqual(set(sortie), CLES_RESULTAT)
        self.assertEqual(_cles_interdites(_json(sortie)) + _cles_interdites(_json(resultat.etude_params))
                         + _cles_interdites(_json(resultat.conception_electrique))
                         + _cles_interdites(_json(resultat.journal)), [])
        self.assertIn(resultat.option_retenue, sortie['valeurs'])
        attendues = VALEURS_POMPAGE if resultat.marche == 'agricole' else VALEURS_SOLAIRES
        for option, valeurs in sortie['valeurs'].items():
            self.assertEqual(set(valeurs), attendues, option)
            for cle, valeur in valeurs.items():
                self.assertEqual(set(valeur), CLES_VALEUR, cle)
                self.assertIn(valeur['source'], SOURCES_VALEUR, cle)
        self.assertEqual(len(sortie['empreinte']), 64)

    def test_un_lead_sans_ville_ni_gps_est_refuse_nomme(self):
        company, lead = self._residentiel(facture_hiver=Decimal('1800'), ville='')
        resultat = self._calculer(company, lead)
        self.assertEqual((resultat.etat, resultat.refus['code'], resultat.refus['champ']),
                         ('refus', 'localisation_inconnue', 'ville'))
        self.assertEqual((resultat.valeurs, resultat.blocs, resultat.lignes), ({}, {}, []))
        self.assertEqual(set(resultat.refus), CLES_REFUS)

    def test_un_refus_du_devis_automatique_est_nomme(self):
        company, lead = self._residentiel()  # aucune consommation déclarée
        resultat = self._calculer(company, lead)
        self.assertEqual((resultat.etat, resultat.refus['code']), ('refus', 'refus_moteur'))
        self.assertTrue(resultat.refus['message'])

    def test_e6d_refus_ci_nomme_l_heure_de_fin_quand_le_debut_est_saisi(self):
        """Écart 5 de l'acceptation du 25/11 — lead commercial sans activité, jours saisis :
        sans aucune heure, le refus nomme ``heure_debut`` ; heure de début saisie et fin
        absente, il nomme ``heure_fin`` (mutant « toujours heure_debut » : rouge)."""
        from apps.ventes.conception.decisions import MESSAGE_HEURE_FIN

        commun = dict(conso_mensuelle_kwh=Decimal('6000'), categorie_commerciale=None, jours_ouverture=[1, 2, 3, 4, 5])
        company, sans_heure = self._ci(**commun)
        refus = self._calculer(company, sans_heure).refus
        self.assertEqual((refus['code'], refus['champ']), ('refus_moteur', 'heure_debut'))
        type(sans_heure).objects.filter(pk=sans_heure.pk).update(heure_debut=8)
        sans_heure.refresh_from_db()
        refus = self._calculer(company, sans_heure).refus
        self.assertEqual((refus['code'], refus['champ'], refus['message']), ('refus_moteur', 'heure_fin',
                                                                             MESSAGE_HEURE_FIN))

    def test_acal2020_forme_horaire_24_du_moteur_residentiel(self):
        """Reste d'ACAL2020 — la forme 24 h de la consommation que le moteur horaire a utilisée
        est SERVIE (24 parts de somme 1, source de ``forme_horaire``), la même pour chaque option,
        jamais uniforme ; hors résidentiel : ``None``."""
        company, lead = self._residentiel(facture_hiver=Decimal('1800'))
        resultat = self._calculer(company, lead)
        self.assertEqual((resultat.etat, resultat.absents), ('complet', {}), resultat.refus)
        formes = {option: v['forme_horaire_24'] for option, v in resultat.valeurs.items()}
        for option, forme in formes.items():
            self.assertEqual(len(forme['valeur']), 24, option)  # mutant « clé absente » : rouge
            self.assertAlmostEqual(sum(forme['valeur']), 1.0, places=4)
            self.assertEqual((forme['unite'], forme['source']),
                             ('part', resultat.valeurs[option]['forme_horaire']['source']))
            self.assertGreater(max(forme['valeur']) - min(forme['valeur']), 0.01)  # jamais uniforme
        self.assertEqual(len({tuple(f['valeur']) for f in formes.values()}), 1)
        self.assertEqual(formes[resultat.option_retenue]['valeur'], resultat.forme_horaire_24)

    def test_une_autre_societe_n_obtient_rien(self):
        from authentication.models import Company

        company, lead = self._residentiel(facture_hiver=Decimal('1800'))
        autre = Company.objects.create(nom='Autre moteur', slug='autre-moteur-unique')
        with self.assertRaises(ValueError):
            self._calculer(autre, lead)

    def test_un_devis_accepte_du_lead_n_est_pas_touche(self):
        from apps.ventes.models import Devis
        from apps.ventes.services import build_devis_auto

        company, lead = self._cas('res_facture_dirhams')
        devis = build_devis_auto(lead=lead, user=self._utilisateur(company), company=company)
        Devis.objects.filter(pk=devis.pk).update(statut='accepte')
        avant = _json(Devis.objects.filter(pk=devis.pk).values()[0])
        self._calculer(company, lead)
        self.assertEqual(_json(Devis.objects.filter(pk=devis.pk).values()[0]), avant)

    def test_blocs_servis_et_deux_options(self):
        resultat = self._parite('res_kwh_declare_ete_different')
        # ADEV135 — ``blocs`` = l'``etude_params`` complet du devis automatique.
        self.assertEqual(resultat.blocs, resultat.etude_params)
        self.assertLessEqual({'etude_horaire', 'etude_horaire_sans', 'dimensionnement', 'profils_comparatifs',
                              'puissance_kwc', 'ville_calcul', 'origine_conception'}, set(resultat.blocs))
        self.assertEqual(set(resultat.valeurs), {'sans', 'avec'})
        self.assertNotEqual(resultat.valeurs['sans']['puissance_kwc'], resultat.valeurs['avec']['puissance_kwc'])
        # Relecture E5 m4 — le matériel est nommé par l'IDENTIFIANT de sa ligne, jamais par son nom.
        from apps.ventes.domain.catalogue import classer_produit
        for option, valeurs in resultat.valeurs.items():
            with self.subTest(option=option):
                lignes = {classer_produit(li.produit.nom): li.produit_id for li in resultat.lignes
                          if li.produit_id and (li.variante or '') in ('', option) and not li.optionnelle}
                self.assertEqual(valeurs['module_produit']['valeur'], lignes['panneau'])
                self.assertEqual(valeurs['onduleur_produit']['valeur'], valeurs['onduleurs']['valeur'][0]['produit'])
                self.assertEqual(valeurs['batterie_produit']['valeur'], lignes.get('batterie'))
        self.assertIsNotNone(resultat.valeurs['avec']['batterie_produit']['valeur'])

    def test_verdicts_non_calcules_disent_la_fiche_a_completer(self):
        # Relecture E6 (acceptation, copie anonymisée) — catalogue sans fiche électrique : chaînes, tension,
        # ratio null ; le verdict ne passe JAMAIS pour « conforme », il nomme le champ et où le remplir.
        resultat = self._parite('res_kwh_declare_ete_different')
        for option, valeurs in resultat.valeurs.items():
            with self.subTest(option=option):
                self.assertIsNone(valeurs['chaines']['valeur'])
                verdicts = valeurs['verdicts']['valeur']
                self.assertEqual((verdicts['ratio_dc_ac'], verdicts['capacite_hybride'],
                                  verdicts['longueur_chaine']), (None, None, None))
                self.assertIn('non renseigné(e) sur la fiche technique', verdicts['non_calcule'])
                self.assertIn('Stock → Catalogue', verdicts['non_calcule'])

    def test_verdicts_ranges_pour_l_option_de_la_conception_electrique(self):
        # ACAL2016 — l'option dont la conception électrique porte l'onduleur porte ses verdicts rangés.
        resultat = self._parite('res_conception_electrique')
        portees = [o for o, v in resultat.valeurs.items() if v['chaines']['valeur']]
        self.assertTrue(portees)
        for option, valeurs in resultat.valeurs.items():
            verdicts = valeurs['verdicts']['valeur']
            if option not in portees:
                self.assertIsNone(verdicts['ratio_dc_ac'])
                self.assertIn("l'autre option", verdicts['non_calcule'])
                continue
            self.assertEqual(set(verdicts), {'ratio_dc_ac', 'capacite_hybride', 'longueur_chaine', 'non_calcule'})
            self.assertIsNone(verdicts['non_calcule'])
            self.assertEqual(verdicts['ratio_dc_ac']['valeur'], valeurs['ratio_dc_ac']['valeur'])
            self.assertIsInstance(verdicts['ratio_dc_ac']['conforme'], bool)

    # ── ADEV134 — chaque supposition sort avec le champ de la fiche ─────────
    def _suppositions(self, resultat):
        for sup in resultat.suppositions:
            self.assertEqual(set(sup), CLES_SUPPOSITION, sup)
            self.assertTrue(sup['champ'] and sup['message'], sup)  # mutant « champ retiré » : rouge
            self.assertEqual(sup['source'], 'defaut', sup)
        json.dumps(resultat.suppositions)
        return {sup['code']: (sup['champ'], sup['valeur']) for sup in resultat.suppositions}

    def test_suppositions_residentiel_sans_presence_ni_ete(self):
        from apps.parametres.pvgis_profils import PVGIS_ANGLE_DEG, PVGIS_ASPECT_DEG
        from apps.ventes.domain.creation_auto_residentiel import SUPPOSITIONS_RESIDENTIEL
        from core.electrique.types import TEMP_FROID_DEFAUT_C

        resultat = self._calculer(*self._cas('res_facture_dirhams'))
        dites = self._suppositions(resultat)
        self.assertEqual({code: champ for code, (champ, _v) in dites.items()},
                         {'suppose_presence': 'occupation_jour', 'suppose_ete_egal_hiver': 'facture_ete',
                          'suppose_kwh_depuis_facture': 'conso_mensuelle_kwh',
                          'suppose_30_plein_sud': 'inclinaison_deg', 'froid_suppose': 'gps_lat'})
        self.assertEqual(dites['suppose_presence'][1], 'presence_jour')
        self.assertEqual(dites['suppose_ete_egal_hiver'][1], 1800.0)
        # La valeur RETENUE à la place : la consommation MENSUELLE du calcul
        # (golden : 12 × 1 022,9 kWh), le plan de la production par ville, le froid.
        self.assertEqual(dites['suppose_kwh_depuis_facture'][1], 1022.9)
        self.assertEqual(dites['suppose_30_plein_sud'][1],
                         {'inclinaison_deg': PVGIS_ANGLE_DEG, 'azimut_deg': PVGIS_ASPECT_DEG})
        self.assertEqual(dites['froid_suppose'][1], TEMP_FROID_DEFAUT_C)
        self.assertEqual(resultat.valeurs['avec']['temperature_froid']['source'], 'defaut')
        # Aucune seconde formulation : la phrase est celle du journal du devis.
        messages = {sup['code']: sup['message'] for sup in resultat.suppositions}
        self.assertEqual(messages['suppose_presence'], SUPPOSITIONS_RESIDENTIEL['occupation_jour'][1])

    def test_facture_ete_saisie_sans_ete_different_dit_de_cocher_la_case(self):
        """Relecture E5 (rejeu orchestrateur, b) — facture d'été SAISIE (900) sans « Été
        différent » : la supposition ne demande pas de la renseigner (elle l'est), elle dit
        de cocher « Été différent » pour qu'elle compte."""
        from apps.ventes.domain.creation_auto_residentiel import SUPPOSITIONS_RESIDENTIEL

        resultat = self._calculer(*self._residentiel(facture_hiver=Decimal('1800'), facture_ete=Decimal('900')))
        messages = {sup['code']: sup['message'] for sup in resultat.suppositions}
        self.assertEqual(messages['suppose_ete_egal_hiver'],
                         "Facture d'été saisie (900 MAD) mais non prise en compte : cochez « Été différent » "
                         "sur la fiche pour qu'elle compte (sinon l'été est supposé égal à l'hiver).")
        self.assertNotEqual(messages['suppose_ete_egal_hiver'], SUPPOSITIONS_RESIDENTIEL['facture_ete'][1])

    def test_suppositions_residentiel_renseigne_seule_la_production_reste_supposee(self):
        """Présence, été et kWh déclarés : plus rien de supposé sur la fiche ;
        la production à 30° plein sud reste dite (aucune pose au niveau 14)."""
        dites = self._suppositions(self._calculer(*self._cas('res_kwh_declare_ete_different')))
        self.assertEqual(set(dites), {'suppose_30_plein_sud', 'froid_suppose'})

    def test_cles_d_achat_retirees_de_tout_ce_que_le_resultat_expose(self):
        """Relecture ADEV134, point 5 : le retrait récursif (liste
        ``etude_ci.CLES_INTERDITES``) s'applique aussi à la conception
        électrique et au journal ; les lignes (instances) ne sont pas exposées."""
        from apps.ventes.conception import moteur

        resultat = moteur.ResultatConception(
            marche='residentiel', entrees_utilisees={'x': {'prix_achat': 1}}, empreinte='e' * 64, niveau_regles=14,
            journal={'alertes': [{'code': 'a', 'marge_brute': 2}]},
            conception_electrique={'materiel': {'onduleur': {'prix_achat_ht': 3, 'designation': 'O'}}},
            etude_params={'etude_ci': {'marge': 4, 'bilan': {}}})
        moteur._sans_cles_interdites_partout(resultat)
        self.assertEqual((resultat.entrees_utilisees, resultat.journal, resultat.conception_electrique,
                          resultat.etude_params),
                         ({'x': {}}, {'alertes': [{'code': 'a'}]}, {'materiel': {'onduleur': {'designation': 'O'}}},
                          {'etude_ci': {'bilan': {}}}))

    def test_suppositions_inclinaison_de_la_fiche_non_lue_reste_dite(self):
        """Relecture ADEV134, point 2 (contesté) : au niveau de règles courant,
        sans pose servie, la production résidentielle est calculée au plan de
        ``pvgis_profils`` QUELLE QUE SOIT la pente de la fiche — la taire quand
        ``inclinaison_deg`` est rempli cacherait un défaut réellement appliqué.
        Le résultat ne change pas avec la pente déclarée : preuve qu'elle n'est
        pas lue."""
        from apps.crm.models import Lead

        company, lead = self._cas('res_kwh_declare_ete_different')
        sans = self._calculer(company, lead)
        Lead.objects.filter(pk=lead.pk).update(inclinaison_deg=Decimal('15'))
        lead.refresh_from_db()
        avec = self._calculer(company, lead)
        self.assertIn('suppose_30_plein_sud', self._suppositions(avec))
        self.assertEqual(_json(avec.valeurs), _json(sans.valeurs))

    def test_sans_reglages_societe_aucune_ecriture_meme_resultat(self):
        """Relecture ADEV134, point 4 : une société sans réglages tarifaires
        ni profil — le moteur les LIT sans les créer (zéro écriture), et rend
        le même résultat qu'avec les lignes par défaut."""
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        from apps.parametres.models import CompanyProfile
        from apps.parametres.models_tariff import TariffSettings
        from apps.ventes.conception.moteur import calculer_conception

        for nom in ('res_facture_dirhams', 'ci_commercial'):
            with self.subTest(cas=nom):
                company, lead = self._cas(nom)
                TariffSettings.objects.filter(company=company).delete()
                CompanyProfile.objects.filter(company=company).delete()
                with CaptureQueriesContext(connection) as requetes:
                    sans_lignes = calculer_conception(lead, company)
                self.assertEqual(_ecritures(requetes), [], 'le moteur a écrit en base')
                self.assertFalse(TariffSettings.objects.filter(company=company).exists())
                self.assertFalse(CompanyProfile.objects.filter(company=company).exists())
                avec_lignes = self._calculer(company, lead)
                self.assertEqual(_json(sans_lignes.sortie()), _json(avec_lignes.sortie()))

    def test_suppositions_ci_sans_contrat_ni_phase_ni_tension(self):
        from apps.ventes import tarif_ci

        reel = tarif_ci.tarif_applicable  # avant le patch de la fabrique : le tarif « omis » réel
        company, lead = self._ci(conso_mensuelle_kwh=Decimal('6000'), raccordement='', tension_raccordement='')
        with mock.patch.object(tarif_ci, 'tarif_applicable', reel):
            dites = self._suppositions(self._calculer(company, lead))
        self.assertEqual(dites['supposition_contrat_electricite'], ('contrat_electricite', 'bt_patente'))
        self.assertEqual(dites['supposition_tension'], ('tension_raccordement', 'bt'))
        self.assertEqual(dites['supposition_phases'], ('raccordement', 'tri'))
        self.assertEqual(dites['profil_estime'][0], 'jours_ouverture')
        self.assertEqual(dites['supposition_inclinaison_deg'], ('gps_lat', 30))

    def test_suppositions_ci_renseigne_aucune_sur_les_champs_declares(self):
        dites = self._suppositions(self._calculer(*self._ci(
            conso_mensuelle_kwh=Decimal('6000'), jours_ouverture=[1, 2, 3, 4, 5], heure_debut=8, heure_fin=18,
            contrat_electricite='bt_patente', compteur_puissance_kva=Decimal('200'),
            equipements_hors_horaires='aucun')))
        champs = {champ for champ, _v in dites.values()}
        self.assertFalse(champs & {'contrat_electricite', 'tension_raccordement', 'raccordement',
                                   'jours_ouverture', 'heure_debut', 'compteur_puissance_kva',
                                   'equipements_hors_horaires'}, dites)

    def test_exclusions_de_parite_figees(self):
        """Relecture ADEV134 — l'exclusion de parité est VISIBLE et ne grossit pas
        en silence : exactement ``journal_taille_cible`` (raison liée à ADEV150), et
        chaque exclu reste un golden réel (renommé ou supprimé ⇒ ce test rougit)."""
        self.assertEqual(set(HORS_PARITE), {'journal_taille_cible'})
        self.assertIn('ADEV150', HORS_PARITE['journal_taille_cible'])
        for nom in HORS_PARITE:
            self.assertTrue((DOSSIER_FIGEAGE / f'{nom}.json').is_file(), f'golden exclu {nom} absent')
            self.assertNotIn(nom, PARITE)


def _test_de_parite(nom):
    def test(self):
        self._parite(nom)
    test.__doc__ = f'ADEV133 — parité du moteur unique avec le golden « {nom} ».'
    return test


# Les exclus de ``HORS_PARITE`` n'ont pas de test de parité : leur exclusion est
# prouvée par ``MoteurUniqueTests.test_exclusions_de_parite_figees``.
for _nom in PARITE:
    setattr(MoteurUniqueTests, f'test_parite_{_nom}', _test_de_parite(_nom))


# ── ADEV135 — l'écrivain unique : empreinte égale ⇒ rien, sinon version + 1 ───

class _Evenements:
    """Les ``conception_recalculee`` reçus pendant un test."""

    def __init__(self, test):
        from core.events import conception_recalculee

        self.recus = []
        conception_recalculee.connect(self._recevoir, dispatch_uid='adev135-test')
        test.addCleanup(conception_recalculee.disconnect, dispatch_uid='adev135-test')

    def _recevoir(self, sender, **kwargs):
        kwargs.pop('signal', None)
        self.recus.append(kwargs)


def _declencheur(origine='remplissage', **champs):
    return {'champs': [{'champ': c, 'avant': a, 'apres': b} for c, (a, b) in champs.items()],
            'origine': origine}


class RelanceConceptionTests(_emprunt(FigeageDevisAutoTests, 'setUp', '_patcher', '_utilisateur', '_residentiel',
                                      '_ci', '_agricole', '_fiches_residentielles', '_site_isole', '_structures',
                                      '_fiches_ci', '_cas'), TestCase):
    """ADEV135 — ``conception/service.py::relancer`` : une empreinte égale
    n'écrit rien ; une empreinte changée range la version suivante (l'ancienne
    ``courante=False``), le déclencheur avec sa phrase « pourquoi », et émet
    ``conception_recalculee`` une fois, après validation."""

    def _relancer(self, lead, company, declencheur, **kw):
        from apps.ventes.conception.service import relancer

        with self.captureOnCommitCallbacks(execute=True):
            return relancer(lead, company=company, declencheur=declencheur, **kw)

    def test_empreinte_egale_rien_puis_facture_changee_version_suivante(self):
        from django.utils import timezone

        from apps.crm.models import Lead
        from apps.ventes.models import ConceptionLead

        company, lead = self._cas('res_facture_dirhams')
        _reglages_de_la_societe(company)
        evenements = _Evenements(self)
        premiere = self._relancer(lead, company, _declencheur())
        self.assertTrue(premiere.ecrite)
        self.assertEqual((premiere.conception.version, premiere.conception.courante), (1, True))
        v1 = _json(ConceptionLead.objects.filter(pk=premiere.conception.pk).values()[0])

        meme = self._relancer(lead, company, _declencheur('manuel'))  # mutant « toujours écrire » : rouge
        self.assertEqual((meme.ecrite, meme.conception.pk), (False, premiere.conception.pk))
        self.assertEqual(ConceptionLead.objects.filter(lead=lead).count(), 1)
        self.assertEqual(len(evenements.recus), 1)

        Lead.objects.filter(pk=lead.pk).update(facture_hiver=Decimal('2400'))
        lead.refresh_from_db()
        suivante = self._relancer(lead, company, _declencheur(
            'lead_entrees_modifiees', facture_hiver=(Decimal('1800.00'), Decimal('2400.00'))))
        self.assertTrue(suivante.ecrite)
        relue = ConceptionLead.objects.get(pk=suivante.conception.pk)
        self.assertEqual((relue.version, relue.courante, relue.company_id), (2, True, company.pk))
        self.assertNotEqual(relue.empreinte, premiere.conception.empreinte)
        self.assertEqual(relue.entrees_utilisees['facture_hiver'], {'valeur': 2400.0, 'source': 'lead'})
        moment = timezone.localtime(relue.calcule_le)
        self.assertEqual(relue.declencheur, {
            'raison': 'Recalculé le %s à %d h %02d : Facture hiver 1 800 → 2 400 MAD' % (
                moment.strftime('%d/%m'), moment.hour, moment.minute),
            'champs': [{'champ': 'facture_hiver', 'avant': 1800.0, 'apres': 2400.0}],
            'origine': 'lead_entrees_modifiees'})
        # La version 1 se relit inchangée, sauf ``courante``.
        v1_relue = _json(ConceptionLead.objects.filter(pk=premiere.conception.pk).values()[0])
        self.assertEqual(v1_relue, dict(v1, courante=False))
        self.assertEqual([e['version'] for e in evenements.recus], [1, 2])
        self.assertEqual(set(evenements.recus[-1]),
                         {'company_id', 'lead_id', 'calepinage_id', 'version', 'declencheur'})
        self.assertEqual(evenements.recus[-1]['declencheur'], relue.declencheur)
        self.assertEqual(_cles_interdites(relue.valeurs) + _cles_interdites(relue.blocs), [])
        self.assertEqual(set(relue.valeurs), {'sans', 'avec'})
        self.assertEqual(relue.option_retenue, 'avec')

        forcee = self._relancer(lead, company, _declencheur('manuel'), forcer=True)
        self.assertEqual((forcee.ecrite, forcee.conception.version), (True, 3))
        self.assertTrue(forcee.conception.declencheur['raison'].endswith(' : recalcul demandé'))

    def test_relances_simultanees_des_memes_entrees_une_seule_version(self):
        """Relecture m1 — deux relances parties ensemble lisent toutes deux
        l'ancienne courante (empreinte différente) ; la seconde, qui range
        APRÈS la première, retrouve sous verrou la même empreinte : rien
        d'écrit, aucun second événement."""
        from apps.crm.models import Lead
        from apps.ventes.conception import service
        from apps.ventes.models import ConceptionLead

        company, lead = self._cas('res_facture_dirhams')
        _reglages_de_la_societe(company)
        evenements = _Evenements(self)
        self._relancer(lead, company, _declencheur())
        Lead.objects.filter(pk=lead.pk).update(facture_hiver=Decimal('2400'))
        lead.refresh_from_db()
        v1 = ConceptionLead.objects.get(lead=lead, courante=True)
        premiere = self._relancer(lead, company, _declencheur('manuel'))
        with mock.patch.object(service, '_courante', return_value=v1):  # lecture d'avant la première
            seconde = self._relancer(lead, company, _declencheur('manuel'))
        self.assertEqual((premiere.ecrite, seconde.ecrite), (True, False))  # mutant « sans relecture » : v3
        self.assertEqual(seconde.conception.pk, premiere.conception.pk)
        self.assertEqual(list(ConceptionLead.objects.filter(lead=lead).order_by('version')
                              .values_list('version', 'courante')), [(1, False), (2, True)])
        self.assertEqual([e['version'] for e in evenements.recus], [1, 2])

    def test_chaine_reelle_une_ligne_au_chatter_avec_la_phrase_exacte(self):
        """Relecture m4 — la VRAIE chaîne : facture changée → ``relancer`` →
        ``conception_recalculee`` → UNE ligne système au chatter du lead, un
        seul préfixe, l'unité dite ; une seconde livraison n'en écrit pas."""
        from apps.crm.models import Lead, LeadActivity
        from core.events import conception_recalculee

        company, lead = self._cas('res_facture_dirhams')
        _reglages_de_la_societe(company)
        self._relancer(lead, company, _declencheur())
        Lead.objects.filter(pk=lead.pk).update(facture_hiver=Decimal('2400'))
        lead.refresh_from_db()
        version = self._relancer(lead, company, _declencheur(
            'lead_entrees_modifiees', facture_hiver=(Decimal('1800'), Decimal('2400')))).conception
        lignes = LeadActivity.objects.filter(lead=lead, field='conception_version', new_value='2')
        self.assertEqual([(li.body, li.user_id) for li in lignes],
                         [('Conception recalculée : Facture hiver 1 800 → 2 400 MAD', None)])
        conception_recalculee.send(sender='ventes.ConceptionLead', company_id=company.pk, lead_id=lead.pk,
                                   calepinage_id=None, version=2, declencheur=version.declencheur)
        self.assertEqual(lignes.count(), 1)

    def test_effacement_pendant_le_calcul_rien_n_est_range(self):
        """Relecture E3 B1(b) — la relance a lu le lead, l'effacement passe
        pendant son calcul (versions supprimées) : ``ranger`` relit la ligne du
        lead sous verrou et ne range RIEN, aucun événement."""
        from apps.crm.dsr_provider import anonymiser_lead
        from apps.crm.models import Lead
        from apps.ventes.conception import moteur
        from apps.ventes.models import ConceptionLead

        company, lead = self._cas('res_facture_dirhams')
        _reglages_de_la_societe(company)
        Lead.objects.filter(pk=lead.pk).update(gps_lat=Decimal('33.5731'), gps_lng=Decimal('-7.5898'))
        lead.refresh_from_db()
        evenements = _Evenements(self)
        vrai = moteur.calculer_conception

        def calcul_puis_effacement(*args, **kwargs):
            resultat = vrai(*args, **kwargs)
            with self.captureOnCommitCallbacks(execute=True):
                anonymiser_lead(company, Lead.all_objects.get(pk=lead.pk), motif='Effacement (test B1b)')
            return resultat
        self._patcher(moteur, 'calculer_conception', side_effect=calcul_puis_effacement)
        relance = self._relancer(lead, company, _declencheur())  # le lead lu AVANT l'effacement
        self.assertEqual((relance.conception, relance.ecrite), (None, False))  # mutant « sans garde » : v1
        self.assertFalse(ConceptionLead.objects.filter(lead_id=lead.pk).exists())
        self.assertEqual(evenements.recus, [])

    def test_une_relance_plus_ancienne_ne_recouvre_pas_une_plus_recente(self):
        """Relecture E3 Q5 — A part (facture 2 000), une modification range B
        (facture 2 600) pendant le calcul de A : A ne range pas ses entrées
        plus anciennes par-dessus ; B reste courante, un seul événement."""
        import datetime

        from django.utils import timezone

        from apps.crm.models import Lead
        from apps.ventes.conception import moteur
        from apps.ventes.models import ConceptionLead

        company, lead = self._cas('res_facture_dirhams')
        _reglages_de_la_societe(company)
        self._relancer(lead, company, _declencheur())
        evenements = _Evenements(self)
        Lead.objects.filter(pk=lead.pk).update(facture_hiver=Decimal('2000'))
        lead_a = Lead.objects.get(pk=lead.pk)
        vrai = moteur.calculer_conception
        etat = {'b': False}

        def calcul_de_a(*args, **kwargs):
            resultat = vrai(*args, **kwargs)
            if not etat['b']:
                etat['b'] = True
                Lead.objects.filter(pk=lead.pk).update(facture_hiver=Decimal('2600'))
                plus_tard = timezone.now() + datetime.timedelta(seconds=1)
                with mock.patch('django.utils.timezone.now', return_value=plus_tard):
                    self._relancer(Lead.objects.get(pk=lead.pk), company, _declencheur('manuel'))
            return resultat
        self._patcher(moteur, 'calculer_conception', side_effect=calcul_de_a)
        relance_a = self._relancer(lead_a, company, _declencheur('manuel'))
        self.assertEqual((relance_a.conception, relance_a.ecrite), (None, False))  # mutant « ranger A » : v3
        courante = ConceptionLead.objects.get(lead=lead, courante=True)
        self.assertEqual((courante.version, courante.entrees_utilisees['facture_hiver']['valeur']), (2, 2600.0))
        # (B est annoncée par sa propre capture ET rejouée par celle de A, englobante.)
        self.assertEqual({e['version'] for e in evenements.recus}, {2})

    def test_chatter_muet_pour_remplissage_filet_et_regles(self):
        """Relecture E3 M3 — seule une relance causée par un changement de la
        fiche ou de la pose écrit « Conception recalculée » ; remplissage,
        filet et règles se taisent (le remplissage écrivait sur CHAQUE lead)."""
        from apps.crm.models import LeadActivity

        company, lead = self._cas('res_facture_dirhams')
        _reglages_de_la_societe(company)
        lignes = LeadActivity.objects.filter(lead=lead, field='conception_version')
        for origine in ('remplissage', 'filet', 'regles'):
            with self.subTest(origine=origine):
                relance = self._relancer(lead, company, _declencheur(origine), forcer=True)
                self.assertTrue(relance.ecrite)
                self.assertEqual(lignes.count(), 0)  # mutant « toujours écrire » : rouge
        for rang, origine in enumerate(('lead_entrees_modifiees', 'pose_enregistree'), start=1):
            with self.subTest(origine=origine):
                self._relancer(lead, company, _declencheur(origine), forcer=True)
                self.assertEqual(lignes.count(), rang)

    def test_aucune_cle_d_achat_ni_de_marge_meme_si_le_moteur_en_rendait(self):
        from types import SimpleNamespace

        from apps.ventes.conception import entrees, moteur
        from apps.ventes.conception.moteur import ResultatConception

        company, lead = self._residentiel(facture_hiver=Decimal('1800'))
        resultat = ResultatConception(
            marche='residentiel', entrees_utilisees={}, empreinte='e' * 64, niveau_regles=14,
            option_retenue='sans', valeurs={'sans': {'nb_panneaux': {'valeur': 4, 'unite': None, 'source': 'moteur',
                                                                     'marge_ht': 9}}},
            blocs={'etude_ci': {'prix_achat': 1, 'bilan': [{'prix_achat_ht': 2, 'production_kwh': 3}]},
                   'marge_snapshot': {'x': 1}})
        self._patcher(entrees, 'entrees_pour', return_value=SimpleNamespace(empreinte_pose=''))
        self._patcher(moteur, 'calculer_conception', return_value=resultat)
        rangee = self._relancer(lead, company, _declencheur()).conception
        rangee.refresh_from_db()
        self.assertEqual(rangee.blocs, {'etude_ci': {'bilan': [{'production_kwh': 3}]}})
        self.assertEqual(rangee.valeurs, {'sans': {'nb_panneaux': {'valeur': 4, 'unite': None, 'source': 'moteur'}}})

    def test_autre_societe_ou_origine_inconnue_rien_n_est_ecrit(self):
        from authentication.models import Company

        from apps.ventes.models import ConceptionLead

        company, lead = self._residentiel(facture_hiver=Decimal('1800'))
        autre = Company.objects.create(nom='Autre relance', slug='autre-relance-conception')
        with self.assertRaises(ValueError):
            self._relancer(lead, autre, _declencheur())
        with self.assertRaises(ValueError):
            self._relancer(lead, company, _declencheur('inventee'))
        self.assertFalse(ConceptionLead.objects.filter(lead=lead).exists())

    # ── ADEV136 — le porteur sans lead est le calepinage (réponse Q3 du 23/11) ──
    def test_porteur_calepinage_avec_et_sans_lead_et_appel_d_offres(self):
        from authentication.models import Company

        from apps.calepinage.models import Calepinage
        from apps.crm.models import Client
        from apps.ventes.conception.service import CODE_APPEL_OFFRES
        from apps.ventes.models import ConceptionLead

        company, lead = self._residentiel(facture_hiver=Decimal('1800'))
        _reglages_de_la_societe(company)
        client = Client.objects.create(company=company, nom='Client calepinage seul')
        du_lead = Calepinage.objects.create(company=company, lead_id=lead.pk, titre='Toit du lead')
        sans_lead = Calepinage.objects.create(company=company, client=client, titre='Client seul')
        dossier_ao = Calepinage.objects.create(company=company, client=client, appel_offre_id=7, titre='AO')

        # Calepinage d'un lead : porté par le lead, le calepinage noté.
        rangee = self._relancer(None, company, _declencheur(), calepinage_id=du_lead.pk).conception
        self.assertEqual((rangee.lead_id, rangee.calepinage_id, rangee.etat), (lead.pk, du_lead.pk, 'complet'))

        # Sans lead : porté par le calepinage lui-même (jamais un lead inventé) ;
        # il ne porte ni ville ni consommation : le refus du moteur est rangé, nommé.
        premiere = self._relancer(None, company, _declencheur(), calepinage_id=sans_lead.pk)
        relue = ConceptionLead.objects.get(pk=premiere.conception.pk)
        self.assertEqual((relue.lead_id, relue.calepinage_id, relue.courante, relue.version),
                         (None, sans_lead.pk, True, 1))
        self.assertEqual((relue.etat, relue.refus['code']), ('refus', 'localisation_inconnue'))
        # T4-X9-013 — sans lead, le refus ne demande jamais « la ville … du lead ».
        self.assertEqual(relue.refus['message'], "Sans lead, l'atelier ne calcule pas de conception : "
                                                 'la production vient de la simulation de la pose.')
        self.assertTrue(relue.declencheur['raison'].endswith(' : premier calcul'))
        meme = self._relancer(None, company, _declencheur('manuel'), calepinage_id=sans_lead.pk)
        self.assertFalse(meme.ecrite)
        forcee = self._relancer(None, company, _declencheur('manuel'), calepinage_id=sans_lead.pk, forcer=True)
        self.assertEqual(forcee.conception.version, 2)
        self.assertEqual(ConceptionLead.objects.filter(calepinage_id=sans_lead.pk, lead__isnull=True,
                                                       courante=True).count(), 1)

        # Dossier d'appel d'offres : jamais calculé par le moteur, rien n'est écrit.
        ao = self._relancer(None, company, _declencheur(), calepinage_id=dossier_ao.pk)
        self.assertEqual((ao.conception, ao.ecrite, ao.refus['code']), (None, False, CODE_APPEL_OFFRES))
        self.assertIn('16 modules par chaîne', ao.refus['message'])
        self.assertFalse(ConceptionLead.objects.filter(calepinage_id=dossier_ao.pk).exists())

        # Un calepinage d'une autre société est introuvable.
        autre = Company.objects.create(nom='Autre calepinage', slug='autre-calepinage-conception')
        with self.assertRaises(ValueError):
            self._relancer(None, autre, _declencheur(), calepinage_id=sans_lead.pk)

    def test_phrase_du_declencheur_choix_lisibles_et_motif_sans_champ(self):
        from datetime import datetime, timezone as tz

        from apps.ventes.conception.service import phrase_du_declencheur

        _company, lead = self._residentiel(facture_hiver=Decimal('1800'))
        quand = datetime(2026, 11, 23, 13, 5, tzinfo=tz.utc)
        phrase = phrase_du_declencheur(lead, [
            {'champ': 'occupation_jour', 'avant': None, 'apres': 'absent'},
            {'champ': 'ete_differente', 'avant': False, 'apres': True},
            {'champ': 'conso_mensuelle_kwh', 'avant': 1234.5, 'apres': 1300}], 'lead_entrees_modifiees', quand)
        self.assertTrue(phrase.startswith('Recalculé le 23/11 à '), phrase)
        choix = dict(lead._meta.get_field('occupation_jour').choices)
        self.assertTrue(phrase.endswith(
            ' : Présence en journée — → %s ; Été différent Non → Oui ; Conso mensuelle (kWh) 1 234,5 → 1 300'
            % choix['absent']), phrase)
        self.assertTrue(phrase_du_declencheur(lead, [], 'pose_enregistree', quand).endswith(
            ' : pose enregistrée sur le calepinage'))


# ── ADEV137 — les lecteurs et les routes de la conception rangée ─────────────

URL_CONCEPTION = '/api/django/ventes/conception/%d/'
URL_APERCU = '/api/django/ventes/conception/apercu/'


def _photo_devis(devis_id):
    """Le devis et ses lignes tels qu'en base (preuve « jamais touché »)."""
    from apps.ventes.models import Devis, LigneDevis

    return _json({'devis': Devis.objects.filter(pk=devis_id).values()[0],
                  'lignes': list(LigneDevis.objects.filter(devis_id=devis_id).order_by('pk').values())})


class ServirConceptionTests(_emprunt(RelanceConceptionTests, '_relancer'),
                            _emprunt(FigeageDevisAutoTests, 'setUp', '_patcher', '_utilisateur', '_residentiel',
                                     '_ci', '_agricole', '_fiches_residentielles', '_site_isole', '_structures',
                                     '_fiches_ci', '_cas'), TestCase):
    """ADEV137 — ``selectors_conception`` (bornés société, lecture seule) et
    les routes ``GET conception/<lead_id>/`` et ``POST conception/apercu/``."""

    def test_acal2020_apercu_recoit_la_consommation_imposee_de_l_ecran(self):
        """Reste d'ACAL2020 (note de l'orchestrateur) — l'aperçu de l'écran devis reçoit LA
        consommation imposée du moteur (``imposes.consommation`` : douze factures saisies) :
        la conception servie est calculée avec elle et le DIT ; rien n'est écrit ; une forme
        hors bornes ⇒ 400 nommant le champ (mutant « clé inconnue » : 400 ``consommation``)."""
        from apps.crm.models import Lead
        from apps.ventes.models import ConceptionLead

        company, lead = self._cas('res_facture_dirhams')
        _reglages_de_la_societe(company)
        api = self._api(self._utilisateur(company))
        fiche, versions = _json(Lead.objects.filter(pk=lead.pk).values()[0]), ConceptionLead.objects.count()
        temoin = api.post(URL_APERCU, {'lead': lead.pk}, format='json')
        self.assertEqual(temoin.status_code, 200, temoin.content[:300])
        mois = [700.0, 650.0, 600.0, 560.0, 620.0, 800.0, 950.0, 980.0, 760.0, 600.0, 640.0, 740.0]
        corps = {'lead': lead.pk, 'imposes': {'consommation': {'kwh_mensuels': mois, 'source': 'factures'}}}
        reponse = api.post(URL_APERCU, corps, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.content[:300])
        lue = reponse.json()
        self.assertEqual(lue['entrees_utilisees']['conso_mensuelle_kwh'], {'valeur': 716.7, 'source': 'saisie'})
        dites = [s for s in lue['suppositions'] if s['code'] == 'consommation_imposee']
        self.assertEqual(len(dites), 1, lue['suppositions'])
        self.assertIn('factures saisies', dites[0]['message'])
        self.assertIn('ramenés à leur moyenne mensuelle', dites[0]['message'])
        option = lue['option_retenue']
        avant = temoin.json()
        self.assertNotEqual(lue['valeurs'][option]['consommation_annuelle']['valeur'],
                            avant['valeurs'][avant['option_retenue']]['consommation_annuelle']['valeur'])
        for faute, champ in (({'kwh_mensuels': mois[:11], 'source': 'factures'}, 'kwh_mensuels'),
                             ({'kwh_annuel': 9000, 'kwh_mensuels': mois, 'source': 'factures'}, 'kwh_annuel'),
                             ({'kwh_annuel': True, 'source': 'saisie'}, 'kwh_annuel'),
                             ({'kwh_annuel': -5, 'source': 'saisie'}, 'kwh_annuel'),
                             ({'kwh_annuel': 6000, 'source': 'devine'}, 'source'),
                             ({'kwh_annuel': 6000, 'source': 'saisie', 'pic': 1}, 'pic')):
            with self.subTest(champ=champ, faute=faute):
                refus = api.post(URL_APERCU, {'lead': lead.pk, 'imposes': {'consommation': faute}}, format='json')
                self.assertEqual(refus.status_code, 400, refus.content[:300])
                self.assertEqual(refus.json()['champ'], 'imposes.consommation.' + champ)
        self.assertEqual((_json(Lead.objects.filter(pk=lead.pk).values()[0]), ConceptionLead.objects.count()),
                         (fiche, versions))  # l'aperçu n'écrit rien

    def test_e6_payback_servi_a_la_lecture_celui_du_pdf(self):
        """Relecture E6 — le payback de la conception est SERVI À LA LECTURE (jamais rangé) :
        par option, celui que ``build_quote_data`` imprime pour le devis de référence ; source
        ``devis`` et sa référence ; sans devis, ``None`` et le motif ; un devis envoyé n'est
        pas écrit ; aucun prix d'achat dans la réponse."""
        from apps.ventes.models import ConceptionLead, Devis
        from apps.ventes.quote_engine.builder import build_quote_data
        from apps.ventes.selectors import conception_courante
        from apps.ventes.services import build_devis_auto

        company, lead = self._cas('res_facture_dirhams')
        _reglages_de_la_societe(company)
        self._relancer(lead, company, _declencheur())
        sans_devis = conception_courante(company, lead.pk)
        self.assertEqual(sans_devis['payback_devis'],
                         {'devis_ref': None, 'motif': 'retour sur investissement : après un premier devis'})
        self.assertTrue(all(v['payback']['valeur'] is None for v in sans_devis['valeurs'].values()))
        with self.captureOnCommitCallbacks(execute=True):
            devis = build_devis_auto(lead=lead, user=self._utilisateur(company), company=company)
        Devis.objects.filter(pk=devis.pk).update(statut='envoye')
        devis.refresh_from_db()
        avant, rangee = _photo_devis(devis.pk), _json(ConceptionLead.objects.filter(lead=lead).values()[0])
        lue = conception_courante(company, lead.pk)
        data = build_quote_data(devis, {'pdf_mode': 'full'})
        self.assertEqual(lue['payback_devis'], {'devis_ref': devis.reference, 'motif': None})
        for option, cle in (('sans', 'roi_s'), ('avec', 'roi_a')):
            payback = lue['valeurs'][option]['payback']
            self.assertEqual(payback['source'], 'devis')
            self.assertAlmostEqual(payback['valeur'], data[cle], places=1, msg=option)
        self.assertEqual(_cles_interdites(lue), [])
        self.assertEqual(_photo_devis(devis.pk), avant)  # le devis envoyé n'est jamais écrit
        self.assertEqual(_json(ConceptionLead.objects.filter(lead=lead).values()[0]), rangee)  # jamais rangé

    def test_t4x9016_le_payback_servi_porte_son_montant_et_son_economie(self):
        """T4-X9-016 — « Retour 21,4 ans — d'après le devis DEV-… » sans dire quel montant ni
        quelle économie : le payback servi porte À CÔTÉ de lui l'investissement TTC de SON option
        et l'économie annuelle de la MÊME option (celle de la colonne), et la phrase du calcul
        (cumul de 25 ans, baisse de production, remplacement de l'onduleur) quand ce n'est pas un
        simple quotient. Établi : 65 900 MAD et 6 397 MAD/an donnent 10,6 ans
        (``payback_publiable``, résidentiel, part stockée 0) — jamais 21,4."""
        from apps.ventes.quote_engine.pricing import payback_publiable
        from apps.ventes.selectors import conception_courante
        from apps.ventes.services import build_devis_auto

        self.assertEqual(payback_publiable(65900, 6397, stockage=True, part_batterie=0,
                                           cout_onduleur_ttc=15000)['payback_years'], 10.6)
        company, lead = self._cas('res_facture_dirhams')
        _reglages_de_la_societe(company)
        self._relancer(lead, company, _declencheur())
        with self.captureOnCommitCallbacks(execute=True):
            build_devis_auto(lead=lead, user=self._utilisateur(company), company=company)
        lue = conception_courante(company, lead.pk)
        for option, table in lue['valeurs'].items():
            payback = table['payback']
            self.assertEqual(payback['economie_annuelle'], table['economies_annuelles']['valeur'], option)
            self.assertGreater(payback['investissement_ttc'], 0, option)
            self.assertEqual(payback['valeur'], payback_publiable(
                payback['investissement_ttc'], payback['economie_annuelle'], stockage=option == 'avec',
                cout_onduleur_ttc=payback.get('cout_onduleur_ttc'), part_batterie=0)['payback_years'], option)
            self.assertIn('25 ans', payback['calcul'], option)
        self.assertEqual(_cles_interdites(lue), [])

    def test_e6d_cout_onduleur_un_seul_calcul_payback_servi_au_centime(self):
        """Lane E6d — la provision d'onduleur du payback servi est calculée par LA fonction des
        cartes (``offres_tailles._cout_onduleur_ttc``) : sur ce devis de référence elle vaut, au
        centime, l'ancien calcul de la lecture (Σ qté × P.U. × (1 + TVA de la ligne) × remise),
        et le payback servi est identique."""
        from unittest import mock as _mock

        from apps.ventes import offres_tailles
        from apps.ventes.domain.catalogue import classer_produit
        from apps.ventes.quote_engine.montants import arrondi_affichage
        from apps.ventes.quote_engine.pricing import payback_publiable
        from apps.ventes.selectors import conception_courante
        from apps.ventes.services import build_devis_auto
        from apps.ventes.utils.options import (AVEC_BATTERIE, SANS_BATTERIE, filter_lines_for_option,
                                               lignes_avec_produit, option_totaux)

        company, lead = self._cas('res_facture_dirhams')
        _reglages_de_la_societe(company)
        self._relancer(lead, company, _declencheur())
        with self.captureOnCommitCallbacks(execute=True):
            devis = build_devis_auto(lead=lead, user=self._utilisateur(company), company=company)
        from apps.ventes.models import Devis
        Devis.objects.filter(pk=devis.pk).update(remise_globale=Decimal('5'))
        devis.refresh_from_db()
        lignes = list(lignes_avec_produit(devis))
        couts = []
        vrai = offres_tailles._cout_onduleur_ttc

        def espion(*args, **kwargs):
            couts.append(vrai(*args, **kwargs))
            return couts[-1]
        with _mock.patch.object(offres_tailles, '_cout_onduleur_ttc', side_effect=espion):
            lue = conception_courante(company, lead.pk)
        self.assertEqual(len(couts), len(lue['valeurs']))  # LA fonction des cartes, une fois par option
        for (option, table), cout in zip(lue['valeurs'].items(), couts):
            panier = AVEC_BATTERIE if option == 'avec' else SANS_BATTERIE
            de_l_option = filter_lines_for_option(lignes, panier, devis=devis) if len(lue['valeurs']) > 1 else lignes
            onduleurs = [li for li in de_l_option if li.type_ligne == 'produit' and (classer_produit(
                getattr(li.produit, 'nom', '') or li.designation) or '').startswith('onduleur')]
            ancien = sum(float(li.quantite or 0) * float(li.prix_unitaire or 0) * (1 + float(li.taux_tva or 0) / 100)
                         for li in onduleurs) * (1 - float(devis.remise_globale or 0) / 100)
            self.assertTrue(onduleurs, option)
            self.assertEqual(cout, arrondi_affichage(ancien, 2) or None, option)  # au centime
            horaire = {'part_batterie': 0}
            attendu = payback_publiable(option_totaux(devis, '', lignes=de_l_option)['ttc'],
                                        table['economies_annuelles']['valeur'], stockage=option == 'avec',
                                        cout_onduleur_ttc=arrondi_affichage(ancien, 2) or None,
                                        **horaire)['payback_years']
            self.assertEqual(table['payback']['valeur'], attendu, option)

    def test_t4x4018_tableau_de_l_apercu_couvre_la_taille_de_chaque_option(self):
        """T4-X4-018 — le tableau des tailles (``blocs.dimensionnement.tableau``,
        ``recommander_taille``) s'arrête à la parité + 1 panneau
        (``dimensionnement.bornes_candidates``) : la taille de l'option « avec » que la
        conception vend (panneaux ajoutés pour remplir la batterie) peut être au-delà,
        donc absente. L'aperçu porte une ligne à la taille de CHAQUE option servie,
        calculée par le même balayage (une taille), marquée ``taille_du_devis`` ; la
        version rangée n'est pas touchée (aucune clé ne bouge)."""
        from apps.ventes.selectors import conception_courante

        company, lead = self._cas('res_facture_dirhams')
        _reglages_de_la_societe(company)
        self._relancer(lead, company, _declencheur())
        rangee = conception_courante(company, lead.pk)
        api = self._api(self._utilisateur(company))
        apercu = api.post(URL_APERCU, {'lead': lead.pk}, format='json').json()
        tableau = apercu['blocs']['dimensionnement']['tableau']
        for option, table in apercu['valeurs'].items():
            with self.subTest(option=option):
                nb = table['nb_panneaux']['valeur']
                lignes = [li for li in tableau if li['panneaux'] == nb]
                self.assertEqual(len(lignes), 1, (option, nb, [li['panneaux'] for li in tableau]))
                self.assertIn(option, lignes[0]['taille_du_devis'])
        self.assertEqual([li['panneaux'] for li in tableau], sorted(li['panneaux'] for li in tableau))
        rangees = rangee['blocs']['dimensionnement']['tableau']
        self.assertFalse(any('taille_du_devis' in li for li in rangees))  # la version rangée ne bouge pas
        self.assertEqual(conception_courante(company, lead.pk)['blocs'], rangee['blocs'])
        # Le cas du constat : un balayage borné SOUS la taille des options (parité + 1
        # plus petite que l'option avec) ⇒ les tailles des options y sont ajoutées.
        from unittest import mock as _mock

        from apps.ventes.conception import etudes_lignes as EL
        vrai = EL.dimensionnement_des_lignes

        def borne_a_deux(*args, **kwargs):
            etat, bloc = vrai(*args, **kwargs)
            if isinstance(bloc, dict):
                bloc = dict(bloc, tableau=[li for li in bloc.get('tableau') or [] if li['panneaux'] <= 2])
            return etat, bloc
        with _mock.patch.object(EL, 'dimensionnement_des_lignes', side_effect=borne_a_deux):
            borne = api.post(URL_APERCU, {'lead': lead.pk}, format='json').json()
        tableau = borne['blocs']['dimensionnement']['tableau']
        for option, table in borne['valeurs'].items():
            with self.subTest(option=option, borne=2):
                nb = table['nb_panneaux']['valeur']
                self.assertGreater(nb, 2)
                ligne = next((li for li in tableau if li['panneaux'] == nb), None)
                self.assertIsNotNone(ligne, [li['panneaux'] for li in tableau])
                self.assertIn(option, ligne['taille_du_devis'])

    def test_e7d_payback_de_l_apercu_sur_l_investissement_de_l_ecran(self):
        """E7d (revue lot 4, M1) — l'aperçu sert le payback de CE QUE L'ÉCRAN MONTRE :
        ``investissement`` (TTC de vente des lignes de chaque option) entre dans le corps ;
        même fonction que le payback servi à la lecture (provision d'onduleur des cartes,
        part stockée 0 en résidentiel) : sur les lignes du devis de référence, le même
        chiffre au centime ; sans investissement, aucun payback ; hors forme ⇒ 400 nommant
        ``investissement.<option>`` ; aucun prix d'achat dans la réponse, rien d'écrit."""
        from apps.ventes.models import ConceptionLead
        from apps.ventes.selectors import conception_courante
        from apps.ventes.services import build_devis_auto
        from apps.ventes.utils.options import (AVEC_BATTERIE, SANS_BATTERIE, filter_lines_for_option,
                                               lignes_avec_produit, option_totaux)

        company, lead = self._cas('res_facture_dirhams')
        _reglages_de_la_societe(company)
        self._relancer(lead, company, _declencheur())
        user = self._utilisateur(company)
        with self.captureOnCommitCallbacks(execute=True):
            devis = build_devis_auto(lead=lead, user=user, company=company)
        lue, lignes = conception_courante(company, lead.pk), list(lignes_avec_produit(devis))
        plusieurs = len(lue['valeurs']) > 1
        investissement = {option: float(option_totaux(devis, '', lignes=filter_lines_for_option(
            lignes, AVEC_BATTERIE if option == 'avec' else SANS_BATTERIE, devis=devis) if plusieurs else lignes)['ttc'])
            for option in lue['valeurs']}
        api, versions = self._api(user), ConceptionLead.objects.count()
        sans = api.post(URL_APERCU, {'lead': lead.pk}, format='json').json()
        self.assertTrue(all(v['payback']['valeur'] is None for v in sans['valeurs'].values()))
        reponse = api.post(URL_APERCU, {'lead': lead.pk, 'investissement': investissement}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.content[:300])
        apercu = reponse.json()
        for option, table in apercu['valeurs'].items():
            with self.subTest(option=option):
                self.assertIsNotNone(table['payback']['valeur'])
                self.assertEqual(table['payback'], lue['valeurs'][option]['payback'])  # un seul chiffre
        self.assertEqual(_cles_interdites(apercu), [])
        for faute, champ in (({'sans': -1}, 'sans'), ({'sans': True}, 'sans'), ({'les_deux': 9}, 'les_deux'),
                             ('50000', 'investissement')):
            with self.subTest(faute=faute):
                refus = api.post(URL_APERCU, {'lead': lead.pk, 'investissement': faute}, format='json')
                self.assertEqual(refus.status_code, 400, refus.content[:300])
                self.assertEqual(refus.json()['champ'],
                                 champ if champ == 'investissement' else 'investissement.' + champ)
        self.assertEqual(ConceptionLead.objects.count(), versions)  # l'aperçu n'écrit rien

    def _api(self, user):
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken

        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api

    def _autre_societe(self):
        """Société B : un lead et une version rangée (aucun calcul)."""
        from authentication.models import Company

        from apps.crm.models import Lead
        from apps.ventes.models import ConceptionLead

        autre = Company.objects.create(nom='Conception B route', slug='conception-b-route')
        lead_b = Lead.objects.create(company=autre, nom='B', prenom='Lead', telephone='+212600000099')
        ConceptionLead.ranger(lead=lead_b, **_champs_version())
        return autre, lead_b

    def test_route_et_selecteurs_bornes_a_la_societe(self):
        from apps.crm.models import Lead
        from apps.ventes.models import ConceptionLead
        from apps.ventes.selectors import conception_courante, historique_conception

        company, lead = self._cas('res_facture_dirhams')
        _reglages_de_la_societe(company)
        self._relancer(lead, company, _declencheur())
        Lead.objects.filter(pk=lead.pk).update(facture_hiver=Decimal('2400'))
        lead.refresh_from_db()
        self._relancer(lead, company, _declencheur('lead_entrees_modifiees',
                                                   facture_hiver=(Decimal('1800'), Decimal('2400'))))
        autre, lead_b = self._autre_societe()

        self.assertEqual(conception_courante(company, lead.pk)['version'], 2)
        self.assertIsNone(conception_courante(company, lead_b.pk))  # mutant « sans filtre société » : rouge
        self.assertEqual([v['version'] for v in historique_conception(company, lead.pk)], [2, 1])
        self.assertEqual(historique_conception(company, lead_b.pk), [])

        api = self._api(self._utilisateur(company))
        avant = ConceptionLead.objects.count()
        reponse = api.get(URL_CONCEPTION % lead.pk)
        self.assertEqual(reponse.status_code, 200, reponse.content[:300])
        corps = reponse.json()
        self.assertEqual(set(corps), CLES_RESULTAT | CLES_RANGEES)
        self.assertEqual((corps['version'], corps['lead'], corps['calepinage'], corps['perimee']),
                         (2, lead.pk, None, False))
        self.assertEqual((corps['etat'], corps['option_retenue'], corps['ecart_devis']), ('complet', 'avec', []))
        self.assertTrue(corps['declencheur']['raison'].endswith(' : Facture hiver 1 800 → 2 400 MAD'))
        self.assertEqual(_cles_interdites(corps), [])
        self.assertEqual(api.get(URL_CONCEPTION % lead.pk).json(), corps)  # relire = même version
        self.assertEqual(ConceptionLead.objects.count(), avant)  # la lecture n'écrit rien
        self.assertEqual(api.get(URL_CONCEPTION % lead_b.pk).status_code, 404)
        self.assertEqual(self._api(self._utilisateur(autre)).get(URL_CONCEPTION % lead.pk).status_code, 404)
        sans_version = Lead.objects.create(company=company, nom='Sans', prenom='Version',
                                           telephone='+212600000098')
        absente = api.get(URL_CONCEPTION % sans_version.pk)
        self.assertEqual((absente.status_code, absente.json()),
                         (200, json.loads(CONTRAT.read_text(encoding='utf-8'))['exemple_aucune']))
        self.assertEqual(api.get(URL_CONCEPTION % 2147483000).status_code, 404)  # inexistant

    def _avec_role(self, company, nom, permissions):
        """Un utilisateur portant un VRAI rôle du registre (portée comprise)."""
        from django.contrib.auth import get_user_model

        from apps.roles.models import Role

        role = Role.objects.create(company=company, nom=f'B1 {nom}', permissions=list(permissions))
        return get_user_model().objects.create_user(username=f'b1-{nom}-{company.pk}', password='x',
                                                    company=company, role=role)

    def test_portee_du_role_sur_les_deux_routes(self):
        """Relecture B1 — la conception porte factures, consommation et lieu :
        un Commercial (portée « les siens ») ne lit pas le lead d'un collègue,
        ni par la route, ni par l'aperçu (lead ou calepinage) : 404 comme une
        autre société ; un rôle sans ``crm_voir`` est refusé ; le propriétaire,
        le Commercial responsable et l'administrateur lisent comme avant."""
        from apps.calepinage.models import Calepinage
        from apps.crm.models import Lead
        from apps.roles.permissions_registre import (
            ADMIN_PERMISSIONS, COMMERCIAL_PERMISSIONS, COMMERCIAL_RESP_PERMISSIONS,
            COMMERCIAL_TERRAIN_PERMISSIONS)

        company, lead = self._cas('res_facture_dirhams')
        _reglages_de_la_societe(company)
        proprietaire = self._avec_role(company, 'proprietaire', COMMERCIAL_PERMISSIONS)
        Lead.objects.filter(pk=lead.pk).update(owner=proprietaire)
        lead.refresh_from_db()
        self._relancer(lead, company, _declencheur())
        calepinage = Calepinage.objects.create(company=company, lead_id=lead.pk, titre='Toit B1')
        par_lead = {'lead': lead.pk, 'entrees': {'facture_hiver': 3600}}
        par_calepinage = {'calepinage': calepinage.pk, 'entrees': {'facture_hiver': 3600}}

        collegue = self._api(self._avec_role(company, 'collegue', COMMERCIAL_PERMISSIONS))
        self.assertEqual(collegue.get(URL_CONCEPTION % lead.pk).status_code, 404)  # mutant « société seule » : 200
        self.assertEqual(collegue.post(URL_APERCU, par_lead, format='json').status_code, 404)
        self.assertEqual(collegue.post(URL_APERCU, par_calepinage, format='json').status_code, 404)
        terrain = self._api(self._avec_role(company, 'terrain', COMMERCIAL_TERRAIN_PERMISSIONS))
        self.assertEqual(terrain.get(URL_CONCEPTION % lead.pk).status_code, 403)
        self.assertEqual(terrain.post(URL_APERCU, par_lead, format='json').status_code, 403)

        responsable = self._avec_role(company, 'responsable', COMMERCIAL_RESP_PERMISSIONS)
        administrateur = self._avec_role(company, 'administrateur', ADMIN_PERMISSIONS)
        for user in (proprietaire, responsable, administrateur):
            with self.subTest(utilisateur=user.username):
                api = self._api(user)
                self.assertEqual(api.get(URL_CONCEPTION % lead.pk).status_code, 200)
                reponse = api.post(URL_APERCU, par_lead, format='json')
                self.assertEqual(reponse.status_code, 200, reponse.content[:200])
        reponse = self._api(proprietaire).post(URL_APERCU, par_calepinage, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.content[:200])

    def test_manques_du_moteur_et_champs_entrees(self):
        from apps.ventes.conception.champs import CHAMPS_ENTREES
        from apps.ventes.selectors import champs_entrees, manques_du_moteur

        from apps.crm.models import Lead

        company, complet = self._residentiel(facture_hiver=Decimal('1800'))
        self.assertEqual(manques_du_moteur(complet), [])
        sans_ville = Lead.objects.create(company=company, nom='Sans', prenom='Ville', facture_hiver=Decimal('1800'))
        self.assertEqual(manques_du_moteur(sans_ville), [{'champ': 'ville', 'label': 'Ville'}])
        sans_conso = Lead.objects.create(company=company, nom='Sans', prenom='Conso', ville=complet.ville)
        self.assertTrue(manques_du_moteur(sans_conso))
        self.assertNotIn('ville', {m['champ'] for m in manques_du_moteur(sans_conso)})
        self.assertEqual(champs_entrees('agricole'), CHAMPS_ENTREES['agricole'])
        with self.assertRaises(KeyError):
            champs_entrees('inconnu')

    def test_ecart_devis_lit_le_devis_envoye_sans_jamais_le_toucher(self):
        from django.utils import timezone

        from apps.crm.models import Lead
        from apps.ventes.models import Devis
        from apps.ventes.selectors import ecart_devis
        from apps.ventes.services import build_devis_auto

        company, lead = self._cas('res_facture_dirhams')
        _reglages_de_la_societe(company)
        user = self._utilisateur(company)
        devis = build_devis_auto(lead=lead, user=user, company=company)
        Devis.objects.filter(pk=devis.pk).update(statut='envoye', date_envoi=timezone.now())
        devis.refresh_from_db()
        lead.refresh_from_db()
        self._relancer(lead, company, _declencheur())
        self.assertEqual(ecart_devis(devis), [], 'conception = devis : aucun écart')

        photo = _photo_devis(devis.pk)
        Lead.objects.filter(pk=lead.pk).update(facture_hiver=Decimal('3600'))
        lead.refresh_from_db()
        self._relancer(lead, company, _declencheur('lead_entrees_modifiees',
                                                   facture_hiver=(Decimal('1800'), Decimal('3600'))))
        ecarts = ecart_devis(devis)
        self.assertLessEqual({'nb_panneaux', 'production_annuelle'}, {e['valeur'] for e in ecarts}, ecarts)
        for ecart in ecarts:
            self.assertEqual(set(ecart), CLES_ECART)
            self.assertNotEqual(ecart['devis'], ecart['conception'])
            self.assertEqual((ecart['devis_ref'], ecart['reviser_possible'], ecart['mise_a_jour_proposee'],
                              ecart['courante_refusee']), (devis.reference, True, False, False))
        self.assertEqual(self._api(user).get(URL_CONCEPTION % lead.pk).json()['ecart_devis'], ecarts)
        Devis.objects.filter(pk=devis.pk).update(statut='accepte')
        photo_acceptee = _photo_devis(devis.pk)
        devis.refresh_from_db()
        self.assertEqual(ecart_devis(devis), ecarts)
        self.assertEqual(ecart_devis(devis), ecarts)  # relire deux fois : même liste
        self.assertEqual(_photo_devis(devis.pk), photo_acceptee)  # jamais touché (accepté)
        photo_acceptee['devis']['statut'] = 'envoye'
        self.assertEqual(photo_acceptee, photo)  # rien d'autre n'a bougé depuis l'envoi

        # ADEV146 (relecture m5) — la version courante devient un REFUS (lieu
        # effacé) : l'écart ne disparaît pas, il est comparé à la dernière
        # version complète et le refus est dit.
        Lead.objects.filter(pk=lead.pk).update(ville='')
        lead.refresh_from_db()
        refusee = self._relancer(lead, company, _declencheur('manuel')).conception
        self.assertEqual(refusee.etat, 'refus')
        apres_refus = ecart_devis(devis)
        self.assertEqual([(e['valeur'], e['devis'], e['conception']) for e in apres_refus],
                         [(e['valeur'], e['devis'], e['conception']) for e in ecarts])  # mutant « courante seule » : []
        self.assertTrue(all(e['courante_refusee'] for e in apres_refus))
        self.assertEqual(_photo_devis(devis.pk), photo_acceptee | {'devis': dict(photo_acceptee['devis'],
                                                                                 statut='accepte')})

    def test_apercu_sans_ecriture_404_et_corps_refuse(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        from apps.calepinage.models import Calepinage
        from apps.crm.models import Client
        from apps.ventes.conception.service import apercu_conception
        from apps.ventes.models import ConceptionLead

        company, lead = self._cas('res_facture_dirhams')
        _reglages_de_la_societe(company)
        _autre, lead_b = self._autre_societe()
        api = self._api(self._utilisateur(company))
        avant = ConceptionLead.objects.count()
        reponse = api.post(URL_APERCU, {'lead': lead.pk, 'entrees': {'facture_hiver': 3600}}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.content[:300])
        tapee = reponse.json()
        self.assertEqual(set(tapee), CLES_RESULTAT)
        self.assertEqual(tapee['entrees_utilisees']['facture_hiver'], {'valeur': 3600.0, 'source': 'saisie'})
        with CaptureQueriesContext(connection) as requetes:
            fiche, _refus = apercu_conception(lead, company)
        self.assertEqual(_ecritures(requetes), [])
        self.assertNotEqual(tapee['valeurs'], fiche['valeurs'])  # la saisie a bien été calculée
        self.assertEqual(tapee['valeurs'], api.post(URL_APERCU, {'lead': lead.pk, 'entrees': {
            'facture_hiver': 3600}}, format='json').json()['valeurs'])  # rappeler = même réponse
        self.assertEqual(ConceptionLead.objects.count(), avant)
        lead.refresh_from_db()
        self.assertEqual(lead.facture_hiver, Decimal('1800'))  # la fiche n'est jamais écrite

        self.assertEqual(api.post(URL_APERCU, {'lead': lead_b.pk, 'entrees': 'x'}, format='json').status_code, 404)
        refus = api.post(URL_APERCU, {'lead': lead.pk, 'entrees': {'nom': 'X'}}, format='json')
        self.assertEqual((refus.status_code, refus.json()['champ']), (400, 'nom'))
        impose = api.post(URL_APERCU, {'lead': lead.pk, 'imposes': {'module_id': 3}}, format='json')
        self.assertEqual((impose.status_code, impose.json()['champ']), (400, 'module_id'))
        self.assertEqual(api.post(URL_APERCU, {'entrees': {}}, format='json').status_code, 400)
        client = Client.objects.create(company=company, nom='Client AO')
        dossier = Calepinage.objects.create(company=company, client=client, appel_offre_id=3, titre='AO')
        self.assertEqual(api.post(URL_APERCU, {'calepinage': dossier.pk}, format='json').status_code, 409)

    def test_apercu_devis_sans_lead_ni_calepinage(self):
        """ADEV152 — un devis SANS lead (ni calepinage) : l'aperçu porte sur les
        seules valeurs tapées (lead NON enregistré de la société), même moteur,
        mêmes chiffres que le lead qui porterait ces valeurs ; rien n'est écrit ;
        rappeler = même réponse ; sans aucune valeur, le porteur reste requis."""
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        from apps.crm.models import Lead
        from apps.ventes.conception.service import apercu_conception
        from apps.ventes.models import ConceptionLead

        company, lead = self._cas('res_facture_dirhams')
        _reglages_de_la_societe(company)
        api = self._api(self._utilisateur(company))
        tapees = {'ville': lead.ville, 'facture_hiver': 1800}
        corps = {'lead': None, 'calepinage': None, 'entrees': tapees}
        leads, versions = Lead.objects.count(), ConceptionLead.objects.count()
        reponse = api.post(URL_APERCU, corps, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.content[:300])  # avant : 400 « Porteur requis »
        sans_lead = reponse.json()
        self.assertEqual(set(sans_lead), CLES_RESULTAT)
        self.assertEqual(sans_lead['entrees_utilisees']['facture_hiver'], {'valeur': 1800.0, 'source': 'saisie'})
        par_lead, _refus = apercu_conception(lead, company)
        self.assertEqual(sans_lead['valeurs'], par_lead['valeurs'])  # un seul moteur, un seul chiffre
        with CaptureQueriesContext(connection) as requetes:
            apercu_conception(None, company, saisies=tapees)
        self.assertEqual(_ecritures(requetes), [])
        self.assertEqual(api.post(URL_APERCU, corps, format='json').json()['valeurs'], sans_lead['valeurs'])
        self.assertEqual((Lead.objects.count(), ConceptionLead.objects.count()), (leads, versions))
        self.assertEqual(api.post(URL_APERCU, {'lead': None, 'entrees': {}}, format='json').status_code, 400)


# ── ADEV138 — PARITÉ STOCKÉE : ce que relancer RANGE = ce qu'écrit le devis auto ─
#
# Pour chaque golden de ``FigeageDevisAutoTests`` (même fabrique ``_cas``) : les
# ``blocs`` RELUS en base après ``relancer`` égalent, clé par clé, l'``etude_params``
# du golden ET celui d'un devis automatique fraîchement écrit (mêmes
# normalisations, sans les notes vendeur ``journal_auto`` que la version ne
# range pas) ; la taille et le module de chaque option égalent les lignes
# panneau du golden. Un écart nomme la première clé fautive ; aucun golden
# n'est réécrit.

def _sans_journal(etude_params):
    return {cle: valeur for cle, valeur in etude_params.items() if cle != 'journal_auto'}


def _panneaux_de_l_option(golden, option):
    lignes = [li for li in golden['lignes'] if (li['produit_nom'] or '').startswith('Panneau')
              and not li['optionnelle'] and (li['variante'] or '') in ('', option)]
    return sum(int(float(li['quantite'])) for li in lignes), sorted({li['designation'] for li in lignes})


class VerdictsDuMoteurTests(TestCase):
    """ACAL2016 — le MOTEUR juge, une fois, avec LA règle du calepinage
    (``ratio_devis.juger_ratio`` + D-HYB-1) et range le verdict ; un hybride dans sa
    capacité publiée est « conforme » même au-delà du seuil d'alerte de 1,50."""

    def setUp(self):
        from decimal import Decimal as D

        from authentication.models import Company
        from apps.stock.models import FicheTechnique, Produit

        self.company = Company.objects.create(nom='Verdicts', slug='verdicts-moteur')

        def onduleur(nom, **fiche):
            produit = Produit.objects.create(company=self.company, nom=nom, sku='V-' + nom,
                                             prix_vente=D('1000'), quantite_stock=1)
            FicheTechnique.objects.create(company=self.company, produit=produit, type_fiche='onduleur',
                                          ond_ac_kw=10.0, **fiche)
            return produit
        self.hybride = onduleur('Onduleur hybride 10 kW', ond_dc_max_kwc=D('18'))
        self.reseau = onduleur('Onduleur réseau 10 kW')

    def _verdicts(self, produit, ratio=1.7, kwc=17.04, chaines=({'nb_modules': 12, 'conforme': True},)):
        from apps.ventes.conception.porte_calepinage import verdicts_electriques

        design = {'ratio_dc_ac': ratio, 'chaines': list(chaines),
                  'materiel': {'onduleur': {'designation': produit.nom, 'ac_kw': 10.0}}}
        return verdicts_electriques(self.company, design,
                                    [{'produit': produit.pk, 'designation': produit.nom, 'quantite': 1}], kwc)

    def test_hybride_dans_sa_capacite_conforme_sans_alerte_1_50(self):
        verdicts = self._verdicts(self.hybride)
        self.assertEqual((verdicts['ratio_dc_ac']['conforme'], verdicts['capacite_hybride']['conforme'],
                          verdicts['longueur_chaine']['conforme']), (True, True, True))
        self.assertEqual(verdicts['ratio_dc_ac']['borne_source'], "capacité publiée de l'onduleur")
        self.assertNotIn('1,50', json.dumps(verdicts, ensure_ascii=False))

    def test_reseau_meme_ratio_non_conforme_et_hybride_au_dela_de_sa_capacite(self):
        self.assertIs(self._verdicts(self.reseau)['ratio_dc_ac']['conforme'], False)
        self.assertIsNone(self._verdicts(self.reseau)['capacite_hybride'])
        au_dela = self._verdicts(self.hybride, ratio=2.0, kwc=20.0)
        self.assertEqual((au_dela['ratio_dc_ac']['conforme'], au_dela['capacite_hybride']['conforme']),
                         (False, False))
        longue = self._verdicts(self.reseau, ratio=1.2, kwc=12.0, chaines=({'nb_modules': 30, 'conforme': False},))
        self.assertIs(longue['longueur_chaine']['conforme'], False)

    def test_sans_conception_electrique_aucun_verdict(self):
        from apps.ventes.conception.porte_calepinage import verdicts_electriques

        self.assertIsNone(verdicts_electriques(self.company, None, [], 10.0))

    def test_t4_x3_009_la_note_nomme_le_panneau_de_la_conception(self):
        """T4-X3-009 (lane E9) — conception 8 × 550 W = 4,40 kWc, pose en 710 W : la note ne dit
        jamais un « 8 » nu à côté de panneaux de 710 W, elle nomme le panneau de la conception ;
        même compte (8) mais autre puissance (5,68 kWc) : jugé pour la POSE, plus le verdict rangé."""
        from apps.ventes.selectors_conception import verdicts_pour_le_calepinage

        range_ = self._verdicts(self.reseau, ratio=0.88, kwc=4.4)
        ligne = {'produit': self.reseau.pk, 'designation': self.reseau.nom, 'quantite': 1}
        conception = {'lead': 9, 'option_retenue': 'sans', 'valeurs': {'sans': {
            'nb_panneaux': {'valeur': 8}, 'puissance_kwc': {'valeur': 4.4}, 'onduleurs': {'valeur': [ligne]},
            'verdicts': {'valeur': range_}}}}
        pose = {'onduleur_produit': self.reseau.pk, 'chaines': [{'nb_modules': 6}]}
        moins = dict(pose, nb_panneaux=6, kwc=4.26, ratio=0.85)
        _j, note, _r = verdicts_pour_le_calepinage(self.company, conception, moins)
        self.assertEqual(note, 'jugé pour la pose : 6 panneaux — la conception du lead en compte 8 de 550 W')
        autre_module = dict(pose, nb_panneaux=8, kwc=5.68, ratio=1.14)
        jugees, note, _r = verdicts_pour_le_calepinage(self.company, conception, autre_module)
        self.assertEqual(jugees['ratio_dc_ac']['valeur'], 1.14)
        self.assertEqual(note, 'jugé pour la pose : 8 panneaux — la conception du lead en compte 8 de 550 W')

    def test_e6_m4_pose_d_un_autre_compte_jugee_par_la_meme_regle(self):
        """Relecture E6 M4 + m3 — même compte : le verdict RANGÉ ; compte différent : LA règle
        de la porte du moteur pour la pose (24 panneaux, 14,4 kWc, ratio 1,44) et la note ;
        version sans ``verdicts`` : « à recalculer » et UNE relance en file."""
        from apps.ventes.conception import porte_calepinage as P
        from apps.ventes.selectors_conception import verdicts_pour_le_calepinage

        range_ = self._verdicts(self.reseau, ratio=2.07, kwc=20.7)
        ligne = {'produit': self.reseau.pk, 'designation': self.reseau.nom, 'quantite': 1}
        conception = {'lead': 9, 'option_retenue': 'sans', 'valeurs': {'sans': {
            'nb_panneaux': {'valeur': 35}, 'onduleurs': {'valeur': [ligne]},
            'verdicts': {'valeur': range_}}}}
        pose = {'nb_panneaux': 35, 'kwc': 20.7, 'ratio': 2.07, 'onduleur_produit': self.reseau.pk,
                'chaines': [{'nb_modules': 12}]}
        with mock.patch.object(P, 'verdicts_electriques', wraps=P.verdicts_electriques) as regle:
            self.assertEqual(verdicts_pour_le_calepinage(self.company, conception, pose), (range_, '', False))
            regle.assert_not_called()
            jugees, note, a_recalculer = verdicts_pour_le_calepinage(
                self.company, conception, dict(pose, nb_panneaux=24, kwc=14.4, ratio=1.44))
        self.assertEqual(regle.call_args.args[3], 14.4)  # mutant « verdict rangé pour une autre pose »
        self.assertEqual(jugees['ratio_dc_ac']['valeur'], 1.44)
        self.assertNotEqual(jugees['ratio_dc_ac'], range_['ratio_dc_ac'])
        self.assertEqual((note, a_recalculer),
                         ('jugé pour la pose : 24 panneaux — la conception du lead en compte 35', False))
        ancienne = {'lead': 9, 'option_retenue': 'sans', 'valeurs': {'sans': {'nb_panneaux': {'valeur': 35}}}}
        with mock.patch('apps.ventes.conception.receivers.mettre_en_file') as en_file:
            self.assertEqual(verdicts_pour_le_calepinage(self.company, ancienne, pose), (None, '', True))
        en_file.assert_called_once_with(self.company.pk, lead_id=9, origine='filet', champs=[])


class PariteStockeeTests(_emprunt(RelanceConceptionTests, '_relancer'),
                         _emprunt(FigeageDevisAutoTests, 'setUp', '_patcher', '_utilisateur', '_residentiel',
                                  '_ci', '_agricole', '_fiches_residentielles', '_site_isole', '_structures',
                                  '_fiches_ci', '_cas'), TestCase):
    """ADEV138 — la version rangée par ``relancer`` = le devis automatique."""

    def _parite_stockee(self, nom):
        from types import SimpleNamespace

        from apps.ventes.models import ConceptionLead
        from apps.ventes.services import build_devis_auto

        appel = dict(APPELS_FIGEAGE.get(nom, {}))
        company, lead = self._cas(nom)
        _reglages_de_la_societe(company)
        toit = (SimpleNamespace(empreinte='', plafond_panneaux=appel['plafond_toit'])
                if 'plafond_toit' in appel else None)
        relance = self._relancer(lead, company, _declencheur(), toit=toit)
        rangee = ConceptionLead.objects.get(pk=relance.conception.pk)
        self.assertEqual(rangee.etat, 'complet', rangee.refus)
        self.assertEqual(_cles_interdites(rangee.blocs) + _cles_interdites(rangee.valeurs), [])
        stockes = json.loads(json.dumps(_normaliser_figeage(rangee.blocs), default=str))

        golden = json.loads((DOSSIER_FIGEAGE / f'{nom}.json').read_text(encoding='utf-8'))
        ecarts = _ecarts_figeage(_sans_journal(golden['etude_params']), stockes, '$.blocs')
        self.assertEqual(ecarts, [], f'{nom} : rangé ≠ golden, première clé : {ecarts[0] if ecarts else ""}\n'
                                     + '\n'.join(ecarts[:20]))

        if appel.pop('journal', False):
            appel['journal_auto'] = {}
        devis = build_devis_auto(lead=lead, user=self._utilisateur(company), company=company, **appel)
        frais = json.loads(json.dumps(_photo_du_devis(devis)['etude_params'], default=str))
        ecarts = _ecarts_figeage(_sans_journal(frais), stockes, '$.blocs')
        self.assertEqual(ecarts, [], f'{nom} : rangé ≠ devis frais, première clé : {ecarts[0] if ecarts else ""}\n'
                                     + '\n'.join(ecarts[:20]))

        for option, valeurs in rangee.valeurs.items():
            with self.subTest(cas=nom, option=option):
                nombre, designations = _panneaux_de_l_option(golden, option)
                self.assertEqual(valeurs['nb_panneaux']['valeur'], nombre)
                if rangee.marche != 'agricole':
                    self.assertEqual([valeurs['module']['valeur']], designations)


def _test_de_parite_stockee(nom):
    def test(self):
        self._parite_stockee(nom)
    test.__doc__ = f'ADEV138 — parité STOCKÉE de la conception avec le golden « {nom} ».'
    return test


# Mêmes exclus que la parité du moteur (``test_exclusions_de_parite_figees``).
for _nom in PARITE:
    setattr(PariteStockeeTests, f'test_parite_stockee_{_nom}', _test_de_parite_stockee(_nom))


# ── ADEV139 — la relance en tâche dédupliquée (abonnés des deux événements) ──

class RelanceEnTacheTests(_emprunt(RelanceConceptionTests, '_relancer'),
                          _emprunt(FigeageDevisAutoTests, '_patcher', '_utilisateur', '_residentiel',
                                   '_ci', '_agricole', '_fiches_residentielles', '_site_isole', '_structures',
                                   '_fiches_ci', '_cas'), TestCase):
    """ADEV139 — ``conception/receivers.py`` : un événement met UNE tâche en
    file par porteur ; le calcul tourne dans la tâche (``task_relancer_
    conception``), jamais dans la requête ; une relance en échec n'empêche pas
    l'enregistrement de la fiche."""

    def setUp(self):
        from django.core.cache import cache

        from apps.ventes import tasks

        FigeageDevisAutoTests.setUp(self)
        cache.clear()
        self.addCleanup(cache.clear)
        patcher = mock.patch.object(tasks.task_relancer_conception, 'apply_async')
        self.en_file = patcher.start()
        self.addCleanup(patcher.stop)

    def _enregistrer(self, lead, **valeurs):
        lead.refresh_from_db()
        for cle, valeur in valeurs.items():
            setattr(lead, cle, valeur)
        with self.captureOnCommitCallbacks(execute=True):
            lead.save()

    def _executer_les_taches(self, appels=None):
        """Ce que ferait le worker : chaque tâche mise en file, dans l'ordre."""
        from apps.ventes.tasks import task_relancer_conception

        rendus = []
        for appel in list(appels if appels is not None else self.en_file.call_args_list):
            with self.captureOnCommitCallbacks(execute=True):
                rendus.append(task_relancer_conception(**appel.kwargs['kwargs']))
        self.en_file.reset_mock()
        return rendus

    def test_dix_modifications_une_tache_puis_un_calcul(self):
        from apps.ventes.conception.receivers import mettre_en_file
        from apps.ventes.models import ConceptionLead

        company, lead = self._cas('res_facture_dirhams')
        _reglages_de_la_societe(company)
        self._relancer(lead, company, _declencheur())  # conception à jour (version 1)
        for i in range(10):
            self._enregistrer(lead, facture_hiver=Decimal('1900') + i * 100)
        self.assertEqual(self.en_file.call_count, 1)  # mutant « sans déduplication » : 10
        self.assertGreater(self.en_file.call_args.kwargs['countdown'], 0)
        self.assertEqual(ConceptionLead.objects.filter(lead=lead).count(), 1)  # rien dans la requête

        self.assertEqual(self._executer_les_taches(), [{'version': 2, 'ecrite': True}])
        courante = ConceptionLead.objects.get(lead=lead, courante=True)
        self.assertEqual(courante.version, 2)
        self.assertEqual(courante.entrees_utilisees['facture_hiver'], {'valeur': 2800.0, 'source': 'lead'})
        self.assertEqual(courante.declencheur['origine'], 'lead_entrees_modifiees')
        self.assertEqual(courante.declencheur['champs'],
                         [{'champ': 'facture_hiver', 'avant': 1800.0, 'apres': 2800.0}])
        self.assertIsNone(courante.calcule_par)

        # Un événement sans changement d'empreinte : une tâche, aucune version.
        self.assertEqual(mettre_en_file(company.pk, lead_id=lead.pk, origine='lead_entrees_modifiees',
                                        champs=[{'champ': 'facture_hiver', 'avant': 2800, 'apres': 2800}]),
                         'lancee')
        self.assertEqual(self._executer_les_taches(), [{'version': 2, 'ecrite': False}])
        self.assertEqual(ConceptionLead.objects.filter(lead=lead).count(), 2)
        # Le marqueur est libéré : la modification suivante repart en file.
        self._enregistrer(lead, facture_hiver=Decimal('3000'))
        self.assertEqual(self.en_file.call_count, 1)

    def test_import_de_dix_leads_un_calcul_par_lead(self):
        from apps.crm.models import Lead
        from apps.ventes.models import ConceptionLead

        company, premier = self._residentiel(facture_hiver=Decimal('1800'))
        _reglages_de_la_societe(company)
        leads = [premier] + [Lead.objects.create(company=company, nom='Import', prenom=str(i),
                                                 ville=premier.ville, facture_hiver=Decimal('1800'))
                             for i in range(9)]
        with self.captureOnCommitCallbacks(execute=True):
            for lead in leads:  # l'import réécrit chaque fiche deux fois (une transaction)
                lead.facture_hiver = Decimal('2200')
                lead.save()
                lead.facture_hiver = Decimal('2400')
                lead.save()
        self.assertEqual(self.en_file.call_count, 10)
        self.assertEqual(sorted(a.kwargs['kwargs']['lead_id'] for a in self.en_file.call_args_list),
                         sorted(lead.pk for lead in leads))
        self.assertEqual(self._executer_les_taches(), [{'version': 1, 'ecrite': True}] * 10)
        for lead in leads:
            version = ConceptionLead.objects.get(lead=lead, courante=True)
            self.assertEqual(version.entrees_utilisees['facture_hiver']['valeur'], 2400.0)

    def test_pose_enregistree_relance_le_porteur_avec_sa_pose(self):
        from apps.calepinage.models import Calepinage
        from apps.ventes.models import ConceptionLead
        from core.events import pose_enregistree

        company, lead = self._residentiel(facture_hiver=Decimal('1800'))
        _reglages_de_la_societe(company)
        calepinage = Calepinage.objects.create(company=company, lead_id=lead.pk, titre='Toit')
        for _ in range(3):
            pose_enregistree.send(sender='calepinage.Calepinage', company_id=company.pk,
                                  calepinage_id=calepinage.pk, lead_id=lead.pk, empreinte_pose='p' * 64)
        self.assertEqual(self.en_file.call_count, 1)
        self.assertEqual(self._executer_les_taches(), [{'version': 1, 'ecrite': True}])
        version = ConceptionLead.objects.get(lead=lead, courante=True)
        self.assertEqual((version.calepinage_id, version.empreinte_pose), (calepinage.pk, 'p' * 64))
        self.assertTrue(version.declencheur['raison'].endswith(' : pose enregistrée sur le calepinage'))
        # Une fiche modifiée ensuite garde la pose connue (aucun aller-retour).
        self._enregistrer(lead, facture_hiver=Decimal('2400'))
        self._executer_les_taches()
        suivante = ConceptionLead.objects.get(lead=lead, courante=True)
        self.assertEqual((suivante.version, suivante.calepinage_id, suivante.empreinte_pose),
                         (2, calepinage.pk, 'p' * 64))

    def test_echec_de_la_file_ou_du_calcul_n_empeche_pas_l_enregistrement(self):
        from apps.ventes.conception import service
        from apps.ventes.models import ConceptionLead

        company, lead = self._residentiel(facture_hiver=Decimal('1800'))
        self.en_file.side_effect = OSError('courtier injoignable')
        with self.assertLogs('apps.ventes.conception.receivers', level='WARNING'):
            self._enregistrer(lead, facture_hiver=Decimal('2000'))
        lead.refresh_from_db()
        self.assertEqual(lead.facture_hiver, Decimal('2000'))
        self.en_file.side_effect = None
        self._enregistrer(lead, facture_hiver=Decimal('2100'))  # le marqueur a été libéré
        self.assertEqual(self.en_file.call_count, 2)
        tache = mock.call(kwargs={'company_id': company.pk, 'lead_id': lead.pk, 'calepinage_id': None,
                                  'origine': 'lead_entrees_modifiees', 'champs': [], 'empreinte_pose': None,
                                  'jeton': None})
        with mock.patch.object(service, 'relancer', side_effect=RuntimeError('moteur en panne')), \
                self.assertLogs('apps.ventes.conception.receivers', level='ERROR'):
            self.assertEqual(self._executer_les_taches([tache]), [None])
        self.assertFalse(ConceptionLead.objects.filter(lead=lead).exists())

    def test_effacement_legal_jamais_defait_par_la_relance_en_file(self):
        """Relecture E3 B1 (loi 09-08) — une relance en file quand le lead est
        effacé : le scrub (GPS vidé) passe par la fusion du marqueur, les
        versions sont supprimées, puis la tâche part. Elle ne doit RIEN
        recalculer, ranger ni écrire au chatter : ni version, ni ligne
        « Conception recalculée : GPS latitude 33,57 → — »."""
        import json as _json_mod

        from apps.crm.dsr_provider import anonymiser_lead
        from apps.crm.models import Lead, LeadActivity
        from apps.ventes.conception.receivers import _cle, cle_marqueur
        from apps.ventes.models import ConceptionLead
        from django.core.cache import cache

        company, lead = self._cas('res_facture_dirhams')
        _reglages_de_la_societe(company)
        Lead.objects.filter(pk=lead.pk).update(gps_lat=Decimal('33.5731'), gps_lng=Decimal('-7.5898'))
        lead.refresh_from_db()
        self._relancer(lead, company, _declencheur())
        self.assertTrue(ConceptionLead.objects.filter(lead=lead).exists())
        self._enregistrer(lead, facture_hiver=Decimal('2400'))  # tâche en file, marqueur EN_FILE
        self.assertEqual(self.en_file.call_count, 1)

        lead.refresh_from_db()
        with self.captureOnCommitCallbacks(execute=True):
            anonymiser_lead(company, lead, motif='Effacement (test B1)')
        derniere_ligne = LeadActivity.objects.filter(lead_id=lead.pk).order_by('-pk').values_list(
            'pk', flat=True).first() or 0
        self.assertFalse(ConceptionLead.objects.filter(lead_id=lead.pk).exists())
        self.assertIsNone(cache.get(_cle(company.pk, cle_marqueur(lead.pk))))  # marqueur retiré

        rendus = self._executer_les_taches()  # la tâche en file part quand même (worker)
        self.assertTrue(rendus)
        self.assertEqual(rendus, [None] * len(rendus))  # mutant « relancer quand même » : version 1
        self.assertFalse(ConceptionLead.objects.filter(lead_id=lead.pk).exists())
        self.assertFalse(LeadActivity.objects.filter(lead_id=lead.pk, pk__gt=derniere_ligne).exists())
        self.assertFalse(LeadActivity.objects.filter(lead_id=lead.pk, field='conception_version',
                                                     body__contains='33,57').exists())
        for version in ConceptionLead.objects.filter(company=company):
            self.assertNotIn('33.57', _json_mod.dumps(version.declencheur))

    def _lead_efface(self):
        """Un lead situé, sa conception rangée, puis effacé (loi 09-08)."""
        from apps.crm.dsr_provider import anonymiser_lead
        from apps.crm.models import Lead

        company, lead = self._cas('res_facture_dirhams')
        _reglages_de_la_societe(company)
        Lead.objects.filter(pk=lead.pk).update(gps_lat=Decimal('33.5731'), gps_lng=Decimal('-7.5898'))
        lead.refresh_from_db()
        self._relancer(lead, company, _declencheur())
        with self.captureOnCommitCallbacks(execute=True):
            anonymiser_lead(company, lead, motif='Effacement (garde)')
        return company, Lead.all_objects.get(pk=lead.pk)

    def test_garde_1_le_save_du_scrub_ne_met_rien_en_file(self):
        """Relecture E3 (h), garde 1/5 — l'émetteur ALEA68 se tait pour un lead effacé."""
        self._lead_efface()
        self.assertEqual(self.en_file.call_count, 0)  # garde retirée : 1 tâche (GPS d'avant)

    def test_garde_2_executer_relance_n_appelle_pas_le_moteur(self):
        """Relecture E3 (h), garde 2/5 — la tâche d'un lead effacé n'appelle pas ``relancer``."""
        from apps.ventes.conception import service
        from apps.ventes.conception.receivers import executer_relance

        company, lead = self._lead_efface()
        with mock.patch.object(service, 'relancer') as relancer:
            self.assertIsNone(executer_relance(company.pk, lead_id=lead.pk, origine='filet'))
        relancer.assert_not_called()

    def test_garde_3_relancer_refuse_sans_calculer(self):
        """Relecture E3 (h), garde 3/5 — ``relancer`` refuse un lead effacé AVANT tout calcul."""
        from apps.ventes.conception import moteur
        from apps.ventes.conception.service import relancer
        from apps.ventes.models import ConceptionLead

        company, lead = self._lead_efface()
        with mock.patch.object(moteur, 'calculer_conception') as calcul:
            relance = relancer(lead, company=company, declencheur=_declencheur('manuel'))
        calcul.assert_not_called()
        self.assertEqual((relance.conception, relance.refus['code']), (None, 'lead_efface'))
        self.assertFalse(ConceptionLead.objects.filter(lead_id=lead.pk).exists())

    def test_garde_4_le_chatter_n_ecrit_rien_apres_l_effacement(self):
        """Relecture E3 (h), garde 4/5 — ``conception_recalculee`` d'un lead effacé : aucune ligne."""
        from apps.crm.models import LeadActivity
        from core.events import conception_recalculee

        company, lead = self._lead_efface()
        conception_recalculee.send(
            sender='ventes.ConceptionLead', company_id=company.pk, lead_id=lead.pk, calepinage_id=None,
            version=9, declencheur={'raison': 'GPS latitude 33,57 → —', 'champs': [],
                                    'origine': 'lead_entrees_modifiees'})
        self.assertFalse(LeadActivity.objects.filter(lead_id=lead.pk, new_value='9').exists())

    def test_garde_5_l_effacement_retire_le_marqueur(self):
        """Relecture E3 (h), garde 5/5 — ``lead_erased`` retire le marqueur de relance du lead."""
        from django.core.cache import cache

        from apps.ventes.conception.receivers import _cle, cle_marqueur, mettre_en_file
        from core.events import lead_erased

        company, lead = self._residentiel(facture_hiver=Decimal('1800'))
        mettre_en_file(company.pk, lead_id=lead.pk, origine='lead_entrees_modifiees',
                       champs=[{'champ': 'gps_lat', 'avant': 33.57, 'apres': None}])
        self.assertIsNotNone(cache.get(_cle(company.pk, cle_marqueur(lead.pk))))
        lead_erased.send(sender=None, company=company, crm_lead_id=lead.pk, phone_key='')
        self.assertIsNone(cache.get(_cle(company.pk, cle_marqueur(lead.pk))))

    def test_effacement_caviarde_les_lignes_de_conception_deja_ecrites(self):
        """Relecture E3 B1(f) — le GPS et la facture DITS au chatter avant
        l'effacement (« Conception recalculée : GPS latitude 33,57 → … »)
        sortent de chaque ligne et de chaque ligne archivée du lead."""
        from apps.crm.dsr_provider import anonymiser_lead
        from apps.crm.models import Lead, LeadActivity, LeadActivityArchive

        company, lead = self._cas('res_facture_dirhams')
        _reglages_de_la_societe(company)
        Lead.objects.filter(pk=lead.pk).update(gps_lat=Decimal('33.5731'), gps_lng=Decimal('-7.5898'))
        lead.refresh_from_db()
        self._relancer(lead, company, _declencheur())
        self._enregistrer(lead, gps_lat=Decimal('33.5801'), facture_hiver=Decimal('2437'))
        self._executer_les_taches()
        lignes = LeadActivity.objects.filter(lead=lead, field='conception_version')
        corps = ' '.join(lignes.values_list('body', flat=True))
        self.assertIn('33,58', corps)
        self.assertIn('2 437', corps)
        ligne = lignes.first()
        LeadActivityArchive.objects.create(
            original_id=ligne.pk, company_id=company.pk, lead_id=lead.pk, kind=ligne.kind,
            field=ligne.field, field_label=ligne.field_label, old_value=ligne.old_value,
            new_value=ligne.new_value, body=ligne.body, created_at=ligne.created_at)

        lead.refresh_from_db()
        with self.captureOnCommitCallbacks(execute=True):
            anonymiser_lead(company, lead, motif='Effacement (test B1f)')
        textes = []
        for modele, filtre in ((LeadActivity, {'lead_id': lead.pk, 'field': 'conception_version'}),
                               (LeadActivityArchive, {'lead_id': lead.pk})):
            for body, ancien, nouveau in modele.objects.filter(**filtre).values_list(
                    'body', 'old_value', 'new_value'):
                textes.append(' '.join(str(t) for t in (body, ancien, nouveau) if t))
        tout = ' | '.join(textes)
        for valeur in ('33,57', '33,58', '33.57', '33.58', '7,58', '7.58', '2 437', '2437', '1 800'):
            self.assertNotIn(valeur, tout)  # mutant « corps gardé » : rouge
        self.assertEqual(set(LeadActivityArchive.objects.filter(lead_id=lead.pk).values_list('body', flat=True)),
                         {'Conception recalculée'})

    def test_fusion_ecrite_apres_la_prise_le_marqueur_est_libere(self):
        """Relecture E3 m-a — une fusion lue AVANT la prise de la tâche et
        écrite APRÈS remet le marqueur « en file » sous le jeton de la tâche :
        la fin de la tâche le libère quand même (sinon il reste orphelin et
        chaque modification rafraîchit son délai : plus aucune relance)."""
        from django.core.cache import cache

        from apps.ventes.conception import receivers, service

        company, lead = self._cas('res_facture_dirhams')
        _reglages_de_la_societe(company)
        self._relancer(lead, company, _declencheur())
        self._enregistrer(lead, facture_hiver=Decimal('2400'))
        cle = receivers._cle(company.pk, receivers.cle_marqueur(lead.pk))
        vrai = service.relancer

        def course(*args, **kwargs):
            fusion = dict(cache.get(cle), etat=receivers.EN_FILE)  # l'écriture tardive de la fusion
            cache.set(cle, fusion, receivers.DUREE_MARQUEUR_S)
            return vrai(*args, **kwargs)
        with mock.patch.object(service, 'relancer', side_effect=course):
            self.assertEqual(self._executer_les_taches(), [{'version': 2, 'ecrite': True}])
        self.assertIsNone(cache.get(cle))  # mutant « libérer seulement EN_COURS » : marqueur orphelin
        self._enregistrer(lead, facture_hiver=Decimal('2600'))
        self.assertEqual(self.en_file.call_count, 1)

    def test_pose_regroupee_dans_une_tache_de_fiche_garde_son_calepinage(self):
        """Relecture E3 m-b — une pose regroupée dans une tâche née d'une fiche
        modifiée : la version porte la pose ET son calepinage."""
        from apps.calepinage.models import Calepinage
        from apps.ventes.models import ConceptionLead
        from core.events import pose_enregistree

        company, lead = self._residentiel(facture_hiver=Decimal('1800'))
        _reglages_de_la_societe(company)
        calepinage = Calepinage.objects.create(company=company, lead_id=lead.pk, titre='Toit')
        self._enregistrer(lead, facture_hiver=Decimal('2400'))
        pose_enregistree.send(sender='calepinage.Calepinage', company_id=company.pk,
                              calepinage_id=calepinage.pk, lead_id=lead.pk, empreinte_pose='p' * 64)
        self.assertEqual(self.en_file.call_count, 1)
        self._executer_les_taches()
        version = ConceptionLead.objects.get(lead=lead, courante=True)
        self.assertEqual((version.calepinage_id, version.empreinte_pose),
                         (calepinage.pk, 'p' * 64))  # mutant « marqueur sans calepinage » : None

    def test_geste_regroupe_dans_un_filet_en_file_le_rend_parlant(self):
        """Relecture E3 M3 — un filet en file (muet) puis une fiche modifiée
        regroupée dedans : l'origine devient celle du geste, le chatter le dit."""
        from apps.crm.models import LeadActivity
        from apps.ventes.conception.receivers import mettre_en_file
        from apps.ventes.models import ConceptionLead

        company, lead = self._cas('res_facture_dirhams')
        _reglages_de_la_societe(company)
        self._relancer(lead, company, _declencheur())
        self.assertEqual(mettre_en_file(company.pk, lead_id=lead.pk, origine='filet'), 'lancee')
        self._enregistrer(lead, facture_hiver=Decimal('2400'))
        self.assertEqual(self.en_file.call_count, 1)
        self._executer_les_taches()
        courante = ConceptionLead.objects.get(lead=lead, courante=True)
        self.assertEqual(courante.declencheur['origine'], 'lead_entrees_modifiees')  # mutant « garder filet »
        self.assertEqual(LeadActivity.objects.filter(lead=lead, field='conception_version').count(), 1)

    def test_calepinage_archive_ou_relie_la_conception_du_lead_continue(self):
        """Relecture E3 M1 — le calepinage de la version courante est archivé
        (puis relié à un autre lead) : la relance suivante n'échoue pas, elle
        range la conception du lead SANS cette pose ; ``perimee`` repasse à
        faux ; une ligne d'avertissement, aucune pile d'erreur."""
        from django.utils import timezone

        from apps.calepinage.models import Calepinage
        from apps.crm.models import Lead
        from apps.ventes.models import ConceptionLead
        from apps.ventes.selectors import conception_courante
        from core.events import pose_enregistree

        company, lead = self._residentiel(facture_hiver=Decimal('1800'))
        _reglages_de_la_societe(company)
        calepinage = Calepinage.objects.create(company=company, lead_id=lead.pk, titre='Toit')
        pose_enregistree.send(sender='calepinage.Calepinage', company_id=company.pk,
                              calepinage_id=calepinage.pk, lead_id=lead.pk, empreinte_pose='p' * 64)
        self._executer_les_taches()
        Calepinage.objects.filter(pk=calepinage.pk).update(archive_le=timezone.now())

        self._enregistrer(lead, facture_hiver=Decimal('2400'))
        with self.assertLogs('apps.ventes.conception', level='WARNING') as journaux:
            rendus = self._executer_les_taches()
        self.assertEqual(rendus, [{'version': 2, 'ecrite': True}])  # mutant « ValueError » : [None]
        self.assertFalse(any(r.exc_info for r in journaux.records))
        courante = ConceptionLead.objects.get(lead=lead, courante=True)
        self.assertEqual((courante.calepinage_id, courante.empreinte_pose), (None, ''))
        self.assertFalse(conception_courante(company, lead.pk)['perimee'])
        self.assertEqual(self.en_file.call_count, 0)

        # Relié à un autre lead : même repli, la conception suit la fiche.
        autre = Lead.objects.create(company=company, nom='Autre', prenom='Lead', ville=lead.ville,
                                    facture_hiver=Decimal('1800'))
        Calepinage.objects.filter(pk=calepinage.pk).update(archive_le=None, lead_id=autre.pk)
        ConceptionLead.objects.filter(pk=courante.pk).update(calepinage_id=calepinage.pk)
        self._enregistrer(lead, facture_hiver=Decimal('2600'))
        with self.assertLogs('apps.ventes.conception', level='WARNING'):
            self.assertEqual(self._executer_les_taches(), [{'version': 3, 'ecrite': True}])
        self.assertIsNone(ConceptionLead.objects.get(lead=lead, courante=True).calepinage_id)

    # ── ADEV140 — le filet d'empreinte à la lecture ─────────────────────────
    def test_entree_changee_sans_evenement_perimee_puis_une_relance(self):
        from apps.crm.models import Lead
        from apps.ventes.models import ConceptionLead
        from apps.ventes.selectors import conception_courante

        company, lead = self._cas('res_facture_dirhams')
        _reglages_de_la_societe(company)
        self._relancer(lead, company, _declencheur())
        self.assertFalse(conception_courante(company, lead.pk)['perimee'])  # à jour : rien en file
        self.assertEqual(self.en_file.call_count, 0)

        Lead.objects.filter(pk=lead.pk).update(facture_hiver=Decimal('2400'))  # écriture directe : aucun événement
        avant = ConceptionLead.objects.count()
        lue = conception_courante(company, lead.pk)
        self.assertEqual((lue['perimee'], lue['version'], lue['declencheur']['origine']), (True, 1, 'remplissage'))
        self.assertEqual(conception_courante(company, lead.pk)['perimee'], True)  # relire : toujours UNE tâche
        self.assertEqual(self.en_file.call_count, 1)  # mutant « toujours perimee: false » : 0
        # Relecture E3 (d) : l'origine vit dans le marqueur, la tâche ne porte que des identifiants.
        from django.core.cache import cache

        from apps.ventes.conception.receivers import _cle, cle_marqueur
        self.assertEqual(cache.get(_cle(company.pk, cle_marqueur(lead.pk)))['origine'], 'filet')
        self.assertEqual(set(self.en_file.call_args.kwargs['kwargs']),
                         {'company_id', 'lead_id', 'calepinage_id', 'jeton'})  # mutant « valeurs au courtier »
        self.assertEqual(ConceptionLead.objects.count(), avant)  # la lecture n'écrit pas

        self.assertEqual(self._executer_les_taches(), [{'version': 2, 'ecrite': True}])
        relue = conception_courante(company, lead.pk)
        self.assertEqual((relue['perimee'], relue['version'], relue['declencheur']['origine']), (False, 2, 'filet'))
        self.assertEqual(relue['entrees_utilisees']['facture_hiver']['valeur'], 2400.0)
        self.assertEqual(self.en_file.call_count, 0)

    def _calepinage_designe(self, company, lead, **entree):
        """Un calepinage du lead dont l'étape Électrique porte ``entree`` (désignations)."""
        from apps.calepinage.models import Calepinage
        from apps.calepinage.services.electrique import CLE_ENTREE

        return Calepinage.objects.create(company=company, lead_id=lead.pk, titre='Toit',
                                         resultat={CLE_ENTREE: dict(entree)})

    def test_e6b1_designation_a_la_main_la_lecture_dit_a_jour(self):
        """Relecture E6 B1 — une désignation à la main entre dans l'empreinte rangée ;
        la lecture recalcule LA MÊME empreinte : ``perimee`` faux, rien en file
        (mutant « empreinte de lecture sans les désignations » : perimee vrai, une tâche)."""
        from apps.stock.models import Produit
        from apps.ventes.selectors import conception_courante

        company, lead = self._cas('res_facture_dirhams')
        _reglages_de_la_societe(company)
        onduleur = Produit.objects.get(company=company, nom='Onduleur réseau Huawei 5kW Monophasé')
        calepinage = self._calepinage_designe(company, lead, onduleur_produit=onduleur.pk)
        relance = self._relancer(lead, company, _declencheur('pose_enregistree'), calepinage_id=calepinage.pk)
        self.assertTrue(relance.ecrite)
        self.en_file.reset_mock()
        lue = conception_courante(company, lead.pk)
        self.assertEqual((lue['perimee'], lue['calepinage']), (False, calepinage.pk))
        self.assertEqual(self.en_file.call_count, 0)
        self.assertFalse(conception_courante(company, lead.pk)['perimee'])
        self.assertEqual(self.en_file.call_count, 0)
        # Une désignation SANS compte de panneaux n'est plus un refus « indiquez nb_panneaux ».
        self.assertEqual(lue['etat'], 'complet', lue['refus'])

    def test_e6b1_designation_archivee_jamais_un_refus(self):
        """Relecture E6 B2 — un module désigné puis archivé : la conception reste
        ``complet`` avec le module du moteur et la phrase qui nomme le produit (jamais son
        identifiant) ; mutant « imposer quand même » : refus."""
        self._hors_catalogue('archive', {'is_archived': True})

    def test_e6b1_designation_sans_prix_jamais_un_refus(self):
        self._hors_catalogue('sans_prix', {'prix_vente': Decimal('0')})

    def _hors_catalogue(self, cas, champs):
        from apps.stock.models import Produit
        from apps.ventes.selectors import conception_courante

        def _textes(noeud):
            if isinstance(noeud, dict):
                return [t for v in noeud.values() for t in _textes(v)]
            if isinstance(noeud, list):
                return [t for v in noeud for t in _textes(v)]
            return [noeud] if isinstance(noeud, str) else []

        company, lead = self._cas('res_facture_dirhams')
        _reglages_de_la_societe(company)
        module = Produit.objects.create(company=company, nom='Panneau Désigné 600W', sku='E6B2-%s' % cas,
                                        prix_vente=Decimal('1300'), prix_achat=Decimal('1'),
                                        quantite_stock=10)
        calepinage = self._calepinage_designe(company, lead, module_produit=module.pk)
        Produit.objects.filter(pk=module.pk).update(**champs)
        self._relancer(lead, company, _declencheur('pose_enregistree'), calepinage_id=calepinage.pk)
        lue = conception_courante(company, lead.pk)
        self.assertEqual(lue['etat'], 'complet', lue['refus'])
        retenue = lue['valeurs'][lue['option_retenue']]
        self.assertNotEqual(retenue['module_produit']['valeur'], module.pk)
        self.assertIn(
            'Le matériel désigné « Panneau Désigné 600W » n\'est plus au catalogue de vente : la conception '
            'utilise le matériel choisi par le moteur. Désignez un autre produit à l\'étape Électrique, ou '
            'remettez celui-ci en vente dans Stock.', [s['message'] for s in lue['suppositions']])
        self.assertFalse([t for t in _textes(lue) if str(module.pk) in t.split()
                          or 'n° %s' % module.pk in t or 'Produit %s' % module.pk in t])
        self.assertFalse(lue['perimee'])

    def test_e6b1_m2_materiel_designe_dit_impose(self):
        """Relecture E6 m2 — l'onduleur DÉSIGNÉ à la main est porté par la conception avec
        la source ``impose`` (contrat ``source_valeur``) et figure dans ``entrees_utilisees``
        avec sa provenance ; le reste reste ``moteur``. Mutant « source moteur » : rouge."""
        from apps.stock.models import Produit
        from apps.ventes.selectors import conception_courante

        company, lead = self._cas('res_facture_dirhams')
        _reglages_de_la_societe(company)
        onduleur = Produit.objects.get(company=company, nom='Onduleur réseau Huawei 5kW Monophasé')
        calepinage = self._calepinage_designe(company, lead, onduleur_produit=onduleur.pk)
        self._relancer(lead, company, _declencheur('pose_enregistree'), calepinage_id=calepinage.pk)
        lue = conception_courante(company, lead.pk)
        self.assertEqual(lue['etat'], 'complet', lue['refus'])
        retenue = lue['valeurs'][lue['option_retenue']]
        self.assertEqual(retenue['onduleur_produit'], {'valeur': onduleur.pk, 'unite': None, 'source': 'impose'})
        self.assertEqual(retenue['onduleurs']['source'], 'impose')
        self.assertEqual((retenue['module']['source'], retenue['nb_panneaux']['source']), ('moteur', 'moteur'))
        self.assertEqual(lue['entrees_utilisees']['onduleur_designe'],
                         {'valeur': onduleur.nom, 'source': 'calepinage'})
        self.assertNotIn('module_designe', lue['entrees_utilisees'])

    def test_e6e_une_conception_quel_que_soit_le_declencheur(self):
        """Lane E6e, item 1 (T4-X5-003) — un lead dont le calepinage OUVERT porte un onduleur
        désigné à l'étape Électrique : la conception rangée (empreinte et valeurs) est LA
        MÊME, que le recalcul parte du calepinage (pose enregistrée) ou du lead (porte de
        lecture, fiche modifiée, devis automatique, commande de remplissage) ; et, une fois
        rangée depuis le calepinage, aucun déclencheur du lead ne la refait sans lui."""
        from types import SimpleNamespace

        from django.core.management import call_command

        from apps.calepinage.models import Calepinage
        from apps.stock.models import Produit
        from apps.ventes.conception.receivers import mettre_en_file
        from apps.ventes.conception.service import conception_ou_calcul
        from apps.ventes.domain.creation_auto import conception_pour_le_devis
        from apps.ventes.models import ConceptionLead
        from apps.ventes.selectors import conception_courante

        company, lead = self._cas('res_facture_dirhams')
        _reglages_de_la_societe(company)
        deye = Produit.objects.get(company=company, nom='Onduleur hybride Deye 5kW Monophasé')
        module = Produit.objects.create(company=company, nom='Panneau Canadian Solar 710W', sku='E6E-710',
                                        prix_vente=Decimal('1500'), prix_achat=Decimal('1'), quantite_stock=50)
        calepinage = self._calepinage_designe(company, lead, onduleur_produit=deye.pk, module_produit=module.pk)
        Calepinage.objects.filter(pk=calepinage.pk).update(layout_hash='h' * 64)
        user = self._utilisateur(company)

        def _rangee():
            courante = ConceptionLead.objects.get(company=company, lead=lead, courante=True)
            retenue = courante.valeurs[courante.option_retenue]
            return (courante.empreinte, courante.calepinage_id, courante.option_retenue,
                    retenue['onduleur_produit']['valeur'], retenue['module_produit']['valeur'],
                    retenue['nb_panneaux']['valeur'], retenue['puissance_kwc']['valeur'])

        toit = SimpleNamespace(empreinte='h' * 64, plafond_panneaux=None)
        self._relancer(None, company, _declencheur('pose_enregistree'), calepinage_id=calepinage.pk, toit=toit)
        reference = _rangee()
        self.assertEqual(reference[3:5], (deye.pk, module.pk))

        def _taches():
            self._executer_les_taches()

        declencheurs = {
            'porte_de_lecture': lambda: (conception_ou_calcul(company, lead.pk), _taches()),
            'fiche_modifiee': lambda: (mettre_en_file(company.pk, lead_id=lead.pk, origine='lead_entrees_modifiees',
                                                      champs=[]), _taches()),
            'devis_automatique': lambda: conception_pour_le_devis(lead, company, user),
            'remplissage': lambda: self._commande_remplir(call_command, company),
        }
        for nom, declencher in declencheurs.items():
            with self.subTest(declencheur=nom, premier=True):  # le lead déclenche le PREMIER calcul
                ConceptionLead.objects.filter(company=company, lead=lead).delete()
                declencher()
                self.assertEqual(_rangee(), reference)
                self.assertFalse(conception_courante(company, lead.pk)['perimee'])  # le filet lit la même pose
        for nom, declencher in declencheurs.items():
            with self.subTest(declencheur=nom, premier=False):  # rangée depuis le calepinage : rien ne bouge
                ConceptionLead.objects.filter(company=company, lead=lead).delete()
                self._relancer(None, company, _declencheur('pose_enregistree'), calepinage_id=calepinage.pk,
                               toit=toit)
                declencher()
                self.assertEqual(ConceptionLead.objects.filter(company=company, lead=lead).count(), 1)
                self.assertEqual(_rangee(), reference)

    def test_e6e_conception_recalculee_dit_le_materiel_designe(self):
        """Lane E6e, item 2 — une désignation à l'étape Électrique change la conception : la
        phrase rangée (lue au chatter du lead et à l'atelier) dit « matériel désigné à
        l'atelier : <module> / <onduleur> », jamais un « Module désigné X → — » parasite sur
        un recalcul qui ne touche pas au matériel (filet, fiche modifiée)."""
        from apps.calepinage.models import Calepinage
        from apps.calepinage.services.electrique import CLE_ENTREE
        from apps.stock.models import Produit
        from apps.ventes.models import ConceptionLead

        company, lead = self._cas('res_facture_dirhams')
        _reglages_de_la_societe(company)
        deye = Produit.objects.get(company=company, nom='Onduleur hybride Deye 5kW Monophasé')
        module = Produit.objects.create(company=company, nom='Panneau Canadian Solar 710W', sku='E6E-710b',
                                        prix_vente=Decimal('1500'), prix_achat=Decimal('1'), quantite_stock=50)
        calepinage = self._calepinage_designe(company, lead)
        self._relancer(lead, company, _declencheur('pose_enregistree'))
        Calepinage.objects.filter(pk=calepinage.pk).update(
            resultat={CLE_ENTREE: {'onduleur_produit': deye.pk, 'module_produit': module.pk}})
        self.assertTrue(self._relancer(lead, company, _declencheur('pose_enregistree')).ecrite)
        courante = ConceptionLead.objects.get(lead=lead, courante=True)
        self.assertTrue(courante.declencheur['raison'].endswith(
            " : matériel désigné à l'atelier : Panneau Canadian Solar 710W / Onduleur hybride Deye 5kW Monophasé"),
            courante.declencheur['raison'])
        self.assertEqual([c['champ'] for c in courante.declencheur['champs']], ['materiel_designe'])

        self._relancer(lead, company, _declencheur('filet'), forcer=True)  # même matériel : rien à dire de lui
        courante = ConceptionLead.objects.get(lead=lead, courante=True)
        self.assertEqual(courante.declencheur['champs'], [])

    def test_x9_009_onduleur_designe_garde_la_taille_de_son_option(self):
        """Constat T4-X9-009 (relecteur X9, 25/11) — un onduleur HYBRIDE désigné à l'étape
        Électrique ne laisse que l'option « avec batterie » : sa taille est celle que le
        moteur décide pour CETTE option (son propre optimum), jamais celle de l'option
        « sans batterie ». Mutant « taille décidée sans regarder l'onduleur désigné » : la
        conception retenue perd des panneaux sans que la fiche ait changé."""
        from apps.stock.models import Produit
        from apps.ventes.domain import creation_auto_residentiel as R
        from apps.ventes.selectors import conception_courante

        company, lead = self._cas('res_facture_dirhams')
        _reglages_de_la_societe(company)
        reel = R._panneaux_dimensionnement_horaire

        def deux_tailles(**kw):  # le moteur horaire, dont l'axe « avec batterie » retient 2 panneaux de plus
            nombre, watt, source, avec = reel(**kw)
            plus = dict(avec or {}, nb_panneaux=nombre + 2, panel_watt=watt,
                        kwc=round((nombre + 2) * watt / 1000, 2))
            plus.setdefault('batterie_kwh', 10.0)
            return nombre, watt, source, plus

        with mock.patch.object(R, '_panneaux_dimensionnement_horaire', side_effect=deux_tailles):
            self._relancer(lead, company, _declencheur())
            temoin = conception_courante(company, lead.pk)['valeurs']
            tailles = {option: v['nb_panneaux']['valeur'] for option, v in temoin.items()}
            self.assertEqual(set(tailles), {'sans', 'avec'})
            self.assertEqual(tailles['avec'], tailles['sans'] + 2)
            deye = Produit.objects.get(company=company, nom='Onduleur hybride Deye 5kW Monophasé')
            calepinage = self._calepinage_designe(company, lead, onduleur_produit=deye.pk)
            self._relancer(lead, company, _declencheur('pose_enregistree'), calepinage_id=calepinage.pk)
            lue = conception_courante(company, lead.pk)
        self.assertEqual((lue['etat'], lue['option_retenue']), ('complet', 'avec'), lue['refus'])
        retenue = lue['valeurs']['avec']
        self.assertEqual(retenue['onduleur_produit']['valeur'], deye.pk)
        self.assertEqual(retenue['nb_panneaux']['valeur'], tailles['avec'])

    def _commande_remplir(self, call_command, company):
        import io

        with self.captureOnCommitCallbacks(execute=True):
            call_command('remplir_conceptions', '--company', str(company.pk), '--appliquer', stdout=io.StringIO())


# ── ADEV141 — remplir les conceptions des leads existants, liste d'abord ─────

class RemplirConceptionsTests(_emprunt(FigeageDevisAutoTests, 'setUp', '_patcher', '_utilisateur', '_residentiel',
                                       '_ci', '_agricole', '_fiches_residentielles', '_site_isole', '_structures',
                                       '_fiches_ci', '_cas'), TestCase):
    """ADEV141 — ``manage.py remplir_conceptions`` : sans option, la LISTE
    (rien n'est écrit) ; ``--appliquer`` range par l'écrivain unique, société
    par société ; aucun devis n'est modifié ; rejouer n'écrit rien."""

    def _commande(self, *args):
        import io

        from django.core.management import call_command

        sortie = io.StringIO()
        with self.captureOnCommitCallbacks(execute=True):
            call_command('remplir_conceptions', *args, stdout=sortie)
        return sortie.getvalue()

    def test_liste_puis_appliquer_societe_isolee_aucun_devis_touche(self):
        from django.utils import timezone

        from apps.crm.models import Lead
        from apps.ventes.models import ConceptionLead, Devis
        from apps.ventes.services import build_devis_auto
        from authentication.models import Company

        company, premier = self._residentiel(facture_hiver=Decimal('1800'))
        _reglages_de_la_societe(company)
        situes = [premier] + [Lead.objects.create(company=company, nom='Situe', prenom=str(i), ville=premier.ville,
                                                  facture_hiver=Decimal('1500') + i * 100) for i in range(6)]
        sans_lieu = [Lead.objects.create(company=company, nom='SansLieu', prenom=str(i), ville='',
                                         facture_hiver=Decimal('1800')) for i in range(3)]
        autre = Company.objects.create(nom='Autre remplissage', slug='autre-remplissage-conception')
        lead_b = Lead.objects.create(company=autre, nom='B', prenom='Lead', ville=premier.ville,
                                     facture_hiver=Decimal('1800'))
        devis = build_devis_auto(lead=premier, user=self._utilisateur(company), company=company)
        Devis.objects.filter(pk=devis.pk).update(statut='envoye', date_envoi=timezone.now())
        photo = _photo_devis(devis.pk)

        # ADEV142 — le devis automatique de ``premier`` a rangé SA conception (v1).
        self.assertEqual(list(ConceptionLead.objects.values_list('lead_id', flat=True)), [premier.pk])
        liste = self._commande('--company', str(company.pk))
        self.assertEqual(ConceptionLead.objects.count(), 1, liste)  # mutant « écrire sans --appliquer » : rouge
        for lead in situes:
            self.assertIn(f'lead #{lead.pk} [residentiel] option retenue : ', liste)
        for lead in sans_lieu:
            self.assertIn(f'lead #{lead.pk} [residentiel] REFUS localisation_inconnue (ville)', liste)
        self.assertIn('LISTE : 7 conception(s) complète(s), 3 refus, 0 erreur(s)', liste)
        self.assertNotIn(f'lead #{lead_b.pk} ', liste)

        applique = self._commande('--company', str(company.pk), '--appliquer')
        self.assertIn('APPLIQUÉ : 6 version(s) rangée(s), 1 inchangée(s), 3 sans ville ni GPS', applique)
        rangees = ConceptionLead.objects.filter(company=company, courante=True)
        self.assertEqual(set(rangees.values_list('lead_id', flat=True)), {lead.pk for lead in situes})
        for version in rangees:
            self.assertEqual((version.etat, version.declencheur['origine'], version.version),
                             ('complet', 'remplissage', 1))
        self.assertFalse(ConceptionLead.objects.filter(company=autre).exists())
        self.assertEqual(_photo_devis(devis.pk), photo)  # le devis envoyé n'a pas bougé

        rejoue = self._commande('--company', str(company.pk), '--appliquer')
        self.assertIn('APPLIQUÉ : 0 version(s) rangée(s), 7 inchangée(s)', rejoue)
        self.assertEqual(ConceptionLead.objects.filter(company=company).count(), 7)
        self.assertEqual(_photo_devis(devis.pk), photo)

    def _banc_des_ecarts(self):
        """ADEV151 — deux leads à toit tracé (un brouillon, un devis envoyé) et un lead sans toit."""
        from django.utils import timezone

        from apps.calepinage.models import Calepinage
        from apps.crm.models import Lead
        from apps.ventes.models import Devis
        from apps.ventes.services import build_devis_auto

        company, brouillon_lead = self._residentiel(facture_hiver=Decimal('1800'))
        _reglages_de_la_societe(company)
        envoye_lead = Lead.objects.create(company=company, nom='Envoyé', prenom='Toit', ville=brouillon_lead.ville,
                                          facture_hiver=Decimal('2000'))
        sans_toit = Lead.objects.create(company=company, nom='Sans', prenom='Toit', ville=brouillon_lead.ville,
                                        facture_hiver=Decimal('1600'))
        auteur = self._utilisateur(company)
        with self.captureOnCommitCallbacks(execute=True):
            brouillon = build_devis_auto(lead=brouillon_lead, user=auteur, company=company)
            envoye = build_devis_auto(lead=envoye_lead, user=auteur, company=company)
        Devis.objects.filter(pk=envoye.pk).update(statut='envoye', date_envoi=timezone.now())
        toits = {}
        for lead, empreinte in ((brouillon_lead, 'a' * 64), (envoye_lead, 'b' * 64)):
            toit = Calepinage.objects.create(company=company, lead_id=lead.pk, titre='Toit', resultat={'x': 1})
            Calepinage.objects.filter(pk=toit.pk).update(layout_hash=empreinte)
            toits[lead.pk] = toit.pk
        return company, brouillon_lead, envoye_lead, sans_toit, brouillon, envoye, toits

    def test_adev151_ecarts_liste_brouillons_production_pose_zero_ecriture(self):
        """ADEV151 — ``--ecarts`` : deux leads à toit tracé (un brouillon, un envoyé) listés,
        production actuelle contre production de la pose (niveau 15 forcé dans le
        processus), écart en kWh et en % ; un lead sans toit absent ; RIEN d'écrit.
        Relecture E6 M3 — la simulation n'est PAS doublée à la frontière d'écriture : elle
        écrit vraiment ``Calepinage.resultat`` (``modifier_resultat``, sous verrou), et tout
        est annulé lead par lead ; « actuel » = la conception RANGÉE ; ``--limite``,
        ``--lead`` et la ligne de progression."""
        import io

        from django.core.management import call_command

        from apps.calepinage.models import Calepinage
        from apps.calepinage.services.resultat import modifier_resultat
        from apps.ventes.conception import porte_calepinage as P
        from apps.ventes.domain import regles_calcul as RC
        from apps.ventes.management.commands import remplir_conceptions as commande
        from apps.ventes.models import ConceptionLead

        company, brouillon_lead, envoye_lead, sans_toit, brouillon, envoye, toits = self._banc_des_ecarts()
        photos = (_photo_devis(brouillon.pk), _photo_devis(envoye.pk))
        conceptions = _json(list(ConceptionLead.objects.order_by('pk').values()))
        resultats = _json(list(Calepinage.objects.order_by('pk').values('pk', 'resultat')))
        rangee = ConceptionLead.objects.get(lead=brouillon_lead, courante=True)
        production_rangee = rangee.valeurs[rangee.option_retenue]['production_annuelle']['valeur']
        pose = {'nb_panneaux': 10, 'kwc': None, 'complete': True, 'a_la_main': False, 'empreinte_pose': '',
                'manquants': [], 'module_produit': None}
        kwh = [150.0, 160.0, 190.0, 210.0, 230.0, 240.0, 250.0, 240.0, 210.0, 180.0, 150.0, 140.0]

        def simuler(calepinage, *, materiel=None, client=None):  # ÉCRIT vraiment, sous verrou
            modifier_resultat(calepinage, lambda resultat: resultat.update(e6_simule=True))
            return {'complete': True}

        def lire(calepinage, **_kw):
            if not (calepinage.resultat or {}).get('e6_simule'):
                return None  # jamais simulée
            return {'perime': False, 'kwc_simule': None, 'source': 'calepinage_enregistre', 'complete': True,
                    'kwh_kwc_annuel': sum(kwh), 'kwh_kwc_mensuel': list(kwh), 'pertes_et_ombrage_inclus': True}

        def lancer(*args):
            sortie, erreurs = io.StringIO(), io.StringIO()
            call_command('remplir_conceptions', *args, stdout=sortie, stderr=erreurs)
            return sortie.getvalue(), erreurs.getvalue()
        with mock.patch.object(P, 'pose_du_calepinage', return_value=pose), \
                mock.patch('apps.calepinage.services.pose_pour_moteur.simuler_pose', side_effect=simuler) as simulee, \
                mock.patch('apps.calepinage.selectors_devis.productible_pose_du_calepinage', side_effect=lire), \
                mock.patch.object(commande, 'PROGRESSION_TOUS', 1):
            liste, progression = lancer('--company', str(company.pk), '--ecarts')
            limitee, _p = lancer('--company', str(company.pk), '--ecarts', '--limite', '1')
            seule, _p = lancer('--company', str(company.pk), '--ecarts', '--lead', str(envoye_lead.pk))
        self.assertEqual(RC.REGLES_COURANTES, 14)  # le niveau 15 n'est jamais laissé courant
        self.assertTrue(simulee.called)  # la simulation a tourné (et écrit) dans la commande
        ligne = next(li for li in liste.splitlines()
                     if li.startswith(f'  lead #{brouillon_lead.pk} (calepinage #{toits[brouillon_lead.pk]})'))
        self.assertIn('production %s → ' % '{:,.0f}'.format(production_rangee).replace(',', ' '), ligne)
        self.assertNotIn('simulation de la pose non faite', ligne)  # mutant « niveau 15 du module seul »
        self.assertIn(f'{brouillon.reference} brouillon jamais envoyé — changera : oui', liste)
        self.assertIn(f'{envoye.reference} envoye — lecture seule : ne changera jamais', liste)
        self.assertNotIn(f'lead #{sans_toit.pk} ', liste)
        self.assertIn('ÉCARTS : 2 lead(s) à toit tracé listé(s)', liste)
        self.assertIn('lead(s) examiné(s)', progression)
        self.assertIn('ÉCARTS : 1 lead(s)', limitee)
        self.assertIn(f'lead #{envoye_lead.pk} ', seule)
        self.assertNotIn(f'lead #{brouillon_lead.pk} ', seule)
        # RIEN d'écrit : conceptions, calepinages (écriture de la simulation annulée) et devis.
        self.assertEqual(_json(list(ConceptionLead.objects.order_by('pk').values())), conceptions)
        self.assertEqual(_json(list(Calepinage.objects.order_by('pk').values('pk', 'resultat'))), resultats)
        self.assertEqual((_photo_devis(brouillon.pk), _photo_devis(envoye.pk)), photos)

    def test_adev154_ecarts_sans_toit_plan_par_defaut_zero_ecriture(self):
        """ADEV154 — ``--ecarts-sans-toit`` : deux leads sans toit listés (production du moteur
        contre le plan par défaut au kWc et au matériel de l'option, pente du lead ou supposée),
        écart et « changera » ; moyenne et plus grand écart EN TÊTE ; un lead à toit absent ;
        RIEN d'écrit (mutant « écrire pendant la liste » : rouge)."""
        import io

        from django.core.management import call_command

        from apps.calepinage.models import Calepinage
        from apps.ventes.conception.moteur import calculer_conception
        from apps.ventes.models import ConceptionLead

        company, toit_lead, _envoye_lead, sans_toit, _b, _e, _toits = self._banc_des_ecarts()
        pentu = type(sans_toit).objects.create(company=company, nom='Pentu', prenom='Sans toit', ville=sans_toit.ville,
                                               facture_hiver=Decimal('2200'), inclinaison_deg=Decimal('18'))
        sans_ville = type(sans_toit).objects.create(company=company, nom='Sans', prenom='Ville', ville='',
                                                    facture_hiver=Decimal('1800'))
        attendus = {lead.pk: calculer_conception(lead, company) for lead in (sans_toit, pentu)}
        instantane = (_json(list(ConceptionLead.objects.order_by('pk').values())),
                      _json(list(Calepinage.objects.order_by('pk').values())))
        appels = []

        def plan(company_, lat, lon, kwc, **kw):
            appels.append((kw['lead_id'], kwc, kw['pente'], kw['produits'], kw['nb_panneaux']))
            # ACAL2045 — les champs du lead qui font la pose supposée sont passés au plan.
            self.assertEqual((kw['type_installation'], kw['type_toiture']), (None, None))
            # Le lead pentu : fiche du module VIDE (puissance de la conception, deux étapes omises).
            vide = [{'code': 'puissance_module_de_la_conception'}] + [{'code': 'fiche_module_incomplete'}] * 2
            return {'production_annuelle': kwc * 1500.0,
                    'suppositions': ([] if kw['pente'] is not None else [{'champ': 'inclinaison_deg'}])
                    + [{'code': 'pose_supposee', 'valeur': 'affleurante'}]
                    + (vide if kw['lead_id'] == pentu.pk else [])}
        sortie = io.StringIO()
        with mock.patch('apps.calepinage.services.plan_par_defaut.simuler_plan_par_defaut', side_effect=plan):
            call_command('remplir_conceptions', '--company', str(company.pk), '--ecarts-sans-toit', stdout=sortie,
                         stderr=io.StringIO())
        liste = sortie.getvalue()
        lignes = liste.splitlines()
        options = sum(len(attendus[lead.pk].valeurs) for lead in (sans_toit, pentu))
        vides, completes = len(attendus[pentu.pk].valeurs), len(attendus[sans_toit.pk].valeurs)
        # Les COMPTES d'abord, puis les moyennes (fiche complète, puis toutes les lignes), avant les leads.
        self.assertEqual(lignes[1], f"  COMPTES : 3 lead(s) sans toit listé(s) ; {options} ligne(s) d'option "
                                    f"simulée(s), dont {vides} avec une fiche de module vide (production "
                                    "surestimée) ; 0 non simulée(s) : aucune ; 1 lead(s) refusé(s) par le moteur : "
                                    "1 × localisation_inconnue", liste)
        self.assertTrue(lignes[2].startswith(f'  ÉCART MOYEN (fiche complète, {completes} ligne(s)) : '), liste)
        self.assertIn('PLUS GRAND : lead #%d ' % sans_toit.pk, lignes[2])  # jamais une ligne à fiche vide
        self.assertTrue(lignes[3].startswith(f'  ÉCART MOYEN (toutes les lignes simulées, {options}) : '), liste)
        self.assertNotIn(f'lead #{toit_lead.pk} ', liste)
        self.assertIn('ÉCARTS SANS TOIT : 3 lead(s) sans toit tracé listé(s)', liste)
        # Le lead refusé n'est PAS un écart : un seul bloc, à la fin, après toutes les options.
        bloc = lignes.index('  LEADS REFUSÉS PAR LE MOTEUR (1, pas des écarts) :')
        self.assertTrue(lignes[bloc + 1].startswith(f'    lead #{sans_ville.pk} : localisation_inconnue — '))
        self.assertFalse([li for li in lignes[bloc:] if '(sans toit) option' in li])
        for lead in (sans_toit, pentu):
            conception = attendus[lead.pk]
            for option, valeurs in conception.valeurs.items():
                kwc, avant = valeurs['puissance_kwc']['valeur'], valeurs['production_annuelle']['valeur']
                self.assertIn((lead.pk, kwc, 18.0 if lead is pentu else None,
                               {'module': valeurs['module_produit']['valeur'],
                                'onduleur': valeurs['onduleur_produit']['valeur']},
                               valeurs['nb_panneaux']['valeur']), appels)
                ligne = next(li for li in lignes if li.startswith(f'  lead #{lead.pk} (sans toit) option {option} '))
                self.assertLess(lignes.index(ligne), bloc)
                ecart = kwc * 1500.0 - avant
                # Le RENDEMENT avant → après (kWh/kWc) : c'est lui qui bouge, pas la taille.
                self.assertIn('rendement %s → 1 500 kWh/kWc' % '{:,.0f}'.format(avant / kwc).replace(',', ' '), ligne)
                self.assertIn('production %s → %s kWh/an (écart %s kWh, %+.1f %%' % (
                    '{:,.0f}'.format(avant).replace(',', ' '), '{:,.0f}'.format(kwc * 1500.0).replace(',', ' '),
                    '{:+,.0f}'.format(ecart).replace(',', ' '), ecart / avant * 100), ligne)
                self.assertIn('pente supposée 30°' if lead is sans_toit else 'changera : ', ligne)
                self.assertIn(', pose supposée affleurante', ligne)  # ACAL2045 : la pose supposée, dite
                drapeau = ('fiche du module vide : 2 étape(s) de pertes non appliquée(s), puissance prise de '
                           'la conception')
                (self.assertIn if lead is pentu else self.assertNotIn)(drapeau, ligne)
                self.assertIn('changera : oui' if round(kwc * 1500.0) != round(avant) else 'changera : non', ligne)
        self.assertEqual((_json(list(ConceptionLead.objects.order_by('pk').values())),
                          _json(list(Calepinage.objects.order_by('pk').values()))), instantane)
        # Aucune ligne à fiche complète : la tête le DIT au lieu d'une moyenne.
        from types import SimpleNamespace

        from apps.ventes.management.commands.remplir_conceptions import _sortie_sans_toit
        seule = {'option': 'sans', 'kwc': 5.0, 'avant': 7000.0, 'apres': 8000.0, 'kwc_plan': 5.0, 'refus': None,
                 'pente_supposee': False, 'etapes_sans_fiche': 1, 'puissance_conception': True, 'fiche_vide': True}
        tete = _sortie_sans_toit([(SimpleNamespace(pk=1), {'options': [seule]})])
        self.assertEqual(tete[1], '  ÉCART MOYEN (fiche complète) : aucune ligne simulée avec une fiche de module '
                                  'complète — aucun écart fiable à moyenner')
        self.assertTrue(tete[2].startswith('  ÉCART MOYEN (toutes les lignes simulées, 1) : '))

    def test_appliquer_ne_touche_pas_une_version_courante_venue_d_un_toit(self):
        """Relecture E3 M2 — un remplissage, pas un rafraîchissement : le lead
        dont la version courante vient d'une pose (empreinte du toit) n'est
        pas recalculé sans elle ; ``--appliquer`` exige ``--company``."""
        from types import SimpleNamespace

        from django.core.management.base import CommandError

        from apps.ventes.conception.service import relancer
        from apps.ventes.models import ConceptionLead

        company, lead = self._residentiel(facture_hiver=Decimal('1800'))
        _reglages_de_la_societe(company)
        with self.captureOnCommitCallbacks(execute=True):
            relancer(lead, company=company, declencheur={'origine': 'pose_enregistree', 'champs': []},
                     toit=SimpleNamespace(empreinte='p' * 64, plafond_panneaux=None))
        avant = ConceptionLead.objects.get(lead=lead, courante=True)
        self.assertEqual(avant.empreinte_pose, 'p' * 64)

        self.assertIn('APPLIQUÉ : 0 version(s) rangée(s), 1 inchangée(s)',
                      self._commande('--company', str(company.pk), '--appliquer'))
        apres = ConceptionLead.objects.get(lead=lead, courante=True)  # mutant « relancer sans toit » : v2, ''
        self.assertEqual((apres.pk, apres.version, apres.empreinte_pose), (avant.pk, 1, 'p' * 64))
        with self.assertRaises(CommandError):
            self._commande('--appliquer')

    def test_appliquer_premier_calcul_avec_la_pose_deja_enregistree(self):
        """Relecture E3 M2 (suite) — un lead dont le calepinage ouvert porte
        déjà une pose, sans version : ``--appliquer`` range sa première
        version AVEC l'empreinte de cette pose et son calepinage."""
        from apps.calepinage.models import Calepinage
        from apps.ventes.models import ConceptionLead

        company, lead = self._residentiel(facture_hiver=Decimal('1800'))
        _reglages_de_la_societe(company)
        calepinage = Calepinage.objects.create(company=company, lead_id=lead.pk, titre='Toit posé',
                                               layout_hash='a' * 64)
        self._commande('--company', str(company.pk), '--appliquer')
        version = ConceptionLead.objects.get(lead=lead, courante=True)
        self.assertEqual((version.calepinage_id, version.empreinte_pose),
                         (calepinage.pk, 'a' * 64))  # mutant « sans toit » : (None, '')

    def test_liste_une_erreur_de_base_n_empoisonne_pas_les_leads_suivants(self):
        """Relecture E3 M2 — la liste ouvre un point de sauvegarde par lead :
        une erreur de base sur un lead ne fait pas échouer tous les suivants."""
        from django.db import connection

        from apps.crm.models import Lead
        from apps.ventes.conception import moteur

        company, premier = self._residentiel(facture_hiver=Decimal('1800'))
        _reglages_de_la_societe(company)
        second = Lead.objects.create(company=company, nom='Second', prenom='Lead', ville=premier.ville,
                                     facture_hiver=Decimal('1800'))
        vrai = moteur.calculer_conception

        def calcul(lead, company, **kw):
            if lead.pk == premier.pk:
                with connection.cursor() as curseur:
                    curseur.execute('SELECT * FROM table_qui_n_existe_pas_m2')
            return vrai(lead, company, **kw)
        self._patcher(moteur, 'calculer_conception', side_effect=calcul)
        liste = self._commande('--company', str(company.pk))
        self.assertIn(f'lead #{premier.pk} : calcul impossible', liste)
        self.assertIn(f'lead #{second.pk} [residentiel] option retenue : ', liste)  # mutant « sans point » : rouge
        self.assertIn('LISTE : 1 conception(s) complète(s), 0 refus, 1 erreur(s)', liste)


# ── ADEV145 — PARITÉ : aucun devis envoyé ou accepté ne change ─────────────

class DevisFigesInchangesTests(_emprunt(RelanceConceptionTests, '_relancer'), _emprunt(ServirConceptionTests, '_api'),
                               _emprunt(FigeageDevisAutoTests, 'setUp', '_patcher', '_utilisateur', '_residentiel',
                                        '_ci', '_agricole', '_fiches_residentielles', '_site_isole', '_structures',
                                        '_fiches_ci', '_cas'), TestCase):
    """ADEV145 — un devis ``envoye`` ou ``accepte`` garde ``etude_params``,
    ``electrical_design``, ses lignes et ses totaux octet pour octet quand le
    moteur de son lead écrit une version nouvelle (règle du 08/10/2026,
    D-ACAL-96) ; ``ecart_devis`` nomme la différence sans rien écrire."""

    def test_envoye_et_accepte_inchanges_apres_une_relance_du_moteur(self):
        from django.utils import timezone

        from apps.crm.models import Lead
        from apps.ventes.models import ConceptionLead, Devis
        from apps.ventes.selectors import ecart_devis
        from apps.ventes.services import build_devis_auto

        figes = {}
        company, premier = self._cas('res_conception_electrique')  # fiches complètes : conception électrique rangée
        _reglages_de_la_societe(company)
        user = self._utilisateur(company)
        second = Lead.objects.create(company=company, nom='Second', prenom='Lead', ville=premier.ville,
                                     facture_hiver=Decimal('1800'))
        for statut, lead in (('envoye', premier), ('accepte', second)):
            devis = build_devis_auto(lead=lead, user=user, company=company)
            Devis.objects.filter(pk=devis.pk).update(statut=statut, date_envoi=timezone.now())
            self._relancer(lead, company, _declencheur())
            figes[statut] = (company, lead, devis.pk, _photo_devis(devis.pk))

        for statut, (company, lead, devis_id, photo) in figes.items():
            with self.subTest(statut=statut):
                Lead.objects.filter(pk=lead.pk).update(facture_hiver=Decimal('3600'))
                lead.refresh_from_db()
                relance = self._relancer(lead, company, _declencheur(
                    'lead_entrees_modifiees', facture_hiver=(Decimal('1800'), Decimal('3600'))))
                self.assertEqual((relance.ecrite, relance.conception.version), (True, 2))
                self.assertEqual(_ecarts_figeage(photo, _photo_devis(devis_id))[:12], [])  # mutant « suivre » : rouge
                # Un nouveau devis automatique du même lead (brouillon) et la
                # lecture de la conception ne touchent pas le figé non plus.
                build_devis_auto(lead=lead, user=user, company=company)
                self.assertEqual(self._api(user).get(URL_CONCEPTION % lead.pk).status_code, 200)
                self.assertEqual(_ecarts_figeage(photo, _photo_devis(devis_id))[:12], [])
                ecarts = ecart_devis(Devis.objects.get(pk=devis_id))
                self.assertIn('nb_panneaux', {e['valeur'] for e in ecarts})
                self.assertEqual(_photo_devis(devis_id), photo)
                self.assertEqual(ConceptionLead.objects.filter(lead=lead).count(), 2)


# ── ADEV142 — le devis automatique C&I et agricole né de la conception ──────

#: Les noyaux d'une conception C&I / agricole (module, nom) ; ``etudier_*`` :
#: la DÉCISION (taille, lignes ; l'étude pompage relit la sortie de la
#: décision, ``pompage.etude_precalculee``) ; ``etude_ci_calculee`` : le
#: recalcul du BLOC ``etude_ci`` sur les lignes ; ``recommander_taille`` : le
#: bloc ``dimensionnement``. Les profils comparatifs ne sont pas un bloc hors
#: résidentiel (``calculer_profils_comparatifs`` y rend ``None``, rien rangé).
NOYAUX_DECISION = (('apps.ventes.domain.etude_ci', 'etudier_ci'), ('apps.ventes.domain.pompage', 'etudier_pompage'))
NOYAUX_ETUDES = (('apps.ventes.conception.etudes_lignes', 'etude_ci_calculee'),
                 ('apps.ventes.dimensionnement', 'recommander_taille'))


class DevisDepuisLaConceptionMarchesTests(_emprunt(RelanceConceptionTests, '_relancer'),
                                          _emprunt(FigeageDevisAutoTests, 'setUp', '_patcher', '_utilisateur',
                                                   '_residentiel', '_ci', '_agricole', '_fiches_residentielles',
                                                   '_site_isole', '_structures', '_fiches_ci', '_cas'), TestCase):
    """ADEV142 — C&I et agricole (forme décidée par l'orchestrateur, dite au
    fondateur) : la conception rangée ne porte AUCUNE ligne ; conception à
    jour ⇒ EXACTEMENT UN appel de décision (les lignes, prix du jour) et ZÉRO
    bloc d'étude recalculé (copiés de la version) ; conception absente ⇒ le
    moteur tourne UNE fois dans la requête et le devis relit SA décision."""

    @staticmethod
    def _espions(noyaux):
        import contextlib
        import importlib

        @contextlib.contextmanager
        def bloc():
            with contextlib.ExitStack() as pile:
                yield {nom: pile.enter_context(mock.patch.object(
                    importlib.import_module(module), nom,
                    wraps=getattr(importlib.import_module(module), nom))) for module, nom in noyaux}
        return bloc()

    def _creer(self, company, lead):
        from apps.ventes.services import build_devis_auto
        with self.captureOnCommitCallbacks(execute=True):
            return build_devis_auto(lead=lead, user=self._utilisateur(company), company=company)

    def _cas_du_marche(self, nom):
        company, lead = self._cas(nom)
        _reglages_de_la_societe(company)
        return company, lead

    def test_conception_a_jour_une_decision_zero_bloc_recalcule(self):
        from apps.ventes.models import ConceptionLead

        for nom, decision in (('ci_commercial', 'etudier_ci'), ('agr_pompe_courbe', 'etudier_pompage')):
            with self.subTest(cas=nom):
                company, lead = self._cas_du_marche(nom)
                self._relancer(lead, company, _declencheur())
                with self._espions(NOYAUX_DECISION + NOYAUX_ETUDES) as espions:
                    devis = self._creer(company, lead)
                appels = {k: v.call_count for k, v in espions.items()}
                self.assertEqual(appels.pop(decision), 1, appels)  # la décision : une fois, jamais deux
                self.assertEqual(appels, {k: 0 for k in appels})  # mutant « recalculer l'étude » : rouge
                self.assertEqual(devis.statut, 'brouillon')
                self.assertEqual(ConceptionLead.objects.filter(lead=lead).count(), 1)
                self.assertNotIn('profils_comparatifs', devis.etude_params)

    def test_conception_absente_le_moteur_tourne_une_fois(self):
        from apps.ventes.conception.moteur import calculer_conception
        from apps.ventes.models import ConceptionLead

        for nom in ('ci_commercial', 'agr_pompe_courbe'):
            with self.subTest(cas=nom):
                company, lead = self._cas_du_marche(nom)
                with self._espions(NOYAUX_DECISION + NOYAUX_ETUDES) as espions:
                    calculer_conception(lead, company)
                une_execution = {k: v.call_count for k, v in espions.items()}
                with self._espions(NOYAUX_DECISION + NOYAUX_ETUDES) as espions:
                    devis = self._creer(company, lead)
                appels = {k: v.call_count for k, v in espions.items()}
                self.assertEqual(appels, une_execution)  # mutant « seconde décision au devis » : rouge
                self.assertEqual(devis.statut, 'brouillon')
                self.assertEqual(ConceptionLead.objects.get(lead=lead, courante=True).version, 1)


# ── Relecture E4 B1 — ce que les noyaux lisent hors du lead entre dans l'empreinte ─

_FABRIQUES = ('setUp', '_patcher', '_utilisateur', '_residentiel', '_ci', '_agricole', '_fiches_residentielles',
              '_site_isole', '_structures', '_fiches_ci', '_cas')


class EntreesHorsLeadTests(_emprunt(RelanceConceptionTests, '_relancer'), _emprunt(FigeageDevisAutoTests, *_FABRIQUES),
                           TestCase):
    """Raccordement, catalogue (prix, archivage) et TVA de la société : une
    version rangée avant leur changement est PÉRIMÉE, recalculée paresseusement
    (devis demandé, lecture) avec la raison dite ; rien n'a changé ⇒ rien écrit."""

    def _ancien_chemin(self, company, lead, user):
        """Le devis du chemin d'AVANT la conception (calcul propre au devis)."""
        from apps.ventes.domain.creation_auto import marquer_rapide
        from apps.ventes.domain.creation_auto_residentiel import _build_devis_auto_residentiel
        from apps.ventes.utils.company_settings import tva_standard

        return marquer_rapide(_build_devis_auto_residentiel(
            lead=lead, user=user, company=company, taux_tva=tva_standard(company)))

    def _devis_auto(self, company, lead, user):
        from apps.ventes.services import build_devis_auto
        with self.captureOnCommitCallbacks(execute=True):
            return build_devis_auto(lead=lead, user=user, company=company)

    def test_raccordement_change_le_devis_demande_relance_et_egale_l_ancien_chemin(self):
        from apps.crm.models import Lead
        from apps.ventes.models import ConceptionLead

        company, lead = self._cas('res_facture_dirhams')
        _reglages_de_la_societe(company)
        Lead.objects.filter(pk=lead.pk).update(raccordement='monophase')
        lead.refresh_from_db()
        self._relancer(lead, company, _declencheur())
        Lead.objects.filter(pk=lead.pk).update(raccordement='triphase')
        lead.refresh_from_db()
        user = self._utilisateur(company)
        devis = self._devis_auto(company, lead, user)
        courante = ConceptionLead.objects.get(lead=lead, courante=True)
        self.assertEqual(courante.version, 2)  # mutant « phase hors empreinte » : 1
        self.assertTrue(courante.declencheur['raison'].endswith(' : Raccordement Monophasé → Triphasé'),
                        courante.declencheur)
        ancien = self._ancien_chemin(company, lead, user)
        self.assertEqual(_ecarts_figeage(_photo_du_devis(ancien), _photo_du_devis(devis)), [])

    def test_prix_archivage_et_tva_perimes_et_dits_rien_change_rien_ecrit(self):
        from apps.parametres.models import CompanyProfile
        from apps.stock.models import Produit
        from apps.ventes.conception import receivers
        from apps.ventes.models import ConceptionLead
        from apps.ventes.selectors import conception_courante

        company, lead = self._cas('res_facture_dirhams')
        _reglages_de_la_societe(company)
        self._relancer(lead, company, _declencheur())
        rien = self._relancer(lead, company, _declencheur('filet'))
        self.assertEqual((rien.ecrite, ConceptionLead.objects.filter(lead=lead).count()), (False, 1))
        panneau = Produit.objects.filter(company=company, nom__icontains='panneau').order_by('pk').first()
        autre = Produit.objects.filter(company=company).exclude(pk=panneau.pk).order_by('-pk').first()
        changements = (
            (lambda: Produit.objects.filter(pk=panneau.pk).update(prix_vente=panneau.prix_vente + 100),
             'catalogue modifié'),
            (lambda: Produit.objects.filter(pk=autre.pk).update(is_archived=True), 'catalogue modifié'),
            (lambda: CompanyProfile.objects.filter(company=company).update(tva_standard=Decimal('10')),
             'TVA modifiée (20 → 10 %)'),
        )
        for version, (changer, raison) in enumerate(changements, start=2):
            with self.subTest(raison=raison, version=version):
                changer()
                with mock.patch.object(receivers, 'mettre_en_file') as en_file:
                    self.assertTrue(conception_courante(company, lead.pk)['perimee'])  # filet : paresseux
                self.assertEqual(en_file.call_args.kwargs['origine'], 'filet')
                relance = self._relancer(lead, company, _declencheur('filet'))
                self.assertEqual((relance.ecrite, relance.conception.version), (True, version))
                self.assertTrue(relance.conception.declencheur['raison'].endswith(' : ' + raison),
                                relance.conception.declencheur)
                self.assertEqual(_cles_interdites(relance.conception.entrees_utilisees), [])

    def test_empreinte_du_catalogue_une_fois_par_requete(self):
        from apps.ventes.conception import societe
        from apps.ventes.conception.moteur import reglages_lus_sans_creer
        from core import request_cache

        company, _lead = self._cas('res_facture_dirhams')
        with mock.patch.object(societe, '_empreinte_catalogue', wraps=societe._empreinte_catalogue) as calcul:
            with request_cache.request_scope():  # la requête d'une page de leads
                for _ in range(3):
                    with reglages_lus_sans_creer(company):
                        societe.entrees_de_la_societe(company)
        self.assertEqual(calcul.call_count, 1)


# ── ADEV144 — PARITÉ : le devis né de la conception RANGÉE = les goldens ─────

class PariteDevisDepuisConceptionTests(_emprunt(RelanceConceptionTests, '_relancer'),
                                       _emprunt(EntreesHorsLeadTests, '_ancien_chemin', '_devis_auto'),
                                       _emprunt(FigeageDevisAutoTests, *_FABRIQUES, '_figer'), TestCase):
    """ADEV144 — la conception du lead est RANGÉE d'abord (``relancer``), puis
    le devis automatique est créé : il la LIT (ADEV142, chemin « à jour ») et
    doit écrire EXACTEMENT ce que figent les goldens ``golden/conception/``
    (lignes, totaux, ``etude_params``, conception électrique), trois marchés,
    zéro clé différente. Le chemin « conception absente » est la parité de
    ``FigeageDevisAutoTests`` (mêmes goldens, même comparaison). Un écart
    nomme le cas et la clé ; aucun golden n'est régénéré ici."""

    def _parite_depuis_conception(self, nom):
        from apps.ventes.models import ConceptionLead

        company, lead = self._cas(nom)
        _reglages_de_la_societe(company)
        rangee = self._relancer(lead, company, _declencheur()).conception
        with self.captureOnCommitCallbacks(execute=True):
            self._figer(nom, company, lead, **APPELS_FIGEAGE.get(nom, {}))  # compare au golden, clé par clé
        courante = ConceptionLead.objects.get(lead=lead, courante=True)
        self.assertEqual(courante.pk, rangee.pk)  # lue telle quelle : aucune relance écrite

    def test_version_complete_sans_dimensionnement_le_devis_prend_l_ancien_chemin(self):
        """Relecture E4 m1 — une étude ``dimensionnement`` dite absente ne
        bloque pas le devis (« moteur indisponible ») : le chemin d'aujourd'hui."""
        from apps.ventes.conception import etudes_lignes

        company, lead = self._cas('res_facture_dirhams')
        _reglages_de_la_societe(company)
        with mock.patch.object(etudes_lignes, 'dimensionnement_des_lignes', side_effect=RuntimeError('panne')):
            rangee = self._relancer(lead, company, _declencheur()).conception
        self.assertEqual((rangee.etat, 'dimensionnement' in rangee.blocs), ('complet', False))
        user = self._utilisateur(company)
        nouveau = self._devis_auto(company, lead, user)  # mutant « bloc exigé » : AutoDevisError
        ancien = self._ancien_chemin(company, lead, user)
        self.assertEqual(_ecarts_figeage(_photo_du_devis(ancien), _photo_du_devis(nouveau)), [])

    def test_conception_rangee_depuis_une_pose(self):
        """Relecture E4 m3 — la version née d'une pose est relue avec sa pose."""
        from types import SimpleNamespace

        from apps.ventes.models import ConceptionLead

        company, lead = self._cas('res_facture_dirhams')
        _reglages_de_la_societe(company)
        toit = SimpleNamespace(empreinte='p' * 64, plafond_panneaux=None)
        rangee = self._relancer(lead, company, _declencheur('pose_enregistree'), toit=toit).conception
        self.assertEqual(rangee.empreinte_pose, 'p' * 64)
        with self.captureOnCommitCallbacks(execute=True):
            self._figer('res_facture_dirhams', company, lead)
        self.assertEqual(ConceptionLead.objects.get(lead=lead, courante=True).pk, rangee.pk)

    def test_version_en_refus_le_devis_garde_le_message_d_aujourd_hui(self):
        from apps.ventes.domain.taille import AutoDevisError

        company, lead = self._residentiel()  # aucune consommation : le moteur refuse
        _reglages_de_la_societe(company)
        self.assertEqual(self._relancer(lead, company, _declencheur()).conception.etat, 'refus')
        user = self._utilisateur(company)
        with self.assertRaises(AutoDevisError) as nouveau:
            self._devis_auto(company, lead, user)
        with self.assertRaises(AutoDevisError) as ancien:
            self._ancien_chemin(company, lead, user)
        self.assertEqual((nouveau.exception.message, nouveau.exception.field),
                         (ancien.exception.message, ancien.exception.field))

    def test_entree_changee_avant_le_devis_relance_et_egale_l_ancien_chemin(self):
        """Dérive : la facture change entre la version rangée et le devis ; le
        devis relance dans la requête et vaut le chemin d'avant, rendu compris
        (``build_quote_data``, masque du golden SPL160)."""
        from apps.crm.models import Lead
        from apps.ventes.coherence.contexte import rendu_sans_reseau
        from apps.ventes.quote_engine.builder import build_quote_data
        from apps.ventes.tests import split_golden as sg
        from apps.ventes.tests.test_moteur_golden_build_quote_data import CLES_IDS

        company, lead = self._cas('res_facture_dirhams')
        _reglages_de_la_societe(company)
        self._relancer(lead, company, _declencheur())
        Lead.objects.filter(pk=lead.pk).update(facture_hiver=Decimal('2500'))
        lead.refresh_from_db()
        user = self._utilisateur(company)
        nouveau = self._devis_auto(company, lead, user)
        from apps.ventes.models import ConceptionLead
        self.assertTrue(ConceptionLead.objects.get(lead=lead, courante=True).declencheur['raison'].endswith(
            ' : Facture hiver 1 800 → 2 500 MAD'))
        ancien = self._ancien_chemin(company, lead, user)
        self.assertEqual(_ecarts_figeage(_photo_du_devis(ancien), _photo_du_devis(nouveau)), [])
        rendus = []
        for devis in (ancien, nouveau):
            with rendu_sans_reseau():
                rendus.append(_normaliser_figeage(sg.normaliser(build_quote_data(devis, {}), CLES_IDS)))
        self.assertEqual(_ecarts_figeage(*rendus)[:20], [])


def _test_de_parite_depuis_conception(nom):
    def test(self):
        self._parite_depuis_conception(nom)
    test.__doc__ = f'ADEV144 — devis né de la conception rangée = golden « {nom} ».'
    return test


for _nom in PARITE:
    setattr(PariteDevisDepuisConceptionTests, f'test_parite_depuis_conception_{_nom}',
            _test_de_parite_depuis_conception(_nom))


# ── ADEV147 / ADEV148 — les brouillons suivent la conception (Q2 du 23/11) ───

URL_MISE_A_JOUR = '/api/django/ventes/devis/%d/mettre-a-jour-conception/'


class BrouillonsSuiventLaConceptionTests(_emprunt(RelanceConceptionTests, '_relancer'),
                                         _emprunt(ServirConceptionTests, '_api', '_avec_role'),
                                         _emprunt(FigeageDevisAutoTests, 'setUp', '_patcher', '_utilisateur',
                                                  '_residentiel', '_ci', '_agricole', '_fiches_residentielles',
                                                  '_site_isole', '_structures', '_fiches_ci', '_cas'), TestCase):
    """ADEV147 — un brouillon intact né d'une version plus ancienne suit la
    nouvelle (réaligné, pointeur, ligne d'historique) ; un retouché ne bouge
    pas ; un envoyé ne bouge pas. ADEV148 — le retouché est listé
    (``brouillons_a_mettre_a_jour``, ``mise_a_jour_proposee``) et se réaligne
    SUR DEMANDE (route), quantité tapée gardée et nommée ; envoyé : 409 ;
    hors portée : 404."""

    def setUp(self):
        from django.core.cache import cache

        from apps.ventes import tasks

        FigeageDevisAutoTests.setUp(self)
        cache.clear()
        self.addCleanup(cache.clear)
        patcher = mock.patch.object(tasks.task_suivre_la_conception, 'apply_async')  # jamais le courtier réel
        self.suivi = patcher.start()
        self.addCleanup(patcher.stop)

    def _trois_devis(self):
        from django.utils import timezone

        from apps.ventes.models import Devis
        from apps.ventes.services import build_devis_auto

        company, lead = self._cas('res_facture_dirhams')
        _reglages_de_la_societe(company)
        user = self._utilisateur(company)
        with self.captureOnCommitCallbacks(execute=True):
            intact, retouche, envoye = (build_devis_auto(lead=lead, user=user, company=company) for _ in range(3))
        panneau = retouche.lignes.filter(designation__icontains='panneau').order_by('ordre', 'pk').first()
        type(panneau).objects.filter(pk=panneau.pk).update(quantite=panneau.quantite + 2, quantite_manuelle=True)
        Devis.objects.filter(pk=envoye.pk).update(statut='envoye', date_envoi=timezone.now())
        return company, lead, user, intact, retouche, envoye

    def _nouvelle_version(self, company, lead):
        from apps.crm.models import Lead

        Lead.objects.filter(pk=lead.pk).update(facture_hiver=Decimal('3600'))
        lead.refresh_from_db()
        return self._relancer(lead, company, _declencheur(
            'lead_entrees_modifiees', facture_hiver=(Decimal('1800'), Decimal('3600')))).conception

    def test_e6e_reviser_sur_la_conception_compose_la_v2_sur_la_conception_courante(self):
        """Lane E6e, item 4 (T4-X5-011) — « Réviser le devis » de l'atelier (corps
        ``sur_la_conception``) : la V2 est composée sur la conception COURANTE du lead (la même
        recomposition que le suivi des brouillons, ``brouillons.appliquer_a_la_demande``), le
        devis envoyé reste octet pour octet ; sans le drapeau, la révision clone comme avant."""
        from apps.ventes.conception.brouillons import _comptes
        from apps.ventes.models import Devis

        company, lead, user, _intact, _retouche, envoye = self._trois_devis()

        def _lignes(devis):
            return list(devis.lignes.order_by('ordre', 'pk').values_list(
                'designation', 'quantite', 'prix_unitaire', 'remise', 'variante'))
        avant, comptes_v1 = _lignes(envoye), _comptes(envoye)
        version = self._nouvelle_version(company, lead)
        attendus = {o: v['nb_panneaux']['valeur'] for o, v in version.valeurs.items()}
        self.assertNotEqual(comptes_v1.get('avec', comptes_v1.get('')), attendus.get('avec'))

        reponse = self._api(user).post('/api/django/ventes/devis/%d/reviser/' % envoye.pk,
                                       {'sur_la_conception': True}, format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        v2 = Devis.objects.get(pk=reponse.data['id'])
        self.assertEqual({o: _comptes(v2).get(o, _comptes(v2).get('')) for o in attendus}, attendus)
        self.assertEqual(v2.conception_source['version'], version.version)
        envoye.refresh_from_db()
        self.assertEqual((_lignes(envoye), envoye.statut), (avant, 'envoye'))

    def test_e6e_reviser_sans_drapeau_clone(self):
        from apps.ventes.conception.brouillons import _comptes
        from apps.ventes.models import Devis

        company, lead, user, _intact, _retouche, envoye = self._trois_devis()
        comptes_v1 = _comptes(envoye)
        self._nouvelle_version(company, lead)
        reponse = self._api(user).post('/api/django/ventes/devis/%d/reviser/' % envoye.pk, {}, format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.assertEqual(_comptes(Devis.objects.get(pk=reponse.data['id'])), comptes_v1)

    def test_e6d_duplicata_garde_le_pointeur_suit_ou_est_liste(self):
        """Écart 4 de l'acceptation du 25/11 — un brouillon né de « Dupliquer » garde la version
        de conception de sa source (même contenu, même version) : intact, il SUIT la nouvelle
        version ; retouché, il est listé « à mettre à jour ». Une source sans conception donne un
        duplicata sans pointeur (mutant « pointeur jamais copié » : rouge)."""
        from apps.ventes.conception.brouillons import brouillons_a_mettre_a_jour, suivre_la_conception
        from apps.ventes.domain.creation_clone import dupliquer_devis
        from apps.ventes.models import Devis

        from django.core.cache import cache

        company, lead, user, intact, retouche, envoye = self._trois_devis()
        cache.clear()
        self.suivi.reset_mock()
        with self.captureOnCommitCallbacks(execute=True):
            copie_intacte = dupliquer_devis(intact, user=user)
        self.assertEqual(self.suivi.call_count, 1)  # le suivi du lead la rattrape si sa version est dépassée
        copie_retouchee = dupliquer_devis(retouche, user=user)
        copie_envoyee = dupliquer_devis(envoye, user=user)
        for source, copie in ((intact, copie_intacte), (retouche, copie_retouchee), (envoye, copie_envoyee)):
            self.assertEqual(copie.conception_source, source.conception_source)
            self.assertEqual((copie.statut, copie.lead_id), ('brouillon', lead.pk))
        v2 = self._nouvelle_version(company, lead)
        suivis = suivre_la_conception(v2)
        self.assertIn(copie_intacte.pk, suivis)
        self.assertIn(copie_envoyee.pk, suivis)  # copie intacte d'un envoyé : un brouillon qui suit
        self.assertEqual(Devis.objects.get(pk=copie_intacte.pk).conception_source['version'], 2)
        self.assertIn(copie_retouchee.pk, [b['devis'] for b in brouillons_a_mettre_a_jour(company.pk, lead.pk, 2)])
        Devis.objects.filter(pk=intact.pk).update(conception_source=None)
        intact.refresh_from_db()
        self.assertIsNone(dupliquer_devis(intact, user=user).conception_source)

    def test_intact_suit_retouche_et_envoye_ne_bougent_pas(self):
        from apps.ventes.conception.brouillons import suivre_la_conception
        from apps.ventes.models import Devis, DevisActivity

        company, lead, _user, intact, retouche, envoye = self._trois_devis()
        photos = {d.pk: _photo_devis(d.pk) for d in (retouche, envoye)}
        v2 = self._nouvelle_version(company, lead)
        self.assertEqual(v2.version, 2)
        self.assertEqual(suivre_la_conception(v2), [intact.pk])  # mutant « suivre aussi le retouché » : rouge
        relu = Devis.objects.get(pk=intact.pk)
        self.assertEqual(relu.conception_source['version'], 2)
        self.assertEqual(relu.statut, 'brouillon')
        panneaux = {li.variante or '': int(li.quantite) for li in relu.lignes.all()
                    if 'panneau' in li.designation.lower()}
        attendu = {option: valeurs['nb_panneaux']['valeur'] for option, valeurs in v2.valeurs.items()}
        self.assertEqual({option: panneaux.get(option, panneaux.get('')) for option in attendu}, attendu)
        ligne = DevisActivity.objects.filter(devis=relu, body__startswith='Mis à jour : panneaux ').get()
        self.assertTrue(ligne.body.endswith(' (champ modifié : Facture hiver)'), ligne.body)  # rejeu E5 (c)
        from types import SimpleNamespace

        from apps.ventes.conception.brouillons import _ce_qui_a_change
        deux = SimpleNamespace(lead=lead, declencheur={'champs': [{'champ': 'facture_hiver'}, {'champ': 'ville'}]})
        self.assertEqual(_ce_qui_a_change(deux), 'champs modifiés : Facture hiver, Ville')
        for pk, photo in photos.items():
            self.assertEqual(_photo_devis(pk), photo)
        # Une seconde relance sans changement ne le touche pas.
        self.assertEqual(suivre_la_conception(v2), [])

    def test_chaque_version_rangee_fait_suivre_en_tache(self):
        """Relecture E4 M2 — D1 né de v1 ; la facture change (relance en file) ;
        « Devis auto » range v2 DANS la requête ; la tâche de relance n'écrit
        plus rien : le suivi, mis en file par l'écriture de la requête, fait
        suivre D1 quand même."""
        from apps.ventes import tasks
        from apps.ventes.models import Devis
        from apps.ventes.services import build_devis_auto

        company, lead = self._cas('res_facture_dirhams')
        _reglages_de_la_societe(company)
        user = self._utilisateur(company)
        with mock.patch.object(tasks.task_relancer_conception, 'apply_async') as relance:
            with self.captureOnCommitCallbacks(execute=True):
                d1 = build_devis_auto(lead=lead, user=user, company=company)
            self.assertEqual(tasks.task_suivre_la_conception(**self.suivi.call_args.kwargs['kwargs']), [])
            self.suivi.reset_mock()
            lead.refresh_from_db()
            lead.facture_hiver = Decimal('3600')
            with self.captureOnCommitCallbacks(execute=True):
                lead.save()
            self.assertEqual(relance.call_count, 1)
            with self.captureOnCommitCallbacks(execute=True):
                build_devis_auto(lead=lead, user=user, company=company)
                rendu = tasks.task_relancer_conception(**relance.call_args.kwargs['kwargs'])
        self.assertEqual(rendu, {'version': 2, 'ecrite': False})
        self.assertEqual(self.suivi.call_count, 1)  # mutant « suivi dans la tâche seulement » : 0
        self.assertEqual(tasks.task_suivre_la_conception(**self.suivi.call_args.kwargs['kwargs']), [d1.pk])
        self.assertEqual(Devis.objects.get(pk=d1.pk).conception_source['version'], 2)

    def test_e6b1_m5_meme_contenu_seul_le_pointeur_suit(self):
        """Relecture E6 M5 — une version née sans changement de ce que le devis recevrait
        (relance forcée : seule la version change, comme un saut de ``VERSION_MOTEUR``) :
        le brouillon intact n'est PAS recomposé et ne reçoit aucune ligne d'historique —
        seul son pointeur avance ; l'envoyé n'est jamais écrit. Mutant « recomposer à
        chaque version » : une ligne d'historique, des lignes réécrites."""
        from apps.ventes.conception.brouillons import suivre_la_conception
        from apps.ventes.models import DevisActivity

        company, lead, _user, intact, _retouche, envoye = self._trois_devis()
        avant, photo_envoye = _photo_devis(intact.pk), _photo_devis(envoye.pk)
        v2 = self._relancer(lead, company, _declencheur('manuel'), forcer=True).conception
        self.assertEqual(v2.version, 2)
        self.assertEqual(suivre_la_conception(v2), [intact.pk])
        apres = _photo_devis(intact.pk)
        self.assertEqual(apres['devis'].pop('conception_source')['version'], 2)
        avant['devis'].pop('conception_source')
        self.assertEqual(apres, avant)  # devis et lignes octet pour octet, hors pointeur
        self.assertFalse(DevisActivity.objects.filter(devis_id=intact.pk, body__startswith='Mis à jour').exists())
        self.assertEqual(_photo_devis(envoye.pk), photo_envoye)

    def test_e6b1_m5_onduleur_designe_le_brouillon_recompose_le_porte(self):
        """Relecture E6 M5 — une conception née d'un onduleur DÉSIGNÉ à la main : le
        brouillon intact recomposé porte CET onduleur (l'imposition de la version passe à la
        recomposition ; mutant « imposition=None » : l'onduleur du moteur)."""
        from apps.calepinage.models import Calepinage
        from apps.calepinage.services.electrique import CLE_ENTREE
        from apps.stock.models import Produit
        from apps.ventes.conception.brouillons import suivre_la_conception
        from apps.ventes.models import Devis

        company, lead, _user, intact, _retouche, envoye = self._trois_devis()
        photo_envoye = _photo_devis(envoye.pk)
        # Un onduleur plus grand au catalogue : le compositeur le prendrait pour cette taille ;
        # l'onduleur DÉSIGNÉ (5 kW, ratio dans la fenêtre) doit rester.
        Produit.objects.create(company=company, nom='Onduleur réseau Growatt 8kW Monophasé', sku='E6M5-OND',
                               prix_vente=Decimal('15500'), prix_achat=Decimal('1'), quantite_stock=10)
        designe = Produit.objects.get(company=company, nom='Onduleur réseau Huawei 5kW Monophasé')
        calepinage = Calepinage.objects.create(company=company, lead_id=lead.pk, titre='Toit',
                                               resultat={CLE_ENTREE: {'onduleur_produit': designe.pk}})
        v2 = self._relancer(lead, company, _declencheur('pose_enregistree'), calepinage_id=calepinage.pk).conception
        self.assertEqual(v2.valeurs[v2.option_retenue]['onduleur_produit']['source'], 'impose', v2.suppositions)
        self.assertEqual(suivre_la_conception(v2), [intact.pk])
        relu = Devis.objects.get(pk=intact.pk)
        onduleurs = [li.produit_id for li in relu.lignes.all() if 'nduleur' in li.designation]
        self.assertEqual(set(onduleurs), {designe.pk}, [li.designation for li in relu.lignes.all()])
        self.assertEqual(_photo_devis(envoye.pk), photo_envoye)

    def test_envoye_entre_selection_et_ecriture_rien_ne_bouge(self):
        """Relecture E4 M1 — le devis passe « envoyé » entre la sélection et
        l'écriture : relu sous verrou, devis et lignes octet pour octet ; la
        route répond 409."""
        from apps.ventes.conception import brouillons
        from apps.ventes.models import Devis

        company, lead, user, intact, _retouche, _envoye = self._trois_devis()
        v2 = self._nouvelle_version(company, lead)
        selection = list(brouillons._brouillons_nes_avant(company.pk, lead.pk, v2.version))
        Devis.objects.filter(pk=intact.pk).update(statut='envoye')
        photo = _photo_devis(intact.pk)
        with mock.patch.object(brouillons, '_brouillons_nes_avant', return_value=selection):
            self.assertEqual(brouillons.suivre_la_conception(v2), [])  # mutant « sans relecture » : [intact]
        with self.assertRaises(brouillons.MiseAJourRefusee):
            brouillons.appliquer_a_la_demande(next(d for d in selection if d.pk == intact.pk), user)
        self.assertEqual(_photo_devis(intact.pk), photo)

    def test_brouillon_a_ligne_ajoutee_propose_jamais_recompose(self):
        """Relecture E4 m2 — une ligne ajoutée à la main (« Transport ») que la
        recomposition effacerait : le brouillon ne suit pas seul, il est PROPOSÉ."""
        from apps.ventes.conception.brouillons import suivre_la_conception
        from apps.ventes.models import LigneDevis
        from apps.ventes.selectors import conception_courante

        company, lead, _user, intact, _retouche, _envoye = self._trois_devis()
        modele = intact.lignes.order_by('pk').first()
        LigneDevis.objects.create(devis=intact, produit=modele.produit, designation='Transport ajouté',
                                  quantite=Decimal('1'), prix_unitaire=Decimal('500'), taux_tva=modele.taux_tva,
                                  ligne_composee=False, ordre=99)
        photo = _photo_devis(intact.pk)
        v2 = self._nouvelle_version(company, lead)
        self.assertEqual(suivre_la_conception(v2), [])  # mutant « recomposer » : la ligne disparaît
        self.assertEqual(_photo_devis(intact.pk), photo)
        proposes = conception_courante(company, lead.pk)['brouillons_a_mettre_a_jour']
        self.assertIn(intact.pk, [b['devis'] for b in proposes])

    def test_ci_et_agricole_recomposes_par_la_decision(self):
        """Relecture E4 M3 — un brouillon C&I ou agricole intact suit avec les
        lignes, études et totaux du devis automatique né de la nouvelle version ;
        un brouillon C&I retouché, mis à jour sur demande, garde sa taille et
        son pointeur (la mise à jour reste proposée)."""
        from apps.crm.models import Lead
        from apps.stock.models import Produit
        from apps.ventes.conception.brouillons import appliquer_a_la_demande, suivre_la_conception
        from apps.ventes.models import Devis
        from apps.ventes.services import build_devis_auto

        changer = {'ci_commercial': lambda co, ld: Lead.objects.filter(pk=ld.pk).update(
                       conso_mensuelle_kwh=Decimal('12000')),
                   'agr_pompe_courbe': lambda co, ld: Produit.objects.filter(
                       company=co, nom__startswith='Pompe').update(prix_vente=Decimal('17000'))}
        for nom, changement in changer.items():
            with self.subTest(cas=nom):
                company, lead = self._cas(nom)
                _reglages_de_la_societe(company)
                user = self._utilisateur(company)
                with self.captureOnCommitCallbacks(execute=True):
                    brouillon, retouche = (build_devis_auto(lead=lead, user=user, company=company) for _ in range(2))
                changement(company, lead)
                lead.refresh_from_db()
                v2 = self._relancer(lead, company, _declencheur('filet')).conception
                panneau = retouche.lignes.filter(designation__icontains='panneau').order_by('pk').first()
                type(panneau).objects.filter(pk=panneau.pk).update(quantite_manuelle=True)
                self.assertEqual(suivre_la_conception(v2), [brouillon.pk])
                frais = _photo_du_devis(build_devis_auto(lead=lead, user=user, company=company))
                suivi = _photo_du_devis(Devis.objects.get(pk=brouillon.pk))
                self.assertEqual(_ecarts_figeage(frais['lignes'], suivi['lignes'])  # mutant « pointeur seul » : rouge
                                 + _ecarts_figeage(frais['etude_params'], suivi['etude_params']), [])
                if nom == 'ci_commercial':
                    rendu = appliquer_a_la_demande(Devis.objects.get(pk=retouche.pk), user)
                    self.assertEqual(rendu['appliquees'], [])
                    self.assertIn('taille', [n['champ'] for n in rendu['non_appliquees']])
                    self.assertEqual(Devis.objects.get(pk=retouche.pk).conception_source['version'], 1)

    def test_retouche_liste_puis_mis_a_jour_sur_demande(self):
        from authentication.models import Company

        from apps.ventes.models import Devis
        from apps.ventes.selectors import conception_courante, ecart_devis

        company, lead, user, _intact, retouche, envoye = self._trois_devis()
        self._nouvelle_version(company, lead)
        lue = conception_courante(company, lead.pk)
        self.assertEqual(lue['brouillons_a_mettre_a_jour'],
                         [{'devis': retouche.pk, 'reference': retouche.reference, 'motif': 'retouché à la main'}])
        ecarts = ecart_devis(Devis.objects.get(pk=retouche.pk))
        self.assertTrue(ecarts and all(e['mise_a_jour_proposee'] for e in ecarts), ecarts)
        photo = _photo_devis(retouche.pk)
        self.assertEqual(_photo_devis(retouche.pk), photo)  # la lecture n'écrit rien

        api = self._api(user)
        self.assertEqual(api.post(URL_MISE_A_JOUR % envoye.pk).status_code, 409)
        autre = Company.objects.create(nom='Autre ADEV148', slug='autre-adev148')
        self.assertEqual(self._api(self._utilisateur(autre)).post(URL_MISE_A_JOUR % retouche.pk).status_code, 404)
        reponse = api.post(URL_MISE_A_JOUR % retouche.pk)
        self.assertEqual(reponse.status_code, 200, reponse.content)
        corps = reponse.json()
        self.assertEqual((corps['devis_id'], corps['appliquees']), (retouche.pk, ['conception_v2']))
        self.assertTrue(any(n['champ'] == 'quantite' for n in corps['non_appliquees']), corps)
        relu = Devis.objects.get(pk=retouche.pk)
        self.assertEqual(relu.conception_source['version'], 2)
        manuelle = relu.lignes.get(quantite_manuelle=True)  # mutant « écraser la quantité tapée » : rouge
        self.assertEqual(manuelle.quantite, Decimal(photo['lignes'][[li['quantite_manuelle'] for li in
                                                                     photo['lignes']].index(True)]['quantite']))
        self.assertEqual(api.post(URL_MISE_A_JOUR % retouche.pk).json()['appliquees'], [])  # rien de plus
        self.assertEqual(conception_courante(company, lead.pk)['brouillons_a_mettre_a_jour'], [])

    def test_agen12_raisons_disent_la_conception_du_lead(self):
        """AGEN12 (constat en direct) — « Mettre à jour » réutilise le chemin
        réconcilier, qui parle du CALEPINAGE (« La conception 3D porte… »,
        « Écart de calepinage non entièrement appliqué… ») quand seule la fiche du
        lead a changé : le vendeur lit désormais ce qui a vraiment changé (la
        conception du lead et son champ) ; le chemin réconcilier, lui, est intact."""
        from apps.ventes.domain import pipeline

        company, lead, user, _intact, retouche, _envoye = self._trois_devis()
        self._nouvelle_version(company, lead)
        dit_par_le_calepinage = ['La conception 3D porte le devis de 5 à 7 panneaux.',
                                 'Écart de calepinage non entièrement appliqué : le devis reste « à resynchroniser » '
                                 '— corrigez la cause ci-dessus puis resynchronisez.', 'Autre avertissement.']
        with mock.patch.object(pipeline, 'reappliquer_lead', return_value={'avertissements': dit_par_le_calepinage}):
            corps = self._api(user).post(URL_MISE_A_JOUR % retouche.pk).json()
        raisons = [n['raison'] for n in corps['non_appliquees'] if n['champ'] == 'composition']
        self.assertEqual(raisons, [
            'La conception du lead porte le devis de 5 à 7 panneaux (champ modifié : Facture hiver).',
            "La conception du lead n'a pas pu être entièrement appliquée (champ modifié : Facture hiver) : "
            'corrigez la cause ci-dessus puis cliquez de nouveau « Mettre à jour ».',
            'Autre avertissement.'])
        self.assertFalse([r for r in raisons if 'calepinage' in r or '3D' in r])

    def test_mise_a_jour_meme_garde_que_reprendre_le_lead(self):
        """Relecture E4 M4 — aucun rôle élargi : la garde de « Reprendre les
        valeurs du lead » (rôles RÉELS du registre), 403 en français ; hors
        portée (Commercial non propriétaire) : 404."""
        from apps.crm.models import Lead
        from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES

        company, lead, _user, _intact, retouche, _envoye = self._trois_devis()
        self._nouvelle_version(company, lead)
        grille = dict(CANONICAL_SYSTEM_ROLES)
        roles = ('Viewer', 'Commercial', 'Commercial responsable', 'Administrateur')
        comptes = {nom: self._avec_role(company, nom, grille[nom]) for nom in roles}
        Lead.objects.filter(pk=lead.pk).update(owner=comptes['Commercial'])
        statuts = {}
        for nom in roles:
            api = self._api(comptes[nom])
            reprendre = api.post('/api/django/ventes/devis/%d/reappliquer-lead/' % retouche.pk)
            reponse = api.post(URL_MISE_A_JOUR % retouche.pk)
            statuts[nom] = (reprendre.status_code == 403, reponse.status_code)
            if reponse.status_code == 403:
                self.assertTrue(reponse.json()['detail'].startswith('Votre rôle ne permet pas'), reponse.json())
        self.assertEqual(statuts, {'Viewer': (True, 403), 'Commercial': (False, 200),  # mutant « crm_voir seul » : 200
                                   'Commercial responsable': (False, 200), 'Administrateur': (False, 200)})
        collegue = self._api(self._avec_role(company, 'collegue', grille['Commercial']))
        self.assertEqual(collegue.post(URL_MISE_A_JOUR % retouche.pk).status_code, 404)


# ── ADEV149 / ADEV150 — la pose du toit tracé, PAR le moteur, au niveau 15 seulement ─

class PoseReelleTests(_emprunt(RelanceConceptionTests, '_relancer'), _emprunt(FigeageDevisAutoTests, *_FABRIQUES),
                      _emprunt(ServirConceptionTests, '_api'), TestCase):
    """ADEV149 — toit tracé et pose complète, au niveau de règles 15 : la production
    rangée est celle de LA simulation de la pose (façade ACAL2018), source « pose » ;
    sans toit, ou au niveau 14 courant : le chemin d'aujourd'hui, la façade jamais
    appelée. ADEV150 — une pose ajustée à la main impose son compte (source « pose »)."""

    PRODUCTION = [round(500.0 + 10 * m, 1) for m in range(12)]
    #: Relecture E6 M1 — le productible SERVI de la pose (kWh/kWc, pertes incluses), très
    #: au-dessus de la ville : toute valeur calculée sur lui s'en écarte.
    KWH_KWC = [150.0, 160.0, 190.0, 210.0, 230.0, 240.0, 250.0, 240.0, 210.0, 180.0, 150.0, 140.0]

    def _servi(self):
        return {'perime': False, 'motif': '', 'source': 'calepinage_enregistre', 'kwc_simule': None,
                'kwh_kwc_annuel': sum(self.KWH_KWC), 'kwh_kwc_mensuel': list(self.KWH_KWC), 'complete': True,
                'pertes_et_ombrage_inclus': True}

    def _pose(self, nb, *, complete=True, a_la_main=False, module=None):
        return {'nb_panneaux': nb, 'kwc': None, 'complete': complete, 'a_la_main': a_la_main,
                'empreinte_pose': 'f' * 64, 'manquants': [], 'module_produit': module}

    def _calculer(self, company, lead, *, niveau=None, pose=None, calepinage_id=77):
        from apps.ventes.conception import porte_calepinage as P
        from apps.ventes.conception.moteur import calculer_conception
        from apps.ventes.domain import regles_calcul as RC

        _reglages_de_la_societe(company)
        with mock.patch.object(RC, 'REGLES_COURANTES', niveau or RC.REGLES_COURANTES), \
                mock.patch.object(P, 'pose_du_calepinage', return_value=pose) as lue, \
                mock.patch.object(P, 'productible_de_la_pose', return_value=self._servi()) as simulee:
            resultat = calculer_conception(lead, company, calepinage_id=calepinage_id)
        return resultat, lue, simulee

    def test_niveau_14_la_facade_n_est_jamais_appelee_parite_intacte(self):
        company, lead = self._cas('res_facture_dirhams')
        resultat, lue, simulee = self._calculer(company, lead, pose=self._pose(12))
        lue.assert_not_called()  # mutant « appeler la simulation au niveau 14 » : rouge
        simulee.assert_not_called()
        temoin, _l, _s = self._calculer(company, lead, calepinage_id=None)
        self.assertEqual(_json(resultat.valeurs), _json(temoin.valeurs))
        self.assertEqual(resultat.valeurs['sans']['production_annuelle']['source'], 'moteur')

    def test_niveau_15_pose_complete_production_de_la_simulation(self):
        """Relecture E6 M1 — au niveau 15, la production de LA pose est la BASE des études :
        production, économies, autoconsommation et le bloc horaire copié au devis viennent
        TOUS d'elle (une seule production de bout en bout). Mutant « remplacer les deux clés
        de production seulement » : économies et bloc restent ceux de la ville — rouge."""
        from apps.ventes.domain.regles_calcul import REGLES_POSE_REELLE_2111

        company, lead = self._cas('res_batterie_sans')
        temoin, _l, _s = self._calculer(company, lead, niveau=REGLES_POSE_REELLE_2111, calepinage_id=None)
        resultat, lue, simulee = self._calculer(company, lead, niveau=REGLES_POSE_REELLE_2111,
                                                pose=self._pose(12))
        lue.assert_called_once_with(company, 77)
        self.assertEqual(simulee.call_args.args[:2], (company, 77))
        self.assertEqual(set(simulee.call_args.args[2]), {'module', 'onduleur'})
        self.assertEqual(resultat.etat, 'complet', resultat.refus)
        option = resultat.option_retenue
        retenue, avant = resultat.valeurs[option], temoin.valeurs[option]
        annuel = resultat.blocs['etude_horaire']['annuel']
        self.assertEqual(resultat.blocs['etude_horaire']['base_production']['source'], 'calepinage_enregistre')
        self.assertEqual(retenue['production_annuelle']['valeur'], annuel['production_kwh'])
        self.assertEqual(retenue['production_annuelle']['source'], 'pose')
        self.assertEqual(retenue['economies_annuelles']['valeur'], annuel['economie_%s_mad' % option])
        for cle in ('production_annuelle', 'economies_annuelles', 'autoconsommation'):
            self.assertNotEqual(retenue[cle]['valeur'], avant[cle]['valeur'], cle)
        self.assertNotEqual(resultat.blocs['etude_horaire']['annuel'], temoin.blocs['etude_horaire']['annuel'])
        self.assertEqual(resultat.niveau_regles, REGLES_POSE_REELLE_2111)
        # Un lead SANS toit tracé, même au niveau 15 : chemin par marché.
        lue_sans = self._calculer(company, lead, niveau=REGLES_POSE_REELLE_2111, pose=self._pose(12),
                                  calepinage_id=None)[1]
        lue_sans.assert_not_called()
        self.assertEqual(avant['production_annuelle']['source'], 'moteur')

    def test_niveau_15_jamais_de_simulation_dans_une_requete(self):
        """Relecture E6 — au niveau 15, une pose jamais simulée : la tâche du moteur la simule ;
        le devis automatique (requête web) ne la simule JAMAIS — il la met en file et répond
        409 « La simulation de la pose est en cours : réessayez dans une minute. », rien rangé."""
        from apps.calepinage.models import Calepinage
        from apps.crm.models import Lead
        from apps.ventes.conception import porte_calepinage as P
        from apps.ventes.domain import regles_calcul as RC
        from apps.ventes.models import ConceptionLead, Devis

        company, lead = self._cas('res_batterie_sans')
        _reglages_de_la_societe(company)
        user = self._utilisateur(company)
        calepinage = Calepinage.objects.create(company=company, lead_id=lead.pk, titre='Toit')
        with mock.patch.object(RC, 'REGLES_COURANTES', RC.REGLES_POSE_REELLE_2111), \
                mock.patch.object(P, 'pose_du_calepinage', return_value=self._pose(12)), \
                mock.patch('apps.calepinage.selectors_devis.productible_pose_du_calepinage',
                           return_value=None), \
                mock.patch.object(P, 'simuler_la_pose') as simulee, \
                mock.patch('apps.calepinage.services.simulation_auto.lancer_simulation_automatique') as en_file:
            with P.contexte_de_pose(simuler=True):  # la tâche du moteur : elle simule
                self._relancer(lead, company, _declencheur('pose_enregistree'), calepinage_id=calepinage.pk)
            self.assertEqual(simulee.call_count, 1)
            simulee.reset_mock()
            Lead.objects.filter(pk=lead.pk).update(facture_hiver=Decimal('3000'))
            versions = ConceptionLead.objects.filter(lead=lead).count()
            reponse = self._api(user).post('/api/django/ventes/devis/auto/', {'lead': lead.pk}, format='json')
        self.assertEqual(reponse.status_code, 409, reponse.content[:400])
        self.assertEqual(reponse.json()['detail'], 'La simulation de la pose est en cours : réessayez dans une minute.')
        simulee.assert_not_called()  # mutant « simuler dans la requête » : rouge
        self.assertEqual(en_file.call_count, 1)
        self.assertEqual(en_file.call_args.kwargs['user'], user)
        self.assertEqual(ConceptionLead.objects.filter(lead=lead).count(), versions)
        self.assertFalse(Devis.objects.filter(lead=lead).exists())

    def test_niveau_15_pose_incomplete_aucune_simulation(self):
        from apps.ventes.domain.regles_calcul import REGLES_POSE_REELLE_2111

        company, lead = self._cas('res_facture_dirhams')
        resultat, _lue, simulee = self._calculer(company, lead, niveau=REGLES_POSE_REELLE_2111,
                                                 pose=self._pose(12, complete=False))
        simulee.assert_not_called()
        self.assertEqual(resultat.valeurs[resultat.option_retenue]['production_annuelle']['source'], 'moteur')

    def test_adev150_pose_a_la_main_souveraine_puis_retiree(self):
        from apps.ventes.domain.regles_calcul import REGLES_POSE_REELLE_2111

        company, lead = self._cas('res_facture_dirhams')
        temoin, _l, _s = self._calculer(company, lead, niveau=REGLES_POSE_REELLE_2111, calepinage_id=None)
        recommande = temoin.valeurs[temoin.option_retenue]['nb_panneaux']['valeur']
        posee = recommande + 3
        resultat, _lue, _simulee = self._calculer(company, lead, niveau=REGLES_POSE_REELLE_2111,
                                                  pose=self._pose(posee, complete=False, a_la_main=True,
                                                                  module=temoin.valeurs[temoin.option_retenue][
                                                                      'module_produit']['valeur']))
        self.assertEqual(resultat.etat, 'complet', resultat.refus)
        retenue = resultat.valeurs[resultat.option_retenue]
        # Relecture E6 m2 — une pose AJUSTÉE À LA MAIN est imposée par un humain : ``impose``.
        self.assertEqual((retenue['nb_panneaux']['valeur'], retenue['nb_panneaux']['source']), (posee, 'impose'))
        self.assertEqual(retenue['puissance_kwc']['source'], 'impose')
        self.assertEqual(resultat.entrees_utilisees['pose'], {'valeur': posee, 'source': 'calepinage'})
        self.assertNotEqual(retenue['production_annuelle']['valeur'],
                            temoin.valeurs[temoin.option_retenue]['production_annuelle']['valeur'])
        # Pose non ajustée (remplie par le plan) : la facture garde la main.
        suivie, _l, _s = self._calculer(company, lead, niveau=REGLES_POSE_REELLE_2111,
                                        pose=self._pose(posee, complete=False))
        self.assertEqual(suivie.valeurs[suivie.option_retenue]['nb_panneaux']['valeur'], recommande)

    def test_acal2020_releve_colle_entree_imposee_du_moteur_niveau_15(self):
        """Reste d'ACAL2020 — au niveau 15, le relevé collé au calepinage (source ``csv``) est une
        entrée IMPOSÉE : la conception est recalculée avec lui, le dit (entrée de source
        ``calepinage`` + supposition), la lecture la dit À JOUR (mutant « filet sans le relevé » :
        périmée pour toujours), le lead n'est jamais écrit ; retirer le relevé rend la
        consommation du lead. Au niveau 14 : rien ne bouge."""
        from apps.calepinage.models import Calepinage
        from apps.crm.models import Lead
        from apps.ventes.conception import porte_calepinage as P
        from apps.ventes.conception.moteur import calculer_conception
        from apps.ventes.domain import regles_calcul as RC
        from apps.ventes.models import ConceptionLead
        from apps.ventes.selectors import conception_courante

        company, lead = self._cas('res_facture_dirhams')
        _reglages_de_la_societe(company)
        releve = {'courbe24': [1.5] * 24, 'methode': 'courbe', 'appareils': [],  # 36 kWh/j ⇒ 1 095 kWh/mois
                  'source': {'origine': 'csv', 'saisi_le': '2026-11-20T10:00:00Z', 'bareme': 'societe'}}
        calepinage = Calepinage.objects.create(company=company, lead_id=lead.pk, titre='Toit',
                                               roof_layout={'version': 2, 'consumption': releve})
        fiche = _json(Lead.objects.filter(pk=lead.pk).values()[0])

        def conso(version):
            return version.valeurs[version.option_retenue]['consommation_annuelle']['valeur']
        with mock.patch.object(RC, 'REGLES_COURANTES', RC.REGLES_POSE_REELLE_2111), \
                mock.patch.object(P, 'pose_du_calepinage', return_value=None):
            temoin = calculer_conception(lead, company)
            relance = self._relancer(lead, company, _declencheur('pose_enregistree'), calepinage_id=calepinage.pk)
            rangee = ConceptionLead.objects.get(pk=relance.conception.pk)
            self.assertEqual(rangee.etat, 'complet', rangee.refus)
            self.assertEqual(rangee.entrees_utilisees['conso_mensuelle_kwh'],
                             {'valeur': 1095.0, 'source': 'calepinage'})
            dites = [s for s in rangee.suppositions if s['code'] == 'consommation_du_releve']
            self.assertEqual([(s['champ'], s['valeur'], s['source']) for s in dites],
                             [('conso_mensuelle_kwh', 1095.0, 'calepinage')])
            self.assertIn('relevé collé au calepinage (1 095 kWh par mois)', dites[0]['message'])
            self.assertNotEqual(conso(rangee), temoin.valeurs[temoin.option_retenue]['consommation_annuelle']['valeur'])
            self.assertFalse(conception_courante(company, lead.pk)['perimee'])  # le filet relit le relevé
            self.assertFalse(self._relancer(lead, company, _declencheur('pose_enregistree'),
                                            calepinage_id=calepinage.pk).ecrite)  # même empreinte : rien
            self.assertEqual(_json(Lead.objects.filter(pk=lead.pk).values()[0]), fiche)  # jamais écrit sur le lead
            # Retirer le relevé : la consommation du lead revient, sans supposition, à jour.
            Calepinage.objects.filter(pk=calepinage.pk).update(roof_layout={'version': 2})
            retour = self._relancer(lead, company, _declencheur('pose_enregistree'), calepinage_id=calepinage.pk)
            self.assertTrue(retour.ecrite)
            revenue = ConceptionLead.objects.get(pk=retour.conception.pk)
            self.assertEqual(conso(revenue), temoin.valeurs[temoin.option_retenue]['consommation_annuelle']['valeur'])
            self.assertFalse([s for s in revenue.suppositions if s['code'] == 'consommation_du_releve'])
            self.assertFalse(conception_courante(company, lead.pk)['perimee'])
        # Niveau 14 courant : le relevé n'entre pas, la conception est celle du lead, au bit près.
        Calepinage.objects.filter(pk=calepinage.pk).update(roof_layout={'version': 2, 'consumption': releve})
        with mock.patch.object(P, 'pose_du_calepinage', return_value=None):
            avec = calculer_conception(lead, company, calepinage_id=calepinage.pk)
            sans = calculer_conception(lead, company)
        self.assertEqual((_json(avec.valeurs), avec.empreinte, avec.suppositions),
                         (_json(sans.valeurs), sans.empreinte, sans.suppositions))

    def test_relance_passe_le_calepinage_au_moteur_devis_envoye_intact(self):
        from apps.ventes.conception import moteur as M
        from apps.ventes.models import Devis
        from apps.ventes.services import build_devis_auto

        company, lead = self._cas('res_facture_dirhams')
        _reglages_de_la_societe(company)
        devis = build_devis_auto(lead=lead, user=self._utilisateur(company), company=company)
        Devis.objects.filter(pk=devis.pk).update(statut='envoye')
        avant = _json(Devis.objects.filter(pk=devis.pk).values()[0])
        with mock.patch.object(M, 'pose_reelle', return_value=None) as lue:
            self._relancer(lead, company, _declencheur(), forcer=True)
        self.assertEqual(lue.call_args.args[1:], (None, 'residentiel'))
        self.assertEqual(_json(Devis.objects.filter(pk=devis.pk).values()[0]), avant)
