# -*- coding: utf-8 -*-
"""PVFULLRANGE — garde-fou PERMANENT : « toujours pouvoir composer un devis
complet de 5 à 50 kWc, dans ses différentes saveurs, et TOUJOURS obtenir le
devis ET le schéma unifilaire » (ordre fondateur, 20/08/2026).

Ce module ne teste pas une fonction isolée : il COMPOSE, sur le catalogue
RÉELLEMENT SEEDÉ (``manage.py seed_catalogue``), chaque saveur que l'audit du
20/08 a vérifiée reachable, et parcourt les TROIS chaînes de bout en bout :

  1. **La chaîne CATALOGUE** — un kit COMPLET (panneaux, onduleur du bon
     palier, structures, câbles, forfaits, ± batterie), chaque ligne tarifée
     (> 0), un total TTC positif.
  2. **La chaîne FICHE TECHNIQUE** — aucune variable d'équipement manquante
     (``fiches_manquantes_du_devis`` == []) : PVFCH interdit tout calcul sur
     une valeur supposée.
  3. **La chaîne ÉLECTRIQUE/SCHÉMA** — ``build_electrical_design`` ne refuse
     PAS pour fiche incomplète, et ``rendre_schema_du_devis`` rend un SVG.

ENTRÉE CHOISIE. ``apps.ventes.services.build_devis_from_layout`` (le chemin de
PRODUCTION — c'est lui que ``ventes.devis.creer_auto`` et le calepinage 3D
appellent) pour CHAQUE saveur où le sélecteur automatique de
``composition_residentielle`` retombe naturellement sur le bon modèle depuis
un simple couple (kWc cible, avec/sans batterie). UNE saveur ne s'atteint PAS
ainsi : « hybride monophasé 10 kW ». ``choisir_onduleur`` (services.py,
~L2014) préfère TOUJOURS le triphasé dès que le modèle retenu couvre ≥ 10 kW
(``prefere_tri = meilleure >= 10``) — et à 10 kW le catalogue porte À LA FOIS
OND-H-DEY-10M (mono) ET OND-H-DEY-10T (tri) au MÊME palier : le tri gagne
systématiquement, jamais le mono. Pour cette seule saveur, le test appelle
directement ``composition_residentielle`` — LA MÊME fonction, sur LE MÊME
catalogue seedé, LES MÊMES prix et fiches — simplement débarrassée du modèle
triphasé AVANT l'appel, puis assemble le ``Devis``/``LigneDevis`` à la main
(même patron que la fermeture ``_create`` de ``build_devis_from_layout``).
Aucun produit, prix ou fiche n'est inventé nulle part dans ce module.

LA MATRICE ENCODÉE (catalogue du 20/08/2026) :

  * réseau triphasé — 10, 15, 20, 30 (bascule sur le modèle 25 kW, aucun
    palier 30 kW n'existe), 50 kWc — Huawei OND-R-HUA-*T.
  * réseau monophasé — 5 kWc seul (OND-R-HUA-5M ; les paliers mono 10/12 kW
    sont ARCHIVÉS par le seeder, ``ARTEFACTS_ONDULEUR_SKUS`` — jamais
    reachable par la composition automatique).
  * hybride monophasé + batterie — 5 kWc (naturel) et 10 kWc (vivier forcé,
    cf. ci-dessus) — Deye OND-H-DEY-5M/10M + Dyness BAT-DEY-5/10 (fenêtre
    basse tension 40-60 V, batterie mesurée à 51,2 V).
  * hybride triphasé BASSE TENSION + batterie — 10, 15 et 20 kWc
    (OND-H-DEY-10T/15T/20T, tous SG05LP3 basse tension — PVLV2, fondateur
    21/08/2026 : « i only know 15 and 20kw on LV ») — MÊME fenêtre 40-60 V
    que les mono, batteries Dyness 51,2 V.

TROU DE CATALOGUE DOCUMENTÉ, DÉLIBÉRÉMENT NON COUVERT PAR LA MATRICE
CI-DESSUS : aucun onduleur hybride ≥ 25 kW n'existe au catalogue (le parc
réel s'arrête à 20 kW ; la batterie HV Deye BOS-B Pro reste hors
auto-composition — système C&I apparié par Deye aux onduleurs 30-80 kW).
Une demande « hybride 30 kW avec batterie » replie donc sur le plus gros
modèle disponible.
``QuoteFullRange5To50Test.test_trous_catalogue_documentes_ne_cassent_jamais``
vérifie SEULEMENT que cette composition ne LÈVE JAMAIS — elle ne fige à
dessein aucune sortie dégradée, pour que le jour où le fondateur ajoute un
palier ≥ 25 kW rien ici ne devienne rouge.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_pvfullrange_5_50"
"""
from collections import namedtuple
from decimal import Decimal
from io import StringIO
import itertools

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from apps.crm.models import Lead
from apps.crm.services import resolve_client_for_lead
from apps.ventes import electrical_service, services
from apps.ventes.models import Devis, LigneDevis
from apps.ventes.utils.references import create_with_reference
from authentication.models import Company

