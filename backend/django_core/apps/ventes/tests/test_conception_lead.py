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
}
CLES_VALEUR = {'valeur', 'unite', 'source'}
SOURCES_VALEUR = {'moteur', 'pose', 'impose', 'devis', 'defaut'}
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
    'forme_horaire', 'module_produit', 'onduleur_produit', 'batterie_produit', 'verdicts',
}
#: La table §2 en agricole (la pompe remplace taille / matériel / bilan).
VALEURS_POMPAGE = {'nb_panneaux', 'puissance_kwc', 'pompe', 'variateur', 'm3_jour'}
CLES_CORPS_APERCU = {'lead', 'calepinage', 'entrees', 'imposes'}
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
                        self.assertEqual(set(valeur), CLES_VALEUR, cle)
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

    def test_verdicts_ranges_pour_l_option_de_la_conception_electrique(self):
        # ACAL2016 — l'option dont la conception électrique porte l'onduleur porte ses verdicts rangés.
        resultat = self._parite('res_conception_electrique')
        portees = [o for o, v in resultat.valeurs.items() if v['chaines']['valeur']]
        self.assertTrue(portees)
        for option, valeurs in resultat.valeurs.items():
            verdicts = valeurs['verdicts']['valeur']
            if option not in portees:
                self.assertIsNone(verdicts)
                continue
            self.assertEqual(set(verdicts), {'ratio_dc_ac', 'capacite_hybride', 'longueur_chaine'})
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
        self.assertEqual((absente.status_code, absente.json()['code']), (404, 'conception_absente'))

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
        self.assertTrue(ligne.body.endswith(' (Facture hiver modifié(s))'), ligne.body)
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
                      TestCase):
    """ADEV149 — toit tracé et pose complète, au niveau de règles 15 : la production
    rangée est celle de LA simulation de la pose (façade ACAL2018), source « pose » ;
    sans toit, ou au niveau 14 courant : le chemin d'aujourd'hui, la façade jamais
    appelée. ADEV150 — une pose ajustée à la main impose son compte (source « pose »)."""

    PRODUCTION = [round(500.0 + 10 * m, 1) for m in range(12)]

    def _pose(self, nb, *, complete=True, a_la_main=False, module=None):
        return {'nb_panneaux': nb, 'kwc': None, 'complete': complete, 'a_la_main': a_la_main,
                'empreinte_pose': 'f' * 64, 'manquants': [], 'module_produit': module}

    def _calculer(self, company, lead, *, niveau=None, pose=None, calepinage_id=77):
        from apps.ventes.conception import porte_calepinage as P
        from apps.ventes.conception.moteur import calculer_conception
        from apps.ventes.domain import regles_calcul as RC

        _reglages_de_la_societe(company)
        sortie = {'complete': True, 'production_annuelle': sum(self.PRODUCTION),
                  'production_mensuelle': self.PRODUCTION, 'hash_entree': 'h' * 64}
        with mock.patch.object(RC, 'REGLES_COURANTES', niveau or RC.REGLES_COURANTES), \
                mock.patch.object(P, 'pose_du_calepinage', return_value=pose) as lue, \
                mock.patch.object(P, 'simuler_la_pose', return_value=sortie) as simulee:
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
        from apps.ventes.domain.regles_calcul import REGLES_POSE_REELLE_2111

        company, lead = self._cas('res_facture_dirhams')
        resultat, lue, simulee = self._calculer(company, lead, niveau=REGLES_POSE_REELLE_2111,
                                                pose=self._pose(12))
        lue.assert_called_once_with(company, 77)
        retenue = resultat.valeurs[resultat.option_retenue]
        simulee.assert_called_once_with(company, 77, {'module': retenue['module_produit']['valeur'],
                                                      'onduleur': retenue['onduleur_produit']['valeur']})
        self.assertEqual(retenue['production_annuelle'],
                         {'valeur': sum(self.PRODUCTION), 'unite': 'kWh/an', 'source': 'pose'})
        self.assertEqual(retenue['production_mensuelle']['valeur'], self.PRODUCTION)
        self.assertEqual(resultat.niveau_regles, REGLES_POSE_REELLE_2111)
        # Un lead SANS toit tracé, même au niveau 15 : chemin par marché.
        sans_toit, lue, simulee = self._calculer(company, lead, niveau=REGLES_POSE_REELLE_2111,
                                                 pose=self._pose(12), calepinage_id=None)
        lue.assert_not_called()
        self.assertEqual(sans_toit.valeurs[sans_toit.option_retenue]['production_annuelle']['source'], 'moteur')

    def test_niveau_15_pose_incomplete_aucune_simulation(self):
        from apps.ventes.domain.regles_calcul import REGLES_POSE_REELLE_2111

        company, lead = self._cas('res_facture_dirhams')
        resultat, _lue, simulee = self._calculer(company, lead, niveau=REGLES_POSE_REELLE_2111,
                                                 pose=self._pose(12, complete=False))
        simulee.assert_not_called()
        self.assertEqual(resultat.valeurs[resultat.option_retenue]['production_annuelle']['source'], 'moteur')

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
