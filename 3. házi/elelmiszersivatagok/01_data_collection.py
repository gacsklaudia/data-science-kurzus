"""Download Hungarian grocery shops and settlement boundaries from Overpass."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import geopandas as gpd
import requests
from shapely.geometry import (
    LineString,
    MultiLineString,
    MultiPolygon,
    Point,
    Polygon,
)
from shapely.ops import polygonize, unary_union


OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OVERPASS_TIMEOUT = (15, 180)
CRS = "EPSG:4326"

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
SHOPS_PATH = DATA_DIR / "shops.geojson"
SETTLEMENTS_PATH = DATA_DIR / "settlements.geojson"

SHOP_TYPES = [
    "supermarket",
    "convenience",
    "general",
    "bakery",
    "greengrocer",
    "butcher",
]


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def is_valid_cache(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        gdf = gpd.read_file(path)
    except Exception:
        return False
    return not gdf.empty and "geometry" in gdf.columns and gdf.geometry.notna().any()


def query_overpass(query: str) -> list[dict[str, Any]]:
    try:
        response = requests.post(
            OVERPASS_URL,
            data={"data": query},
            timeout=OVERPASS_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise RuntimeError(
            "Overpass request failed. Check internet access/retry later."
        ) from exc

    if response.status_code != 200:
        raise RuntimeError(
            f"Overpass returned HTTP {response.status_code}. "
            "Try again later or use another Overpass endpoint."
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError(
            "Overpass returned malformed JSON. Retry later or check endpoint status."
        ) from exc

    elements = payload.get("elements")
    if not isinstance(elements, list) or not elements:
        raise RuntimeError(
            "Overpass response was empty/malformed. Verify query scope and retry."
        )
    return elements


def _coords_from_geometry(geometry: list[dict[str, Any]]) -> list[tuple[float, float]]:
    coords: list[tuple[float, float]] = []
    for point in geometry:
        if "lon" in point and "lat" in point:
            coords.append((point["lon"], point["lat"]))
    return coords


def representative_point_from_element(element: dict[str, Any]) -> Point | None:
    if element.get("type") == "node" and "lon" in element and "lat" in element:
        return Point(element["lon"], element["lat"])

    if "center" in element and isinstance(element["center"], dict):
        center = element["center"]
        if "lon" in center and "lat" in center:
            return Point(center["lon"], center["lat"])

    geometry = element.get("geometry")
    if isinstance(geometry, list) and geometry:
        coords = _coords_from_geometry(geometry)
        if len(coords) == 1:
            return Point(coords[0])
        if len(coords) >= 3 and coords[0] == coords[-1]:
            return Polygon(coords).representative_point()
        if len(coords) >= 2:
            return LineString(coords).representative_point()
    return None


def relation_boundary_geometry(element: dict[str, Any]) -> Polygon | MultiPolygon | MultiLineString | None:
    members = element.get("members")
    if not isinstance(members, list):
        return None

    outer_lines: list[LineString] = []
    inner_lines: list[LineString] = []
    for member in members:
        if member.get("type") != "way":
            continue
        geometry = member.get("geometry")
        if not isinstance(geometry, list):
            continue
        coords = _coords_from_geometry(geometry)
        if len(coords) < 2:
            continue
        line = LineString(coords)
        if member.get("role") == "inner":
            inner_lines.append(line)
        else:
            outer_lines.append(line)

    if not outer_lines:
        return None

    outer_polys = list(polygonize(unary_union(outer_lines)))
    if not outer_polys:
        return MultiLineString(outer_lines)

    outer_geom = unary_union(outer_polys)
    if inner_lines:
        inner_polys = list(polygonize(unary_union(inner_lines)))
        if inner_polys:
            outer_geom = outer_geom.difference(unary_union(inner_polys))
    return outer_geom


def settlement_geometry_from_element(element: dict[str, Any]):
    etype = element.get("type")
    geometry = element.get("geometry")

    if etype == "node" and "lon" in element and "lat" in element:
        return Point(element["lon"], element["lat"])

    if etype == "relation":
        relation_geom = relation_boundary_geometry(element)
        if relation_geom is not None:
            return relation_geom

    if isinstance(geometry, list) and geometry:
        coords = _coords_from_geometry(geometry)
        if len(coords) >= 4 and coords[0] == coords[-1]:
            return Polygon(coords)
        if len(coords) >= 2:
            return LineString(coords)
    return None


def write_shops_geojson(path: Path) -> None:
    shop_pattern = "|".join(SHOP_TYPES)
    query = f"""
[out:json][timeout:180];
area["ISO3166-1"="HU"][admin_level=2]->.country;
(
  node["shop"~"^({shop_pattern})$"](area.country);
  way["shop"~"^({shop_pattern})$"](area.country);
  relation["shop"~"^({shop_pattern})$"](area.country);
);
out body center geom;
"""

    features = []
    for element in query_overpass(query):
        point = representative_point_from_element(element)
        if point is None:
            continue
        tags = element.get("tags", {})
        features.append(
            {
                "geometry": point,
                "shop": tags.get("shop"),
            }
        )

    if not features:
        raise RuntimeError(
            "No shop features were parsed from Overpass response. "
            "Check if Overpass returned expected geometry."
        )

    gdf = gpd.GeoDataFrame(features, geometry="geometry", crs=CRS)
    gdf.to_file(path, driver="GeoJSON")


def write_settlements_geojson(path: Path) -> None:
    query = """
[out:json][timeout:180];
area["ISO3166-1"="HU"][admin_level=2]->.country;
(
  relation["boundary"="administrative"]["admin_level"="8"](area.country);
  way["boundary"="administrative"]["admin_level"="8"](area.country);
);
out body geom;
"""

    features = []
    for element in query_overpass(query):
        geom = settlement_geometry_from_element(element)
        if geom is None:
            continue
        tags = element.get("tags", {})
        features.append(
            {
                "geometry": geom,
                "name": tags.get("name"),
                "ksh_ref": tags.get("ksh_ref"),
            }
        )

    if not features:
        raise RuntimeError(
            "No settlement boundaries were parsed from Overpass response. "
            "Check if relation/way geometries are present in response."
        )

    gdf = gpd.GeoDataFrame(features, geometry="geometry", crs=CRS)
    gdf.to_file(path, driver="GeoJSON")


def main() -> None:
    ensure_data_dir()

    if is_valid_cache(SHOPS_PATH):
        print(f"Using cache: {SHOPS_PATH}")
    else:
        print("Downloading shops from Overpass...")
        write_shops_geojson(SHOPS_PATH)
        print(f"Wrote {SHOPS_PATH}")

    if is_valid_cache(SETTLEMENTS_PATH):
        print(f"Using cache: {SETTLEMENTS_PATH}")
    else:
        print("Downloading settlements from Overpass...")
        write_settlements_geojson(SETTLEMENTS_PATH)
        print(f"Wrote {SETTLEMENTS_PATH}")


if __name__ == "__main__":
    main()
