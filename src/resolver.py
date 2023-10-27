#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import argparse
import socket
import flask
import psycopg2
import urllib.parse, urllib.request
from functools import cmp_to_key
from collections import namedtuple
from util import normalise
from html_page import html_451_page

Row = namedtuple('Row', ['url', 'url_type', 'source_id', 'source_priority'])
Priority = namedtuple('Priority', ['source_a_id', 'source_b_id', 'rel'])

app = flask.Flask(__name__)

class Error(Exception):
    """Base class for our exceptions."""
    def __init__(self, http_status, message=''):
        self.http_status = http_status
        self.message = message

class InvalidURNError(Error):
    def __init__(self, urn):
        super().__init__(400, 'Invalid URN: %s' % urn)

class UnknownURNError(Error):
    def __init__(self, urn):
        super().__init__(404, 'Unknown URN: %s' % urn)

class RedirectTimeoutError(Error):
    def __init__(self, url):
        super().__init__(504, 'Timeout while trying to access %s' % url)

class RedirectFailedError(Error):
    def __init__(self, urn, urls):
        message = ('Redirect to the following URL(s):<ul>%s</ul>failed.' %
                   ''.join(['<li>%s</li>' % url for url in urls]))
        super().__init__(502, message)

class ConfigurationError(Error):
    def __init__(self, message=None):
        if not message:
            message = 'Configuration error'
        else:
            message = 'Configuration error: ' % message
        super().__init__(500, message)

class OnlyAvailableInLegalDepositLibrariesError(Error):
    def __init__(self):
        super().__init__(451, html_451_page)

class NotAvailabelOnLegalDepositWorkstationsError(Error):
    def __init__(self):
        super().__init__(451, 'Legal deposit workstations can\'t access the internet.')

def make_cmp_function(priorities, referrer):
    """ Sometimes there are several URLs for one URN. In these cases we
    have to decide which URL to use. This function returns a comparison
    function that is used to sort URLs (so that we can first try to
    redirect to the URL with the highest priority).
    """

    def domain_name(url):
        try:
            parts = urllib.parse.urlparse(url).netloc.split('.')
            return '%s.%s' % (parts[-2], parts[-1])
        except:
            return ''
        
    def cmp_func(a,b):
        # Criterion 1:
        for p in filter(lambda x: x.rel == '<<', priorities):
            if p.source_a_id == a.source_id and p.source_b_id == b.source_id:
                return -1
            if p.source_a_id == b.source_id and p.source_b_id == a.source_id:
                return 1

        # Criterion 2:
        if domain_name(a.url) == domain_name(referrer):
            return 1
        if domain_name(b.url) == domain_name(referrer):
            return -1

        # Criterion 3:
        for p in filter(lambda x: x.rel == '<', priorities):
            if p.source_a_id == a.source_id and p.source_b_id == b.source_id:
                return -1
            if p.source_a_id == b.source_id and p.source_b_id == a.source_id:
                return 1
        
        # Criterion 4:
        if a.source_priority < b.source_priority:
            return -1
        if a.source_priority > b.source_priority:
            return 1

        # We don't have any criterion: a and b are equal:
        return 0

    return cmp_func

def nbn_fi_au_urn_to_url(urn):
    def mime_preference():
        """Returns a pair (a,b) where:

         - a is True if the request prefers application/rdf+xml,
           application/json or text/turtle to text/html, False otherwise.

         - b is the preferred mime type. """

        mime_types = ['application/rdf+xml', 'application/json', 'text/turtle']
        at = flask.request.accept_mimetypes
        best = at.best_match(['text/html'] + mime_types)
        return (best in mime_types and at[best] > at['text/html']), best

    name_space = urn.split(':')[4]
    better_than_html, mime_type = mime_preference()
    if better_than_html:
        url = 'http://api.finto.fi/rest/v1/%s/data?' % name_space
        url += urllib.parse.urlencode((('uri', 'http://urn.fi/' + urn),
                                       ('format', mime_type)))
    else:
        url = 'http://finto.fi/%s/page/%s' % \
            (name_space, ':'.join(urn.split(':')[5:]))
    return url

def get_components(urn):
    """Given an urn, return a (r-component, q-component) tuple.

    For explanation of r-component and q-component, please see rfc 8141.
    """

    r = '?+' in urn
    q = '?=' in urn

    if (r,q) == (False, False):
        return (None, None)
    elif (r,q) == (False, True):
        return (None, urn.split('?=')[-1])
    elif (r,q) == (True, False):
        return (urn.split('?+')[-1], None)
    else:
        return tuple(urn.split('?+')[-1].split('?='))

