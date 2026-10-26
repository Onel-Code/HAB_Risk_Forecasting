"""Laguna de Bay Copernicus Sentinel-3 OLCI quality-screened test-point probe.

Run in GitHub Codespaces after previous CDSE discovery steps:
    python backend/copernicus_laguna_validation.py

Reads /tmp/hab_olci_test/candidates.json and optionally clear_scene/selected.json.
It does not publish anything to Firebase or GitHub.
"""
import argparse
import csv
import json
import os
from pathlib import Path
from urllib.parse import urlparse

import boto3
import numpy as np
from botocore.config import Config
from netCDF4 import Dataset

ROOT = Path('/tmp/hab_olci_test')
FILES = ('geo_coordinates.nc', 'wqsf.nc', 'chl_Nn.nc')
CLOUD_FLAGS = ('CLOUD', 'CLOUD_AMBIGUOUS', 'CLOUD_MARGIN')
BAD_FLAGS = (
    'INVALID', 'CLOUD', 'CLOUD_AMBIGUOUS',
    'CLOUD_MARGIN', 'CLOUD_SHADOW',
    'SNOW_ICE', 'COSMETIC', 'SUSPECT',
    'SATURATED', 'HISOLZEN',
    'HIGHGLINT', 'HIGHLGINT', 'UNCORR_GLINT',
    'OCNN_FAIL'
)


def s3_bucket_key(path):
    if path.startswith('s3://'):
        result = urlparse(path)
        return result.netloc, result.path.lstrip('/')
    parts = path.lstrip('/').split('/', 1)
    if len(parts) != 2:
        raise ValueError(f'Unexpected S3Path format: {path!r}')
    return parts


def load_scenes():
    candidate_file = ROOT / 'candidates.json'
    if not candidate_file.exists():
        raise FileNotFoundError(f'Run the previous catalogue-search cell first: {candidate_file}')
    candidates = json.loads(candidate_file.read_text())
    selected_file = ROOT / 'clear_scene' / 'selected.json'
    if selected_file.exists():
        selected = json.loads(selected_file.read_text()).get('scene')
        candidates = ([selected] if selected else []) + candidates
    seen = set()
    unique = []
    for item in candidates:
        if not item or not item.get('S3Path'):
            continue
        id_ = item.get('Id') or item['Name']
        if id_ not in seen:
            unique.append(item)
            seen.add(id_)
    return unique


def download_one(s3, bucket, objects, outdir, filename):
    matches = [x for x in objects if x['Key'].rsplit('/', 1)[-1].casefold() == filename.casefold()]
    if not matches:
        raise FileNotFoundError(f'Product lacks {filename}')
    obj = matches[0]
    target = outdir / filename
    if not target.exists() or target.stat().st_size != obj['Size']:
        s3.download_file(bucket, obj['Key'], str(target))
    if target.stat().st_size != obj['Size']:
        raise IOError(f'Incomplete {filename} download')
    return target


def pixels_near_point(geo_path, lat0, lon0, radius_km):
    row_parts, col_parts = [], []
    nearest = float('inf')
    with Dataset(geo_path) as nc:
        latvar = nc.variables['latitude']
        lonvar = nc.variables['longitude']
        for start in range(0, latvar.shape[0], 256):
            stop = min(start + 256, latvar.shape[0])
            index = np.s_[start:stop, :]
            lat = np.ma.asarray(latvar[index]).astype('float64').filled(np.nan)
            lon = np.ma.asarray(lonvar[index]).astype('float64').filled(np.nan)
            a = (np.sin(np.radians(lat-lat0)/2)**2
                 + np.cos(np.radians(lat0))*np.cos(np.radians(lat))
                 * np.sin(np.radians(lon-lon0)/2)**2)
            km = 12742 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))
            finite = np.isfinite(km)
            if finite.any():
                nearest = min(nearest, float(np.nanmin(km)))
            r, c = np.where(finite & (km <= radius_km))
            if r.size:
                row_parts.append(r+start)
                col_parts.append(c)
    if not row_parts:
        return np.array([], dtype=int), np.array([], dtype=int), nearest
    return np.concatenate(row_parts), np.concatenate(col_parts), nearest


def masked_region(rows, cols):
    r0, r1 = int(rows.min()), int(rows.max()+1)
    c0, c1 = int(cols.min()), int(cols.max()+1)
    return np.s_[r0:r1, c0:c1], (rows-r0, cols-c0)


