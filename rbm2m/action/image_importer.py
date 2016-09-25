# -*- coding: utf-8 -*-
import os
import logging

from image_manager import ImageManager, make_thumbnail
from record_manager import RecordManager
import scraper

from rbm2m.util import to_unicode, to_str

logger = logging.getLogger(__name__)


class ImageImporter(object):

    """
        Imports images for records
    """

    def __init__(self, config, session):
        self.config = config
        self.session = session
        self._image_manager = None

    @property
    def image_manager(self):
        if self._image_manager is None:
            self._image_manager = ImageManager(self.session)

        return self._image_manager

    def run(self, rec_ids):
        """
            Import images for records, identified by rec_ids
        """
        rec_image_urls = scraper.get_image_urls(rec_ids)

        dl_list = self.make_dl_list(rec_image_urls)

        saved = scraper.download_and_save_images(dl_list)

        for img_id, length in saved:
            img = self.image_manager.get(img_id)
            img.length = length

        return len(saved)

    def make_dl_list(self, rec_image_urls):
        """
            Accepts dict {rec_id_1: ['img_url_1', 'img_url_2', ..], ...}
            Generate list of tuples (image_id, image_url, filename)
        """
        for rec_id, urls in rec_image_urls.items():
            if not urls:
                self.mark_record(rec_id, 'missing_images')
                logger.warn("Missing images for record #%d".format(rec_id))
                continue

            images = self.save_image_rows(rec_id, urls)

            for image in images:
                savepath = os.path.join(self.config.MEDIA_DIR, image.make_filename())
                yield image.id, image.url, savepath

    def save_image_rows(self, rec_id, urls):
        """
            Return list of images for rec_id, creating new ones if necessary.
            Do not return existing images with length>0
        """
        self.image_manager.find(record_id=rec_id).delete()
        self.session.flush()
        for url in urls:
            fields = {'record_id': rec_id, 'url': url}
            fields['is_cover'] = is_cover(rec_id, url)
            yield self.image_manager.from_dict(fields)

    def mark_record(self, rec_id, flag):
        """
            Mark record, identified by rec_id, with flag
        """
        recman = RecordManager(self.session)
        recman.set_flag(rec_id, flag)

    def make_smaller_covers(self, rec_ids):
        """
            Generate smaller cover image for each record in rec_ids
        """
        covers = self.image_manager.find_covers_for_records(rec_ids)

        for c in covers:
            fn = os.path.join(self.config.MEDIA_DIR, c.make_filename())
            thumb_fn = os.path.join(self.config.MEDIA_DIR,
                                    c.make_filename('_small.jpg'))
            make_thumbnail(fn, thumb_fn)

        logger.debug("Created {} small covers for {} records".format(
            covers.count(), len(rec_ids)))


def is_cover(rec_id, img_url):
    """
        Returns trus if filename is the same as record id
    """
    filename = os.path.basename(img_url)
    slug = os.path.splitext(filename)[0]
    return str(rec_id) == to_str(slug)
