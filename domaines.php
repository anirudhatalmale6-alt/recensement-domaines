<?php
/**
 * domaines.php — recensement des domaines d'un compte d'hebergement.
 *
 * A DEPOSER dans le public_html d'un domaine, a ouvrir dans le navigateur,
 * et A SUPPRIMER une fois le recensement fait.
 *
 * CE FICHIER NE MODIFIE RIEN. Il n'a aucune fonction d'ecriture : ni unlink,
 * ni rmdir, ni fopen en ecriture, ni rename. C'est un inventaire, pas un
 * outil. On ne restructure pas 29 domaines a partir de suppositions, et je
 * ne peux pas les lire moi-meme : le SSH du compte repond 403 et le FTP est
 * enferme dans un seul public_html.
 *
 * Il n'imprime jamais le CONTENU d'un fichier. La seule valeur lue dans un
 * wp-config.php est DB_NAME — necessaire pour savoir quels domaines
 * partagent une base, ce qui est exactement la question d'une
 * restructuration. Ni l'utilisateur ni le mot de passe ne sont lus.
 */

/* ------------------------------------------------------------------ */
/* 1. CLE D'ACCES — A CHANGER AVANT DE TELEVERSER                     */
/* ------------------------------------------------------------------ */
$CLE = 'change-cette-cle-avant-de-televerser';

if (!isset($_GET['cle']) || !hash_equals($CLE, (string)$_GET['cle'])) {
    header('HTTP/1.1 403 Forbidden');
    header('X-Robots-Tag: noindex, nofollow');
    exit('403');
}
header('X-Robots-Tag: noindex, nofollow');
header('Content-Type: text/html; charset=utf-8');
@set_time_limit(0);
@ini_set('memory_limit', '256M');

$BUDGET = isset($_GET['budget']) ? (int)$_GET['budget'] : 40;
if ($BUDGET < 5)   $BUDGET = 5;
if ($BUDGET > 240) $BUDGET = 240;
$DEBUT = microtime(true);
$tronque = false;

/* ------------------------------------------------------------------ */
/* 2. RACINE DU COMPTE                                                */
/* ------------------------------------------------------------------ */
/* Meme regle que menage.php : on cherche d'abord un dossier contenant
   domains/, c'est la racine du COMPTE et donc tous les domaines d'un coup.
   Un dossier contenant public_html/ n'est que la racine d'UN domaine : on
   le garde en repli, jamais en premier choix. */
function racine_compte($depart) {
    $d = realpath($depart);
    $repli = null;
    for ($i = 0; $i < 8 && $d && $d !== '/' && $d !== ''; $i++) {
        if (is_dir($d . '/domains')) return $d;
        if ($repli === null && is_dir($d . '/public_html')) $repli = $d;
        $p = dirname($d);
        if ($p === $d) break;
        $d = $p;
    }
    return $repli ? $repli : realpath($depart);
}

$RACINE = racine_compte(__DIR__);
if (isset($_GET['racine'])) {
    /* Une racine imposee n'est suivie que si elle est DANS le compte.
       ?racine=/etc doit etre ignore, pas suivi. */
    $r = realpath($_GET['racine']);
    if ($r && strpos($r . '/', $RACINE . '/') === 0) $RACINE = $r;
}

/* ------------------------------------------------------------------ */
/* 3. MESURES                                                         */
/* ------------------------------------------------------------------ */

function budget_depasse() {
    global $DEBUT, $BUDGET, $tronque;
    if (microtime(true) - $DEBUT > $BUDGET) { $tronque = true; return true; }
    return false;
}

/** Poids et nombre de fichiers d'un dossier. S'arrete si le budget tombe :
 *  mieux vaut un chiffre annonce comme partiel qu'un chiffre faux. */
function peser($dir, &$fichiers, $profondeur = 0) {
    $octets = 0;
    if ($profondeur > 12 || budget_depasse()) return $octets;
    $d = @opendir($dir);
    if (!$d) return $octets;
    while (($e = readdir($d)) !== false) {
        if ($e === '.' || $e === '..') continue;
        $p = $dir . '/' . $e;
        if (is_link($p)) continue;          /* jamais suivre un lien */
        if (is_dir($p)) {
            $octets += peser($p, $fichiers, $profondeur + 1);
        } else {
            $fichiers++;
            $octets += (int)@filesize($p);
        }
        if (budget_depasse()) break;
    }
    closedir($d);
    return $octets;
}

