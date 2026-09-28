# Landing video source frames

The four looks used as start and end frames for the landing-page video transitions, aligned to one
1080x1920 frame: the top of the head at 11% of the height, the feet at 90.5%, the head centred and
the backdrop matched to the page colour (#F8F7F5).

1. `0-base.jpg`: white T-shirt and trousers
2. `1-blouse.jpg`: silk blouse
3. `2-blazer.jpg`: black blazer
4. `3-coat.jpg`: camel overcoat

Each video clip goes from one look to the next (0 to 1, 1 to 2, 2 to 3). Build the page frames
with `python scripts/build_scroll_video.py clip1.mp4 clip2.mp4 clip3.mp4`.
