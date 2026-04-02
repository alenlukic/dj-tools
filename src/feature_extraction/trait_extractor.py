"""Trait extractor: mel preprocessing + ONNX embedding + classification heads.

Computes all Phase I semantic traits for a single audio file:
- Binary classifiers → float P(positive class)
- Multi-label classifiers → {label: probability} dict above threshold
- Genre from MAEST backbone output (519-class Discogs taxonomy)
- librosa extras: onset_density, spectral_flatness

ONNX sessions are loaded once per TraitExtractor instance (expensive). Create
one instance per worker process and reuse it across tracks.

Usage:
    extractor = TraitExtractor()
    traits = extractor.compute("/path/to/track.mp3")
"""

import numpy as np

try:
    import librosa
except ImportError as exc:
    raise ImportError("librosa is required for trait extraction") from exc

from src.feature_extraction import model_manager
from src.feature_extraction.config import (
    TRAIT_CLASSIFIER_MAEST,
    TRAIT_CLASSIFIERS_EFFNET,
    TRAIT_PREDICTION_THRESHOLD,
    TRAIT_SAMPLE_RATE,
    TRAIT_VERSION,
)


# EffNet input: 128 time frames × 96 mel bands per window
_EFFNET_FRAMES = 128
# Step between windows (50 % overlap)
_EFFNET_HOP = 64

# MAEST input: 1876 time frames × 96 mel bands (≈30 s at 16 kHz, hop 256)
_MAEST_FRAMES = 1876
# Step between windows (no overlap — one patch per 30 s segment)
_MAEST_HOP = 1875

# ------------------------------------------------------------------ #
# Label constants (fetched from essentia.upf.edu JSON metadata)       #
# ------------------------------------------------------------------ #

LABELS_MOOD_THEME = [
    "action",
    "adventure",
    "advertising",
    "background",
    "ballad",
    "calm",
    "children",
    "christmas",
    "commercial",
    "cool",
    "corporate",
    "dark",
    "deep",
    "documentary",
    "drama",
    "dramatic",
    "dream",
    "emotional",
    "energetic",
    "epic",
    "fast",
    "film",
    "fun",
    "funny",
    "game",
    "groovy",
    "happy",
    "heavy",
    "holiday",
    "hopeful",
    "inspiring",
    "love",
    "meditative",
    "melancholic",
    "melodic",
    "motivational",
    "movie",
    "nature",
    "party",
    "positive",
    "powerful",
    "relaxing",
    "retro",
    "romantic",
    "sad",
    "sexy",
    "slow",
    "soft",
    "soundscape",
    "space",
    "sport",
    "summer",
    "trailer",
    "travel",
    "upbeat",
    "uplifting",
]  # 56 classes — MTG Jamendo Mood/Theme

LABELS_INSTRUMENT = [
    "accordion",
    "acousticbassguitar",
    "acousticguitar",
    "bass",
    "beat",
    "bell",
    "bongo",
    "brass",
    "cello",
    "clarinet",
    "classicalguitar",
    "computer",
    "doublebass",
    "drummachine",
    "drums",
    "electricguitar",
    "electricpiano",
    "flute",
    "guitar",
    "harmonica",
    "harp",
    "horn",
    "keyboard",
    "oboe",
    "orchestra",
    "organ",
    "pad",
    "percussion",
    "piano",
    "pipeorgan",
    "rhodes",
    "sampler",
    "saxophone",
    "strings",
    "synthesizer",
    "trombone",
    "trumpet",
    "viola",
    "violin",
    "voice",
]  # 40 classes — MTG Jamendo Instrument