/** Version de WordPress, lue dans wp-includes/version.php.
 *  C'est la version REELLEMENT installee. Le numero affiche dans les ?ver=
 *  des pages peut etre celui d'un cache et mentir. */
function version_wp($doc) {
    $f = $doc . '/wp-includes/version.php';
    if (!is_file($f)) return null;
    $t = @file_get_contents($f, false, null, 0, 4000);
    if ($t && preg_match('/\$wp_version\s*=\s*[\'"]([^\'"]+)/', $t, $m)) {
        return $m[1];
    }
    return null;
}

/** UNIQUEMENT DB_NAME. Ni l'utilisateur, ni le mot de passe : deux domaines
 *  qui pointent sur la meme base, c'est le premier fait d'une
 *  restructuration ; le mot de passe n'y sert a rien. */
function base_wp($doc) {
    $f = $doc . '/wp-config.php';
    if (!is_file($f)) return null;
    $t = @file_get_contents($f, false, null, 0, 8000);
    if ($t && preg_match('/DB_NAME[\'"]\s*,\s*[\'"]([^\'"]+)/', $t, $m)) {
        return $m[1];
    }
    return null;
}

function themes_installes($doc) {
    $d = $doc . '/wp-content/themes';
    if (!is_dir($d)) return array();
    $out = array();
    foreach ((array)@scandir($d) as $e) {
        if ($e === '.' || $e === '..') continue;
        if (is_dir($d . '/' . $e)) $out[] = $e;
    }
    return $out;
}

function compte_dossiers($d) {
    if (!is_dir($d)) return null;
    $n = 0;
    foreach ((array)@scandir($d) as $e) {
        if ($e === '.' || $e === '..') continue;
        if (is_dir($d . '/' . $e)) $n++;
    }
    return $n;
}

/** Signes qu'un domaine repond sans etre un site. On lit l'index, et
 *  seulement lui, et on ne recopie AUCUN extrait dans la page : on rend le
 *  nom du signe, jamais le texte trouve. */
function signes_vides($doc) {
    $out = array();
    $f = null;
    foreach (array('index.php', 'index.html') as $n) {
        if (is_file($doc . '/' . $n)) { $f = $doc . '/' . $n; break; }
    }
    if ($f === null) return array('aucun index : le domaine ne sert rien');
    $t = @file_get_contents($f, false, null, 0, 60000);
    if ($t === false) return $out;
    if (preg_match('/arolax/i', $t))                    $out[] = 'demo du theme Arolax';
    if (preg_match('/lorem ipsum/i', $t))               $out[] = 'texte lorem ipsum du theme';
    if (preg_match('/coming soon|under construction|en construction/i', $t))
        $out[] = 'page « bientot disponible »';
    if (filesize($f) < 400 && !is_dir($doc . '/wp-includes'))
        $out[] = 'index quasi vide';
    return $out;
}

/** Les extensions qui posent un mode « site ferme » : un domaine peut etre
 *  parfaitement installe et rester invisible a cause d'une seule d'entre
 *  elles. C'est une cause de « domaine mort » qu'on ne voit pas de dehors. */
function extensions_fermeture($doc) {
    $d = $doc . '/wp-content/plugins';
    if (!is_dir($d)) return array();
    $cherchees = array(
        'coming-soon', 'under-construction-page', 'minimal-coming-soon-maintenance-mode',
        'maintenance', 'wp-maintenance-mode', 'seedprod-coming-soon-pro-5',
    );
    $out = array();
    foreach ($cherchees as $c) if (is_dir($d . '/' . $c)) $out[] = $c;
    return $out;
}

/** Une installation WordPress dans un SOUS-DOSSIER du docroot. C'est la
 *  cause classique du « j'ai deux sites et je ne sais plus lequel tourne ». */
function installs_secondaires($doc) {
    $out = array();
    foreach ((array)@scandir($doc) as $e) {
        if ($e === '.' || $e === '..' || !is_dir($doc . '/' . $e)) continue;
        if (in_array($e, array('wp-admin', 'wp-includes', 'wp-content'), true)) continue;
        if (is_file($doc . '/' . $e . '/wp-config.php')) $out[] = $e;
    }
    return $out;
}

