#!/usr/bin/env python3
import gps_xyt

gpx_dir = "example_data/gpx/"
ref_geojson = "example_data/refs.geojson"
out_dir = "example_data/out/"
gps_xyt.gps_to_xyt (gpx_dir, ref_geojson, out_dir)
