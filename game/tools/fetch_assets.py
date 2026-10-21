#!/usr/bin/env python3
"""Download the CC0 Poly Haven assets BugWorld uses (1k). Run: python3 tools/fetch_assets.py"""
import json, os, urllib.request
op = urllib.request.build_opener(); op.addheaders = [("User-Agent","BugWorld-asset-fetch/1.0")]
urllib.request.install_opener(op)
API = "https://api.polyhaven.com/files/"
MODELS = ["gothic_statue","marble_bust_01","chess_set","wooden_candlestick","fern_02","grass_medium_01","dandelion_01",
  "tree_stump_01","dead_tree_trunk","boulder_01","rock_moss_set_01","wooden_barrels_01","tea_set_01",
  "vintage_oil_lamp","treasure_chest","root_cluster_01","garden_gnome","painted_wooden_chair_01","vintage_grandfather_clock_01"]
TEXTURES = ["forest_ground_04","leaves_forest_ground","mossy_brick_floor","wood_floor_worn","marble_tiles","rock_pitted_mossy"]
HDRIS = ["dark_autumn_forest"]
def get(url, dest):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if not os.path.exists(dest):
        urllib.request.urlretrieve(url, dest)
def files(id): return json.load(urllib.request.urlopen(API + id))
for m in MODELS:
    g = files(m)["gltf"]["1k"]["gltf"]
    d = f"assets/models/{m}"; get(g["url"], f"{d}/{m}.gltf")
    for rel, f in g["include"].items(): get(f["url"], f"{d}/{rel}")
    print("model", m)
for t in TEXTURES:
    j = files(t)
    for k, name in (("Diffuse","diff"),("nor_gl","nor"),("arm","arm")):
        get(j[k]["1k"]["jpg"]["url"], f"assets/tex/{t}_{name}.jpg")
    print("tex", t)
for h in HDRIS:
    get(files(h)["hdri"]["1k"]["hdr"]["url"], f"assets/hdri/{h}.hdr"); print("hdri", h)
