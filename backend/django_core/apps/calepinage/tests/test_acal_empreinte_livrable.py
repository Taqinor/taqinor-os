"""ACAL221 — ``empreinte_des_entrees`` : stable sans geste, sensible à CHAQUE
entrée d'un livrable, insensible aux champs volatils.

Le calepinage est fabriqué par les VRAIS écrivains
(``acal_livrables_helpers.calepinage_simule_reel`` : entrée électrique puis
simulation, météo rejouée), puis enregistré en base ; chaque cas modifie UNE
entrée par son écrivain réel (``enregistrer_layout``, ``modifier_resultat`` —
l'écrivain unique de ``Calepinage.resultat`` —, ORM du module pour la pose
réelle / les photos / les gabarits, sélecteurs CRM lus tels quels). La seule
substitution est le catalogue matériel (``patch_materiel``), seam documenté
des essais de livrables : la source sous test n'est jamais simulée.

Run :
    python manage.py test apps.calepinage.tests.test_acal_empreinte_livrable -v2
"""
import copy
import datetime

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from apps.calepinage.models import (
    Calepinage, GabaritDossierReglementaire, PhotoSite, PoseReelle,
)
from apps.calepinage.services.empreinte_livrable import empreinte_des_entrees
from apps.calepinage.services.layout import enregistrer_layout
from apps.calepinage.services.resultat import modifier_resultat
from apps.crm.models import Client, Lead
from apps.records.models import Attachment
from apps.roles.models import Role
from apps.roles.permissions_registre import DIRECTEUR_PERMISSIONS
from authentication.models import Company
from core.models import TenantTheme

from .acal_livrables_helpers import calepinage_simule_reel, patch_materiel

User = get_user_model()