LABELS_GENRE_DISCOGS519 = [
    "Blues---Boogie Woogie",
    "Blues---Chicago Blues",
    "Blues---Country Blues",
    "Blues---Delta Blues",
    "Blues---East Coast Blues",
    "Blues---Electric Blues",
    "Blues---Harmonica Blues",
    "Blues---Jump Blues",
    "Blues---Louisiana Blues",
    "Blues---Memphis Blues",
    "Blues---Modern Electric Blues",
    "Blues---Piano Blues",
    "Blues---Piedmont Blues",
    "Blues---Rhythm & Blues",
    "Blues---Texas Blues",
    "Brass & Military---Brass Band",
    "Brass & Military---Marches",
    "Brass & Military---Military",
    "Brass & Military---Pipe & Drum",
    "Children's---Educational",
    "Children's---Nursery Rhymes",
    "Children's---Story",
    "Classical---Baroque",
    "Classical---Choral",
    "Classical---Classical",
    "Classical---Contemporary",
    "Classical---Early",
    "Classical---Impressionist",
    "Classical---Medieval",
    "Classical---Modern",
    "Classical---Neo-Classical",
    "Classical---Neo-Romantic",
    "Classical---Opera",
    "Classical---Operetta",
    "Classical---Oratorio",
    "Classical---Post-Modern",
    "Classical---Renaissance",
    "Classical---Romantic",
    "Classical---Twelve-tone",
    "Electronic---Abstract",
    "Electronic---Acid",
    "Electronic---Acid House",
    "Electronic---Acid Jazz",
    "Electronic---Ambient",
    "Electronic---Baltimore Club",
    "Electronic---Bassline",
    "Electronic---Beatdown",
    "Electronic---Berlin-School",
    "Electronic---Big Beat",
    "Electronic---Bleep",
    "Electronic---Breakbeat",
    "Electronic---Breakcore",
    "Electronic---Breaks",
    "Electronic---Broken Beat",
    "Electronic---Chillwave",
    "Electronic---Chiptune",
    "Electronic---Dance-pop",
    "Electronic---Dark Ambient",
    "Electronic---Darkwave",
    "Electronic---Deep House",
    "Electronic---Deep Techno",
    "Electronic---Disco",
    "Electronic---Disco Polo",
    "Electronic---Donk",
    "Electronic---Doomcore",
    "Electronic---Downtempo",
    "Electronic---Drone",
    "Electronic---Drum n Bass",
    "Electronic---Dub",
    "Electronic---Dub Techno",
    "Electronic---Dubstep",
    "Electronic---Dungeon Synth",
    "Electronic---EBM",
    "Electronic---Electro",
    "Electronic---Electro House",
    "Electronic---Electroacoustic",
    "Electronic---Electroclash",
    "Electronic---Euro House",
    "Electronic---Euro-Disco",
    "Electronic---Eurobeat",
    "Electronic---Eurodance",
    "Electronic---Experimental",
    "Electronic---Footwork",
    "Electronic---Freestyle",
    "Electronic---Future Jazz",
    "Electronic---Gabber",
    "Electronic---Garage House",
    "Electronic---Ghetto",
    "Electronic---Ghetto House",
    "Electronic---Ghettotech",
    "Electronic---Glitch",
    "Electronic---Glitch Hop",
    "Electronic---Goa Trance",
    "Electronic---Grime",
    "Electronic---Halftime",
    "Electronic---Hands Up",
    "Electronic---Happy Hardcore",
    "Electronic---Hard Beat",
    "Electronic---Hard House",
    "Electronic---Hard Techno",
    "Electronic---Hard Trance",
    "Electronic---Hardcore",
    "Electronic---Hardstyle",
    "Electronic---Harsh Noise Wall",
    "Electronic---Hi NRG",
    "Electronic---Hip Hop",
    "Electronic---Hip-House",
    "Electronic---House",
    "Electronic---IDM",
    "Electronic---Illbient",
    "Electronic---Industrial",
    "Electronic---Italo House",
    "Electronic---Italo-Disco",
    "Electronic---Italodance",
    "Electronic---J-Core",
    "Electronic---Jazzdance",
    "Electronic---Juke",
    "Electronic---Jumpstyle",
    "Electronic---Jungle",
    "Electronic---Latin",
    "Electronic---Leftfield",
    "Electronic---Lento Violento",
    "Electronic---Makina",
    "Electronic---Minimal",
    "Electronic---Minimal Techno",
    "Electronic---Modern Classical",
    "Electronic---Musique Concrète",
    "Electronic---Neo Trance",
    "Electronic---Neofolk",
    "Electronic---New Age",
    "Electronic---New Beat",
    "Electronic---New Wave",
    "Electronic---Noise",
    "Electronic---Nu-Disco",
    "Electronic---Power Electronics",
    "Electronic---Progressive Breaks",
    "Electronic---Progressive House",
    "Electronic---Progressive Trance",
    "Electronic---Psy-Trance",
    "Electronic---Rhythmic Noise",
    "Electronic---Schranz",
    "Electronic---Sound Collage",
    "Electronic---Speed Garage",
    "Electronic---Speedcore",
    "Electronic---Synth-pop",
    "Electronic---Synthwave",
    "Electronic---Tech House",
    "Electronic---Tech Trance",
    "Electronic---Techno",
    "Electronic---Trance",
    "Electronic---Tribal",
    "Electronic---Tribal House",
    "Electronic---Trip Hop",
    "Electronic---Tropical House",
    "Electronic---UK Funky",
    "Electronic---UK Garage",
    "Electronic---Vaporwave",
    "Electronic---Witch House",
    "Folk, World, & Country---Aboriginal",
    "Folk, World, & Country---African",
    "Folk, World, & Country---Andalusian Classical",
    "Folk, World, & Country---Andean Music",
    "Folk, World, & Country---Appalachian Music",
    "Folk, World, & Country---Basque Music",
    "Folk, World, & Country---Bhangra",
    "Folk, World, & Country---Bluegrass",
    "Folk, World, & Country---Cajun",
    "Folk, World, & Country---Canzone Napoletana",
    "Folk, World, & Country---Carnatic",
    "Folk, World, & Country---Catalan Music",
    "Folk, World, & Country---Celtic",
    "Folk, World, & Country---Chacarera",
    "Folk, World, & Country---Chinese Classical",
    "Folk, World, & Country---Chutney",
    "Folk, World, & Country---Copla",
    "Folk, World, & Country---Country",
    "Folk, World, & Country---Cretan",
    "Folk, World, & Country---Dangdut",
    "Folk, World, & Country---Fado",
    "Folk, World, & Country---Flamenco",
    "Folk, World, & Country---Folk",
    "Folk, World, & Country---Funaná",
    "Folk, World, & Country---Gamelan",
    "Folk, World, & Country---Ghazal",
    "Folk, World, & Country---Gospel",
    "Folk, World, & Country---Griot",
    "Folk, World, & Country---Hawaiian",
    "Folk, World, & Country---Highlife",
    "Folk, World, & Country---Hillbilly",
    "Folk, World, & Country---Hindustani",
    "Folk, World, & Country---Honky Tonk",
    "Folk, World, & Country---Indian Classical",
    "Folk, World, & Country---Kaseko",
    "Folk, World, & Country---Klezmer",
    "Folk, World, & Country---Laïkó",
    "Folk, World, & Country---Luk Thung",
    "Folk, World, & Country---Maloya",
    "Folk, World, & Country---Mbalax",
    "Folk, World, & Country---Min'yō",
    "Folk, World, & Country---Mizrahi",
    "Folk, World, & Country---Nhạc Vàng",
    "Folk, World, & Country---Nordic",
    "Folk, World, & Country---Népzene",
    "Folk, World, & Country---Ottoman Classical",
    "Folk, World, & Country---Overtone Singing",
    "Folk, World, & Country---Pacific",
    "Folk, World, & Country---Pasodoble",
    "Folk, World, & Country---Persian Classical",
    "Folk, World, & Country---Phleng Phuea Chiwit",
    "Folk, World, & Country---Polka",
    "Folk, World, & Country---Qawwali",
    "Folk, World, & Country---Raï",
    "Folk, World, & Country---Rebetiko",
    "Folk, World, & Country---Romani",
    "Folk, World, & Country---Salegy",
    "Folk, World, & Country---Sea Shanties",
    "Folk, World, & Country---Soukous",
    "Folk, World, & Country---Séga",
    "Folk, World, & Country---Volksmusik",
    "Folk, World, & Country---Western Swing",
    "Folk, World, & Country---Zouk",
    "Folk, World, & Country---Zydeco",
    "Folk, World, & Country---Éntekhno",
    "Funk / Soul---Afrobeat",
    "Funk / Soul---Bayou Funk",
    "Funk / Soul---Boogie",
    "Funk / Soul---Contemporary R&B",
    "Funk / Soul---Disco",
    "Funk / Soul---Free Funk",
    "Funk / Soul---Funk",
    "Funk / Soul---Gogo",
    "Funk / Soul---Gospel",
    "Funk / Soul---Minneapolis Sound",
    "Funk / Soul---Neo Soul",
    "Funk / Soul---New Jack Swing",
    "Funk / Soul---P.Funk",
    "Funk / Soul---Psychedelic",
    "Funk / Soul---Rhythm & Blues",
    "Funk / Soul---Soul",
    "Funk / Soul---Swingbeat",
    "Funk / Soul---UK Street Soul",
    "Hip Hop---Bass Music",
    "Hip Hop---Beatbox",
    "Hip Hop---Boom Bap",
    "Hip Hop---Bounce",
    "Hip Hop---Britcore",
    "Hip Hop---Cloud Rap",
    "Hip Hop---Conscious",
    "Hip Hop---Crunk",
    "Hip Hop---Cut-up/DJ",
    "Hip Hop---DJ Battle Tool",
    "Hip Hop---Electro",
    "Hip Hop---Favela Funk",
    "Hip Hop---G-Funk",
    "Hip Hop---Gangsta",
    "Hip Hop---Go-Go",
    "Hip Hop---Grime",
    "Hip Hop---Hardcore Hip-Hop",
    "Hip Hop---Hiplife",
    "Hip Hop---Horrorcore",
    "Hip Hop---Hyphy",
    "Hip Hop---Instrumental",
    "Hip Hop---Jazzy Hip-Hop",
    "Hip Hop---Kwaito",
    "Hip Hop---Miami Bass",
    "Hip Hop---Pop Rap",
    "Hip Hop---Ragga HipHop",
    "Hip Hop---RnB/Swing",
    "Hip Hop---Screw",
    "Hip Hop---Thug Rap",
    "Hip Hop---Trap",
    "Hip Hop---Trip Hop",
    "Hip Hop---Turntablism",
    "Jazz---Afro-Cuban Jazz",
    "Jazz---Afrobeat",
    "Jazz---Avant-garde Jazz",
    "Jazz---Big Band",
    "Jazz---Bop",
    "Jazz---Bossa Nova",
    "Jazz---Cape Jazz",
    "Jazz---Contemporary Jazz",
    "Jazz---Cool Jazz",
    "Jazz---Dixieland",
    "Jazz---Easy Listening",
    "Jazz---Free Improvisation",
    "Jazz---Free Jazz",
    "Jazz---Fusion",
    "Jazz---Gypsy Jazz",
    "Jazz---Hard Bop",
    "Jazz---Jazz-Funk",
    "Jazz---Jazz-Rock",
    "Jazz---Latin Jazz",
    "Jazz---Modal",
    "Jazz---Post Bop",
    "Jazz---Ragtime",
    "Jazz---Smooth Jazz",
    "Jazz---Soul-Jazz",
    "Jazz---Space-Age",
    "Jazz---Swing",
    "Latin---Afro-Cuban",
    "Latin---Axé",
    "Latin---Bachata",
    "Latin---Baião",
    "Latin---Batucada",
    "Latin---Beguine",
    "Latin---Bolero",
    "Latin---Boogaloo",
    "Latin---Bossanova",
    "Latin---Carimbó",
    "Latin---Cha-Cha",
    "Latin---Charanga",
    "Latin---Choro",
    "Latin---Compas",
    "Latin---Conjunto",
    "Latin---Corrido",
    "Latin---Cubano",
    "Latin---Cumbia",
    "Latin---Danzon",
    "Latin---Descarga",
    "Latin---Forró",
    "Latin---Gaita",
    "Latin---Guaguancó",
    "Latin---Guajira",
    "Latin---Guaracha",
    "Latin---Jibaro",
    "Latin---Lambada",
    "Latin---MPB",
    "Latin---Mambo",
    "Latin---Mariachi",
    "Latin---Marimba",
    "Latin---Merengue",
    "Latin---Música Criolla",
    "Latin---Norteño",
    "Latin---Nueva Cancion",
    "Latin---Nueva Trova",
    "Latin---Pachanga",
    "Latin---Plena",
    "Latin---Porro",
    "Latin---Quechua",
    "Latin---Ranchera",
    "Latin---Reggaeton",
    "Latin---Rumba",
    "Latin---Salsa",
    "Latin---Samba",
    "Latin---Samba-Canção",
    "Latin---Son",
    "Latin---Son Montuno",
    "Latin---Sonero",
    "Latin---Tango",
    "Latin---Tejano",
    "Latin---Timba",
    "Latin---Trova",
    "Latin---Vallenato",
    "Non-Music---Audiobook",
    "Non-Music---Comedy",
    "Non-Music---Dialogue",
    "Non-Music---Education",
    "Non-Music---Erotic",
    "Non-Music---Field Recording",
    "Non-Music---Health-Fitness",
    "Non-Music---Interview",
    "Non-Music---Monolog",
    "Non-Music---Movie Effects",
    "Non-Music---Poetry",
    "Non-Music---Political",
    "Non-Music---Promotional",
    "Non-Music---Public Broadcast",
    "Non-Music---Radioplay",
    "Non-Music---Religious",
    "Non-Music---Sermon",
    "Non-Music---Sound Art",
    "Non-Music---Sound Poetry",
    "Non-Music---Special Effects",
    "Non-Music---Speech",
    "Non-Music---Spoken Word",
    "Non-Music---Technical",
    "Non-Music---Therapy",
    "Pop---Ballad",
    "Pop---Barbershop",
    "Pop---Bollywood",
    "Pop---Break-In",
    "Pop---Bubblegum",
    "Pop---Chanson",
    "Pop---City Pop",
    "Pop---Enka",
    "Pop---Ethno-pop",
    "Pop---Europop",
    "Pop---Indie Pop",
    "Pop---J-pop",
    "Pop---K-pop",
    "Pop---Karaoke",
    "Pop---Kayōkyoku",
    "Pop---Levenslied",
    "Pop---Light Music",
    "Pop---Music Hall",
    "Pop---Novelty",
    "Pop---Parody",
    "Pop---Schlager",
    "Pop---Vocal",
    "Reggae---Calypso",
    "Reggae---Dancehall",
    "Reggae---Dub",
    "Reggae---Dub Poetry",
    "Reggae---Lovers Rock",
    "Reggae---Mento",
    "Reggae---Ragga",
    "Reggae---Reggae",
    "Reggae---Reggae Gospel",
    "Reggae---Reggae-Pop",
    "Reggae---Rocksteady",
    "Reggae---Roots Reggae",
    "Reggae---Ska",
    "Reggae---Soca",
    "Reggae---Steel Band",
    "Rock---AOR",
    "Rock---Acid Rock",
    "Rock---Acoustic",
    "Rock---Alternative Rock",
    "Rock---Arena Rock",
    "Rock---Art Rock",
    "Rock---Atmospheric Black Metal",
    "Rock---Avantgarde",
    "Rock---Beat",
    "Rock---Black Metal",
    "Rock---Blues Rock",
    "Rock---Brit Pop",
    "Rock---Classic Rock",
    "Rock---Coldwave",
    "Rock---Country Rock",
    "Rock---Crust",
    "Rock---Death Metal",
    "Rock---Deathcore",
    "Rock---Deathrock",
    "Rock---Depressive Black Metal",
    "Rock---Doo Wop",
    "Rock---Doom Metal",
    "Rock---Dream Pop",
    "Rock---Emo",
    "Rock---Ethereal",
    "Rock---Experimental",
    "Rock---Folk Metal",
    "Rock---Folk Rock",
    "Rock---Funeral Doom Metal",
    "Rock---Funk Metal",
    "Rock---Garage Rock",
    "Rock---Glam",
    "Rock---Goregrind",
    "Rock---Goth Rock",
    "Rock---Gothic Metal",
    "Rock---Grindcore",
    "Rock---Groove Metal",
    "Rock---Grunge",
    "Rock---Hard Rock",
    "Rock---Hardcore",
    "Rock---Heavy Metal",
    "Rock---Horror Rock",
    "Rock---Indie Rock",
    "Rock---Industrial",
    "Rock---Industrial Metal",
    "Rock---J-Rock",
    "Rock---Jangle Pop",
    "Rock---K-Rock",
    "Rock---Krautrock",
    "Rock---Lo-Fi",
    "Rock---Lounge",
    "Rock---Math Rock",
    "Rock---Melodic Death Metal",
    "Rock---Melodic Hardcore",
    "Rock---Metalcore",
    "Rock---Mod",
    "Rock---NDW",
    "Rock---Neofolk",
    "Rock---New Wave",
    "Rock---No Wave",
    "Rock---Noise",
    "Rock---Noisecore",
    "Rock---Nu Metal",
    "Rock---Oi",
    "Rock---Parody",
    "Rock---Pop Punk",
    "Rock---Pop Rock",
    "Rock---Pornogrind",
    "Rock---Post Rock",
    "Rock---Post-Hardcore",
    "Rock---Post-Metal",
    "Rock---Post-Punk",
    "Rock---Power Metal",
    "Rock---Power Pop",
    "Rock---Power Violence",
    "Rock---Prog Rock",
    "Rock---Progressive Metal",
    "Rock---Psychedelic Rock",
    "Rock---Psychobilly",
    "Rock---Pub Rock",
    "Rock---Punk",
    "Rock---Rock & Roll",
    "Rock---Rock Opera",
    "Rock---Rockabilly",
    "Rock---Shoegaze",
    "Rock---Ska",
    "Rock---Skiffle",
    "Rock---Sludge Metal",
    "Rock---Soft Rock",
    "Rock---Southern Rock",
    "Rock---Space Rock",
    "Rock---Speed Metal",
    "Rock---Stoner Rock",
    "Rock---Surf",
    "Rock---Swamp Pop",
    "Rock---Symphonic Rock",
    "Rock---Technical Death Metal",
    "Rock---Thrash",
    "Rock---Twist",
    "Rock---Viking Metal",
    "Rock---Yé-Yé",
    "Stage & Screen---Musical",
    "Stage & Screen---Score",
    "Stage & Screen---Soundtrack",
    "Stage & Screen---Theme",
]  # 519 classes — Discogs style taxonomy (MAEST)


