from __future__ import annotations

from pydantic import BaseModel


class ImageTile(BaseModel):
    id: str
    x: int
    y: int
    width: int
    height: int


def generate_grid_tiles(width: int, height: int, rows: int = 2, cols: int = 2) -> list[ImageTile]:
    tile_width = width // cols
    tile_height = height // rows
    tiles: list[ImageTile] = []
    for row in range(rows):
        for col in range(cols):
            x = col * tile_width
            y = row * tile_height
            w = width - x if col == cols - 1 else tile_width
            h = height - y if row == rows - 1 else tile_height
            tiles.append(ImageTile(id=f"tile_{row}_{col}", x=x, y=y, width=w, height=h))
    return tiles
