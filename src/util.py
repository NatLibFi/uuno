#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re

def _only_contains(s, valid_chars):
    if len(frozenset(s) - frozenset(valid_chars)) == 0:
        return True
    else:
        return False

def _is_valid_isbn(isbn):
    isbn = isbn.strip()
    valid_chars = ''.join(('0123456789- xX', \
                           '\u2010',  # UNICODE HYPHEN \
                           '\u2011',  # NON-BREAKING HYPHEN \
                           '\u2012',  # MINUS SIGN \
                           '\u2013',  # EN DASH \
                           '\u2014')) # EM DASH
    if len(isbn) < 10: return False
    if not _only_contains(isbn, valid_chars): return False
    if isbn[0] not in '0123456789': return False
    if isbn[-1] not in '0123456789xX': return False
    isbn = re.sub('[^0-9xX]+', '', isbn).lower()

    if len(isbn) == 10:
        digits = [(10 if c == 'x' else int(c)) for c in isbn]
        if (sum([((11 - i) * digits[i-1]) for i in range(1, 11)]) % 11) == 0:
            return True
        else:
            return False
    elif len(isbn) == 13:
        if 'x' in isbn: return False
        weights = (1, 3)*6 + (1, )
        digits = [int(c) for c in isbn]
        if (sum([w*d for (w,d) in zip(weights, digits)]) % 10) == 0:
            return True
        else:
            return False
    else:
        return False

def _is_valid_issn(issn):
    if not re.match('^[0-9]{4}-[0-9]{3}[0-9xX]$', issn): return False
    issn = issn.lower()
    weights = (8, 7, 6, 5, 4, 3, 2)
    digits = [(10 if c == 'x' else int(c)) for c in (issn[:4] + issn[5:])]
    remainder = sum([w*d for (w,d) in zip(weights, digits)]) % 11
    c = 0 if remainder == 0 else 11 - remainder
    if c == digits[-1]:
        return True
    else:
        return False
        
def normalise(urn):
    "Return a normalised version of urn or None if urn is not valid."
    
    urn = urn.strip()

    urn_parts = urn.split(':')
    if len(urn_parts) < 3: return None
    if urn_parts[0].lower() != 'urn': return None

    namespace = urn_parts[1].lower()
    rest = ':'.join(urn_parts[2:])
    if namespace == 'isbn':
        if _is_valid_isbn(rest):
            rest = re.sub('[^0-9xX]+', '', rest)
            rest = rest.replace('X', 'x')
            return 'urn:isbn:' + rest
        else:
            return None
    elif namespace== 'nbn':
        # TODO: Add error checking
        return 'urn:nbn:' + rest
    elif namespace == 'issn':
        if _is_valid_issn(rest):
            return 'urn:issn:' + rest
        else:
            return None
    else:
        # Unknown namespace.
        return None

if __name__ == '__main__':
    assert(normalise('urn:nbn:fi:uef-20201500') == 'urn:nbn:fi:uef-20201500')

    assert(normalise('foo') == None)
    assert(normalise(' foo ') == None)
    assert(normalise('urn:nbn:foo ') == 'urn:nbn:foo')
    assert(normalise('  URN:NBN:foo ') == 'urn:nbn:foo')
    assert(normalise('urn:nbn') == None)
    assert(normalise('urn:isbn:1a3') == None)
    assert(normalise('urn:isbn:123') == None)
    assert(normalise('urn:isbn:978-951-98548-9-2') == 'urn:isbn:9789519854892')

    # TODO: We accept consecutive hyphens and spaces. Shoudn't we?
    assert(normalise('urn:isbn:978-----951-98548-9-2') == 'urn:isbn:9789519854892')
    assert(normalise('urn:isbn:978     951-98548-9-2') == 'urn:isbn:9789519854892')
    assert(normalise('urn:isbn:978 - - 951-98548-9-2') == 'urn:isbn:9789519854892')

    assert(normalise('   urn:isbn:978-951-98548-9-2 ') == 'urn:isbn:9789519854892')
    assert(normalise('urn:isbn:978-951-98548-9-1') == None)
    assert(normalise('urn:isbn:951-98548-9-4') == 'urn:isbn:9519854894')
    assert(normalise('uRn:iSBn:951-98548-9-4') == 'urn:isbn:9519854894')
    assert(normalise('uRn:iSBn:951 98548 9 4') == 'urn:isbn:9519854894')
    assert(normalise('   URN:iSBn:9 5 1 9 8    54 8 9 4  ') == 'urn:isbn:9519854894')
    assert(normalise('uRn:iSBn:951-98548-9-5') == None)
    assert(normalise('urn:isbn:   951-98548-9-4   ') == 'urn:isbn:9519854894')
    assert(normalise('urn:isbn:-951-98548-9-4') == None)
    assert(normalise('urn:isbn:951-98548-9-4-') == None)
    assert(normalise('urn:isbn:043942089X') == 'urn:isbn:043942089x')
    assert(normalise('urn:isbn:143942089X') == None)

    assert(normalise('urn:isbn:978-952-317-483-2') == 'urn:isbn:9789523174832')

    assert(normalise('URN:ISBN:951-33-1779-X') == 'urn:isbn:951331779x')
    assert(normalise('URN:ISBN:051-53-0167-X') == None)

    assert(normalise('URN:ISBN:978\u2010952‐309‐349‐2') == 'urn:isbn:9789523093492')
    assert(normalise('URN:ISBN:978-952-309-349-2') == 'urn:isbn:9789523093492')

    assert(normalise('urn:issn:') == None)
    assert(normalise('urn:issn:1234-5678') == None)
    assert(normalise('urn:issn:0378-5955') == 'urn:issn:0378-5955')
    assert(normalise('uRn:ISSN:0378-5955') == 'urn:issn:0378-5955')