def _compute_mel_from_signal(y: np.ndarray) -> np.ndarray:
    """Compute log-compressed mel spectrogram from a pre-loaded signal.

    IO-free: operates on an already-loaded 16 kHz mono waveform.
    Matches Essentia's TensorflowInputMusiCNN preprocessing:
    - 96 mel bands, n_fft=512, hop_length=256, fmax=8000 Hz
    - log(10000 * mel + 1)

    Returns:
        ndarray of shape (96, T) — float32
    """
    mel = librosa.feature.melspectrogram(
        y=y,
        sr=TRAIT_SAMPLE_RATE,
        n_fft=512,
        hop_length=256,
        n_mels=96,
        fmax=8000,
        norm=None,
        power=1.0,  # amplitude (not power=2.0) to match Essentia TensorflowInputMusiCNN
        htk=False,
    )
    return np.log(10000.0 * mel + 1.0).astype(np.float32)


def compute_mel_spectrogram(audio_path: str) -> np.ndarray:
    """Load audio and compute log-compressed mel spectrogram.

    Matches Essentia's TensorflowInputMusiCNN preprocessing:
    - 16 kHz mono
    - 96 mel bands, n_fft=512, hop_length=256, fmax=8000 Hz
    - log(10000 * mel + 1)

    Returns:
        ndarray of shape (96, T) — float32
    """
    y, _ = librosa.load(audio_path, sr=TRAIT_SAMPLE_RATE, mono=True)
    return _compute_mel_from_signal(y)


