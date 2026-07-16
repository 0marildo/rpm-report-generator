import io
import unittest

from PIL import Image

from report_agent.services.image_layout_engine import ImageLayoutEngine


def image_bytes(width: int = 1600, height: int = 900) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(buffer, format="PNG")
    return buffer.getvalue()


class ImageLayoutEngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = ImageLayoutEngine()

    def solve(self, count: int, *, height: float = 600):
        return self.engine.solve(
            [{"data": image_bytes(), "filename": f"{index}.png"} for index in range(count)],
            x=35,
            y=100,
            width=525,
            height=height,
        )

    def test_single_image_uses_ninety_percent_of_flow_width(self):
        layout = self.solve(1)
        rect = layout.placed[0].rect_coords
        self.assertAlmostEqual(rect[2] - rect[0], 525 * 0.90)
        self.assertFalse(layout.page_break_recommendation)

    def test_two_images_use_balanced_columns(self):
        layout = self.solve(2)
        first, second = layout.placed
        self.assertAlmostEqual(first.rect_coords[2] - first.rect_coords[0], second.rect_coords[2] - second.rect_coords[0])
        self.assertAlmostEqual(first.rect_coords[1], second.rect_coords[1])

    def test_three_images_center_the_final_row(self):
        layout = self.solve(3)
        first, _, last = layout.placed
        self.assertGreater(last.rect_coords[1], first.rect_coords[1])
        self.assertAlmostEqual((last.rect_coords[0] + last.rect_coords[2]) / 2, 35 + 525 / 2)

    def test_four_images_form_symmetric_grid_and_fifth_paginates(self):
        layout = self.solve(5)
        self.assertEqual(len(layout.placed), 4)
        self.assertEqual(len(layout.remaining), 1)
        self.assertAlmostEqual(layout.placed[0].rect_coords[2] - layout.placed[0].rect_coords[0], layout.placed[3].rect_coords[2] - layout.placed[3].rect_coords[0])

    def test_insufficient_remaining_space_requests_page_break_instead_of_shrinking(self):
        layout = self.solve(4, height=20)
        self.assertTrue(layout.page_break_recommendation)
        self.assertEqual(len(layout.placed), 0)


if __name__ == "__main__":
    unittest.main()
