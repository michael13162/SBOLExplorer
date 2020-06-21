#!/usr/bin/python3

import traceback

from flask import Flask
from flask import request
from flask import jsonify
import logging
import cluster
import pagerank
import index
import search
import utils
import query
import sequencesearch
import requests


log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)


@app.before_first_request
def startup():
    utils.log('SBOLExplorer started :)')
    es_indices = requests.get(utils.get_config()['elasticsearch_endpoint'] + '_cat/indices?format=json').json()
    if (es_indices[0] is None):
        utils.log('Index not found, creating new index.')
        requests.get(request.url_root + '/update')

@app.errorhandler(Exception)
def handle_error(e):
    utils.log('[ERROR] Returning error ' + str(e) + "\n Traceback:\n" + traceback.format_exc())
    return jsonify(error=str(e)), 500


@app.route('/info', methods=['GET'])
def info():
    utils.log('Explorer up!!! Virtutoso ' + str(query.memoized_query_sparql.cache_info()))
    return utils.get_log()


@app.route('/config', methods=['POST', 'GET'])
def config():
    if request.method == 'POST':
        new_config = request.get_json()
        utils.set_config(new_config)
        utils.log('Successfully updated config')

    config = utils.get_config()
    return jsonify(config)


@app.route('/update', methods=['GET'])
def update():
    subject = request.args.get('subject')

    if subject is None:
        utils.save_update_start_time()

        clusters = cluster.update_clusters()
        utils.save_clusters(clusters)
        
        
        uri2rank = pagerank.update_pagerank()
        utils.save_uri2rank(uri2rank)

        index.update_index(utils.get_uri2rank())
        
        query.memoized_query_sparql.cache_clear()
        utils.log('Cache cleared')

        utils.save_update_end_time()
        success_message = 'Successfully updated entire index'
    else:
        index.refresh_index(subject, utils.get_uri2rank())
        success_message = 'Successfully refreshed: ' + subject

    utils.log(success_message)
    return success_message


@app.route('/incrementalupdate', methods=['POST'])
def incremental_update():
    updates = request.get_json()

    index.incremental_update(updates, utils.get_uri2rank())

    success_message = 'Successfully incrementally updated parts'
    utils.log(success_message)
    return success_message


@app.route('/incrementalremove', methods=['GET'])
def incremental_remove():
    subject = request.args.get('subject')

    index.incremental_remove(subject)

    success_message = 'Successfully incrementally removed: ' + subject
    utils.log(success_message)
    return success_message


@app.route('/incrementalremovecollection', methods=['GET'])
def incremental_remove_collection():
    subject = request.args.get('subject')
    uri_prefix = request.args.get('uriPrefix')

    index.incremental_remove_collection(subject, uri_prefix)

    success_message = 'Successfully incrementally removed collection and members: ' + subject
    utils.log(success_message)
    return success_message


@app.route('/', methods=['GET'])
def sparql_search_endpoint():
    sparql_query = request.args.get('query')
    default_graph_uri = request.args.get('default-graph-uri')
    response = jsonify(search.search(sparql_query, utils.get_uri2rank(), utils.get_clusters(), default_graph_uri))

    utils.log('Successfully sparql searched')
    return response


@app.route('/search', methods=['GET'])
def search_by_string():
    query = request.args.get('query')

    response = jsonify(search.search_es(query)['hits'])

    utils.log('Successfully string searched')
    return response

@app.route('/sequencesearch', methods=['POST'])
def sequence_search():
    params = request.get_json()
    fileType = params['fileType']
    sequence = params['sequence']
    flags = params['flags']
    jsonToSBH = sequencesearch.b64_file_search(sequence, fileType, flags)
    utils.log('Successfully sequence searched file.')
    return jsonify(jsonToSBH)

@app.route('/cron', methods=['POST', 'GET'])
def update_cron_tab():
    if request.method == 'GET':
        utils.log('Crontab currently set to: ' + get_cron())
        return get_cron()

    params = request.get_json()
    cron = params['cron']
    utils.set_cron(cron)
    
    return 'Updated cron file.'
