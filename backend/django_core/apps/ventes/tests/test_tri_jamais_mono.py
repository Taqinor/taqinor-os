# -*- coding: utf-8 -*-
"""L-TRI — VERROU PERMANENT : « pourquoi j'ai du mono alors que le client est
tri, c'est une erreur qui doit être résolue et cette erreur ne doit pas se
répéter » (ordre fondateur, 24/08/2026).

CE QUI S'ÉTAIT PASSÉ. La préférence triphasée n'était qu'un DÉPARTAGE À
PUISSANCE ÉGALE : ``choisir_onduleur`` (services.py) retenait « le plus petit
modèle ≥ 80 % du kWc », puis, PARMI LES MODÈLES DE CETTE PUISSANCE-LÀ
seulement, préférait le triphasé. Comme le premier palier triphasé du
catalogue est le 10 kW, tout candidat plus petit (1 à 8 panneaux d'un client
à 3 500 DH/mois, pourtant TRIPHASÉ) sortait avec un « Onduleur réseau Huawei
5kW Monophasé » : aucun triphasé n'existait à 5 kW, donc le monophasé gagnait
sans jamais être comparé au 10 kW triphasé.

LA RÈGLE MAINTENANT TENUE (``_vivier_onduleurs_par_phase``) : un raccordement
TRIPHASÉ déclaré donne un vivier TRIPHASÉ EXCLUSIVEMENT — le monophasé est
EXCLU, pas déprioritisé. Le ratio des 80 % redevient ce qu'il est, un
PLANCHER : un petit kWc prend le plus petit triphasé du catalogue, même très
surdimensionné (le client triphasé prend le 10 kW triphasé). Et un catalogue
SANS triphasé ne compose AUCUN onduleur : la composition est REFUSÉE et le
DIT (canal ``avertissements``), elle ne se rabat JAMAIS sur du monophasé.

Ce module balaie la règle sur plusieurs puissances — dont ≤ 3 kWc, là où le
bug était le plus visible — avec ET sans batterie, épingle le cas de REFUS, et
épingle enfin que le client MONOPHASÉ et le raccordement NON DÉCLARÉ n'ont
strictement pas bougé.

Catalogue : celui RÉELLEMENT seedé (``manage.py seed_catalogue``, même motif
que ``test_pvfullrange_5_50``), semé UNE FOIS par classe. Aucun produit, prix
ou fiche n'est inventé ici.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_tri_jamais_mono"
"""
from decimal import Decimal
from io import StringIO
import itertools

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from apps.crm.models import Lead
from apps.ventes import services
from apps.ventes.compatibilites import est_triphase_produit
from authentication.models import Company

User = get_user_model()

#: Le wattage des DEUX panneaux seedés (aucun autre n'existe au catalogue).
WATT = 710

#: Les puissances balayées — les trois premières sont celles où le bug sortait
#: (aucun triphasé n'existe sous 10 kW, donc le monophasé gagnait).
KWC_BALAYES = (2.13, 3.0, 4.26, 7.1, 10.0, 15.0)

#: Le PLUS PETIT onduleur triphasé de chaque famille au catalogue seedé — ce
#: que doit recevoir un client triphasé de petite puissance (règle fondateur
#: d'origine : « le client tri prend le 10 kW tri »).
PLUS_PETIT_TRI_RESEAU = 'Onduleur réseau Huawei 10kW Triphasé'
PLUS_PETIT_TRI_HYBRIDE = 'Onduleur hybride Deye 10kW Triphasé'


def _est_ligne_onduleur(designation):
    return 'onduleur' in services._sans_accents(designation)


def _dit_monophase(designation):
    """« Monophasé », quelle que soit la casse ou l'accentuation saisie."""
    return 'monophas' in services._sans_accents(designation)


def _dit_triphase(designation):
    return 'triphas' in services._sans_accents(designation)


