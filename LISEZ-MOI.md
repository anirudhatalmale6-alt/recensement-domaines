# Restructurer les domaines — d'abord les recenser

Une restructuration de parc se decide sur des faits : quel domaine sert
quoi, lesquels partagent une base, lesquels ne servent plus rien. Ce dossier
contient les deux moitiés de ce recensement.

```
domaines.php        a deposer sur l'hebergement, LECTURE SEULE
tests-domaines.py   34 controles sur un faux compte
apercu.py           captures d'ecran sur un faux compte
sonde.py            le recensement vu de DEHORS (DNS, HTTP, certificats)
parc.json           ce que la sonde a mesure
```

---

## 1. Ce que j'ai deja pu mesurer, de dehors

Mesure du **28 aout 2026, 01h30**. Un domaine se mesure de l'exterieur sans
aucun acces : DNS, redirections, certificat, contenu servi.

### Deux domaines sont expires

| Domaine | Ce que repond le serveur |
|---|---|
| `8bible.com` | page « **Your domain is expired** » (IP 2.57.91.92) |
| `busfar.com` | page « **Your domain is expired** » (IP 2.57.91.92) |

C'est la page d'atterrissage des domaines expires chez Hostinger. 8bible est
un site qu'on a restaure : les fichiers peuvent etre intacts sur le compte,
le **nom**, lui, n'est plus a toi tant qu'il n'est pas renouvele. C'est le
seul point de cette liste qui a une horloge dessus.

### Treize domaines n'ont plus aucun DNS

`ciryus.com`, `datasial.com`, `evorentalcar.com`, `fuzauto.com`,
`happyviewinn.com`, `hyecom.net`, `mtlagency.ca`, `myelectronic.co`,
`rrently.com`, `shaynababe.fr`, `simpliloans.ca`, `stayelectronic.com`,
`thesimrock.com`.

Aucun enregistrement A ne repond. Ils figuraient tous dans l'inventaire des
sauvegardes. Deux lectures possibles, et je ne peux pas trancher de dehors :
soit le nom n'est plus enregistre, soit il l'est encore mais ne pointe plus
nulle part. La difference se lit dans ton hPanel, pas depuis Internet.

### Un domaine gare, un en construction

- `laparusia.com` → « Parked Domain name on Hostinger DNS system ». Le nom
  existe, il n'est branche sur aucun site.
- `caucasusauto.com` → page « bientot disponible », et il est servi par
  **Vercel**, pas par Hostinger. Il n'est donc pas sur le compte a
  restructurer.

### Sept domaines servent un vrai site

`ops-store.com`, `ops-store.fr`, `saintdb.com`, `skyaccess.com`,
`unicornlabs.ca`, `angelicpedia.com`, `firstsupercarrental.com`.

### Treize domaines : NON MESURES

`steyli.com`, `influus.com`, `8funder.com`, `8secur.com`, `exportrev.com`,
`internsli.com`, `leapollo.com`, `renosly.com`, `azrunthur.com`,
`elitfly.com`, `dubairev.fr`, `hakimadjaoudi.com`, `tidjara.dz`.

Ton hebergeur m'a renvoye **HTTP 429 — trop de requetes** sur chacun, meme
en sondant un domaine toutes les deux secondes et demie avec quatre reprises
espacees. Corps vide, zero octet.

**Je n'en tire donc aucune conclusion.** C'est important : au premier
passage, mon classement lisait ces reponses vides comme « page seule, aucun
lien interne » et m'aurait fait ecrire que steyli.com, influus.com et
renosly.com sont des coquilles vides. Ils ne le sont pas — c'etait ma sonde
qui se faisait rejeter. Une reponse qu'on n'a pas obtenue ne se classe pas ;
elle s'annonce comme non mesuree.

C'est aussi pour ca que la suite ne peut pas se faire de dehors.

---

## 2. `domaines.php` — le recensement vu de l'interieur

Meme principe que `menage.php` : un seul fichier a deposer par le
gestionnaire de fichiers hPanel, a ouvrir dans le navigateur.

**Ce fichier ne modifie rien.** Il ne contient aucune fonction d'ecriture :
ni `unlink`, ni `rmdir`, ni `rename`, ni `file_put_contents`, ni `fwrite`,
ni `mkdir`, ni `chmod`. Un controle le verifie dans le code source, et un
autre compare l'empreinte MD5 des 24 fichiers d'un faux compte avant et
apres execution.