@app.route('/<path:urn>')
def handle_urn(urn):
    assert type(urn) == str

    # First few special cases:
    does_start = urn.lower().startswith
    if does_start('urn:nbn:de:') or does_start('urn:nbn:ch:'):
        return flask.redirect('https://nbn-resolving.de/' + urn, 301)
    elif does_start('urn:nbn:se:'):
        return flask.redirect('https://urn.kb.se/resolve?urn=' + urn, 301)
    elif does_start('urn:nbn:no'): # Note: does not include a colon at the end.
        return flask.redirect('https://urn.nb.no/' + urn, 301)
    elif does_start('urn:nbn:at:'):
        return flask.redirect('https://resolver.obvsg.at/' + urn, 301)
    elif does_start('urn:nbn:nl:'):
        return flask.redirect('https://www.persistent-identifier.nl/' + urn, 301)
    elif does_start('urn:nbn:cz'): # Note: does not include a colon at the end.
        return flask.redirect('https://resolver.nkp.cz/api/v5/resolver/' + urn, 301)
    elif does_start('urn:nbn:hu'): # Note: does not include a colon at the end.
        return flask.redirect('https://nbn.urn.hu/resolver/' + urn, 301)
    elif does_start('urn:nbn:hr'):
        return flask.redirect('https://urn.nsk.hr/' + urn, 301)

    elif does_start('urn:nbn:fi:au:'):
        return flask.redirect(nbn_fi_au_urn_to_url(urn), 303)
        
    try:
        connection = psycopg2.connect(**config.db_config)
        cursor = connection.cursor()

        normalised_urn = normalise(urn)
        if normalised_urn == None: raise InvalidURNError(urn)

        # FIXME: It's not efficient to read the table every time.
        cursor.execute("SELECT source_a_id, source_b_id, rel FROM priorities")
        priorities = [Priority(*r) for r in cursor.fetchall()]
        
        cursor.execute("""
        SELECT
            urn2url.url, urn2url.url_type, urn2url.source_id, source.priority
        FROM
            urn2url
        INNER JOIN
            source
        ON
            urn2url.source_id = source.source_id
        WHERE
            urn = %{urn}s
        """, {'urn': normalised_urn})
        tuples = [Row(*r) for r in cursor.fetchall()]
        if len(tuples) == 0: raise UnknownURNError(urn)

        urls = [t.url for t in \
                sorted(filter(lambda t: t.url_type == config.whoami, tuples),
                       key = cmp_to_key(make_cmp_function(priorities, flask.request.referrer)),
                       reverse = True)]

        r_component, q_component = get_components(flask.request.full_path)

        # Please see rfc 2483.
        if r_component == 's=I2Ls': # URI to URLs
            return '\n'.join(urls)  # FIXME: This is not probably the right format.
        elif r_component == 's=I2L': # URI to URL
            return urls[0]
        elif r_component == 's=I2Lh': # TODO: Historical URLs?
            return 'not implemented (yet?)', 501
        
        timeout_exceeded = False

        # Loop over URLs (sorted by priority). For each URL send first
        # HTTP HEAD: If it returns HTTP 200 OK, redirect there. Otherwise
        # continue looping.
        for url in urls:
            req = urllib.request.Request(url, method='HEAD')
            # Add two headers to keep https://creativecommons.org happy. (Otherwise we get 403.)
            req.add_header('Accept', '*/*')
            req.add_header('User-Agent', 'Wget/1.19.4 (linux-gnu)')
            try:
                if urllib.request.urlopen(req, timeout=5).status == 200:
                    if q_component: url += '?' + q_component
                    return flask.redirect(url, 303)
            except socket.timeout:
                timeout_url = url
                timeout_exceeded = True
            except Exception:
                # urlopen() raised an exception. We don't care what the
                # exact exception was because we know url is not the URL
                # we are looking for.
                pass

        if timeout_exceeded == True:
            raise RedirectTimeoutError(timeout_url)
        else:
            if len(tuples) > len(urls):
                if config.whoami == 'normal':
                    raise OnlyAvailableInLegalDepositLibrariesError()
                elif config.whoami == 'vapaakappale':
                    raise NotAvailabelOnLegalDepositWorkstationsError()
                else:
                    raise ConfigurationError('Unknown whoami')
            else:
                raise RedirectFailedError(urn, urls)
            
    except psycopg2.Error as error:
        # TODO: Security: too much info?
        http_status, message = 500, 'Internal SQL error: %s' % error
    except (InvalidURNError,
            UnknownURNError,
            RedirectTimeoutError,
            RedirectFailedError,
            ConfigurationError,
            OnlyAvailableInLegalDepositLibrariesError,
            NotAvailabelOnLegalDepositWorkstationsError) as error:
        http_status, message = error.http_status, error.message
    except Exception as error:
        http_status, message = 500, 'Unknown error'
    finally:
        if connection:
            cursor.close()
            connection.close()

    if normalised_urn and normalised_urn.startswith('urn:issn:') and http_status == 404:
        # In the future, redirect to the resolver of the the ISSN
        # International Centre instead of https://portal.issn.org/
        # when they they will have their own resolver.

        # TODO: Should we include q-component?
        
        if flask.request.query_string.lower() == b'+s=issn&p=issn-l':
            prefix = 'https://portal.issn.org/resource/ISSN-L/%s'
        else:
            prefix = 'https://portal.issn.org/resource/ISSN/%s'
        return flask.redirect(prefix % urn[len('URN:ISSN:'):])
        
    if message.startswith('<!DOCTYPE html>'):
        error_page = message
    else:
        error_page = ('<!DOCTYPE html><html><head><title>Error</title></head>'
                      '<body><h1>Error</h1><p>%s</p></body></html>' % message)
    return (error_page, http_status)
        
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='URN resolver')
    parser.add_argument('resolvertype', choices=['normal', 'vapaakappale'])
    args = parser.parse_args()

    if args.resolvertype == 'normal':
        import config_normal as config
    elif args.resolvertype == 'vapaakappale':
        import config_vapaakappale as config
    else:
        print('Unknown resolver type.', file=sys.stderr)
        sys.exit(1)
    
    app.run(host=config.app_host, port=config.app_port)
