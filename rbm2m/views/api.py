# -*- coding: utf-8 -*-
from flask import Blueprint, jsonify, current_app, request

from ..webapp import db, redis, basic_auth
from ..action import (stats, scanner, record_manager, genre_manager, user_settings,
                      scan_manager, image_manager, export_manager, debug)

bp = Blueprint('api', __name__)


@bp.before_request
def check_auth():
    if not basic_auth.authenticate():
        return basic_auth.challenge()


@bp.route('/stats')
def get_stats():
    overview = stats.get_overview(db.session)
    scans = stats.active_scans(db.session)
    return jsonify({'stats': overview, 'scans': scans})


@bp.route('/run_scan/<int:genre_id>')
@bp.route('/run_scan/', defaults={'genre_id': None})
def run_scan(genre_id):
    sc = scanner.Scanner(current_app.config, db.session, redis._redis_client)
    try:
        sc.enqueue_scan(genre_id)
    except scanner.ScanError as e:      # Scan already queued
        return jsonify({'success': False, 'message': str(e)})
    else:
        return jsonify({'success': True})


@bp.route('/abort_scan/<int:scan_id>')
@bp.route('/abort_scan/', defaults={'scan_id': None})
def abort_scan(scan_id=None):
    scn = scanner.Scanner(current_app.config, db.session, redis)

    if scan_id is None:
        scan_id = int(request.args.get('scan_id'))

    try:
        scn.abort_scan(scan_id)
    except scanner.ScanError as e:  # no such scan or scan not started
        return jsonify({'success': False, 'message': str(e)})
    else:
        return jsonify({'success': True})


@bp.route('/update_genre')
def update_genre():
    genre_id = int(request.args['gid'])
    field = request.args['f']
    value = int(request.args['v'])
    genman = genre_manager.GenreManager(db.session)
    genre = genman.get(genre_id)
    setattr(genre, field, value)
    return jsonify({'success': True})


@bp.route('/record_list')
def record_list():
    filters = {k[2:]: int(v) for k, v in request.args.items() if k.startswith('f_') and v}
    search_term = request.args.get('search', None)
    order = request.args.get('order', 'id')
    offset = request.args.get('offset', 0)

    recman = record_manager.RecordManager(db.session)
    records = recman.list(filters=filters, search=search_term, order=order,
                          offset=offset)
    return jsonify({'records': [rec.to_dict() for rec in records]})


@bp.route('/record/<int:rec_id>/toggle_flag')
def toggle_record_flag(rec_id):
    flagname = request.args.get('flagname')
    recman = record_manager.RecordManager(db.session)
    return jsonify({'success': recman.toggle_flag(rec_id, flagname)})


@bp.route('/save_settings', methods=['POST'])
def save_settings():
    settings = user_settings.UserSettings(db.session)

    for item in request.json:
        settings[item['name']] = item['value']

    return jsonify({'success': True})


@bp.route('/run_scheduled')
def run_scheduled():
    """
        Run regular scheduled task
    """
    sc = scanner.Scanner(current_app.config, db.session, redis._redis_client)
    rv = sc.tick()
    return jsonify(rv)


@bp.route('/tidy')
def tidy():
    """
        Run daily cleanup
    """
    sm = scan_manager.ScanManager(db.session)
    sm.clean_up_old_scans()
    em = export_manager.ExportManager(db.session)
    em.clean_up_old_exports()
    dumps_glob = "{}/*.html".format(current_app.config['LOGS_DIR'])
    debug.clean_old_dumps(dumps_glob)
    return jsonify({'success': True})


@bp.route('/tidy_scans')
def tidy_scans():
    """
        Run daily cleanup
    """
    sm = scan_manager.ScanManager(db.session)
    sm.clean_up_old_scans(max_rows=10)
    return jsonify({'success': True})


@bp.route('/tidy_images')
def tidy_images():
    """
        Run daily cleanup
    """
    im = image_manager.ImageManager(db.session)
    cleaned = im.clean_up_old_images(current_app.config['MEDIA_DIR'], max_dirs=5)
    return jsonify({'success': True, 'cleaned': cleaned})


@bp.route('/tidy_exports')
def tidy_exports():
    """
        Run daily cleanup
    """
    em = export_manager.ExportManager(db.session)
    em.clean_up_old_exports()
    return jsonify({'success': True})


@bp.route('/tidy_dumps')
def tidy_dumps():
    """
        Run daily cleanup
    """
    dumps_glob = "{}/*.html".format(current_app.config['LOGS_DIR'])
    debug.clean_old_dumps(dumps_glob)
    return jsonify({'success': True})
