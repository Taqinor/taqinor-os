"""RELANCE FOUNDATION — cadence de relance par défaut, par société.

Référentiel founder-editable (Paramètres → CRM) consommé par
``apps.crm.services.initialiser_plan_relance`` pour matérialiser un plan de
relance structuré (``apps.crm.models.RelanceEtape``) sur un lead donné. Chaque
« barreau » de la cadence est un délai en jours après le point de départ du
plan, un canal SUGGÉRÉ (appel/whatsapp/email/visite) et un libellé.

Zéro chiffre affiché au client : ce sont des DÉFAUTS DE PLANIFICATION interne
(ordonnancement de rappels), jamais une statistique de conversion ni une
preuve chiffrée présentée à qui que ce soit (règle fondateur « zéro chiffre
inventé/affiché »). Même patron que ``UniteMesure``
(``apps/parametres/models_units.py``) : ``TenantModel``, seed idempotent
additif, seedé au signup ET à la volée pour les sociétés déjà existantes.
"""
import datetime

from django.db import models

from core.models import TenantModel


class CanalRelance(models.TextChoices):
    APPEL = 'appel', 'Appel'
    WHATSAPP = 'whatsapp', 'WhatsApp'
    EMAIL = 'email', 'E-mail'
    VISITE = 'visite', 'Visite'


# Échelle NEUTRE par défaut (J+2/J+5/J+10/J+20/J+35) — un ordonnancement de
# rappels internes modifiable par société, jamais une statistique de
# conversion affichée (« modifiable » dans Paramètres → CRM).
CADENCE_RELANCE_DEFAUT = [
    {'ordre': 1, 'delai_jours': 2, 'canal': CanalRelance.APPEL,
     'libelle': 'Premier rappel'},
    {'ordre': 2, 'delai_jours': 5, 'canal': CanalRelance.WHATSAPP,
     'libelle': 'Relance WhatsApp'},
    {'ordre': 3, 'delai_jours': 10, 'canal': CanalRelance.EMAIL,
     'libelle': 'Relance e-mail'},
    {'ordre': 4, 'delai_jours': 20, 'canal': CanalRelance.APPEL,
     'libelle': "Point d'étape"},
    {'ordre': 5, 'delai_jours': 35, 'canal': CanalRelance.VISITE,
     'libelle': 'Dernière relance'},
]


class Cadence(models.TextChoices):
    """MRY4 — les trois cadences NOMMÉES du protocole de rappel, plus la
    cadence historique.

    Une seule échelle anonyme ne pouvait pas porter trois rythmes différents :
    la prise de contact (8 touches sur 14 j, la première à J0 + 3 minutes),
    le suivi après devis (J1…J14) et le réveil des dormants (J30/J60). La
    quatrième valeur, ``generique``, N'EST PAS une nouveauté : c'est le nom
    donné aux 5 barreaux neutres qui existaient déjà (J+2/5/10/20/35). Ils ne
    sont ni supprimés ni réécrits — la migration 0081 se contente de les
    étiqueter."""
    CONTACT = 'contact', 'Prise de contact'
    APRES_DEVIS = 'apres_devis', 'Après devis'
    REVEIL = 'reveil', 'Réveil'
    GENERIQUE = 'generique', 'Générique (historique)'


