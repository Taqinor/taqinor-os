# Avis clients (preuve sociale) — mode d'emploi

La section « Ils nous ont fait confiance » (`src/components/Testimonials.astro`)
est **livrée vide**. Tant qu'aucune donnée réelle n'est saisie, elle ne rend
**rien** publiquement : ni section, ni note, ni balisage JSON-LD.

## Règle d'intégrité (à ne jamais enfreindre)

**On n'invente jamais.** Seuls des mots de clients **réels et consentants**, et
une **note Google réelle**, vont dans ce fichier. Aucun témoignage, nom, ville,
système, date ou nombre d'étoiles fabriqué, supposé ou « rempli pour faire
bien ». En cas de doute, on laisse vide.

## Ajouter un vrai témoignage

Éditer `src/lib/testimonials.ts` et ajouter un objet `Testimonial` au tableau
`TESTIMONIALS` :

```ts
export const TESTIMONIALS: Testimonial[] = [
  {
    quote: 'Texte exact dit par le client, avec son accord.',
    name: 'Prénom N.',
    city: 'Casablanca',
    system: '5,68 kWc résidentiel',
    date: '2026-05-12', // optionnel (format AAAA-MM-JJ)
  },
];
```

Dès qu'au moins un témoignage est présent, la grille de cartes apparaît.

## Renseigner la note Google

Toujours dans `src/lib/testimonials.ts`, remplacer le `null` de `GOOGLE_RATING`
par la **vraie** note relevée sur la fiche Google de l'entreprise :

```ts
export const GOOGLE_RATING: ReviewRating | null = {
  value: 4.9, // note réelle affichée sur Google
  count: 23, // nombre réel d'avis
  url: 'https://g.page/r/votre-fiche/review', // optionnel : lien vers les avis
};
```

Dès que `GOOGLE_RATING` n'est plus `null`, le badge étoiles + lien apparaît, et
l'`AggregateRating` JSON-LD est émis.

## Demander un avis Google à un client satisfait (WhatsApp)

Message prêt à copier-coller (remplacer `[prénom]` et `[lien Google avis]`) :

> Bonjour [prénom], ravi que votre installation solaire vous donne
> satisfaction 🙏 Un avis de 10 secondes nous aiderait énormément :
> [lien Google avis]. Merci !

Une fois l'avis publié et le client d'accord pour être cité, reporter ses mots
**à l'identique** dans `TESTIMONIALS` (voir plus haut). Ne jamais reformuler au
point de changer le sens, ni citer sans consentement.