def _patch_mel_for_effnet(mel: np.ndarray) -> np.ndarray:
    """Slice mel spectrogram into overlapping EffNet input windows.

    EffNet ONNX expects shape (batch, time_frames=128, mel_bands=96).
    mel is (96, T) so each patch is mel[:, start:start+128].T → (128, 96).

    Args:
        mel: (96, T) mel spectrogram

    Returns:
        ndarray of shape (N, 128, 96) — float32
    """
    _, T = mel.shape
    if T < _EFFNET_FRAMES:
        mel = np.pad(mel, ((0, 0), (0, _EFFNET_FRAMES - T)))
        T = _EFFNET_FRAMES

    patches = []
    for start in range(0, T - _EFFNET_FRAMES + 1, _EFFNET_HOP):
        patch = mel[:, start : start + _EFFNET_FRAMES].T  # (128, 96)
        patches.append(patch)

    return np.stack(patches, axis=0).astype(np.float32)  # (N, 128, 96)


def _patch_mel_for_maest(mel: np.ndarray) -> list:
    """Slice mel spectrogram into 30-second MAEST input windows.

    MAEST ONNX expects shape (1, 1876, 96) — batch_size is fixed at 1.
    mel is (96, T), so each patch is mel[:, start:start+1876].T → (1876, 96).

    Args:
        mel: (96, T) mel spectrogram

    Returns:
        list of ndarrays each of shape (1, 1876, 96) — float32
    """
    _, T = mel.shape
    if T < _MAEST_FRAMES:
        mel = np.pad(mel, ((0, 0), (0, _MAEST_FRAMES - T)))
        T = _MAEST_FRAMES

    patches = []
    for start in range(0, T - _MAEST_FRAMES + 1, _MAEST_HOP):
        patch = mel[:, start : start + _MAEST_FRAMES].T  # (1876, 96)
        patches.append(patch[np.newaxis, :, :].astype(np.float32))  # (1, 1876, 96)

    return patches