class TriJamaisMonoTest(TestCase):
    """Catalogue seedé UNE SEULE FOIS (``seed_catalogue`` est idempotent mais
    coûteux — jamais par test)."""

    _lead_seq = itertools.count(1)

    @classmethod
    def setUpTestData(cls):
        cls.company, _ = Company.objects.get_or_create(
            slug='ltri-co', defaults={'nom': 'L-TRI'})
        cls.user = User.objects.create_user(
            username='ltri', password='x', role_legacy='responsable',
            company=cls.company)
        call_command('seed_catalogue', company_slug=cls.company.slug,
                     stdout=StringIO())

    # ── Fabriques ────────────────────────────────────────────────────────

    def _catalogue(self):
        return services.catalogue_de_la_societe(self.company)

    def _catalogue_sans_onduleur_triphase(self):
        """Le MÊME catalogue, débarrassé des seuls onduleurs TRIPHASÉS : il
        reste des onduleurs (monophasés) — c'est ce qui distingue un REFUS
        d'un catalogue vide."""
        return [p for p in self._catalogue()
                if not (services.classer_produit(getattr(p, 'nom', '')) in
                        ('onduleur_reseau', 'onduleur_hybride')
                        and est_triphase_produit(p))]

    def _composer(self, *, kwc, avec_batterie, phase, produits=None,
                  avertissements=None):
        return services.composition_residentielle(
            self._catalogue() if produits is None else produits,
            kwc=kwc, panel_watt=WATT, avec_batterie=avec_batterie,
            taux_tva=Decimal('20'), phase=phase,
            avertissements=avertissements)

    def _lead(self):
        n = next(self._lead_seq)
        return Lead.objects.create(
            company=self.company, nom='LTri', prenom='Lead%d' % n,
            email='ltri-%d@example.com' % n, raccordement='triphase')

    @staticmethod
    def _cas(kwc, avec_batterie):
        return '%.2f kWc %s batterie' % (kwc,
                                         'AVEC' if avec_batterie else 'SANS')

    # ── LE VERROU ────────────────────────────────────────────────────────

    def test_aucune_ligne_monophasee_pour_un_client_triphase(self):
        """LE test de l'incident : sur TOUTE la plage, batterie ou non, aucune
        ligne composée pour un client TRIPHASÉ ne peut dire « Monophasé »."""
        for kwc, avec_batterie in itertools.product(KWC_BALAYES,
                                                    (False, True)):
            cas = self._cas(kwc, avec_batterie)
            with self.subTest(cas=cas):
                lignes = self._composer(kwc=kwc, avec_batterie=avec_batterie,
                                        phase='triphase')
                designations = [ligne.designation for ligne in lignes]
                self.assertTrue(
                    designations, '%s : composition VIDE' % cas)
                fautives = [d for d in designations if _dit_monophase(d)]
                self.assertEqual(
                    fautives, [],
                    '%s : client TRIPHASÉ et ligne MONOPHASÉE composée — %s'
                    % (cas, fautives))
                onduleurs = [d for d in designations if _est_ligne_onduleur(d)]
                self.assertTrue(
                    onduleurs,
                    '%s : aucune ligne onduleur composée pour un client '
                    'triphasé alors que le catalogue en porte' % cas)
                pas_tri = [d for d in onduleurs if not _dit_triphase(d)]
                self.assertEqual(
                    pas_tri, [],
                    '%s : onduleur retenu qui n\'annonce PAS le triphasé — %s'
                    % (cas, pas_tri))

    def test_petit_kwc_prend_le_plus_petit_triphase_meme_surdimensionne(self):
        """Le ratio des 80 % est un PLANCHER : à 2,13 kWc le client triphasé
        prend le 10 kW triphasé (× 4,7 sa puissance), jamais un 5 kW
        monophasé — c'est la règle d'origine du fondateur."""
        for avec_batterie, attendu in ((False, PLUS_PETIT_TRI_RESEAU),
                                       (True, PLUS_PETIT_TRI_HYBRIDE)):
            for kwc in (2.13, 3.0):
                cas = self._cas(kwc, avec_batterie)
                with self.subTest(cas=cas):
                    designations = [
                        ligne.designation for ligne in
                        self._composer(kwc=kwc, avec_batterie=avec_batterie,
                                       phase='triphase')]
                    onduleurs = [d for d in designations
                                 if _est_ligne_onduleur(d)]
                    self.assertIn(
                        attendu, onduleurs,
                        '%s : le plus petit onduleur TRIPHASÉ du catalogue '
                        '(« %s ») n\'a pas été retenu — %s'
                        % (cas, attendu, onduleurs))

    def test_catalogue_sans_triphase_refuse_et_n_invente_pas_de_mono(self):
        """Aucun triphasé utilisable ⇒ la composition est REFUSÉE et le DIT ;
        elle ne compose JAMAIS la ligne monophasée qui reste disponible."""
        attendu = services.avertissement_aucun_onduleur_triphase()
        produits = self._catalogue_sans_onduleur_triphase()
        self.assertTrue(
            any(services.classer_produit(getattr(p, 'nom', '')) in
                ('onduleur_reseau', 'onduleur_hybride') for p in produits),
            'le catalogue de ce test doit garder des onduleurs MONOPHASÉS : '
            'sans eux le refus ne prouverait rien')
        for avec_batterie in (False, True):
            cas = self._cas(7.1, avec_batterie)
            with self.subTest(cas=cas):
                avertissements = []
                lignes = self._composer(
                    kwc=7.1, avec_batterie=avec_batterie, phase='triphase',
                    produits=produits, avertissements=avertissements)
                designations = [ligne.designation for ligne in lignes]
                fautives = [d for d in designations if _dit_monophase(d)]
                self.assertEqual(
                    fautives, [],
                    '%s : catalogue sans triphasé — une ligne MONOPHASÉE a '
                    'été composée au lieu du refus : %s' % (cas, fautives))
                onduleurs = [d for d in designations if _est_ligne_onduleur(d)]
                self.assertEqual(
                    onduleurs, [],
                    '%s : un onduleur a été composé alors qu\'aucun triphasé '
                    'n\'est disponible — %s' % (cas, onduleurs))
                self.assertIn(
                    attendu, avertissements,
                    '%s : REFUS silencieux — le commercial doit lire le motif '
                    'français nommé ; avertissements = %s'
                    % (cas, avertissements))

    def test_le_refus_ne_casse_pas_le_client_monophase(self):
        """Le refus est PROPRE au raccordement triphasé : sur le MÊME
        catalogue amputé, un client monophasé garde son onduleur."""
        avertissements = []
        designations = [
            ligne.designation for ligne in self._composer(
                kwc=7.1, avec_batterie=False, phase='monophase',
                produits=self._catalogue_sans_onduleur_triphase(),
                avertissements=avertissements)]
        onduleurs = [d for d in designations if _est_ligne_onduleur(d)]
        self.assertTrue(
            onduleurs,
            'client MONOPHASÉ privé d\'onduleur par le verrou triphasé — %s'
            % designations)
        self.assertNotIn(
            services.avertissement_aucun_onduleur_triphase(), avertissements,
            'le refus TRIPHASÉ a été prononcé pour un client monophasé — %s'
            % avertissements)

    # ── ÉPINGLES DE NON-RÉGRESSION (mono / non déclaré : inchangés) ───────

    def test_le_client_monophase_n_a_pas_bouge(self):
        """PVCOMPAT tel quel : jamais de triphasé chez un monophasé, et le
        5 kWc reste servi par l'onduleur réseau 5 kW monophasé du catalogue."""
        for kwc, avec_batterie in itertools.product(KWC_BALAYES,
                                                    (False, True)):
            cas = self._cas(kwc, avec_batterie)
            with self.subTest(cas=cas):
                designations = [
                    ligne.designation for ligne in
                    self._composer(kwc=kwc, avec_batterie=avec_batterie,
                                   phase='monophase')]
                onduleurs = [d for d in designations
                             if _est_ligne_onduleur(d)]
                self.assertTrue(
                    onduleurs, '%s : client monophasé sans onduleur' % cas)
                fautifs = [d for d in onduleurs if _dit_triphase(d)]
                self.assertEqual(
                    fautifs, [],
                    '%s : onduleur TRIPHASÉ chez un client monophasé — %s'
                    % (cas, fautifs))

        ancre = [ligne.designation for ligne in
                 self._composer(kwc=5.0, avec_batterie=False,
                                phase='monophase')]
        self.assertIn(
            'Onduleur réseau Huawei 5kW Monophasé', ancre,
            'épingle monophasée déplacée : 5 kWc sans batterie ne compose '
            'plus l\'onduleur réseau 5 kW monophasé — %s'
            % [d for d in ancre if _est_ligne_onduleur(d)])

    def test_le_raccordement_non_declare_n_a_pas_bouge(self):
        """Sans raccordement déclaré, l'heuristique historique décide SEULE
        (« ≥ 10 kW ⇒ triphasé »), à l'identique : 5 kWc réseau reste
        monophasé, 7,1 kWc hybride reste le 10 kW triphasé."""
        reseau = [ligne.designation for ligne in
                  self._composer(kwc=5.0, avec_batterie=False, phase=None)]
        self.assertIn(
            'Onduleur réseau Huawei 5kW Monophasé', reseau,
            'raccordement NON déclaré : le choix historique a bougé — %s'
            % [d for d in reseau if _est_ligne_onduleur(d)])

        hybride = [ligne.designation for ligne in
                   self._composer(kwc=7.1, avec_batterie=True, phase=None)]
        self.assertIn(
            PLUS_PETIT_TRI_HYBRIDE, hybride,
            'raccordement NON déclaré : le choix historique a bougé — %s'
            % [d for d in hybride if _est_ligne_onduleur(d)])

    # ── CHEMIN DE PRODUCTION ─────────────────────────────────────────────

    def test_le_devis_reellement_construit_ne_porte_aucun_monophase(self):
        """Le même verrou par le chemin de PRODUCTION
        (``build_devis_from_layout``, celui qu'appellent la création auto et
        le calepinage 3D) : un lead TRIPHASÉ de 3 kWc."""
        journal = {}
        devis = services.build_devis_from_layout(
            layout={'panelWatt': WATT, 'scenario': 'reseau',
                    'result': {'kwc': 3.0}},
            user=self.user, company=self.company, lead=self._lead(),
            journal=journal, phase='triphase')
        designations = [ligne.designation for ligne in devis.lignes.all()]
        fautives = [d for d in designations if _dit_monophase(d)]
        self.assertEqual(
            fautives, [],
            'devis %s : lead TRIPHASÉ et ligne MONOPHASÉE au devis — %s'
            % (devis.reference, fautives))
        self.assertIn(
            PLUS_PETIT_TRI_RESEAU, designations,
            'devis %s : le plus petit onduleur triphasé n\'est pas au devis '
            '— %s' % (devis.reference,
                      [d for d in designations if _est_ligne_onduleur(d)]))
