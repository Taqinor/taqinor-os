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


# ── CAD25 (TRANCHÉ 21/09/2026) — CRÉNEAUX PAR TYPE DE TOUCHE ────────────────
#
# 7 des 11 touches de la prise de contact et 9 des 10 barreaux après devis
# n'avaient AUCUNE heure cible : leur heure était celle de l'arrivée du lead
# ou de l'envoi du devis. Un devis fini à 19 h 50 faisait tomber « le PDF
# s'ouvre bien ? » à 19 h 50 le lendemain, et tous les leads de nuit ou de
# week-end se regroupaient à l'ouverture.
#
# Décision fondateur : un créneau par TYPE de touche — les MESSAGES à 09 h 30,
# les APPELS entre 17 h 30 et 18 h 30 (on pose le milieu de la fourchette,
# 18 h 00, qui est aussi l'heure déjà retenue pour l'« Appel 4 »). Ces heures
# sont des DÉFAUTS DE SEED : l'éditeur Paramètres → CRM reste la source de
# vérité par société, et une société qui observe le Ramadan y ajuste ses
# créneaux comme le reste.
#
# DEUX FAMILLES GARDENT VOLONTAIREMENT `heure_cible: None` :
#   * les trois gestes J0 de la prise de contact (J0, J0+3 min, J0+2 h 30) —
#     ce n'est pas un créneau mais une SÉQUENCE dans la journée, celle qui
#     tient la promesse « rappelé dans les cinq minutes ». Leur imposer une
#     heure les écraserait sur la même minute, le défaut que MRY5 a corrigé ;
#   * les deux réveils J30/J60 — ils sont POSÉS sur un créneau d'étalement
#     calculé par le placement (MRY30, huit réveils par jour ouvré, 20 min
#     d'écart). Une heure imposée ferait retomber les huit sur la même minute.
# La cadence `generique` (historique, plus jamais démarrée — CAD143) n'est pas
# touchée : ses cinq barreaux restent exactement ce qu'ils ont toujours été.
#
# Garde-fou : ces heures restent BORNÉES par les fenêtres de la société
# (message dès 08:30, appel dès 09:00, fermeture 20:00) et par la fenêtre du
# Ramadan — `apps.crm.horaires.prochain_creneau_appel` recale toute heure qui
# n'y tiendrait pas.
CRENEAU_MESSAGE = datetime.time(9, 30)
#: Bornes de la fourchette d'appel décidée le 21/09/2026.
CRENEAU_APPEL_DEBUT = datetime.time(17, 30)
CRENEAU_APPEL_FIN = datetime.time(18, 30)
#: L'heure POSÉE par défaut sur un appel sans heure : le milieu de la
#: fourchette, jamais un de ses bords.
CRENEAU_APPEL = datetime.time(18, 0)


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
# message par jour — **HORS J0** : les trois gestes du jour même (message
# d'identité, appel d'ouverture, appel 2 à +2 h 30) sont VOULUS ensemble, c'est
# la promesse « rappelé dans les cinq minutes ». Ces délais viennent du
# protocole validé par le fondateur — ils ne sont pas une estimation et ne se
# retouchent pas ici.
# CAD20 (21/09/2026) — cette phrase n'est plus une intention : elle est
# EXÉCUTÉE par le moteur (`apps.crm.cadence_temps.un_geste_par_jour`, appelé
# par `calculer_echeances_cadence`). Une touche en trop sur une journée est
# décalée d'un jour ouvré ; les trois touches J0 et le rendez-vous dominical
# en sont exemptés. Un délai retouché depuis Paramètres ne peut donc plus
# empiler trois appels le même jour.
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
    # CAD67 (21/09/2026) — `repondeur` partait DEUX fois en ~20 h (ici ET à
    # l'ordre 6) : le document source (`docs/crm/messages_meryem.md`) le
    # place sur les appels 2 et 4, pas 2 et 3. `repondeur` est donc retiré
    # d'ici (script dédié `appel_relance`) et posé sur l'ordre 6 à sa place,
    # ce qui espace les deux messages répondeur de ~2 jours au lieu de ~20 h.
    {'ordre': 4, 'delai_jours': 1, 'delai_minutes': 0,
     'heure_cible': datetime.time(10, 30),
     'canal': CanalRelance.APPEL, 'libelle': 'Appel 3',
     'template_cle': 'appel_relance', 'dimanche_ok': False},
    {'ordre': 5, 'delai_jours': 1, 'delai_minutes': 0,
     'heure_cible': CRENEAU_MESSAGE,
     'canal': CanalRelance.WHATSAPP, 'libelle': 'WhatsApp de valeur',
     'template_cle': 'valeur_j1', 'dimanche_ok': False},
    {'ordre': 6, 'delai_jours': 2, 'delai_minutes': 0,
     'heure_cible': datetime.time(18, 0),
     'canal': CanalRelance.APPEL, 'libelle': 'Appel 4 (répondeur)',
     'template_cle': 'repondeur', 'dimanche_ok': False},
    {'ordre': 7, 'delai_jours': 3, 'delai_minutes': 0,
     'heure_cible': CRENEAU_MESSAGE,
     'canal': CanalRelance.WHATSAPP, 'libelle': 'Vocal',
     'template_cle': 'vocal_j3', 'dimanche_ok': False},
    {'ordre': 8, 'delai_jours': 5, 'delai_minutes': 0,
     'heure_cible': datetime.time(10, 30),
     'canal': CanalRelance.APPEL, 'libelle': 'Appel 5 (dimanche)',
     'template_cle': 'appel_dimanche', 'dimanche_ok': True},
    {'ordre': 9, 'delai_jours': 7, 'delai_minutes': 0,
     'heure_cible': CRENEAU_MESSAGE,
     'canal': CanalRelance.WHATSAPP, 'libelle': '« Je classe ? »',
     'template_cle': 'je_classe_j7', 'dimanche_ok': False},
    # CAD67 — le DERNIER appel avant clôture (celui qui décide du classement
    # du lead) n'avait aucune phrase d'ouverture : script court dédié.
    {'ordre': 10, 'delai_jours': 10, 'delai_minutes': 0,
     'heure_cible': datetime.time(15, 0),
     'canal': CanalRelance.APPEL, 'libelle': 'Appel 6 (dernier)',
     'template_cle': 'appel_dernier', 'dimanche_ok': False},
    {'ordre': 11, 'delai_jours': 14, 'delai_minutes': 0,
     'heure_cible': CRENEAU_MESSAGE,
     'canal': CanalRelance.WHATSAPP, 'libelle': 'Clôture',
     'template_cle': 'cloture_j14', 'dimanche_ok': False},
]

