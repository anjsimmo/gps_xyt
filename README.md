# gps_xyt

Proof-of-concept demonstration of spatio-temporal reference frame concept.

## Dependencies:

* Python 3
  * aniso8601 (parses ISO date-time intervals)
  * gpxpy (parses GPX traces)
  * pygc (geodesic azimuth calculation using Vincenty's formula)
  * pyproj (wraps the Proj4 library)
  * numpy, pandas (data wrangling)

## Reprojecting the example data

```
./example.py
```

This will reproject any GPX traces placed in `example_data/gpx` relative to the spatio-temporal reference frames defined in `example_data/refs.geojson`. Reprojected event traces will be dumped in `example_data/out`

## Recommended tool for editing refs.geojson

GIS systems can often export to GeoJSON, but tend to assume rigid attribute tables. In contrast, creating events in our system requires a way to easily add a new key-value pair to a feature. This is necessary so that an arbitrary number of events can be easily associated with a reference frame geometry. I've found that [geojson.io](http://geojson.io) does a good job of this (and is much more convenient than installing a full GIS editor).

## Known Bugs

- Internally, the Oblique Mercator projection is performed using the Proj4 library. Unfortunately, Proj4 places some constraints on the permitted inputs, which will cause the projection to fail if a reference frame is *not* oblique, i.e. if it is oriented at *exactly* 0,90,180, or 270 degrees (this is unlikely to occur by chance for hand-drawn reference frames, but is likely to occur for artificially constructed frames).
- The GPX format uses UTC to store date-times. As we don't include a database of leap seconds, the reported relative time won't account for any leap seconds that occurred during the time interval.
