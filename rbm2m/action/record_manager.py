# -*- coding: utf-8 -*-
from sqlalchemy import or_

from base_manager import BaseManager
from ..models import Record, RecordFlag, Image
import logging

logger = logging.getLogger(__name__)

from rbm2m.util import to_str

class RecordManager(BaseManager):

    """
        Handles all DB interactions regarding records
    """
    __model__ = Record

    def find_existing(self, rec_ids):
        return (
            self.session.query(self.__model__)
                .filter(self.__model__.id.in_(rec_ids))
                .all()
        )

    def has_images(self, rec_id):
        return bool(
            self.session.query(Image)
                .filter(Image.record_id == rec_id)
                .count()
        )

    def list(self, filters=None, search=None, order='id', offset=0):
        q = self.session.query(Record)

        q = q.filter_by(**filters)

        if search:
            search = '%{}%'.format(search)
            q = q.filter(or_(
                Record.artist.ilike(search),
                Record.title.ilike(search),
                Record.notes.ilike(search),
                Record.label.ilike(search)
            ))

        if order[0] == '-':
            q = q.order_by(getattr(Record, order[1:].desc()))
        else:
            q = q.order_by(getattr(Record, order))

        return q.offset(offset).limit(50).all()

    def toggle_flag(self, rec_id, flag_name):
        rec = self.get(rec_id)
        flag = rec.flags.filter(RecordFlag.name == flag_name).first()
        if flag:
            rec.flags.remove(flag)
        else:
            rec.flags.append(RecordFlag(name=flag_name))
        return True

    def set_flag(self, rec_id, flag_name):
        rec = self.get(rec_id)
        flag = rec.flags.filter(RecordFlag.name == flag_name).first()
        if not flag:
            rec.flags.append(RecordFlag(name=flag_name))

    def drop_deprecated_records(self,scan):
        model = self.__model__
        records = self.session.query(model).filter(
            model.genre_id == scan.genre_id,
            model.import_date < scan.started_at
        )
        logger.debug(to_str("Removing deprecated %s records" % records.count()))
        ids = [r.id for r in records.all()]
        images = self.session.query(Image).filter(
            Image.record_id.in_(ids)
        )
        logger.debug(to_str("Removing deprecated %s images" % images.count()))
        images.delete(synchronize_session='fetch')
        records.delete(synchronize_session='fetch')
