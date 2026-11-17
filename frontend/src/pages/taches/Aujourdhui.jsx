import CoquilleTaches from '../../features/taches/coquille/CoquilleTaches'

/* TCH43 — page vide « Aujourd'hui » (route /taches/aujourdhui, `/taches` y mène), montée
   dans la coquille. Le jour est celui de l'appareil : « Vendredi 20 novembre ». */
const jourLong = () => {
  const texte = new Intl.DateTimeFormat('fr-FR', { weekday: 'long', day: 'numeric', month: 'long' }).format(new Date())
  return texte.charAt(0).toUpperCase() + texte.slice(1)
}

export default function Aujourdhui() {
  return <CoquilleTaches ecran="aujourdhui" titre="Aujourd'hui" sousTitre={jourLong()} />
}
