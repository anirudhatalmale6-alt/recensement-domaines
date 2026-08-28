# -*- coding: utf-8 -*-
"""Controles sur domaines.php, sur un FAUX compte reconstruit a chaque
execution dans un dossier temporaire.

On ne teste jamais un outil de lecture sur un vrai hebergement, et surtout
pas un outil dont la promesse principale est « je ne modifie rien » : la
seule facon de le prouver est de comparer l'empreinte de chaque fichier
avant et apres, ce qui suppose un compte qu'on peut se permettre de perdre.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

ICI = os.path.dirname(os.path.abspath(__file__))
TEMOIN = 'MOT-DE-PASSE-TEMOIN-NE-DOIT-JAMAIS-SORTIR'
CLE = 'change-cette-cle-avant-de-televerser'
OK = []


def t(nom, cond, detail=''):
    OK.append(bool(cond))
    print('%s %s%s' % ('  OK  ' if cond else ' ECHEC', nom,
                       ('   -> ' + str(detail)) if not cond and detail else ''))


WP_CONFIG = ("<?php\ndefine('DB_NAME','%s');\n"
             "define('DB_USER','u640_utilisateur');\n"
             "define('DB_PASSWORD','" + TEMOIN + "');\n")

VERSION = "<?php\n$wp_version = '%s';\n"

FIXTURE = {
    # site A : WordPress normal, en service
    'domains/site-a.com/public_html/index.php': '<?php // wp\n',
    'domains/site-a.com/public_html/wp-config.php': WP_CONFIG % 'base_a',
    'domains/site-a.com/public_html/wp-includes/version.php': VERSION % '6.5.2',
    'domains/site-a.com/public_html/wp-content/themes/astra/style.css': 'a' * 400,
    'domains/site-a.com/public_html/wp-content/themes/astra-child/style.css': 'b' * 200,
    'domains/site-a.com/public_html/wp-content/plugins/woocommerce/woo.php': 'c' * 900,
    'domains/site-a.com/public_html/wp-content/plugins/yoast/y.php': 'd' * 300,
    'domains/site-a.com/public_html/wp-content/uploads/2024/photo.jpg': 'e' * 5000,

    # site B : MEME base que A -> c'est une copie, et c'est LE signal
    'domains/site-b.net/public_html/index.php': '<?php // wp\n',
    'domains/site-b.net/public_html/wp-config.php': WP_CONFIG % 'base_a',
    'domains/site-b.net/public_html/wp-includes/version.php': VERSION % '5.9.1',
    'domains/site-b.net/public_html/wp-content/plugins/coming-soon/cs.php': 'f' * 100,

    # site C : installe, mais ferme par une extension « bientot disponible »
    'domains/site-c.org/public_html/index.php':
        '<html>Arolax demo template</html>',
    'domains/site-c.org/public_html/wp-config.php': WP_CONFIG % 'base_c',
    'domains/site-c.org/public_html/wp-includes/version.php': VERSION % '6.4.0',
    'domains/site-c.org/public_html/wp-content/plugins/'
    'under-construction-page/ucp.php': 'g' * 120,

    # site D : un SECOND WordPress dans un sous-dossier
    'domains/site-d.ca/public_html/index.php': '<?php // wp\n',
    'domains/site-d.ca/public_html/wp-config.php': WP_CONFIG % 'base_d',
    'domains/site-d.ca/public_html/wp-includes/version.php': VERSION % '6.6.1',
    'domains/site-d.ca/public_html/ancien/wp-config.php': WP_CONFIG % 'base_d_old',
    'domains/site-d.ca/public_html/ancien/index.php': '<?php // vieux\n',

    # site E : domaine gare, aucun index
    'domains/site-e.fr/public_html/.htaccess': '# rien\n',

    # site F : pas de WordPress du tout, un site statique
    'domains/site-f.io/public_html/index.html': '<html>Bonjour</html>' + 'h' * 900,
}


def batir():
    base = tempfile.mkdtemp(prefix='domaines-test-')
    for rel, contenu in FIXTURE.items():
        p = os.path.join(base, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'w') as f:
            f.write(contenu)
    shutil.copy(os.path.join(ICI, 'domaines.php'),
                os.path.join(base, 'domains/site-a.com/public_html/domaines.php'))
    return base


def empreinte(base):
    """Chemin -> (taille, md5) pour chaque fichier du faux compte."""
    out = {}
    for rac, _, fs in os.walk(base):
        for n in fs:
            p = os.path.join(rac, n)
            with open(p, 'rb') as f:
                d = f.read()
            out[os.path.relpath(p, base)] = (len(d), hashlib.md5(d).hexdigest())
    return out


def lancer(base, params):
    doc = os.path.join(base, 'domains/site-a.com/public_html')
    r = subprocess.run(
        ['php', os.path.join(ICI, 'runner.php'), json.dumps(params), doc],
        capture_output=True, text=True, cwd=doc)
    return r.stdout + r.stderr


def json_de(html):
    m = re.search(r'<textarea[^>]*>(.*?)</textarea>', html, re.S)
    if not m:
        return None
    import html as H
    return json.loads(H.unescape(m.group(1)))


base = batir()
avant = empreinte(base)
sortie = lancer(base, {'cle': CLE, 'budget': 60})
apres = empreinte(base)
J = json_de(sortie)

print('\n--- ce fichier ne modifie rien ---')

t('aucun fichier ajoute, supprime ou renomme (%d avant, %d apres)'
  % (len(avant), len(apres)), set(avant) == set(apres),
  sorted(set(avant) ^ set(apres))[:5])
modifies = [p for p in avant if p in apres and avant[p] != apres[p]]
t('aucun fichier modifie : meme taille et meme empreinte pour les %d'
  % len(avant), not modifies, modifies[:5])

src = open(os.path.join(ICI, 'domaines.php')).read()
ecrit = [f for f in ('unlink(', 'rmdir(', 'rename(', 'file_put_contents(',
                     'fwrite(', 'mkdir(', 'copy(', 'chmod(', 'touch(')
         if f in src]
t('le code source ne contient aucune fonction d\'ecriture', not ecrit, ecrit)

print('\n--- aucun secret ne sort ---')

t('le mot de passe temoin du wp-config n\'apparait pas dans la page',
  TEMOIN not in sortie)
t('l\'utilisateur de base de donnees n\'apparait pas non plus',
  'u640_utilisateur' not in sortie)
t('le nom de base, lui, est bien lu (c\'est la question posee)',
  'base_a' in sortie and 'base_c' in sortie)
t('le JSON a renvoyer ne contient pas le mot de passe',
  TEMOIN not in json.dumps(J))

print('\n--- sans cle, rien ---')

nu = lancer(base, {})
t('sans cle : la page ne repond que 403', nu.strip() == '403', nu[:80])
t('sans cle : aucun chemin n\'est revele', base not in nu)
mauvaise = lancer(base, {'cle': 'presque-la-bonne-cle'})
t('mauvaise cle : meme reponse nue', mauvaise.strip() == '403')

print('\n--- le recensement dit vrai ---')

noms = {d['domaine'] for d in J['domaines']}
t('les six domaines du faux compte sont recenses',
  {'site-a.com', 'site-b.net', 'site-c.org', 'site-d.ca', 'site-e.fr',
   'site-f.io'} <= noms, sorted(noms))

par = {d['domaine']: d for d in J['domaines']}

t('la version de WordPress est lue dans wp-includes/version.php',
  par['site-a.com']['version'] == '6.5.2'
  and par['site-d.ca']['version'] == '6.6.1',
  (par['site-a.com']['version'], par['site-d.ca']['version']))
t('un site sans WordPress est signale comme tel',
  par['site-f.io']['wordpress'] is False and par['site-f.io']['version'] is None)
t('les extensions et les themes sont comptes',
  par['site-a.com']['extensions'] == 2 and len(par['site-a.com']['themes']) == 2,
  (par['site-a.com']['extensions'], par['site-a.com']['themes']))

# Le poids doit etre un vrai poids : on le compare a ce qu'on a ecrit.
attendu = sum(len(c) for rel, c in FIXTURE.items()
              if rel.startswith('domains/site-a.com/'))
mesure = par['site-a.com']['octets']
t('le poids mesure correspond aux octets reellement ecrits (%d)' % attendu,
  mesure >= attendu, '%d mesure pour %d ecrits' % (mesure, attendu))
t('un domaine sans contenu ne pese pas comme un site',
  par['site-e.fr']['octets'] < par['site-a.com']['octets'])

print('\n--- ce qu\'une restructuration doit voir ---')

t('deux domaines sur la meme base sont signales',
  'base_a' in J['bases_partagees']
  and set(J['bases_partagees']['base_a']) == {'site-a.com', 'site-b.net'},
  J['bases_partagees'])
t('un domaine seul sur sa base n\'est PAS signale comme partage',
  'base_c' not in J['bases_partagees'] and 'base_d' not in J['bases_partagees'],
  list(J['bases_partagees']))
t('le second WordPress dans un sous-dossier est trouve',
  par['site-d.ca']['secondaire'] == ['ancien'],
  par['site-d.ca']['secondaire'])
t('aucun faux positif de second WordPress sur les autres domaines',
  all(not par[n]['secondaire'] for n in noms if n != 'site-d.ca'),
  {n: par[n]['secondaire'] for n in noms if par[n]['secondaire']})
t('une extension qui ferme le site est nommee',
  par['site-c.org']['fermeture'] == ['under-construction-page']
  and par['site-b.net']['fermeture'] == ['coming-soon'],
  (par['site-c.org']['fermeture'], par['site-b.net']['fermeture']))
t('un site ferme par extension n\'est PAS presente comme servant un site',
  'sert un site' not in
  re.search(r'site-c\.org.*?</tr>', sortie, re.S).group(0))
t('la demo du theme est reconnue',
  'demo du theme Arolax' in par['site-c.org']['vide'],
  par['site-c.org']['vide'])
t('un domaine sans index est signale comme ne servant rien',
  any('aucun index' in v for v in par['site-e.fr']['vide']),
  par['site-e.fr']['vide'])
t('un vrai site n\'herite d\'aucun signe de vide',
  not par['site-a.com']['vide'], par['site-a.com']['vide'])

print('\n--- on ne sort pas du compte ---')

dehors = lancer(base, {'cle': CLE, 'racine': '/etc'})
Jd = json_de(dehors)
t('?racine=/etc est ignore, pas suivi',
  Jd and Jd['racine'].startswith(base), Jd['racine'] if Jd else None)
t('aucun chemin systeme n\'apparait dans la sortie',
  '/etc/passwd' not in dehors and '/etc/shadow' not in dehors)

# Un lien symbolique qui pointe hors du compte ne doit pas etre suivi.
lien = os.path.join(base, 'domains/site-f.io/public_html/echappe')
os.symlink('/etc', lien)
avant2 = empreinte(base)
s2 = lancer(base, {'cle': CLE, 'budget': 30})
t('un lien symbolique vers /etc n\'est pas suivi',
  'root:x:' not in s2 and '/etc/passwd' not in s2)
t('la presence d\'un lien ne fait rien modifier non plus',
  empreinte(base) == avant2)
os.unlink(lien)

print('\n--- une analyse partielle se dit partielle ---')

court = lancer(base, {'cle': CLE, 'budget': 5})
Jc = json_de(court)
t('le drapeau « tronque » existe et vaut un booleen',
  Jc is not None and isinstance(Jc['tronque'], bool))
t('quand l\'analyse est tronquee, la page l\'ecrit en rouge',
  (not Jc['tronque']) or 'Analyse incomplete' in court)
t('le budget est borne (5..240), une valeur absurde ne passe pas',
  'budget = 999999' not in src and '$BUDGET > 240' in src)

print('\n--- la racine du COMPTE, pas celle d\'un domaine ---')

t('le scan remonte au compte : il voit les 6 domaines depuis le docroot de A',
  len(J['domaines']) >= 6, len(J['domaines']))
t('la racine retenue est bien la racine du compte',
  os.path.realpath(J['racine']) == os.path.realpath(base),
  (J['racine'], base))

shutil.rmtree(base, ignore_errors=True)
print('\n%d controles, %d verts, %d rouges'
      % (len(OK), sum(OK), len(OK) - sum(OK)))
sys.exit(0 if all(OK) else 1)
