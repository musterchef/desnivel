"""Trasporto JSON per l'acquisizione esplicita dei contesti esterni."""
import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from desnivel.settings import DEFAULT_SETTINGS


def request_json(url, params, *, post=False, timeout_s=None):
    encoded = urlencode(params).encode('utf-8')
    request = Request(url if post else url+'?'+encoded.decode(),
                      data=encoded if post else None,
                      headers={'User-Agent': 'Desnivel/0.1 (trip context)',
                               'Content-Type': 'application/x-www-form-urlencoded'})
    timeout_s = DEFAULT_SETTINGS.network.context_timeout_s if timeout_s is None else timeout_s
    with urlopen(request, timeout=timeout_s) as response:
        return json.load(response)
