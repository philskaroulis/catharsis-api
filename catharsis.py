# -*- coding: utf-8 -*-
'''

Homepage and documentation: http://

RULES:
* incomming data must be have Content-Type: application/json
* data must be enclosed by single quotes ('') and properties enclosed in double quotes ("")

TEST:

clear && curl http://0.0.0.0:5000/playlists -v && echo ''
clear && curl http://0.0.0.0:5000/playlists/5160d25fe14fe32a8d00065b -v && echo ''
clear && curl http://0.0.0.0:5000/playlists -X POST -d '{"name": "test9pm", "qty": 0, "duration": 0}' --header "Content-Type: application/json" -v && echo ''
clear && curl http://0.0.0.0:5000/playlists/5162082758e8380ae387617b -X PUT -d '{"name": "fight scenes", "qty": 0, "duration": 0}' --header "Content-Type: application/json" -v && echo ''
clear && curl http://0.0.0.0:5000/playlists/5162082758e8380ae387617b -X DELETE -v && echo ''

-X  -v

-X PUT -v

Copyright (c) 2012, Phil Skaroulis.
License: MIT (see LICENSE for details)
'''


__author__ = 'Phil Skaroulis'
__version__ = '0.1-dev'
__license__ = 'MIT'



## IMPORTS

import os, json, logging

from os.path import join, dirname

from functools import wraps
from contextlib import contextmanager

import pymongo
from pymongo import MongoClient

import bson.json_util
from bson.objectid import ObjectId

import requests

import bottle
from bottle import route, get, post, put, delete, response, hook, error, static_file



## INIT

# prep the logger
logging.basicConfig(level=logging.DEBUG)
logging.info('Started')
logging.debug('Hello from Catharsis API')

# read environment vars
DB_NAME = os.getenv('CATHARSIS_DB_NAME', None)
DB_URL = os.getenv('CATHARSIS_DB_URL', None)
TMDB_KEY = os.getenv('CATHARSIS_TMDB_KEY', None)
logging.debug("DB_NAME={}".format(DB_NAME) )
logging.debug("DB_URL={}".format(DB_URL) )
logging.debug("TMDB_KEY={}".format(TMDB_KEY) )



## CATHARSIS EXCEPTIONS

class Error(Exception):
    """Base class for exceptions in this module."""
    pass

class DatabaseError(Error):
    """Exception raised for errors in the database.

    Attributes:
        msg  -- explanation of the error
    """

    def __init__(self, msg):
        logging.error(msg)
        self.msg = msg



## HELPERS

@contextmanager
def mongo(collection_name):
    # may want to pass that in db_name too, later on, when multiple databases are needed
    if (!DB_NAME) or (!DB_URL):
        raise DatabaseError('Database information was not found in the environment variables.')
    else:
        mongo_client = MongoClient(DB_URL+DB_NAME)
        mongo_request = mongo_client.start_request()
        mongo_collection = mongo_client[DB_NAME][collection_name]
        yield mongo_collection
        mongo_client.end_request()


# utility procedure
def clean_data(obj):
    '''clean up the data in preparation to be returned to user.'''

    # clean up the dictionary
    if isinstance(obj, dict):

        # case #1: convert the "_id" (cruf!)
        # from: "_id": {"$oid": "5160d25fe14fe32a8d00065b"}
        # to: "id": "5160d25fe14fe32a8d00065b"
        if "_id" in obj:
            obj["id"] = str( ObjectId(obj["_id"]) )
            del obj["_id"]

    # do the same clean up for each dictionary in a list
    if isinstance(obj, list):
        for a in obj:
            clean_data(a)


# decorator to wrap each HTTP request handler
def make_dry(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):

        # PRE-PROCESS
        if "id" in kwargs:
            # convert string id into an 'ObjectId' object
            # (ready for use with MongoDB methods)
            kwargs["id"]=ObjectId(kwargs["id"])

        # PROCESS REQUEST
        data = fn(*args, **kwargs)

        # POST-PROCESS
        # clean up the data
        clean_data( data )
        # convert dict to JSON
        json_data = json.dumps(data, default=bson.json_util.default)
        bottle.response.content_type = "application/json"

        return json_data

    return wrapper


# decorator
def dejsonise(fn):
    '''Convert a JSON to dict when consuming HTTP Responses'''
    @wraps(fn)
    def wrapper(*args, **kw):
        return json.loads(fn(*args, **kw))
    return wrapper


# return restful errors as json
def json_error(code=500, text='Unknown Error: Application stopped.'):
    """ Returns a jsonised error. """
    # TODO: receive a list of errors and return accordingly
    bottle.request.status = "{} {}".format(code,text)
    bottle.response.content_type = "application/json"
    return {"errors":[{"code": code, "message": text}]}



## HOOKS

@hook('after_request')
def enable_cors():
    bottle.response.headers['Access-Control-Allow-Origin'] = '*'



## RESTful RESOURCE: playlists

playlist_collection_name = 'playlists'


# list
@get('/')
@get('/playlists')
@get('/playlists/')
@make_dry
def list_playlists():
    response_dict = {}
    with mongo(playlist_collection_name) as collection:
        response_dict = [playlist for playlist in collection.find()]
    if not response_dict:
        response_dict = json_error(404, 'Ok. You have no playlists. Get to work.')
    return response_dict


