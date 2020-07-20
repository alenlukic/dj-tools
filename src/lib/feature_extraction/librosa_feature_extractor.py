# class LibrosaFeatureExtractor:
#     def __init__(self, track_ids):
#         self.session = database.create_session()
#         # noinspection PyUnresolvedReferences
#         self.tracks = self.session.query(Track).filter(Track.id.in_(track_ids)).all()
#         self.features = defaultdict(dict)
#
#     def extract_features(self):
#         for track in self.tracks:
#             print(track.file_path)
#             samples, _ = librosa.load(track.file_path, SAMPLE_RATE)
#             samples = samples[0:SAMPLE_RATE * 15]
#             self.features[track.id]['zero_crossing_rate'] = self.get_zero_crossing_rate(samples)
#             self.features[track.id]['spectral_centroid'] = self.get_spectral_centroid(samples)
#             self.features[track.id]['mel_fequency_coeffs'] = self.get_mel_fequency_coeffs(samples)
#             self.features[track.id]['chroma_frequencies'] = self.get_chroma_frequencies(samples)
#
#     def get_zero_crossing_rate(self, samples):
#         return librosa.zero_crossings(samples, pad=False).tolist()
#
#     def get_spectral_centroid(self, samples):
#         return librosa.feature.spectral_centroid(samples, sr=SAMPLE_RATE).tolist()
#
#     def get_mel_fequency_coeffs(self, samples):
#         return sklearn.preprocessing.scale(librosa.feature.mfcc(samples, sr=SAMPLE_RATE), axis=1).tolist()
#
#     def get_chroma_frequencies(self, samples):
#         return librosa.feature.chroma_cqt(samples, sr=SAMPLE_RATE).tolist()

