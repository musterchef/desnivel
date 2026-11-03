"""Trasporto JSON per l'acquisizione esplicita dei contesti esterni."""
import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def request_json(url, params, *, post=False):
    encoded = urlencode(params).encode('utf-8')
    request = Request(url if post else url+'?'+encoded.decode(),
                      data=encoded if post else None,
                      headers={'User-Agent': 'Desnivel/0.1 (trip context)',
                               'Content-Type': 'application/x-www-form-urlencoded'})
    with urlopen(request, timeout=90) as response:
        return json.load(response)
