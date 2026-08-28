# -*- coding: utf-8 -*-
"""Sonde le parc de domaines depuis l'exterieur, en HTTP.

Le SSH du compte repond 403 et le FTP est enferme dans un seul public_html.
Je ne peux donc pas lire l'hebergement. Mais un domaine, ca se mesure de
dehors : DNS, redirections, certificat, generateur, theme, version, noindex.

Regle tenue partout ici : ce fichier n'ecrit QUE ce qu'il a mesure. Toute
case qu'il n'a pas pu mesurer vaut None et s'affiche « non mesure », jamais
une valeur plausible. Un parc de 30 domaines se restructure sur des faits ;
une seule ligne inventee et c'est un domaine coupe pour rien.

Le cache LiteSpeed de cet hebergement sert des pages perimees : chaque URL
part avec un parametre unique (?nocache=...) pour forcer une vraie reponse.
"""

import json
import os
import random
import re
import socket
import ssl
import time
import datetime

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ICI = os.path.dirname(os.path.abspath(__file__))
UA = ('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) '
      'Chrome/124.0 Safari/537.36')

# Le parc connu, reconstitue depuis les sauvegardes de mai et depuis tout ce
# qui est passe dans le fil depuis. La sonde dit elle-meme lesquels repondent.
DOMAINES = [
    'steyli.com', 'influus.com', '8funder.com', '8bible.com', '8secur.com',
    'exportrev.com', 'internsli.com', 'leapollo.com', 'renosly.com',
    'azrunthur.com', 'elitfly.com', 'laparusia.com', 'hakimadjaoudi.com',
    'mtlagency.ca', 'dubairev.fr', 'evorentalcar.com', 'fuzauto.com',
    'ciryus.com', 'happyviewinn.com', 'datasial.com', 'myelectronic.co',
    'shaynababe.fr', 'simpliloans.ca', 'stayelectronic.com', 'revmetal.com',
    'thesimrock.com', 'unicornlabs.ca', 'edenflor.com', 'hyecom.net',
    'rrently.com', 'busfar.com', 'ops-store.com', 'ops-store.fr',
    'saintdb.com', 'angelicpedia.com', 'skyaccess.com', 'tidjara.dz',
    'firstsupercarrental.com', 'caucasusauto.com',
]

# Signatures de pages « vides » : ce qui repond 200 sans etre un site.
VIDES = [
    (re.compile(r'arolax', re.I), 'demo du theme Arolax'),
    (re.compile(r'just another wordpress site', re.I), 'accroche WordPress par defaut'),
    (re.compile(r'(coming soon|bient(o|ô)t disponible|under construction|'
                r'site en construction|maintenance mode)', re.I), 'page « bientot disponible »'),
    (re.compile(r'(domain (is )?for sale|parked (free )?courtesy|'
                r'buy this domain|acheter ce domaine)', re.I), 'page de parking de domaine'),
    (re.compile(r'hello world', re.I), 'article « Hello world » jamais efface'),
    (re.compile(r'lorem ipsum', re.I), 'texte lorem ipsum du theme'),
    (re.compile(r'index of /', re.I), 'listing de repertoire'),
]


def maintenant():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M')


def resoudre(nom):
    """Adresses IP du domaine, ou None si le DNS ne repond pas."""
    try:
        infos = socket.getaddrinfo(nom, None, socket.AF_INET)
        return sorted({i[4][0] for i in infos})
    except Exception:
        return None