function docroots($racine) {
    /* Chaque domaine de Hostinger vit dans domains/<nom>/public_html. Le
       domaine principal a en plus un public_html a la racine du compte. */
    $out = array();
    if (is_dir($racine . '/domains')) {
        foreach ((array)@scandir($racine . '/domains') as $e) {
            if ($e === '.' || $e === '..') continue;
            $d = $racine . '/domains/' . $e;
            if (!is_dir($d)) continue;
            $out[$e] = is_dir($d . '/public_html') ? $d . '/public_html' : $d;
        }
    }
    if (is_dir($racine . '/public_html') && !isset($out['(principal)'])) {
        $out['(public_html du compte)'] = $racine . '/public_html';
    }
    ksort($out);
    return $out;
}

$FICHES = array();
foreach (docroots($RACINE) as $nom => $doc) {
    $fichiers = 0;
    $octets = peser($doc, $fichiers);
    $wp = is_dir($doc . '/wp-includes');
    $themes = $wp ? themes_installes($doc) : array();
    $FICHES[] = array(
        'domaine'    => $nom,
        'docroot'    => $doc,
        'octets'     => $octets,
        'fichiers'   => $fichiers,
        'modifie'    => @filemtime($doc) ? date('Y-m-d', @filemtime($doc)) : null,
        'wordpress'  => $wp,
        'version'    => $wp ? version_wp($doc) : null,
        'base'       => $wp ? base_wp($doc) : null,
        'themes'     => $themes,
        'extensions' => $wp ? compte_dossiers($doc . '/wp-content/plugins') : null,
        'fermeture'  => $wp ? extensions_fermeture($doc) : array(),
        'secondaire' => installs_secondaires($doc),
        'vide'       => signes_vides($doc),
    );
    if (budget_depasse()) break;
}

/* Deux domaines sur la MEME base : l'un des deux est une copie, et c'est
   toujours la premiere chose a trancher dans une restructuration. */
$par_base = array();
foreach ($FICHES as $f) {
    if ($f['base']) $par_base[$f['base']][] = $f['domaine'];
}
$partagees = array();
foreach ($par_base as $b => $ds) if (count($ds) > 1) $partagees[$b] = $ds;

function ko($o) {
    $u = array('o', 'ko', 'Mo', 'Go');
    $i = 0;
    while ($o >= 1024 && $i < 3) { $o /= 1024; $i++; }
    return ($i ? number_format($o, 1, ',', ' ') : (int)$o) . ' ' . $u[$i];
}
function h($s) { return htmlspecialchars((string)$s, ENT_QUOTES, 'UTF-8'); }

