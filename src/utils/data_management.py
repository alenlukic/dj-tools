from copy import deepcopy


def parse_title(title):
    """ Parses track title and returns formatted track title and featured artist name, if any. """

    featured = None
    segments = title.split(' ')
    filtered_segments = []

    i = 0
    n = len(segments)
    open_paren_found = False
    while i < n:
        segment = segments[i]

        if '(' in segment:
            open_paren_found = True

        # Replace all instances of 'feat.' with 'ft.' inside the parenthetical phrase indicating mix type.
        # e.g. "(Hydroid feat. Santiago Nino Mix)" becomes "(Hydroid ft. Santiago Nino Mix)"
        segment_lowercase = segment.lower()
        if segment_lowercase == 'feat.' or segment_lowercase == 'ft.':
            if open_paren_found:
                filtered_segments.append('ft.')
                i += 1
            else:
                # If we haven't seen an open parentheses yet, then the featured artist's name is composed of all
                # words occuring before the parentheses. This heuristic works for MP3 files purchased on Beatport.
                featured = []
                for j in range(i + 1, n):
                    next_part = segments[j]
                    if '(' in next_part:
                        break
                    featured.append(next_part)
                featured = ' '.join(featured)
                i = j
        else:
            filtered_segments.append(segment.strip())
            i += 1

    # Get rid of "(Original Mix)" and "(Extended Mix)" as these are redundant phrases that unnecessarily lengthen
    # the file name.
    formatted_title = ' '.join(filtered_segments).replace('(Original Mix)', '').replace('(Extended Mix)', '')

    return formatted_title, featured


def consolidate_artist_aliases(filtered_artists, formatted_title):
    """ Consolidates artist aliases. """

    split_title = formatted_title.split()
    n = len(filtered_artists)
    m = len(split_title)

    canonical_artists = deepcopy(filtered_artists)
    print('Filtered artists: %s ' % str(canonical_artists))
    aliased_artists = []
    artists_to_remove = []

    for seg_index, segment in enumerate(split_title):
        if seg_index == 0 or seg_index == m - 1:
            continue

        prev_seg = split_title[seg_index - 1]
        next_seg = split_title[seg_index + 1]

        if segment == 'pres.':
            for i in range(n - 1):
                for j in range(i + 1, n):
                    first_artist = filtered_artists[i]
                    second_artist = filtered_artists[j]

                    if first_artist == prev_seg and second_artist == next_seg:
                        aliased_artists.append('%s pres. %s' % (first_artist, second_artist))
                        artists_to_remove.extend([first_artist, second_artist])
                    elif first_artist == next_seg and second_artist == prev_seg:
                        aliased_artists.append('%s pres. %s' % (second_artist, first_artist))
                        artists_to_remove.extend([first_artist, second_artist])

    print('Aliased artists: %s ' % str(aliased_artists))
    print('Artists to remove: %s ' % str(artists_to_remove))
    for artist in artists_to_remove:
        canonical_artists.remove(artist)

    canonical_artists.extend(aliased_artists)
    print('Canonical artists: %s ' % str(canonical_artists))

    return canonical_artists