User = get_user_model()

#: Désignation EXACTE (``seed_catalogue.CATALOGUE``) de l'onduleur hybride
#: triphasé 10 kW — retiré du vivier pour forcer la saveur MONOPHASÉE au même
#: palier (cf. le bandeau du module).
_ONDULEUR_HYBRIDE_10T = 'Onduleur hybride Deye 10kW Triphasé'


Saveur = namedtuple(
    'Saveur',
    'label kwc avec_batterie famille phase kw_attendu exclure_noms')

#: La matrice REACHABLE vérifiée le 20/08/2026 sur le catalogue seedé —
#: ``famille`` ∈ {'reseau', 'hybride'}, ``phase`` ∈ {'mono', 'tri'}.
REACHABLE_MATRIX = (
    Saveur('réseau monophasé 5 kW', 5, False, 'reseau', 'mono', 5, ()),
    Saveur('réseau triphasé 10 kW', 10, False, 'reseau', 'tri', 10, ()),
    Saveur('réseau triphasé 15 kW', 15, False, 'reseau', 'tri', 15, ()),
    Saveur('réseau triphasé 20 kW', 20, False, 'reseau', 'tri', 20, ()),
    Saveur('réseau triphasé 30 kW (bascule sur le 25T)', 30, False,
           'reseau', 'tri', 25, ()),
    Saveur('réseau triphasé 50 kW', 50, False, 'reseau', 'tri', 50, ()),
    Saveur('hybride monophasé 5 kW avec batterie', 5, True,
           'hybride', 'mono', 5, ()),
    Saveur('hybride monophasé 10 kW avec batterie (vivier forcé)', 10, True,
           'hybride', 'mono', 10, (_ONDULEUR_HYBRIDE_10T,)),
    Saveur('hybride triphasé basse tension 10 kW avec batterie', 10, True,
           'hybride', 'tri', 10, ()),
    # PVLV2 (fondateur 21/08/2026) — les 15/20 kW du catalogue SONT les
    # SG05LP3 basse tension (fenêtre batterie 40-60 V, Dyness 51,2 V) :
    # composables de bout en bout avec leurs prix d'origine.
    Saveur('hybride triphasé basse tension 15 kW avec batterie (PVLV2)', 15,
           True, 'hybride', 'tri', 15, ()),
    Saveur('hybride triphasé basse tension 20 kW avec batterie (PVLV2)', 20,
           True, 'hybride', 'tri', 20, ()),
)

#: Au-delà du dernier palier hybride du catalogue (20 kW LV) — cf. bandeau du
#: module : jamais dans ``REACHABLE_MATRIX``, sortie dégradée PAS pinnée.
TROUS_DOCUMENTES_KWC = (30,)