# ── Protocole de rappel v3 (04/09/2026) ─────────────────────────────────────
# 6 APPELS MAXIMUM + 5 WhatsApp sur 14 jours, jamais plus d'un appel ET d'un
# message par jour. Ces délais viennent du protocole validé par le fondateur —
# ils ne sont pas une estimation et ne se retouchent pas ici.
#
# ``dimanche_ok`` : la touche 8 (5ᵉ appel) est le SEUL rendez-vous autorisé le
# dimanche, entre 16 h et 19 h, pour les prospects qu'on ne trouve jamais en
# semaine. Toutes les autres touches sont recalées sur les jours ouvrés.
CADENCE_CONTACT_DEFAUT = [
    {'ordre': 1, 'delai_jours': 0, 'delai_minutes': 0, 'heure_cible': None,
     'canal': CanalRelance.WHATSAPP, 'libelle': "Message d'identité",
     'template_cle': 'identite', 'dimanche_ok': False},
    {'ordre': 2, 'delai_jours': 0, 'delai_minutes': 3, 'heure_cible': None,
     'canal': CanalRelance.APPEL, 'libelle': "Appel d'ouverture",
     'template_cle': 'appel_ouverture', 'dimanche_ok': False},
    {'ordre': 3, 'delai_jours': 0, 'delai_minutes': 150, 'heure_cible': None,
     'canal': CanalRelance.APPEL, 'libelle': 'Appel 2 (répondeur)',
     'template_cle': 'repondeur', 'dimanche_ok': False},
    {'ordre': 4, 'delai_jours': 1, 'delai_minutes': 0,
     'heure_cible': datetime.time(10, 30),
     'canal': CanalRelance.APPEL, 'libelle': 'Appel 3 (répondeur)',
     'template_cle': 'repondeur', 'dimanche_ok': False},
    {'ordre': 5, 'delai_jours': 1, 'delai_minutes': 0, 'heure_cible': None,
     'canal': CanalRelance.WHATSAPP, 'libelle': 'WhatsApp de valeur',
     'template_cle': 'valeur_j1', 'dimanche_ok': False},
    {'ordre': 6, 'delai_jours': 2, 'delai_minutes': 0,
     'heure_cible': datetime.time(18, 0),
     'canal': CanalRelance.APPEL, 'libelle': 'Appel 4',
     'template_cle': '', 'dimanche_ok': False},
    {'ordre': 7, 'delai_jours': 3, 'delai_minutes': 0, 'heure_cible': None,
     'canal': CanalRelance.WHATSAPP, 'libelle': 'Vocal',
     'template_cle': 'vocal_j3', 'dimanche_ok': False},
    {'ordre': 8, 'delai_jours': 5, 'delai_minutes': 0,
     'heure_cible': datetime.time(10, 30),
     'canal': CanalRelance.APPEL, 'libelle': 'Appel 5 (dimanche)',
     'template_cle': 'appel_dimanche', 'dimanche_ok': True},
    {'ordre': 9, 'delai_jours': 7, 'delai_minutes': 0, 'heure_cible': None,
     'canal': CanalRelance.WHATSAPP, 'libelle': '« Je classe ? »',
     'template_cle': 'je_classe_j7', 'dimanche_ok': False},
    {'ordre': 10, 'delai_jours': 10, 'delai_minutes': 0,
     'heure_cible': datetime.time(15, 0),
     'canal': CanalRelance.APPEL, 'libelle': 'Appel 6 (dernier)',
     'template_cle': '', 'dimanche_ok': False},
    {'ordre': 11, 'delai_jours': 14, 'delai_minutes': 0, 'heure_cible': None,
     'canal': CanalRelance.WHATSAPP, 'libelle': 'Clôture',
     'template_cle': 'cloture_j14', 'dimanche_ok': False},
]