def certificat(nom):
    """Emetteur et date de fin du certificat, mesures sur la vraie poignee
    de main. Un « cadenas vert » suppose n'est pas un certificat valide."""
    ctx = ssl.create_default_context()
    try:
        with socket.create_connection((nom, 443), timeout=8) as brut:
            with ctx.wrap_socket(brut, server_hostname=nom) as tls:
                c = tls.getpeercert()
        fin = c.get('notAfter')
        d = datetime.datetime.strptime(fin, '%b %d %H:%M:%S %Y %Z') if fin else None
        em = dict(x[0] for x in c.get('issuer', ()))
        return {
            'valide': True,
            'emetteur': em.get('organizationName') or em.get('commonName'),
            'expire_le': d.strftime('%Y-%m-%d') if d else None,
            'jours_restants': (d - datetime.datetime.utcnow()).days if d else None,
        }
    except ssl.SSLCertVerificationError as e:
        return {'valide': False, 'erreur': str(e.verify_message or e)[:120]}
    except Exception as e:
        return {'valide': False, 'erreur': type(e).__name__}


def version_wp(html, base):
    """Version WordPress lue dans les ?ver= des assets du coeur.

    On ne lit PAS le meta generator seul : beaucoup de sites le retirent, et
    quand il est present il ment aussi souvent qu'il dit vrai. Les ?ver= des
    fichiers de /wp-includes/ suivent la version reellement installee.
    """
    vers = re.findall(r'/wp-includes/[^"\']+\?ver=([0-9]+\.[0-9]+(?:\.[0-9]+)?)', html)
    if vers:
        return max(set(vers), key=vers.count)
    g = re.search(r'name="generator" content="WordPress ([0-9.]+)"', html)
    return g.group(1) if g else None


def themes(html):
    return sorted(set(re.findall(r'/wp-content/themes/([a-z0-9_\-]+)/', html, re.I)))


def sonder(nom):
    fiche = {'domaine': nom, 'mesure_le': maintenant()}
    fiche['ip'] = resoudre(nom)
    if not fiche['ip']:
        fiche['etat'] = 'DNS muet'
        return fiche

    fiche['tls'] = certificat(nom)

    s = requests.Session()
    s.headers['User-Agent'] = UA
    s.max_redirects = 10
    url = 'https://%s/?nocache=%d' % (nom, random.randrange(999983))

    # La quasi-totalite du parc est sur les MEMES adresses IP. Huit sondes en
    # parallele s'y sont fait renvoyer un 429 « Too Many Requests », corps
    # vide — et le classement, lui, a bien voulu conclure « page seule, aucun
    # lien interne » sur des sites parfaitement vivants. On y va donc en
    # serie, avec une pause, et on reessaie quand l'hebergeur dit d'attendre.
    r = None
    for essai in range(4):
        try:
            r = s.get(url, timeout=30, allow_redirects=True, verify=False)
        except Exception as e:
            fiche['etat'] = 'injoignable en HTTPS'
            fiche['erreur'] = type(e).__name__
            return fiche
        if r.status_code not in (429, 503):
            break
        fiche.setdefault('reessais', 0)
        fiche['reessais'] += 1
        time.sleep(6 * (essai + 1))

    fiche['code'] = r.status_code
    fiche['url_finale'] = re.sub(r'[?&]nocache=\d+', '', r.url)
    fiche['redirections'] = [re.sub(r'[?&]nocache=\d+', '', h.url) for h in r.history]
    fiche['octets'] = len(r.content)
    fiche['serveur'] = r.headers.get('server')
    fiche['cache'] = r.headers.get('x-litespeed-cache') or r.headers.get('x-cache')

    html = r.text
    t = re.search(r'<title[^>]*>(.*?)</title>', html, re.S | re.I)
    fiche['titre'] = re.sub(r'\s+', ' ', t.group(1)).strip()[:120] if t else None
    fiche['wordpress'] = '/wp-content/' in html or '/wp-includes/' in html
    fiche['version_wp'] = version_wp(html, nom) if fiche['wordpress'] else None
    fiche['themes'] = themes(html)
    fiche['noindex'] = bool(re.search(r'<meta[^>]+name=["\']robots["\'][^>]+noindex', html, re.I))
    fiche['langue'] = (re.search(r'<html[^>]+lang=["\']([a-zA-Z\-]+)', html) or [None, None])[1]

    fiche['signes_vide'] = [quoi for rx, quoi in VIDES if rx.search(html)]

    # Le nombre de liens internes distincts separe un vrai site d'une page
    # unique : une page de parking en a zero, un theme demo en a beaucoup
    # mais qui ne mene nulle part. On compte, on ne devine pas.
    #
    # On compte sur l'hote REELLEMENT servi, pas sur le nom demande : la
    # plupart de ces sites redirigent vers www., et leurs liens sont ecrits
    # en absolu. Une regle batie sur « nom » seul ne voyait aucun lien et
    # faisait passer un site complet pour une page isolee.
    hote = re.sub(r'^https?://([^/]+).*', r'\1', fiche['url_finale'])
    hotes = {hote, hote[4:] if hote.startswith('www.') else 'www.' + hote}
    motif = r'href=["\'](?:https?://(?:%s))?(/[^"\'#?]*)' % '|'.join(
        re.escape(h) for h in hotes)
    fiche['liens_internes'] = len(set(re.findall(motif, html)))

    # Le sitemap dit combien de pages le site revendique.
    try:
        sm = s.get('https://%s/sitemap.xml' % nom, timeout=15, verify=False)
        fiche['sitemap'] = sm.status_code == 200 and 'xml' in sm.headers.get('content-type', '')
        fiche['sitemap_entrees'] = len(re.findall(r'<loc>', sm.text)) if fiche['sitemap'] else None
    except Exception:
        fiche['sitemap'] = None
        fiche['sitemap_entrees'] = None

    fiche['etat'] = classer(fiche)
    return fiche


