// AMET17 — section « Parcours automatiques » de l'onglet Avancé de Paramètres.
// Les huit drapeaux société qui changent la forme d'un parcours (PA1-PA6) sont
// SERVIS par `GET /parametres/` (`drapeaux_parcours`, contrat AMET16) : aucune
// liste de drapeaux ici. Chaque bascule envoie `PATCH /parametres/update/`
// avec la seule clé ; la valeur affichée est celle relue du serveur (le profil
// du store est remplacé par la réponse) — jamais un état local divergent.
import { Card, CardContent, Badge, Switch } from '../../ui'
import { saveProfile } from '../../features/parametres/store/parametresSlice'
import { SectionTitle } from './peComponents'

export default function ParcoursAutomatiquesSection({
  profile, dispatch, lectureSeule = false, saving = false,
}) {
  const drapeaux = profile?.drapeaux_parcours ?? []
  const bascule = (cle, valeur) => dispatch(saveProfile({ [cle]: valeur }))

  return (
    <Card data-testid="parcours-automatiques">
      <CardContent className="flex flex-col gap-3">
        <SectionTitle icon={<path d="M4 12h16M12 4v16" />} label="Parcours automatiques" />
        <p className="text-[12px] text-muted-foreground">
          Ces réglages changent la forme d&apos;un parcours sans qu&apos;un écran
          ne le montre ailleurs.
          {lectureSeule && ' Lecture seule : votre rôle ne porte pas le droit « Modifier les paramètres ».'}
        </p>
        {drapeaux.length === 0 && (
          <p className="text-[12px] text-muted-foreground">Aucun réglage servi.</p>
        )}
        <ul className="flex flex-col gap-2">
          {drapeaux.map((d) => (
            <li key={d.cle} data-testid={`drapeau-${d.cle}`}
                className="flex items-start justify-between gap-3 rounded-lg border border-border px-3 py-2.5">
              <div className="flex flex-col gap-0.5">
                <span className="flex items-center gap-2 text-[13px] font-medium">
                  {d.libelle}
                  <Badge tone="outline">{d.parcours}</Badge>
                </span>
                <span className="text-[12px] text-muted-foreground">{d.effet}</span>
                <span className="text-[11px] text-muted-foreground">
                  Par défaut : {d.defaut ? 'activé' : 'désactivé'}
                </span>
              </div>
              <Switch checked={!!d.valeur}
                      disabled={lectureSeule || saving}
                      onCheckedChange={(v) => bascule(d.cle, v)}
                      aria-label={d.libelle} />
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  )
}
