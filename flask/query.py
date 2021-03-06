import requests
import urllib.parse
from functools import lru_cache
import json
import utils
import re


def query_parts(_from = '', criteria = '', indexing = False):
    """
    Gets all parts from Virtuoso
    Args:
        _from: Graph the parts are from
        criteria: Any additional criteria
        indexing: Whether this query is being called during indexing

    Returns: Formatted list of all parts from Virtuoso

    """
    query = '''
    SELECT DISTINCT
        ?subject
        ?displayId
        ?version
        ?name
        ?description
        ?type
        ?graph
        ?role
        ?sboltype
    ''' + _from + '''
    WHERE {
    ''' + criteria + '''
        ?subject a ?type .
        ?subject sbh:topLevel ?subject .''' + ('''\n    GRAPH ?graph { ?subject ?a ?t } .''' if indexing else "") + '''
        OPTIONAL { ?subject sbol2:displayId ?displayId . }
        OPTIONAL { ?subject sbol2:version ?version . }
        OPTIONAL { ?subject dcterms:title ?name . }
        OPTIONAL { ?subject dcterms:description ?description . }
        OPTIONAL { ?subject sbol2:role ?role . }
        OPTIONAL { ?subject sbol2:type ?sboltype . }
    } 
    '''

    return memoized_query_sparql(query)


@lru_cache(maxsize=32)
def memoized_query_sparql(query):
    """
    Speeds up SPARQL queries using a LRU cache
    Args:
        query: SPARQL Query

    Returns: Results of the SPARQL query

    """
    return query_sparql(query)


def query_sparql(query):
    """
    Query instances of Virtuoso
    Args:
        query: SPARQL query

    Returns:

    """
    endpoints = [utils.get_config()['sparql_endpoint']]

    if utils.get_config()['distributed_search']:
        instances = utils.get_wor()
        for instance in instances:
            endpoints.append(instance['instanceUrl'] + '/sparql?')

    results = []

    for endpoint in endpoints:
        try:
            results.extend(page_query(query, endpoint))
        except:
            utils.log('[ERROR] failed querying:' + endpoint)
            raise Exception("Endpoint not responding")

    return deduplicate_results(results)


def deduplicate_results(results):
    """
    Removes duplicates from all SPARQL queries to various Virtuoso instances
    Args:
        results: List of results which may contain duplicates

    Returns: Deduplicated list of results

    """
    deduped = set()

    for result in results:
        deduped.add(json.dumps(result, sort_keys=True))

    return [json.loads(result) for result in deduped]


def page_query(query, endpoint):
    """
    Query to get results from a particular page in SynBioHub
    Args:
        query: Query to run
        endpoint: Virtuoso endpoint to hit

    Returns: List of parts

    """
    utils.log('Current endpoint: ' + endpoint)

    bar = [
    "[        ]",
    "[=       ]",
    "[===     ]",
    "[====    ]",
    "[=====   ]",
    "[======  ]",
    "[======= ]",
    "[========]",
    "[ =======]",
    "[  ======]",
    "[   =====]",
    "[    ====]",
    "[     ===]",
    "[      ==]",
    "[       =]",
    "[        ]",
    "[        ]"
    ]
    bar_counter = 0

    if endpoint != utils.get_config()['sparql_endpoint']:
        query = re.sub(r'''FROM.*\n''', '', query)

    query_prefix = '''
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX dcterms: <http://purl.org/dc/terms/>
    PREFIX dc: <http://purl.org/dc/elements/1.1/>
    PREFIX sbh: <http://wiki.synbiohub.org/wiki/Terms/synbiohub#>
    PREFIX synbiohub: <http://synbiohub.org#>
    PREFIX igem: <http://wiki.synbiohub.org/wiki/Terms/igem#>
    PREFIX prov: <http://www.w3.org/ns/prov#>
    PREFIX sbol2: <http://sbols.org/v2#>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX purl: <http://purl.obolibrary.org/obo/>
    PREFIX ncbi: <http://www.ncbi.nlm.nih.gov#>
    '''

    offset = 0
    limit = 10000

    results = []

    while True:
        print(bar[bar_counter % len(bar)], end="\r")
        bar_counter+= 1

        full_query = query_prefix + query + 'OFFSET ' + str(offset) + ' LIMIT ' + str(limit)
        new_results = send_query(full_query, endpoint)
        results.extend(new_results)

        if len(new_results) != limit:
            break

        offset += limit

    return results


def send_query(query, endpoint):
    """
    Sends a query to Virtuoso
    Args:
        query: Query to be sent
        endpoint: Endpoint where Virtuoso resides

    Returns: List of parts from Virtuoso

    """
    params = {'query': query}

    if endpoint == utils.get_config()['sparql_endpoint']:
        params['default-graph-uri'] = '' # utils.get_config()['synbiohub_public_graph']

    url = endpoint + urllib.parse.urlencode(params)
    headers = {'Accept': 'application/json'}
    
    try:
        r = requests.get(url, headers=headers)
    except Exception as e:
        utils.log("[ERROR] exception when connecting: " + str(e))
        raise Exception("Local SynBioHub isn't responding")

    if r.status_code != 200:
        utils.log('[ERROR] Got status code when querying: ' + str(r.status_code))
        utils.log(r.text)
        raise Exception(url + ' is not responding')

    results = []

    for binding in r.json()['results']['bindings']:
        result = {}
        for key in binding:
            result[key] = binding[key]['value']
        results.append(result)

    return results