# show
@get('/playlists/<id>')
@get('/playlists/<id>/')
@make_dry
def show_playlist(id):
    response_dict = {}
    with mongo(playlist_collection_name) as collection:
        response_dict = collection.find_one({"_id": id})
    if not response_dict:
        response_dict = json_error(404, "Can't find playlist with id {}".format(str( id )) )
    return response_dict


# create
@post('/playlists')
@post('/playlists/')
@make_dry
def playlists_create():
    new_playlist = bottle.request.json
    response_dict = {}
    if not new_playlist:
        response_dict = json_error(400, 'Oops. No data received.')
    elif not 'name' in new_playlist:
        response_dict = json_error(400, 'Oops. The required key "name" is missing from the data.')
    else:
        try:
            with mongo(playlist_collection_name) as collection:
                playlist_id = collection.insert(new_playlist)
                response_dict = {'status': 200, 'content': 'Way to go! New playlist has been created.' }
        except Exception as ve:
            response_dict = json_error(400, str(ve))
    return response_dict


# update
@put('/playlists/<id>')
@put('/playlists/<id>/')
@route('/playlists/<id>/update', method='POST')
@route('/playlists/<id>/update/', method='POST')
@make_dry
def update_playlist(id):
    updated_playlist = bottle.request.json
    response_dict = {}
    if not updated_playlist:
        response_dict = json_error(400, 'Oops. No data received.')
    elif not 'name' in updated_playlist:
        response_dict = json_error(400, 'Oops. The required key "name" is missing from the data.')
    else:
        try:
            with mongo(playlist_collection_name) as collection:
                playlist_id = collection.update( {"_id": id}, updated_playlist)
                response_dict = {'status': 200, 'content': 'You did it! Playlist has been updated.' }
        except Exception as ve:
            response_dict = json_error(400, str(ve))
    return response_dict


# delete
@delete('/playlists/<id>')
@delete('/playlists/<id>/')
@route('/playlists/<id>/delete', method='POST')
@route('/playlists/<id>/delete/', method='POST')
@make_dry
def delete_playlist(id):
    response_dict = {}
    try:
        with mongo(playlist_collection_name) as collection:
            playlist_id = collection.remove( {"_id": id} )
            response_dict = {'status': 200, 'content': 'Ok. That playlist is gone. Outta here!' }
    except Exception as ve:
        response_dict = json_error(400, str(ve))
    return response_dict



## RESTful RESOURCE: clips

clip_collection_name = 'clips'


# list
@get('/')
@get('/clips')
@get('/clips/')
@make_dry
def list_clips():
    response_dict = {}
    with mongo(clip_collection_name) as collection:
        response_dict = [clip for clip in collection.find()]
    if not response_dict:
        response_dict = json_error(404, 'Ok. You have no clips. Get to work.')
    return response_dict


# show
@get('/clips/<id>')
@get('/clips/<id>/')
@make_dry
def show_clip(id):
    response_dict = {}
    with mongo(clip_collection_name) as collection:
        response_dict = collection.find_one({"_id": id})
    if not response_dict:
        response_dict = json_error(404, "Can't find clip with id {}".format(str( id )) )
    return response_dict


# create
@post('/clips')
@post('/clips/')
@make_dry
def clips_create():
    new_clip = bottle.request.json
    response_dict = {}
    if not new_clip:
        response_dict = json_error(400, 'Oops. No data received.')
    elif not 'name' in new_clip:
        response_dict = json_error(400, 'Oops. The required key "name" is missing from the data.')
    else:
        try:
            with mongo(clip_collection_name) as collection:
                clip_id = collection.insert(new_clip)
                response_dict = {'status': 200, 'content': 'Way to go! New clip has been created.' }
        except Exception as ve:
            response_dict = json_error(400, str(ve))
    return response_dict


# update
@put('/clips/<id>')
@put('/clips/<id>/')
@route('/clips/<id>/update', method='POST')
@route('/clips/<id>/update/', method='POST')
@make_dry
def update_clip(id):
    updated_clip = bottle.request.json
    response_dict = {}
    if not updated_clip:
        response_dict = json_error(400, 'Oops. No data received.')
    elif not 'name' in updated_clip:
        response_dict = json_error(400, 'Oops. The required key "name" is missing from the data.')
    else:
        try:
            with mongo(clip_collection_name) as collection:
                clip_id = collection.update( {"_id": id}, updated_clip)
                response_dict = {'status': 200, 'content': 'You did it! Clip has been updated.' }
        except Exception as ve:
            response_dict = json_error(400, str(ve))
    return response_dict


# delete
@delete('/clips/<id>')
@delete('/clips/<id>/')
@route('/clips/<id>/delete', method='POST')
@route('/clips/<id>/delete/', method='POST')
@make_dry
def delete_clip(id):
    response_dict = {}
    try:
        with mongo(clip_collection_name) as collection:
            clip_id = collection.remove( {"_id": id} )
            response_dict = {'status': 200, 'content': 'Ok. That clip is gone. Outta here!' }
    except Exception as ve:
        response_dict = json_error(400, str(ve))
    return response_dict



## error responses

'''
@app.error(code=400)
@app.error(code=401)
@app.error(code=403)
@app.error(code=404)
@app.error(code=406)
@app.error(code=409)
@app.error(code=500)
@app.error(code=500)
@app.error(code=501)
@app.error(code=502)
'''

@error(404)
def error404(error):
    return json_error(404, "Nothing here, sorry: %s" % error.output)

@error(500)
def error500(error):
    return json_error(500, "Internal Server Error: %s" % error.output)


## Load our bottle application

app = bottle.default_app()



## THE END
