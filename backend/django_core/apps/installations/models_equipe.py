"""
DC40 — Modèle d'ÉQUIPE terrain CANONIQUE (décision fondateur).

Avant DC40, la notion d'« équipe terrain » était définie de TROIS façons
ad-hoc, une par feature :
  * FG169 (roster, ``apps.rh.AffectationRoster.equipe``) : un simple libellé
    texte (``CharField``) — « Équipe Nord », « Pose A »… ;
  * FG299 (plan de charge, sélecteur ``plan_de_charge_equipes``) : l'équipe
    dérivée AD-HOC du M2M ``Intervention.equipe`` (→ User) + ``technicien`` ;
  * FG303 (planning camionnettes) : dérivée des interventions portant une
    ``camionnette``.

Le fondateur a TRANCHÉ (DECISION) : introduire UN seul modèle d'équipe
CANONIQUE — ``Equipe`` ci-dessous — dont les MEMBRES sont un M2M vers
``settings.AUTH_USER_MODEL`` (les utilisateurs/techniciens), réutilisé par
roster / plan de charge / planning camionnette. Une seule DÉFINITION d'équipe,
pas une par feature.

À NE PAS CONFONDRE avec ``apps.gestion_projet.Equipe`` : celle-là est une
équipe de RESSOURCES DE PROJET (membres = ``RessourceProfil``, pas des
utilisateurs) — une couche distincte du terrain. Les deux ne fusionnent pas :
les membres n'ont pas le même type (User vs RessourceProfil).

Approche ADDITIVE & RÉVERSIBLE (jamais destructive) :
  * on AJOUTE la table ``Equipe`` + son M2M ``membres`` ;
  * on AJOUTE une FK NULLABLE ``Intervention.equipe_ref`` → ``Equipe`` (l'ancien
    M2M ``Intervention.equipe`` reste intact — rien ne casse, les sélecteurs
    existants continuent de fonctionner) ; les membres d'une intervention se
    résolvent via l'équipe canonique quand ``equipe_ref`` est posée, sinon via
    le M2M ad-hoc historique (voir ``selectors.membres_intervention``) ;
  * une migration de DONNÉES rétro-remplit une ``Equipe`` canonique par équipe
    distincte trouvée sur les interventions existantes, et repointe
    ``equipe_ref`` — avec un ``RunPython`` REVERSE réel qui défait le
    rétro-remplissage.

Multi-tenant : ``company`` est posée côté serveur (jamais lue du corps).
Couche INDÉPENDANTE des trois couches de statuts de l'OS (entonnoir STAGES.py,
statut document ventes, statut chantier) : une équipe ne porte AUCUN statut.
"""
from django.conf import settings
from django.db import models


class Equipe(models.Model):
    """DC40 — équipe terrain CANONIQUE (membres = utilisateurs).

    UNE seule définition d'équipe, réutilisée par le roster (FG169), le plan de
    charge (FG299) et le planning camionnette (FG303). Les ``membres`` sont un
    M2M vers les utilisateurs ; un ``chef`` optionnel désigne le responsable
    d'équipe. ``actif`` permet d'archiver une équipe sans la supprimer.

    Multi-tenant : ``company`` posée côté serveur. Nom unique par société."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='installations_equipes')
    nom = models.CharField(max_length=120)
    # Membres de l'équipe — les utilisateurs (techniciens) qui la composent.
    membres = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True,
        related_name='installations_equipes')
    # Chef/responsable d'équipe (optionnel) — un des utilisateurs.
    chef = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='installations_equipes_chef')
    actif = models.BooleanField(default=True)
    description = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='installations_equipes_creees')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Équipe terrain'
        verbose_name_plural = 'Équipes terrain'
        ordering = ['nom']
        # Une équipe est unique par (société, nom).
        unique_together = [('company', 'nom')]
        indexes = [
            models.Index(fields=['company', 'actif'],
                         name='idx_equipe_co_actif'),
        ]

    def __str__(self):
        return self.nom
