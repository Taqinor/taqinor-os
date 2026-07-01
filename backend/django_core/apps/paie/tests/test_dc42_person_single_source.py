"""Tests DC42 — personnes & coût horaire à source unique côté Paie.

DC42 : toute personne (salarié) référencée par la paie est un FK vers le
master employé ``rh.DossierEmploye`` (via ``ProfilPaie``), et le ``cout_horaire``
est un champ UNIQUE porté par ce master (un employé = une fiche, un taux). La
paie ne RE-STOCKE jamais l'identité de la personne (nom/prénom/CIN/matricule)
ni un ``cout_horaire`` parallèle.

Ces tests verrouillent l'invariant en lisant la définition des modèles :
* ``ProfilPaie`` est relié au master par un OneToOne → ``rh.DossierEmploye`` ;
* aucun modèle de paie ne porte un champ d'identité de personne dupliqué ;
* aucun modèle de paie ne porte un champ ``cout_horaire`` (canonique sur le
  master RH uniquement) ;
* tous les modèles « porteurs de personne » de la paie atteignent le master
  par une chaîne de FK (jamais d'identité inline).
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.paie.models import (
    AvanceSalarie,
    BulletinPaie,
    ElementVariable,
    OrdreVirement,
    PeriodePaie,
    ProfilPaie,
    RubriqueEmploye,
    SaisieArret,
)
from apps.paie.services import ensure_defaults, generer_bulletin
from apps.rh.models import DossierEmploye


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


# Champs d'identité de personne qui NE doivent jamais être re-stockés en paie
# (ils vivent sur le master ``rh.DossierEmploye``).
_IDENTITY_FIELDS = {'nom', 'prenom', 'cin', 'matricule', 'cout_horaire'}


class DC42PersonSingleSourceTests(TestCase):
    def setUp(self):
        self.co = make_company('dc42')
        ensure_defaults(self.co)

    def test_profilpaie_one_to_one_vers_master_rh(self):
        field = ProfilPaie._meta.get_field('employe')
        self.assertTrue(field.one_to_one)
        self.assertEqual(field.related_model, DossierEmploye)

    def test_cout_horaire_canonique_sur_le_master_rh(self):
        # Le master RH porte bien le coût horaire unique…
        self.assertTrue(
            any(f.name == 'cout_horaire'
                for f in DossierEmploye._meta.get_fields()))
        # …et AUCUN modèle de paie ne le re-déclare.
        for model in (ProfilPaie, RubriqueEmploye, ElementVariable,
                      BulletinPaie, AvanceSalarie, SaisieArret,
                      OrdreVirement, PeriodePaie):
            noms = {f.name for f in model._meta.get_fields()}
            self.assertNotIn(
                'cout_horaire', noms,
                f'{model.__name__} ne doit pas re-stocker cout_horaire (DC42).')

    def test_aucune_identite_personne_dupliquee_en_paie(self):
        for model in (ProfilPaie, RubriqueEmploye, ElementVariable,
                      BulletinPaie, AvanceSalarie, SaisieArret):
            # On ne regarde que les colonnes concrètes (pas les relations
            # inverses), pour repérer une identité copiée en dur.
            colonnes = {
                f.name for f in model._meta.get_fields()
                if getattr(f, 'concrete', False)
            }
            intersection = colonnes & _IDENTITY_FIELDS
            self.assertEqual(
                intersection, set(),
                f'{model.__name__} re-stocke une identité de personne '
                f'{intersection} — doit passer par le FK master (DC42).')

    def test_chaine_de_fk_atteint_le_master(self):
        """Un bulletin réel remonte jusqu'au DossierEmploye par FK (pas inline)."""
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule='Z1', nom='Master', prenom='Unique',
            cout_horaire=Decimal('45'))
        profil = ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('9000'))
        periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)
        bulletin = generer_bulletin(profil, periode)
        # bulletin → profil → employe (master) : une seule fiche, un seul taux.
        self.assertEqual(bulletin.profil.employe_id, dossier.id)
        self.assertEqual(bulletin.profil.employe.cout_horaire, Decimal('45'))