$total_o = 0; $total_f = 0;
foreach ($FICHES as $f) { $total_o += $f['octets']; $total_f += $f['fichiers']; }
?>
<!doctype html><html lang="fr"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Recensement des domaines</title>
<style>
body{font:15px/1.6 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
 color:#1c1a24;margin:0;background:#faf9fc}
.w{max-width:1180px;margin:0 auto;padding:34px 20px 70px}
h1{font-size:26px;margin:0 0 6px}
h2{font-size:18px;margin:36px 0 10px}
.sub{color:#8b8698;margin:0 0 22px}
table{width:100%;border-collapse:collapse;background:#fff;font-size:13.6px;
 border:1px solid #ececf1;border-radius:8px;overflow:hidden}
th,td{text-align:left;padding:10px 11px;border-bottom:1px solid #f1f0f5;
 vertical-align:top}
th{background:#f7f6fa;font-size:11.5px;letter-spacing:.08em;
 text-transform:uppercase;color:#6f6b7a}
tr:last-child td{border-bottom:0}
code{font:12.5px/1.5 ui-monospace,Menlo,Consolas,monospace;color:#4a4753;
 word-break:break-all}
.note{border-left:3px solid #c9c6d0;padding:10px 0 10px 14px;color:#4a4753;
 margin:16px 0;font-size:14px}
.danger{border-left-color:#c0392b;background:#fdf3f2;padding:12px 14px}
.tag{display:inline-block;font-size:11px;padding:2px 8px;border-radius:20px;
 background:#f2f0f6;color:#4a4753;margin:1px 2px 1px 0}
.tag.warn{background:#fdf3f2;color:#c0392b}
.tag.ok{background:#eaf6ee;color:#1f7a45}
textarea{width:100%;height:190px;font:12px/1.5 ui-monospace,Menlo,monospace;
 border:1px solid #d8d5e0;border-radius:8px;padding:12px;background:#fff}
</style>
<div class="w">
<h1>Recensement des domaines</h1>
<p class="sub">Racine analysee : <code><?= h($RACINE) ?></code><br>
<?= count($FICHES) ?> domaines &middot; <?= ko($total_o) ?> &middot;
<?= number_format($total_f, 0, ',', ' ') ?> fichiers &middot;
lecture seule, rien n'a ete modifie.</p>

<?php if ($tronque): ?>
<div class="note danger"><strong>Analyse incomplete.</strong> Le budget de
<?= $BUDGET ?> s a ete atteint : les poids ci-dessous sont des minorants et
la liste peut etre partielle. Relance avec <code>&amp;budget=180</code>.</div>
<?php endif; ?>

<?php if ($partagees): ?>
<div class="note danger"><strong>Des domaines partagent une base de
donnees.</strong> L'un des deux est une copie de l'autre, ou les deux
ecrivent dans le meme site sans le savoir. A trancher en premier :
<?php foreach ($partagees as $b => $ds): ?>
<br><code><?= h($b) ?></code> &rarr; <?= h(implode(', ', $ds)) ?>
<?php endforeach; ?></div>
<?php endif; ?>

<h2>Un domaine par ligne</h2>
<table>
<tr><th>Domaine</th><th>Poids</th><th>Contenu</th><th>Base</th>
<th>Etat mesure</th></tr>
<?php foreach ($FICHES as $f): ?>
<tr>
 <td><strong><?= h($f['domaine']) ?></strong><br>
     <code><?= h($f['docroot']) ?></code></td>
 <td><?= ko($f['octets']) ?><br>
     <span style="color:#8b8698"><?= number_format($f['fichiers'], 0, ',', ' ') ?> fich.</span></td>
 <td><?php if ($f['wordpress']): ?>
      WordPress <?= h($f['version'] ? $f['version'] : '(version illisible)') ?><br>
      <span style="color:#8b8698"><?php
      /* extensions vaut null quand wp-content/plugins n'existe pas, et 0
         quand le dossier existe et qu'il est vide. Afficher « 0 » dans les
         deux cas ferait passer un dossier absent pour un dossier vide —
         deux situations qui ne se reparent pas de la meme facon. */
      echo $f['extensions'] === null
          ? 'wp-content/plugins absent'
          : ((int)$f['extensions'] . ' extensions'); ?>,
      <?= count($f['themes']) ?> themes</span>
     <?php else: ?><span style="color:#8b8698">pas de WordPress</span><?php endif; ?></td>
 <td><code><?= h($f['base'] ? $f['base'] : '—') ?></code></td>
 <td>
  <?php if ($f['modifie']): ?><span class="tag">modifie <?= h($f['modifie']) ?></span><?php endif; ?>
  <?php foreach ($f['vide'] as $v): ?><span class="tag warn"><?= h($v) ?></span><?php endforeach; ?>
  <?php foreach ($f['fermeture'] as $p): ?><span class="tag warn">site ferme par <?= h($p) ?></span><?php endforeach; ?>
  <?php foreach ($f['secondaire'] as $s): ?><span class="tag warn">2e WordPress dans /<?= h($s) ?>/</span><?php endforeach; ?>
  <?php if (!$f['vide'] && !$f['fermeture'] && $f['wordpress']): ?><span class="tag ok">sert un site</span><?php endif; ?>
 </td>
</tr>
<?php endforeach; ?>
</table>

<h2>A me renvoyer</h2>
<p class="sub">Copie ce bloc et colle-le dans le fil : c'est exactement ce
qu'il me faut pour proposer la restructuration. Il ne contient aucun mot de
passe — chemins, poids, versions et noms de bases uniquement.</p>
<textarea readonly onclick="this.select()"><?= h(json_encode(array(
    'racine'   => $RACINE,
    'tronque'  => $tronque,
    'domaines' => $FICHES,
    'bases_partagees' => $partagees,
), JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE)) ?></textarea>

<div class="note"><strong>Quand c'est fini, supprime ce fichier.</strong>
Un inventaire des domaines d'un compte n'a rien a faire en ligne une fois
lu, meme derriere une cle.</div>
</div>
</html>