class EmpreinteLivrableTest(TestCase):
    def setUp(self):
        self.societe = Company.objects.create(nom='ACAL221', slug='acal221')
        role = Role.objects.create(company=self.societe, nom='Directeur',
                                   permissions=list(DIRECTEUR_PERMISSIONS))
        self.user = User.objects.create_user(
            username='acal221', password='x', company=self.societe,
            role=role)
        self.lead = Lead.objects.create(company=self.societe,
                                        nom='Toiture 221', adresse='Anfa')
        pivot = calepinage_simule_reel()
        self.calepinage = Calepinage.objects.create(
            company=self.societe, lead_id=self.lead.pk, titre='Villa 221',
            roof_layout=copy.deepcopy(pivot.roof_layout),
            resultat=copy.deepcopy(pivot.resultat),
            layout_hash=pivot.layout_hash or '',
            version_moteur=pivot.version_moteur or '')

    # ── outils ──────────────────────────────────────────────────────────
    def _empreinte(self, langue='fr', sections=None):
        calepinage = Calepinage.objects.get(pk=self.calepinage.pk)
        with patch_materiel():
            return empreinte_des_entrees(calepinage, langue, sections)

    def _piece(self, nom):
        return Attachment.objects.create(
            company=self.societe,
            content_type=ContentType.objects.get_for_model(Calepinage),
            object_id=self.calepinage.pk, file_key=f'cle/{nom}',
            filename=nom, size=10, mime='image/jpeg')

    def _saisie(self, cle, valeur):
        def poser(resultat):
            resultat[cle] = valeur
        modifier_resultat(self.calepinage, poser)

    # ── les écrivains d'UNE entrée chacun ───────────────────────────────
    def _conception(self):
        layout = copy.deepcopy(self.calepinage.roof_layout)
        layout['zones'][0]['geometry']['count'] -= 1
        with patch_materiel():
            enregistrer_layout(self.calepinage, layout, user=self.user)

    def _simulation_relancee(self):
        def relancer(resultat):
            production = copy.deepcopy(resultat.get('production') or {})
            production['acal221_relance'] = 1
            resultat['production'] = production
        modifier_resultat(self.calepinage, relancer)

    def _entree_electrique(self):
        entree = copy.deepcopy(
            self.calepinage.resultat.get('entree_electrique') or {})
        entree['dc_m'] = 42
        self._saisie('entree_electrique', entree)

    def _raccordement(self):
        self._saisie('raccordement_saisie', {'distance_m': 17})

    def _sld(self):
        self._saisie('sld_edition', {'notes': ['repère Q1 déplacé']})

    def _pose_reelle(self):
        PoseReelle.objects.create(
            company=self.societe, calepinage=self.calepinage, pan='Pan 1',
            modules_poses=9, releve_le=datetime.date(2026, 9, 1))

    def _pose_corrigee(self):
        pose = PoseReelle.objects.create(
            company=self.societe, calepinage=self.calepinage, pan='Pan 1',
            modules_poses=9, releve_le=datetime.date(2026, 9, 1))
        self._avant = self._empreinte()
        pose.modules_poses = 8
        pose.save()

    def _gabarit(self):
        GabaritDossierReglementaire.objects.create(
            company=self.societe, pays='ma', code='manuel', genre='manuel',
            intitule='Manuel', version='1')

    def _gabarit_version(self):
        gabarit = GabaritDossierReglementaire.objects.create(
            company=self.societe, pays='ma', code='dp', intitule='DP',
            version='1')
        self._avant = self._empreinte()
        gabarit.version = '2'
        gabarit.save()

    def _gabarit_fichier(self):
        gabarit = GabaritDossierReglementaire.objects.create(
            company=self.societe, pays='ma', code='dp', intitule='DP',
            version='1')
        self._avant = self._empreinte()
        gabarit.fichier = self._piece('gabarit.pdf')
        gabarit.save()

    def _photo(self):
        PhotoSite.objects.create(
            company=self.societe, calepinage=self.calepinage,
            attachment=self._piece('toit.jpg'),
            prise_le=datetime.date(2026, 8, 1))

    def _titre(self):
        self.calepinage.titre = 'Villa 221 bis'
        self.calepinage.save(update_fields=['titre'])

    def _client(self):
        client = Client.objects.create(company=self.societe, nom='Atlas',
                                       adresse='Rue 1')
        self.calepinage.client = client
        self.calepinage.save(update_fields=['client'])

    def _adresse_client(self):
        client = Client.objects.create(company=self.societe, nom='Atlas',
                                       adresse='Rue 1')
        self.calepinage.client = client
        self.calepinage.save(update_fields=['client'])
        self._avant = self._empreinte()
        client.adresse = 'Rue 2'
        client.save()

    def _adresse_lead(self):
        self.lead.adresse = 'Maârif'
        self.lead.save()

    def _theme(self):
        TenantTheme.objects.create(company=self.societe,
                                   couleur_primaire='#123456',
                                   nom_affichage='Marque 221')

    # ── essais ──────────────────────────────────────────────────────────
    def test_stable_entre_deux_lectures_sans_geste(self):
        premiere = self._empreinte()
        seconde = self._empreinte()
        self.assertEqual(premiere, seconde)
        self.assertEqual(len(premiere), 64)

    def test_sensible_a_chaque_classe_d_entree(self):
        cas = {
            'conception': self._conception,
            'simulation_relancee': self._simulation_relancee,
            'entree_electrique': self._entree_electrique,
            'raccordement_saisie': self._raccordement,
            'sld_edition': self._sld,
            'pose_reelle_saisie': self._pose_reelle,
            'pose_reelle_corrigee': self._pose_corrigee,
            'gabarit_ajoute': self._gabarit,
            'gabarit_version': self._gabarit_version,
            'gabarit_fichier': self._gabarit_fichier,
            'photo_de_site': self._photo,
            'titre': self._titre,
            'client': self._client,
            'adresse_client': self._adresse_client,
            'adresse_lead': self._adresse_lead,
            'theme_societe': self._theme,
        }
        for nom, geste in cas.items():
            with self.subTest(entree=nom):
                sid = self._savepoint()
                try:
                    self._avant = self._empreinte()
                    geste()
                    self.assertNotEqual(self._avant, self._empreinte(),
                                        f'{nom} ne change pas l\'empreinte')
                finally:
                    self._rollback(sid)

    def test_sensible_a_la_langue_et_aux_sections(self):
        base = self._empreinte('fr', None)
        self.assertNotEqual(base, self._empreinte('en', None))
        self.assertNotEqual(base, self._empreinte('fr', ['ombrage']))
        self.assertNotEqual(self._empreinte('fr', ['ombrage']),
                            self._empreinte('fr', ['ombrage', 'pertes']))

    def test_insensible_aux_champs_volatils(self):
        # Une consommation déjà saisie (sinon on ajouterait la clé
        # `consumption.source` elle-même, qui, elle, est de la conception).
        layout = copy.deepcopy(self.calepinage.roof_layout)
        layout.setdefault('consumption', {}).setdefault('source', {})[
            'saisi_le'] = '2026-01-01T00:00:00Z'
        Calepinage.objects.filter(pk=self.calepinage.pk).update(
            roof_layout=layout)
        self.calepinage.refresh_from_db()
        avant = self._empreinte()
        # La date de saisie de la consommation (roof_layout) …
        layout = copy.deepcopy(self.calepinage.roof_layout)
        layout['consumption']['source']['saisi_le'] = '2030-01-01T00:00:00Z'
        layout['activeAreaId'] = 'autre-pan'
        Calepinage.objects.filter(pk=self.calepinage.pk).update(
            roof_layout=layout)
        self.calepinage.refresh_from_db()

        # … et la date du calcul de simulation ne comptent pas.
        def redater(resultat):
            simulation = dict(resultat.get('simulation') or {})
            simulation['calcule_le'] = '2030-01-01T00:00:00Z'
            resultat['simulation'] = simulation
        modifier_resultat(self.calepinage, redater)
        self.assertEqual(avant, self._empreinte())

    # ── points de sauvegarde (un cas n'en contamine pas un autre) ───────
    @staticmethod
    def _savepoint():
        from django.db import transaction

        return transaction.savepoint()

    def _rollback(self, sid):
        from django.db import transaction

        transaction.savepoint_rollback(sid)
        self.calepinage.refresh_from_db()
        self.lead.refresh_from_db()