# Suivi APRÈS ENVOI DU DEVIS (Guide v2.1 chapitre 7). La touche « dimanche
# famille » est posée sur le premier dimanche 16 h après J3, pour les seuls
# leads portant l'étiquette « Décision à plusieurs ».
CADENCE_APRES_DEVIS_DEFAUT = [
    {'ordre': 1, 'delai_jours': 1, 'delai_minutes': 0, 'heure_cible': None,
     'canal': CanalRelance.WHATSAPP, 'libelle': 'Le PDF s\'ouvre bien ?',
     'template_cle': 'j1_pdf', 'dimanche_ok': False},
    {'ordre': 2, 'delai_jours': 2, 'delai_minutes': 0, 'heure_cible': None,
     'canal': CanalRelance.APPEL, 'libelle': 'Appel de suivi',
     'template_cle': '', 'dimanche_ok': False},
    {'ordre': 3, 'delai_jours': 3, 'delai_minutes': 0,
     'heure_cible': datetime.time(16, 0),
     'canal': CanalRelance.WHATSAPP, 'libelle': 'Dimanche famille',
     'template_cle': 'dimanche_famille', 'dimanche_ok': True},
    {'ordre': 4, 'delai_jours': 4, 'delai_minutes': 0, 'heure_cible': None,
     'canal': CanalRelance.WHATSAPP, 'libelle': 'Preuve — chantier comparable',
     'template_cle': 'j4_preuve', 'dimanche_ok': False},
    {'ordre': 5, 'delai_jours': 6, 'delai_minutes': 0, 'heure_cible': None,
     'canal': CanalRelance.WHATSAPP, 'libelle': 'Garanties fabricants',
     'template_cle': 'j6_garanties', 'dimanche_ok': False},
    {'ordre': 6, 'delai_jours': 7, 'delai_minutes': 0, 'heure_cible': None,
     'canal': CanalRelance.APPEL, 'libelle': 'Appel de suivi',
     'template_cle': '', 'dimanche_ok': False},
    {'ordre': 7, 'delai_jours': 9, 'delai_minutes': 0, 'heure_cible': None,
     'canal': CanalRelance.WHATSAPP, 'libelle': 'Validité de la proposition',
     'template_cle': 'j9_validite', 'dimanche_ok': False},
    {'ordre': 8, 'delai_jours': 11, 'delai_minutes': 0, 'heure_cible': None,
     'canal': CanalRelance.APPEL, 'libelle': 'Appel de suivi',
     'template_cle': '', 'dimanche_ok': False},
    {'ordre': 9, 'delai_jours': 13, 'delai_minutes': 0, 'heure_cible': None,
     'canal': CanalRelance.WHATSAPP, 'libelle': 'Dernier message',
     'template_cle': 'j13_dernier', 'dimanche_ok': False},
    {'ordre': 10, 'delai_jours': 14, 'delai_minutes': 0, 'heure_cible': None,
     'canal': CanalRelance.WHATSAPP, 'libelle': 'Mise en pause',
     'template_cle': 'j14_pause', 'dimanche_ok': False},
]

# Réveil des dormants — deux touches seulement, très espacées.
CADENCE_REVEIL_DEFAUT = [
    {'ordre': 1, 'delai_jours': 30, 'delai_minutes': 0, 'heure_cible': None,
     'canal': CanalRelance.WHATSAPP, 'libelle': 'Réveil J30',
     'template_cle': 'reveil_a1', 'dimanche_ok': False},
    {'ordre': 2, 'delai_jours': 60, 'delai_minutes': 0, 'heure_cible': None,
     'canal': CanalRelance.WHATSAPP, 'libelle': 'Réveil J60',
     'template_cle': 'reveil_a2', 'dimanche_ok': False},
]

#: Cadence -> gabarit par défaut. ``generique`` garde EXACTEMENT les 5
#: barreaux historiques (aucune réécriture rétroactive).
CADENCES_DEFAUT = {
    Cadence.CONTACT: CADENCE_CONTACT_DEFAUT,
    Cadence.APRES_DEVIS: CADENCE_APRES_DEVIS_DEFAUT,
    Cadence.REVEIL: CADENCE_REVEIL_DEFAUT,
    Cadence.GENERIQUE: CADENCE_RELANCE_DEFAUT,
}


