# -*- coding: utf-8 -*-
import urllib
import sys

import requests

from .debug import dump_exception


HOST = 'http://www.recordsbymail.com/'
GENRE_LIST_URL = '{host}browse.php'.format(host=HOST)
SEARCH_URL = '{host}search.php?genre={genre_slug}&instock=1'
IMAGE_LIST_URL = '{host}php/getImageArray.php?item={rec_id}'
TIMEOUTS = (3.05, 30)  # Connect, read


def fetch(url):
    """
        Download content from url and return response object.

        Raises `DownloadError` if operation fails
    """
    resp = None
    try:
        resp = requests.get(url, timeout=TIMEOUTS)
        resp.raise_for_status()
    except requests.RequestException as e:
        exc_type, exc_val, tb = sys.exc_info()
        notes = resp.text if resp else ''
        dump_exception('download', exc_type, exc_val, tb, notes)
        raise DownloadError(e)

    else:
        assert resp is not None
        return resp


def fetch_text(url):
    """
        Download text content from url and return it.

        Raises `DownloadError` if operation fails
    """
    return fetch(url).text


def genre_list():
    """
        Download page with the list of genres
    """
    return fetch_text(GENRE_LIST_URL)


def get_results_page(genre_title, page):
    """
        Download search result page
    """
    url = SEARCH_URL.format(host=HOST,
                            genre_slug=urllib.quote_plus(genre_title))

    if page:
        url = url + '&page={}'.format(page)

    return fetch_text(url)


def get_image_list(rec_id):
    """
        Download list of images for a record
    """
    url = IMAGE_LIST_URL.format(host=HOST, rec_id=rec_id)
    return fetch_text(url)


def get_content(url):
    """
        Downloads content from url
    """
    return fetch(url).content


class DownloadError(requests.RequestException):

    """
    Raised for all download errors (timeouts, http errors etc)
    """
    pass
