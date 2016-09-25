# -*- coding: utf-8 -*-
import datetime
import logging
import os

import task_queue
import scan_manager
import record_manager
import record_importer
import image_importer
import exporter

logger = logging.getLogger(__name__)


FORMATS = ['LP', '45', '12']


class ScanError(Exception):

    """
        Base exception for this module
    """
    pass


class Scanner(object):

    """
        Controls scan execution process
    """

    def __init__(self, config, session, redis):
        self.config = config
        self.session = session
        self.redis = redis
        self._scan_manager = None
        self._queue = None

    @property
    def scan_manager(self):
        if self._scan_manager is None:
            self._scan_manager = scan_manager.ScanManager(self.session)

        return self._scan_manager

    @property
    def queue(self):
        if self._queue is None:
            self._queue = task_queue.TaskQueue(self.redis)

        return self._queue

    def enqueue_scan(self, genre_id):
        """
            Enqueue new scan for specified genre
        """
        if self.scan_manager.get_current_scans(genre_id):
            raise ScanError('Scan already queued')

        scan_dict = {'genre_id': genre_id, 'status': 'queued'}
        scan = self.scan_manager.from_dict(scan_dict)
        self.session.commit()
        self.queue.enqueue('start_scan', scan.id)

    def abort_scan(self, scan_id):
        """
            Aborts scan currently in progress
        """
        scan = self.scan_manager.get(scan_id)

        if not scan:
            raise ScanError('Scan #{} not found'.format(scan_id))

        if scan.status not in ['queued', 'running']:
            raise ScanError('Invalid scan status: {}'.format(scan.status))

        self.finish_scan(scan.id, 'aborted')

    def start_scan(self, scan_id):
        """
            Change scan status to 'running' and enqueue first page task
        """
        scan = self.scan_manager.get(scan_id)
        scan.status = 'running'
        self.queue.enqueue('page_task', scan.id)
        logger.info("Scan #{} for genre {} started".format(scan.id, scan.genre.title))

    def finish_scan(self, scan_id, status):
        """
            Set scan status and finish date
        """
        scan = self.scan_manager.get(scan_id)
        scan.status = status
        scan.finished_at = datetime.datetime.utcnow()

        if status == 'success':
            imp = record_manager.RecordManager(self.session)
            imp.drop_deprecated_records(scan)
            self.queue.enqueue('export_task')

        logger.info("Scan #{} finished with status {}".format(scan_id, status))

    def export_task(self):
        """
            Run exports
        """
        if self.config.EXPORT_XLS:
            self.save_xls()

        if self.config.EXPORT_XLSX:
            self.save_xlsx()

        if self.config.EXPORT_CSV:
            self.save_csv()

    def save_xls(self):
        for fmt in FORMATS:
            fn = os.path.join(self.config.MEDIA_DIR, 'records-{}'.format(fmt))
            xlsexp = exporter.XLSExporter(self.session, filters={'format': fmt})
            xlsexp.save(fn + '.xls')

    def save_xlsx(self):
        for fmt in FORMATS:
            fn = os.path.join(self.config.MEDIA_DIR, 'records-{}'.format(fmt))
            xlsxexp = exporter.XLSXExporter(self.session, filters={'format': fmt})
            xlsxexp.save(fn + '.xlsx')

    def save_csv(self):
        for fmt in FORMATS:
            fn = os.path.join(self.config.MEDIA_DIR, 'records-{}'.format(fmt))
            csvexp = exporter.CSVExporter(self.session, filters={'format': fmt})
            csvexp.save(fn)

    def page_task(self, scan_id, page_no=None):
        """
            Import records from page and queue next page and/or image import
        """
        scan = self.scan_manager.get(scan_id)
        scan.last_action = datetime.datetime.utcnow()
        if scan.status != 'running':
            return

        imp = record_importer.RecordImporter(self.session, scan)

        try:
            imp.run(scan, page_no)
        except record_importer.RecordImportError as e:
            self.finish_scan(scan.id, 'failed')
            logger.error("Task failed: page #{} of scan #{}: {}".format(
                page_no or 1, scan_id, e))
            return

        if imp.has_images and self.config.IMPORT_IMAGES:
            imgjob = self.queue.enqueue('image_task', imp.has_images, at_front=True)
        else:
            imgjob = None

        if imp.next_page:
            self.queue.enqueue('page_task', scan.id, imp.next_page, depends_on=imgjob)
        else:
            self.queue.enqueue('finish_scan', scan.id, 'success', depends_on=imgjob)

        logger.debug("Page #{} of scan #{} completed".format(page_no or 0, scan_id))

    def image_task(self, rec_ids):
        """
            Download and save images for records in rec_ids
        """
        imp = image_importer.ImageImporter(self.config, self.session)
        num_imported = imp.run(rec_ids)
        imp.make_smaller_covers(rec_ids)
        logger.debug("Imported {} images for {} records".format(
            num_imported, len(rec_ids)))

    def tick(self):
        """
            Fail stalled scans (if any) and run next scan (if it's time to)
        """
        num_stalled = self.fail_stalled_scans()
        scheduled = self.run_scheduled_scan()
        logger.debug("Schedule task completed")
        return {'stalled': num_stalled, 'scheduled': scheduled}

    def run_scheduled_scan(self):
        """
            Run next scheduled scan
        """
        active_scans = self.scan_manager.get_current_scans()
        if active_scans:
            return False

        genre = self.get_genre_to_scan()
        if genre:
            self.enqueue_scan(genre.id)

        return genre is not None

    def get_genre_to_scan(self):
        """
            Find imported genre for which there was no successful import
            during update interval

            :return: Genre or None
        """
        not_scanned = self.scan_manager.get_genre_with_no_scans()
        if not_scanned:
            return not_scanned

        return self.scan_manager.get_genre_with_no_scans_in_24h()

    def fail_stalled_scans(self):
        """
            Set status to 'failed' for all scans with no activity for specified interval
        """
        stalled = self.scan_manager.get_stalled_scans()
        for scan in stalled:
            scan.status = 'failed'
            logger.warn("Scan #{} marked as failed due to inactivity".format(scan.id))

        return len(stalled)