def _run_maest(session, mel: np.ndarray) -> np.ndarray:
    """Run standalone MAEST 519l backbone, returning mean 519-class genre probabilities.

    Requests only the 'activations' output (sigmoid genre predictions) to avoid
    computing the 12 intermediate layer embedding tensors that onnxruntime would
    otherwise materialise when output_names=None.

    Processes the mel in 30s patches (batch_size=1 each) and averages predictions.

    Returns:
        mean_genre_probs ndarray (519,)
    """
    patches = _patch_mel_for_maest(mel)
    input_name = session.get_inputs()[0].name

    all_probs = []
    for patch in patches:
        outputs = session.run(["activations"], {input_name: patch})
        all_probs.append(outputs[0].squeeze())  # (519,)

    return np.mean(all_probs, axis=0) if all_probs else np.zeros(519, dtype=np.float32)


def _run_effnet(session, mel: np.ndarray) -> np.ndarray:
    """Run EffNet backbone, returning mean embeddings.

    EffNet ONNX outputs:
      [0] activations  (batch, 400) — Discogs 400-class predictions (unused)
      [1] embeddings   (batch, 1280) — embedding vectors for classifier heads

    Returns:
        mean_embedding  ndarray (1280,)
    """
    patches = _patch_mel_for_effnet(mel)
    input_name = session.get_inputs()[0].name
    outputs = session.run(None, {input_name: patches})
    embeddings = outputs[1]  # (N, 1280)
    return embeddings.mean(axis=0)


