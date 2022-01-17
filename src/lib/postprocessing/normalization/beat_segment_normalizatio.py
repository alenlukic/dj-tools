"""
1. Run beat tracking procedure over entire audio file
2. Create segments based on a threshold distance between beats (e.g. > 1 second)
3. Apply normalization across window segments with exponential backoff (e.g. assuming n total segments, normalize
first across all n segments, then n / 2, n / 4, ... n / log2(n))
"""

import sys
from aubio import source, onset

win_s = 512                 # fft size
hop_s = win_s // 2          # hop size

if len(sys.argv) < 2:
    print("Usage: %s <filename> [samplerate]" % sys.argv[0])
    sys.exit(1)

filename = sys.argv[1]

samplerate = 0
if len( sys.argv ) > 2: samplerate = int(sys.argv[2])

s = source(filename, samplerate, hop_s)
samplerate = s.samplerate

o = onset("default", win_s, hop_s, samplerate)

# list of onsets, in samples
onsets = []

# total number of frames read
total_frames = 0
while True:
    samples, read = s()
    if o(samples):
        print("%f" % o.get_last_s())
        onsets.append(o.get_last())
    total_frames += read
    if read < hop_s: break