<?php
/* Lance domaines.php hors serveur web, avec un $_GET simule.
   Sert uniquement aux tests : jamais televerse chez le client. */
$_GET = json_decode($argv[1], true);
if (!is_array($_GET)) $_GET = array();
require $argv[2] . '/domaines.php';
