# -*- coding: utf-8 -*-
"""Capture de domaines.php sur un faux compte.

Le compte est FICTIF : aucune capture envoyee au client ne doit montrer
l'arborescence reelle de son hebergement — une capture se reexpedie bien
plus facilement qu'un acces.

Le port est demande au systeme (bind sur 0). Un port ecrit en dur finit par
pointer sur le serveur d'un autre projet, et la capture montre alors autre
chose que ce qu'on croit.
"""

import os
import shutil
import socket
import subprocess
import tempfile
import time

from playwright.sync_api import sync_playwright

ICI = os.path.dirname(os.path.abspath(__file__))
CLE = 'change-cette-cle-avant-de-televerser'

WPC = ("<?php\ndefine('DB_NAME','%s');\n"
       "define('DB_PASSWORD','jamais-affiche');\n")
VER = "<?php\n$wp_version = '%s';\n"

# Six domaines plausibles, aux noms neutres, avec les quatre situations
# qu'une restructuration doit voir : une copie sur la meme base, un site
# ferme par extension, un second WordPress dans un sous-dossier, un domaine
# gare qui ne sert rien.
FAUX = [
    ('domains/exemple-a.com/public_html/index.php', '<?php // wp', 0),
    ('domains/exemple-a.com/public_html/wp-config.php', WPC % 'base_boutique', 0),
    ('domains/exemple-a.com/public_html/wp-includes/version.php', VER % '6.6.1', 0),
    ('domains/exemple-a.com/public_html/wp-content/themes/astra/style.css', '', 40_000),
    ('domains/exemple-a.com/public_html/wp-content/themes/astra-child/style.css', '', 9_000),
    ('domains/exemple-a.com/public_html/wp-content/plugins/woocommerce/w.php', '', 6_400_000),
    ('domains/exemple-a.com/public_html/wp-content/plugins/elementor/e.php', '', 4_100_000),
    ('domains/exemple-a.com/public_html/wp-content/plugins/yoast/y.php', '', 1_800_000),
    ('domains/exemple-a.com/public_html/wp-content/uploads/2025/p.jpg', '', 214_000_000),

    ('domains/exemple-b.net/public_html/index.php', '<?php // wp', 0),
    ('domains/exemple-b.net/public_html/wp-config.php', WPC % 'base_boutique', 0),
    ('domains/exemple-b.net/public_html/wp-includes/version.php', VER % '5.9.1', 0),
    ('domains/exemple-b.net/public_html/wp-content/uploads/2023/q.jpg', '', 61_000_000),

    ('domains/exemple-c.org/public_html/index.php', '<html>Arolax demo</html>', 0),
    ('domains/exemple-c.org/public_html/wp-config.php', WPC % 'base_vitrine', 0),
    ('domains/exemple-c.org/public_html/wp-includes/version.php', VER % '6.4.0', 0),
    ('domains/exemple-c.org/public_html/wp-content/plugins/'
     'under-construction-page/u.php', '', 240_000),

    ('domains/exemple-d.ca/public_html/index.php', '<?php // wp', 0),
    ('domains/exemple-d.ca/public_html/wp-config.php', WPC % 'base_agence', 0),
    ('domains/exemple-d.ca/public_html/wp-includes/version.php', VER % '6.5.5', 0),
    ('domains/exemple-d.ca/public_html/ancien/wp-config.php', WPC % 'base_agence_2019', 0),
    ('domains/exemple-d.ca/public_html/ancien/index.php', '<?php // vieux', 0),
    ('domains/exemple-d.ca/public_html/ancien/gros.dat', '', 480_000_000),

    ('domains/exemple-e.fr/public_html/.htaccess', '# rien', 0),

    ('domains/exemple-f.io/public_html/index.html', '<html>Bonjour</html>', 1_200_000),
]


def port_libre():
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    p = s.getsockname()[1]
    s.close()
    return p


def batir():
    base = tempfile.mkdtemp(prefix='domaines-apercu-')
    for rel, texte, taille in FAUX:
        p = os.path.join(base, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'w') as f:
            if texte:
                f.write(texte)
            if taille:
                f.truncate(taille)      # fichier creux : pas 480 Mo sur disque
    shutil.copy(os.path.join(ICI, 'domaines.php'),
                os.path.join(base, 'domains/exemple-a.com/public_html/domaines.php'))
    return base


def main():
    base = batir()
    doc = os.path.join(base, 'domains/exemple-a.com/public_html')
    port = port_libre()
    # Le journal du serveur de test est ecrit HORS du faux compte : depose
    # dedans, il apparait dans le poids du domaine et fausse la capture.
    journal = tempfile.mkstemp(prefix='domaines-php-', suffix='.log')[1]
    srv = subprocess.Popen(['php', '-S', '127.0.0.1:%d' % port, '-t', doc],
                           stdout=open(journal, 'w'),
                           stderr=subprocess.STDOUT)
    try:
        url = 'http://127.0.0.1:%d/domaines.php?cle=%s&budget=60' % (port, CLE)
        os.makedirs(os.path.join(ICI, 'shots'), exist_ok=True)
        with sync_playwright() as pw:
            nav = pw.chromium.launch()
            pg = nav.new_page(viewport={'width': 1280, 'height': 800})
            for _ in range(40):
                try:
                    pg.goto(url, timeout=3000)
                    break
                except Exception:
                    time.sleep(0.25)
            pg.wait_for_selector('h1', timeout=10000)
            assert 'Recensement' in pg.title(), pg.title()

            pg.screenshot(path=os.path.join(ICI, 'shots', 'domaines-1-haut.png'))
            pg.locator('h2', has_text='A me renvoyer').scroll_into_view_if_needed()
            pg.wait_for_timeout(200)
            pg.screenshot(path=os.path.join(ICI, 'shots', 'domaines-2-json.png'))
            nav.close()
    finally:
        srv.terminate()
        shutil.rmtree(base, ignore_errors=True)

    for n in ('domaines-1-haut.png', 'domaines-2-json.png'):
        p = os.path.join(ICI, 'shots', n)
        print('%s  %d octets' % (n, os.path.getsize(p)))


if __name__ == '__main__':
    main()
