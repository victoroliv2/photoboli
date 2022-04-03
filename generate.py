import os
import hashlib
import sqlite3
from PIL import Image, ImageFile
from PIL.ExifTags import TAGS, GPSTAGS
import pickle
import gc
import sys
from multiprocessing import Pool
from datetime import datetime
import base64
import pickle
import reverse_geocoder as rg
import face_recognition
import numpy as np
from sklearn import preprocessing
from sklearn.cluster import AffinityPropagation

from collections import *

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db import *

from detect_cat import *

THUMB_DIR = 'thumbs/'
FACE_DIR = 'faces/'

engine = create_engine('sqlite:///photos.db', convert_unicode=True)
Base.metadata.bind = engine
DBSession = sessionmaker()
DBSession.bind = engine
Base.metadata.create_all(engine)
session = DBSession()

# https://stackoverflow.com/questions/12984426/python-pil-ioerror-image-file-truncated-with-big-images/23575424#23575424
ImageFile.LOAD_TRUNCATED_IMAGES = True

ROOT_DIR = "full"
HEIC_TMP_DIR = "heic_tmp"
FORMATS = [".jpg", ".mpg", ".mov", ".heic"]
THUMB_SIZES = [20,100,250,2000]
SQUARE_THRESHOLD = 250
FACE_SIZE = 1000

def print_status_bar(path, n, total, width, max_path):
    k = int((n * width) / total)
    s = "[%s%s] %s%s" % ("=" * k, " " * (width - k), path, " " * (max_path - len(path)))
    sys.stdout.write(s)
    sys.stdout.flush()
    sys.stdout.write("\b" * len(s)) # return to start of line, after '['

for t in THUMB_SIZES:
    thumb_dir = os.path.join(THUMB_DIR, str(t) + "/")
    if not os.path.exists(thumb_dir):
        os.makedirs(thumb_dir, 0o755 )

def list_files(formats):
    d = {}
    d = dict( [(f.lower(), []) for f in formats] )
    fullpath = os.path.join(".",ROOT_DIR)
    for root, dirs, files in os.walk(fullpath):
        for f in files:
            p = os.path.join(root, f)
            ext = os.path.splitext(p)[-1].lower()
            if ext in formats:
                prel = os.path.relpath(p, fullpath)
                d[ext].append( prel )
    return d

# barrowed from 
# https://gist.github.com/snakeye/fdc372dbf11370fe29eb 
def _convert_to_degress(value):
    """
    Helper function to convert the GPS coordinates stored in the EXIF to degress in float format
    :param value:
    :type value: exifread.utils.Ratio
    :rtype: float
    """
    d = float(value[0][0]) / float(value[0][1])
    m = float(value[1][0]) / float(value[1][1])
    s = float(value[2][0]) / float(value[2][1])

    return d + (m / 60.0) + (s / 3600.0)


def get_exif(I):
    exif = {}
    info = I._getexif()
    metadata = {}

    if info:
        for tag, value in info.items():
            decoded = TAGS.get(tag, tag)
            exif[decoded] = value

    # get orientation
    metadata["orientation"] = int(exif.get("Orientation", -1))

    # get GPS
    # https://stackoverflow.com/questions/19804768/interpreting-gps-info-of-exif-data-from-photo-in-python
    metadata['latitude'] = None
    metadata['longitude'] = None
    if 'GPSInfo' in exif:
        gpsinfo = {}
        for key in exif['GPSInfo'].keys():
            decode = GPSTAGS.get(key,key)
            gpsinfo[decode] = exif['GPSInfo'][key]
        if 'GPSLatitude' in gpsinfo and 'GPSLongitude' in gpsinfo:
            lat_value = _convert_to_degress(gpsinfo['GPSLatitude'])
            lon_value = _convert_to_degress(gpsinfo['GPSLongitude'])
            if gpsinfo['GPSLatitudeRef']  != 'N': lat_value = -1.0 * lat_value
            if gpsinfo['GPSLongitudeRef'] != 'E': lon_value = -1.0 * lon_value
            metadata['latitude'] = lat_value
            metadata['longitude'] = lon_value

    # get date
    if 'DateTime' in exif:
        date = datetime.strptime(exif['DateTime'], '%Y:%m:%d %H:%M:%S')
        metadata['date'] = date
    else:
        metadata['date'] = datetime.fromtimestamp(0)

    return metadata

def do_hash(path):
    hash_ = hashlib.md5()
    BUF_SIZE = 65536  # lets read stuff in 64kb chunks!
    with open(path, 'rb') as f:
        while True:
            data = f.read(BUF_SIZE)
            if not data:
                break
            hash_.update(data)
    return hash_.hexdigest()

def crop_square(I):
    k = min(I.size) / 2
    cx = I.size[0] / 2
    cy = I.size[1] / 2
    l = int(cx - k)
    r = int(cx + k)
    t = int(cy - k)
    b = int(cy + k)

    I = I.crop((l, t, r, b))
    return I

def generate_thumbnail(path, hash_):
    thumbs = sorted(THUMB_SIZES, reverse=True)
    max_thumb = thumbs[0]

    _, file_extension = os.path.splitext(path)
    if file_extension.lower() == ".heic":
        tmppath = os.path.join(HEIC_TMP_DIR, hash_ + ".jpg")
        os.system("sh convert_heic_2_jpg.sh %s %s %d" % (path, tmppath, max_thumb))
       	path = tmppath

    try:
        I = Image.open(path)
    except:
        print("malformed JPEG: %s" % path)
        return None

    try:
        meta = get_exif(I)
    except:
        print("failed EXIF for %s" % path)
        return None

    orientation = meta["orientation"]

    rotate_angle = { 3: 180, 6: 270, 8 : 90 }
    if orientation in rotate_angle:
        I = I.rotate(rotate_angle[orientation], expand=True)

    detect_file = None

    for size in thumbs:
        w = size
        thumb_file = "%s/%d/%s.jpg" % (THUMB_DIR, w, hash_)
        square = w < SQUARE_THRESHOLD

        if os.path.isfile(thumb_file):
            continue

        if square:
            I = crop_square(I)
            h = w
        else:
            h = int((float(I.size[1]) * size) / I.size[0])

        I.thumbnail((w,h), Image.ANTIALIAS)
        I.save(thumb_file, "JPEG", quality=88)

    return path, meta, hash_

