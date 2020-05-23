# -*- coding: utf-8 -*-
import os
import logging
import random
import time

from PIL import Image as PilImage

from base_manager import BaseManager
from ..models import Image


logger = logging.getLogger(__name__)


class ImageManager(BaseManager):
    __model__ = Image

    def find_covers_for_records(self, rec_ids):
        """
            Find all images for list of records
        """
        return (
            self.session.query(Image)
            .filter(Image.record_id.in_(rec_ids))
            .filter(Image.is_cover.is_(True))
        )

    def make_thumbnails(self, media_dir):
        """
            Generate all missing small images
        """
        chunk_size = 1000

        def get_chunk(offset, size=chunk_size):
            return (
                self.session.query(Image)
                .filter(Image.is_cover.is_(True))
                .order_by(Image.id)
                .offset(offset)
                .limit(size)
            )

        chunk_no = 0
        generated = 0

        chunk = get_chunk(chunk_no * chunk_size)

        while chunk.count():

            for img in chunk:
                small_path = os.path.join(media_dir, img.make_filename('_small.jpg'))

                if not os.path.isfile(small_path):
                    orig_path = os.path.join(media_dir, img.make_filename())
                    make_thumbnail(orig_path, small_path)
                    generated += 1

            chunk_no += 1
            chunk = get_chunk(chunk_no * chunk_size)

        return generated

    def clean_up_old_images(self, media_dir, max_dirs=20):
        dir_count = 0
        cleaned = []
        tm_start = time.time()
        for dirpath, dirnames, filenames in os.walk(media_dir):
            random.shuffle(dirnames)
            to_unlink = []
            for name in filenames:
                if os.path.isfile(os.path.join(dirpath, name)):
                    nm = name.split('.', 1)[0]
                    ext = name.split('.', 1)[-1]
                    if not ext == 'jpg':
                        continue
                    if nm[-6:0] == '_small':
                        nm = nm[:-6]
                    if not nm.isdigit():
                        continue
                    if self.session.query(Image).filter(Image.id==int(nm)).count():
                        continue
                    to_unlink.append(os.path.join(dirpath, name))
            if to_unlink:
                dir_count += 1
                logger.info("Deleting odd images from %s: %s", dirpath, len(to_unlink))
                for u in to_unlink:
                    os.unlink(u)
                cleaned += to_unlink
            if dir_count >= max_dirs:
                break
            if time.time() - tm_start > 10:
                break
        return cleaned


def make_thumbnail(original_path, thumbnail_path):
    """
        Make image thumbnail
    """
    size = (640, 640)

    try:
        im = PilImage.open(original_path)
        im.thumbnail(size)
        im.save(thumbnail_path, "JPEG")
    except IOError as e:
        logger.error('Thumbnail generation for {} failed: {}'.format(original_path, e))
