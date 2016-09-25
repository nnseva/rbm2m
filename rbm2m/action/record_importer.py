# -*- coding: utf-8 -*-
import logging

from record_manager import RecordManager
from scan_manager import ScanManager
import scraper
from rbm2m.util import to_str

import datetime

logger = logging.getLogger(__name__)


class RecordImporter(object):

    def __init__(self, session, scan):
        self.session = session
        self.scan = scan
        self._record_manager = None
        self._scan_manager = None
        self._next_page = None
        self._has_images = []

    @property
    def record_manager(self):
        if self._record_manager is None:
            self._record_manager = RecordManager(self.session)

        return self._record_manager

    @property
    def scan_manager(self):
        if self._scan_manager is None:
            self._scan_manager = ScanManager(self.session)

        return self._scan_manager

    @property
    def has_images(self):
        """
            List of ids of records with images
        """
        return self._has_images

    @property
    def next_page(self):
        """
            Number of next page in scan or none if no more pages
        """
        return self._next_page

    def run(self, scan, page_no):
        """
            Run scrape and process results
        """
        scrape = scraper.Scrape()
        try:
            scrape.run(scan.genre.title, page_no)
        except scraper.ScrapeError as e:
            raise RecordImportError(str(e))

        self.update_record_count(page_no, scrape.rec_count)
        self._next_page = scrape.next_page

        self.process_records(scrape.records)

    def process_records(self, records):
        """
            Add existing records to scan and process new ones
        """
        uniquify(records)
        raw_record_ids = [rec['id'] for rec in records]

        # First filter out all records already present in current scan
        record_ids = self.scan_manager.records_not_in_scan(self.scan.id, raw_record_ids)
        records = filter(lambda r: r['id'] in record_ids, records)

        # find records already present in db
        old_records = self.record_manager.find_existing(record_ids)

        # compare present records with just got to reload changed
        records_dict = {r['id']:r for r in records}
        not_changed = [rec for rec in old_records if self.compare_records(rec,records_dict[rec.id])]
        logger.debug(to_str("Not Changed found %s against %s old records") % (len(not_changed),len(old_records)))

        # Add not changed records to scan
        self.scan.records.extend(not_changed)
        not_changed_ids = {r.id for r in not_changed}
        for rec in not_changed:
            self.update_record_timestamp(rec)

        for rec_dict in records:
            if rec_dict['id'] not in not_changed_ids:
                rec_dict['genre_id'] = self.scan.genre_id
                rec = self.new_record(rec_dict)
                self.scan.records.append(rec)

    def compare_records(self, rec, rec_dict):
        for n in ('artist','title','label','notes','grade','format','price'):
            if getattr(rec,n,None) != rec_dict.get(n,None):
                return False
        if bool(self.record_manager.has_images(rec.id)) != bool(rec_dict['has_images']):
            return False
        return True

    def update_record_timestamp(self, rec):
        """
            Update existing record timestamp
        """
        rec = self.record_manager.merge_from_dict({
            'id':rec.id,
            'import_date':datetime.datetime.utcnow()
        })
        msg = to_str("Updated record #{}".format(rec.id))
        logger.debug(msg)
        return rec

    def new_record(self, rec_dict):
        """
            Create new record and add images to self._has_images
        """
        has_images = rec_dict.pop('has_images')
        if has_images:
            self._has_images.append(rec_dict['id'])

        rec = self.record_manager.merge_from_dict(rec_dict)
        rec.genre_id = self.scan.genre_id
        msg = to_str("Added record #{}".format(rec.id))
        logger.debug(msg)
        return rec

    def update_record_count(self, page_no, rec_count):
        """
            Update estimated records count every 10 pages
        """
        if page_no is None or page_no % 10 == 0:
            self.scan.est_num_records = rec_count

    def drop_deprecated_records(self):
        self.record_manager.drop_deprecated_records(self.scan)

def uniquify(records):
    """
        Remove records with duplicate ids from list. Modifies list in-place

        :param records: list of records to uniquify
        :return: None
    """
    seen = set()
    for index, record in enumerate(records):
        if record['id'] in seen:
            logger.warn("Duplicate record #{}, discarding".format(record['id']))
            records.pop(index)
        else:
            seen.add(record['id'])


class RecordImportError(Exception):

    """
        Unrecoverable record import error
    """
    pass
