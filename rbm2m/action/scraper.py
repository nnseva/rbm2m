# -*- coding: utf-8 -*-
import os
import logging
from concurrent import futures

import rbm_parser
import downloader
from rbm2m.helpers import retry


POOL_SIZE = 6

logger = logging.getLogger(__name__)


class ScrapeError(Exception):

    """
        Raised if scraping failed for any reason (after all retries)
    """
    pass


class Scrape(object):

    """
        Represents one page scrape operation
    """

    def __init__(self):
        self.records = []
        self.next_page = None
        self.rec_count = None

    @retry(ScrapeError, tries=4, delay=30, backoff=2)
    def run(self, genre_title, page):
        """
            Download search results page and extract records, total number of
            records and next page
        """
        try:
            html = downloader.get_results_page(genre_title, page)
            rv = rbm_parser.parse_page(html)
        except (downloader.DownloadError, rbm_parser.ParseError) as e:
            raise ScrapeError(str(e))
        else:
            self.records, self.next_page, self.rec_count = rv


@retry(ScrapeError, tries=2, delay=5)
def genre_list():
    """
        Download and parse genre list rom rbm
    """
    try:
        html = downloader.genre_list()
        return rbm_parser.parse_genres(html)
    except (downloader.DownloadError, rbm_parser.ParseError) as e:
        raise ScrapeError(str(e))


@retry(ScrapeError, tries=3, delay=5)
def image_list(rec_id):
    """
        Downloads list of images for a record
    """
    try:
        json_data = downloader.get_image_list(rec_id)
        return rbm_parser.parse_image_list(json_data)
    except (downloader.DownloadError, rbm_parser.ParseError) as e:
        raise ScrapeError(str(e))


def get_image_urls(rec_ids):
    """
        Download image urls for all records in rec_ids
        and return dict {rec_id_1: ['img_url_1', 'img_url_2', ...], ...}
        If there was some error while getting image list for record, the
        corresponding list will be empty
    """
    rv = dict()
    with futures.ThreadPoolExecutor(max_workers=POOL_SIZE) as executor:
        fut_to_recid = {}
        for rec_id in rec_ids:
            fut = executor.submit(image_list, rec_id)
            fut_to_recid[fut] = rec_id

        for future in futures.as_completed(fut_to_recid):
            rec_id = fut_to_recid[future]

            if future.exception() is not None:
                message = 'image_list for record #{} raised {}'
                logger.warn(message.format(rec_id, future.exception()))
                urls = []
            else:
                urls = future.result()

            rv[rec_id] = urls

    return rv


@retry(ScrapeError, tries=3, delay=5)
def import_image(url, filename):
    """
        Download image from url and save to file. Returns content length
    """
    dirname = os.path.dirname(filename)

    if not os.path.isdir(dirname):
        os.makedirs(dirname)

    try:
        content = downloader.get_content(url)
        with open(filename, 'wb') as f:
            f.write(content)
    except downloader.DownloadError as e:
        raise ScrapeError(e)
    else:
        return len(content)


def download_and_save_images(img_tuples):
    """
    Accepts list of tuples (image_id, image_url, filename)
    Returns list of tuples (image_id, length)
    """
    rv = []
    with futures.ThreadPoolExecutor(max_workers=POOL_SIZE) as executor:
        fut_to_imgid = {}
        for img_id, url, fn in img_tuples:
            fut = executor.submit(import_image, url, fn)
            fut_to_imgid[fut] = img_id

        for future in futures.as_completed(fut_to_imgid):
            img_id = fut_to_imgid[future]

            if future.exception() is not None:
                message = 'import_image for image #{} failed: {}'
                logger.warn(message.format(img_id, future.exception()))
            else:
                rv.append((img_id, future.result()))

    return rv
