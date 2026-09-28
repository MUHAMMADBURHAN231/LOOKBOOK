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

## Clips in use

Generated with FLUX 3 Video (1080p, 5 s, 9:16, no audio) on Higgsfield, each from one look to the
next as start and end frames, in project "LOOKBOOK landing: dressing sequence":

1. base to blouse: job `59096ef3-3aba-4604-8821-2ff164493c2b`
2. blouse to blazer: job `84815cb3-7480-47f6-a0c1-92796cf8371d`
3. blazer to coat: job `91b85372-eb85-46b0-a617-3f92262d8f51`

Built with the defaults (24 fps, 720 px wide, 6 frames blended at each join): 351 frames, 5.3 MB.
