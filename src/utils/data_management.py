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