def classer(f):
    """Un etat, et seulement a partir de ce qui a ete mesure.

    Premiere regle, avant toute autre : une reponse qu'on n'a pas obtenue ne
    se classe pas. Un 429 rend un corps VIDE — zero lien, zero titre, zero
    theme — et toutes les regles suivantes le liraient comme « site vide ».
    C'est faux, et c'est le genre de faux sur lequel on coupe un domaine.
    """
    if f.get('code') == 429:
        return 'NON MESURE : l\'hebergeur a repondu 429 (trop de requetes)'
    if f.get('code') in (401, 403):
        return 'NON MESURE : acces refuse (%d)' % f['code']
    if f.get('code') and f['code'] >= 500:
        return 'en erreur serveur (%d)' % f['code']
    if f.get('code') == 404:
        return 'introuvable (404)'
    if not f.get('octets'):
        return 'NON MESURE : reponse %s sans contenu' % f.get('code')
    # Redirige vers un AUTRE domaine : c'est deja une consolidation faite.
    dom_final = re.sub(r'^https?://(www\.)?([^/]+).*', r'\2', f.get('url_finale') or '')
    if dom_final and dom_final != f['domaine'] and not dom_final.endswith('.' + f['domaine']):
        return 'redirige vers %s' % dom_final
    if f.get('signes_vide'):
        return 'repond, mais vide : ' + f['signes_vide'][0]
    if f.get('liens_internes', 0) <= 1:
        return 'page seule, aucun lien interne'
    if f.get('noindex'):
        return 'en ligne mais desindexe (noindex)'
    return 'en ligne'


def main():
    fiches = []
    for i, nom in enumerate(DOMAINES):
        f = sonder(nom)
        fiches.append(f)
        print('%2d/%d  %-26s %s' % (i + 1, len(DOMAINES), nom, f.get('etat')),
              flush=True)
        time.sleep(2.5)          # tout le parc partage les memes IP
    fiches.sort(key=lambda f: f['domaine'])
    chemin = os.path.join(ICI, 'parc.json')
    with open(chemin, 'w') as fp:
        json.dump({'mesure_le': maintenant(), 'domaines': fiches}, fp,
                  indent=1, ensure_ascii=False)
    for f in fiches:
        print('%-26s %-34s %s' % (
            f['domaine'], f.get('etat'), f.get('titre') or ''))
    print('\n%d domaines sondes -> %s' % (len(fiches), chemin))


if __name__ == '__main__':
    main()