def generate_faces(hashes, frames):
    # USE GPU!
    batch_of_face_locations = face_recognition.batch_face_locations(frames, number_of_times_to_upsample=0)

    faces = []
    for frame_number_in_batch, face_locations in enumerate(batch_of_face_locations):
            face_encodings = face_recognition.face_encodings(frames[frame_number_in_batch], known_face_locations=face_locations)
            hash_ = hashes[frame_number_in_batch]
            for index, (face_encoding, face_location) in enumerate(zip(face_encodings,face_locations)):
                top,right,bottom,left = face_location
                face_image = frames[frame_number_in_batch][top:bottom, left:right]
                face_file = "%s/%s_%d.jpg" % (FACE_DIR, hash_, index)

                if not os.path.isfile(face_file):
                    face_image = Image.fromarray(face_image)
                    face_image.save(face_file, "JPEG", quality=88)

                face_encoding = base64.encodebytes(face_encoding.tostring())
                assert(len(face_encoding) == 1386)

                face_location = [float(a)/(FACE_SIZE - 1) for a in face_location]
                top,right,bottom,left = face_location

                face = Face(id = index,
                            photo_id = hash_,
                            x0 = left, y0 = top, x1 = right, y1 = bottom,
                            encoding = face_encoding)
                faces.append(face)
    return faces

def cluster_faces(session):
    faces = session.query(Face).all()

    encodings = np.array([np.frombuffer(base64.b64decode(face.encoding), dtype=np.float64) for face in faces])

    preprocessing.normalize(encodings, axis = 0, copy = False)

    af = AffinityPropagation().fit(encodings)
    cluster_centers_indices = af.cluster_centers_indices_
    labels = af.labels_

    n_clusters = len(cluster_centers_indices)

    idx = np.arange(labels.shape[0])

    print('Estimated number of clusters: %d' % n_clusters)

    session.query(Person).delete()

    for c in range(n_clusters):
        p = Person(id = c)
        session.add(p)
        for i in idx[labels == c]:
            faces[i].person_id = c

    session.commit()

def run_scan(jpeg_fs):
        total = len(jpeg_fs)
        max_path = max(len(p) for p in jpeg_fs)
        db_photos = []
        hashes = {}
        for n, img in enumerate(jpeg_fs):
            print_status_bar(img, n, total, 40, max_path)

            fullpath = os.path.join(".", ROOT_DIR, img)

            hash_ = do_hash(fullpath)

            if hash_ in hashes: continue # duplicate photo
            hashes[hash_] = True

            p = session.query(Photo.hash_ == hash_).all()
            if (len(p) > 0):
                continue

            ts = generate_thumbnail(fullpath, hash_)
            if not ts: continue
            _, meta, hash_ = ts

            year  = meta['date'].year
            month = meta['date'].month
            day   = meta['date'].day

            lat = meta['latitude']
            lon = meta['longitude']
            city = None
            region1 = None
            region2 = None
            if lat and lon:
                results = rg.search([(lat, lon)],mode=1)
                city = results[0]['name']
                region1 = results[0]['admin1']
                region2 = results[0]['admin2']

            p = Photo(hash_ = hash_,
                      path  = img,
                      date  = meta['date'],
                      latitude  = lat,
                      longitude = lon,
                      city      = city,
                      region1   = region1,
                      region2   = region2)
            db_photos.append(p)

            gc.collect()

        session.add_all(db_photos)
        session.commit()

def make_square_with_bars(A, dim):
    if A.shape[0] == dim and A.shape[1] == dim: return A
    B = np.zeros((dim, dim, A.shape[2]), dtype=np.uint8)
    B[0:A.shape[0], 0:A.shape[1], :] = A
    return B

def run_face_detection():
    db_faces = []
    all_hashes = [p[0] for p in session.query(Photo.hash_).all()]
    print(len(all_hashes))
    print(all_hashes[:10])

    batch_size = 16
    batches = (len(all_hashes) + batch_size - 1) // batch_size
    #TODO process faces and detect cat in a separate step that runs only on thumbnails

    session.query(Face).delete()
    session.commit()

    for b in range(batches):
        frames = []
        hashes = []
        for hash_ in all_hashes[b*batch_size:(b+1)*batch_size]:
                thumb_file = "%s/%d/%s.jpg" % (THUMB_DIR, FACE_SIZE, hash_)
                thumbnail = Image.open(thumb_file)
                thumbnail = np.array(thumbnail.convert('RGB'))
                thumbnail = make_square_with_bars(thumbnail, FACE_SIZE) # CNN needs square input of same size
                hashes.append(hash_)
                frames.append(thumbnail)

        #is_cat = predict_hash_is_cat(hash_)
        #if is_cat: print("%s is cat!", fullpath)

        fs = generate_faces(hashes, frames)
        session.add_all(fs)
        session.commit()

    cluster_faces(session)

RUN_SCAN = True
if RUN_SCAN:
    fs = list_files(FORMATS)
    jpeg_fs = sorted(fs['.jpg'] + fs['.heic'])
    run_scan(jpeg_fs)

RUN_FACE_DETECTION = False
if RUN_FACE_DETECTION:
    run_face_detection()

session.close()