### En trois etapes

1. **Change la cle**, ligne 24 :

   ```php
   $CLE = 'change-cette-cle-avant-de-televerser';
   ```

   Sans cle valide, la page repond `403` nu — ni chemin, ni version, ni
   liste. Un inventaire des domaines d'un compte laisse en ligne sans cle,
   c'est le plan du serveur offert au premier venu.

2. **Depose le fichier** dans le `public_html` de n'importe quel domaine :

   ```
   https://<le-domaine>/domaines.php?cle=TA-CLE
   ```

   Il remonte a la racine du **compte** — donc tous les domaines d'un coup,
   pas seulement celui ou il est pose.

3. **Copie le bloc « A me renvoyer »** en bas de page et colle-le dans le
   fil. C'est exactement ce qu'il me faut pour proposer la restructuration.

### Ce qu'il rapporte, domaine par domaine

- le chemin reel du docroot, le poids et le nombre de fichiers ;
- WordPress ou non, et **la version lue dans `wp-includes/version.php`** —
  la vraie version installee, pas celle des `?ver=` d'une page en cache, qui
  ment (c'est exactement ce qui s'est passe sur 8funder) ;
- le nombre d'extensions et de themes ;
- le **nom de la base de donnees** ;
- la date de derniere modification ;
- les signes qu'un domaine repond sans etre un site : demo de theme, lorem
  ipsum, page « bientot disponible », index quasi vide, aucun index ;
- les extensions qui **ferment** le site (`coming-soon`,
  `under-construction-page`, `wp-maintenance-mode`…) — un site peut etre
  parfaitement installe et rester invisible a cause d'une seule d'entre
  elles, et ca ne se voit pas de dehors ;
- un **second WordPress dans un sous-dossier** du docroot : la cause
  classique du « j'ai deux sites et je ne sais plus lequel tourne » ;
- et, en rouge en haut, **les domaines qui partagent une base de donnees**.
  Deux domaines sur la meme base, c'est soit une copie, soit deux sites qui
  ecrivent l'un sur l'autre sans le savoir. C'est toujours la premiere chose
  a trancher dans une restructuration.

### Ce qu'il ne fait pas

Il ne lit **aucun mot de passe**. La seule valeur extraite d'un
`wp-config.php` est `DB_NAME`, parce que c'est la question posee. Ni
`DB_USER` ni `DB_PASSWORD` ne sont lus, et un controle place un mot de passe
temoin dans le faux `wp-config.php` puis verifie qu'il n'apparait nulle
part — ni dans la page, ni dans le bloc JSON a me renvoyer.

Il ne suit pas les liens symboliques et ne sort pas du compte :
`?racine=/etc` est ignore, pas suivi.

L'analyse a un budget de temps (40 s par defaut, borne 5..240). S'il tombe,
la page l'ecrit **en rouge** au lieu de faire croire qu'elle a tout vu.
Relance alors avec `&budget=180`.

### Quand c'est fini

Supprime `domaines.php` du serveur. Un inventaire des domaines d'un compte
n'a rien a faire en ligne une fois lu, meme derriere une cle.

---

## Verification

```
php -l domaines.php
python3 tests-domaines.py     34 controles, tous verts
python3 apercu.py             captures sur un faux compte
python3 sonde.py              re-mesure le parc de dehors
```

Les controles tournent sur un faux compte de six domaines reconstruit dans
un dossier temporaire a chaque execution — jamais sur un vrai hebergement.
On ne teste pas un outil dont la promesse est « je ne modifie rien » sur ce
qu'il est cense ne pas modifier.

Ceux qui portent le plus :

- **empreinte MD5 identique** pour les 24 fichiers avant et apres ;
- le mot de passe temoin du `wp-config.php` **n'apparait nulle part**,
  alors que le nom de base, lui, est bien lu ;
- deux domaines sur la meme base sont signales, et un domaine seul sur la
  sienne ne l'est **pas** ;
- le second WordPress dans `/ancien/` est trouve, sans faux positif sur les
  cinq autres domaines ;
- un site ferme par extension n'est **pas** presente comme servant un site ;
- `?racine=/etc` ignore, lien symbolique vers `/etc` non suivi ;
- la racine retenue est celle du **compte**, pas celle du domaine ou le
  fichier est pose.
