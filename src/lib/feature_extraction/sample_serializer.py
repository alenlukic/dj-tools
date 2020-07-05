import librosa
import json
from os.path import join, exists

from src.definitions.feature_extraction import SAMPLE_RATE, SerializationKeys, SERIALIZED_SAMPLE_DIR
from src.utils.errors import handle_error


def serialize(tracks):
    """ TODO. """

    for track in tracks:
        try:
            track_id = str(track.id)
            output_path = join(SERIALIZED_SAMPLE_DIR, track_id)

            if exists(output_path):
                continue

            file_path = track.file_path
            title = track.title
            samples, _ = librosa.load(file_path, SAMPLE_RATE)

            with open(output_path, 'w') as fp:
                payload = {
                    SerializationKeys.TRACK_ID.value: track_id,
                    SerializationKeys.TRACK_TITLE.value: title,
                    SerializationKeys.SAMPLES.value: str(list(samples))
                }
                json.dump(payload, fp, indent=2)

        except Exception as e:
            handle_error(e)
            continue