# Suivi APRÈS ENVOI DU DEVIS (Guide v2.1 chapitre 7). La touche « dimanche
# famille » est posée sur le premier dimanche 16 h après J3, pour les seuls
# leads portant l'étiquette « Décision à plusieurs ».
#
# CAD52 — PAS DE VARIANTE PAR SEGMENT — décision du 21/09/2026, à rouvrir sur
# les mesures de CAD87.
# `unique_together = ('company', 'cadence', 'ordre')` n'autorise qu'UNE
# cadence après-devis par société, et l'action de démarrage ne lit que le nom
# de la cadence : un rythme différent pour l'agricole ou le B2B demanderait
# donc d'ouvrir la clé, l'API, l'éditeur et le démarrage. Décision fondateur
# du 21/09/2026 : on ne le construit PAS — l'effort est gros, aucune source
# primaire sur le cycle de décision agricole n'a pu être ouverte, et rendre
# les phrases de l'écran lisibles (CAD46-CAD48) couvre le besoin ressenti.
# La question se rouvrira sur les CHIFFRES de CAD87, jamais sur une intuition.
# Cette note existe pour qu'un futur audit ne la re-soulève pas.
CADENCE_APRES_DEVIS_DEFAUT = [
    {'ordre': 1, 'delai_jours': 1, 'delai_minutes': 0,
     'heure_cible': CRENEAU_MESSAGE,
     'canal': CanalRelance.WHATSAPP, 'libelle': 'Le PDF s\'ouvre bien ?',
     'template_cle': 'j1_pdf', 'dimanche_ok': False},
    {'ordre': 2, 'delai_jours': 2, 'delai_minutes': 0,
     'heure_cible': CRENEAU_APPEL,
     'canal': CanalRelance.APPEL, 'libelle': 'Appel de suivi',
     'template_cle': '', 'dimanche_ok': False},
    {'ordre': 3, 'delai_jours': 3, 'delai_minutes': 0,
     'heure_cible': datetime.time(16, 0),
     'canal': CanalRelance.WHATSAPP, 'libelle': 'Dimanche famille',
     'template_cle': 'dimanche_famille', 'dimanche_ok': True},
    {'ordre': 4, 'delai_jours': 4, 'delai_minutes': 0,
     'heure_cible': CRENEAU_MESSAGE,
     'canal': CanalRelance.WHATSAPP, 'libelle': 'Preuve — chantier comparable',
     'template_cle': 'j4_preuve', 'dimanche_ok': False},
    {'ordre': 5, 'delai_jours': 6, 'delai_minutes': 0,
     'heure_cible': CRENEAU_MESSAGE,
     'canal': CanalRelance.WHATSAPP, 'libelle': 'Garanties fabricants',
     'template_cle': 'j6_garanties', 'dimanche_ok': False},
    {'ordre': 6, 'delai_jours': 7, 'delai_minutes': 0,
     'heure_cible': CRENEAU_APPEL,
     'canal': CanalRelance.APPEL, 'libelle': 'Appel de suivi',
     'template_cle': '', 'dimanche_ok': False},
    {'ordre': 7, 'delai_jours': 9, 'delai_minutes': 0,
     'heure_cible': CRENEAU_MESSAGE,
     'canal': CanalRelance.WHATSAPP, 'libelle': 'Validité de la proposition',
     'template_cle': 'j9_validite', 'dimanche_ok': False},
    {'ordre': 8, 'delai_jours': 11, 'delai_minutes': 0,
     'heure_cible': CRENEAU_APPEL,
     'canal': CanalRelance.APPEL, 'libelle': 'Appel de suivi',
     'template_cle': '', 'dimanche_ok': False},
    {'ordre': 9, 'delai_jours': 13, 'delai_minutes': 0,
     'heure_cible': CRENEAU_MESSAGE,
     'canal': CanalRelance.WHATSAPP, 'libelle': 'Dernier message',
     'template_cle': 'j13_dernier', 'dimanche_ok': False},
    {'ordre': 10, 'delai_jours': 14, 'delai_minutes': 0,
     'heure_cible': CRENEAU_MESSAGE,
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