class CadenceRelanceEtape(TenantModel):
    """Un barreau (délai + canal + libellé) de la cadence de relance par
    défaut d'une société — modifiable via l'API Paramètres. Purement un
    GABARIT : ``crm.RelanceEtape`` matérialise une COPIE indépendante par
    lead au moment de l'initialisation (modifier le gabarit après coup
    n'altère jamais un plan déjà initialisé sur un lead)."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: purge tenant
        related_name='cadence_relance_etapes')
    # MRY4 — à QUELLE cadence ce barreau appartient. Défaut `contact` pour les
    # créations nouvelles ; la migration 0081 étiquette l'existant `generique`.
    cadence = models.CharField(
        max_length=20, choices=Cadence.choices, default=Cadence.CONTACT,
        verbose_name='Cadence')
    ordre = models.PositiveIntegerField(default=0)
    delai_jours = models.PositiveIntegerField(
        help_text="Nombre de jours après le point de départ du plan.")
    # MRY4 — granularité MINUTE : la 2ᵉ touche de la prise de contact tombe à
    # J0 + 3 minutes (« rappelé dans les cinq minutes »), ce qu'un délai en
    # jours ne pouvait pas exprimer.
    delai_minutes = models.PositiveIntegerField(
        default=0,
        help_text="Minutes ajoutées au délai en jours (0 à 1439).")
    # Heure locale visée (Africa/Casablanca) : quand elle est posée, elle
    # REMPLACE l'heure calculée avant le recalage sur la fenêtre d'appel.
    heure_cible = models.TimeField(
        null=True, blank=True, verbose_name='Heure cible')
    # Clé du gabarit de message (`parametres.MessageTemplate.Cle`). TEXTE
    # LIBRE volontairement : une FK créerait une dépendance d'import entre
    # deux référentiels qui n'ont pas à se connaître.
    template_cle = models.CharField(
        max_length=40, blank=True, default='',
        verbose_name='Clé du gabarit de message')
    # Seule une touche marquée ainsi peut tomber un dimanche (16 h-19 h) —
    # le rendez-vous du protocole v3 pour les prospects injoignables en
    # semaine. Toutes les autres sont recalées sur un jour ouvré.
    dimanche_ok = models.BooleanField(
        default=False, verbose_name='Autorisée le dimanche')
    canal = models.CharField(max_length=20, choices=CanalRelance.choices)
    libelle = models.CharField(max_length=150)
    actif = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Étape de cadence de relance'
        verbose_name_plural = 'Étapes de cadence de relance'
        ordering = ['cadence', 'ordre', 'delai_jours']
        # Un seul barreau par société + cadence + ordre (idempotence
        # seed/backfill). L'ordre 1 existe désormais dans CHAQUE cadence :
        # l'ancienne clé (company, ordre) les aurait fait se percuter.
        unique_together = [('company', 'cadence', 'ordre')]
        indexes = [
            models.Index(fields=['company', 'cadence', 'actif'],
                         name='param_cad_co_cad_act_idx'),
        ]

    def __str__(self):
        return (f'{self.company_id}: [{self.cadence}] J+{self.delai_jours} '
                f'{self.libelle}')

    @classmethod
    def seed_defaults(cls, company):
        """Seede la cadence NEUTRE historique (``generique``) pour ``company``.

        Signature et effet INCHANGÉS depuis RELANCE FOUNDATION : 5 barreaux
        J+2/5/10/20/35. Les trois cadences nommées passent par
        ``seed_cadence`` — mélanger les deux ferait varier en silence ce que
        cette méthode a toujours produit."""
        return cls.seed_cadence(company, Cadence.GENERIQUE)

    @classmethod
    def seed_cadence(cls, company, cadence):
        """MRY4 — seede UNE cadence nommée (idempotent, additif).

        ``get_or_create`` par (company, cadence, ordre) : rejouable sans
        doublon, ne retouche JAMAIS un barreau déjà personnalisé (le
        fondateur peut décaler un délai sans qu'un redéploiement l'écrase)."""
        crees = 0
        for entry in CADENCES_DEFAUT.get(cadence, []):
            _, created = cls.objects.get_or_create(
                company=company, cadence=cadence, ordre=entry['ordre'],
                defaults={
                    'delai_jours': entry['delai_jours'],
                    'delai_minutes': entry.get('delai_minutes', 0),
                    'heure_cible': entry.get('heure_cible'),
                    'template_cle': entry.get('template_cle', ''),
                    'dimanche_ok': entry.get('dimanche_ok', False),
                    'canal': entry['canal'],
                    'libelle': entry['libelle'],
                    'actif': True,
                })
            if created:
                crees += 1
        return crees

    @classmethod
    def cadence_pour(cls, company, cadence=Cadence.CONTACT):
        """Barreaux ACTIFS d'UNE cadence de ``company``, triés par ordre —
        seedés à la volée si cette cadence est vide (sociétés créées avant le
        référentiel : jamais un défaut codé en dur côté appelant)."""
        def _qs():
            return cls.objects.filter(
                company=company, cadence=cadence, actif=True
            ).order_by('ordre', 'delai_jours', 'delai_minutes')

        if not _qs().exists():
            cls.seed_cadence(company, cadence)
        return list(_qs())
