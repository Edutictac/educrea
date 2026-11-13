<?php
// EduCrea smoke test helper for a LOCAL test Moodle (never a real Aules). Run as the web server user:
//   php moodle_scorm.php create <course-shortname> <package.zip>   -> {"cmid":..,"scorm":..}
//   php moodle_scorm.php tracks <cmid> <username>                  -> {"score":..,"status":..}
//   php moodle_scorm.php delete <cmid>
// MOODLE_DIR selects the installation (default /var/www/moodle).
define('CLI_SCRIPT', true);
require(getenv('MOODLE_DIR') ?: '/var/www/moodle') . '/config.php';
require_once($CFG->dirroot . '/course/lib.php');
require_once($CFG->dirroot . '/course/modlib.php');
require_once($CFG->dirroot . '/mod/scorm/lib.php');
require_once($CFG->dirroot . '/mod/scorm/locallib.php');

function out($data) { echo json_encode($data), "\n"; exit(0); }
function fail($message) { fwrite(STDERR, $message . "\n"); exit(1); }

\core\session\manager::set_user(get_admin());
[$script, $action] = array_pad($argv, 2, '');

if ($action === 'create') {
    [, , $shortname, $zip] = array_pad($argv, 4, '');
    $course = $DB->get_record('course', ['shortname' => $shortname]) ?: fail('course not found');
    is_readable($zip) ?: fail('package not readable');
    $draft = file_get_unused_draft_itemid();
    get_file_storage()->create_file_from_pathname([
        'contextid' => context_user::instance(get_admin()->id)->id, 'component' => 'user', 'filearea' => 'draft',
        'itemid' => $draft, 'filepath' => '/', 'filename' => 'package.zip'], $zip);
    $info = create_module((object)[
        'course' => $course->id, 'section' => 0, 'modulename' => 'scorm', 'visible' => 1,
        'name' => 'EduCrea smoke ' . date('Y-m-d H:i'), 'introeditor' => ['text' => '', 'format' => FORMAT_HTML, 'itemid' => 0],
        'scormtype' => SCORM_TYPE_LOCAL, 'packagefile' => $draft, 'updatefreq' => SCORM_UPDATE_NEVER,
        'popup' => 0, 'width' => 100, 'height' => 600, 'skipview' => SCORM_SKIPVIEW_NEVER, 'hidebrowse' => 1,
        'displaycoursestructure' => 0, 'hidetoc' => SCORM_TOC_HIDDEN, 'nav' => SCORM_NAV_DISABLED,
        'displayattemptstatus' => 1, 'maxgrade' => 100, 'grademethod' => GRADEHIGHEST, 'maxattempt' => 0,
        'whatgrade' => HIGHESTATTEMPT, 'forcenewattempt' => 0, 'lastattemptlock' => 0, 'forcecompleted' => 0,
        'auto' => 0, 'masteryoverride' => 1, 'completionstatusallscos' => 0, 'autocommit' => 1,
    ]);
    $scos = $DB->count_records_select('scorm_scoes', "scorm = ? AND launch <> ''", [$info->instance]);
    $scos > 0 ?: fail('package imported without launchable SCO');
    out(['cmid' => (int)$info->coursemodule, 'scorm' => (int)$info->instance, 'scos' => $scos]);
}

if ($action === 'tracks') {
    [, , $cmid, $username] = array_pad($argv, 4, '');
    $cm = get_coursemodule_from_id('scorm', (int)$cmid) ?: fail('module not found');
    $user = $DB->get_record('user', ['username' => $username]) ?: fail('user not found');
    $result = ['score' => null, 'status' => null];
    foreach ($DB->get_records_select('scorm_scoes', "scorm = ? AND launch <> ''", [$cm->instance]) as $sco) {
        $tracks = scorm_get_tracks($sco->id, $user->id);
        if ($tracks) {
            $result['score'] = isset($tracks->score_raw) ? (float)$tracks->score_raw : null;
            $result['status'] = $tracks->status ?? null;
        }
    }
    out($result);
}

if ($action === 'delete') {
    $cm = get_coursemodule_from_id('scorm', (int)($argv[2] ?? 0)) ?: fail('module not found');
    course_delete_module($cm->id);
    out(['deleted' => (int)$cm->id]);
}

fail('usage: create <course> <zip> | tracks <cmid> <username> | delete <cmid>');
