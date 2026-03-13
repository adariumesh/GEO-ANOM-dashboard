#!/usr/bin/env python3
"""
Geocode Missing AFO Coordinates

Uses US Census Bureau Batch Geocoder to find coordinates for AFOs
that are missing lat/lon data.

Usage:
    python scripts/geocode_missing.py
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point
from geo_anom.core.config import get_config
from geo_anom.core.logging import setup_logger

logger = setup_logger(__name__)


def geocode_with_census(addresses_df):
    """
    Geocode addresses using US Census Bureau Batch Geocoder

    Returns updated dataframe with lat/lon
    """
    import requests
    import io
    import time

    logger.info(f"Geocoding {len(addresses_df)} addresses via US Census Bureau...")

    # Prepare batch file (CSV format required by Census API)
    # Format: ID, Street, City, State, ZIP
    batch_data = []
    for idx, row in addresses_df.iterrows():
        # Try to construct address from available fields
        street = row.get('address', '') or ''
        city = row.get('city', '') or ''
        state = 'MD'  # Maryland
        zipcode = str(row.get('zip_code', '')) or ''

        if city or zipcode:  # Need at least city or zip
            batch_data.append(f"{idx},{street},{city},{state},{zipcode}")

    if not batch_data:
        logger.warning("No valid addresses to geocode")
        return addresses_df

    # Create batch file content
    batch_content = "\n".join(batch_data)

    # Census API endpoint
    url = "https://geocoding.geo.census.gov/geocoder/locations/addressbatch"

    # Send request
    files = {'addressFile': ('batch.csv', batch_content, 'text/csv')}
    data = {'benchmark': 'Public_AR_Current', 'vintage': 'Current_Current'}

    try:
        response = requests.post(url, files=files, data=data, timeout=120)
        response.raise_for_status()

        # Parse results
        results = response.text.strip().split('\n')
        geocoded = {}

        for line in results:
            parts = line.split(',')
            if len(parts) >= 6:
                record_id = int(parts[0])
                match_status = parts[2]

                if match_status == 'Match':
                    lon = float(parts[5])
                    lat = float(parts[6])
                    geocoded[record_id] = (lat, lon)

        logger.info(f"Successfully geocoded {len(geocoded)} out of {len(batch_data)} addresses")

        # Update dataframe
        for idx, (lat, lon) in geocoded.items():
            addresses_df.at[idx, 'latitude'] = lat
            addresses_df.at[idx, 'longitude'] = lon

        return addresses_df

    except Exception as e:
        logger.error(f"Geocoding failed: {e}")
        return addresses_df


def main():
    config = get_config()

    permits_path = config.processed_dir / "afo_permits.gpkg"

    if not permits_path.exists():
        logger.error(f"Permits file not found: {permits_path}")
        logger.error("Run: python scripts/run_phase1.py first")
        sys.exit(1)

    logger.info("=" * 70)
    logger.info("AFO Geocoding - Day 1")
    logger.info("=" * 70)

    # Load permits
    afos = gpd.read_file(permits_path)

    logger.info(f"\nCurrent status:")
    logger.info(f"  Total AFOs: {len(afos)}")
    logger.info(f"  With coordinates: {(~afos.geometry.is_empty).sum()}")
    logger.info(f"  Missing coordinates: {(afos.geometry.is_empty).sum()}")

    # Find missing
    missing = afos[afos.geometry.is_empty].copy()

    if len(missing) == 0:
        logger.info("\n✅ All AFOs already have coordinates!")
        return

    logger.info(f"\n🔍 Attempting to geocode {len(missing)} AFOs...")

    # Save backup
    backup_path = config.processed_dir / "afo_permits_backup.gpkg"
    afos.to_file(backup_path, driver='GPKG')
    logger.info(f"Backup saved to: {backup_path}")

    # Geocode missing
    geocoded_missing = geocode_with_census(missing)

    # Count successful geocodes
    newly_geocoded = (geocoded_missing['latitude'].notna()) & (geocoded_missing['longitude'].notna())
    success_count = newly_geocoded.sum()

    logger.info(f"\n✅ Successfully geocoded: {success_count} AFOs")

    if success_count > 0:
        # Update geometry for successful geocodes
        for idx in geocoded_missing[newly_geocoded].index:
            lat = geocoded_missing.at[idx, 'latitude']
            lon = geocoded_missing.at[idx, 'longitude']
            afos.at[idx, 'latitude'] = lat
            afos.at[idx, 'longitude'] = lon
            afos.at[idx, 'geometry'] = Point(lon, lat)

        # Save updated file
        afos.to_file(permits_path, driver='GPKG')
        logger.info(f"Updated permits saved to: {permits_path}")

        # Summary
        logger.info(f"\n" + "=" * 70)
        logger.info("GEOCODING SUMMARY")
        logger.info("=" * 70)
        logger.info(f"Original AFOs with coordinates: {(~afos.geometry.is_empty).sum() - success_count}")
        logger.info(f"Newly geocoded: {success_count}")
        logger.info(f"Total AFOs with coordinates: {(~afos.geometry.is_empty).sum()}")
        logger.info(f"Still missing: {(afos.geometry.is_empty).sum()}")
        logger.info(f"Coverage: {(~afos.geometry.is_empty).sum() / len(afos) * 100:.1f}%")

        # Save geocoding report
        report_path = config.processed_dir / "geocoding_report.txt"
        with open(report_path, 'w') as f:
            f.write("Geocoding Report\n")
            f.write("=" * 70 + "\n\n")
            f.write(f"Date: {pd.Timestamp.now()}\n\n")
            f.write(f"Original with coordinates: {(~afos.geometry.is_empty).sum() - success_count}\n")
            f.write(f"Newly geocoded: {success_count}\n")
            f.write(f"Total with coordinates: {(~afos.geometry.is_empty).sum()}\n")
            f.write(f"Still missing: {(afos.geometry.is_empty).sum()}\n")
            f.write(f"Coverage: {(~afos.geometry.is_empty).sum() / len(afos) * 100:.1f}%\n")

        logger.info(f"\nReport saved to: {report_path}")
    else:
        logger.warning("\n⚠️ No new coordinates found")
        logger.warning("This could mean:")
        logger.warning("  - Addresses are incomplete in source data")
        logger.warning("  - Census geocoder couldn't match the addresses")
        logger.warning("  - Network issues with Census API")


if __name__ == "__main__":
    main()