def flags_for_pixels(path, region, indices):
    with Dataset(path) as nc:
        var = nc.variables['WQSF']
        raw = var[region]
        bits = np.ma.filled(raw, 0).astype(np.uint64)[indices]
        missing = np.ma.getmaskarray(raw)[indices]
        meanings = str(var.getncattr('flag_meanings')).split()
        masks = var.getncattr('flag_masks')
        if len(meanings) != len(masks):
            raise ValueError('Unexpected mismatch in WQSF flag metadata')
        mapping = {name: int(bit) for name, bit in zip(meanings, masks)}
    return bits, missing, mapping


def summed_mask(mapping, names):
    value = 0
    for name in names:
        value |= mapping.get(name, 0)
    return value


def evaluate_scene(s3, scene, lat0, lon0, radius, cloud_limit, min_valid):
    bucket, prefix = s3_bucket_key(scene['S3Path'])
    prefix = prefix.rstrip('/')+'/'
    scene_id = scene.get('Id') or scene['Name']
    outdir = ROOT / 'probe_cache' / str(scene_id)
    outdir.mkdir(parents=True, exist_ok=True)
    objects = s3.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=1000).get('Contents', [])
    if not objects:
        raise FileNotFoundError('No files found under S3 prefix')
    geo = download_one(s3, bucket, objects, outdir, 'geo_coordinates.nc')
    quality = download_one(s3, bucket, objects, outdir, 'wqsf.nc')
    rows, cols, nearest = pixels_near_point(geo, lat0, lon0, radius)
    result = {
        'product_id': scene.get('Id'), 'product_name': scene['Name'],
        'acquiredAt': scene.get('ContentDate', {}).get('Start'),
        'nearby_pixels': int(rows.size), 'closest_pixel_km': round(nearest, 4)
    }
    if not len(rows):
        return dict(result, status='NO_PIXELS')
    region, indices = masked_region(rows, cols)
    bits, missing, mapping = flags_for_pixels(quality, region, indices)
    clouds = (bits & summed_mask(
        mapping, ('CLOUD', 'CLOUD_AMBIGUOUS')
    )) != 0
    cloud_margin = (
        bits & summed_mask(mapping, ('CLOUD_MARGIN',))
    ) != 0
    water = (bits & summed_mask(mapping, ['WATER','INLAND_WATER'])) != 0
    fails = (bits & summed_mask(mapping, BAD_FLAGS)) != 0
    flags_ok = ~missing & water & ~fails
    result.update(
        cloud_pct=round(float(100*clouds.mean()), 2),
        cloud_margin_pct=round(float(100*cloud_margin.mean()), 2),
        water_pixels=int(water.sum()),
        quality_eligible_pixels=int(flags_ok.sum()),
        top_failures=sorted(
            ((name, int(((bits & mapping.get(name, 0)) != 0).sum()))
             for name in BAD_FLAGS if mapping.get(name, 0)),
            key=lambda t: -t[1]
        )[:6]
    )

    # Diagnostic only. Rejected pixels are not valid measurements.
    result['cloud_flag_counts'] = {
        name: int(((bits & mapping.get(name, 0)) != 0).sum())
        for name in CLOUD_FLAGS
    }
    result['invalid_flag_pixels'] = int(
        ((bits & mapping.get('INVALID', 0)) != 0).sum()
    )

    try:
        diagnostic_file = download_one(
            s3, bucket, objects, outdir, 'chl_Nn.nc'
        )
        with Dataset(diagnostic_file) as nc:
            raw = np.ma.asarray(
                nc.variables['CHL_NN'][region]
            ).astype(float).filled(np.nan)[indices]

        numeric = np.isfinite(raw)

        result['raw_chl_numeric_pixels'] = int(numeric.sum())
        result['raw_water_numeric_pixels'] = int(
            (numeric & water).sum()
        )
        result['quality_passed_numeric_pixels'] = int(
            (numeric & flags_ok).sum()
        )
        result['cloud_flagged_water_pixels'] = int(
            (clouds & water).sum()
        )

    except Exception as exc:
        result['chl_diagnostic_error'] = (
            type(exc).__name__ + ': ' + str(exc)[:160]
        )

    if result['cloud_pct'] > cloud_limit:
        return dict(result, status='REJECT_CLOUD')
    if not flags_ok.any():
        return dict(result, status='REJECT_QUALITY')
    chl_file = download_one(s3, bucket, objects, outdir, 'chl_Nn.nc')
    with Dataset(chl_file) as nc:
        chlvar = nc.variables['CHL_NN']
        units = str(getattr(chlvar, 'units', ''))
        log_chl = np.ma.asarray(chlvar[region]).astype(float).filled(np.nan)[indices]
    result['chl_raw_units'] = units
    result['chl_units'] = 'µg/L'
    valid = flags_ok & np.isfinite(log_chl)
    result['valid_pixels'] = int(valid.sum())
    result['coverage'] = round(float(100*valid.mean()), 2)
    if valid.sum() < min_valid:
        return dict(result, status='INSUFFICIENT_VALID_PIXELS')
    values = 10 ** log_chl[valid]  # log10(mg/m3) -> mg/m3 == ug/L
    values = values[np.isfinite(values) & (values > 0)]
    if values.size < min_valid:
        return dict(result, status='INVALID_CONCENTRATIONS')
    return dict(
        result, status='CANDIDATE',
        chlorophyll=round(float(np.median(values)), 4),
        chl_min=round(float(values.min()), 4),
        chl_max=round(float(values.max()), 4),
        valid_pixels=int(values.size)
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--max-scenes', type=int, default=12)
    parser.add_argument('--lat', type=float, default=14.30)
    parser.add_argument('--lon', type=float, default=121.25)
    parser.add_argument('--radius-km', type=float, default=1.0)
    parser.add_argument('--cloud-limit', type=float, default=5.0)
    parser.add_argument('--min-valid-pixels', type=int, default=5)
    args = parser.parse_args()
    scenes = load_scenes()
    if not scenes:
        raise RuntimeError('No scenes available in candidates.json')
    s3 = boto3.client(
        's3', endpoint_url='https://eodata.dataspace.copernicus.eu',
        aws_access_key_id=os.environ['CDSE_S3_ACCESS_KEY'],
        aws_secret_access_key=os.environ['CDSE_S3_SECRET_KEY'],
        region_name='default',
        config=Config(signature_version='s3v4', s3={'addressing_style':'path'})
    )
    results = []
    accepted = None
    n = min(args.max_scenes, len(scenes))
    print(f'Screening up to {n} scenes at ({args.lat}, {args.lon}); no Firebase writes.', flush=True)
    for i, scene in enumerate(scenes[:n], start=1):
        try:
            row = evaluate_scene(
                s3, scene, args.lat, args.lon, args.radius_km,
                args.cloud_limit, args.min_valid_pixels
            )
        except Exception as exc:
            row = {'product_name': scene.get('Name'),
                   'acquiredAt': scene.get('ContentDate', {}).get('Start'),
                   'status': 'ERROR', 'reason': str(exc)[:180]}
        results.append(row)
        print(f"{i:02d}. {str(row.get('acquiredAt'))[:10]} "
              f"| {row['status']} | cloud={row.get('cloud_pct', '?')}% "
              f"| valid={row.get('valid_pixels', 0)} "
              f"| chl={row.get('chlorophyll', '-')}", flush=True)
        if row['status'] == 'CANDIDATE':
            accepted = row
            break
    summary = ROOT / 'laguna_satellite_quality_report.json'
    summary.write_text(json.dumps(results, indent=2))
    print(f'\nQuality report: {summary}')
    if accepted:
        preview = {
            'acquiredAt': accepted['acquiredAt'],
            'chlorophyll': accepted['chlorophyll'],
            'coverage': accepted['coverage'],
            'sourceProductId': accepted['product_id'],
            'sourceProductName': accepted['product_name'],
            'cloudPercentage': accepted['cloud_pct'],
            'validPixelCount': accepted['valid_pixels'],
            'monitoringLatitude': args.lat,
            'monitoringLongitude': args.lon,
            'locationStatus': 'TEMPORARY_TEST_POINT_NOT_LLDA_STATION',
            'observationStatus': 'RESEARCH_PREVIEW_NOT_VALIDATED'
        }
        filename = ROOT / 'laguna_firestore_record_PREVIEW_ONLY.json'
        filename.write_text(json.dumps(preview, indent=2))
        print('\nVALID NUMERICAL CANDIDATE FOR TECHNICAL PREVIEW:')
        print(json.dumps(preview, indent=2))
        print(f'\nSaved preview: {filename}')
        print('Nothing published to Firebase.')
    else:
        print('\nNo scene passed all checks. No value will be published.')
        print('Option: rerun with --max-scenes 25 for a broader search.')


if __name__ == '__main__':
    main()
