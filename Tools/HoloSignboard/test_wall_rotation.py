"""Pixel-level regression: baked Graphic_Multi directions must be rigid rotations."""

import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
TEXTURES = ROOT / "Textures/Things/Building/WallHoloSignboard"


class WallRotationTests(unittest.TestCase):
    def test_baked_directions_are_exact_rotations_not_retypeset_or_mirrored(self):
        for layer in ("Base", "Hologram"):
            north = Image.open(
                TEXTURES / f"WallHoloSignboard{layer}_north.png"
            ).convert("RGBA")
            for direction, operation in (
                ("east", Image.Transpose.ROTATE_270),
                ("south", Image.Transpose.ROTATE_180),
                ("west", Image.Transpose.ROTATE_90),
            ):
                with self.subTest(layer=layer, direction=direction):
                    actual = Image.open(
                        TEXTURES / f"WallHoloSignboard{layer}_{direction}.png"
                    ).convert("RGBA")
                    self.assertEqual(
                        actual.tobytes(), north.transpose(operation).tobytes()
                    )

    def test_visible_projection_is_narrow_in_world_units(self):
        for direction in ("north", "east", "south", "west"):
            image = Image.open(TEXTURES / f"WallHoloSignboardHologram_{direction}.png")
            bbox = image.getchannel("A").getbbox()
            self.assertIsNotNone(bbox)
            dimensions = sorted(
                (
                    (bbox[2] - bbox[0]) * 2.6 / image.width,
                    (bbox[3] - bbox[1]) * 2.6 / image.height,
                )
            )
            with self.subTest(direction=direction):
                self.assertGreater(dimensions[0], 0.18)
                self.assertLessEqual(dimensions[0], 0.30)
                self.assertGreater(dimensions[1], 0.95)
                self.assertLess(dimensions[1], 1.10)


if __name__ == "__main__":
    unittest.main()
