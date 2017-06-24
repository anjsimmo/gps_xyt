# Dependencies
import aniso8601
import numpy as np
import pandas as pd
import gpxpy
from pygc import great_distance
import pyproj

import json
import os
import os.path
import calendar

def gps_to_xyt (gpx_dir, ref_geojson, out_dir):
    gpx_files = []
    for sub_file in os.listdir(gpx_dir):
        f = os.path.join(gpx_dir, sub_file)
        if f.endswith('.gpx') and os.path.isfile(f):
            gpx_files.append(f)

    refs = list(_extract_refs(ref_geojson))

    for gpx in gpx_files:
        for name,lats,lngs,ts in _load_gpx (gpx):
            for prop, aLat, aLng, bLat, bLng, start_dt, end_dt in refs:
                _lats, _lngs, ts_rel = _extract_rel_tslice(lats, lngs, ts, start_dt, end_dt)
                if len(ts_rel) == 0:
                    # no data for this time interval
                    continue
                xs, ys = _reproject(_lats, _lngs, aLat, aLng, bLat, bLng)
                # Write to: <out>/<event-name>/<gpx-segment-name>.csv
                out_f = os.path.join(out_dir, prop, name + '.csv')
                _to_csv(xs, ys, ts_rel, out_f)

def _sanitize (name):
    # prevent dangerous file names, remove spaces
    return name.replace('/','-').replace('.', '-').replace(' ','-')

def _load_gpx (gpx_file):
    """
    gpx -- path to gpx file
    return -- name,lat,lng,utc numpy arrays
    """
    gpx_name, _ = os.path.splitext(os.path.basename(gpx_file))

    with open(gpx_file) as f:
        gpx = gpxpy.parse(f)

    for i_t, track in enumerate(gpx.tracks):
        if track.name:
            track_name = _sanitize(track.name)
        else:
            track_name = "track{}".format(i_t)
        for i_s, segment in enumerate(track.segments):
            segment_name = "segment{}".format(i_s) # gpx segments don't have names
            name = "{}-{}-{}".format(gpx_name, track_name, segment_name)
            lats = []
            lngs = []
            ts = []
            for point in segment.points:
                lats.append(point.latitude)
                lngs.append(point.longitude)
                ts.append(point.time)

            yield name, lats, lngs, ts

def _extract_refs (ref_geojson):
    """
    ref_geojson -- path to geojson with reference shapes
    return -- dict of refid -> latA,lngA,latB,lngB
    """
    with open(ref_geojson, 'r') as f:
        geo = json.load(f)

    for feature in geo['features']:
        if feature["type"] != "Feature":
            continue
        geom = feature["geometry"]
        if geom["type"] != "LineString":
            # Todo: Allow using a single point to setup a north facing reference frame
            continue
        points = geom["coordinates"]
        a = points[0]  # first point
        b = points[-1] # last point
        aLng, aLat = a[0], a[1]
        bLng, bLat = b[0], b[1]

        try:
            props = feature["properties"]
        except KeyError:
            # no properties / events defined to setup temporal frame
            continue

        for prop, val in props.items():
            try:
                start_dt, end_dt = aniso8601.parse_interval(val)
            except ValueError as ex:
                # not a date interval
                print (ex)
                continue

            yield prop, aLat, aLng, bLat, bLng, start_dt, end_dt

def _to_epoch(dt):
    """
    Convert datetime to unix timestamp.
    If timezone not specified, will be assumed to be in UTC.
    """
    return calendar.timegm(dt.utctimetuple())

def _extract_rel_tslice (lats,lngs,t_dts,start_dt,end_dt):
    """
    lats,lngs,t_dts -- gps points
    start_dt -- start date time
    end_dt -- end date time
    return -- lats,lngs,ts_rel numpy arrays
    """
    assert len(lats) == len(lngs) == len(t_dts)
    start_t = _to_epoch(start_dt)
    end_t   = _to_epoch(end_dt)
    ts  = [_to_epoch(dt) for dt in t_dts]
    ts_rel = np.array(ts) - start_t
    idx = np.array([i for i,t in enumerate(ts) if start_t <= t and t <= end_t])
    return np.array(lats)[idx], np.array(lngs)[idx], ts_rel[idx]

def _reproject (lats,lngs,latA,lngA,latB,lngB):
    """
    lat,lng -- wgs84 input arrays
    latA,lngA,latB,lngB -- ref coordinates
    return -- x,y numpy array
    """
    lats = np.array(lats)
    lngs = np.array(lngs)

    vincenty = great_distance(start_latitude  = latA,
                              start_longitude = lngA,
                              end_latitude    = latB,
                              end_longitude   = lngB)
    alpha = vincenty['azimuth']

    p1 = pyproj.Proj(proj='longlat', datum='WGS84')

    if alpha == 0 or alpha == 180 or (latA == 0 and (alpha == 90 or alpha == 270)) or (latA >= 90 or latA <= -90):
        # TODO: Use transverse mercator / simple mercator when appropriate, else libproj4 will throw
        #       "RuntimeError: lat_1=lat_2 or lat_1=0 or lat_2=90"
        raise NotImplementedError("Proj.4 doesn't support omerc projection perfectly aligned with a meridian, perfectly aligned with equator, or at pole")

    if alpha <= 90 or alpha > 270:
        p2 = pyproj.Proj(proj  = 'omerc',
                         lat_0 = latA,
                         lonc  = lngA,
                         alpha = alpha,
                         gamma = 0,
                         )
        xs,ys = pyproj.transform(p1,p2,lngs,lats)
    else:
        # Workaround bug in Proj.4 when alpha is in south direction: https://github.com/OSGeo/proj.4/issues/331
        # For south facing angles, use opposite north facing direction, and flip results
        alpha = (alpha-180) % 360
        p2 = pyproj.Proj(proj  = 'omerc',
                         lat_0 = latA,
                         lonc  = lngA,
                         alpha = alpha,
                         gamma = 0,
                         )
        xs,ys = pyproj.transform(p1,p2,lngs,lats)
        xs = -xs
        ys = -ys

    return xs,ys

def _to_csv(xs, ys, ts_rel, csv):
    """
    xs, ys, ts_rel -- x,y,t numpy arrays
    csv -- path to output file
    """
    os.makedirs(os.path.dirname(csv), exist_ok=True)
    pd.DataFrame({"x": xs, "y": ys, "t": ts_rel}).to_csv(csv, header=True, index=False)
