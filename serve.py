import json
from db import Base, Photo, Face
from flask import Flask, request
import datetime
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import cast, DATE, extract

engine = create_engine('sqlite:///photos-saved.db', convert_unicode=True)
Base.metadata.bind = engine
DBSession = scoped_session(sessionmaker(autocommit=False,
                                         autoflush=False,
                                         bind=engine))

app = Flask(__name__)

def generate_timeline(sorted_photos):
    last_year = None
    last_month = None
    last_region = None
    cities_in_region = {}
    current = []
    timeline = []

    for photo in sorted_photos:
        do_break = False

        photo_year, photo_month = photo.date.year, photo.date.month

        if photo_year != 1969:
            if photo_year and photo_year != last_year:
                timeline.append({"year" : photo_year})
                last_year = photo_year

            if photo_month and photo_month != last_month:
                timeline.append({"month" : photo_month})
                last_month = photo_month

            if photo.region2 and photo.region2 != last_region:
                timeline.append({"region" : photo.region2})
                last_region = photo.region2

        timeline.append({ "filename" : "%s.jpg" % photo.hash_,
                          "aspectRatio" : 1.0,
                          "city" : photo.city,
                          "lat" : photo.latitude,
                          "lon" : photo.longitude})
        
    timeline2 = []
    tmp = []

    def get_cities(l):
        cities = {}
        for e in l:
            c = e["city"]
            if c: cities[c] = True
        return ", ".join( sorted(cities.keys()) )

    while len(timeline) > 0:
        e = timeline.pop(0)
        if "filename" in e:
            tmp.append(e)
        
        if not "filename" in e or len(timeline) == 0:
            c = get_cities(tmp)
            timeline2.append({ "cities" : c })
            if len(tmp) > 0: timeline2.append(tmp)
            tmp = []
            timeline2.append(e)

    return timeline2

@app.route('/', methods = ['GET', 'POST'])
def index():
    session = DBSession()

    if request.method == 'POST':
        query_year = int(request.form['query_year'])
        query_city = request.form['query_city']
        ## Y no query by date year
        query = session.query(Photo)

        if query_year:
            query = query.filter(Photo.date >= datetime.date(query_year,   1, 1) )\
                         .filter(Photo.date <  datetime.date(query_year+1, 1, 1) )

        if query_city:
            query = query.filter(Photo.city.ilike(query_city))

        sorted_photos = query.order_by(Photo.date.desc(),Photo.path).all()
    else:
        sorted_photos = session.query(Photo).order_by(Photo.date.desc(),Photo.path).all()

    timeline = { "data" : generate_timeline(sorted_photos) }

    response = app.response_class(
        response=json.dumps(timeline),
        status=200,
        mimetype='application/json'
    )

    session.close()

    return response

@app.route('/query_data', methods = ['GET',])
def qet_query_data():
    session = DBSession()

    years  = sorted([a[0] for a in session.query(extract('year', Photo.date)).distinct().all()])

    d = {}
    for year in years:
        query = session.query(Photo.city)
        query = query.filter(Photo.date >= datetime.date(year,   1, 1) )\
                     .filter(Photo.date <  datetime.date(year+1, 1, 1) )
        cities = sorted([a[0] for a in query.filter(Photo.city.isnot(None)).distinct().all()])
        d[year] = cities

    response = app.response_class(
        response=json.dumps(d),
        status=200,
        mimetype='application/json'
    )

    session.close()

    return response

@app.route('/photo/<hash_>.jpg', methods = ['GET',])
def photo(hash_):
    session = DBSession()

    photo = session.query(Photo).filter(Photo.hash_ == hash_).all()[0]
    if photo:
        d = { "path" : photo.path,
	      "date" : photo.date.strftime('%d %b %Y') if photo.date else "",
	      "latitude" : photo.latitude,
	      "longitude" : photo.longitude }
    else:
        d = {}

    response = app.response_class(
        response=json.dumps(d),
        status=200,
        mimetype='application/json'
    )

    session.close()

    return response

@app.route('/faces/<hash_>.jpg', methods = ['GET',])
def faces(hash_):
    session = DBSession()

    faces = session.query(Face).filter(Face.photo_id == hash_).all()
    d = ["faces/%s_%d.jpg" % (f.photo_id, f.id) for f in faces]

    response = app.response_class(
        response=json.dumps(d),
        status=200,
        mimetype='application/json'
    )

    session.close()

    return response


# TODO
@app.route('/person/<hash_>.jpg', methods = ['GET',])
def person(hash_):
    session = DBSession()

    photo  = session.query(Photo).filter(Photo.hash_ == hash_).all()[0]
    people = session.query(Face) .filter(Face.photo_id == photo.hash_).query(Face.person_id).distinct().all()

    d = {}
    for p in people:
        photos = session.query(Face).filter(Face.person_id == p.id).query(Face.photo_id).distinct().all()
        d[p.id] = { p.name, photos }

    response = app.response_class(
        response=json.dumps(d),
        status=200,
        mimetype='application/json'
    )

    session.close()

    return response

@app.route('/nearby/<hash_>.jpg', methods = ['GET',])
def nearby(hash_):
    session = DBSession()

    photo  = session.query(Photo).filter(Photo.hash_ == hash_).all()[0]

    d = []
    if photo.latitude and photo.longitude:
        photos_nearby = session.query(Photo).filter(Photo.intersects(photo)).all()

        d = [{ "filename" : "%s.jpg" % p.hash_,
               "lat" : p.latitude,
               "lon" : p.longitude } for p in photos_nearby if p.hash_ != photo.hash_][:10]

        d.insert(0, { "filename" : "%s.jpg" % photo.hash_,
                      "lat" : photo.latitude,
                      "lon" : photo.longitude } )

    response = app.response_class(
        response=json.dumps(d),
        status=200,
        mimetype='application/json'
    )

    session.close()

    return response


@app.after_request
def after_request(response):
  response.headers.add('Access-Control-Allow-Origin', '*')
  response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
  response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
  return response
