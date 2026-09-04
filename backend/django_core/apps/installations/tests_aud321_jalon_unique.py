"""AUD321 — `JalonProjet(installation, phase)` est unique EN BASE.

Défaut d'origine : `notifier_reception_solde_a_facturer` crée le jalon
`(installation, phase=RECEPTION)` par `get_or_create`, mais `JalonProjet.Meta`
ne portait AUCUN `unique_together` / `UniqueConstraint` — contrairement à
`StockReservation` ou aux OneToOne `CommissioningRecord`/`HandoverPack`. Or la
reprise interne de `get_or_create` (IntegrityError → re-`get`) n'a rien à
intercepter tant que la base ne contraint rien : deux PATCH quasi-simultanés
faisant passer le même chantier à RECEPTIONNE (double submit, retry) passaient
tous deux la lecture et créaient DEUX lignes RECEPTION divergentes — dont une
seule portait le drapeau d'idempotence `rappel_facturation_envoye`.

C'est donc la CONTRAINTE elle-même qui est le correctif, et c'est elle que ces
tests exercent : la seconde écriture est refusée par la base (ce que
`get_or_create` transforme en « je relis le gagnant »), et les jalons AD HOC
(phase vide/NULL) restent libres.

Run :
    python manage.py test apps.installations.tests_aud321_jalon_unique -v2
"""
import itertools

from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.installations.models import Installation, JalonProjet
from apps.installations.services import notifier_reception_solde_a_facturer


_seq = itertools.count(1)


def make_company():
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'aud321-co-{n}', defaults={'nom': f'AUD321 Co {n}'})
    return company


class JalonUniqueParPhaseTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.inst = Installation.objects.create(
            company=self.company, reference=f'AUD321-{next(_seq)}')

    def _jalon(self, phase, libelle='Réception'):
        return JalonProjet.objects.create(
            company=self.company, installation=self.inst,
            phase=phase, libelle=libelle)

    def test_deuxieme_jalon_de_meme_phase_refuse_par_la_base(self):
        """ROUGE avant AUD321 : la seconde ligne s'insérait sans broncher."""
        self._jalon(JalonProjet.Phase.RECEPTION)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._jalon(JalonProjet.Phase.RECEPTION, 'Réception bis')

    def test_get_or_create_resout_sur_le_gagnant(self):
        """C'est la contrainte qui rend `get_or_create` course-safe : sans
        elle, sa reprise IntegrityError → re-`get` n'intercepte jamais rien."""
        gagnant = self._jalon(JalonProjet.Phase.RECEPTION)
        jalon, cree = JalonProjet.objects.get_or_create(
            installation=self.inst, phase=JalonProjet.Phase.RECEPTION,
            defaults={'company': self.company, 'libelle': 'Réception'})
        self.assertFalse(cree)
        self.assertEqual(jalon.id, gagnant.id)
        self.assertEqual(
            JalonProjet.objects.filter(
                installation=self.inst,
                phase=JalonProjet.Phase.RECEPTION).count(), 1)

    def test_phases_differentes_coexistent(self):
        self._jalon(JalonProjet.Phase.RECEPTION)
        self._jalon(JalonProjet.Phase.POSE, 'Pose')
        self.assertEqual(
            JalonProjet.objects.filter(installation=self.inst).count(), 2)

    def test_deux_chantiers_ont_chacun_leur_jalon_de_phase(self):
        autre = Installation.objects.create(
            company=self.company, reference=f'AUD321-{next(_seq)}')
        self._jalon(JalonProjet.Phase.RECEPTION)
        JalonProjet.objects.create(
            company=self.company, installation=autre,
            phase=JalonProjet.Phase.RECEPTION, libelle='Réception')
        self.assertEqual(
            JalonProjet.objects.filter(
                phase=JalonProjet.Phase.RECEPTION).count(), 2)

    def test_les_jalons_ad_hoc_restent_libres(self):
        """`phase` NULL ou vide = jalon ad hoc : hors de l'index partiel."""
        for phase in (None, ''):
            with self.subTest(phase=phase):
                JalonProjet.objects.create(
                    company=self.company, installation=self.inst,
                    phase=phase, libelle='Visite de courtoisie')
                JalonProjet.objects.create(
                    company=self.company, installation=self.inst,
                    phase=phase, libelle='Visite de courtoisie 2')
        self.assertEqual(
            JalonProjet.objects.filter(installation=self.inst).count(), 4)

    def test_appliquer_modele_ne_viole_jamais_la_contrainte(self):
        """Un modèle de projet portant une phase DÉJÀ posée sur le chantier
        crée un jalon AD HOC au lieu de faire remonter une 500."""
        from apps.installations.models import ModeleProjet, ModeleProjetJalon
        from apps.installations.services import instantiate_modele_projet

        self._jalon(JalonProjet.Phase.POSE, 'Pose (existant)')
        modele = ModeleProjet.objects.create(
            company=self.company, nom=f'Modèle AUD321-{next(_seq)}')
        ModeleProjetJalon.objects.create(
            company=self.company, modele=modele,
            phase=JalonProjet.Phase.POSE,
            libelle='Pose (modèle)', ordre=1, offset_jours=10)

        instantiate_modele_projet(self.inst, modele)

        libelles = set(JalonProjet.objects.filter(
            installation=self.inst).values_list('libelle', flat=True))
        self.assertIn('Pose (modèle)', libelles)
        self.assertEqual(
            JalonProjet.objects.filter(
                installation=self.inst,
                phase=JalonProjet.Phase.POSE).count(), 1)

    def test_notifier_reception_deux_fois_ne_cree_quun_jalon(self):
        """Le chemin réel (YSERV7) : deux appels = UN jalon RECEPTION."""
        from decimal import Decimal
        from apps.crm.models import Client
        from apps.ventes.models import Devis

        n = next(_seq)
        client = Client.objects.create(
            company=self.company, nom='Site', prenom='Client',
            email=f'aud321-{self.company.id}-{n}@example.invalid')
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-AUD321-{n}',
            client=client, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20'))
        self.inst.devis = devis
        self.inst.save(update_fields=['devis'])

        notifier_reception_solde_a_facturer(self.inst)
        notifier_reception_solde_a_facturer(self.inst)
        jalons = JalonProjet.objects.filter(
            installation=self.inst, phase=JalonProjet.Phase.RECEPTION)
        self.assertEqual(jalons.count(), 1)
        self.assertTrue(jalons.first().atteint)
