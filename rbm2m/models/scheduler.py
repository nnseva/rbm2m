# -*- coding: utf-8 -*-
import datetime

from rq import Queue

from . import Record, Scan, Genre, Image
from .scraper import Scraper


class Scheduler(object):
    def __init__(self, session, redis, queue_name):
        self.session = session
        self.redis = redis
        self.queue_name = queue_name
        self.queue = Queue(self.queue_name, connection=self.redis)

    def run_scan(self, genre_id):
        current_scan = self.get_current_scan(genre_id)
        if current_scan:
            raise AlreadyStarted('Scan for genre #%d already started: %s'
                                 % (genre_id, current_scan))

        job = self.queue.enqueue('rbm2m.worker.start_scan', genre_id)
        return job

    def abort_scan(self, scan_id):
        # TODO
        pass

    def get_current_scan(self, genre_id):
        return self.session.query(Scan) \
            .filter_by(genre_id=genre_id, status='started') \
            .first()

    def start_scan(self, genre_id):
        genre = Genre.get(genre_id)
        num_records = Scraper.get_num_pages(genre_id)
        scan = Scan(genre_id=genre_id, started=datetime.datetime.utcnow(),
                    status='started', num_records=num_records)
        self.session.add(scan)
        self.session.commit()
        print "*** Starting scan #%d for genre %d" % (scan.id, genre_id)

        job = self.queue.enqueue('run_task', scan.to_dict(), genre.title)

    def finish_scan(self, scan_dict, pages, status):
        print "*** Scan #%d finished - %d pages" % (scan_dict['id'], pages+1)
        scan = Scan.get(scan_dict['id'])
        scan.status = 'success'
        self.session.add(scan)
        self.session.commit()

    def run_task(self, scan_dict, genre_title, page=0):
        records, nextpage, num_records = Scraper.scrape_page(genre_title, page)

        # records: [(id, {values}), ...]
        ids = [rid for rid, rv in records]
        existing_ids = self.session.query(Record.id).filter(Record.id in ids).all()

        # new_ids = list(set(ids) - {rec_id for (rec_id,) in existing_ids})
        for rid, rv in records:
            if rid in existing_ids:
                continue
            rec = Record(**rv)
            for imgurl in rv['images']:
                rec.images.append(Image(url=imgurl))
            self.session.add(rec)

        self.session.commit()
        print "Scan #%d page #%d - %d items, %d new" % (scan_dict['id'], page, len(ids), len(ids)-len(existing_ids))

        if nextpage:
            job = self.queue.enqueue('task', scan_dict, genre_title, page+1)
        else:
            job = self.queue.enqueue('finish_scan', scan_dict, page, 'success')



class SchedulerError(Exception):
    pass

class AlreadyStarted(SchedulerError):
    pass
