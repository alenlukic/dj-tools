import base64
from collections import defaultdict
import json
import librosa
import numpy as np
import sklearn

from src.db import database
from src.db.entities.track import Track
from src.definitions.feature_extraction import SAMPLE_RATE
from src.lib.feature_extraction.track_feature import Feature