def _run_classifier(session, embedding: np.ndarray) -> np.ndarray:
    """Run a classification head on a single mean embedding vector.

    Args:
        session: onnxruntime.InferenceSession for the classification head
        embedding: (1280,) mean embedding

    Returns:
        ndarray of probabilities (n_classes,)
    """
    input_name = session.get_inputs()[0].name
    x = embedding[np.newaxis, :].astype(np.float32)  # (1, 1280)
    output = session.run(None, {input_name: x})[0]  # (1, n_classes) predictions
    return output.squeeze()  # (n_classes,)


def _binary_prob(probs: np.ndarray) -> float:
    """P(positive class) from a 2-class Softmax or single Sigmoid output."""
    if probs.ndim == 0:
        return float(probs)
    if probs.shape[0] == 2:
        return float(probs[1])
    return float(probs[0])


def _multilabel_dict(probs: np.ndarray, labels: list) -> dict:
    """Build {label: probability} dict for entries above the threshold."""
    n = min(len(probs), len(labels))
    return {
        labels[i]: round(float(probs[i]), 4)
        for i in range(n)
        if float(probs[i]) >= TRAIT_PREDICTION_THRESHOLD
    }


class TraitExtractor:
    """Loads ONNX sessions once and computes all Phase I traits per track.

    Instantiate once per worker process; reuse across tracks. Classifier
    sessions that could not be loaded (missing/corrupt ONNX file) are stored
    as None, and the corresponding trait is returned as None in compute().
    """

    def __init__(self):
        self._effnet = model_manager.load_model("discogs-effnet-bsdynamic")
        # MAEST loaded with graceful degradation — genre will be None if it fails
        try:
            self._maest = model_manager.load_model(TRAIT_CLASSIFIER_MAEST)
        except (RuntimeError, KeyError) as exc:
            print(
                "Warning: could not load MAEST model '%s': %s — genre will be None"
                % (TRAIT_CLASSIFIER_MAEST, exc),
                flush=True,
            )
            self._maest = None
        self._classifiers = {}
        for name in TRAIT_CLASSIFIERS_EFFNET:
            try:
                self._classifiers[name] = model_manager.load_model(name)
            except (RuntimeError, KeyError) as exc:
                print(
                    "Warning: could not load classifier '%s': %s — trait will be None"
                    % (name, exc),
                    flush=True,
                )
                self._classifiers[name] = None

    def compute(self, audio_path: str) -> dict:
        """Compute all traits for an audio file.

        Returns a dict with keys matching TrackTrait columns. Traits whose
        classifier model failed to load are set to None.
        """
        y, _ = librosa.load(audio_path, sr=TRAIT_SAMPLE_RATE, mono=True)
        if len(y) == 0:
            raise ValueError("Audio file loaded with zero samples: %s" % audio_path)
        mel = _compute_mel_from_signal(y)

        effnet_emb = _run_effnet(self._effnet, mel)
        genre_probs = _run_maest(self._maest, mel) if self._maest is not None else None

        def _run(key):
            sess = self._classifiers.get(key)
            return _run_classifier(sess, effnet_emb) if sess is not None else None

        vi_probs = _run("voice_instrumental-discogs-effnet-1")
        dance_probs = _run("danceability-discogs-effnet-1")
        timbre_probs = _run("timbre-discogs-effnet-1")
        ac_el_probs = _run("nsynth_acoustic_electronic-discogs-effnet-1")
        tonal_probs = _run("tonal_atonal-discogs-effnet-1")
        reverb_probs = _run("nsynth_reverb-discogs-effnet-1")
        mood_probs = _run("mtg_jamendo_moodtheme-discogs-effnet-1")
        instr_probs = _run("mtg_jamendo_instrument-discogs-effnet-1")

        # librosa extras
        onset_env = librosa.onset.onset_strength(y=y, sr=TRAIT_SAMPLE_RATE)
        onset_frames = librosa.onset.onset_detect(
            onset_envelope=onset_env, sr=TRAIT_SAMPLE_RATE
        )
        duration_sec = len(y) / TRAIT_SAMPLE_RATE
        onset_density = (
            round(float(len(onset_frames) / duration_sec), 4)
            if duration_sec > 0
            else 0.0
        )
        if np.max(np.abs(y)) < 1e-10:
            spectral_flatness = 0.0
        else:
            _sf_raw = float(np.nanmean(librosa.feature.spectral_flatness(y=y)))
            spectral_flatness = round(
                min(_sf_raw, 1.0) if not np.isnan(_sf_raw) else 0.0, 6
            )

        return {
            "voice_instrumental": _binary_prob(vi_probs)
            if vi_probs is not None
            else None,
            "danceability": _binary_prob(dance_probs)
            if dance_probs is not None
            else None,
            "bright_dark": _binary_prob(timbre_probs)
            if timbre_probs is not None
            else None,
            "acoustic_electronic": _binary_prob(ac_el_probs)
            if ac_el_probs is not None
            else None,
            "tonal_atonal": _binary_prob(tonal_probs)
            if tonal_probs is not None
            else None,
            "reverb": _binary_prob(reverb_probs) if reverb_probs is not None else None,
            "onset_density": onset_density,
            "spectral_flatness": spectral_flatness,
            "mood_theme": _multilabel_dict(mood_probs, LABELS_MOOD_THEME)
            if mood_probs is not None
            else None,
            "genre": _multilabel_dict(genre_probs, LABELS_GENRE_DISCOGS519)
            if genre_probs is not None
            else None,
            "instruments": _multilabel_dict(instr_probs, LABELS_INSTRUMENT)
            if instr_probs is not None
            else None,
            "trait_version": TRAIT_VERSION,
        }
