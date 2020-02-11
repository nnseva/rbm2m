# -*- coding: utf-8 -*-
import datetime
import logging

from sqlalchemy import and_, func
from base_manager import BaseManager
from ..models import Scan, scan_records, Genre


# All scans with no activity for this long are considered stalled
INACTIVITY_PERIOD = datetime.timedelta(seconds=600)

# Update interval
UPDATE_INTERVAL = datetime.timedelta(days=1)


logger = logging.getLogger(__name__)


class ScanManager(BaseManager):

    """
        Handles all DB interactions regarding scans
    """
    __model__ = Scan

    def get_current_scans(self, genre_id=None):
        """
            Returns currently running scans for genre (or all genres if genre_id is None)
            :return list of Scans
        """
        query = (
            self.session.query(Scan)
            .filter(Scan.status.in_(['queued', 'running']))
        )

        if genre_id:
            query = query.filter(Scan.genre_id == genre_id)

        return query.all()

    def last_scans(self):
        return (
            self.session.query(Scan)
            .order_by(Scan.started_at.desc())
            .limit(50)
            .all()
        )

    def records_not_in_scan(self, scan_id, rec_ids):
        result = (
            self.session.query(scan_records.c.record_id)
            .filter(scan_records.c.scan_id == scan_id)
            .filter(scan_records.c.record_id.in_(rec_ids))
            .all()
        )
        in_scan = [rec_id for rec_id, in result]
        return list(set(rec_ids) - set(in_scan))

    def get_stalled_scans(self):
        """
            Mark scans with no activity during last INACTIVITY_THRESHOLD seconds as failed

        :return: List of stalled scans
        """
        threshold = datetime.datetime.utcnow() - INACTIVITY_PERIOD
        active_scans = (
            self.session.query(Scan)
            .filter(Scan.status.in_(['queued', 'running']))
            .all()
        )
        rv = [s for s in active_scans if s.last_action < threshold]
        return rv

    def get_genre_with_no_scans_in_24h(self):
        """
            Find one imported genre for which there were no succesful scans in last day

            :return: Genre
        """
        threshold = datetime.datetime.utcnow() - UPDATE_INTERVAL
        q = (
            self.session.query(Genre)
            .select_from(Scan)
            .join(Genre)
            .filter(Scan.status == 'success')
            .filter(Genre.import_enabled.is_(True))
            .group_by(Scan.genre_id)
            .having(func.max(Scan.started_at) < threshold)
        )
        return q.first()

    def get_genre_with_no_scans(self):
        """
            Find one imported genre for which there were no successful scans at all

            :return: Genre
        """
        q = (
            self.session.query(Genre)
                .outerjoin(Scan,
                           and_(
                               Scan.genre_id == Genre.id,
                               Scan.status == 'success')
                           )
                .filter(Genre.import_enabled.is_(True))
                .filter(Scan.id.is_(None))
        )
        return q.first()

    def clean_up_old_scans(self):
        """
            Delete all scans older than 7 days from now
        """
        threshold = datetime.datetime.utcnow() - datetime.timedelta(days=7)
        scans = self.session.query(Scan).filter(Scan.started_at < threshold).order_by(Scan.started_at.asc())
        logger.info("Removing deprecated %s scans", scans.count())
        for s in list(scans):
            logger.debug("Removing deprecated scan: %s", s)
            self.session.query(Scan).filter(Scan.id == s.id).delete()