class QuoteFullRange5To50Test(TestCase):
    """Catalogue seedé UNE SEULE FOIS (``seed_catalogue`` est idempotent mais
    coûteux — jamais par test)."""

    _lead_seq = itertools.count(1)

    @classmethod
    def setUpTestData(cls):
        cls.company, _ = Company.objects.get_or_create(
            slug='pvfullrange-co', defaults={'nom': 'PV Full Range'})
        cls.user = User.objects.create_user(
            username='pvfullrange', password='x',
            role_legacy='responsable', company=cls.company)
        out = StringIO()
        call_command('seed_catalogue', company_slug=cls.company.slug,
                     stdout=out)

    # ── Fabriques ────────────────────────────────────────────────────────

    def _lead(self):
        n = next(self._lead_seq)
        return Lead.objects.create(
            company=self.company, nom='FullRange', prenom='Lead%d' % n,
            email='fullrange-%d@example.com' % n)

    def _devis_layout(self, *, kwc, avec_batterie):
        """Chemin de PRODUCTION : ``build_devis_from_layout`` sur le
        catalogue seedé COMPLET, sans calepinage 3D (donc un unique groupe de
        panneaux dérivé des LIGNES — ``groupes_du_devis``)."""
        layout = {
            'panelWatt': 710,
            'scenario': 'avec_batterie' if avec_batterie else 'reseau',
            'result': {'kwc': kwc},
        }
        return services.build_devis_from_layout(
            layout=layout, user=self.user, company=self.company,
            lead=self._lead())

    def _devis_composition_directe(self, *, kwc, avec_batterie,
                                   exclure_noms):
        """Repli EXPLICITE pour une saveur que le sélecteur automatique NE
        PEUT PAS atteindre à lui seul (égalité de puissance mono/tri, cf. le
        bandeau du module). Appelle ``composition_residentielle`` — LA MÊME
        fonction — sur le catalogue RÉEL, seulement débarrassé des
        désignations de ``exclure_noms``, puis assemble le devis à la main,
        au même patron que la fermeture ``_create`` de
        ``build_devis_from_layout``."""
        lead = self._lead()
        client = resolve_client_for_lead(lead)
        taux_tva = Decimal('20')
        produits = [p for p in services.catalogue_de_la_societe(self.company)
                    if p.nom not in exclure_noms]
        line_specs = services.composition_residentielle(
            produits, kwc=kwc, panel_watt=710, avec_batterie=avec_batterie,
            taux_tva=taux_tva,
            marques=services.carte_marques_composition(self.company),
            ordre_lignes=services.ordre_lignes_societe(self.company))

        def _create(reference):
            devis = Devis.objects.create(
                company=self.company, reference=reference, client=client,
                lead=lead, statut=Devis.Statut.BROUILLON, taux_tva=taux_tva,
                remise_globale=Decimal('0'), created_by=self.user,
                mode_installation=Devis.ModeInstallation.RESIDENTIEL,
                etude_params={'puissance_kwc': kwc})
            for index, spec in enumerate(line_specs):
                LigneDevis.objects.create(
                    devis=devis, produit=spec.produit,
                    designation=spec.designation,
                    quantite=Decimal(str(spec.quantite)),
                    prix_unitaire=Decimal(spec.prix_unitaire),
                    remise=Decimal('0'), ordre=index)
            return devis

        return create_with_reference(Devis, 'DEV', self.company, _create)

    # ── Assertions partagées ────────────────────────────────────────────

    def _assert_chaine_complete(self, devis, label):
        """Les trois chaînes (catalogue → fiche → électrique/schéma), pour LA
        saveur ``label`` — chaque message d'échec la NOMME, jamais un numéro
        de ligne anonyme (c'est le tableau de bord catalogue du fondateur)."""
        self.assertTrue(devis.pk, '%s : devis non créé' % label)
        lignes = list(devis.lignes.all())
        self.assertTrue(
            lignes, '%s : devis composé SANS AUCUNE ligne' % label)
        for ligne in lignes:
            self.assertGreater(
                Decimal(ligne.prix_unitaire), 0,
                '%s : ligne « %s » à prix ZÉRO — jamais coté au client'
                % (label, ligne.designation))
        self.assertGreater(
            devis.total_ttc, 0, '%s : total TTC nul ou négatif' % label)

        manquantes = electrical_service.fiches_manquantes_du_devis(devis)
        self.assertEqual(
            manquantes, [],
            '%s : fiche technique incomplète — %s'
            % (label, electrical_service.motifs_fiche_incomplete(devis)))

        design = electrical_service.build_electrical_design(devis)
        bloquants = list(design['conformite']['bloquants'])
        refus_fiche = [b for b in bloquants if 'non renseigné' in b]
        self.assertEqual(
            refus_fiche, [],
            '%s : étude électrique refusée pour fiche incomplète — %s'
            % (label, refus_fiche))
        self.assertEqual(
            bloquants, [],
            '%s : étude électrique BLOQUÉE par le moteur (défaut '
            'd\'ingénierie réel, pas un trou de catalogue) — %s'
            % (label, bloquants))

        schema = electrical_service.rendre_schema_du_devis(devis)
        self.assertIsInstance(
            schema, str,
            '%s : aucun schéma unifilaire rendu (None)' % label)
        self.assertIn(
            '<svg', schema,
            '%s : le rendu ne contient aucun <svg> — %r'
            % (label, schema[:120]))

        return lignes

    def _assert_kit_coherent(self, lignes, label, *, famille, phase,
                             kw_attendu):
        """Le kit sert la bonne FAMILLE (réseau XOR hybride+batterie) et le
        bon PALIER — classification par les prédicats PARTAGÉS du moteur de
        devis (``services._is_battery``/``_is_hybrid_inverter``/
        ``_is_reseau_inverter``, mêmes mots-clés que le PDF), jamais un
        mot-clé réinventé ici."""
        designations = [li.designation for li in lignes]
        onduleurs = [d for d in designations if 'onduleur' in d.lower()]
        self.assertTrue(
            onduleurs, '%s : aucune ligne onduleur composée' % label)

        a_batterie = any(services._is_battery(d) for d in designations)
        a_hybride = any(services._is_hybrid_inverter(d) for d in designations)
        a_reseau = any(services._is_reseau_inverter(d) for d in designations)

        if famille == 'reseau':
            self.assertTrue(
                a_reseau,
                '%s : aucun onduleur RÉSEAU retenu — %s' % (label, onduleurs))
            self.assertFalse(
                a_hybride,
                '%s : un onduleur HYBRIDE s\'est glissé dans un kit réseau '
                '— %s' % (label, onduleurs))
            self.assertFalse(
                a_batterie,
                '%s : une BATTERIE s\'est glissée dans un devis réseau '
                '(sans batterie demandée)' % label)
        else:
            self.assertTrue(
                a_hybride,
                '%s : aucun onduleur HYBRIDE retenu — %s'
                % (label, onduleurs))
            self.assertFalse(
                a_reseau,
                '%s : un onduleur RÉSEAU s\'est glissé dans un kit hybride '
                '— %s' % (label, onduleurs))
            self.assertTrue(
                a_batterie,
                '%s : AUCUNE ligne batterie — le devis « avec batterie » en '
                'est parti sans stockage' % label)

        attendu = 'monophasé' if phase == 'mono' else 'triphasé'
        self.assertTrue(
            any(attendu in d.lower() for d in onduleurs),
            '%s : aucun onduleur %s parmi les retenus — %s'
            % (label, attendu, onduleurs))

        motif_kw = '%dkW' % kw_attendu
        self.assertTrue(
            any(motif_kw in d for d in onduleurs),
            '%s : palier %d kW absent des onduleurs retenus — %s'
            % (label, kw_attendu, onduleurs))

    # ── La matrice ───────────────────────────────────────────────────────

    def test_matrice_saveurs_reachables(self):
        """La matrice VÉRIFIÉE du 20/08/2026, saveur par saveur, avec
        ``subTest`` : une saveur cassée ne masque pas les autres — le
        fondateur voit TOUT ce qui a régressé en une seule exécution."""
        for saveur in REACHABLE_MATRIX:
            with self.subTest(saveur=saveur.label):
                if saveur.exclure_noms:
                    devis = self._devis_composition_directe(
                        kwc=saveur.kwc, avec_batterie=saveur.avec_batterie,
                        exclure_noms=saveur.exclure_noms)
                else:
                    devis = self._devis_layout(
                        kwc=saveur.kwc, avec_batterie=saveur.avec_batterie)
                lignes = self._assert_chaine_complete(devis, saveur.label)
                self._assert_kit_coherent(
                    lignes, saveur.label, famille=saveur.famille,
                    phase=saveur.phase, kw_attendu=saveur.kw_attendu)

    def test_trous_catalogue_documentes_ne_cassent_jamais(self):
        """PVLV — au-delà du dernier palier hybride du catalogue (20 kW LV),
        la composition replie sur le plus gros modèle disponible. AUCUNE
        assertion sur le dimensionnement ni la présence d'une batterie ici :
        c'est PRÉCISÉMENT le trou documenté — ce test vérifie SEULEMENT que
        composer à ce palier NE LÈVE JAMAIS et rend toujours un devis tarifé.
        Le jour où le fondateur ajoute un hybride ≥ 25 kW, rien ici ne doit
        devenir rouge — ajoutez alors le palier à ``REACHABLE_MATRIX``.
        """
        for kwc in TROUS_DOCUMENTES_KWC:
            label = ('hybride triphasé %d kW avec batterie — au-delà du '
                     'catalogue (trou documenté)' % kwc)
            with self.subTest(saveur=label):
                try:
                    devis = self._devis_layout(kwc=kwc, avec_batterie=True)
                except Exception as exc:  # noqa: BLE001 — la garantie EST
                    # « ne casse jamais » : une levée ICI est l'échec que ce
                    # test existe pour attraper.
                    self.fail(
                        '%s : la composition a LEVÉ %r au lieu de dégrader '
                        'gracieusement (rendre un devis SANS batterie plutôt '
                        'que planter)' % (label, exc))

                self.assertTrue(devis.pk, '%s : aucun devis rendu' % label)
                lignes = list(devis.lignes.all())
                self.assertTrue(
                    lignes, '%s : devis composé SANS AUCUNE ligne' % label)
                self.assertGreater(
                    devis.total_ttc, 0,
                    '%s : total TTC nul ou négatif' % label)

                # La conception électrique (panneau/onduleur, indépendante de
                # la batterie) ne doit pas non plus CASSER.
                try:
                    electrical_service.build_electrical_design(devis)
                    electrical_service.rendre_schema_du_devis(devis)
                except Exception as exc:  # noqa: BLE001
                    self.fail(
                        '%s : la conception électrique a LEVÉ %r au lieu de '
                        'dégrader gracieusement' % (label, exc))
