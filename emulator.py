"""Pygame-based LED matrix emulator — shows exactly what the hardware displays."""

import sys
import numpy as np
import pygame
from PIL import Image

from display import FlightDisplay, DISPLAY_WIDTH, DISPLAY_HEIGHT
from main import FlightTracker

# ── Configuration ─────────────────────────────────────────────────
SCALE = 8  # each LED pixel becomes SCALE×SCALE screen pixels
GRID_COLOR = (15, 15, 15)  # thin dark lines between pixels
WINDOW_WIDTH = DISPLAY_WIDTH * SCALE  # 1024
WINDOW_HEIGHT = DISPLAY_HEIGHT * SCALE  # 256


class EmulatedDisplay(FlightDisplay):
    """FlightDisplay subclass that renders to a pygame window instead of hardware."""

    def _init_matrix(self) -> None:
        """Initialize pygame display instead of RGB matrix hardware."""
        pygame.init()
        self._screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("Flight Tracker LED Emulator")
        self._screen.fill((0, 0, 0))
        pygame.display.flip()

    def _show_image(self, img: Image.Image) -> None:
        """Convert Pillow Image to pygame surface with scaled-up pixel grid."""
        # Handle pygame quit events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit(0)

        # Convert Pillow RGB image to numpy array, then scale up
        arr = np.array(img)  # (32, 128, 3)

        # Create the scaled surface
        surface = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT))
        surface.fill((0, 0, 0))

        # Scale each pixel and draw grid lines
        for y in range(DISPLAY_HEIGHT):
            for x in range(DISPLAY_WIDTH):
                r, g, b = arr[y, x]
                if r > 0 or g > 0 or b > 0:
                    # Draw the pixel as a filled rect (1px smaller for grid gap)
                    pygame.draw.rect(
                        surface,
                        (int(r), int(g), int(b)),
                        (x * SCALE + 1, y * SCALE + 1, SCALE - 1, SCALE - 1),
                    )
                else:
                    # Draw grid lines even for dark pixels
                    pygame.draw.rect(
                        surface,
                        GRID_COLOR,
                        (x * SCALE, y * SCALE, SCALE, SCALE),
                        1,
                    )

        self._screen.blit(surface, (0, 0))
        pygame.display.flip()

    def clear(self) -> None:
        """Clear the emulated display."""
        self._screen.fill((0, 0, 0))
        pygame.display.flip()

    def shutdown(self) -> None:
        """Show goodbye, then close pygame."""
        self.show_status("Goodbye!")
        pygame.time.wait(1000)
        self.clear()
        pygame.quit()


def main() -> None:
    display = EmulatedDisplay()
    tracker = FlightTracker(display=display)
    tracker.run()


if __name__ == "__main__":
    main()
