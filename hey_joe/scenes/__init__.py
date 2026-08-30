"""Scene registry."""

from hey_joe.scenes.base import Scene
from hey_joe.scenes.nada import NadaScene
from hey_joe.scenes.enigma import EnigmaScene
from hey_joe.scenes.raudra import RaudraScene
from hey_joe.scenes.paisley import PaisleyScene
from hey_joe.scenes.confession import ConfessionScene
from hey_joe.scenes.jhala import JhalaScene
from hey_joe.scenes.desert import DesertScene
from hey_joe.scenes.wings import WingsScene
from hey_joe.scenes.samadhi import SamadhiScene

SCENE_CLASSES = {
    "nada": NadaScene,
    "enigma": EnigmaScene,
    "raudra": RaudraScene,
    "paisley": PaisleyScene,
    "confession": ConfessionScene,
    "jhala": JhalaScene,
    "desert": DesertScene,
    "wings": WingsScene,
    "samadhi": SamadhiScene,
}

__all__ = [
    "Scene",
    "SCENE_CLASSES",
    "NadaScene",
    "EnigmaScene",
    "RaudraScene",
    "PaisleyScene",
    "ConfessionScene",
    "JhalaScene",
    "DesertScene",
    "WingsScene",
    "SamadhiScene",
]
